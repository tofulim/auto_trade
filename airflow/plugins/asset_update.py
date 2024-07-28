import os
import logging
import dotenv
import requests
from datetime import datetime, timedelta

dotenv.load_dotenv(f"./config/PROD.env")
logger = logging.getLogger("api_logger")


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
    kwargs['task_instance'].xcom_push(key='balance', value=balance)

    # 이체일이 지나 이체되어 잔액이 잘 있는 경우 포트폴리오를 구성한다.
    if balance >= int(os.getenv("INVESTMENT_MONEY_PER_MONTH")):
        logger.info(
            f"run check_portfolio",
        )
        return 'check_portfolio'
    else:
        logger.info(
            f"run empty",
        )
        return 'task_empty'


def get_balance():
    """
    day+2 예수금을 이용한다.
    구매해서 빠지지 않은 예수금이 있을 수 있기 때문.

    Returns:
        +day2_balance (int)

    """
    response = requests.post(
        url='http://0.0.0.0:8000/v1/trader/get_balance',
    )
    response_json = response.json()
    balance = int(response_json["output"]["prvs_rcdl_excc_amt"])

    return balance


def check_portfolio(**kwargs):
    """포트폴리오 투자
    1. db에서 Portfolio table을 가져온다.
        ex. [
                {'updated_at': '2024-07-14T05:05:35.796000', 'stock_symbol': '453810', 'month_purchase_flag': False, 'country': 'ks', 'ratio': 0.5, 'id': 1},
                {'updated_at': '2024-07-14T05:23:47.648000', 'stock_symbol': '368590', 'month_purchase_flag': False, 'country': 'ks', 'ratio': 0.5, 'id': 2}
            ]
    2. portfolio row의 month_purchase_column을 확인하고 아직 구매하지 않은(False) 종목들을 가져온다.
    3. 구매한다.
    - slack 보낸다.

    """
    # 0. 앞서 구한 예수금 가져오기
    balance = kwargs['task_instance'].xcom_pull(key='balance')

    # 1. db에서 Portfolio table을 가져온다.
    response = requests.get(url='http://0.0.0.0:8000/v1/portfolio/get/stock_symbol?all')
    portfolio_rows = response.json()
    status = distribute_asset(
        balance=balance,
        portfolio_rows=portfolio_rows,
    )

    return balance


def distribute_asset(balance: int, portfolio_rows: list):
    """ asset 분배
    asset을 portfolio 종목들 ratio에 따라 분배한다.

    Args:
        balance (int): 예수금
        portfolio_rows (list): Portfolio rows

    Returns:
        status (bool): 상태
    """
    status = False
    for portfolio_row in portfolio_rows:
        # utc + 9hours = ktc
        now_ktc = datetime.now() + timedelta(hours=9)
        ratio = portfolio_row["ratio"]
        month_budget = portfolio_row["month_budget"]
        month_purchase_flag = portfolio_row["month_purchase_flag"]

        # 해당 종목의 구매비율, 금월 구매여부, 현재 할당예산 등을 고려한다.
        if ratio >= 0 and month_purchase_flag is not True and month_budget == 0:
            # 조건을 만족하는 경우 분배한다.
            budget = int(balance * ratio)
            status = True


    return status
