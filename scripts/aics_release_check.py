"""Accept the dated eleven-node research release in one run. Run from the repository root."""
import argparse
import json
from decimal import Decimal
from pathlib import Path

from scripts.aics_nasdaq_session_review import RECEIPT as NASDAQ_RECEIPT
from scripts.aics_nasdaq_session_review import SESSION, analyze
from scripts.aics_progress_dashboard import (
    DEFAULT_MANIFEST,
    build,
    digest_file,
    strict_repo_path,
)
from scripts.aics_release_operands import ratios, score_from_ratio
from scripts.aics_research_20261119 import calculate, composite
from scripts.aics_score_reproducibility_gate import WEIGHTS

RELEASE = Path("aics_data/progress/research_release_2026-11-19.json")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_release(release, verify_nasdaq=False):
    root = Path(".")
    inputs = release["inputs_by_node"]
    fingerprints = release["input_sha256"]
    publication = release["first_publication"]
    session = SESSION.isoformat()
    if publication["session"] != session or inputs.keys() != WEIGHTS.keys():
        raise ValueError("Incomplete release or wrong session")
    if publication["scores"].keys() != WEIGHTS.keys() or any(not files for files in inputs.values()):
        raise ValueError("Missing published scores or source references")
    if set(fingerprints) != {name for files in inputs.values() for name in files}:
        raise ValueError("Source references and pinned fingerprints differ")
    matching = {name: digest_file(strict_repo_path(root, name)) == digest for name, digest in fingerprints.items()}
    audit = build(root, load(Path(DEFAULT_MANIFEST)))
    audit_nodes = {r["node"]: r for r in audit["node_progress"]}

    primary = load(NASDAQ_RECEIPT)
    observed = primary["result"]
    if verify_nasdaq and analyze(primary["sources"]) != observed:
        raise ValueError("The live Nasdaq replay differs from the dated receipt")
    original = calculate()
    current_session, = [s for s in observed["equity_basket_sessions"] if s["session"] == session]
    basket = {r["symbol"] for r in primary["sources"]}
    decliners = current_session["decliners"]
    if (primary["index_session"] != session or original["session"] != session
            or len(primary["sources"]) != len(basket) or current_session["constituents"] != len(basket)
            or len(set(decliners)) != len(decliners) or not set(decliners) <= basket or len(basket) != 7):
        raise ValueError("Invalid dated equity basket")
    scores = dict(original["scores"])
    scores["AI Equities"] = 100 * len(decliners) / len(basket)
    current = composite(scores)
    operands = ratios(len(decliners), len(basket))
    recorded = {r["node"]: r for r in observed["contributions_at_observed_multiplier"]}
    if recorded.keys() != WEIGHTS.keys() or len(recorded) != len(observed["contributions_at_observed_multiplier"]):
        raise ValueError("Incomplete or duplicated contributions")

    multiplier = Decimal(str(current["multiplier"]))
    base = {node: Decimal(str(score)) * WEIGHTS[node] / 100 for node, score in scores.items()}
    raw = sum(base.values())
    points = {node: amount * multiplier for node, amount in base.items()}
    total = round(sum(points.values()), 2)
    aggregate_ok = (
        raw == Decimal(str(publication["raw"])) == Decimal(observed["raw_point_total"])
        and multiplier == Decimal(str(publication["multiplier"])) == Decimal(observed["multiplier"])
        and current["hot_nodes"] == publication["hot_nodes"] == observed["hot_nodes"]
        and total == Decimal(str(publication["research_aics"])) == Decimal(str(observed["research_aics"]))
        and total == Decimal(str(current["research_aics"]))
    )
    rows = []
    for node, weight in WEIGHTS.items():
        prior = audit_nodes[node]
        reference = recorded[node]
        numerator, denominator = operands[node]
        failed_inputs = [name for name in inputs[node] if not matching[name]]
        checks = {
            "source_registered": prior["gates"]["primary_source_registry"] and prior["weight"] == weight,
            "source_archived": prior["gates"]["raw_candidate_archive"],
            "dated_inputs_pinned": not failed_inputs,
            "indicator_recalculated": score_from_ratio(numerator, denominator) == Decimal(str(scores[node])),
            "node_score_reproduced": scores[node] == original["scores"][node] == publication["scores"][node] == reference["score"],
            "contribution_reconciled": (
                reference["weight"] == weight and points[node] == Decimal(reference["points"]) and aggregate_ok
            ),
        }
        completed = next((i for i, passed in enumerate(checks.values()) if not passed), len(checks))
        rows.append({"node": node, "numerator": str(numerator), "denominator": str(denominator),
                     "score": scores[node], "points": str(points[node]), "completed": completed,
                     "failed_checks": [k for k, passed in checks.items() if not passed],
                     "changed_inputs": failed_inputs, "certified": prior["independently_certified"]})
    total_steps = 6 * len(rows)
    return {
        "session": session,
        "technical_steps_completed": sum(r["completed"] for r in rows),
        "total_steps": total_steps,
        "original_rubric_completed": sum(min(5, r["completed"]) + int(r["completed"] >= 5 and r["certified"])
                                         for r in rows),
        "untouched_24m_oos_nodes": audit["untouched_24m_oos_nodes"],
        "independently_certified_nodes": audit["independently_certified_nodes"],
        "research_aics": current["research_aics"], "certified_aics": current["certified_aics"],
        "input_files_checked": len(matching), "nodes": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-nasdaq", action="store_true", help="Also fetch and rehash all seven quote files.")
    parser.add_argument("--details", action="store_true", help="Show each node and any failed checks.")
    args = parser.parse_args()
    report = check_release(load(RELEASE), args.verify_nasdaq)
    passed = report["technical_steps_completed"] == report["total_steps"]
    if passed and not args.details:
        report.pop("nodes")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
