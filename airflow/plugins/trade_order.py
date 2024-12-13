import json
import os
import logging
import dotenv
import requests

dotenv.load_dotenv(f"/home/ubuntu/zed/auto_trade/config/prod.env")
logger = logging.getLogger("api_logger")


def get_portfolio_rows():
    # 1. db에서 Portfolio table을 가져온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/get',
        data=json.dumps({
            "get_all": True,
        })
    )
    portfolio_rows = response.json()

    return portfolio_rows

def check_order_exist(next_task_name: str, **kwargs):
    """주문 확인
    예약 매수/매도 주문한 종목들 여부를 확인한다.
    1. 있을 때
    - 한투 API에 조회
    2. 없을 때
    - 종료
    """
    # db에서 Portfolio table을 가져온다.
    portfolio_rows = get_portfolio_rows()

    # 매매 신청한 종목들을 구한다.
    candidate_portfolio_rows = list(filter(
        lambda row: row["order_status"] in ["O", "W"], portfolio_rows
    ))

    if len(candidate_portfolio_rows) > 0:
        kwargs['task_instance'].xcom_push(key='candidate_portfolio_rows', value=candidate_portfolio_rows)

        logger.info(
            f"run {next_task_name}",
        )
        return next_task_name
    else:
        logger.info(
            "no order exist. run task_empty",
        )
        return "task_empty"

def check_order(next_task_name: str, **kwargs):
    # 전체 orders를 받아온다.
    response = requests.post(
        url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/get_orders',
        data=json.dumps({
            "get_all": True,
        })
    )
    rsvn_orders = response.json()["output"]

    if len(rsvn_orders) > 0:
        kwargs['task_instance'].xcom_push(key='rsvn_orders', value=rsvn_orders)
        logger.info(
            f"run {next_task_name}",
        )
        return next_task_name
    else:
        logger.info(
            "run task_empty",
        )
        return "task_empty"


# 주문 전송 및 slack msg 전송
def change_status(**kwargs):
    # 1. 앞서 구한 주문 가져오기
    rsvn_orders = kwargs['task_instance'].xcom_pull(key='rsvn_orders')
    # 2. 종목 포트폴리오 rows 가져오기
    candidate_portfolio_rows = kwargs['task_instance'].xcom_pull(key='candidate_portfolio_rows')
    pdno2budget = {
        candidate_portfolio_row["stock_symbol"]: candidate_portfolio_row["month_budget"]
        for candidate_portfolio_row in candidate_portfolio_rows
    }

    for rsvn_order in rsvn_orders:
        # 종목번호
        pdno = rsvn_order["pdno"]

        order_status, update_dict = "E", {}
        try:
            # 종목 한글명
            kor_item_shtn_name = rsvn_order["kor_item_shtn_name"]
            # 매매 구분 (매도: 01, 매수: 02)
            sll_buy_dvsn_cd = rsvn_order["sll_buy_dvsn_cd"]
            sll_buy_dvsn_cd_str = "매도" if sll_buy_dvsn_cd == "01" else "매수"
            # 총 체결금액
            tot_ccld_amt = rsvn_order["tot_ccld_amt"]
            # 처리 결과
            prcs_rslt = rsvn_order["prcs_rslt"]
            # 주문 구분명
            ord_dvsn_name = rsvn_order["ord_dvsn_name"]

            if prcs_rslt == "미처리":
                order_status = "F"
                update_dict.update({
                    "order_status": order_status,
                })
            # 정상 처리된 경우
            elif prcs_rslt == "처리":
                order_status = "S"
                update_dict.update({
                    "month_purchase_flag": True,
                    "month_budget": pdno2budget[pdno] - tot_ccld_amt, # 예산 - 체결금액
                    "reserved_budget": 0,
                    "order_status": order_status,
                })
            # 그 외 뭔가 잘못됐거나 처리 대기 케이스
            else:
                order_status = "W"
                update_dict.update({
                    "order_status": order_status,
                })


            logger.info(
                f"종목 {pdno}({kor_item_shtn_name})의 {sll_buy_dvsn_cd_str} {ord_dvsn_name}는 {prcs_rslt}되었습니다. order_status: {order_status} (총액 {tot_ccld_amt})",
            )

            requests.put(
                url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/portfolio/put_fields?stock_symbol={pdno}',
                data=json.dumps(update_dict),
            )

        except Exception as e:
            logger.info(
                f"종목 {pdno}을 처리하던 중 에러 발생 {e}",
            )
            order_status = "E"
        finally:
            input_text = f"종목 {pdno}는 현재 {order_status} 상태입니다."
            channel_id = os.getenv("TRADE_ALARM_CHANNEL")
            requests.post(
                url=f'http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/slackbot/send_message',
                data=json.dumps({
                    "channel_id": channel_id,
                    "input_text": input_text,
                }),
            )
