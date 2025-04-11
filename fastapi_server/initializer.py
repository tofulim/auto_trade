import os
import inject
from database.database import Database
from repository.asset_repository_service import AssetRepositoryService
from repository.portfolio_repository_service import PortfolioRepositoryService
from prophecy import ProphetModel
from slack import KISSlackBot
from trader import Trader


class Initializer:
    def __init__(self):
        self._configure()

    def _configure(self):
        inject.configure(self._bind)

    def _bind(self, binder):
        db = Database(os.getenv("DATABASE_PATH"))
        portfolio_repository_service = PortfolioRepositoryService(db=db)
        asset_repository_service = AssetRepositoryService(db=db)
        prophet_model = ProphetModel()
        trader = Trader(
            app_key=os.getenv("APP_KEY"),
            app_secret=os.getenv("APP_SECRET"),
            url_base=os.getenv("BASE_URL"),
            mode="PROD",
        )
        kis_slackbot = KISSlackBot(slack_bot_token=os.getenv("SLACK_BOT_TOKEN"))

        binder.bind(Database, db)
        binder.bind(PortfolioRepositoryService, portfolio_repository_service)
        binder.bind(AssetRepositoryService, asset_repository_service)
        binder.bind(ProphetModel, prophet_model)
        binder.bind(Trader, trader)
        binder.bind(KISSlackBot, kis_slackbot)
