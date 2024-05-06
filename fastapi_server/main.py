import os
import dotenv
import logging
import pandas as pd

from datetime import datetime
from fastapi import FastAPI, Request

from prophecy import ProphetModel
from trader import Trader
from fastapi_server.utils import initialize_api_logger


app = FastAPI(
    title="Auto Trade",
)
initialize_api_logger()

dotenv.load_dotenv(f"./config/prod.env")
prophet_model = ProphetModel()
trader = Trader(
    app_key=os.getenv("APP_KEY"),
    app_secret=os.getenv("APP_SECRET"),
    url_base=os.getenv("BASE_URL"),
    mode="PROD",
)


logger = logging.getLogger("api_logger")


@app.get("/update_token")
async def update_token(request: Request):
    token = trader.get_credential_access_token()
    trader.set_credential_access_token(token)

    logger.inform("Token updated", extra={"endpoint_name": request.url.path})

@app.get("/prophet")
async def prophet(request: Request):
    # load portfolio
    portfolio = pd.read_csv(os.getenv("PORTFOLIO_PATH"))
    stock_symbol2change_rate = prophet_model(portfolio, '2021-01-01', datetime.today().strftime('%Y-%m-%d'))

    logger.inform(f"stock_symbol2change_rate {stock_symbol2change_rate}", extra={"endpoint_name": request.url.path})

    return stock_symbol2change_rate


@app.post("/buy")
async def buy(request: Request, stock_symbole: str, ord_qty: int, ord_price: int):
    res = trader.buy_stock(
        stock_code=stock_symbole,
        ord_qty=str(ord_qty),
        ord_price=str(ord_price)
    )

    logger.inform(
        f"Buy stock {stock_symbole} {ord_qty} {ord_price} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path}
    )

    return res


@app.post("/cancel")
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


@app.post("/sell")
async def sell(request: Request, stock_symbole: str, ord_qty: int, ord_price: int):
    res = trader.sell_stock(
        stock_code=stock_symbole,
        ord_qty=str(ord_qty),
        ord_price=str(ord_price)
    )

    logger.inform(
        f"Sell stock {stock_symbole} {ord_qty} {ord_price} | Status {res['status_code']} | Error {res['error']}",
        extra={"endpoint_name": request.url.path}
    )

    return res
