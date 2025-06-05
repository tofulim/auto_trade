# create all이 있는 곳에 table import 문이 있어야 테이블을 자동생성한다.
from entity.asset import Asset  # noqa
from entity.portfolio import Portfolio  # noqa
from sqlmodel import SQLModel, create_engine


class Database:
    def __init__(self, db_name):
        self.engine = create_engine(f"sqlite:///{db_name}", encoding="utf-8")
        SQLModel.metadata.create_all(self.engine)
