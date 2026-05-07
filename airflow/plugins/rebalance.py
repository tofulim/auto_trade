"""
리밸런싱 플러그인

매일 Slack 채널을 확인하여 리밸런싱 요청이 있는 경우 포트폴리오를 리밸런싱한다.

리밸런싱 알고리즘:
1. Slack 채널에서 오늘 리밸런싱 요청 메시지 확인
2. 현재 보유 종목 및 평가금액 조회 (한투 API)
3. DB에서 포트폴리오 목표 비율 조회
4. 각 종목의 목표 금액 산정
5. 초과 보유 종목 매도 (비싸진 것 먼저 팔기)
6. 부족 보유 종목 매수 (싸진 것 사기, 미수 없이 가용 예수금 내에서)

주의: 매도가 이루어져도 D+2에 예수금이 생기기 때문에
      매도 당일에는 해당 대금으로 매수 불가. 기존 예수금 내에서만 매수한다.
"""

import json
import os
from datetime import datetime, timedelta

import requests
import yfinance as yf
from common.calc_business_day import is_ktc_business_day
from common.logger_config import setup_logger
from curl_cffi import requests as curl_requests

logger = setup_logger(__name__)


def check_rebalance_request(**kwargs):
    """
    Slack 채널에서 오늘 리밸런싱 요청 메시지가 있는지 확인한다.

    리밸런싱 요청이 있으면 'execute_rebalance_sells' task를 반환한다.
    없으면 'task_empty' task를 반환한다.

    Returns:
        next_task_name (str): 다음에 수행할 task 이름
    """
    response = requests.get(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/slackbot/check_rebalance_request'
    )
    result = response.json()

    if result.get("requested", False):
        logger.info("Rebalance request found. Running rebalancing.")
        return "execute_rebalance_sells"
    else:
        logger.info("No rebalance request found. Skipping rebalancing.")
        return "task_empty"


def execute_rebalance_sells(**kwargs):
    """
    포트폴리오 리밸런싱을 위한 매도를 수행한다.

    1. 현재 보유 종목 및 평가금액 조회
    2. 포트폴리오 목표 비율 조회
    3. 전체 자산 대비 각 종목의 목표 금액 산정
    4. 초과 보유 종목 매도 주문 실행

    Returns:
        status (bool): 수행 여부
    """
    # 1. 현재 보유 종목 및 평가금액 조회
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/get_holdings'
    )
    holdings_response = response.json()
    holdings_data = holdings_response["output"]

    holdings_list = holdings_data["holdings"]
    total_evlu_amt = holdings_data["total_evlu_amt"]

    # pdno(종목코드) -> 보유 정보 매핑
    pdno2holding = {h["pdno"]: h for h in holdings_list}

    # xcom에 저장 (매수 task에서 재사용)
    kwargs["task_instance"].xcom_push(key="holdings_data", value=holdings_data)

    # 2. 포트폴리오 목표 비율 조회
    portfolio_rows = _get_portfolio_rows()
    if not portfolio_rows:
        logger.info("No portfolio found. Skipping rebalancing.")
        return False

    kwargs["task_instance"].xcom_push(key="portfolio_rows", value=portfolio_rows)

    # 3. 각 종목의 목표 금액 및 현재 금액 산정
    sells = []
    report_lines = [
        "[리밸런싱 매도 리포트]",
        f"총 평가금액: {total_evlu_amt:,}원",
        "",
    ]

    for row in portfolio_rows:
        stock_symbol = row["stock_symbol"]
        ratio = float(row["ratio"])

        target_value = int(total_evlu_amt * ratio)

        holding = pdno2holding.get(stock_symbol, {})
        current_value = int(holding.get("evlu_amt", 0))
        current_price = int(holding.get("prpr", 0))
        hldg_qty = int(holding.get("hldg_qty", 0))

        diff = current_value - target_value

        report_lines.append(
            f"{stock_symbol}: 목표 {target_value:,}원 (비율 {ratio * 100:.1f}%) | "
            f"현재 {current_value:,}원 | 차이 {diff:,}원"
        )

        # 초과 보유 시 매도 대상 추가
        if diff > 0 and current_price > 0:
            sell_qty = diff // current_price
            if sell_qty > 0 and sell_qty <= hldg_qty:
                sells.append(
                    {
                        "stock_symbol": stock_symbol,
                        "sell_qty": sell_qty,
                        "current_price": current_price,
                    }
                )

    report_lines.append("")

    # 4. 매도 주문 실행
    for sell in sells:
        stock_symbol = sell["stock_symbol"]
        sell_qty = sell["sell_qty"]
        current_price = sell["current_price"]

        result = requests.post(
            url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/sell',
            params={"stock_symbol": stock_symbol, "ord_qty": sell_qty, "ord_price": current_price},
        )
        result_json = result.json()

        sell_amount = sell_qty * current_price
        status = result_json.get("status_code", "unknown")
        report_lines.append(
            f"매도 주문: {stock_symbol} {sell_qty}주 @ {current_price:,}원 "
            f"(총 {sell_amount:,}원) | 결과: {status}"
        )
        logger.info(f"Sell order for {stock_symbol}: {sell_qty} shares @ {current_price}. Result: {result_json}")

    if not sells:
        report_lines.append("매도할 종목 없음")

    # Slack 리포트
    channel_id = os.getenv("REBALANCE_REQUEST_CHANNEL")
    requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/slackbot/send_message',
        data=json.dumps({"channel_id": channel_id, "input_text": "\n".join(report_lines)}),
    )

    return True


def execute_rebalance_buys(**kwargs):
    """
    포트폴리오 리밸런싱을 위한 매수를 수행한다.

    매도가 이루어져도 D+2에 예수금이 생기기 때문에,
    현재 가용한 예수금(prvs_rcdl_excc_amt) 내에서만 매수한다.
    가용 예수금이 필요 매수금보다 부족한 경우 부족분 비율에 따라 비례 배분하여 매수한다.

    1. 앞서 저장된 보유 현황 및 포트폴리오 정보 가져오기
    2. 최신 예수금(D+2) 재조회
    3. 각 종목의 부족분 계산
    4. 가용 예수금 내에서 비율에 따라 매수 주문 실행

    Returns:
        status (bool): 수행 여부
    """
    # 1. 앞서 저장된 데이터 가져오기
    holdings_data = kwargs["task_instance"].xcom_pull(key="holdings_data")
    portfolio_rows = kwargs["task_instance"].xcom_pull(key="portfolio_rows")

    holdings_list = holdings_data["holdings"]
    total_evlu_amt = holdings_data["total_evlu_amt"]

    pdno2holding = {h["pdno"]: h for h in holdings_list}

    # 2. 최신 예수금 재조회
    # 주의: D+2 결제 특성상 이번 매도 대금은 당일 예수금에 반영되지 않는다.
    #       조회되는 예수금은 이전에 이미 결제 완료된 가용 현금이다.
    balance_response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/get_balance'
    )
    balance_data = balance_response.json()["output"]
    available_cash = int(balance_data.get("prvs_rcdl_excc_amt", 0))

    # 3. 부족 종목 및 필요 금액 계산
    buys = []

    for row in portfolio_rows:
        stock_symbol = row["stock_symbol"]
        ratio = float(row["ratio"])
        country = row.get("country", "ks")

        target_value = int(total_evlu_amt * ratio)

        holding = pdno2holding.get(stock_symbol, {})
        current_value = int(holding.get("evlu_amt", 0))
        current_price = int(holding.get("prpr", 0))

        # 보유 종목이 없는 경우 yfinance로 현재가 조회
        if current_price == 0:
            current_price = _get_current_price_from_yfinance(stock_symbol, country)

        needed_value = target_value - current_value

        if needed_value > 0 and current_price > 0:
            buys.append(
                {
                    "stock_symbol": stock_symbol,
                    "needed_value": needed_value,
                    "current_price": current_price,
                }
            )

    total_needed = sum(b["needed_value"] for b in buys)

    report_lines = [
        "[리밸런싱 매수 리포트]",
        f"가용 예수금: {available_cash:,}원 | 필요 매수금: {total_needed:,}원",
        "",
    ]

    # 가용 예수금이 없거나 필요 매수금이 없으면 매수 생략
    if available_cash <= 0 or total_needed <= 0 or not buys:
        report_lines.append("매수할 종목 없음")
        channel_id = os.getenv("REBALANCE_REQUEST_CHANNEL")
        requests.post(
            url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/slackbot/send_message',
            data=json.dumps({"channel_id": channel_id, "input_text": "\n".join(report_lines)}),
        )
        return True

    # 가용 예수금이 필요 매수금보다 부족한 경우 비례 배분
    scale_factor = min(1.0, available_cash / total_needed)

    if scale_factor < 1.0:
        report_lines.append(
            f"가용 예수금 부족 → 비례 배분 (실제 매수 비율: {scale_factor * 100:.1f}%)"
        )

    # 예약주문 종료일 (향후 30일 내 가장 먼 영업일)
    end_dt = _get_end_dt()

    # 4. 매수 주문 실행
    for buy in buys:
        stock_symbol = buy["stock_symbol"]
        needed_value = buy["needed_value"]
        current_price = buy["current_price"]

        adjusted_buy_value = int(needed_value * scale_factor)
        buy_qty = adjusted_buy_value // current_price

        if buy_qty <= 0:
            report_lines.append(f"매수 제외: {stock_symbol} (매수 수량 0주)")
            continue

        result = requests.post(
            url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/buy',
            data=json.dumps(
                {
                    "stock_symbol": stock_symbol,
                    "ord_qty": buy_qty,
                    "ord_price": current_price,
                    "rsvn_ord_end_dt": end_dt.strftime("%Y%m%d"),
                }
            ),
        )
        result_json = result.json()

        buy_amount = buy_qty * current_price
        status = result_json.get("status_code", "unknown")
        report_lines.append(
            f"매수 주문: {stock_symbol} {buy_qty}주 @ {current_price:,}원 "
            f"(총 {buy_amount:,}원) | 결과: {status}"
        )
        logger.info(f"Buy order for {stock_symbol}: {buy_qty} shares @ {current_price}. Result: {result_json}")

    # Slack 리포트
    channel_id = os.getenv("REBALANCE_REQUEST_CHANNEL")
    requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/slackbot/send_message',
        data=json.dumps({"channel_id": channel_id, "input_text": "\n".join(report_lines)}),
    )

    return True


def _get_portfolio_rows():
    """DB에서 포트폴리오 rows를 가져온다."""
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({"get_all": True}),
    )
    return response.json()


def _get_current_price_from_yfinance(stock_symbol: str, country: str) -> int:
    """yfinance를 통해 종목의 현재가를 가져온다.

    Args:
        stock_symbol (str): 종목코드 (ex. 453810)
        country (str): 국가 코드 (ex. ks, us)

    Returns:
        int: 현재가 (조회 실패 시 0)
    """
    if country != "us":
        yf_symbol = f"{stock_symbol}.{country.upper()}"
    else:
        yf_symbol = stock_symbol

    try:
        session = curl_requests.Session(impersonate="chrome")
        ticker = yf.Ticker(yf_symbol, session=session)
        hist = ticker.history(period="1d")

        if len(hist) > 0:
            return int(hist["Close"].iloc[-1])
        else:
            logger.info(f"No price data found for {yf_symbol}")
            return 0

    except Exception as e:
        logger.info(f"Failed to get price for {yf_symbol}: {e}")
        return 0


def _get_end_dt() -> datetime:
    """예약 주문 종료일을 구한다. (향후 30일 내 가장 먼 영업일)"""
    for days in range(30, 0, -1):
        candidate_end_dt = datetime.now() + timedelta(days=days)
        if is_ktc_business_day(execution_date=candidate_end_dt, is_next=False):
            return candidate_end_dt

    logger.info("No business day found within 30 days. Using tomorrow as fallback.")
    return datetime.now() + timedelta(days=1)
