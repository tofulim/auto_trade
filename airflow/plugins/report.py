import json
import os
import logging
import dotenv
import requests

dotenv.load_dotenv(f"/home/ubuntu/zed/auto_trade/config/prod.env")
logger = logging.getLogger("api_logger")


def get_portfolio_rows():
    # 1. db에서 Portfolio table을 가져온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({
            "get_all": True,
        })
    )
    portfolio_rows = response.json()

    return portfolio_rows

def check_portfolio(**kwargs):
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

    # 2. 아직 예산이 할당되지 않았고 매수 신청을 하지 않은 후보 종목들의 종목 id를 구한다.
    candidate_portfolio_rows = list(filter(
        lambda row: row["order_status"] == "N" and row["month_budget"] == 0, portfolio_rows
    ))

    if len(candidate_portfolio_rows) > 0:
        # xcom에 저장하고 다음 task_name 반환
        kwargs['task_instance'].xcom_push(key='candidate_portfolio_rows', value=candidate_portfolio_rows)
        logger.info(
            f"run distribute_asset",
        )
        return "distribute_asset"
    else:
        logger.info(
            f"run task_empty",
        )
        return "task_empty"
