# create all이 있는 곳에 table import 문이 있어야 테이블을 자동생성한다.
from entity.asset import Asset  # noqa
from entity.portfolio import LEGACY_ORDER_STATUSES, Portfolio
from sqlalchemy import update
from sqlmodel import SQLModel, create_engine


class Database:
    def __init__(self, db_name: str) -> None:
        """테이블을 준비하고 기존 주문 상태 코드를 변환한다.

        Args:
            db_name: SQLite 데이터베이스 파일 경로.
        """
        self.engine = create_engine(f"sqlite:///{db_name}", encoding="utf-8")
        SQLModel.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            for legacy_status, status in LEGACY_ORDER_STATUSES.items():
                connection.execute(
                    update(Portfolio).where(Portfolio.order_status == legacy_status).values(order_status=status)
                )
