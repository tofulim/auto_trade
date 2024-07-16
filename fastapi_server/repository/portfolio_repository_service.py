"""
Author: zed.ai
Reviewer:
2024.05.22
"""
from sqlmodel import Session, select

from fastapi_server.database.database import Database
from fastapi_server.entity.portfolio import Portfolio


class PortfolioRepositoryService:
    def __init__(self, db: Database):
        self.db = db

    def add(self, portfolio: Portfolio):
        with Session(self.db.engine) as session:
            session.add(portfolio)
            session.commit()

    def get(self, stock_symbol: str, stay_entity=False):
        with Session(self.db.engine) as session:
            statement = select(Portfolio).where(Portfolio.stock_symbol == stock_symbol)
            result = session.exec(statement).all()

        if stay_entity:
            return result
        else:
            return self._dump_models(result)

    def get_all(self, stay_entity=False):
        with Session(self.db.engine) as session:
            statement = select(Portfolio)
            result = session.exec(statement).all()

        if stay_entity:
            return result
        else:
            return self._dump_models(result)

    def delete(self, stock_symbol: str):
        with Session(self.db.engine) as session:
            portfolios = self.get(stock_symbol, stay_entity=True)
            for portfolio in portfolios:
                session.delete(portfolio)
            session.commit()

    def update(self, stock_symbol: str, portfolio: Portfolio):
        with Session(self.db.engine) as session:
            statement = select(Portfolio).where(Portfolio.stock_symbol == stock_symbol)
            result = session.exec(statement).one()
            result.stock_symbol = portfolio.stock_symbol
            result.country = portfolio.country
            result.ratio = portfolio.ratio
            result.month_purchase_flag = portfolio.month_purchase_flag
            result.updated_at = portfolio.updated_at
            # session.add(result)
            session.commit()

    @staticmethod
    def _dump_models(models):
        if len(models) > 0:
            # pydantic v>=2.7
            # return [model.model_dump() for model in models]
            # pydantic v<2.7
            return [model.dict() for model in models]
        else:
            return []


if __name__ == "__main__":
    db = Database("./fastapi_server/database/auto_trade.db")
    # query = """
    # select * from portfolio
    # """
    # db.execute("CREATE TABLE IF NOT EXISTS stocks")
    # res = db.fetch(query)
    # print(res)

    prs = PortfolioRepositoryService(db)
    # res = prs.add(Portfolio(stock_symbol="123121", country="US", ratio=0.5, accum_asset=1000))
    # res = prs.update("123126", Portfolio(stock_symbol="123126", country="ks", ratio=0.3, accum_asset=5000))
    # res = prs.delete("123124")
    res = prs.get_all()
    print(res)
    # print(res[0].model_dump())
