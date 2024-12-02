import os
import logging
import dotenv
import holidays
from datetime import datetime, timedelta, date


dotenv.load_dotenv(f"./config/PROD.env")
logger = logging.getLogger("api_logger")


def is_holiday(curr_datetime: str):
    # 대한민국 공휴일에 대한 holidays 객체 생성
    kr_holidays = holidays.SouthKorea()
    # 문자열을 date 객체로 변환
    check_date = date.fromisoformat(str(curr_datetime))

    if check_date in kr_holidays:
        return True
    else:
        return False

def is_ktc_business_day(execution_date, is_next: bool = False):
    """한국 영업일 확인
    지금 시간이 거래가능일인지 확인한다.
    - 평일 확인
    - 공휴일 확인
    평일이면서 공휴일이 아닌 경우 True를 반환한다. 장이 열지 않는 날이라면 False를 반환한다.

    Returns:
        flag (bool): 영업일 여부 (True | False)

    """
    flag = False
    if is_next:
        curr_date = datetime.strptime(execution_date, "%Y-%m-%d").date()
    else:
        curr_date = execution_date.strftime("%Y-%m-%d")


    if curr_date.weekday() < 5 and is_holiday(curr_date) is False:
        flag = True

    return flag


def check_date(execution_date: datetime, next_task_name: str, next_ds: str, use_next_ds: bool = False):
    """날짜 확인
    현재 날짜를 확인하고 주어진 task를 실행할지 혹은 empty task를 실행할 지 결정한다.
    Args:
        execution_date (str): 실행시점
        next_task_name (str): 날짜가 맞다면 수행할 다음 task

    Returns:
        next_task_name (str): 다음에 수행할 task의 이름으로 파라미터로 받은 next_task_name이 될 수 있도 empty_task가 될 수도 있다.

    """
    # 정상 영업일의 경우 다음 과정을 수행한다.
    logger.info(
            f"input execution_date is {execution_date} and next_ds is {next_ds}. next_ds type is {type(next_ds)}",
        )


    if use_next_ds is True:
        run_date = next_ds
    else:
        run_date = execution_date

    if is_ktc_business_day(run_date, is_next=use_next_ds) is True:
        logger.info(
            f"run next task {next_task_name}",
        )
        return next_task_name
    else:
        logger.info(
            f"run empty",
        )
        return 'task_empty'
