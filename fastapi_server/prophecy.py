"""
주어진 종목들에 대한 종가 예측을 진행한다.
해당 종목이 향후 n일 동안 보여줄 종가를 예측하고 현재대비 증감율을 반환한다.

사용 전략의 예시는 다음과 같다.
- 증감이 0.5% 이상이면 매수, 0.5% 이하이면 매도를 진행한다.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List

import yfinance as yf
from prophet import Prophet
from utils import ensure_directory_exists


class ProphetModel:
    """
    Prophet 모델을 사용하여 주식 종가 예측을 진행한다.
    여러개의 주식에 대해 경향성을 예측하고 변화율을 반환한다.
    """

    def __init__(self):
        self.periods = int(os.getenv("PERIOD_DAYS"))

    def __call__(self, stock_rows: List[dict], start_date: str, end_date: str, save_plot: bool = True):
        """
        주식 데이터를 불러와서 Prophet 모델을 학습시킨다.

        Args:
            stock_rows (List[dict]): db 포트폴리오 데이터
            start_date (str): 사용할 시작 날짜 ex. '2021-01-01'
            end_date (str): 사용할 종료 날짜 ex. '2021-12-31'

        Returns:
            prophecies (dict): 종가 경향 변화율 예측 결과와 마지막 종가를 담은 dict (key: 종목명, value: {변화율, 종가})
        """
        prophecies = {}
        for stock_row in stock_rows:
            if stock_row["country"] != "us":
                # 한국 주식의 경우 종목코드 뒤에 .KS를 붙여준다.
                stock_symbol = f"{stock_row['stock_symbol']}.{stock_row['country'].upper()}"
            else:
                stock_symbol = stock_row["stock_symbol"]

            self.model = Prophet()
            self.fit(stock_symbol, start_date, end_date)
            forecast = self.predict(periods=self.periods)

            diff_rate = self.get_diff_rate(forecast, periods=self.periods)
            last_price = self.stock_data["y"][-1]
            prophecies[stock_symbol] = {"diff_rate": diff_rate, "last_price": last_price}
            # 경향 예측 그래프를 저장한다.
            if save_plot:
                fig = self.plot(forecast)
                # TODO: 추후 경로 지정
                save_path = f"/shared/reports/{datetime.now().strftime('%Y-%m-%d')}_{stock_symbol}.png"
                ensure_directory_exists(save_path)
                fig.savefig(save_path)
                prophecies[stock_symbol]["fig_save_path"] = save_path

        return prophecies

    @staticmethod
    def get_diff_rate(forecast, periods: int):
        """
        변화율을 계산한다.
        오늘로부터 n일 후의 종가와 n일 전의 종가를 비교하여 변화율을 계산한다.

        Args:
            forecast (object): Prophet 모델의 예측 결과
            periods (int): 예측한 기간

        Returns:
            diff_rate (float): 0-1 사이의 float 변화율에 100을 곱한 퍼센테이지 값

        """
        yhats = forecast["yhat"].values
        diff_rate = round(((yhats[-1] - yhats[-periods]) / yhats[-periods]) * 100, 2)
        return diff_rate

    def fit(self, stock_symbol: str, start_date: str, end_date: str):
        """
        주식 데이터를 불러와서 Prophet 모델을 학습시킨다.

        Args:
            stock_symbol (str): yfinance에서 사용하는 주식 종목 심볼
            start_date (str): 사용할 시작 날짜 ex. '2021-01-01'
            end_date (str): 사용할 종료 날짜 ex. '2021-12-31'
        """
        self.stock_symbol = stock_symbol
        self.start_date = start_date
        KST = timezone(timedelta(hours=9))
        end_datetime = datetime.now(KST) + timedelta(days=1)
        self.end_date = end_datetime.strftime("%Y-%m-%d")

        self.stock_data = yf.download(stock_symbol, start=start_date, end=self.end_date)
        self.stock_data = self.stock_data.asfreq("B")

        # 종가 기준
        self.stock_data["y"] = self.stock_data["Close"]
        self.stock_data["ds"] = self.stock_data.index
        self.model.fit(self.stock_data)

    def predict(self, periods: int = 30):
        future = self.model.make_future_dataframe(periods=periods, freq="B")
        forecast = self.model.predict(future)

        return forecast

    def plot(self, forecast):
        fig = self.model.plot(forecast, include_legend=True)
        return fig


if __name__ == "__main__":
    import dotenv

    dotenv.load_dotenv("/home/ubuntu/zed/auto_trade/config/prod.env")
    pf = ProphetModel()

    stock_rows = [{"country": "ks", "accum_asset": 5000.0, "stock_symbol": "453810", "id": 1, "ratio": 0.3}]

    cr = pf(stock_rows, "2021-01-01", datetime.today().strftime("%Y-%m-%d"))
    print(f"종가 변화율 예측 결과: {cr}")
