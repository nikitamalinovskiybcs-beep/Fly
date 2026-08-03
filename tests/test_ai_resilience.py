from src.ai_resilience import committee_quorum, run_provider_panel


def test_timeout_is_preserved_and_excluded_from_quorum() -> None:
    def runner(provider: str, prompt: str, timeout: float) -> dict[str, object]:
        raise TimeoutError("local model timed out")

    attempts = run_provider_panel(
        [{"provider": "ollama", "model": "qwen2.5:1.5b"}],
        prompt="review",
        runner=runner,
        short_prompt="short review",
    )
    assert attempts[0]["status"] == "timeout"
    assert attempts[0]["counts_as_approval"] is False
    assert committee_quorum(attempts)["quorum"] is False


def test_short_retry_preserves_lineage_and_valid_vote() -> None:
    calls = 0

    def runner(provider: str, prompt: str, timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("long prompt")
        return {"verdict": "approve", "summary": "bounded"}

    attempts = run_provider_panel(
        [{"provider": "mistral", "model": "mistral-small-latest"}],
        prompt="long review",
        runner=runner,
        short_prompt="short review",
    )
    assert attempts[0]["status"] == "completed"
    assert attempts[0]["retry"] == "short_prompt"
    assert attempts[0]["initial_status"] == "timeout"


def test_malformed_reviews_and_missing_votes_never_approve() -> None:
    def runner(provider: str, prompt: str, timeout: float) -> dict[str, object]:
        if provider == "bad":
            return {"summary": "no verdict"}
        return {"verdict": "approve"}

    attempts = run_provider_panel(
        [
            {"provider": "bad", "model": "local"},
            {"provider": "good", "model": "cloud"},
        ],
        prompt="review",
        runner=runner,
    )
    quorum = committee_quorum(attempts, minimum_approvals=2)
    assert attempts[0]["status"] == "error"
    assert attempts[0]["counts_as_approval"] is False
    assert quorum["approval_votes"] == 1
    assert quorum["quorum"] is False
