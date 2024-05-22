import logging
import inject

from datetime import datetime
from fastapi import APIRouter, Request

from fastapi_server.database.database import Database
from fastapi_server.repository.portfolio_repository_service import PortfolioRepositoryService
from prophecy import ProphetModel
from trader import Trader


router = APIRouter(
    prefix="/v1/trader",
    tags=["Trader"],
)

db = inject.instance(Database)
portfolio_repository_service = inject.instance(PortfolioRepositoryService)
prophet_model = inject.instance(ProphetModel)
trader = inject.instance(Trader)


logger = logging.getLogger("api_logger")


@router.get("/update_token")
async def update_token(request: Request):
    token = trader.get_credential_access_token()
    trader.set_credential_access_token(token)

    logger.inform("Token updated", extra={"endpoint_name": request.url.path})


@router.get("/prophet")
async def prophet(request: Request):
    # load portfolio from db
    stock_rows = portfolio_repository_service.get_all()
    stock_symbol2change_rate = prophet_model(stock_rows, '2021-01-01', datetime.today().strftime('%Y-%m-%d'))

    logger.inform(f"stock_symbol2change_rate {stock_symbol2change_rate}", extra={"endpoint_name": request.url.path})

    return stock_symbol2change_rate


@router.post("/buy")
async def buy(request: Request, stock_symbol: str, ord_qty: int, ord_price: int):
    res = trader.buy_stock(
        stock_code=stock_symbol,
        ord_qty=str(ord_qty),
        ord_price=str(ord_price)
    )

    logger.inform(
        f"Buy stock {stock_symbol} {ord_qty} {ord_price} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path}
    )

    return res


@router.post("/cancel")
async def cancel(request: Request, ord_orgno: int, orgn_odno: int):
    res = trader.cancel_request(
        ord_orgno=str(ord_orgno),
        orgn_odno=str(orgn_odno),
    )

    logger.inform(
        f"Cancel order {ord_orgno} {orgn_odno} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path}
    )

    return res


@router.post("/sell")
async def sell(request: Request, stock_symbol: str, ord_qty: int, ord_price: int):
    res = trader.sell_stock(
        stock_code=stock_symbol,
        ord_qty=str(ord_qty),
        ord_price=str(ord_price)
    )

    logger.inform(
        f"Sell stock {stock_symbol} {ord_qty} {ord_price} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path}
    )

    return res
