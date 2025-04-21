import datetime
import logging

import pendulum
from asset_update import check_balance, check_portfolio, distribute_asset
from common.calc_business_day import check_auto_payment_date

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator

# Configure logger.py correctly
# Logger
logger = logging.getLogger("api_logger")


# KST 시간
kst = pendulum.timezone("Asia/Seoul")
# 예수금 확인 -> 종목들에 분배
asset_check_n_distribution_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="asset_check_n_distribution_dag",
    description="check current balance and update available portfolio",
    start_date=datetime.datetime(2024, 10, 13, tzinfo=kst),
    # 매일 18:00에 실행합니다
    schedule_interval="0 18 * * *",
)

check_date = BranchPythonOperator(
    task_id="check_date",
    python_callable=check_auto_payment_date,
    op_kwargs={"next_task_name": "check_balance", "use_next_ds": True},
    dag=asset_check_n_distribution_dag,
    provide_context=True,
)

check_balance = BranchPythonOperator(
    task_id="check_balance", python_callable=check_balance, provide_context=True, dag=asset_check_n_distribution_dag
)

check_portfolio = BranchPythonOperator(
    task_id="check_portfolio", python_callable=check_portfolio, provide_context=True, dag=asset_check_n_distribution_dag
)

distribute_asset = PythonOperator(
    task_id="distribute_asset",
    python_callable=distribute_asset,
    provide_context=True,
    dag=asset_check_n_distribution_dag,
)

task_empty = EmptyOperator(task_id="task_empty", dag=asset_check_n_distribution_dag)

# 영업일인지 확인하고 주말 및 공휴일이면 DAG 종료
check_date >> [check_balance, task_empty]
# balance를 받아서 env에 저장된 금액을 충족했는지 확인하고 만족했다면 portfolio에 가용한 금액인 accum_asset을 갱신해준다.
# 예수금 확인 -> 분배 종목 리스트 반환
check_balance >> [check_portfolio, task_empty]
# # 미할당 포트폴리오에 자산 분배
check_portfolio >> [distribute_asset, task_empty]
