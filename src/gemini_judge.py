"""Gemini-backed model-risk review for research artifacts."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

import requests


DEFAULT_MODEL = "gemini-2.0-flash"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


JsonObject = dict[str, object]


def build_judge_prompt(
    report: Mapping[str, object],
    proposal: Mapping[str, object],
) -> str:
    formula_review = report.get("review_type") == (
        "phoenix_formula_and_risk_code_review"
    )
    system_review = report.get("review_type") == (
        "phoenix_whole_system_architecture_audit"
    )
    evidence = {
        "benchmark": report,
        "improvement_proposal": proposal,
        "instructions": {
            "role": "independent quantitative model-risk judge",
            "allowed_verdicts": ["approve", "revise", "reject"],
            "production_rule": (
                "No candidate may be promoted unless it beats the empirical "
                "baseline at every fixed-24-month maturity anchor."
            ),
            "required_output": [
                "verdict",
                "top_technical_reasons",
                "candidate_safety",
                "next_experiments",
                "data_or_label_risks",
            ],
        },
    }
    if formula_review:
        evidence["instructions"]["formula_review"] = (
            "For every material component, return KEEP, REMOVE, or REPLACE. "
            "Cite the supplied file/line range, explain any double counting or "
            "unsupported proxy, and give a fixed-24-month OOS metric gate."
        )
    if system_review:
        evidence["instructions"]["system_review"] = (
            "Audit all supplied modules and key files. Return strengths, an "
            "overall_score_0_to_100, architecture_risks, and findings whose "
            "action is KEEP, REMOVE, REPLACE, or ADD_TEST with priority P0/P1/P2."
        )
    return (
        "Evaluate Phoenix using only this JSON evidence. Do not invent results. "
        "Return valid JSON with keys verdict, summary, top_technical_reasons, "
        "candidate_safety, next_experiments, and data_or_label_risks. "
        + (
            "Because this is a formula/code review, also return findings with "
            "action KEEP, REMOVE, or REPLACE, component, reason, replacement, "
            "and metric_gate. "
            if formula_review
            else ""
        )
        + (
            "Because this is a whole-system audit, also return strengths, "
            "overall_score_0_to_100, architecture_risks, and prioritized "
            "findings with action KEEP, REMOVE, REPLACE, or ADD_TEST. "
            if system_review
            else ""
        )
        + " "
        "Each next_experiment must include hypothesis, change, metric_gate, "
        "and why_it_is_informative. Treat replay as replay, not realized trading. "
        "Keep production_weights_changed and verdict_mutated false.\n\n"
        + json.dumps(evidence, indent=2, sort_keys=True)
    )


def _extract_json(text: str) -> JsonObject:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    candidate = fenced.group(1) if fenced else cleaned
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini response must be a JSON object")
    return {str(key): value for key, value in parsed.items()}


def _required_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Gemini response is missing {name}")
    return value


def judge_report(
    report: Mapping[str, object],
    proposal: Mapping[str, object],
    api_key: str,
    *,
    model: str = DEFAULT_MODEL,
    timeout: float = 45.0,
) -> JsonObject:
    if not api_key.strip():
        raise ValueError("Gemini API key is empty")

    response = requests.post(
        API_URL.format(model=model),
        headers={"x-goog-api-key": api_key},
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": build_judge_prompt(report, proposal),
                        },
                    ],
                },
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = _required_mapping(response.json(), "candidates")
    candidates = payload["candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response contains no candidates")
    candidate = _required_mapping(candidates[0], "candidate content")
    content = _required_mapping(candidate["content"], "candidate content")
    parts = content["parts"]
    if not isinstance(parts, list) or not parts:
        raise ValueError("Gemini response contains no content parts")
    text = _required_mapping(parts[0], "candidate text")["text"]
    if not isinstance(text, str):
        raise ValueError("Gemini response text is not a string")
    result = _extract_json(text)
    result["provider"] = "google_gemini"
    result["model"] = model
    result["production_weights_changed"] = False
    result["verdict_mutated"] = False
    return result
