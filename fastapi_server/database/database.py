from sqlmodel import create_engine, SQLModel
# create all이 있는 곳에 table import 문이 있어야 테이블을 자동생성한다.
from fastapi_server.entity.asset import Asset # noqa
from fastapi_server.entity.portfolio import Portfolio # noqa


class Database:
    def __init__(self, db_name):
        self.engine = create_engine(f"sqlite:///{db_name}", encoding='utf-8')
        SQLModel.metadata.create_all(self.engine)
