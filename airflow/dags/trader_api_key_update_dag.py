import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from common.trader_key_update import update_trader_key

key_update_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="kis_key_update_dag",
    description="update KIS(한투) api key and carve at python environment",
    start_date=datetime.datetime.now(),
    # 매일 00:00에 실행합니다
    schedule_interval="0 0 * * *",
)

update_key = PythonOperator(
    task_id="update_kis_key",
    python_callable=update_trader_key,
    dag=key_update_dag,
)

update_key
