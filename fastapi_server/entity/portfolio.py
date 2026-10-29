from datetime import datetime, timedelta

from sqlmodel import Field, SQLModel

LEGACY_ORDER_STATUSES = {
    "N": "NOT_ORDERED",
    "O": "RESERVATION_ACCEPTED",
    "F": "UNPROCESSED",
    "S": "PROCESSED",
    "W": "RESULT_PENDING",
    "E": "PROCESSING_ERROR",
}


def normalize_order_status(order_status: str) -> str:
    """기존 알파벳 주문 상태를 의미가 명확한 저장 값으로 변환한다.

    Args:
        order_status: 기존 코드 또는 새 주문 상태.

    Returns:
        기존 코드에 대응하는 새 상태 또는 입력된 상태.
    """
    return LEGACY_ORDER_STATUSES.get(order_status, order_status)


def get_default_updated_at():
    return datetime.utcnow() + timedelta(hours=9)


class PortfolioBase(SQLModel):
    stock_symbol: str
    ratio: float
    country: str = Field(default="ks", nullable=False)
    month_purchase_flag: bool = Field(default=False, nullable=False)
    month_budget: int = Field(default=0, nullable=False)
    reserved_budget: int = Field(default=0, nullable=False)
    order_status: str = Field(default="NOT_ORDERED", nullable=False)
    updated_at: datetime = Field(default_factory=get_default_updated_at, nullable=False)


class Portfolio(PortfolioBase, table=True):
    __tablename__ = "portfolio"
    id: int = Field(default=None, primary_key=True)
