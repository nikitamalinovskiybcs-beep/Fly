from src.research_orchestrator import run_research_pipeline


def _ready_stage(name: str):
    def stage(context):
        assert context["research_only"] is True
        return {"status": "passed", "stage": name}

    return stage


def test_research_pipeline_preserves_stage_order_and_safety() -> None:
    result = run_research_pipeline(
        records={},
        calculation=_ready_stage("calculation"),
        committee=_ready_stage("committee"),
        fact_check=_ready_stage("fact_check"),
        oos=_ready_stage("oos"),
        safety=_ready_stage("safety"),
    )

    assert result["status"] == "blocked"
    assert result["stage_order"] == [
        "storage",
        "data_readiness",
        "calculation",
        "committee",
        "fact_check",
        "oos",
        "safety",
    ]
    assert "data_readiness" in result["blocking_stages"]
    assert result["production_weights_changed"] is False
    assert result["verdict_mutated"] is False
    assert result["trades_created"] is False


def test_research_pipeline_blocks_failed_fact_check() -> None:
    def fact_check(context):
        return {"status": "blocked", "reason": "unsupported_claim"}

    complete_records = {
        "settled_24m_notes": [{
            "note_id": "n1",
            "basket": ["AAPL", "MSFT"],
            "as_of": "2024-01-01",
            "maturity_date": "2026-01-01",
            "outcome_type": "no_loss",
            "source": "realized",
            "observations": [{"date": "2025-01-01", "levels": {"AAPL": 1.0}}],
            "term_months": 24,
        }],
        "observation_paths": [{
            "ticker": "AAPL",
            "observation_timestamp": "2025-01-01",
            "level": 1.0,
            "source": "public",
        }],
        "bcs_capital_quotes": [{
            "quote_id": "q1",
            "dealer": "BCS Capital",
            "quote_timestamp": "2025-01-01",
            "basket": ["AAPL", "MSFT"],
            "barrier": 0.6,
            "coupon_pa": 0.2,
            "term_months": 24,
        }],
        "iv_surfaces": [{
            "ticker": "AAPL",
            "as_of": "2025-01-01",
            "strike": 1.0,
            "tenor": 24,
            "iv": 0.3,
        }],
        "alternative_features": [{
            "feature_id": "footfall",
            "ticker": "AAPL",
            "feature_timestamp": "2025-01-01",
            "source": "public",
            "license_status": "licensed_or_public",
        }],
    }
    result = run_research_pipeline(
        complete_records,
        storage={"sqlite": True},
        calculation=_ready_stage("calculation"),
        committee=_ready_stage("committee"),
        fact_check=fact_check,
        oos=_ready_stage("oos"),
        safety=_ready_stage("safety"),
    )

    assert result["status"] == "blocked"
    assert result["blocking_stages"] == ["fact_check"]
