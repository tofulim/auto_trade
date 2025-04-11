import os
import logging
import dotenv
import holidays
from datetime import datetime, timedelta, date


dotenv.load_dotenv(f"/opt/airflow/config/prod.env")
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
        curr_date = execution_date.date()


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


def check_auto_payment_date(execution_date: datetime, next_task_name: str, next_ds: str, use_next_ds: bool = False):
    """자동이체 날 여부 확인
    오늘이 자동이체 날 다음 영업일인지 확인하고 주어진 task를 실행할지 혹은 empty task를 실행할 지 결정한다.
    한 달에 한 번만 수행해야하는 로직을 위한 검사이다.

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

    auto_payment_day: int = int(os.getenv("AUTO_PAYMENT_DAY", 11))

    if use_next_ds is True:
        run_date = next_ds
        run_date = datetime.strptime(run_date, "%Y-%m-%d").date()
    else:
        run_date = execution_date

    # 애초에 아직 자동이체일보다도(defautl: 11) 작은 날짜인 경우
    if run_date.day < auto_payment_day:
        logger.info(
            f"today is not ready before auto_payment_day {auto_payment_day} run empty",
        )
        return 'task_empty'
    # 자동이체일을 넘은 경우
    else:
        # 자동이체날 이후 가장 가까운 다음 영업일을 구한다. (자동이체날 정확하게 이체가 되지 않기 때문)
        safe_payment_day = -1
        year, month = run_date.year, run_date.month
        for day in range(auto_payment_day + 1, 30):
            curr_datetime = datetime(year, month, day)

            if is_ktc_business_day(curr_datetime) is True:
                logger.info(
                    f"this month is {run_date.month}. and safe payment day is {curr_datetime}",
                )
                safe_payment_day = curr_datetime.day
                break

        assert safe_payment_day != -1, f"safe_payment_day should not be {safe_payment_day}"

        # 오늘이 자동이체일 이후 가장 가까운 다음 영업일인 경우
        # 예수금을 조회해 포트폴리오를 갱신한다.
        if safe_payment_day == run_date.day:
            logger.info(
                f"today is the day! run next task {next_task_name}",
            )
            return next_task_name
        else:
            logger.info(
            "today is not the day! run empty",
            )
            return 'task_empty'


if __name__ == "__main__":

    res = check_auto_payment_date(
        execution_date=datetime(2024, 8, 10),
        next_task_name="next",
        next_ds="f",
    )
    print(res)
