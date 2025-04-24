import json
import logging
import os
from datetime import datetime, timedelta

import requests
import yfinance as yf
from common.calc_business_day import is_ktc_business_day
from common.statistics import get_moving_averages, get_rsi, get_zscore
from const import PURCHASE, SELL, STAY

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
    price_df = yf.download(stock_symbol)

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
