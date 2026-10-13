# LLM Trading Strategy Configuration Guide

## OpenRouter API Setup

1. **Get API Key**:
   - Sign in at https://openrouter.ai/keys and create an API key.

2. **Add to Environment**:
   - Add these values to `.fastapi.env` (loaded by the FastAPI container):
   ```dotenv
   OPENROUTER_API_KEY=your_api_key_here
   OPENROUTER_MODEL=openrouter/free
   ```
   - Only `OPENROUTER_API_KEY` is required. Missing or blank `OPENROUTER_MODEL` defaults to `openrouter/free`.
   - `openrouter/free` automatically selects an available free model supporting JSON responses.
   - To select a specific model, use an available model ID ending in `:free` from https://openrouter.ai/models.
   - Paid model IDs are rejected and disable the LLM strategy. No paid fallback is configured.
   - The previous `GEMINI_API_KEY` is no longer used. Airflow calls FastAPI and does not need the OpenRouter key.

3. **Apply Configuration**:
   - Build or deploy the updated FastAPI image, then recreate the FastAPI container to load the environment:
   ```sh
   docker compose up -d --force-recreate fastapi-server
   ```
   - `GET /v1/llm/health` checks local configuration only; it does not validate the API key or model availability.

4. **Free Model Limits and Failures**:
   - Free model availability and account rate limits can change. Check the [free router documentation](https://openrouter.ai/docs/guides/routing/routers/free-router) and [current limits](https://openrouter.ai/docs/api/reference/limits).
   - Requests have a 60-second timeout. Authentication errors, rate limits, unavailable models, and empty responses return HOLD with confidence 0.0 through the existing failure path.
   - Run the mocked provider tests without an API key or live trading:
   ```sh
   python -m unittest discover -s tests -v
   ```

## How It Works

The LLM strategy enhances the existing Prophet and statistical analysis by:

1. **Analyzing Market Context**: Current price trends, volume, volatility
2. **Economic Reasoning**: Provides detailed justification for trades
3. **Smart Integration**: High-confidence LLM decisions get priority when they align with other indicators
4. **Conservative Approach**: Mixed signals result in HOLD to avoid risky trades

## Decision Priority

1. **High Confidence LLM (>0.7)** + Traditional signals agree → Follow LLM
2. **Mixed Signals** → Conservative HOLD
3. **No LLM or Low Confidence** → Traditional Prophet + Statistical analysis

## Notification Enhancement

Trading notifications now include:
- Original technical analysis (RSI, MA, Z-score)
- Prophet model predictions
- LLM decision with confidence score
- Economic reasoning from AI analysis

This allows users to:
- Review AI reasoning before trades execute
- Learn about market conditions and economic factors
- Cancel trades if the reasoning seems flawed
- Build economic knowledge through AI explanations

## Example Output

```
005930: PURCHASE - statistics {'rsi': 30.0, 'ma': {'day5': 70000}} is oversold.
it's time to buy | diff_rate 4.0 is over purchase_threshold 3.0 |
LLM: BUY (confidence: 0.85) - Current oversold conditions combined with
positive earnings outlook and sector rotation into tech stocks suggest
strong buying opportunity. Technical indicators align with macroeconomic trends.
```
