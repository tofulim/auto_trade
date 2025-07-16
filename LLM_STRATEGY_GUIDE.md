# LLM Trading Strategy Configuration Guide

## Google Gemini API Setup

To enable the LLM trading strategy, you need to obtain a free Google Gemini API key:

1. **Get API Key**:
   - Go to https://ai.google.dev/
   - Click "Get API key" and sign in with your Google account
   - Create a new project if needed
   - Generate an API key

2. **Add to Environment**:
   - Copy your API key to `.fastapi.env`:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

3. **Free Tier Limits**:
   - Gemini 1.5 Flash: 15 requests per minute, 1 million tokens per day
   - Gemini 1.5 Pro: 2 requests per minute, 50 requests per day
   
   The system is designed to work within these limits for daily trading decisions.

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