from __future__ import annotations

import json
from pathlib import Path

import requests

from scripts import run_gemini_judge


def test_main_defers_transient_gemini_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report = tmp_path / "report.json"
    proposal = tmp_path / "proposal.json"
    output = tmp_path / "review.json"
    report.write_text("{}")
    proposal.write_text("{}")

    response = requests.Response()
    response.status_code = 429
    error = requests.HTTPError(response=response)
    monkeypatch.setattr(
        run_gemini_judge,
        "judge_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "configured")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_gemini_judge",
            str(report),
            str(proposal),
            "--output",
            str(output),
        ],
    )

    run_gemini_judge.main()
    payload = json.loads(output.read_text())
    assert payload["status"] == "deferred"
    assert payload["production_weights_changed"] is False
