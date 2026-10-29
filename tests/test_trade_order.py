import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "airflow" / "plugins"))

import trade_order  # noqa: E402


class TradeOrderTests(unittest.TestCase):
    """주문 확인 대상만 상태와 알림을 갱신하는지 검증한다."""

    def setUp(self) -> None:
        """가상 주문과 외부 요청 모의 객체를 준비한다."""
        self.orders = []
        self.candidates = [{"stock_symbol": "PENDING", "month_budget": 1000}]
        self.task_instance = Mock()
        self.task_instance.xcom_pull.side_effect = [self.orders, self.candidates]
        env = patch.dict(
            "os.environ", {"FASTAPI_SERVER_HOST": "api", "FASTAPI_SERVER_PORT": "8000", "TRADE_ALARM_CHANNEL": "test"}
        )
        env.start()
        self.addCleanup(env.stop)
        for name in ("post", "put"):
            patcher = patch.object(trade_order.requests, name)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def test_non_candidate_orders_are_skipped(self) -> None:
        """대상이 아닌 주문은 어떤 처리 결과여도 갱신하거나 알리지 않는다."""
        for result in ("처리", "미처리", "대기"):
            self.orders.append(
                {
                    "pdno": "COMPLETED",
                    "kor_item_shtn_name": "완료 종목",
                    "sll_buy_dvsn_cd": "02",
                    "tot_ccld_amt": "400",
                    "prcs_rslt": result,
                    "ord_dvsn_name": "현금매수",
                }
            )

        trade_order.change_status(task_instance=self.task_instance)

        self.put.assert_not_called()
        self.post.assert_not_called()

    def test_mixed_orders_preserve_candidate_processing(self) -> None:
        """과거 주문이 함께 조회되어도 대상 주문의 S/F/W 처리를 유지한다."""
        for result, status in (("처리", "PROCESSED"), ("미처리", "UNPROCESSED"), ("대기", "RESULT_PENDING")):
            with self.subTest(result=result):
                self.task_instance.xcom_pull.side_effect = [self.orders, self.candidates]
                self.orders[:] = [
                    {"pdno": "COMPLETED"},
                    {
                        "pdno": "PENDING",
                        "kor_item_shtn_name": "대기 종목",
                        "sll_buy_dvsn_cd": "02",
                        "tot_ccld_amt": "400",
                        "prcs_rslt": result,
                        "ord_dvsn_name": "현금매수",
                    },
                    {"pdno": "OTHER"},
                ]

                trade_order.change_status(task_instance=self.task_instance)

                self.put.assert_called_once()
                self.assertEqual(
                    self.put.call_args.kwargs["url"], "http://api:8000/v1/portfolio/put_fields?stock_symbol=PENDING"
                )
                expected = {"order_status": status}
                if status == "PROCESSED":
                    expected.update({"month_purchase_flag": True, "month_budget": 600, "reserved_budget": 0})
                self.assertEqual(json.loads(self.put.call_args.kwargs["data"]), expected)
                self.post.assert_called_once()
                self.assertEqual(
                    json.loads(self.post.call_args.kwargs["data"]),
                    {"channel_id": "test", "input_text": f"종목 PENDING: {trade_order.ORDER_STATUS_LABELS[status]}"},
                )
                self.put.reset_mock()
                self.post.reset_mock()


if __name__ == "__main__":
    unittest.main()
