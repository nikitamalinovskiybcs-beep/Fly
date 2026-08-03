from src.drift_monitor import build_evidence_drift_report


def test_drift_monitor_flags_p_loss_and_bcs_coupon_shift() -> None:
    result = build_evidence_drift_report(
        reference_p_loss=[0.20, 0.22],
        current_p_loss=[0.40, 0.42],
        reference_bcs_coupon=[18.0, 19.0],
        current_bcs_coupon=[22.0, 23.0],
    )

    assert result["status"] == "drift_detected"
    assert result["alerts"] == ["p_loss_drift", "bcs_coupon_drift"]
    assert result["action"] == "committee_review"
