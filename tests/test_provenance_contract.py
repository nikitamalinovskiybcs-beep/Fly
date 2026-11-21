from src.provenance_contract import validate_field_provenance


def test_complete_field_provenance_is_verified() -> None:
    result = validate_field_provenance(
        {
            "crwd_quote": {
                "source": "dealer",
                "source_id": "quote-123",
                "observed_at": "2026-05-24T10:00:00Z",
                "dataset_version": "quotes-v1",
                "evidence_class": "dealer_verified",
                "freshness_seconds": 30,
            }
        }
    )
    assert result["status"] == "verified"
    assert result["all_verified"] is True


def test_missing_and_estimated_fields_are_blocked() -> None:
    result = validate_field_provenance(
        {
            "crwd_quote": {
                "source": "model",
                "source_id": "",
                "observed_at": "2026-05-24T10:00:00Z",
                "dataset_version": "synthetic-v1",
                "evidence_class": "estimated",
            }
        }
    )
    assert result["status"] == "blocked"
    assert "source_id" in result["missing"]["crwd_quote"]
    assert "evidence_class" in result["invalid"]["crwd_quote"]


def test_empty_provenance_never_approves() -> None:
    result = validate_field_provenance({})
    assert result["all_verified"] is False
    assert result["production_weights_changed"] is False
