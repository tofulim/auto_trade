import logging
import os

import requests

logger = logging.getLogger("api_logger")


def check_take_profit() -> None:
    """종가 기준 익절 조건을 검사하고 다음 거래일 예약 매도를 접수한다.

    Raises:
        requests.HTTPError: 서버의 익절 검사 요청이 실패한 경우.
    """
    response = requests.post(
        f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/take_profit/check',
        timeout=240,
    )
    response.raise_for_status()
    logger.info("익절 검사 결과: %s", response.json())
