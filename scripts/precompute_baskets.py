"""Precompute ready Phoenix snapshots for a cloud batch job."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.full_pipeline import run_full_analysis
from src.snapshot_cache import save_snapshot


DEFAULT_BASKETS = (
    ("AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"),
    ("AAPL", "MSFT", "NVDA"),
)


def parse_baskets(raw: str) -> list[list[str]]:
    """Parse semicolon-separated baskets with stable ticker ordering."""
    baskets: list[list[str]] = []
    for raw_basket in raw.split(";"):
        tickers = list(dict.fromkeys(
            ticker.strip().upper()
            for ticker in raw_basket.split(",")
            if ticker.strip()
        ))
        if tickers:
            baskets.append(tickers)
    return baskets


def _snapshot_name(tickers: list[str]) -> str:
    key = ",".join(tickers).encode()
    digest = hashlib.sha256(key).hexdigest()[:12]
    return f"phoenix-{digest}.pkl"


def precompute_baskets(
    baskets: list[list[str]],
    output_dir: Path,
) -> dict[str, object]:
    """Run each basket independently and persist a batch manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for tickers in baskets:
        try:
            payload = run_full_analysis(tickers)
            snapshot_path = output_dir / _snapshot_name(tickers)
            save_snapshot(tickers, payload, path=snapshot_path)
            records.append(
                {
                    "tickers": tickers,
                    "status": "completed",
                    "snapshot": snapshot_path.name,
                    "generated_at": payload.get("generated_at"),
                },
            )
        except Exception as exc:
            records.append(
                {
                    "tickers": tickers,
                    "status": "failed",
                    "error": str(exc),
                },
            )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baskets",
        default=";".join(",".join(basket) for basket in DEFAULT_BASKETS),
        help="Semicolon-separated baskets; tickers comma-separated",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/runtime/cloud_snapshots"),
    )
    args = parser.parse_args()
    manifest = precompute_baskets(parse_baskets(args.baskets), args.output_dir)
    print(json.dumps(manifest, indent=2))
    return 0 if all(
        record["status"] == "completed"
        for record in manifest["records"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
