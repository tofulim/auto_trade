import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fastapi_server"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "airflow" / "plugins"))

from controllers.settings_controller import router  # noqa: E402
from trading_settings import TradingSettingsService  # noqa: E402


class TradingSettingsTests(unittest.TestCase):
    """실제 HTTP 요청으로 설정 검증과 DB 영속성을 확인한다."""

    def setUp(self) -> None:
        """일시 SQLite와 설정 라우터만 가진 앱을 생성한다."""
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.engine = create_engine(
            f"sqlite:///{directory.name}/settings.db", connect_args={"check_same_thread": False}
        )
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine)
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        dependency = patch(
            "controllers.settings_controller.inject.instance", return_value=SimpleNamespace(engine=self.engine)
        )
        dependency.start()
        self.addCleanup(dependency.stop)
        environment = patch.dict(
            "os.environ",
            {"PERIOD_DAYS": "30", "TAKE_PROFIT_THRESHOLD": "50", "PURCHASE_THRESHOLD": "3", "SELL_THRESHOLD": "-25"},
        )
        environment.start()
        self.addCleanup(environment.stop)

    def test_defaults_and_partial_update_persist_after_restart(self) -> None:
        """일부 필드만 변경하고 서비스 재생성 후에도 같은 설정을 읽는다."""
        response = self.client.get("/v1/settings/trading")
        self.assertEqual(response.status_code, 200)
        original = response.json()
        self.assertEqual(original["take_profit_threshold"], 50)
        response = self.client.put("/v1/settings/trading", json={"take_profit_threshold": 60})
        self.assertEqual(response.status_code, 200)
        expected = dict(original, take_profit_threshold=60)
        self.assertEqual(response.json(), expected)
        with patch.dict("os.environ", {"TAKE_PROFIT_THRESHOLD": "90"}):
            self.assertEqual(TradingSettingsService(self.engine).get(), expected)

    def test_invalid_updates_leave_settings_unchanged(self) -> None:
        """잘못된 값과 알 수 없는 키를 거절하고 기존 설정을 보존한다."""
        original = self.client.get("/v1/settings/trading").json()
        for payload in [
            {"take_profit_threshold": -1},
            {"take_profit_threshold": 0},
            {"take_profit_threshold": "NaN"},
            {"take_profit_threshold": "Infinity"},
            {"take_profit_threshold": None},
            {"period_days": 0},
            {"period_days": 366},
            {"purchase_threshold": "Infinity"},
            {"sell_threshold": "NaN"},
            {"unknown": 1},
        ]:
            with self.subTest(payload=payload):
                response = self.client.put("/v1/settings/trading", json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(self.client.get("/v1/settings/trading").json(), original)

    def test_prediction_settings_can_be_changed_together(self) -> None:
        """기존 환경변수 기반의 예측 관련 숫자도 함께 변경한다."""
        values = {"purchase_threshold": 5, "sell_threshold": -15, "period_days": 60}
        response = self.client.put("/v1/settings/trading", json=values)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), dict(values, take_profit_threshold=50))

    def test_llm_prompt_uses_requested_prediction_period(self) -> None:
        """LLM의 예측 기간 설명에도 변경한 기간을 전달한다."""
        from llm_strategy import LLMTradingStrategy

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            strategy = LLMTradingStrategy()
        with (
            patch.object(strategy, "_get_market_context", return_value={}) as market,
            patch.object(strategy, "_generate_response", return_value='{"decision": "HOLD"}') as generate,
        ):
            strategy.analyze_stock_and_decide("TEST.KS", 3, {}, 100, period_days=60)
        market.assert_called_once_with("TEST.KS", 60)
        self.assertIn("over next 60 days", generate.call_args.args[0])

    def test_airflow_decision_receives_runtime_settings(self) -> None:
        """Airflow가 환경변수 대신 최신 API 설정으로 의사결정한다."""
        import prophesy

        values = {"purchase_threshold": 5, "sell_threshold": -15, "period_days": 60}
        self.client.put("/v1/settings/trading", json=values)
        settings = TradingSettingsService(self.engine).get()
        portfolio = Mock()
        portfolio.json.return_value = [{"stock_symbol": "TEST", "month_budget": 1000, "order_status": "N"}]
        prediction = Mock()
        prediction.json.return_value = {"TEST.KS": {"last_price": 100, "diff_rate": 4}}
        with (
            patch.object(prophesy, "get_trading_settings", return_value=settings),
            patch.object(prophesy.requests, "post", side_effect=[portfolio, prediction, Mock()]),
            patch.object(prophesy, "_get_statistics", return_value={}),
            patch.object(prophesy, "_get_behavior", return_value=(prophesy.STAY, "보유")) as behavior,
        ):
            prophesy.prophesy_portfolio(task_instance=Mock())
        for key, value in values.items():
            self.assertEqual(behavior.call_args.kwargs[key], value)


if __name__ == "__main__":
    unittest.main()
