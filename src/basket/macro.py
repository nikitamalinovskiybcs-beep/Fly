"""Macro overlay — VIX, DXY, oil, yields for basket risk assessment."""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class MacroOverlay:
    """Fetch macro indicators and compute risk score."""

    MACRO_TICKERS = {
        "VIX": "^VIX",
        "DXY": "DX-Y.NYB",
        "OIL": "CL=F",
        "TNX": "^TNX",
    }

    def get_current(self) -> dict[str, float]:
        """Fetch current macro indicators.

        Returns:
            Dict with VIX, DXY, OIL, TNX values.
        """
        result: dict[str, float] = {}
        try:
            import yfinance as yf
            for name, ticker in self.MACRO_TICKERS.items():
                hist = yf.Ticker(ticker).history(period="5d")
                if not hist.empty:
                    result[name] = float(hist["Close"].iloc[-1])
        except Exception as exc:
            logger.warning("Macro fetch failed: %s", exc)
        return result

    def macro_risk_score(self) -> float:
        """Compute macro risk score 0-100 (higher = riskier).

        Returns:
            Risk score. 50 if data unavailable.
        """
        data = self.get_current()
        if not data:
            return 50.0

        score = 50.0

        vix = data.get("VIX", 20)
        if vix > 30:
            score += 20
        elif vix > 25:
            score += 10
        elif vix < 15:
            score -= 10

        tnx = data.get("TNX", 4.0)
        if tnx > 5.0:
            score += 10
        elif tnx > 4.5:
            score += 5

        oil = data.get("OIL", 75)
        if oil > 100:
            score += 10
        elif oil < 50:
            score += 5

        return float(np.clip(score, 0, 100))

    def impact_on_basket(self, sectors: list[str]) -> dict[str, str]:
        """Assess macro impact per sector.

        Args:
            sectors: List of sector names.

        Returns:
            Dict of sector → impact description.
        """
        data = self.get_current()
        impacts: dict[str, str] = {}

        vix = data.get("VIX", 20)
        oil = data.get("OIL", 75)

        for sector in set(sectors):
            if sector == "Energy":
                impacts[sector] = "positive" if oil > 80 else "neutral"
            elif sector == "Technology":
                impacts[sector] = "negative" if vix > 25 else "neutral"
            elif sector == "Utilities":
                impacts[sector] = "defensive"
            elif sector == "Financial Services":
                tnx = data.get("TNX", 4.0)
                impacts[sector] = "positive" if tnx > 4.0 else "neutral"
            else:
                impacts[sector] = "neutral"

        return impacts
