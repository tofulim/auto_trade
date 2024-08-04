import json
import os
import logging
import dotenv
import requests

from const import STAY, PURCHASE, SELL

dotenv.load_dotenv(f"./config/PROD.env")
logger = logging.getLogger("api_logger")


def prophesy_portfolio(**kwargs):
    """
    portfolio 내 종목들 경향을 예측하고 매매 의사 결정을 내린다.
    1. 주어진 종목들에 대한 경향 예측을 수행한다.
    - [(stock_symbol, behavior, diff_rate, d), ... , ]
    2. 매매 threshold를 만족하는 경우를 모아 반환한다.
    - xcom에 저장

    Returns:
        task_id (object): 분기 로직을 통해 결정되는 task id

    """
    portfolio_behavior_decisions = []

    # 0. db에서 Portfolio table을 가져온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({
            "get_all": True,
        })
    )
    portfolio_rows = response.json()
    kwargs['task_instance'].xcom_push(key='portfolio_rows', value=portfolio_rows)
    stock_symbol2month_budget = {
        row["stock_symbol"]: row["month_budget"]
        for row in portfolio_rows
    }
    # 1. 주어진 종목들에 대한 경향 예측을 수행한다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/prophet',
        data=json.dumps({
            "stock_symbols": list(stock_symbol2month_budget.keys()),
        })
    )
    stock_symbol2prophecy = response.json()

    # 2. 매매 threshold를 만족하는 경우를 모아 반환한다.
    for stock_symbol, prophecy in stock_symbol2prophecy.items():
        stock_symbol = stock_symbol.split(".")[0]
        last_price, diff_rate = prophecy["last_price"], prophecy["diff_rate"]
        behavior = _get_behavior(
            diff_rate=diff_rate,
            purchase_threshold=float(os.getenv("PURCHASE_THRESHOLD")),
            sell_threshold=float(os.getenv("SELL_THRESHOLD")),
        )
        portfolio_behavior_decisions.append(
            # (stock_symbol, behavior, diff_rate, month_budget, last_price)
            (stock_symbol, behavior, diff_rate, stock_symbol2month_budget[stock_symbol], last_price)
        )

    kwargs['task_instance'].xcom_push(key='portfolio_behavior_decisions', value=portfolio_behavior_decisions)

    return True


def execute_decisions(**kwargs):
    """결정 수행
    portfolio 종목들에 대한 prophecies를 받아 매매를 수행한다.
    """

    # 1. 앞서 구한 할당/구매 안한 포트폴리오 의사결정 가져오기
    portfolio_behavior_decisions = kwargs['task_instance'].xcom_pull(key='portfolio_behavior_decisions')
    logger.info(f"portfolio_behavior_decisions: {portfolio_behavior_decisions}")
    # 2. 결정 수행
    for portfolio_behavior_decision in portfolio_behavior_decisions:
        stock_symbol, behavior, diff_rate, month_budget, last_price = portfolio_behavior_decision
        ord_qty = month_budget // last_price
        result = None
        if behavior == STAY:
            continue
        elif behavior == PURCHASE:
            if ord_qty > 0:
                result = requests.post(
                    url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/buy',
                    data=json.dumps({
                        "stock_symbol": stock_symbol,
                        "ord_qty": int(ord_qty),
                        "ord_price": int(last_price),
                    })
                )

        elif behavior == SELL:
            if ord_qty > 0:
                result = requests.post(
                    url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/sell',
                    data=json.dumps({
                        "stock_symbol": stock_symbol,
                        "ord_qrt": ord_qty,
                        "ord_price": last_price,
                    })
                )

        else:
            raise ValueError("behavior must one of (STAY | PURCHASE | SELL)")

        logger.info(f"stock_symbol: {stock_symbol} - behavior {behavior}'s result is {result.json()}")


def _get_behavior(
    diff_rate: float,
    purchase_threshold: float,
    sell_threshold: float,
):
    """행동 결정

    Args:
        diff_rate (float): 종목의 기울기를 의미한다. 동작 판별의 근거가 된다.
        purchase_threshold (float): 매수 기준점
        sell_threshold (float): 매도 기준점

    Returns:
        behavior (str): const에 정의된 행동 (PURCHASE | SELL | STAY) 중 하나이다.

    """
    behavior = STAY
    if diff_rate >= purchase_threshold:
        behavior = PURCHASE
    elif diff_rate <= sell_threshold:
        behavior = SELL

    return behavior


def get_balance():
    """
    day+2 예수금을 이용한다.
    구매해서 빠지지 않은 예수금이 있을 수 있기 때문.

    Returns:
        +day2_balance (int)

    """
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/get_balance',
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
    2. portfolio row의 month_purchase_column과 month_budget을 확인하고 아직 구매 및 할당되지 않은(False) 종목들을 가져온다.
    3. 분기점
    - 종목들이 있다면 distribute_asset을 실행한다.
    - 없다면 빈 테스크를 실행한다.

    """
    # 1. db에서 Portfolio table을 가져온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({
            "get_all": True,
        })
    )
    portfolio_rows = response.json()

    # 2. 아직 구매 및 할당되지 않는 후보 종목들의 종목 id를 구한다.
    candidate_portfolio_rows = list(filter(
        lambda row: row["month_purchase_flag"] is False and row["month_budget"] == 0, portfolio_rows
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


def distribute_asset(**kwargs):
    """ asset 분배
    asset을 portfolio 종목들 ratio에 따라 분배한다.
    (단, xcom을 통해 받은 종목들은 month_budget이 아직 할당되지 않아 0이고 month_purchase_flag 또한 False인 상태이다.)

    Returns:
        status (bool): 상태
    """
    # 0. 앞서 구한 예수금 가져오기
    balance = kwargs['task_instance'].xcom_pull(key='balance')
    # 1. 앞서 구한 할당/구매 안한 포트폴리오 rows 가져오기
    candidate_portfolio_rows = kwargs['task_instance'].xcom_pull(key='candidate_portfolio_rows')

    for candidate_portfolio_row in candidate_portfolio_rows:
        stock_symbol = candidate_portfolio_row["stock_symbol"]
        ratio = float(candidate_portfolio_row["ratio"])

        # 구매는 다음 DAG에서 수행하므로 distribute DAG에서는 month_budget만 업데이트해준다.
        update_dict = {
            "month_budget": balance * ratio,
        }

        response = requests.put(
            url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/put_fields?stock_symbol={stock_symbol}',
            data=json.dumps(update_dict),
        )
        logger.info(
            response.json(),
        )

        if response.status_code != 200:
            raise Exception(f"status_code is {response.status_code} !")

    return True
