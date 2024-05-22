import logging
from http.client import HTTPException

import inject

from fastapi import APIRouter

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
def create_portfolio(portfolio: PortfolioBase):
    portfolio = Portfolio(**portfolio.dict())
    portfolio_repository_service.add(portfolio)

    return {"message": "Portfolio created successfully"}


@router.get("/get/{stock_symbol}")
def read_portfolio(stock_symbol: str):
    portfolio = portfolio_repository_service.get(stock_symbol=stock_symbol)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.put("/put/{stock_symbol}")
def update_portfolio(stock_symbol: str, portfolio: PortfolioBase):
    portfolio = Portfolio(**portfolio.dict())
    portfolio_repository_service.update(stock_symbol=stock_symbol, portfolio=portfolio)

    return {"message": "Portfolio updated successfully"}


@router.delete("/delete/{stock_symbol}")
def delete_portfolio(stock_symbol: str):
    portfolio = portfolio_repository_service.get(stock_symbol=stock_symbol)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    portfolio_repository_service.delete(stock_symbol=stock_symbol)

    return {"message": "Portfolio deleted successfully"}
