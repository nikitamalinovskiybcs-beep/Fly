"""Build a bounded, secret-free AI audit packet for the whole Phoenix system."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEY_FILES = [
    "README.md",
    "requirements.txt",
    "app.py",
    "src/structured_product.py",
    "src/real_data.py",
    "src/phoenix_engine.py",
    "src/quant_benchmarks.py",
    "src/risk_metrics.py",
    "src/decision_gate.py",
    "src/full_pipeline.py",
    "src/self_learning_agents.py",
    "src/continuous_improvement.py",
    "src/ai_judge_panel.py",
    ".github/workflows/ci.yml",
    ".github/workflows/auto-improve.yml",
    ".github/workflows/friday-multi-horizon-benchmark.yml",
]


def _module_inventory() -> list[dict[str, object]]:
    modules: list[dict[str, object]] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            modules.append({"file": str(path.relative_to(ROOT)), "syntax_error": str(error)})
            continue
        functions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        classes = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        modules.append(
            {
                "file": str(path.relative_to(ROOT)),
                "function_count": len(functions),
                "class_count": len(classes),
                "functions": functions[:15],
                "classes": classes[:10],
            },
        )
    return modules


def _file_summary(relative_path: str) -> dict[str, object]:
    path = ROOT / relative_path
    if not path.exists():
        return {"file": relative_path, "status": "missing"}
    text = path.read_text(encoding="utf-8")
    limit = 1800 if relative_path.endswith(".py") else 1200
    return {
        "file": relative_path,
        "status": "present",
        "line_count": len(text.splitlines()),
        "content": text[:limit],
        "truncated": len(text) > limit,
    }


def build_packet() -> dict[str, object]:
    return {
        "review_type": "phoenix_whole_system_architecture_audit",
        "objective": (
            "Review the complete Phoenix repository and recommend what to keep, "
            "remove, simplify, replace, or test next."
        ),
        "system_contract": {
            "product_term_months": 24,
            "historical_anchors_months_ago": [6, 12, 18, 24],
            "replay_is_not_realized": True,
            "synthetic_data_is_not_independent_evidence": True,
            "dealer_quotes_must_not_be_fabricated": True,
            "ai_may_not_change_production": True,
            "ai_may_not_create_trades": True,
        },
        "review_dimensions": [
            "mathematical correctness and payoff semantics",
            "probability calibration and baseline comparison",
            "data provenance, leakage and OOS design",
            "agent usefulness versus double counting and arbitrary weights",
            "risk metrics, stress testing and tail dependence",
            "production architecture, reliability and observability",
            "security, secrets and external-provider failure handling",
            "test quality, CI coverage and maintainability",
            "user-facing decision clarity and auditability",
        ],
        "required_output": {
            "verdict": "approve|revise|reject",
            "overall_score_0_to_100": 0,
            "summary": "",
            "strengths": [],
            "findings": [
                {
                    "action": "KEEP|REMOVE|REPLACE|ADD_TEST",
                    "component": "",
                    "reason": "",
                    "replacement": "",
                    "metric_gate": "",
                    "priority": "P0|P1|P2",
                },
            ],
            "architecture_risks": [],
            "next_experiments": [],
            "production_safety": "",
            "production_weights_changed": False,
            "verdict_mutated": False,
        },
        "module_inventory": _module_inventory(),
        "key_files": [_file_summary(path) for path in KEY_FILES],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(
        json.dumps(build_packet(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
