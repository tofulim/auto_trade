import datetime
import json
import logging
import os

import dotenv
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf

dotenv.load_dotenv("/opt/airflow/config/prod.env")
logger = logging.getLogger("api_logger")


def ensure_directory_exists(save_path: str):
    # 부모 디렉토리 경로를 가져옵니다.
    parent_directory = os.path.dirname(save_path)

    # 부모 디렉토리가 존재하는지 확인하고, 없으면 생성합니다.
    if not os.path.exists(parent_directory):
        os.makedirs(parent_directory)


def get_portfolio_rows():
    # 1. db에서 Portfolio table을 가져온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({"get_all": True}),
    )
    portfolio_rows = response.json()

    return portfolio_rows


def check_portfolio(next_task_name: str, **kwargs):
    """포트폴리오 투자
    1. db에서 Portfolio table을 가져온다.
        ex. [
                {'updated_at': '2024-07-14T05:05:35.796000', 'stock_symbol': '453810', 'month_purchase_flag': False, 'country': 'ks', 'ratio': 0.5, 'id': 1},
                {'updated_at': '2024-07-14T05:23:47.648000', 'stock_symbol': '368590', 'month_purchase_flag': False, 'country': 'ks', 'ratio': 0.5, 'id': 2}
            ]
    2. portfolio row의 month_purchase_column과 month_budget을 확인하고 아직 구매 및 할당되지 않은(False) 종목들을 가져온다.
    3. 분기점
    - 종목들이 있다면 distribute_asset을 실행한다.
    - 없다면 빈 테스크를 실행한다.

    """
    # 1. db에서 Portfolio table을 가져온다.
    portfolio_rows = get_portfolio_rows()

    # 2. 이번달 구매를 진행한 종목 리스트를 가져온다.
    purchased_portfolio_rows = list(filter(lambda row: row["month_purchase_flag"] is True, portfolio_rows))

    if len(purchased_portfolio_rows) > 0:
        # xcom에 저장하고 다음 task_name 반환
        kwargs["task_instance"].xcom_push(key="purchased_portfolio_rows", value=purchased_portfolio_rows)
        logger.info(f"run {next_task_name}")
        return next_task_name
    else:
        logger.info("run task_empty")
        return "task_empty"


def report_monthly(**kwargs):
    # 1. 앞서 구한 구매한 포트폴리오 rows 가져오기
    purchased_portfolio_rows = kwargs["task_instance"].xcom_pull(key="purchased_portfolio_rows")

    end = datetime.datetime.now() + datetime.timedelta(days=1)
    start = end.replace(day=1)
    for purchased_portfolio_row in purchased_portfolio_rows:
        ticker = f"{purchased_portfolio_row['stock_symbol']}.{purchased_portfolio_row['country']}"

        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        min_close_row = df.loc[df["Close"].idxmin()]
        # "2024-12-20T00:00:00.000000000"
        # min_close_date = str(min_close_row.index.values[0])
        min_close = min_close_row["Close"].values[0][0]

        # "2024-12-12T18:00:13.824977"
        updated_date = purchased_portfolio_row["updated_at"]
        purchased_date = pd.Timestamp(updated_date.split("T")[0])
        purchased_row = df.loc[purchased_date]
        purchased_close = purchased_row["Close"][0]

        # 플롯 생성
        plt.figure(figsize=(12, 6))
        plt.plot(df.index, df["Close"], label="Close Price", marker="o", linestyle="-")
        plt.hlines(min_close, df.index[0], df.index[-1], color="red", linestyle="solid", linewidth=3)
        plt.text(df.index[-1], min_close, "lowest", ha="left", va="center")
        plt.hlines(purchased_close, df.index[0], df.index[-1], color="orange", linestyle="solid", linewidth=3)
        plt.text(df.index[-1], purchased_close, "purchased", ha="left", va="center")
        plt.title(f"{ticker} Close Price Report")

        save_path = f"/shared/reports/{datetime.datetime.now().year}_{datetime.datetime.now().month}_{ticker}.png"
        ensure_directory_exists(save_path)
        plt.savefig(save_path)

        report_summary = f"""종목 {ticker}의 최저 종가는 {min_close}이며, 구매한 가격은 {purchased_close}입니다.\n저점대비 {round((purchased_close - min_close) / min_close * 100, 2)}% 가격입니다."""

        requests.post(
            url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/monthly_report',
            data=json.dumps({"save_path": save_path, "summary": report_summary}),
        )
