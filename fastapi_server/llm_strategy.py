"""
LLM-based trading strategy using Google Gemini.

This module provides AI-powered trading decisions with economic reasoning,
complementing the existing Prophet and statistical analysis strategies.
"""

import json
import os
from typing import Dict, Tuple

import google.generativeai as genai
import yfinance as yf
from curl_cffi import requests as curl_requests
from utils import setup_logger

logger = setup_logger(__name__)


class LLMTradingStrategy:
    """
    LLM-based trading strategy using Google Gemini for generating
    trading decisions with economic reasoning.
    """

    def __init__(self):
        """Initialize the LLM trading strategy."""
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. LLM strategy will be disabled.", extra={"endpoint_name": "init"})
            self.enabled = False
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
            self.enabled = True
            logger.info("LLM trading strategy initialized successfully", extra={"endpoint_name": "init"})
        except Exception as e:
            logger.error(f"Failed to initialize LLM strategy: {e}", extra={"endpoint_name": "init"})
            self.enabled = False

    def analyze_stock_and_decide(
        self, stock_symbol: str, prophet_diff_rate: float, statistics: Dict, current_price: float, period_days: int = 30
    ) -> Tuple[str, str, float]:
        """
        Analyze stock using LLM and provide trading decision with reasoning.

        Args:
            stock_symbol (str): Stock symbol (e.g., "005930.KS")
            prophet_diff_rate (float): Prophet model's predicted change rate
            statistics (Dict): Technical statistics (RSI, MA, Z-score)
            current_price (float): Current stock price
            period_days (int): Analysis period in days

        Returns:
            Tuple[str, str, float]: (decision, reasoning, confidence_score)
            - decision: "BUY", "SELL", or "HOLD"
            - reasoning: Detailed economic reasoning
            - confidence_score: Confidence level (0.0 to 1.0)
        """
        if not self.enabled:
            return "HOLD", "LLM strategy disabled", 0.0

        try:
            # Get recent market data
            market_data = self._get_market_context(stock_symbol, period_days)

            # Generate LLM prompt
            prompt = self._create_analysis_prompt(
                stock_symbol=stock_symbol,
                prophet_diff_rate=prophet_diff_rate,
                statistics=statistics,
                current_price=current_price,
                market_data=market_data,
            )

            # Get LLM response
            response = self.model.generate_content(prompt)

            # Parse LLM response
            decision, reasoning, confidence = self._parse_llm_response(response.text)

            logger.info(
                f"LLM analysis for {stock_symbol}: {decision} (confidence: {confidence})",
                extra={"endpoint_name": "analyze"},
            )
            return decision, reasoning, confidence

        except Exception as e:
            logger.error(f"Error in LLM analysis for {stock_symbol}: {e}", extra={"endpoint_name": "analyze"})
            return "HOLD", f"LLM analysis failed: {str(e)}", 0.0

    def _get_market_context(self, stock_symbol: str, period_days: int) -> Dict:
        """Get market context data for analysis."""
        try:
            session = curl_requests.Session(impersonate="chrome")

            # Get stock data
            stock_data = yf.download(stock_symbol, period=f"{period_days}d", session=session)

            if stock_data.empty:
                return {"error": "No market data available"}

            # Calculate basic metrics
            latest_close = stock_data["Close"].iloc[-1].values[0]
            period_start_close = stock_data["Close"].iloc[0].values[0]
            price_change = ((latest_close - period_start_close) / period_start_close) * 100
            # Volume analysis
            avg_volume = stock_data["Volume"].mean().values[0]
            recent_volume = stock_data["Volume"].iloc[-5:].mean().values[0]  # Last 5 days
            volume_trend = "increasing" if recent_volume > avg_volume else "decreasing"
            # Volatility
            volatility = stock_data["Close"].pct_change().std().values[0] * 100

            hight_52w = stock_data["High"].max().values[0]
            low_52w = stock_data["Low"].min().values[0]

            return {
                "price_change_period": round(price_change, 2),
                "volume_trend": volume_trend,
                "volatility": round(volatility, 2),
                "trading_days": len(stock_data),
                "high_52w": high_52w,
                "low_52w": low_52w,
                "current_vs_high": round(((latest_close - high_52w) / high_52w) * 100, 2),
                "current_vs_low": round(((latest_close - low_52w) / low_52w) * 100, 2),
            }

        except Exception as e:
            logger.error(f"Error getting market context: {e}", extra={"endpoint_name": "get_market_context"})
            return {"error": str(e)}

    def _create_analysis_prompt(
        self, stock_symbol: str, prophet_diff_rate: float, statistics: Dict, current_price: float, market_data: Dict
    ) -> str:
        """Create comprehensive analysis prompt for LLM."""

        # Determine stock market (Korean or US)
        market = "Korean (KS)" if ".KS" in stock_symbol else "US"
        clean_symbol = stock_symbol.replace(".KS", "").replace(".US", "")

        prompt = f"""
        You are an expert financial analyst providing trading recommendations for automated trading system.

        STOCK ANALYSIS REQUEST:
        Stock Symbol: {clean_symbol} (Market: {market})
        Current Price: ${current_price:.2f}

        TECHNICAL ANALYSIS DATA:
        - Prophet Model Prediction: {prophet_diff_rate:.2f}% change expected over next 30 days
        - RSI: {statistics.get('rsi', 'N/A')}
        - Moving Averages: 5-day: {statistics.get('ma', {}).get('day5', 'N/A')}, 10-day: {statistics.get('ma', {}).get('day10', 'N/A')}, 20-day: {statistics.get('ma', {}).get('day20', 'N/A')}, 60-day: {statistics.get('ma', {}).get('day60', 'N/A')}
        - Z-Score: {statistics.get('zscore', 'N/A')}

        MARKET CONTEXT:
        - Price change over analysis period: {market_data.get('price_change_period', 'N/A')}%
        - Volume trend: {market_data.get('volume_trend', 'N/A')}
        - Volatility: {market_data.get('volatility', 'N/A')}%
        - Position vs 52-week high: {market_data.get('current_vs_high', 'N/A')}%
        - Position vs 52-week low: {market_data.get('current_vs_low', 'N/A')}%

        TRADING CONTEXT:
        - This is for a long-term, dollar-cost-averaging strategy
        - Focus on ETFs and diversified holdings
        - Trades are executed as reserved orders (next trading day)
        - User can review and cancel based on reasoning

        INSTRUCTIONS:
        1. Analyze the technical indicators and market context
        2. Consider current economic conditions and market trends
        3. Provide a clear BUY/SELL/HOLD recommendation
        4. Give detailed economic reasoning (2-3 sentences)
        5. Assign confidence score (0.0 to 1.0)

        RESPONSE FORMAT (JSON):
        {{
            "decision": "BUY|SELL|HOLD",
            "reasoning": "기술적 분석, 시장 상황 및 경제적 요인을 기반으로 결정을 설명하는 자세한 경제적 추론",
            "confidence": 0.85,
            "key_factors": ["factor1", "factor2", "factor3"]
        }}

        Please provide your analysis:
        """
        return prompt

    def _parse_llm_response(self, response_text: str) -> Tuple[str, str, float]:
        """Parse LLM response and extract decision, reasoning, and confidence."""
        try:
            # Try to find JSON in the response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1

            if start == -1 or end == 0:
                # Fallback: simple text parsing
                return self._parse_text_response(response_text)

            json_str = response_text[start:end]
            data = json.loads(json_str)

            decision = data.get("decision", "HOLD").upper()
            reasoning = data.get("reasoning", "No reasoning provided")
            confidence = float(data.get("confidence", 0.5))

            # Validate decision
            if decision not in ["BUY", "SELL", "HOLD"]:
                decision = "HOLD"

            # Validate confidence
            confidence = max(0.0, min(1.0, confidence))

            return decision, reasoning, confidence

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}", extra={"endpoint_name": "parse_llm_response"})
            return self._parse_text_response(response_text)

    def _parse_text_response(self, response_text: str) -> Tuple[str, str, float]:
        """Fallback text parsing when JSON parsing fails."""
        response_lower = response_text.lower()

        # Simple keyword-based decision
        if any(word in response_lower for word in ["buy", "purchase", "acquire"]):
            decision = "BUY"
        elif any(word in response_lower for word in ["sell", "exit", "liquidate"]):
            decision = "SELL"
        else:
            decision = "HOLD"

        # Extract reasoning (first 200 chars as fallback)
        reasoning = response_text[:200] + "..." if len(response_text) > 200 else response_text

        # Default confidence
        confidence = 0.5

        return decision, reasoning, confidence

    def is_enabled(self) -> bool:
        """Check if LLM strategy is enabled and ready."""
        return self.enabled


# Helper function for integration with existing system
def get_llm_decision(stock_symbol: str, prophet_diff_rate: float, statistics: Dict, current_price: float) -> Dict:
    """
    Convenience function to get LLM trading decision.

    Returns:
        Dict with keys: decision, reasoning, confidence, enabled
    """
    strategy = LLMTradingStrategy()

    if not strategy.is_enabled():
        return {"decision": "HOLD", "reasoning": "LLM strategy not available", "confidence": 0.0, "enabled": False}

    decision, reasoning, confidence = strategy.analyze_stock_and_decide(
        stock_symbol=stock_symbol,
        prophet_diff_rate=prophet_diff_rate,
        statistics=statistics,
        current_price=current_price,
    )

    return {"decision": decision, "reasoning": reasoning, "confidence": confidence, "enabled": True}


if __name__ == "__main__":
    # Simple test
    strategy = LLMTradingStrategy()
    if strategy.is_enabled():
        print("LLM Strategy is ready!")
        res = get_llm_decision(
            stock_symbol="453810.KS",
            prophet_diff_rate=-0.03,
            statistics={
                "rsi": 47.05,
                "ma": {"day5": 13841.0, "day10": 13854.0, "day20": 13801.0, "day60": 13734.0},
                "zscore": 0.0,
            },
            current_price=13815,
        )

        print(res)
    else:
        print("LLM Strategy is not available")
