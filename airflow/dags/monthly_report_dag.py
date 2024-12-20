import datetime
import pendulum

from airflow import DAG
from airflow.operators.python import PythonOperator

from common.trader_key_update import update_trader_key


# KST 시간
kst = pendulum.timezone("Asia/Seoul")

monthly_report_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="monthly_report_dag",
    description="report monthly trading result compared to lowerst close price",
    start_date=datetime.datetime(2024, 10, 13, tzinfo=kst),
    # 매일 KTC 08:30에 실행합니다.
    schedule_interval="0 20 28 * *",
)

report_monthly = PythonOperator(
    task_id="report_monthly",
    python_callable=report_monthly,
    dag=monthly_report_dag,
)

report_monthly
