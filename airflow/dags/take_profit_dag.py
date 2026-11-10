import datetime

import pendulum
from take_profit_check import check_take_profit

from airflow import DAG
from airflow.operators.python import PythonOperator

take_profit_dag = DAG(
    dag_id="take_profit_dag",
    description="Check closing returns and reserve next-session half take-profit",
    start_date=datetime.datetime(2024, 10, 13, tzinfo=pendulum.timezone("Asia/Seoul")),
    schedule_interval="0 20 * * 1-5",
    catchup=False,
    max_active_runs=1,
)

check_take_profit_task = PythonOperator(
    task_id="check_take_profit", python_callable=check_take_profit, dag=take_profit_dag
)
