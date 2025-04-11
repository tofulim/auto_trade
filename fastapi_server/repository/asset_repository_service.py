from sqlmodel import Session, select

from database.database import Database
from entity.asset import Asset


class AssetRepositoryService:
    def __init__(self, db: Database):
        self.db = db

    def add(self, asset: Asset):
        with Session(self.db.engine) as session:
            session.add(asset)
            session.commit()

    def get(self, stay_entity=False):
        with Session(self.db.engine) as session:
            statement = select(Asset)
            result = session.exec(statement).all()

        if stay_entity:
            return result
        else:
            return self._dump_models(result)

    def delete(self):
        with Session(self.db.engine) as session:
            assets = self.get(stay_entity=True)
            for asset in assets:
                session.delete(asset)
            session.commit()

    def update(self, update_number: int):
        with Session(self.db.engine) as session:
            statement = select(Asset)
            result = session.exec(statement).one()
            result.budget = update_number
            # session.add(result)
            session.commit()

    @staticmethod
    def _dump_models(models):
        if len(models) > 0:
            return [model.model_dump() for model in models]
        else:
            return []


if __name__ == "__main__":
    db = Database("./fastapi_server/database/auto_trade.db")
    # query = """
    # select * from portfolio
    # """
    # db.execute("CREATE TABLE IF NOT EXISTS stocks")
    # res = db.fetch(query)
    # print(res)

    prs = AssetRepositoryService(db)
    # res = prs.add(Asset(budget=1000))
    # res = prs.update(update_number=3000)
    # res = prs.delete()
    res = prs.get()
    print(res)
    # print(res[0].model_dump())
