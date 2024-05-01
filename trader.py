import json
import os
import pandas as pd
import requests
import dotenv


class Trader:
    """
    한국투자증권의 트레이딩 API를 통해 매매하기 위해 필요한 method들이 포함된 클래스이다.
    인증 / 매입 / 매각 을 목적으로 한다.
    """
    def __init__(self, app_key: str, app_secret: str, url_base: str):
        """
        거래 API 초기화

        Args:
            app_key (str): APP KEY
            app_secret (str): APP_SECRET
            url_base (str): 한투 api base url 실제/모의 투자 포트는 별도로 설정해야함
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.url_base = url_base

        self.headers = {"content-type": "application/json"}

        self.access_token = None

        self.portfolio_path = os.getenv("PORTFOLIO_PATH")

    @staticmethod
    def get_port_by_mode(mode: str):
        if mode == "PROD":
            return os.getenv("PROD_PORT")
        else:
            return os.getenv("DEV_PORT")

    def get_credential_access_token(self, mode: str = "PROD"):
        """
        get method로 호출하는 API 요청에 필요한 access token을 받아온다.

        Args:
            mode (str):  (PROD | DEV)

        Returns:
            status_code (int): 200

        """
        api = "oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        port = self.get_port_by_mode(mode=mode)

        response = requests.post(
            url=f"{self.url_base}:{port}/{api}",
            headers=self.headers,
            data=json.dumps(body)
        )

        self.access_token = response.json()["access_token"]

        return 200

    def hashkey(self, datas: dict, mode: str = "PROD"):
        """
        post 요청을 안전하게 암호화하여 통신하기 위해 hashkey를 활용한다.

        Args:
            datas (dict): 전달하고자 하는 data
            mode (str): PROD/DEV

        Returns:
            hashkey (str)

        """
        api = "uapi/hashkey"
        headers = {
            'content-Type': 'application/json',
            'appKey': self.app_key,
            'appSecret': self.app_secret,
        }
        port = self.get_port_by_mode(mode=mode)

        response = requests.post(
            url=f"{self.url_base}:{port}/{api}",
            headers=headers,
            data=json.dumps(datas)
        )
        hashkey = response.json()["HASH"]

        return hashkey

    # 이미 token을 발급받은 경우 토큰을 해당 토큰으로 설정한다.
    def set_credential_access_token(self, access_token: str):
        self.access_token = access_token


    # 종가 기준으로 지정가 구매. 해당 stock의 accum
    def buy_stock(self, stock_code: str, ord_qty: int, ord_price: str):
        api = "uapi/domestic-stock/v1/trading/order-cash"

        data = {
            # 계좌번호
            "CANO": os.getenv("ACCOUNT_FRONT"),
            "ACNT_PRDT_CD": os.getenv("ACCOUNT_REAR"),
            # 종목번호
            "PDNO": stock_code,
            # 주문구분 - 지정가(00), 시장가(01)
            "ORD_DVSN": "00",
            # 주문 수량
            "ORD_QTY": ord_qty,
            # 주문 단가
            "ORD_UNPR": ord_price,
        }

    # (code, country, ratio, accum_assets) csv 파일을 읽어 반환한다.
    def get_portfolio(self):
        portfolio_df = pd.read_csv(self.portfolio_path)
        return portfolio_df


if __name__ == "__main__":
    dotenv.load_dotenv("./config/config.env")

    print(os.getenv("APP_KEY"))
    trader = Trader(
        app_key=os.getenv("APP_KEY"),
        app_secret=os.getenv("APP_SECRET"),
        url_base=os.getenv("BASE_URL"),
    )

    res = trader.get_credential_access_token()
    print(f"res : {res}")
    print(trader.access_token)
