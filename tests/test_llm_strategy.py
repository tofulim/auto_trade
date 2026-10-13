import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
        self.response = Mock()
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

    def test_http_errors_return_hold(self):
        for status in [401, 429, 503]:
            with self.subTest(status=status):
                self.response.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
                decision, reasoning, confidence = self.analyze()
                self.assertEqual((decision, confidence), ("HOLD", 0.0))
                self.assertIn("LLM analysis failed", reasoning)

    def test_timeout_returns_hold(self):
        self.post.side_effect = TimeoutError("Request timed out")
        self.assertEqual(self.analyze()[::2], ("HOLD", 0.0))
        self.post.assert_called_once()

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
