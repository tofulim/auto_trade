import json
import logging
import os
from datetime import datetime, timedelta

import requests
import yfinance as yf
from common.calc_business_day import is_ktc_business_day
from common.statistics import get_moving_averages, get_rsi, get_zscore
from const import PURCHASE, SELL, STAY
from curl_cffi import requests as curl_requests

logger = logging.getLogger("api_logger")


def prophesy_portfolio(**kwargs):
    """
    portfolio 내 종목들 경향을 예측하고 매매 의사 결정을 내린다.
    1. 주어진 종목들에 대한 경향 예측을 수행한다.
    - [(stock_symbol, behavior, diff_rate, d), ... , ]
    2. 매매 threshold를 만족하는 경우를 모아 반환한다.
    - xcom에 저장

    Returns:
        task_id (object): 분기 로직을 통해 결정되는 task id

    """
    portfolio_behavior_decisions = []

    # 0. db에서 Portfolio table을 가져온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({"get_all": True}),
    )
    portfolio_rows = response.json()
    kwargs["task_instance"].xcom_push(key="portfolio_rows", value=portfolio_rows)
    stock_symbol2month_budget = {row["stock_symbol"]: row["month_budget"] for row in portfolio_rows}
    stock_symbol2order_status = {row["stock_symbol"]: row["order_status"] for row in portfolio_rows}
    # 1. 주어진 종목들에 대한 경향 예측을 수행한다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/prophet',
        data=json.dumps({"stock_symbols": list(stock_symbol2month_budget.keys())}),
    )
    stock_symbol2prophecy = response.json()

    # 2. 매매 threshold를 만족하는 경우를 모아 반환한다.
    for stock_symbol, prophecy in stock_symbol2prophecy.items():
        stock_symbol_tz = stock_symbol
        stock_symbol = stock_symbol.split(".")[0]
        last_price, diff_rate = prophecy["last_price"], prophecy["diff_rate"]
        behavior, behavior_reason = _get_behavior(
            diff_rate=diff_rate,
            statistics=_get_statistics(stock_symbol=stock_symbol_tz),
            order_status=stock_symbol2order_status[stock_symbol],
            purchase_threshold=float(os.getenv("PURCHASE_THRESHOLD")),
            sell_threshold=float(os.getenv("SELL_THRESHOLD")),
        )
        portfolio_behavior_decisions.append(
            # (stock_symbol, behavior, diff_rate, month_budget, last_price)
            (stock_symbol, behavior, diff_rate, stock_symbol2month_budget[stock_symbol], last_price)
        )

        input_text = f"{stock_symbol}: {behavior} - {behavior_reason}"
        channel_id = os.getenv("DAILY_REPORT_CHANNEL")
        print(f"channel_id: {channel_id}")
        response = requests.post(
            url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/slackbot/send_message',
            data=json.dumps({"channel_id": channel_id, "input_text": input_text}),
        )

    kwargs["task_instance"].xcom_push(key="portfolio_behavior_decisions", value=portfolio_behavior_decisions)
    logger.info(f"portfolio_behavior_decisions: {portfolio_behavior_decisions}")

    return True


def _get_statistics(stock_symbol: str, n_days: int = 20):
    """주식 종목의 통계치를 가져온다.
    RSI, MA, ZSCORE를 반환한다.

    Args:
        stock_symbol (str): 주식 종목 심볼 (ex. 005930.KS)
        n_days (str): 통계 계산할 과거 영업일 수

    Returns:
        statistics (dict): 종목의 통계치

    """
    # end = datetime.now() + timedelta(days=1)
    session = curl_requests.Session(impersonate="chrome")
    price_df = yf.download(stock_symbol, session=session)

    day5_close_avg, day10_close_avg, day20_close_avg, day60_close_avg = get_moving_averages(price_df)
    statistics = {
        "rsi": get_rsi(target_df=price_df, n_days=n_days),
        "ma": {"day5": day5_close_avg, "day10": day10_close_avg, "day20": day20_close_avg, "day60": day60_close_avg},
        "zscore": get_zscore(target_df=price_df, n_days=n_days),
    }

    return statistics


def execute_decisions(**kwargs):
    """결정 수행
    portfolio 종목들에 대한 prophecies를 받아 매매를 수행한다.
    """
    # 0. 예약 주문 목록을 준비해놓는다. (예약 주문이 존재하는지 확인하고 존재한다면 취소하기 위함)
    rsvn_orders = _get_rsvn_orders()

    # 1. 앞서 구한 할당/구매 안한 포트폴리오 의사결정 가져오기
    portfolio_behavior_decisions = kwargs["task_instance"].xcom_pull(key="portfolio_behavior_decisions")
    logger.info(f"portfolio_behavior_decisions: {portfolio_behavior_decisions}")
    # 2. 결정 수행
    for portfolio_behavior_decision in portfolio_behavior_decisions:
        stock_symbol, behavior, _, month_budget, last_price = portfolio_behavior_decision
        ord_qty = int(month_budget // last_price)
        last_price = int(last_price)
        result = None
        if behavior == STAY:
            continue
        elif behavior == PURCHASE:
            if ord_qty > 0:
                # 이미 예약 주문을 넣어 놓은 상태라면 기존 예약 주문을 취소한다. (새로 예약 주문을 넣기 위해)
                check_rsvn_order_n_cancel(rsvn_orders=rsvn_orders, stock_symbol=stock_symbol)

                result = requests.post(
                    url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/buy',
                    data=json.dumps(
                        {
                            "stock_symbol": stock_symbol,
                            "ord_qty": ord_qty,
                            "ord_price": last_price,
                            "rsvn_ord_end_dt": _get_end_dt().strftime("%Y%m%d"),
                        }
                    ),
                )

                # 구매는 다음 DAG에서 수행하므로 distribute DAG에서는 예약금과 order_status를 변경한다
                update_dict = {"reserved_budget": ord_qty * last_price, "order_status": "O"}

                response = requests.put(
                    url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/put_fields?stock_symbol={stock_symbol}',
                    data=json.dumps(update_dict),
                )
                logger.info(
                    f"stock_symbol: {stock_symbol} - behavior {behavior}'s result has saved at db with {response.json()}"
                )

        elif behavior == SELL:
            if ord_qty > 0:
                result = requests.post(
                    url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/sell',
                    data=json.dumps({"stock_symbol": stock_symbol, "ord_qty": ord_qty, "ord_price": last_price}),
                )

        else:
            raise ValueError("behavior must one of (STAY | PURCHASE | SELL)")

        logger.info(f"stock_symbol: {stock_symbol} - behavior {behavior}'s result is {result.json()}")


def _get_rsvn_orders():
    """예약 주문 목록을 가져온다.
    1. db에서 Portfolio table을 가져온다.
    2. 예약 주문이 존재하는지 확인한다.
    3. 존재한다면 취소한다.
    4. 존재하지 않는다면 pass한다.

    Args:
        stock_symbol (str): 주식 종목 심볼 (ex. 005930)

    Returns:
        rsvn_orders (list): 예약 주문 목록

        ex. [{
            "rsvn_ord_seq": "4657",
            "rsvn_ord_ord_dt": "20250509",
            "rsvn_ord_rcit_dt": "20250422",
            "pdno": "368590",
            "ord_dvsn_cd": "01",
            "ord_rsvn_qty": "24",
            "tot_ccld_qty": "0",
            "cncl_ord_dt": "",
            "ord_tmd": "082113",
            "ctac_tlno": "",
            "rjct_rson2": "정상 처리 완료되었습니다.",
            "odno": "0000429300",
            "rsvn_ord_rcit_tmd": "200038",
            "kor_item_shtn_name": "RISE 미국나스닥100",
            "sll_buy_dvsn_cd": "02",
            "ord_rsvn_unpr": "18805",
            "tot_ccld_amt": "0",
            "loan_dt": "",
            "cncl_rcit_tmd": "",
            "prcs_rslt": "처리",
            "ord_dvsn_name": "현금매수",
            "tmnl_mdia_kind_cd": "31",
            "rsvn_end_dt": "20250522"
            }]
    """
    end = datetime.datetime.now() + datetime.timedelta(days=1)
    start = end.replace(day=1)

    # 이번달 전체 orders를 받아온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/get_orders',
        data=json.dumps({"rsvn_ord_start_dt": start.strftime("%Y%m%d"), "rsvn_ord_end_dt": end.strftime("%Y%m%d")}),
    )
    rsvn_orders = response.json()["output"]

    return rsvn_orders


def check_rsvn_order_n_cancel(rsvn_orders: list, stock_symbol: str):
    """예약 주문 확인 및 취소
    1. 예약 주문이 존재하는지 확인한다.
    2. 존재한다면 취소한다.
    3. 존재하지 않는다면 pass한다.

    신규 예약 주문이 기존 예약 주문 위에 쌓이는 현상을 방지한다.
    하나의 종목에 대해 여러 예약 주문이 쌓이는 현상은 발생하지 않도록 한다.

    Args:
        rsvn_orders (list): 예약 주문 목록
        stock_symbol (str): 주식 종목 심볼 (ex. 005930)
    """
    # 1. 예약 주문 내 해당 종목 확인
    rsvn_orders = list(filter(lambda rsvn_order: rsvn_order["pdno"] == stock_symbol, rsvn_orders))

    if len(rsvn_orders) > 0:
        # 2. 존재한다면 취소한다.
        for rsvn_order in rsvn_orders:
            result = requests.post(
                url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/rsvn_cancel',
                data=json.dumps({"rsvn_ord_seq": rsvn_order["rsvn_ord_seq"]}),
            )
            logger.info(f"cancel rsvn order {rsvn_order['rsvn_ord_seq']} - result {result.json()}")

    # 3. 존재하지 않는다면 pass한다.
    else:
        logger.info(f"no rsvn order exist for {stock_symbol}. pass cancel rsvn order")
        return None


def _get_end_dt():
    for days in range(30, 0, -1):
        candidate_end_dt = datetime.now() + timedelta(days=days)
        if is_ktc_business_day(execution_date=candidate_end_dt, is_next=False):
            end_dt = candidate_end_dt
            break

    return end_dt


def _get_behavior(
    diff_rate: float, statistics: dict, order_status: str, purchase_threshold: float, sell_threshold: float
):
    """행동 결정

    Args:
        diff_rate (float): 종목의 기울기를 의미한다. 동작 판별의 근거가 된다.
        statistics (dict): 종목의 통계치
        order_status (str): 매매 주문 상태
        purchase_threshold (float): 매수 기준점
        sell_threshold (float): 매도 기준점

    Returns:
        behavior (str): const에 정의된 행동 (PURCHASE | SELL | STAY) 중 하나이다.
        behavior_reason (str): 행동 결정의 근거를 설명한다.

    """
    behavior, behavior_reason = STAY, ""
    # 종목 상태가 예약 매수가 진행된 적이 없거나 실패한 상태일 때 수행한다.
    statisstics_behavior, model_behavior = STAY, STAY
    # 1. rsi, ma, zscore로 행동을 결정한다.
    if statistics["rsi"] >= 70 and statistics["ma"]["day5"] > statistics["ma"]["day20"] and statistics["zscore"] >= 1:
        statisstics_behavior = SELL
        behavior_reason += f"statistics {statistics} is overbought. it's time to sell"
    # 구매에는 보다 유연한 기준을 적용한다.
    elif (
        int(statistics["rsi"]) <= 40
        or statistics["ma"]["day5"] < statistics["ma"]["day20"]
        or statistics["zscore"] <= -1
    ):
        statisstics_behavior = PURCHASE
        behavior_reason += f"statistics {statistics} is oversold. it's time to buy"
    else:
        behavior_reason += f"statistics {statistics} is normal"

    # 2. meta prophet 모델의 예측값을 통해 행동을 결정한다.
    if diff_rate >= purchase_threshold:
        model_behavior = PURCHASE
        behavior_reason += f" | diff_rate {diff_rate} is over purchase_threshold {purchase_threshold}"
    elif diff_rate <= sell_threshold:
        model_behavior = SELL
        behavior_reason += f" | diff_rate {diff_rate} is under sell_threshold {sell_threshold}"
    else:
        model_behavior = STAY

    # 3. 최종 행동을 결정한다
    if order_status not in ["N", "F"]:
        behavior = STAY
    elif statisstics_behavior == PURCHASE or model_behavior == PURCHASE:
        behavior = PURCHASE
    elif statisstics_behavior == SELL and model_behavior == SELL:
        behavior = SELL
    else:
        behavior = STAY

    return behavior, behavior_reason
