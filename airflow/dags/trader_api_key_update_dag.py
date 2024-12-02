import datetime
import pendulum

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.trader_key_update import update_trader_key


# KST 시간
kst = pendulum.timezone("Asia/Seoul")

key_update_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="trader_key_update_dag",
    description="update KIS(한투) api key and carve at python environment",
    start_date=datetime.datetime(2024, 10, 13, tzinfo=kst),
    # 매일 KTC 08:30에 실행합니다.
    schedule_interval="30 8 * * *",
)

update_key = PythonOperator(
    task_id="update_trader_key",
    python_callable=update_trader_key,
    dag=key_update_dag,
)

update_key
