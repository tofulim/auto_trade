import os
import logging
import dotenv

from datetime import datetime, timedelta
from holidayskr import today_is_holiday

dotenv.load_dotenv(f"./config/PROD.env")
logger = logging.getLogger("api_logger")


def is_ktc_business_day():
    """한국 영업일 확인
    지금 시간이 거래가능일인지 확인한다.
    - 평일 확인
    - 공휴일 확인
    평일이면서 공휴일이 아닌 경우 True를 반환한다. 장이 열지 않는 날이라면 False를 반환한다.

    Returns:
        flag (bool): 영업일 여부 (True | False)

    """
    flag = False

    # 현재 UTC 시간
    now_utc = datetime.utcnow()
    # 한국 시간
    kst_offset = timedelta(hours=9)
    now_kst = now_utc + kst_offset

    if now_kst.weekday() < 5 and today_is_holiday() is False:
        flag = True

    return flag


def check_date(next_task_name: str):
    """날짜 확인
    현재 날짜를 확인하고 주어진 task를 실행할지 혹은 empty task를 실행할 지 결정한다.
    Args:
        next_task_name (str): 날짜가 맞다면 수행할 다음 task

    Returns:
        next_task_name (str): 다음에 수행할 task의 이름으로 파라미터로 받은 next_task_name이 될 수 있도 empty_task가 될 수도 있다.

    """
    # 정상 영업일의 경우 다음 과정을 수행한다.
    if is_ktc_business_day() is True:
        logger.info(
            f"run next task {next_task_name}",
        )
        return next_task_name
    else:
        logger.info(
            f"run empty",
        )
        return 'task_empty'
