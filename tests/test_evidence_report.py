from src.evidence_report import build_fixed_24m_evidence_report


def test_evidence_report_keeps_bcs_quote_advisory() -> None:
    result = build_fixed_24m_evidence_report(
        anchors={
            "6": {"model_brier": 0.10, "baseline_brier": 0.12},
            "12": {"model_brier": 0.11, "baseline_brier": 0.12},
        },
        bcs_quote={
            "coupon_pa": 20.0,
            "model_coupon_pa": 19.0,
        },
    )

    assert result["promotion_gate"] is True
    assert result["bcs_quote_fit"]["dealer"] == "BCS Capital"
    assert result["bcs_quote_fit"]["evidence_only"] is True
    assert result["production_weights_changed"] is False
