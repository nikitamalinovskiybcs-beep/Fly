"""End-to-end Numerai self-learning pipeline.

Downloads tournament data, trains a LightGBM model on a chosen feature set,
generates live predictions and (optionally) submits them to a model slot.

Memory-conscious: reads only the needed feature columns and can subsample
eras for fast iteration in constrained environments.

Run:
    python -m src.integrations.numerai_pipeline --submit
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DATA_VERSION = "v5.0"
DEFAULT_DIR = "data/numerai"
TARGET_COL = "target"


def _napi(public_id: str = "", secret_key: str = ""):
    from numerapi import NumerAPI

    return NumerAPI(
        public_id=public_id or os.getenv("NUMERAI_PUBLIC_ID") or None,
        secret_key=secret_key or os.getenv("NUMERAI_SECRET_KEY") or None,
    )


def download_data(
    save_dir: str = DEFAULT_DIR,
    feature_set: str = "small",
) -> dict:
    """Download features.json, train, validation and live parquet files.

    Returns a dict of local paths and the selected feature list.
    """
    napi = _napi()
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    paths = {
        "features": f"{save_dir}/features.json",
        "train": f"{save_dir}/train.parquet",
        "validation": f"{save_dir}/validation.parquet",
        "live": f"{save_dir}/live.parquet",
    }
    napi.download_dataset(f"{DATA_VERSION}/features.json", paths["features"])
    napi.download_dataset(f"{DATA_VERSION}/train.parquet", paths["train"])
    napi.download_dataset(f"{DATA_VERSION}/validation.parquet", paths["validation"])
    napi.download_dataset(f"{DATA_VERSION}/live.parquet", paths["live"])

    with open(paths["features"]) as fh:
        meta = json.load(fh)
    features = meta["feature_sets"][feature_set]
    paths["feature_list"] = features
    logger.info("Downloaded Numerai %s data; %d features (%s set)",
                DATA_VERSION, len(features), feature_set)
    return paths


def _read_columns(path: str, features: list[str], extra: list[str]) -> pd.DataFrame:
    cols = [c for c in extra if c] + features
    return pd.read_parquet(path, columns=cols)


def neutralize(
    predictions: np.ndarray,
    feature_df: pd.DataFrame,
    proportion: float = 0.5,
) -> np.ndarray:
    """Feature-neutralize predictions via a single least-squares fit.

    Cheap post-process (no retraining): subtracts a ``proportion`` of the
    linear projection of predictions onto the feature space, reducing
    feature exposure. This is the standard Numerai trick that trades a bit
    of raw correlation for far more stable per-era performance.
    """
    preds = np.asarray(predictions, dtype=float)
    fmat = feature_df.to_numpy(dtype=float)
    fmat = fmat - fmat.mean(axis=0)
    centered = preds - preds.mean()
    beta, *_ = np.linalg.lstsq(fmat, centered, rcond=None)
    exposure = fmat @ beta
    return preds - proportion * exposure


def era_correlations(
    predictions: np.ndarray,
    targets: np.ndarray,
    eras: pd.Series,
) -> list[float]:
    """Return finite per-era correlations for robust validation scoring."""
    frame = pd.DataFrame({
        "prediction": np.asarray(predictions, dtype=float),
        "target": np.asarray(targets, dtype=float),
        "era": eras.to_numpy(),
    })
    correlations: list[float] = []
    for _, group in frame.groupby("era", sort=True):
        if len(group) < 2 or group["prediction"].nunique() < 2:
            continue
        corr = float(np.corrcoef(group["prediction"], group["target"])[0, 1])
        if np.isfinite(corr):
            correlations.append(corr)
    return correlations


def _mean_era_corr(predictions: np.ndarray, frame: pd.DataFrame) -> float:
    if "era" not in frame.columns:
        return float(np.corrcoef(predictions, frame[TARGET_COL])[0, 1])
    values = era_correlations(predictions, frame[TARGET_COL].to_numpy(), frame["era"])
    return float(np.mean(values)) if values else 0.0


def _choose_neutralize_proportion(
    predictions: np.ndarray,
    frame: pd.DataFrame,
    candidates: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0),
) -> tuple[float, dict[float, float]]:
    """Select the cheapest post-process using validation-era mean correlation."""
    scores = {
        proportion: _mean_era_corr(
            neutralize(predictions, frame.iloc[:, : len(frame.columns) - 2], proportion),
            frame,
        )
        for proportion in candidates
    }
    best = max(scores, key=scores.get)
    return best, scores


def train_and_predict(
    paths: dict,
    era_stride: int = 4,
    num_boost_round: int = 2000,
    neutralize_proportion: float = 0.5,
) -> dict:
    """Train LightGBM on (optionally subsampled) train data and predict live.

    Args:
        paths: output of download_data.
        era_stride: keep every Nth era to bound memory/time (1 = all eras).
        num_boost_round: max boosting rounds (early-stopped on validation).

    Returns:
        Dict with validation corr, feature count, and the live predictions
        DataFrame keyed under ``predictions``.
    """
    import lightgbm as lgb

    features = paths["feature_list"]

    train = _read_columns(paths["train"], features, ["era", TARGET_COL])
    train = train.dropna(subset=[TARGET_COL])
    if era_stride > 1 and "era" in train.columns:
        keep = sorted(train["era"].unique())[::era_stride]
        train = train[train["era"].isin(keep)]

    valid = _read_columns(paths["validation"], features, ["era", TARGET_COL])
    valid = valid.dropna(subset=[TARGET_COL])
    if era_stride > 1 and "era" in valid.columns:
        keep = sorted(valid["era"].unique())[::era_stride]
        valid = valid[valid["era"].isin(keep)]

    dtrain = lgb.Dataset(train[features], label=train[TARGET_COL])
    dvalid = lgb.Dataset(valid[features], label=valid[TARGET_COL])

    params = {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.01,
        "max_depth": 5,
        "num_leaves": 31,
        "colsample_bytree": 0.1,
        "verbosity": -1,
    }
    model = lgb.train(
        params,
        dtrain,
        num_boost_round=num_boost_round,
        valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
    )

    val_pred = model.predict(valid[features])
    corr_raw = float(np.corrcoef(val_pred, valid[TARGET_COL])[0, 1])
    raw_era_corr = era_correlations(
        val_pred, valid[TARGET_COL].to_numpy(), valid["era"]
    ) if "era" in valid.columns else []
    proportion = neutralize_proportion
    selection_scores: dict[float, float] = {}
    if "era" in valid.columns:
        proportion, selection_scores = _choose_neutralize_proportion(
            val_pred,
            valid[features + ["era", TARGET_COL]],
            (0.0, 0.25, neutralize_proportion, 0.75, 1.0),
        )
    val_neutral = neutralize(val_pred, valid[features], proportion)
    corr_neutral = float(np.corrcoef(val_neutral, valid[TARGET_COL])[0, 1])
    neutral_era_corr = era_correlations(
        val_neutral, valid[TARGET_COL].to_numpy(), valid["era"]
    ) if "era" in valid.columns else []

    live = _read_columns(paths["live"], features, [])
    live_pred = model.predict(live[features])
    live_neutral = neutralize(live_pred, live[features], proportion)
    predictions = pd.DataFrame(
        {"id": live.index, "prediction": _rank(live_neutral)}
    )

    return {
        "validation_corr": round(corr_neutral, 5),
        "validation_corr_raw": round(corr_raw, 5),
        "validation_era_corr_raw": round(float(np.mean(raw_era_corr)), 5) if raw_era_corr else None,
        "validation_era_corr_neutral": round(float(np.mean(neutral_era_corr)), 5) if neutral_era_corr else None,
        "neutral_era_wins": int(sum(
            neutral > raw for neutral, raw in zip(neutral_era_corr, raw_era_corr)
        )),
        "n_validation_eras": len(raw_era_corr),
        "neutralize_proportion": proportion,
        "neutralize_selection_scores": selection_scores,
        "n_features": len(features),
        "n_train_rows": int(len(train)),
        "n_live_rows": int(len(predictions)),
        "best_iteration": int(model.best_iteration or num_boost_round),
        "predictions": predictions,
    }


def _rank(values: np.ndarray) -> np.ndarray:
    """Rank-normalise predictions to (0, 1) as Numerai expects."""
    order = pd.Series(values).rank(method="first")
    return (order / (len(order) + 1)).to_numpy()


def submit(predictions: pd.DataFrame, model_id: Optional[str] = None) -> dict:
    """Upload predictions to the given (or first) model slot."""
    napi = _napi()
    if model_id is None:
        models = napi.get_models()
        if not models:
            return {"error": "no model slots found"}
        model_id = next(iter(models.values()))
    out = f"{DEFAULT_DIR}/live_predictions.csv"
    predictions.to_csv(out, index=False)
    sub_id = napi.upload_predictions(out, model_id=model_id)
    return {"submission_id": str(sub_id), "model_id": model_id}


def run(
    feature_set: str = "small",
    era_stride: int = 4,
    do_submit: bool = False,
) -> dict:
    """Full pipeline: download → train → predict → (optional) submit."""
    paths = download_data(feature_set=feature_set)
    result = train_and_predict(paths, era_stride=era_stride)
    preds = result.pop("predictions")
    if do_submit:
        result["submission"] = submit(preds)
    else:
        out = f"{DEFAULT_DIR}/live_predictions.csv"
        preds.to_csv(out, index=False)
        result["predictions_path"] = out
    return result


def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(description="Numerai self-learning pipeline")
    ap.add_argument("--feature-set", default="small",
                    choices=["small", "medium", "all"])
    ap.add_argument("--era-stride", type=int, default=4)
    ap.add_argument("--submit", action="store_true")
    args = ap.parse_args()

    from dotenv import load_dotenv

    load_dotenv(override=True)
    result = run(
        feature_set=args.feature_set,
        era_stride=args.era_stride,
        do_submit=args.submit,
    )
    print(json.dumps({k: v for k, v in result.items()}, indent=2, default=str))


if __name__ == "__main__":
    _main()
