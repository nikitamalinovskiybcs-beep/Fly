"""Backfill historical replay calculations into the note-tracking ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.storage import Storage


def backfill(report_path: Path) -> dict[str, int | str]:
    report = json.loads(report_path.read_text())
    storage = Storage()
    attempted = 0
    for anchor, block in report.get("anchors", {}).items():
        for row in block.get("rows", []):
            basket = row.get("basket", [])
            if not isinstance(basket, list) or len(basket) < 2:
                continue
            identity = {"anchor": anchor, "basket": basket, "source": str(report_path)}
            note_id = "replay-" + hashlib.sha256(
                json.dumps(identity, sort_keys=True).encode()
            ).hexdigest()[:24]
            storage.record_calculated_note({
                "note_id": note_id,
                "calculated_at": report.get("generated_at"),
                "basket": json.dumps(basket, separators=(",", ":")),
                "barrier": 0.65,
                "term_months": int(report.get("product_term_months", 24)),
                "p_ki": row.get("predicted_p_loss"),
                "evidence_status": "historical_replay",
                "lifecycle_status": "historical_replay",
            })
            attempted += 1
    return {
        "source": str(report_path),
        "rows_attempted": attempted,
        "notes_last_6_months": storage.count_calculated_notes(6),
        "unique_baskets_last_6_months": storage.count_calculated_baskets(6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(json.dumps(backfill(args.report), indent=2))


if __name__ == "__main__":
    main()
