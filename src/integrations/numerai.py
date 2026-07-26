"""Numerai integration — FREE tournament data + signals submission.

Numerai provides:
- 1000+ obfuscated features for 5000+ stocks (weekly)
- Historical data going back years
- Scoring against real hedge fund performance
- NMR crypto rewards for good predictions

Keys are optional — can download data without an account.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class NumeraiIntegration:
    """Main Numerai tournament integration."""

    def __init__(self, public_id: str = "", secret_key: str = "") -> None:
        self._napi = None
        self._enabled = False
        public_id = public_id or os.getenv("NUMERAI_PUBLIC_ID", "")
        secret_key = secret_key or os.getenv("NUMERAI_SECRET_KEY", "")

        if not public_id or not secret_key:
            logger.info("Numerai keys not provided, submission disabled")
            return

        try:
            import numerapi
            self._napi = numerapi.NumerAPI(
                public_id=public_id,
                secret_key=secret_key,
            )
            self._enabled = True
        except ImportError:
            logger.info("numerapi not installed, Numerai disabled")
        except Exception as exc:
            logger.warning("Numerai init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def download_latest_data(self, save_dir: str = "data/numerai/") -> Optional[str]:
        """Download latest tournament data (FREE, ~500MB).

        Args:
            save_dir: Directory to save downloaded files.

        Returns:
            Path to downloaded training file, or None.
        """
        if not self._enabled:
            return None

        Path(save_dir).mkdir(parents=True, exist_ok=True)
        try:
            train_path = f"{save_dir}train.parquet"
            live_path = f"{save_dir}live.parquet"
            features_path = f"{save_dir}features.json"

            self._napi.download_dataset("v5.0/train.parquet", train_path)
            self._napi.download_dataset("v5.0/live.parquet", live_path)
            self._napi.download_dataset("v5.0/features.json", features_path)

            logger.info("Downloaded Numerai data to %s", save_dir)
            return train_path
        except Exception as exc:
            logger.warning("Numerai download failed: %s", exc)
            return None

    def get_meta_model_predictions(self, save_dir: str = "data/numerai/") -> Optional[pd.DataFrame]:
        """Get meta-model predictions (crowd consensus).

        Args:
            save_dir: Directory for downloaded file.

        Returns:
            DataFrame with predictions, or None.
        """
        if not self._enabled:
            return None
        try:
            path = f"{save_dir}meta_model.parquet"
            self._napi.download_dataset("v5.0/meta_model.parquet", path)
            return pd.read_parquet(path)
        except Exception as exc:
            logger.warning("Meta model download failed: %s", exc)
            return None

    def train_numerai_model(
        self,
        features_path: str = "data/numerai/train.parquet",
        target_col: str = "target",
    ) -> dict:
        """Train a LightGBM model on Numerai data.

        Args:
            features_path: Path to training parquet.
            target_col: Target column name.

        Returns:
            Dict with metrics (corr_mean, corr_std, sharpe, feature_importance).
        """
        try:
            import lightgbm as lgb
            df = pd.read_parquet(features_path)
            feature_cols = [c for c in df.columns if c.startswith("feature_")]
            if not feature_cols:
                return {"error": "no feature columns found"}

            X = df[feature_cols].values
            y = df[target_col].values

            n_eras = df["era"].nunique() if "era" in df.columns else 1
            split_era = int(n_eras * 0.8)

            if "era" in df.columns:
                eras = df["era"].unique()
                train_eras = eras[:split_era]
                val_eras = eras[split_era:]
                train_mask = df["era"].isin(train_eras)
                val_mask = df["era"].isin(val_eras)
            else:
                split = int(len(df) * 0.8)
                train_mask = pd.Series([True] * split + [False] * (len(df) - split))
                val_mask = ~train_mask

            dtrain = lgb.Dataset(X[train_mask], y[train_mask])
            dval = lgb.Dataset(X[val_mask], y[val_mask])

            params = {
                "objective": "regression",
                "metric": "rmse",
                "n_estimators": 2000,
                "learning_rate": 0.01,
                "max_depth": 6,
                "colsample_bytree": 0.1,
                "verbosity": -1,
            }

            model = lgb.train(
                params, dtrain, valid_sets=[dval],
                callbacks=[lgb.early_stopping(50)],
            )

            preds = model.predict(X[val_mask])
            corr = float(np.corrcoef(preds, y[val_mask])[0, 1])

            importance = dict(zip(feature_cols, model.feature_importance().tolist()))
            top_features = dict(sorted(importance.items(), key=lambda x: -x[1])[:20])

            return {
                "corr_mean": round(corr, 4),
                "n_features": len(feature_cols),
                "n_eras_train": split_era,
                "feature_importance_top20": top_features,
            }
        except ImportError:
            return {"error": "lightgbm not installed"}
        except Exception as exc:
            return {"error": str(exc)}

    def submit_predictions(
        self,
        predictions: pd.DataFrame,
        model_id: str,
    ) -> dict:
        """Submit predictions to Numerai tournament.

        Args:
            predictions: DataFrame with 'id' and 'prediction' columns.
            model_id: Numerai model ID.

        Returns:
            Submission status dict.
        """
        if not self._enabled:
            return {"error": "not enabled"}
        try:
            submission_id = self._napi.upload_predictions(predictions, model_id=model_id)
            return {"submission_id": str(submission_id), "status": "submitted"}
        except Exception as exc:
            return {"error": str(exc)}

    def get_leaderboard_stats(self, model_id: str = "") -> dict:
        """Get model performance on leaderboard.

        Args:
            model_id: Numerai model ID.

        Returns:
            Leaderboard stats dict.
        """
        if not self._enabled:
            return {"error": "not enabled"}
        try:
            models = self._napi.get_models()
            return {"models": models}
        except Exception as exc:
            return {"error": str(exc)}

    def extract_alpha_signals(
        self,
        tickers: list[str],
        price_history: Optional[dict[str, pd.Series]] = None,
    ) -> dict[str, float]:
        """Cross-sectional, rank-normalized alpha in the Numerai style.

        The Numerai *tournament* model is trained on obfuscated stock IDs that
        cannot be mapped back to real tickers (AAPL, MSFT, …), so it cannot
        score an arbitrary basket directly. This method instead builds a
        genuine cross-sectional alpha from price history using the same
        principles Numerai rewards — rank-normalized, market-neutral factors
        (momentum, short-term reversal, low-volatility) blended and ranked to
        [-1, +1]. Missing tickers get 0.0.

        Args:
            tickers: Tickers to score.
            price_history: Optional dict ticker -> close-price Series (for
                offline/testing). Fetched from yfinance when omitted.

        Returns:
            Dict of ticker -> signal in [-1, +1].
        """
        if price_history is None:
            price_history = self._fetch_close_history(tickers)

        feats: dict[str, dict[str, float]] = {}
        for t in tickers:
            s = price_history.get(t)
            if s is None or len(s) < 63:
                continue
            s = s.dropna()
            if len(s) < 63:
                continue
            rets = s.pct_change().dropna()
            momentum = float(s.iloc[-1] / s.iloc[-63] - 1.0)
            reversal = -float(s.iloc[-1] / s.iloc[-5] - 1.0)
            vol = float(rets.tail(63).std() * np.sqrt(252))
            feats[t] = {"momentum": momentum, "reversal": reversal, "low_vol": -vol}

        if not feats:
            return {t: 0.0 for t in tickers}

        blend = {"momentum": 0.5, "reversal": 0.3, "low_vol": 0.2}
        composite: dict[str, float] = {}
        for name, weight in blend.items():
            vals = {t: feats[t][name] for t in feats}
            z = self._zscore(vals)
            for t, zv in z.items():
                composite[t] = composite.get(t, 0.0) + weight * zv

        ranked = self._rank_to_unit(composite)
        return {t: round(ranked.get(t, 0.0), 4) for t in tickers}

    @staticmethod
    def _zscore(values: dict[str, float]) -> dict[str, float]:
        """Cross-sectional z-score (market-neutralization)."""
        arr = np.array(list(values.values()), dtype=float)
        mean = float(arr.mean())
        std = float(arr.std())
        if std == 0:
            return {k: 0.0 for k in values}
        return {k: (v - mean) / std for k, v in values.items()}

    @staticmethod
    def _rank_to_unit(values: dict[str, float]) -> dict[str, float]:
        """Rank values cross-sectionally and map to [-1, +1]."""
        n = len(values)
        if n == 0:
            return {}
        if n == 1:
            return {k: 0.0 for k in values}
        order = sorted(values, key=lambda k: values[k])
        out: dict[str, float] = {}
        for i, k in enumerate(order):
            out[k] = 2.0 * (i / (n - 1)) - 1.0
        return out

    def _fetch_close_history(
        self, tickers: list[str], period: str = "6mo",
    ) -> dict[str, pd.Series]:
        """Batched close-price download for alpha computation."""
        try:
            import yfinance as yf
            raw = yf.download(
                tickers, period=period, interval="1d", progress=False,
                group_by="ticker", auto_adjust=True, threads=True,
            )
            out: dict[str, pd.Series] = {}
            if raw is None or raw.empty:
                return {}
            for t in tickers:
                try:
                    df = raw[t] if len(tickers) > 1 else raw
                    if df is not None and "Close" in df:
                        series = df["Close"].dropna()
                        if not series.empty:
                            out[t] = series
                except (KeyError, TypeError):
                    continue
            return out
        except Exception as exc:
            logger.warning("Alpha history fetch failed: %s", exc)
            return {}


class NumeraiSignalsIntegration:
    """Numerai Signals — submit predictions on REAL tickers.

    Unlike main tournament, Signals uses actual Yahoo Finance tickers.
    """

    def __init__(self, public_id: str = "", secret_key: str = "") -> None:
        self._napi = None
        self._enabled = False

        try:
            import numerapi
            self._napi = numerapi.SignalsAPI(
                public_id=public_id or None,
                secret_key=secret_key or None,
            )
            self._enabled = True
        except ImportError:
            logger.info("numerapi not installed, Numerai Signals disabled")
        except Exception as exc:
            logger.warning("Numerai Signals init failed: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_ticker_universe(self) -> list[str]:
        """Get list of valid tickers for Signals submission."""
        if not self._enabled:
            return []
        try:
            return self._napi.ticker_universe()
        except Exception:
            return []

    def format_predictions(self, signals: dict[str, float]) -> pd.DataFrame:
        """Convert paper trading signals to Numerai Signals format.

        Args:
            signals: Dict of ticker → signal (-1 to +1).

        Returns:
            DataFrame with ticker and signal columns (0 to 1).
        """
        rows = []
        for ticker, signal in signals.items():
            numerai_signal = (signal + 1) / 2
            rows.append({"ticker": ticker, "signal": numerai_signal})
        return pd.DataFrame(rows)

    def submit_signals(self, predictions: pd.DataFrame, model_id: str) -> dict:
        """Submit to Numerai Signals tournament.

        Args:
            predictions: DataFrame with ticker and signal columns.
            model_id: Model ID.

        Returns:
            Submission status.
        """
        if not self._enabled:
            return {"error": "not enabled"}
        try:
            sub_id = self._napi.upload_predictions(predictions, model_id=model_id)
            return {"submission_id": str(sub_id), "status": "submitted"}
        except Exception as exc:
            return {"error": str(exc)}

    def get_diagnostics(self, model_id: str) -> dict:
        """Get diagnostics for submitted model.

        Args:
            model_id: Model ID.

        Returns:
            Diagnostics dict.
        """
        if not self._enabled:
            return {"error": "not enabled"}
        try:
            return self._napi.diagnostics(model_id)
        except Exception as exc:
            return {"error": str(exc)}
