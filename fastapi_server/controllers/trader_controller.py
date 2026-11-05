import logging
import os
from datetime import datetime, timedelta, timezone

import inject
from database.database import Database
from fastapi import APIRouter, Request
from prophecy import ProphetModel
from pydantic import BaseModel, Field
from repository.portfolio_repository_service import PortfolioRepositoryService
from slack import KISSlackBot
from trader import Trader

router = APIRouter(prefix="/v1/trader", tags=["Trader"])

db = inject.instance(Database)
portfolio_repository_service = inject.instance(PortfolioRepositoryService)
prophet_model = inject.instance(ProphetModel)
trader = inject.instance(Trader)
slack_bot = inject.instance(KISSlackBot)


logger = logging.getLogger("api_logger")


@router.get("/update_token")
async def update_token(request: Request):
    token = trader.get_credential_access_token()
    trader.set_credential_access_token(token)

    logger.inform("Token updated", extra={"endpoint_name": request.url.path})

    return True


class Prophet(BaseModel):
    stock_symbols: list = Field(default=[])


class Buy(BaseModel):
    stock_symbol: str
    ord_qty: int
    ord_price: int


class RsvnBuy(BaseModel):
    stock_symbol: str
    ord_qty: int
    ord_price: int
    rsvn_ord_end_dt: str


class Report(BaseModel):
    summary: str
    save_path: str


class Order(BaseModel):
    rsvn_ord_start_dt: str
    rsvn_ord_end_dt: str


@router.post("/prophet")
async def prophet(request: Request, prophet: Prophet):
    # load portfolio from db
    stock_rows = portfolio_repository_service.get(stock_symbols=prophet.stock_symbols)

    KST = timezone(timedelta(hours=9))
    end_datetime = datetime.now(KST)
    prophecies = prophet_model(stock_rows, "2021-01-01", end_datetime.strftime("%Y-%m-%d"))

    channel_id = os.getenv("DAILY_REPORT_CHANNEL")
    for stock_symbol, prophecy_dict in prophecies.items():
        fig_save_path = prophecy_dict.pop("fig_save_path", None)

        diff_rate = prophecy_dict["diff_rate"]
        color = "#ea602e" if diff_rate >= 0 else "#0660f2"
        last_price = prophecy_dict["last_price"]
        statistics = {"변화율": diff_rate, "금일 종가": last_price}

        response = slack_bot.post_attachment(
            channel_id=channel_id, color=color, title=stock_symbol, statistics=statistics
        )

        thread_ts = response["ts"]
        channel_id = response["channel"]
        # TODO: post file을 router로 빼서도 사용할 수 있도록 변경
        _ = slack_bot.post_file(
            channel_id=channel_id, thread_ts=thread_ts, file_path=fig_save_path, filename=f"prop_{stock_symbol}.jpg"
        )

    logger.inform(f"prophecies {prophecies}", extra={"endpoint_name": request.url.path})

    return prophecies


@router.post("/monthly_report")
async def monthly_report(request: Request, report: Report):
    channel_id = os.getenv("MONTHLY_REPORT_CHANNEL")

    fig_save_path = report.save_path
    text = report.summary
    response = slack_bot.post_message(channel_id=channel_id, text=text)

    thread_ts = response["ts"]
    channel_id = response["channel"]
    _ = slack_bot.post_file(
        channel_id=channel_id, thread_ts=thread_ts, file_path=fig_save_path, filename="monthly_report"
    )

    logger.inform(f"text {text} sended with {fig_save_path}", extra={"endpoint_name": request.url.path})

    return 200


@router.post("/buy")
async def buy(request: Request, buy: Buy):
    res = trader.buy_stock(
        stock_code=buy.stock_symbol,
        ord_qty=buy.ord_qty,
        ord_price=buy.ord_price,
        # rsvn_ord_end_dt=buy.rsvn_ord_end_dt,
        # 장전 시간외는 전날 종가를 사용하지만 공란으로 비우지말고 0을 넣으라고 하는데 그럼 안되고 일반 예약으로 해야 체결됨.
        # ord_price=0,
    )

    text = f"Buy stock {buy.dict()} | Status {res['status_code']} | output {str(res['output'])} | Error {res['error']}"
    if res["status_code"] == "200":
        _ = slack_bot.post_message(channel_id=os.getenv("TRADE_ALARM_CHANNEL"), text=text)

    logger.inform(text, extra={"endpoint_name": request.url.path})

    return res


@router.post("/rsvn_buy")
async def rsvn_buy(request: Request, rsvn_buy: RsvnBuy):
    res = trader.rsvn_stock(
        stock_code=rsvn_buy.stock_symbol,
        ord_qty=rsvn_buy.ord_qty,
        ord_price=rsvn_buy.ord_price,
        rsvn_ord_end_dt=rsvn_buy.rsvn_ord_end_dt,
        # 장전 시간외는 전날 종가를 사용하지만 공란으로 비우지말고 0을 넣으라고 하는데 그럼 안되고 일반 예약으로 해야 체결됨.
        # ord_price=0,
    )

    text = f"Buy stock {rsvn_buy.dict()} | Status {res['status_code']} | output {str(res['output'])} | Error {res['error']}"
    if res["status_code"] == "200":
        _ = slack_bot.post_message(channel_id=os.getenv("TRADE_ALARM_CHANNEL"), text=text)

    logger.inform(text, extra={"endpoint_name": request.url.path})

    return res


@router.post("/cancel_fix")
async def cancel(request: Request, ord_orgno: int, orgn_odno: int, method_code: str = "02", fix_price: str = "0"):
    res = trader.cancel_request(
        ord_orgno=str(ord_orgno), orgn_odno=str(orgn_odno), method_code=method_code, fix_price=fix_price
    )

    method_code = "정정" if method_code == "01" else "취소"
    logger.inform(
        f"Cancel order {ord_orgno} {orgn_odno} with method_code {method_code} and fix_price {fix_price} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path},
    )

    return res


@router.post("/rsvn_cancel")
async def rsvn_cancel(request: Request, rsvn_ord_seq: str):
    res = trader.cancel_rsvn_request(rsvn_ord_seq=rsvn_ord_seq)

    logger.inform(
        f"Cancel Reservation order of sequence {rsvn_ord_seq} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path},
    )

    return res


@router.post("/sell")
async def sell(request: Request, stock_symbol: str, ord_qty: int, ord_price: int):
    res = trader.sell_stock(stock_code=stock_symbol, ord_qty=ord_qty, ord_price=ord_price)

    logger.inform(
        f"Sell stock {stock_symbol} {ord_qty} {ord_price} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path},
    )

    return res


@router.post("/get_balance")
async def get_balance(request: Request):
    res = trader.get_balance()

    logger.inform(
        f"Current Assset is {res['output']} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path},
    )

    return res


@router.post("/get_holdings")
async def get_holdings(request: Request):
    """
    주식 잔고 및 보유 종목 상세를 가져온다.
    리밸런싱 등에 활용하기 위해 개별 종목 보유 현황과 계좌 평가 금액을 반환한다.

    Returns:
        dict:
            - holdings (list): 보유 종목 리스트 (pdno, prdt_name, hldg_qty, prpr, evlu_amt 등)
            - total_evlu_amt (int): 총 평가금액 (주식 평가금액 + 예수금)
            - prvs_rcdl_excc_amt (int): 전일 매매 확정 예수금 (D+2 결제 가능 금액)
    """
    res = trader.get_holdings()

    logger.inform(
        f"Current Holdings: {res['output']} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path},
    )

    return res


@router.post("/get_orders")
async def get_orders(request: Request, order: Order):
    res = trader.get_reserved_orders(rsvn_ord_start_dt=order.rsvn_ord_start_dt, rsvn_ord_end_dt=order.rsvn_ord_end_dt)

    logger.inform(
        f"get orders from {order.rsvn_ord_start_dt} - {order.rsvn_ord_end_dt} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path},
    )

    return res


@router.post("/inquire_psbl_rvsecncl")
async def inquire_psbl_rvsecncl(request: Request, inqr_dvsn_1: str, inqr_dvsn_2: str):
    res = trader.inquire_psbl_rvsecncl(inqr_dvsn_1=inqr_dvsn_1, inqr_dvsn_2=inqr_dvsn_2)

    logger.inform(
        f"get possible cancel quantity for {inqr_dvsn_1} {inqr_dvsn_2} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path},
    )

    return res
