import datetime
import logging
import pendulum

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from trade_order import check_order_exist, check_order, change_status

# Configure logger.py correctly
# Logger
logger = logging.getLogger("api_logger")

# KST 시간
kst = pendulum.timezone("Asia/Seoul")

"""주문 확인
예약 매수/매도 주문을 확인하고 각 종목들의 성공/실패에 따라 portfolio rows의 order_status를 update한다.

1. 주문한 종목들 존재 여부 확인
2. 한투 API에 조회하여 상태 확인
3. db에 적용
"""
check_order_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="check_order_dag",
    description="check trade order and apply to db",
    start_date=datetime.datetime(2024, 10, 13, tzinfo=kst),
    schedule_interval="0 19 * * *",
)

# 주문한 종목이 있다면 status를 확인한다.
check_order_exist = BranchPythonOperator(
    task_id='check_order_exist',
    python_callable=check_order_exist,
    op_kwargs={"next_task_name": "check_order"},
    dag=check_order_dag,
    provide_context=True,
)

# 주문 확인
check_order = BranchPythonOperator(
    task_id="check_order",
    python_callable=check_order,
    provide_context=True,
    op_kwargs={"next_task_name": "change_status"},
    dag=check_order_dag,
)

# 주문 db 반영
change_status = PythonOperator(
    task_id="change_status",
    python_callable=change_status,
    provide_context=True,
    dag=check_order_dag,
)

task_empty = EmptyOperator(
    task_id='task_empty',
    dag=check_order_dag
)

# 매매 주문 내역 확인하고 존재하면 상태 확인
check_order_exist >> [check_order, task_empty]
# 상태 반영
check_order >> [change_status, task_empty]
