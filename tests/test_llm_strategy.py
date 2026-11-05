import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from curl_cffi.requests.exceptions import ConnectionError, HTTPError, Timeout

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fastapi_server"))

from controllers.llm_controller import LLMAnalysisRequest  # noqa: E402
from controllers.llm_controller import analyze_stock_with_llm  # noqa: E402
from controllers.llm_controller import check_llm_health  # noqa: E402
from llm_strategy import LLMTradingStrategy, get_llm_decision  # noqa: E402


class OpenRouterStrategyTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        market = patch.object(LLMTradingStrategy, "_get_market_context", return_value={})
        market.start()
        self.addCleanup(market.stop)
        post = patch("llm_strategy.curl_requests.post")
        self.post = post.start()
        self.addCleanup(post.stop)
        sleep = patch("llm_strategy.time.sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)
        self.response = Mock(status_code=200)
        self.response.json.return_value = {
            "choices": [
                {"message": {"content": json.dumps({"decision": "BUY", "reasoning": "분석 근거", "confidence": 0.85})}}
            ]
        }
        self.post.return_value = self.response

    def analyze(self):
        return LLMTradingStrategy().analyze_stock_and_decide("005930.KS", 3.0, {}, 70000)

    def test_default_router_request_and_decision(self):
        self.assertEqual(self.analyze(), ("BUY", "분석 근거", 0.85))
        args, kwargs = self.post.call_args
        self.assertEqual(args, ("https://openrouter.ai/api/v1/chat/completions",))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["headers"]["HTTP-Referer"], "https://github.com/tofulim/auto_trade")
        self.assertEqual(kwargs["headers"]["X-OpenRouter-Title"], "GitHub auto-trade")
        self.assertEqual(kwargs["json"]["model"], "openrouter/free")
        self.assertEqual(kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertTrue(kwargs["json"]["provider"]["require_parameters"])
        self.assertIn("005930", kwargs["json"]["messages"][0]["content"])
        self.assertEqual(kwargs["timeout"], 60)
        self.response.raise_for_status.assert_called_once()

    def test_specific_free_model(self):
        with patch.dict("os.environ", {"OPENROUTER_MODEL": " vendor/model:free "}):
            self.analyze()
        self.assertEqual(self.post.call_args.kwargs["json"]["model"], "vendor/model:free")

    def test_blank_model_uses_default(self):
        with patch.dict("os.environ", {"OPENROUTER_MODEL": " "}):
            self.assertEqual(LLMTradingStrategy().model, "openrouter/free")

    def test_missing_key_disables_strategy(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "legacy-key"}, clear=True):
            self.assertFalse(LLMTradingStrategy().is_enabled())
            self.assertEqual(self.analyze(), ("HOLD", "LLM strategy disabled", 0.0))
            self.assertFalse(get_llm_decision("005930.KS", 3.0, {}, 70000)["enabled"])
        self.post.assert_not_called()

    def test_paid_models_are_rejected(self):
        for model in ["openrouter/auto", "vendor/paid-model"]:
            with self.subTest(model=model), patch.dict("os.environ", {"OPENROUTER_MODEL": model}):
                self.assertFalse(LLMTradingStrategy().is_enabled())
                self.assertEqual(self.analyze()[0], "HOLD")
        self.post.assert_not_called()

    def test_non_retryable_http_errors_return_hold(self) -> None:
        """인증과 요청 오류는 재시도하지 않고 기존 실패 결과를 반환한다."""
        for status in [400, 401, 402, 403]:
            with self.subTest(status=status):
                self.post.reset_mock()
                self.response.status_code = status
                self.response.raise_for_status.side_effect = HTTPError(f"HTTP {status}", response=self.response)
                self.assertEqual(self.analyze()[::2], ("HOLD", 0.0))
                self.post.assert_called_once()
                self.sleep.assert_not_called()

    def test_transient_http_errors_retry_twice_and_recover(self) -> None:
        """일시적 HTTP 오류 후 두 번까지 대기하고 재시도하여 분석을 복구한다."""
        for status in [408, 429, 500, 502, 503, 504]:
            with self.subTest(status=status):
                self.post.reset_mock()
                self.sleep.reset_mock()
                self.response.status_code = status
                error = HTTPError(f"HTTP {status}", response=self.response)
                self.response.raise_for_status.side_effect = [error, error, None]
                self.assertEqual(self.analyze(), ("BUY", "분석 근거", 0.85))
                self.assertEqual(self.post.call_count, 3)
                self.assertEqual(self.sleep.call_args_list, [call(5), call(10)])

    def test_persistent_http_error_stops_after_three_attempts(self) -> None:
        """503이 계속되면 총 세 번 호출한 뒤 기존 실패 결과를 반환한다."""
        self.response.status_code = 503
        self.response.raise_for_status.side_effect = HTTPError("HTTP 503", response=self.response)
        decision, reasoning, confidence = self.analyze()
        self.assertEqual((decision, confidence), ("HOLD", 0.0))
        self.assertIn("HTTP 503", reasoning)
        self.assertEqual(self.post.call_count, 3)
        self.assertEqual(self.sleep.call_args_list, [call(5), call(10)])

    def test_transport_errors_retry_and_recover(self) -> None:
        """타임아웃과 연결 오류도 재시도하여 정상 응답을 사용한다."""
        for error_type in [Timeout, ConnectionError]:
            with self.subTest(error_type=error_type):
                self.post.reset_mock()
                self.sleep.reset_mock()
                self.post.side_effect = [error_type("Temporary failure"), self.response]
                self.assertEqual(self.analyze(), ("BUY", "분석 근거", 0.85))
                self.assertEqual(self.post.call_count, 2)
                self.sleep.assert_called_once_with(5)

    def test_timeout_returns_hold_after_two_retries(self) -> None:
        """타임아웃이 계속되면 재시도 한도 이후 실패 결과를 반환한다."""
        self.post.side_effect = Timeout("Request timed out")
        self.assertEqual(self.analyze()[::2], ("HOLD", 0.0))
        self.assertEqual(self.post.call_count, 3)
        self.assertEqual(self.sleep.call_args_list, [call(5), call(10)])

    def test_invalid_provider_responses_return_hold(self):
        responses = [{"error": {"message": "Cannot buy tokens"}}, {"choices": []}] + [
            {"choices": [{"message": {"content": content}}]} for content in [None, "", "  ", []]
        ]
        for data in responses:
            with self.subTest(data=data):
                self.response.json.return_value = data
                self.assertEqual(self.analyze()[::2], ("HOLD", 0.0))

    def test_invalid_json_envelope_returns_hold(self):
        self.response.json.side_effect = ValueError("Invalid JSON")
        self.assertEqual(self.analyze()[::2], ("HOLD", 0.0))

    def test_api_response_contract(self):
        request = LLMAnalysisRequest(
            stock_symbol="005930.KS", prophet_diff_rate=3.0, statistics={}, current_price=70000
        )
        self.assertEqual(
            analyze_stock_with_llm(request).dict(),
            {"decision": "BUY", "reasoning": "분석 근거", "confidence": 0.85, "enabled": True},
        )

    def test_health_checks_configuration_without_network(self):
        self.assertTrue(check_llm_health()["enabled"])
        self.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
