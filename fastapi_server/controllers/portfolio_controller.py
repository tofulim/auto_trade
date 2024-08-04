import logging
from http.client import HTTPException
from typing import Union

import inject

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from fastapi_server.database.database import Database
from fastapi_server.entity.portfolio import Portfolio, PortfolioBase
from fastapi_server.repository.portfolio_repository_service import PortfolioRepositoryService

router = APIRouter(
    prefix="/v1/portfolio",
    tags=["Portfolio"],
)

db = inject.instance(Database)
portfolio_repository_service = inject.instance(PortfolioRepositoryService)


logger = logging.getLogger("api_logger")


# CRUD 엔드포인트 구성
@router.post("/add")
def create_portfolio(portfolio: PortfolioBase, request: Request):
    portfolio = Portfolio(**portfolio.dict())
    portfolio_repository_service.add(portfolio)

    logger.inform(f"Portfolio updated {portfolio}", extra={"endpoint_name": request.url.path})

    return {"message": "Portfolio created successfully"}


class ReadPortfolio(BaseModel):
    stock_symbols: list = Field(default=[])
    get_all: bool = False


@router.post("/get")
def read_portfolios(request: Request, read_portfolio: ReadPortfolio):
    if read_portfolio.get_all:
        portfolio = portfolio_repository_service.get_all()
    else:
        portfolio = portfolio_repository_service.get(stock_symbols=read_portfolio.stock_symbols)

    logger.inform(f"get Portfolio {portfolio}", extra={"endpoint_name": request.url.path})
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.put("/put/{stock_symbol}")
def update_portfolio(stock_symbol: str, portfolio: PortfolioBase, request: Request):
    portfolio = Portfolio(**portfolio.dict())
    portfolio_repository_service.update(stock_symbol=stock_symbol, portfolio=portfolio)

    logger.inform(f"Portfolio {stock_symbol} updated with {portfolio}", extra={"endpoint_name": request.url.path})
    return {"message": "Portfolio updated successfully"}


@router.put("/put_fields")
def update_portfolio_with_dict(stock_symbol: str, update_dict: dict, request: Request):
    portfolio_repository_service.update_fields(stock_symbol=stock_symbol, update_data=update_dict)

    logger.inform(f"Portfolio {stock_symbol} updated with update_dict{update_dict}", extra={"endpoint_name": request.url.path})
    return {"message": "Portfolio updated successfully"}


@router.delete("/delete/{stock_symbol}")
def delete_portfolio(stock_symbol: str, request: Request):
    portfolio = portfolio_repository_service.get(stock_symbols=[stock_symbol])
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    portfolio_repository_service.delete(stock_symbol=stock_symbol)
    logger.inform(f"Portfolio {stock_symbol} deleted", extra={"endpoint_name": request.url.path})

    return {"message": "Portfolio deleted successfully"}
