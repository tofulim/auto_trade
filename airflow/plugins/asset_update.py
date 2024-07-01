import os
import dotenv
import requests

from trader import Trader


dotenv.load_dotenv(f"./config/PROD.env")

trader = Trader(
    app_key=os.getenv("APP_KEY"),
    app_secret=os.getenv("APP_SECRET"),
    url_base=os.getenv("BASE_URL"),
    mode="PROD",
)


def get_balance():
    response_json = trader.inquire_balance()
    # 참조: https://apiportal.koreainvestment.com/apiservice/apiservice-domestic-stock-order#L_66c61080-674f-4c91-a0cc-db5e64e9a5e6
    output2 = response_json["output"]["output2"]
    current_asset = output2["dnca_tot_amt"]

    print(f"curr asset is {current_asset}")

    return current_asset
