import json

from scripts.backfill_calculated_notes import backfill


def test_backfill_is_idempotent(tmp_path, monkeypatch) -> None:
    report = tmp_path / "benchmark.json"
    report.write_text(json.dumps({
        "generated_at": "2099-01-01T00:00:00",
        "product_term_months": 24,
        "anchors": {
            "6": {"rows": [{"basket": ["AAPL", "MSFT"], "predicted_p_loss": 0.2}],
        }},
    }))
    from src.storage.database import Database
    from src.storage import Storage

    Database._instance = None
    monkeypatch.setattr("src.storage.database.DB_PATH", tmp_path / "fly.db")
    monkeypatch.setattr("src.storage.DB_PATH", tmp_path / "fly.db", raising=False)
    first = backfill(report)
    second = backfill(report)

    assert first["rows_attempted"] == 1
    assert second["notes_last_6_months"] == 1
    Storage().db.close()
