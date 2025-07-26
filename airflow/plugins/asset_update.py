import json
import os

import requests
from common.logger_config import setup_logger

logger = setup_logger(__name__)


def check_balance(**kwargs):
    """
    asset을 확인하고 portfolio를 재구성하는 메인 함수
    1. 한투 계좌 내 예수금을 확인한다.
    2-a. 매달 정해진 이체일이 지나 예수금이 입금된 경우
        3-a. portfolio를 요청해 받아온다.
        3-b. portfolio의 purchased flag가 False인 종목들을 가져온다.
        4. portfolio의 각 종목 비율에 맞게 asset을 분배한다.
    2-b. 아직 입금되지 않아 예수금이 정해진 이체액을 충족하지 못할 경우
        3-a. 과정을 종료한다.

    Returns:
        task_id (object): 분기 로직을 통해 결정되는 task id

    """
    # 예수금 구한 뒤 저장
    balance = get_balance()
    kwargs["task_instance"].xcom_push(key="balance", value=balance)

    # 이체일이 지나 이체되어 잔액이 잘 있는 경우 포트폴리오를 구성한다.
    if balance >= int(os.getenv("INVESTMENT_MONEY_PER_MONTH")):
        logger.info("run check_portfolio")
        return "check_portfolio"
    else:
        logger.info("run empty")
        return "task_empty"


def get_balance():
    """
    day+2 예수금을 이용한다.
    구매해서 빠지지 않은 예수금이 있을 수 있기 때문.

    Returns:
        +day2_balance (int)

    """
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/get_balance'
    )

    response_json = response.json()
    balance = int(response_json["output"]["prvs_rcdl_excc_amt"])

    return balance


def get_portfolio_rows():
    # 1. db에서 Portfolio table을 가져온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({"get_all": True}),
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
    2. 분기점
    - 종목들이 있다면 distribute_asset을 실행한다.
    - 없다면 빈 테스크를 실행한다.

    """
    # 1. db에서 Portfolio table을 가져온다.
    candidate_portfolio_rows = get_portfolio_rows()

    if len(candidate_portfolio_rows) > 0:
        # xcom에 저장하고 다음 task_name 반환
        kwargs["task_instance"].xcom_push(key="candidate_portfolio_rows", value=candidate_portfolio_rows)
        logger.info("run distribute_asset")
        return "distribute_asset"
    else:
        logger.info("run task_empty")
        return "task_empty"


def distribute_asset(**kwargs):
    """asset 분배
    asset을 portfolio 종목들에 ratio에 따라 분배한다.

    Returns:
        status (bool): 상태
    """
    # 0. 앞서 구한 예수금 가져오기
    balance = kwargs["task_instance"].xcom_pull(key="balance")
    # 1. 앞서 구한 포트폴리오 rows 가져오기
    candidate_portfolio_rows = kwargs["task_instance"].xcom_pull(key="candidate_portfolio_rows")

    input_text = ""
    for candidate_portfolio_row in candidate_portfolio_rows:
        stock_symbol = candidate_portfolio_row["stock_symbol"]
        ratio = float(candidate_portfolio_row["ratio"])

        # distribute DAG에서는 매월 예수금 이체되면 분배한다. 구매 상태와 상관없이 month_budget와 상태를 초기화해준다.
        update_dict = {"month_budget": balance * ratio, "month_purchase_flag": False, "order_status": "N"}

        response = requests.put(
            url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/put_fields?stock_symbol={stock_symbol}',
            data=json.dumps(update_dict),
        )
        logger.info(response.json())

        if response.status_code != 200:
            raise Exception(f"status_code is {response.status_code} !")

        input_text += f"stock_symbol {stock_symbol}에 month_budget {update_dict['month_budget']}이 할당되었습니다.\n"

    channel_id = os.getenv("DAILY_REPORT_CHANNEL")
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/slackbot/send_message',
        data=json.dumps({"channel_id": channel_id, "input_text": input_text}),
    )

    return True
