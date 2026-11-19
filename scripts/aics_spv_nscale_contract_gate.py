#!/usr/bin/env python3
"""Fail-closed Nscale SPV agreement evidence gate (original SEC source review).

Consumes the already byte-rehashed SEC exhibit lineage in the frozen 2026-11-19
research review. This local reconciliation does not re-download original bytes,
independently attest 2026 live-time PIT, prove principal drawn, or certify AICS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

REGISTRY = Path("aics_data/source_registry/observed_review_2026-11-19.json")
OBSERVED = Path("aics_data/research/observed_source_review_2026-11-19.json")
OUTPUT = Path("aics_data/source_evidence/spv_nscale_contract_gate_2026-11-19.json")

SOURCE = {
    "cik": "2110365",
    "accession": "0001193125-26-395475",
    "form": "S-1",
    "filed_at": "2026-09-18",
    "available_at": "2026-10-02",
    "document_type": "EX-10.24",
    "source_page": ("https://www.sec.gov/Archives/edgar/data/2110365/"
                    "000119312526395475/ck0002110365-ex10_24.htm"),
    "original_url": ("https://www.sec.gov/Archives/edgar/data/2110365/"
                     "000119312526395475/0001193125-26-395475.txt"),
    "original_sha256": "b56c25775e3f7e3637f91380d25a02927c713d30675ba31c43fc67efafbb70e9",
    "document_text_sha256": "b7d2dd391a2c843f58ea84d17b664f934af3350e1e5361e1672aa3b9891657df",
    "original_bytes": 64469423,
}
BORROWER = "Nscale NC Borrower SPV, LLC"
GUARANTOR = "Nscale Services US Inc."
FIXED = 370_000_000
FLOATING = 830_000_000
EXPECTED_CEILING = 1_200_000_000


class ContractEvidenceError(ValueError):
    """The frozen original-source contract evidence is incomplete or changed."""


def _blocked(obj: dict) -> bool:
    return (
        obj.get("index_aics") is None
        and obj.get("promotion") == "BLOCKED"
        and obj.get("trades_created") is False
    )


def audit(registry: dict, observed: dict, registry_bytes: bytes) -> dict:
    if registry.get("evidence_cutoff") != "2026-11-18" or registry.get("review_date") != "2026-11-19":
        raise ContractEvidenceError("Source-review chronology changed")
    sources = registry.get("sources")
    if not isinstance(sources, dict) or "nscale" not in sources:
        raise ContractEvidenceError("Nscale SEC original missing")
    item = sources["nscale"]
    original = item.get("original")
    if not isinstance(original, dict):
        raise ContractEvidenceError("Nscale SEC original provenance missing")
    for key in ("cik", "accession", "form", "filed_at", "available_at",
                "document_type", "source_page"):
        if item.get(key) != SOURCE[key]:
            raise ContractEvidenceError("Nscale filing or exhibit identity mismatch")
    if (original.get("url") != SOURCE["original_url"]
            or original.get("sha256") != SOURCE["original_sha256"]
            or original.get("bytes") != SOURCE["original_bytes"]
            or item.get("document_text_sha256") != SOURCE["document_text_sha256"]):
        raise ContractEvidenceError("SEC original byte-level receipt differs from pinned evidence")
    filed = dt.date.fromisoformat(item["filed_at"])
    available = dt.date.fromisoformat(item["available_at"])
    cutoff = dt.date.fromisoformat(registry["evidence_cutoff"])
    if available != filed + dt.timedelta(days=14) or available > cutoff:
        raise ContractEvidenceError("SEC +14 calendar-day rule or time cutoff violated")
    if (observed.get("review_date") != registry["review_date"]
            or observed.get("source_cutoff") != registry["evidence_cutoff"]
            or observed.get("registry_sha256") != hashlib.sha256(registry_bytes).hexdigest()
            or observed.get("independently_attested_historical_pit") is not False
            or observed.get("certified_node_scores") != 0
            or observed.get("production_weights_changed") is not False
            or observed.get("verdict_mutated") is not False
            or not _blocked(observed)):
        raise ContractEvidenceError("Research review source linkage or no-promotion gate changed")
    observations = observed.get("observations")
    if not isinstance(observations, dict) or not isinstance(observations.get("nscale_nc_gpu_credit"), dict):
        raise ContractEvidenceError("No Nscale agreement-derived observations")
    nscale = observations["nscale_nc_gpu_credit"]
    if (nscale.get("sources") != ["nscale"]
            or nscale.get("borrower") != BORROWER
            or nscale.get("affiliate_guarantor") != GUARANTOR
            or type(nscale.get("fixed_commitment_usd")) is not int
            or type(nscale.get("floating_commitment_usd")) is not int
            or type(nscale.get("contractual_ceiling_usd")) is not int
            or nscale["fixed_commitment_usd"] != FIXED
            or nscale["floating_commitment_usd"] != FLOATING
            or nscale["contractual_ceiling_usd"] != EXPECTED_CEILING
            or nscale["fixed_commitment_usd"] + nscale["floating_commitment_usd"]
               != nscale["contractual_ceiling_usd"]
            or nscale.get("drawn_principal_from_this_agreement_usd") is not None
            or nscale.get("effective_economic_recourse_amount_usd") is not None):
        raise ContractEvidenceError("Contract amount, parties or unproven drawn exposure altered")
    return {
        "schema_version": "aics-spv-nscale-contract-original-lineage-gate-v1",
        "source_review_date": observed["review_date"],
        "source_cutoff": observed["source_cutoff"],
        "source_registry_sha256": observed["registry_sha256"],
        "source_exhibit_text_sha256": item["document_text_sha256"],
        "sec_accession": item["accession"],
        "source_document_type": item["document_type"],
        "sec_filed_at": item["filed_at"],
        "sec_available_at": item["available_at"],
        "source_issuer_cik": item["cik"],
        "named_borrower": BORROWER,
        "named_affiliate_guarantor": GUARANTOR,
        "fixed_commitment_usd": FIXED,
        "floating_commitment_usd": FLOATING,
        "contractual_ceiling_usd": EXPECTED_CEILING,
        "drawn_principal_usd": None,
        "effective_recourse_usd": None,
        "other_spv_contracts_authenticated": 0,
        "verified_direct_source_review_contracts": 1,
        "original_bytes_rehashed_in_this_gate": False,
        "independently_attested_historical_pit": False,
        "heldout_24m_oos": False,
        "spv_node_score": None,
        "index_aics": None,
        "promotion": "BLOCKED",
        "trades_created": False,
        "limitations": [
            "The frozen observed-review pipeline verified original SEC S-1 EX-10.24 source bytes; this gate checks its committed lineage, not raw bytes again.",
            "A contractual facility ceiling is neither drawn principal nor an economically additive guarantee or loss.",
            "One named borrower/guarantor agreement does not validate all 13 SPV research companies, the three project graphs, or representative historical PIT.",
            "No synthetic balances, score, investment action, or 24-month OOS is inferred.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--observed", type=Path, default=OBSERVED)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        raw = args.registry.read_bytes()
        result = audit(json.loads(raw), json.loads(args.observed.read_bytes()), raw)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "contract_originals_with_lineage": result["verified_direct_source_review_contracts"],
        "contractual_ceiling_usd": result["contractual_ceiling_usd"],
        "drawn_principal_usd": None, "spv_node_score": None, "index_aics": None,
        "promotion": "BLOCKED",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
