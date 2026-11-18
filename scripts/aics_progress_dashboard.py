#!/usr/bin/env python3
"""AICS 11-node project milestone progress (NOT a model certification gate).

Measures six transparent work milestones for every node, without inventing
market data, verified PIT, model scores or predictive claims. Completion of
a project milestone never authorizes index calculation or trading.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

WEIGHTS = {
    "Private Credit": 150,
    "Insurers": 125,
    "UST 30Y": 125,
    "Neoclouds": 100,
    "AI Equities": 100,
    "Hyperscalers": 100,
    "SPV": 100,
    "Repo": 100,
    "Power/Data Centers": 50,
    "Semiconductors Supply": 50,
    "AI Demand": 50,
}
GATES = (
    "primary_source_registry",
    "raw_candidate_archive",
    "independently_attested_pit",
    "audited_node_scoring",
    "untouched_24m_oos",
    "independent_certification",
)
AUDIT_FIELDS = (
    "independently_pit_attested_nodes",
    "independently_audited_score_nodes",
    "untouched_oos_24mo_passed_nodes",
    "independently_certified_nodes",
)
PROVEN_SERIES = {
    "Private Credit": {"BAMLH0A0HYM2", "BAMLH0A3HYC"},
    "UST 30Y": {"DGS30"},
    "Repo": {"SOFR"},
}
DEFAULT_MANIFEST = "aics_data/progress/evidence_milestones_2026-11-18.json"
DEFAULT_STATUS = "aics_data/progress/status.json"
DEFAULT_MD = "docs/aics_progress.md"
assert len(WEIGHTS) == 11 and sum(WEIGHTS.values()) == 1050


def fail(message):
    raise ValueError(message)


def strict_repo_path(root: Path, filename: str) -> Path:
    if not isinstance(filename, str) or not filename or filename.startswith("/"):
        fail("invalid repository file path")
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        fail("missing or unsafe repository evidence path: " + filename)
    return path


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_audit_evidence(root, audit, field, prior_nodes):
    """Workboard attestation evidence must be explicitly archived and hashed.

    The workboard is NOT authorized to certify AICS; that requires a separate
    independent review process and the score reproducibility gate.
    """
    entries = audit.get(field, [])
    if not isinstance(entries, list):
        fail("invalid audit milestone array: " + field)
    done = set()
    for item in entries:
        if not isinstance(item, dict):
            fail("audit milestone must contain an evidence document")
        name = item.get("node")
        if name not in WEIGHTS or name in done or name not in prior_nodes:
            fail("unknown/duplicate/out-of-order audit milestone: " + str(name))
        path = strict_repo_path(root, item.get("evidence_path"))
        digest = item.get("evidence_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            fail("audit evidence missing SHA-256")
        if digest_file(path) != digest:
            fail("audit evidence mismatch")
        # A checksum alone does not make a review independent; this is only a
        # transparent workboard marker. Do not emit an AICS or node score.
        done.add(name)
    return done


def build(root: Path, manifest: dict) -> dict:
    if manifest.get("schema_version") != "aics-progress-milestones-v1":
        fail("unknown progress ledger version")
    dt.date.fromisoformat(manifest["report_as_of"])
    registry = strict_repo_path(root, manifest["registry_path"]).read_text(encoding="utf-8")
    registry_nodes = {
        node for node, weight in WEIGHTS.items()
        if re.search(r"^\\|\\s*" + re.escape(node) + r"\\s*\\|\\s*"
                     + str(weight) + r"\\s*\\|", registry, flags=re.M)
    }
    archive = manifest["research_archive"]
    refdoc_path = strict_repo_path(root, archive["supporting_document"])
    refdoc = refdoc_path.read_text(encoding="utf-8")
    digest = archive["archive_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        fail("archive SHA-256 missing or malformed")
    if digest not in refdoc:
        fail("archive SHA-256 is not documented in research report")
    url = archive["workflow_url"]
    if not isinstance(url, str) or not re.fullmatch(
        r"https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+", url
    ):
        fail("archive run URL missing or malformed")
    series_by_node = archive["series_by_node"]
    if not isinstance(series_by_node, dict) or set(series_by_node) - set(PROVEN_SERIES):
        fail("unknown archived candidate node")
    archived_nodes = set()
    seen = set()
    for node, series in series_by_node.items():
        if node not in registry_nodes or not isinstance(series, list) or not series:
            fail("raw archive node has no documented registry or series")
        if len(set(series)) != len(series) or set(series) != PROVEN_SERIES[node]:
            fail("raw archive does not match source inventory")
        if seen.intersection(series):
            fail("same raw source counted under two nodes")
        seen.update(series)
        if not all(s in refdoc and s in registry for s in series):
            fail("archived source is not documented in both registry and report")
        archived_nodes.add(node)

    audit = manifest["independent_audit"]
    if not isinstance(audit, dict) or set(audit) != set(AUDIT_FIELDS):
        fail("audit fields changed or missing")
    stage3 = checked_audit_evidence(root, audit, AUDIT_FIELDS[0], archived_nodes)
    stage4 = checked_audit_evidence(root, audit, AUDIT_FIELDS[1], stage3)
    stage5 = checked_audit_evidence(root, audit, AUDIT_FIELDS[2], stage4)
    stage6 = checked_audit_evidence(root, audit, AUDIT_FIELDS[3], stage5)
    completed_by_gate = [
        registry_nodes, archived_nodes, stage3, stage4, stage5, stage6
    ]
    node_rows = []
    for name, weight in WEIGHTS.items():
        flags = {gate: name in nodes for gate, nodes in zip(GATES, completed_by_gate)}
        count = sum(flags.values())
        node_rows.append({
            "node": name, "weight": weight, "gates": flags,
            "completed_milestones": count, "milestone_count": len(GATES),
            "project_progress_pct": round(100 * count / len(GATES), 1),
            "independently_certified": name in stage6,
            "node_stress_score": None,
        })
    completed = sum(len(s) for s in completed_by_gate)
    total = len(GATES) * len(WEIGHTS)
    return {
        "as_of": manifest["report_as_of"], "schema_version": "aics-progress-status-v1",
        "scope": "PROJECT_MILESTONES_NOT_MODEL_QUALITY",
        "total_nodes": len(WEIGHTS), "total_weight": sum(WEIGHTS.values()),
        "milestones_per_node": len(GATES), "milestones_completed": completed,
        "milestones_total": total, "project_progress_pct": round(100 * completed / total, 1),
        "registry_nodes": len(registry_nodes), "archived_candidate_nodes": len(archived_nodes),
        "source_pit_attested_nodes": len(stage3),
        "audited_scoring_nodes": len(stage4),
        "untouched_24m_oos_nodes": len(stage5),
        "independently_certified_nodes": len(stage6),
        "certification_pct": round(100 * len(stage6) / len(WEIGHTS), 1),
        "node_progress": node_rows, "archive": {
            "source": "ALFRED historical as-of source snapshots",
            "workflow_url": url, "reported_sha256": digest,
            "independently_verified": False,
        },
        "index_aics": None, "predictive_skill_score": None,
        "promotion": "BLOCKED", "trades_created": False,
        "important": "Project completion percentage is NOT certified model readiness. "
                     "The separate reproducibility/PIT/OOS process is authoritative.",
    }


def progress_bar(value: float, segments: int = 20) -> str:
    marked = int(segments * value / 100)
    return "█" * marked + "░" * (segments - marked)


def as_markdown(status: dict) -> str:
    lines = [
        "# AICS — динамический статус работы по 11 узлам",
        "",
        "**Это прогресс по проверяемым этапам разработки, не точность прогноза.**",
        "",
        "Дата данных: " + status["as_of"] + ". Обновляется при изменении подтверждённых этапов.",
        "",
        "## Общий технический прогресс",
        "",
        "**" + progress_bar(status["project_progress_pct"]) + " "
        + str(status["project_progress_pct"]) + "%**",
        "",
        str(status["milestones_completed"]) + " / " + str(status["milestones_total"])
        + " этапов (11 узлов × 6 этапов).",
        "",
        "## Сертификация",
        "",
        "**" + progress_bar(status["certification_pct"]) + " "
        + str(status["certification_pct"]) + "%**",
        "",
        str(status["independently_certified_nodes"]) + " / 11 узлов. "
        "Сертифицированный AICS = **N/A**. Прогнозный skill = **N/A**.",
        "",
        "## Узлы",
        "",
        "| Узел | Вес | Прогресс | Этапы | Сертифицирован |",
        "|---|---:|---:|---:|---|",
    ]
    for row in status["node_progress"]:
        lines.append("| " + row["node"] + " | " + str(row["weight"])
                     + " | " + str(row["project_progress_pct"]) + "%"
                     + " | " + str(row["completed_milestones"]) + "/6"
                     + " | " + ("да" if row["independently_certified"] else "нет") + " |")
    lines.extend([
        "",
        "## Проверяемые этапы",
        "",
        "1. Реестр первичных источников.",
        "2. Архив кандидатов данных (не означает независимый PIT).",
        "3. Независимо проверенная историческая доступность (PIT).",
        "4. Аудированная методология 0–100 для узла.",
        "5. Независимый 24-месячный OOS.",
        "6. Независимая сертификация узла.",
        "",
        "Исходный архив: [GitHub Actions](" + status["archive"]["workflow_url"] + ").",
        "Архивные источники могут быть кандидатами сразу для трёх узлов, "
        "но ни один скор ими не сертифицирован.",
        "",
        "**Нельзя считать процент основанием для инвестиций или рассчитывать AICS.**",
        "",
    ])
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--status", default=DEFAULT_STATUS)
    p.add_argument("--markdown", default=DEFAULT_MD)
    args = p.parse_args()
    root = args.repo_root.resolve()
    manifest = json.loads(strict_repo_path(root, args.manifest).read_text(encoding="utf-8"))
    result = build(root, manifest)
    status_path = root / args.status
    markdown_path = root / args.markdown
    status_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    markdown_path.write_text(as_markdown(result), encoding="utf-8")
    print(json.dumps({"completed": result["milestones_completed"], "total": result["milestones_total"],
                      "progress_percent": result["project_progress_pct"],
                      "certified_nodes": result["independently_certified_nodes"],
                      "index_aics": None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
