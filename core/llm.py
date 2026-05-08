import json
from openai import OpenAI
from utils.config import get_secret
from utils.logger import logger

client = OpenAI(api_key=get_secret("OPENAI_API_KEY"))


def classify_trade_signal(
    ticker: str,
    signal_type: str,
    direction: str,
    insider_title: str = "",
    company: str = "",
    extra_context: str = ""
) -> dict:
    prompt = f"""
You are evaluating a stock trade signal for an algorithmic trading system.

Signal details:
- Ticker: {ticker}
- Company: {company}
- Signal type: {signal_type} (insider_filing / unusual_options / politician_trade)
- Direction: {direction} (BULLISH / BEARISH)
- Insider title: {insider_title}
- Additional context: {extra_context}

Score this signal on three dimensions from 0.0 to 1.0:
- clarity: how clear and unambiguous is the signal? (1.0 = very clear)
- predictability: how likely is this signal to predict a price move? (1.0 = highly predictable)
- timeliness: how time-sensitive is this signal? (1.0 = act immediately)

Also provide:
- catalyst: one sentence describing the likely reason behind this trade
- risk_level: LOW / MEDIUM / HIGH

Return ONLY a JSON object like this with no explanation:
{{"clarity": 0.8, "predictability": 0.7, "timeliness": 0.9, "catalyst": "CEO buying ahead of earnings", "risk_level": "LOW"}}
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        composite = round(
            (result.get("clarity", 0) +
             result.get("predictability", 0) +
             result.get("timeliness", 0)) / 3,
            4
        )
        result["composite"] = composite
        logger.info(f"LLM classified {ticker} — composite: {composite} | catalyst: {result.get('catalyst', '')}")
        return result
    except Exception as e:
        logger.error(f"LLM classification failed for {ticker}: {e}")
        return {
            "clarity": 0.5,
            "predictability": 0.5,
            "timeliness": 0.5,
            "composite": 0.5,
            "catalyst": "Unknown",
            "risk_level": "MEDIUM"
        }
