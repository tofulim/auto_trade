import os

import requests


def get_trading_settings() -> dict:
    """환경변수 대신 FastAPI에 저장된 최신 매매 설정을 조회한다.

    Returns:
        전체 공통 매매 설정.

    Raises:
        requests.HTTPError: 설정 조회가 실패한 경우.
    """
    response = requests.get(
        f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/settings/trading', timeout=30
    )
    response.raise_for_status()
    return response.json()
