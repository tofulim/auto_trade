import os

import dotenv

from trader import Trader


dotenv.load_dotenv(f"./config/PROD.env")

trader = Trader(
    app_key=os.getenv("APP_KEY"),
    app_secret=os.getenv("APP_SECRET"),
    url_base=os.getenv("BASE_URL"),
    mode="PROD",
)


def update_kis_key():
    origin_key = os.getenv("KIS_ACCESS_TOKEN", None)
    token = trader.get_credential_access_token()
    trader.set_credential_access_token(token)

    print(f"key has been updated from {origin_key} to {token}")
