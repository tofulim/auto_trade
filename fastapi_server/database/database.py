from sqlmodel import create_engine, SQLModel


class Database:
    def __init__(self, db_name):
        self.engine = create_engine(f"sqlite:///{db_name}")
        SQLModel.metadata.create_all(self.engine)
