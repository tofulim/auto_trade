import os

import requests


def update_trader_key():
    """
    Trader(KIS)의 token을 업데이트한다.
    """
    url = f"http://{os.getenv('FASTAPI_SERVER_HOST')}:{os.getenv('FASTAPI_SERVER_PORT')}/v1/trader/update_token"
    response = requests.get(url=url)

    request_status = response.status_code

    return request_status, response.json()
