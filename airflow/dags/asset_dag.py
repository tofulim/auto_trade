import datetime
import os

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator

from airflow.plugins.asset_update import get_balance


def get_run_task():
    """
    asset을 확인하고 portfolio를 재구성하는 메인 함수
    1. 한투 계좌 내 예수금을 확인한다.
    2-a. 매달 정해진 이체일이 지나 예수금이 입금된 경우
        3. portfolio를 요청해 받아온다.
        4. portfolio의 각 종목 비율에 맞게 asset을 분배한다.
        5. asset을 update한다.
    2-b. 아직 입금되지 않아 예수금이 정해진 이체액을 충족하지 못할 경우

    Returns:
        task_id (object): 분기 로직을 통해 결정되는 task id

    """
    balance = get_balance()
    # 이체일이 지나 이체되어 잔액이 잘 있는 경우 포트폴리오를 구성한다.
    if balance >= int(os.getenv("INVESTMENT_MONEY_PER_MONTH")):
        return redistribute_portfolio.task_id
    else:
        return task_empty.task_id


asset_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="asset_dag",
    description="check current balance and update available portfolio",
    start_date=datetime.datetime.now(),
    # 매일 06:00에 실행합니다
    schedule_interval="0 6 * * *",
)

redistribute_portfolio = PythonOperator(
    task_id="redistribute_portfolio",
    python_callable=redistribute_portfolio,
    dag=asset_dag,
)

task_empty = EmptyOperator(
    task_id='task_empty',
    dag=asset_dag
)

task_branch = BranchPythonOperator(
    task_id='task_branch',
    python_callable=get_run_task,
    dag=asset_dag
)

# balance를 받아서 env에 저장된 금액을 충족했는지 확인하고 만족했다면 portfolio에 가용한 금액인 accum_asset을 갱신해준다.
