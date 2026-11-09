from sqlmodel import Field, SQLModel


class TradingSettings(SQLModel, table=True):
    """서버 재시작 후에도 유지되는 공통 매매 설정이다."""

    id: int = Field(default=1, primary_key=True)
    take_profit_threshold: float = 50.0
    purchase_threshold: float = 3.0
    sell_threshold: float = -25.0
    period_days: int = 30
