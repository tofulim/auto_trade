from datetime import datetime, timedelta

from sqlmodel import SQLModel, Field


def get_default_updated_at():
    return datetime.utcnow() + timedelta(hours=9)


class PortfolioBase(SQLModel):
    stock_symbol: str
    country: str
    ratio: float
    month_purchase_flag: bool = Field(default=False, nullable=False)
    updated_at: datetime = Field(default_factory=get_default_updated_at, nullable=False)


class Portfolio(PortfolioBase, table=True):
    __tablename__ = "portfolio"
    id: int = Field(default=None, primary_key=True)
