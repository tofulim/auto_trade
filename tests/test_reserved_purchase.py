import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "airflow" / "plugins"))

import prophesy  # noqa: E402


class ReservedPurchaseTests(unittest.TestCase):
    """실주문 없이 예약매수 경로와 실패 시 상태 보존을 검증한다."""

    def setUp(self) -> None:
        """외부 요청과 주문 조회를 모의 객체로 대체한다."""
        env = patch.dict("os.environ", {"FASTAPI_SERVER_HOST": "api", "FASTAPI_SERVER_PORT": "8000"})
        env.start()
        self.addCleanup(env.stop)
        self.task_instance = Mock()
        self.task_instance.xcom_pull.return_value = [("TEST", prophesy.PURCHASE, 0.0, 1000, 100.0)]
        patches = {
            "orders": patch.object(prophesy, "_get_rsvn_orders", return_value=[]),
            "cancel": patch.object(prophesy, "check_rsvn_order_n_cancel"),
            "end_date": patch.object(prophesy, "_get_end_dt", return_value=datetime(2026, 11, 2)),
            "post": patch.object(prophesy.requests, "post"),
            "put": patch.object(prophesy.requests, "put"),
        }
        for name, patcher in patches.items():
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)
        self.post.return_value.json.return_value = {"status_code": "200", "output": {}, "error": None}

    def test_success_uses_reserved_endpoint_and_updates_state(self) -> None:
        """예약 접수 성공 후에만 예약금과 주문 대기 상태를 저장한다."""
        prophesy.execute_decisions(task_instance=self.task_instance)

        self.cancel.assert_called_once_with(rsvn_orders=[], stock_symbol="TEST")
        self.post.assert_called_once()
        self.assertEqual(self.post.call_args.kwargs["url"], "http://api:8000/v1/trader/rsvn_buy")
        self.assertEqual(
            json.loads(self.post.call_args.kwargs["data"]),
            {"stock_symbol": "TEST", "ord_qty": 10, "ord_price": 100, "rsvn_ord_end_dt": "20261102"},
        )
        self.put.assert_called_once()
        self.assertEqual(
            json.loads(self.put.call_args.kwargs["data"]),
            {"reserved_budget": 1000, "order_status": "RESERVATION_ACCEPTED"},
        )

    def test_rejected_order_fails_without_updating_state(self) -> None:
        """업무 오류를 발생시켜 Airflow가 성공 처리하지 않게 한다."""
        for status in ["4xx", "5xx"]:
            with self.subTest(status=status):
                self.post.return_value.json.return_value = {"status_code": status, "output": {}, "error": "접수 거절"}
                with self.assertRaisesRegex(RuntimeError, "TEST.*접수 거절"):
                    prophesy.execute_decisions(task_instance=self.task_instance)
                self.put.assert_not_called()

    def test_http_error_does_not_update_state(self) -> None:
        """예약매수 HTTP 오류를 전달하고 DB 갱신을 생략한다."""
        self.post.return_value.raise_for_status.side_effect = requests.HTTPError("503")
        with self.assertRaises(requests.HTTPError):
            prophesy.execute_decisions(task_instance=self.task_instance)
        self.put.assert_not_called()

    def test_connection_error_does_not_update_state(self) -> None:
        """연결 실패 시 주문 대기 상태를 만들지 않는다."""
        self.post.side_effect = requests.ConnectionError("연결 실패")
        with self.assertRaises(requests.ConnectionError):
            prophesy.execute_decisions(task_instance=self.task_instance)
        self.put.assert_not_called()

    def test_state_update_error_is_propagated(self) -> None:
        """접수 후 DB 갱신이 실패해도 작업을 성공 처리하지 않는다."""
        self.put.return_value.raise_for_status.side_effect = requests.HTTPError("500")
        with self.assertRaises(requests.HTTPError):
            prophesy.execute_decisions(task_instance=self.task_instance)

    def test_no_purchase_does_not_submit_order(self) -> None:
        """관망 또는 한 주 미만 예산일 때 주문과 상태 갱신을 생략한다."""
        for behavior, budget in [(prophesy.STAY, 1000), (prophesy.PURCHASE, 99)]:
            with self.subTest(behavior=behavior, budget=budget):
                self.task_instance.xcom_pull.return_value = [("TEST", behavior, 0.0, budget, 100.0)]
                prophesy.execute_decisions(task_instance=self.task_instance)
                self.cancel.assert_not_called()
                self.post.assert_not_called()
                self.put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
