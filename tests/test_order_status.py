import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fastapi_server"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "airflow" / "plugins"))

import asset_update  # noqa: E402
import prophesy  # noqa: E402
import trade_order  # noqa: E402
from database.database import Database  # noqa: E402
from entity.portfolio import LEGACY_ORDER_STATUSES, Portfolio, PortfolioBase  # noqa: E402
from repository.portfolio_repository_service import PortfolioRepositoryService  # noqa: E402


class OrderStatusStorageTests(unittest.TestCase):
    """기존 데이터 변환과 API 저장 경로의 호환성을 검증한다."""

    def setUp(self) -> None:
        """실제 계좌와 분리된 임시 DB를 준비한다."""
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / "test.db")
        self.db = Database(self.path)
        self.addCleanup(self.db.engine.dispose)
        self.repository = PortfolioRepositoryService(self.db)

    def test_startup_migrates_once_without_changing_other_fields(self) -> None:
        """기존 코드만 변환하고 재시작 시 새 값과 다른 필드를 보존한다."""
        with Session(self.db.engine) as session:
            for status in (*LEGACY_ORDER_STATUSES, "PROCESSED"):
                session.add(Portfolio(stock_symbol=status, ratio=0.5, order_status=status, month_budget=1000))
            session.commit()
            before = {row.stock_symbol: row.dict() for row in session.exec(select(Portfolio)).all()}

        for _ in range(2):
            migrated = Database(self.path)
            with Session(migrated.engine) as session:
                for row in session.exec(select(Portfolio)).all():
                    expected = dict(before[row.stock_symbol])
                    expected["order_status"] = LEGACY_ORDER_STATUSES.get(row.stock_symbol, row.stock_symbol)
                    self.assertEqual(row.dict(), expected)
            migrated.engine.dispose()

    def test_repository_normalizes_legacy_writes(self) -> None:
        """생성·전체 수정·부분 수정 모두 새 단어를 저장한다."""
        for legacy, status in LEGACY_ORDER_STATUSES.items():
            with self.subTest(status=status):
                self.repository.add(Portfolio(stock_symbol=legacy, ratio=0.5, order_status=legacy))
                self.assertEqual(self.repository.get([legacy])[0]["order_status"], status)
                self.repository.update_fields(legacy, {"order_status": "NOT_ORDERED"})
                self.repository.update(legacy, PortfolioBase(stock_symbol=legacy, ratio=0.5, order_status=legacy))
                self.assertEqual(self.repository.get([legacy])[0]["order_status"], status)
                self.repository.update_fields(legacy, {"order_status": "NOT_ORDERED"})
                self.repository.update_fields(legacy, {"order_status": legacy})
                self.assertEqual(self.repository.get([legacy])[0]["order_status"], status)
        self.assertEqual(PortfolioBase(stock_symbol="DEFAULT", ratio=0.5).order_status, "NOT_ORDERED")


class OrderStatusNotificationTests(unittest.TestCase):
    """DB에는 명확한 단어를 저장하고 알림에는 한국어를 표시한다."""

    def test_monthly_distribution_resets_to_not_ordered(self) -> None:
        """월 예산 배분 시 주문 상태를 새 기본값으로 초기화한다."""
        task = Mock()
        task.xcom_pull.side_effect = [2000, [{"stock_symbol": "TEST", "ratio": 0.5}]]
        with patch.object(asset_update.requests, "post"), patch.object(asset_update.requests, "put") as put:
            put.return_value.status_code = 200
            self.assertTrue(asset_update.distribute_asset(task_instance=task))
        self.assertEqual(
            json.loads(put.call_args.kwargs["data"]),
            {"month_budget": 1000, "month_purchase_flag": False, "order_status": "NOT_ORDERED"},
        )

    def test_order_results_and_processing_error(self) -> None:
        """증권사 결과와 처리 예외를 구분하고 저장 값과 알림을 검증한다."""
        cases = (
            ("처리", "400", "PROCESSED", "주문 처리 완료"),
            ("미처리", "0", "UNPROCESSED", "미처리"),
            ("확인 중", "0", "RESULT_PENDING", "처리 결과 확인 대기"),
            ("처리", "invalid", "PROCESSING_ERROR", "주문 결과 처리 중 오류"),
        )
        for result, amount, status, label in cases:
            with self.subTest(status=status):
                task = Mock()
                task.xcom_pull.side_effect = [
                    [
                        {
                            "pdno": "TEST",
                            "kor_item_shtn_name": "테스트",
                            "sll_buy_dvsn_cd": "02",
                            "tot_ccld_amt": amount,
                            "prcs_rslt": result,
                            "ord_dvsn_name": "현금매수",
                        }
                    ],
                    [{"stock_symbol": "TEST", "month_budget": 1000}],
                ]
                with patch.object(trade_order.requests, "post") as post, patch.object(
                    trade_order.requests, "put"
                ) as put:
                    trade_order.change_status(task_instance=task)
                post.assert_called_once()
                message = json.loads(post.call_args.kwargs["data"])["input_text"]
                self.assertIn(label, message)
                if status == "PROCESSING_ERROR":
                    self.assertIn("주문 실패 여부는 별도 확인", message)
                    put.assert_not_called()
                else:
                    put.assert_called_once()
                    data = json.loads(put.call_args.kwargs["data"])
                    expected = {"order_status": status}
                    if status == "PROCESSED":
                        expected.update({"month_purchase_flag": True, "month_budget": 600, "reserved_budget": 0})
                    self.assertEqual(data, expected)

    def test_pending_selection_accepts_new_and_legacy_statuses(self) -> None:
        """전환 중 구형·신형 대기 상태를 모두 선택하고 완료 상태는 제외한다."""
        statuses = ["N", "NOT_ORDERED", "O", "RESERVATION_ACCEPTED", "W", "RESULT_PENDING", "S", "PROCESSED"]
        rows = [{"stock_symbol": status, "order_status": status} for status in statuses]
        task = Mock()
        with patch.object(trade_order, "get_portfolio_rows", return_value=rows):
            self.assertEqual(trade_order.check_order_exist("next", task_instance=task), "next")
        selected = task.xcom_push.call_args.kwargs["value"]
        self.assertEqual(
            [row["order_status"] for row in selected], ["O", "RESERVATION_ACCEPTED", "W", "RESULT_PENDING"]
        )

    def test_purchase_eligibility_is_unchanged(self) -> None:
        """기존 코드와 새 단어 모두 주문 전·미처리 상태에서만 매수한다."""
        for legacy, status in LEGACY_ORDER_STATUSES.items():
            for value in (legacy, status):
                with self.subTest(status=value):
                    behavior, _ = prophesy._get_behavior(
                        diff_rate=0.1,
                        statistics={"rsi": 30, "ma": {"day5": 90, "day20": 100}, "zscore": -1},
                        order_status=value,
                        purchase_threshold=0.05,
                        sell_threshold=-0.05,
                    )
                    expected = prophesy.PURCHASE if legacy in ("N", "F") else prophesy.STAY
                    self.assertEqual(behavior, expected)


if __name__ == "__main__":
    unittest.main()
