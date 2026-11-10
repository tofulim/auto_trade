from sqlmodel import Field, SQLModel


class TakeProfit(SQLModel, table=True):
    """한 보유 구간에서 절반 익절의 목표 수량과 접수 상태를 보존한다."""

    stock_symbol: str = Field(primary_key=True)
    target_qty: int
    filled_qty: int = 0
    status: str = "ready"
    order_number: str = ""  # 예약주문순번
    order_date: str = ""
    order_qty: int = 0
    result: str = ""
