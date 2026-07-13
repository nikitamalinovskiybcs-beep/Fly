"""Tests for src.scheduler — Numerai auto-submission gating (mocked)."""

import json
from pathlib import Path


class TestNumeraiSubmission:
    """Numerai auto-submit must be graceful, idempotent, and secret-free."""

    def _scheduler(self, tmp_path: Path):
        import src.scheduler as sched_mod
        sched_mod.NUMERAI_STATE = tmp_path / "numerai_submissions.json"
        sched_mod.SCHEDULE_LOG = tmp_path / "scheduler_log.json"
        return sched_mod.FlyScheduler(tickers=["AAPL"])

    def test_no_credentials(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("NUMERAI_PUBLIC_ID", raising=False)
        monkeypatch.delenv("NUMERAI_SECRET_KEY", raising=False)
        scheduler = self._scheduler(tmp_path)
        result = scheduler._run_numerai_submission()
        assert result["status"] == "no_credentials"

    def test_already_submitted_is_idempotent(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("NUMERAI_PUBLIC_ID", "pub")
        monkeypatch.setenv("NUMERAI_SECRET_KEY", "sec")

        import src.integrations.numerai_pipeline as pipeline

        class _FakeNapi:
            def get_current_round(self) -> int:
                return 1309

        submit_called = {"n": 0}

        def _fake_run(**kwargs):
            submit_called["n"] += 1
            return {"validation_corr": 0.02, "submission": {"submission_id": "x"}}

        monkeypatch.setattr(pipeline, "_napi", lambda *a, **k: _FakeNapi())
        monkeypatch.setattr(pipeline, "run", _fake_run)

        scheduler = self._scheduler(tmp_path)
        scheduler._save_numerai_round(1309)

        result = scheduler._run_numerai_submission()
        assert result["status"] == "already_submitted"
        assert result["round"] == 1309
        assert submit_called["n"] == 0  # no duplicate upload

    def test_submits_new_round(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("NUMERAI_PUBLIC_ID", "pub")
        monkeypatch.setenv("NUMERAI_SECRET_KEY", "sec")

        import src.integrations.numerai_pipeline as pipeline

        class _FakeNapi:
            def get_current_round(self) -> int:
                return 1310

        def _fake_run(**kwargs):
            return {"validation_corr": 0.015,
                    "submission": {"submission_id": "abc123"}}

        monkeypatch.setattr(pipeline, "_napi", lambda *a, **k: _FakeNapi())
        monkeypatch.setattr(pipeline, "run", _fake_run)

        scheduler = self._scheduler(tmp_path)
        result = scheduler._run_numerai_submission()
        assert result["status"] == "submitted"
        assert result["round"] == 1310
        assert result["submission_id"] == "abc123"

        # State recorded → a second call within the same round no-ops.
        import src.scheduler as sched_mod
        saved = json.loads(sched_mod.NUMERAI_STATE.read_text())
        assert saved["last_round"] == 1310
        second = scheduler._run_numerai_submission()
        assert second["status"] == "already_submitted"
