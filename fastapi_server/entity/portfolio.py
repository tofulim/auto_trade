from datetime import datetime, timedelta

from sqlmodel import Field, SQLModel


def get_default_updated_at():
    return datetime.utcnow() + timedelta(hours=9)


class PortfolioBase(SQLModel):
    stock_symbol: str
    ratio: float
    country: str = Field(default="ks", nullable=False)
    month_purchase_flag: bool = Field(default=False, nullable=False)
    month_budget: int = Field(default=0, nullable=False)
    reserved_budget: int = Field(default=0, nullable=False)
    order_status: str = Field(default="N", nullable=False)
    updated_at: datetime = Field(default_factory=get_default_updated_at, nullable=False)


class Portfolio(PortfolioBase, table=True):
    __tablename__ = "portfolio"
    id: int = Field(default=None, primary_key=True)
