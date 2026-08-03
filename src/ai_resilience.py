"""Fail-closed provider routing for research-only AI committee reviews."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping


VALID_VERDICTS = {"approve", "approved", "revise", "reject", "research"}
APPROVAL_VERDICTS = {"approve", "approved"}


def _status_for_error(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    return "error"


def run_provider_panel(
    providers: Iterable[Mapping[str, str]],
    *,
    prompt: str,
    runner: Callable[[str, str, float], Mapping[str, object]],
    timeout_seconds: float = 30.0,
    short_prompt: str = "",
) -> list[dict[str, object]]:
    """Run all providers while preserving failures and never inventing votes."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if not prompt.strip():
        raise ValueError("prompt must not be empty")

    results: list[dict[str, object]] = []
    for provider_spec in providers:
        provider = str(provider_spec.get("provider", ""))
        model = str(provider_spec.get("model", ""))
        if not provider or not model:
            results.append(_failed_attempt(provider, model, "error", "missing provider/model"))
            continue

        attempt = _call_provider(
            provider,
            model,
            prompt,
            runner,
            timeout_seconds,
            retry_prompt=short_prompt,
        )
        results.append(attempt)
    return results


def _call_provider(
    provider: str,
    model: str,
    prompt: str,
    runner: Callable[[str, str, float], Mapping[str, object]],
    timeout_seconds: float,
    *,
    retry_prompt: str,
) -> dict[str, object]:
    try:
        response = dict(runner(provider, prompt, timeout_seconds))
        verdict = str(response.get("verdict", "")).lower()
        if verdict not in VALID_VERDICTS:
            return _failed_attempt(provider, model, "error", "review missing or invalid verdict")
        return _completed_attempt(provider, model, verdict, response)
    except BaseException as error:
        first_status = _status_for_error(error)
        if not retry_prompt.strip():
            return _failed_attempt(provider, model, first_status, str(error))
        try:
            response = dict(runner(provider, retry_prompt, timeout_seconds))
            verdict = str(response.get("verdict", "")).lower()
            if verdict not in VALID_VERDICTS:
                return _failed_attempt(provider, model, "error", "short retry missing or invalid verdict")
            result = _completed_attempt(provider, model, verdict, response)
            result["retry"] = "short_prompt"
            result["initial_status"] = first_status
            return result
        except BaseException as retry_error:
            return _failed_attempt(
                provider,
                model,
                _status_for_error(retry_error),
                f"initial={error}; retry={retry_error}",
            )


def _completed_attempt(
    provider: str,
    model: str,
    verdict: str,
    response: Mapping[str, object],
) -> dict[str, object]:
    return {
        "provider": provider,
        "model": model,
        "status": "completed",
        "verdict": verdict,
        "response": dict(response),
        "counts_as_approval": verdict in APPROVAL_VERDICTS,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def _failed_attempt(
    provider: str,
    model: str,
    status: str,
    reason: str,
) -> dict[str, object]:
    return {
        "provider": provider,
        "model": model,
        "status": status,
        "verdict": None,
        "reason": reason,
        "counts_as_approval": False,
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }


def committee_quorum(
    attempts: Iterable[Mapping[str, object]],
    *,
    minimum_approvals: int = 2,
) -> dict[str, object]:
    if minimum_approvals <= 0:
        raise ValueError("minimum_approvals must be positive")
    completed = [
        attempt for attempt in attempts
        if attempt.get("status") == "completed"
        and str(attempt.get("verdict", "")).lower() in VALID_VERDICTS
    ]
    approvals = [
        attempt for attempt in completed
        if str(attempt.get("verdict", "")).lower() in APPROVAL_VERDICTS
    ]
    return {
        "completed_votes": len(completed),
        "approval_votes": len(approvals),
        "quorum": len(approvals) >= minimum_approvals,
        "unavailable": [
            {
                "provider": attempt.get("provider", ""),
                "model": attempt.get("model", ""),
                "status": attempt.get("status", ""),
                "reason": attempt.get("reason", ""),
            }
            for attempt in attempts
            if attempt.get("status") != "completed"
        ],
        "production_weights_changed": False,
        "verdict_mutated": False,
        "trades_created": False,
    }
