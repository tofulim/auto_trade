import datetime
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from prophesy import prophesy_portfolio, execute_decisions

# Configure logger.py correctly
# Logger
logger = logging.getLogger("api_logger")

# 종목 경향 예측 -> 매매 결정 -> 매매 (할당예수금이 있다면)
prophesy_n_make_decision_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="prophesy_n_make_decision_dag",
    description="prophesy current portfolio's trend and make decision of purchase or sell",
    start_date=datetime.datetime(2024, 7, 1),
    # 매일 08:25 시간 외 장전거래를 실행합니다 (08:20 - 08:40)
    schedule_interval="25 8 * * *",
    # schedule_interval=None,
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

# 포트폴리오 경향 예측 및 의사 결정 >> 결정 수행
prophesy_portfolio >> execute_decisions
