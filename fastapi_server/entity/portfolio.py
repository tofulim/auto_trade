from sqlmodel import SQLModel, Field


class PortfolioBase(SQLModel):
    stock_symbol: str
    country: str
    ratio: float
    accum_asset: float = 0


class Portfolio(PortfolioBase, table=True):
    __tablename__ = "portfolio"
    id: int = Field(default=None, primary_key=True)
