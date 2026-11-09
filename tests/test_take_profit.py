import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import Mock, patch

import requests
from sqlmodel import SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fastapi_server"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "airflow" / "plugins"))

import trading_settings  # noqa: E402
from take_profit import TakeProfitService  # noqa: E402
from trader import Trader  # noqa: E402


class TakeProfitTests(unittest.TestCase):
    """실주문 없이 익절 경계값과 영속 중복 방지를 검증한다."""

    def setUp(self) -> None:
        """일시 DB와 장 마감 시각 및 모의 계좌를 준비한다."""
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = create_engine(f"sqlite:///{directory.name}/test.db", connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine)
        self.trader = Mock()
        self.holding = {"pdno": "005930", "hldg_qty": "11", "ord_psbl_qty": "11", "pchs_avg_pric": "100", "prpr": "150"}
        self.trader.inquire_balance.return_value = {"status_code": "200", "output": {"output1": [self.holding]}}
        self.trader.rsvn_stock.return_value = {"status_code": "200", "output": {"RSVN_ORD_SEQ": "123"}, "error": None}
        self.close = {"stck_bsop_date": "20261106", "stck_clpr": "150"}
        self.trader.inquire_daily_prices.return_value = {"status_code": "200", "output": [self.close]}
        self.order = {
            "rsvn_ord_seq": "123",
            "rsvn_ord_rcit_dt": "20261106",
            "pdno": "005930",
            "sll_buy_dvsn_cd": "01",
            "tot_ccld_qty": "0",
            "cncl_ord_dt": "",
            "prcs_rslt": "미처리",
        }
        self.trader.get_reserved_orders.return_value = {"status_code": "200", "output": [self.order]}
        self.service = TakeProfitService(self.engine, self.trader)
        clock = patch("take_profit.datetime")
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.clock.now.return_value = datetime(2026, 11, 6, 20, tzinfo=timezone(timedelta(hours=9)))

    def test_exact_threshold_sells_half_of_holdings_not_budget(self) -> None:
        """수익률 50%에 정확히 도달하면 홀수 수량의 절반을 내림한다."""
        self.service.run()
        self.trader.rsvn_stock.assert_called_once_with(
            stock_code="005930", ord_qty=5, ord_price=0, sll_buy_dvsn_cd="01", ord_dvsn_cd="01"
        )
        state = self.service.get_states()[0]
        self.assertEqual(state["status"], "accepted")
        self.assertEqual(state["filled_qty"], 0)

    def test_below_threshold_and_one_share_do_not_sell(self) -> None:
        """기준 미달 또는 한 주만 보유한 경우 매도하지 않는다."""
        self.close["stck_clpr"] = "149.999"
        self.service.run()
        self.close["stck_clpr"] = "200"
        self.holding["hldg_qty"] = "1"
        self.service.run()
        self.trader.rsvn_stock.assert_not_called()

    def test_closing_price_is_used_instead_of_balance_current_price(self) -> None:
        """장중 가격이 기준을 넘어도 종가 미달이면 매도를 예약하지 않는다."""
        self.holding["prpr"] = "200"
        self.close["stck_clpr"] = "149"
        self.service.run()
        self.trader.rsvn_stock.assert_not_called()
        self.holding["prpr"] = "100"
        self.close["stck_clpr"] = "150"
        self.service.run()
        self.trader.rsvn_stock.assert_called_once()

    def test_missing_today_close_does_not_use_previous_close(self) -> None:
        """휴장 등으로 당일 종가가 없으면 이전 거래일 가격을 사용하지 않는다."""
        self.close["stck_bsop_date"] = "20261105"
        self.service.run()
        self.trader.rsvn_stock.assert_not_called()

    def test_close_query_failure_does_not_submit_reservation(self) -> None:
        """종가 조회 실패를 잔고 현재가로 대체하지 않는다."""
        self.trader.inquire_daily_prices.return_value = {"status_code": "5xx"}
        with self.assertRaises(RuntimeError):
            self.service.run()
        self.trader.rsvn_stock.assert_not_called()

    def test_checks_all_account_holdings_and_latest_settings(self) -> None:
        """등록 포트폴리오와 무관하게 모든 계좌 종목에 최신 기준을 적용한다."""
        self.trader.inquire_balance.return_value["output"]["output1"].append(
            dict(self.holding, pdno="OTHER", hldg_qty="20", prpr="160")
        )
        settings = trading_settings.TradingSettingsService(self.engine)
        settings.update(trading_settings.TradingSettingsUpdate(take_profit_threshold=70))
        self.service.run()
        self.trader.rsvn_stock.assert_not_called()
        settings.update(trading_settings.TradingSettingsUpdate(take_profit_threshold=50))
        self.service.run()
        self.assertEqual(self.trader.rsvn_stock.call_count, 2)

    def test_partial_and_complete_fills_never_repeat_half_sale(self) -> None:
        """부분 체결과 재시작 후에도 원래 목표 수량을 추가 매도하지 않는다."""
        self.service.run()
        self.order["tot_ccld_qty"] = "2"
        self.holding.update(hldg_qty="9", ord_psbl_qty="6")
        TakeProfitService(self.engine, self.trader).run()
        self.assertEqual(self.service.get_states()[0]["status"], "accepted")
        self.order["tot_ccld_qty"] = "5"
        self.holding.update(hldg_qty="6", ord_psbl_qty="6")
        self.service.run()
        self.service.run()
        self.assertEqual(self.service.get_states()[0]["status"], "completed")
        self.trader.rsvn_stock.assert_called_once()

    def test_cancelled_partial_order_only_retries_unfilled_target(self) -> None:
        """부분 체결 후 취소되어도 남은 목표 수량만 재접수한다."""
        self.service.run()
        self.order.update(tot_ccld_qty="2", cncl_ord_dt="20261106")
        self.holding.update(hldg_qty="9", ord_psbl_qty="9")
        self.service.run()
        self.assertEqual(self.trader.rsvn_stock.call_args.kwargs["ord_qty"], 3)
        self.assertEqual(self.service.get_states()[0]["filled_qty"], 2)

    def test_processed_next_session_reservation_retries_only_remaining_shares(self) -> None:
        """일반예약 처리일이 끝나면 미체결 잔량만 다음 거래일로 예약한다."""
        self.service.run()
        self.clock.now.return_value = datetime(2026, 11, 9, 20, tzinfo=timezone(timedelta(hours=9)))
        self.close["stck_bsop_date"] = "20261109"
        self.order.update(tot_ccld_qty="2", prcs_rslt="처리")
        self.holding.update(hldg_qty="9", ord_psbl_qty="9")
        self.trader.rsvn_stock.return_value["output"]["RSVN_ORD_SEQ"] = "456"
        self.service.run()
        self.assertEqual(self.trader.rsvn_stock.call_args.kwargs["ord_qty"], 3)
        state = self.service.get_states()[0]
        self.assertEqual(state["filled_qty"], 2)
        self.assertEqual(state["order_number"], "456")
        self.assertEqual(state["order_date"], "20261109")

    def test_complete_exit_resets_only_after_confirmed_fill(self) -> None:
        """전량 청산을 확인한 뒤 재진입한 보유 구간에서 다시 한 번 익절한다."""
        self.service.run()
        self.order["tot_ccld_qty"] = "5"
        self.trader.inquire_balance.return_value["output"]["output1"] = []
        self.service.run()
        self.assertEqual(self.service.get_states(), [])
        self.trader.inquire_balance.return_value["output"]["output1"] = [self.holding]
        self.service.run()
        self.assertEqual(self.trader.rsvn_stock.call_count, 2)

    def test_orderable_quantity_does_not_reduce_half_target(self) -> None:
        """다른 주문으로 매도 가능 수량이 부족하면 목표 수량을 줄이지 않는다."""
        self.holding["ord_psbl_qty"] = "4"
        self.service.run()
        self.trader.rsvn_stock.assert_not_called()
        self.assertEqual(self.service.get_states(), [])

    def test_lost_broker_response_and_unknown_result_block_resubmission(self) -> None:
        """증권사 응답 유실 시 접수 의도를 보존하여 재매도를 차단한다."""
        self.trader.rsvn_stock.side_effect = requests.Timeout("응답 유실")
        with self.assertRaises(requests.Timeout):
            self.service.run()
        self.service.run()
        self.trader.rsvn_stock.assert_called_once()
        self.assertEqual(self.service.get_states()[0]["status"], "pending")

    def test_server_error_remains_unknown_after_restart(self) -> None:
        """오류 응답이 실제 접수 실패인지 불명확하면 자동 재접수하지 않는다."""
        self.trader.rsvn_stock.return_value = {"status_code": "5xx", "output": {}, "error": "timeout"}
        self.service.run()
        TakeProfitService(self.engine, self.trader).run()
        self.trader.rsvn_stock.assert_called_once()
        self.assertEqual(self.service.get_states()[0]["status"], "unknown")

    def test_explicit_rejection_can_retry(self) -> None:
        """명시적으로 거절된 주문은 다음 검사에서 다시 시도할 수 있다."""
        self.trader.rsvn_stock.return_value = {"status_code": "4xx", "output": {}, "error": "거절"}
        self.service.run()
        self.service.run()
        self.assertEqual(self.trader.rsvn_stock.call_count, 2)

    def test_failed_queries_do_not_sell_or_reset_state(self) -> None:
        """잔고 및 체결 조회 실패를 빈 결과로 취급하지 않는다."""
        self.trader.inquire_balance.return_value = {"status_code": "5xx", "error": "실패"}
        with self.assertRaises(RuntimeError):
            self.service.run()
        self.trader.rsvn_stock.assert_not_called()
        self.trader.inquire_balance.return_value = {"status_code": "200", "output": {"output1": [self.holding]}}
        self.service.run()
        self.trader.get_reserved_orders.return_value = {"status_code": "5xx"}
        with self.assertRaises(RuntimeError):
            self.service.run()
        self.assertEqual(self.service.get_states()[0]["status"], "accepted")
        self.trader.rsvn_stock.assert_called_once()

    def test_journal_failure_prevents_order(self) -> None:
        """최초 접수 기록 저장이 실패하면 외부 주문을 수행하지 않는다."""
        trading_settings.TradingSettingsService(self.engine).get()
        with patch("take_profit.Session.commit", side_effect=RuntimeError("DB 실패")):
            with self.assertRaises(RuntimeError):
                self.service.run()
        self.trader.rsvn_stock.assert_not_called()

    def test_concurrent_checks_submit_once(self) -> None:
        """동시 검사도 영속 접수 의도를 확인하여 종목당 한 번만 매도한다."""
        entered, release = Event(), Event()

        def sell(**kwargs: object) -> dict:
            """주문 응답을 지연시켜 동시 검사를 재현한다."""
            entered.set()
            if not release.wait(5):
                raise RuntimeError("테스트 시간 초과")
            return {"status_code": "200", "output": {"RSVN_ORD_SEQ": "123"}}

        self.trader.rsvn_stock.side_effect = sell
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.service.run)
            try:
                self.assertTrue(entered.wait(5))
                self.service.run()
            finally:
                release.set()
            first.result(timeout=5)
        self.trader.rsvn_stock.assert_called_once()

    def test_reservation_hours_guard(self) -> None:
        """장중·주말·공휴일·예약 접수 중단 시각에는 주문하지 않는다."""
        for timestamp in [
            datetime(2026, 11, 6, 10),
            datetime(2026, 11, 7, 20),
            datetime(2026, 12, 25, 20),
            datetime(2026, 11, 6, 23, 40),
        ]:
            self.clock.now.return_value = timestamp
            self.assertEqual(self.service.run()["status"], "outside_reservation_hours")
        self.trader.inquire_balance.assert_not_called()

    def test_reserved_sales_do_not_update_monthly_purchase_budget(self) -> None:
        """기존 예약매수 확인 작업은 익절 예약매도를 예산 변경에서 제외한다."""
        import trade_order

        task = Mock()
        task.xcom_pull.side_effect = [
            [{"pdno": "005930", "sll_buy_dvsn_cd": "01"}],
            [{"stock_symbol": "005930", "month_budget": 1000}],
        ]
        with patch.object(trade_order.requests, "put") as put, patch.object(trade_order.requests, "post") as post:
            trade_order.change_status(task_instance=task)
        put.assert_not_called()
        post.assert_not_called()


class TraderPaginationTests(unittest.TestCase):
    """한투 연속 조회와 시장가 주문 파라미터를 검증한다."""

    def setUp(self) -> None:
        """인증 없이 모의 요청을 수행할 클라이언트를 준비한다."""
        self.trader = Trader("key", "secret", "https://example.test", "DEV")

    def test_balance_includes_every_page(self) -> None:
        """두 번째 페이지의 종목도 잔고 결과에 포함한다."""
        results = [
            {
                "status_code": "200",
                "tr_cont": "M",
                "output": {"output1": [{"pdno": "A"}], "ctx_area_fk100": "fk", "ctx_area_nk100": "nk"},
            },
            {"status_code": "200", "tr_cont": "", "output": {"output1": [{"pdno": "B"}]}},
        ]
        with (
            patch.object(self.trader, "hashkey", return_value="hash"),
            patch.object(self.trader, "_request", side_effect=results) as request,
        ):
            result = self.trader.inquire_balance()
        self.assertEqual(result["output"]["output1"], [{"pdno": "A"}, {"pdno": "B"}])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args.args[2]["tr_cont"], "N")

    def test_reserved_orders_include_every_page(self) -> None:
        """예약매도도 20건 이후의 연속조회 페이지까지 포함한다."""
        results = [
            {
                "status_code": "200",
                "tr_cont": "M",
                "output": [{"rsvn_ord_seq": "A"}],
                "ctx_area_fk200": "fk",
                "ctx_area_nk200": "nk",
            },
            {"status_code": "200", "tr_cont": "", "output": [{"rsvn_ord_seq": "B"}]},
        ]
        with (
            patch.object(self.trader, "hashkey", return_value="hash"),
            patch.object(self.trader, "_request", side_effect=results) as request,
        ):
            result = self.trader.get_reserved_orders("20261106", "20261109")
        self.assertEqual(result["output"], [{"rsvn_ord_seq": "A"}, {"rsvn_ord_seq": "B"}])
        self.assertEqual(request.call_args.args[1]["CTX_AREA_NK200"], "nk")

    def test_daily_prices_use_krx_daily_unadjusted_prices(self) -> None:
        """다음날 예약 판단에는 KRX 원주가의 일별 종가를 요청한다."""
        with patch.object(self.trader, "_request") as request:
            self.trader.inquire_daily_prices("005930")
        payload = request.call_args.args[1]
        self.assertEqual(payload["FID_COND_MRKT_DIV_CODE"], "J")
        self.assertEqual(payload["FID_PERIOD_DIV_CODE"], "D")
        self.assertEqual(payload["FID_ORG_ADJ_PRC"], "0")

    def test_reservation_sale_keeps_existing_buy_defaults(self) -> None:
        """익절은 다음 거래일 시장가 예약매도로, 기존 예약은 지정가 매수로 접수한다."""
        with (
            patch.object(self.trader, "hashkey", return_value="hash"),
            patch.object(self.trader, "_request") as request,
        ):
            self.trader.rsvn_stock("TEST", 5, 0, sll_buy_dvsn_cd="01", ord_dvsn_cd="01")
            payload = request.call_args.args[1]
            self.assertEqual(payload["ORD_DVSN_CD"], "01")
            self.assertEqual(payload["SLL_BUY_DVSN_CD"], "01")
            self.assertEqual(payload["ORD_UNPR"], "0")
            self.assertNotIn("RSVN_ORD_END_DT", payload)
            self.trader.rsvn_stock("TEST", 5, 150)
            self.assertEqual(request.call_args.args[1]["ORD_DVSN_CD"], "00")
            self.assertEqual(request.call_args.args[1]["SLL_BUY_DVSN_CD"], "02")


if __name__ == "__main__":
    unittest.main()
