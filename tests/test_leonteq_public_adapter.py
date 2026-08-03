from __future__ import annotations

from src.leonteq_public_adapter import parse_leonteq_public_page


def test_parse_leonteq_public_page() -> None:
    html = """
    <html><head><title>Express Certificate | CH1571714935</title></head>
    <body>
    CH1571714935 Phoenix Autocallable
    * Issuer Leonteq Securities AG, Guernsey Branch
    * Product type Multi Express Certificate with Barrier
    * Underlyings
    <a href="/underlyings/AMD.OQ?id=1">AMD</a>
    <a href="/underlyings/INTC.OQ?id=2">Intel</a>
    * Barrier 50,00%
    * Memory effect Yes
    Initial fixing 17 Jun2026
    Issue date 23 Jun2026
    Expiry 16 Jun2030
    Bid EUR921,09 Ask EUR930,35
    </body></html>
    """

    record = parse_leonteq_public_page(
        html,
        "https://certificati.leonteq.com/isin/CH1571714935",
        retrieved_at="2026-08-03T00:00:00+00:00",
    )

    assert record.isin == "CH1571714935"
    assert record.product_type == "Phoenix Autocallable"
    assert record.underlyings == ("AMD", "Intel")
    assert record.barrier_pct == 50.0
    assert record.memory_effect is True
    assert record.bid == 921.09
    assert record.ask == 930.35
    assert record.evidence_class == "public_product_page"
    assert record.outcome_status == "missing_verified_outcome"
