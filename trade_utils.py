import os
import requests
import dotenv


class TradeAPI:
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

        self.headers = {"content-type":"application/json"}

    def get_credential_auth_key(self,):
        url = "oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }







if __name__ == "__main__":
    dotenv.load_dotenv("./config/config.env")
