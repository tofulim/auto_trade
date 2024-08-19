import datetime
import logging
import pendulum

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from prophesy import prophesy_portfolio, execute_decisions
from common.calc_business_day import check_date

# Configure logger.py correctly
# Logger
logger = logging.getLogger("api_logger")

# KST 시간
kst = pendulum.timezone("Asia/Seoul")

# 종목 경향 예측 -> 매매 결정 -> 매매 (할당예수금이 있다면)
prophesy_n_make_decision_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="prophesy_n_make_decision_dag",
    description="prophesy current portfolio's trend and make decision of purchase or sell",
    start_date=datetime.datetime(2024, 7, 1, tzinfo=kst),
    # 장 종료 후 금일 종가로 내일 장전 시간외 매수로 예약 매수를 걸어 놓는다.
    schedule_interval="0 20 * * *",
    # schedule_interval=None,
)

check_date = BranchPythonOperator(
    task_id='check_date',
    python_callable=check_date,
    op_kwargs={"next_task_name": "prophesy_portfolio"},
    dag=prophesy_n_make_decision_dag,
    provide_context=True,
)

# 종목 경향 예측 및 매매 결정
prophesy_portfolio = PythonOperator(
    task_id="prophesy_portfolio",
    python_callable=prophesy_portfolio,
    dag=prophesy_n_make_decision_dag,
)

# 결정된 매매 수행
execute_decisions = PythonOperator(
    task_id="execute_decision",
    python_callable=execute_decisions,
    provide_context=True,
    dag=prophesy_n_make_decision_dag,
)

task_empty = EmptyOperator(
    task_id='task_empty',
    dag=prophesy_n_make_decision_dag
)

# 영업일인지 확인하고 주말 및 공휴일이면 DAG 종료
check_date >> [prophesy_portfolio, task_empty]

# 포트폴리오 경향 예측 및 의사 결정 >> 결정 수행
prophesy_portfolio >> execute_decisions
