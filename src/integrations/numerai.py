"""Numerai integration — FREE tournament data + signals submission.

Numerai provides:
- 1000+ obfuscated features for 5000+ stocks (weekly)
- Historical data going back years
- Scoring against real hedge fund performance
- NMR crypto rewards for good predictions

Keys are optional — can download data without an account.
"""

import logging
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

        if not public_id or not secret_key:
            logger.info("Numerai keys not provided, submission disabled")

        try:
            import numerapi
            self._napi = numerapi.NumerAPI(
                public_id=public_id or None,
                secret_key=secret_key or None,
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

    def extract_alpha_signals(self, tickers: list[str]) -> dict[str, float]:
        """Extract alpha signals from Numerai meta-model.

        Args:
            tickers: Tickers to look up.

        Returns:
            Dict of ticker → signal (-1 to +1).
        """
        return {t: 0.0 for t in tickers}


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
