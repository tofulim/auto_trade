import datetime

import pendulum
from common.calc_business_day import check_date
from rebalance import check_rebalance_request, execute_rebalance_buys, execute_rebalance_sells

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator

# KST 시간
kst = pendulum.timezone("Asia/Seoul")

# 리밸런싱 DAG
# 매일 Slack 채널을 확인하여 리밸런싱 요청이 있는 경우 포트폴리오를 리밸런싱한다.
rebalance_dag = DAG(
    # DAG 식별자용 아이디
    dag_id="rebalance_dag",
    description="check rebalance request from slack and rebalance portfolio if requested",
    start_date=datetime.datetime(2024, 10, 13, tzinfo=kst),
    # 매일 KST 09:30에 실행합니다 (장 개시 후 30분)
    schedule_interval="30 0 * * *",
    catchup=False,
)

check_date = BranchPythonOperator(
    task_id="check_date",
    python_callable=check_date,
    op_kwargs={"next_task_name": "check_rebalance_request", "use_next_ds": True},
    dag=rebalance_dag,
    provide_context=True,
)

# Slack 채널에서 리밸런싱 요청 여부 확인
check_rebalance_request = BranchPythonOperator(
    task_id="check_rebalance_request",
    python_callable=check_rebalance_request,
    provide_context=True,
    dag=rebalance_dag,
)

# 초과 보유 종목 매도 (비싸진 것 팔기)
execute_rebalance_sells = PythonOperator(
    task_id="execute_rebalance_sells",
    python_callable=execute_rebalance_sells,
    provide_context=True,
    dag=rebalance_dag,
)

# 부족 보유 종목 매수 (싸진 것 사기, 가용 예수금 내에서)
execute_rebalance_buys = PythonOperator(
    task_id="execute_rebalance_buys",
    python_callable=execute_rebalance_buys,
    provide_context=True,
    dag=rebalance_dag,
)

task_empty = EmptyOperator(task_id="task_empty", dag=rebalance_dag)

# 영업일인지 확인하고 주말 및 공휴일이면 DAG 종료
check_date >> [check_rebalance_request, task_empty]
# Slack 리밸런싱 요청 확인 → 매도 or 종료
check_rebalance_request >> [execute_rebalance_sells, task_empty]
# 매도 완료 후 매수 진행
execute_rebalance_sells >> execute_rebalance_buys
