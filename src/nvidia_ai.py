"""
NVIDIA AI — Free NIM API for risk intelligence (Karpathy method).

Uses NVIDIA NIM (free tier) for:
1. Risk scoring enhancement — LLM-based basket analysis
2. Anomaly detection — unusual risk patterns
3. Sentiment analysis — market news sentiment per ticker

Free tier: 1000 API calls/month via build.nvidia.com
Graceful fallback: if NVIDIA unavailable, return neutral scores.
"""

import os
import json
from typing import Dict, List, Any, Optional

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


# ── Config ──
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _nvidia_chat(
    prompt: str,
    model: str = "meta/llama-3.1-8b-instruct",
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> Optional[str]:
    """Call NVIDIA NIM chat completion API."""
    if not REQUESTS_OK or not NVIDIA_API_KEY:
        return None
    try:
        resp = requests.post(
            f"{NVIDIA_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None


def get_status() -> Dict[str, Any]:
    """Check NVIDIA AI integration status."""
    available = bool(NVIDIA_API_KEY)
    return {
        "available": available,
        "key_set": available,
        "label": "NVIDIA NIM (Llama 3.1)" if available else "NVIDIA AI не подключен",
        "description": "Risk intelligence + anomaly detection (бесплатно)",
    }


# ═══════════════════════════════════════════════════════════════
# 1. Risk Analysis — LLM-based basket scoring
# ═══════════════════════════════════════════════════════════════

def analyze_basket_risk(
    tickers: List[str],
    scores: Dict[str, float],
    p_ki: float,
    avg_vol: float,
    avg_corr: float,
) -> Dict[str, Any]:
    """
    LLM-enhanced risk analysis for basket.
    Returns structured risk assessment + score adjustment.
    """
    prompt = f"""You are a structured products risk analyst. Analyze this worst-of Phoenix autocallable basket:

Tickers: {', '.join(tickers)}
Current P(knock-in): {p_ki:.1f}%
Avg implied vol: {avg_vol:.1f}%
Avg correlation: {avg_corr:.2f}
Per-ticker scores: {json.dumps(scores)}

Respond in JSON only (no markdown):
{{
  "risk_level": "low|medium|high|extreme",
  "score_adjustment": <float between -10 and +10>,
  "key_risks": ["risk1", "risk2"],
  "concentration_warning": true|false,
  "recommendation": "brief one-line recommendation"
}}"""

    result = _nvidia_chat(prompt)
    if result is None:
        return _fallback_risk(tickers, p_ki, avg_vol, avg_corr)

    try:
        # Parse JSON from LLM response
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = json.loads(clean)
        # Clamp score_adjustment to safe range
        adj = float(parsed.get("score_adjustment", 0))
        parsed["score_adjustment"] = max(-10, min(10, adj))
        parsed["source"] = "nvidia_nim"
        return parsed
    except (json.JSONDecodeError, KeyError, ValueError):
        return _fallback_risk(tickers, p_ki, avg_vol, avg_corr)


def _fallback_risk(
    tickers: List[str],
    p_ki: float,
    avg_vol: float,
    avg_corr: float,
) -> Dict[str, Any]:
    """Deterministic fallback when NVIDIA unavailable."""
    # Simple rule-based risk
    risk_score = 0
    risks = []

    if p_ki > 30:
        risk_score += 3
        risks.append(f"High P(KI) = {p_ki:.0f}%")
    if avg_vol > 40:
        risk_score += 2
        risks.append(f"High vol = {avg_vol:.0f}%")
    if avg_corr > 0.7:
        risk_score += 2
        risks.append("High correlation — low diversification")
    if len(tickers) < 3:
        risk_score += 1
        risks.append("Small basket — concentration risk")

    # Check sector concentration
    from src.precompute import SECTOR_MAP
    sectors = [SECTOR_MAP.get(t, "Unknown") for t in tickers]
    unique_sectors = set(sectors)
    concentration = len(unique_sectors) == 1 and len(tickers) > 1

    if concentration:
        risk_score += 2
        risks.append(f"Single sector: {sectors[0]}")

    if risk_score >= 5:
        level = "extreme"
    elif risk_score >= 3:
        level = "high"
    elif risk_score >= 1:
        level = "medium"
    else:
        level = "low"

    adj_map = {"low": 2, "medium": 0, "high": -2, "extreme": -4}
    return {
        "risk_level": level,
        "score_adjustment": adj_map[level],
        "key_risks": risks[:3],
        "concentration_warning": concentration,
        "recommendation": "Модель недоступна — детерминистическая оценка",
        "source": "fallback_rules",
    }


# ═══════════════════════════════════════════════════════════════
# 2. Anomaly Detection — unusual patterns
# ═══════════════════════════════════════════════════════════════

def detect_anomalies(
    tickers: List[str],
    vol_history: Dict[str, float],
    corr_history: Dict[str, float],
) -> Dict[str, Any]:
    """
    Detect anomalous risk patterns using NVIDIA NIM.
    """
    prompt = f"""You are a risk monitoring system. Check for anomalies in this portfolio:

Tickers: {', '.join(tickers)}
Recent volatilities: {json.dumps(vol_history)}
Recent correlations: {json.dumps(corr_history)}

Respond in JSON only:
{{
  "anomalies_found": <int>,
  "alerts": [
    {{"ticker": "X", "type": "vol_spike|corr_break|regime_change", "severity": "low|medium|high", "detail": "..."}}
  ]
}}"""

    result = _nvidia_chat(prompt)
    if result is None:
        return {"anomalies_found": 0, "alerts": [], "source": "unavailable"}

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = json.loads(clean)
        parsed["source"] = "nvidia_nim"
        return parsed
    except (json.JSONDecodeError, KeyError):
        return {"anomalies_found": 0, "alerts": [], "source": "parse_error"}


# ═══════════════════════════════════════════════════════════════
# 3. Sentiment — market news per ticker
# ═══════════════════════════════════════════════════════════════

def get_sentiment(tickers: List[str]) -> Dict[str, Any]:
    """
    Get market sentiment per ticker using NVIDIA NIM.
    """
    prompt = f"""You are a financial sentiment analyzer. For each ticker, provide current market sentiment.

Tickers: {', '.join(tickers)}

Respond in JSON only:
{{
  "sentiments": {{
    "TICKER": {{"sentiment": "bullish|neutral|bearish", "score": <float -1 to 1>, "reason": "brief"}}
  }},
  "overall": "bullish|neutral|bearish"
}}"""

    result = _nvidia_chat(prompt, max_tokens=300)
    if result is None:
        sentiments = {t: {"sentiment": "neutral", "score": 0, "reason": "N/A"} for t in tickers}
        return {"sentiments": sentiments, "overall": "neutral", "source": "unavailable"}

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = json.loads(clean)
        parsed["source"] = "nvidia_nim"
        return parsed
    except (json.JSONDecodeError, KeyError):
        sentiments = {t: {"sentiment": "neutral", "score": 0, "reason": "N/A"} for t in tickers}
        return {"sentiments": sentiments, "overall": "neutral", "source": "parse_error"}
