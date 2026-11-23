"""Provider-agnostic AI judge panel for research-only model review."""

from __future__ import annotations

import os
from collections.abc import Mapping

import requests

from src.gemini_judge import _extract_json, build_judge_prompt, judge_report


JsonObject = dict[str, object]

OPENAI_COMPATIBLE_PROVIDERS = {
    "cerebras": {
        "key": "CEREBRAS_API_KEY",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
    },
    "nvidia": {
        "key": "NVIDIA_API_KEY",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "meta/llama-3.1-8b-instruct",
    },
    "openai": {
        "key": "OPENAI_API_KEY",
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
    },
    "mistral": {
        "key": "MISTRAL_API_KEY",
        "url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-small-latest",
    },
    "groq": {
        "key": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openai/gpt-4o-mini",
    },
}


def _validated_review(result: JsonObject) -> JsonObject:
    if not isinstance(result.get("verdict"), str):
        raise ValueError("review is missing a verdict")
    return result


def _call_ollama(
    prompt: str,
    *,
    url: str,
    model: str,
    num_ctx: int = 4096,
    keep_alive: str = "0",
) -> JsonObject:
    request = {
        "model": model,
        "stream": False,
        "format": "json",
        "keep_alive": keep_alive,
        "options": {"num_ctx": num_ctx},
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(
        f"{url.rstrip('/')}/api/chat",
        json=request,
        timeout=90,
    )
    if response.status_code == 400:
        request.pop("format")
        response = requests.post(
            f"{url.rstrip('/')}/api/chat",
            json=request,
            timeout=90,
        )
    response.raise_for_status()
    payload = response.json()
    message = payload.get("message")
    if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
        raise ValueError("Ollama response has no text content")
    result = _extract_json(message["content"])
    result.update(
        {
            "provider": "ollama",
            "model": model,
            "production_weights_changed": False,
            "verdict_mutated": False,
        },
    )
    return _validated_review(result)


def _safe_result(provider: str, status: str, reason: str) -> JsonObject:
    return {
        "provider": provider,
        "status": status,
        "reason": reason,
        "production_weights_changed": False,
        "verdict_mutated": False,
    }


def _call_openai_compatible(
    provider: str,
    config: Mapping[str, str],
    api_key: str,
    prompt: str,
) -> JsonObject:
    response = requests.post(
        config["url"],
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": config["model"],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("provider response contains no choices")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ValueError("provider response choice is invalid")
    message = choice.get("message")
    if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
        raise ValueError("provider response has no text content")
    result = _extract_json(message["content"])
    result.update(
        {
            "provider": provider,
            "model": config["model"],
            "production_weights_changed": False,
            "verdict_mutated": False,
        },
    )
    return _validated_review(result)


def _call_anthropic(
    api_key: str,
    prompt: str,
    model: str = "claude-3-5-haiku-latest",
) -> JsonObject:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 1800,
            "temperature": 0.1,
            "system": "Return only valid JSON.",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("content")
    if not isinstance(content, list) or not content:
        raise ValueError("Anthropic response contains no content")
    first = content[0]
    if not isinstance(first, Mapping) or not isinstance(first.get("text"), str):
        raise ValueError("Anthropic response has no text")
    result = _extract_json(first["text"])
    result.update(
        {
            "provider": "anthropic",
            "model": model,
            "production_weights_changed": False,
            "verdict_mutated": False,
        },
    )
    return _validated_review(result)


def run_judge_panel(
    report: Mapping[str, object],
    proposal: Mapping[str, object],
    environ: Mapping[str, str] | None = None,
) -> JsonObject:
    variables = environ or os.environ
    prompt = build_judge_prompt(report, proposal)
    reviews: list[JsonObject] = []

    ollama_url = variables.get("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_models = variables.get(
        "OLLAMA_MODELS",
        variables.get(
            "OLLAMA_MODEL",
            "qwen2.5:1.5b,deepseek-r1:1.5b,llama3.2:1b,gemma3:1b",
        ),
    )
    ollama_num_ctx = int(variables.get("OLLAMA_NUM_CTX", "4096"))
    ollama_keep_alive = variables.get("OLLAMA_KEEP_ALIVE", "0")
    for ollama_model in (
        model.strip() for model in ollama_models.split(",") if model.strip()
    ):
        provider = f"ollama:{ollama_model}"
        try:
            reviews.append(
                {
                    "provider": provider,
                    "status": "completed",
                    "review": _call_ollama(
                        prompt,
                        url=ollama_url,
                        model=ollama_model,
                        num_ctx=ollama_num_ctx,
                        keep_alive=ollama_keep_alive,
                    ),
                },
            )
        except requests.ConnectionError:
            reviews.append(_safe_result(provider, "skipped", "Ollama is not running"))
        except requests.Timeout:
            reviews.append(_safe_result(provider, "deferred", "Ollama timed out"))
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else 0
            reviews.append(_safe_result(provider, "deferred", f"HTTP {status}"))
        except (ValueError, KeyError) as error:
            reviews.append(_safe_result(provider, "error", str(error)))

    gemini_key = variables.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            reviews.append(
                {
                    "provider": "google_gemini",
                    "status": "completed",
                    "review": _validated_review(
                        judge_report(report, proposal, gemini_key),
                    ),
                },
            )
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else 0
            reviews.append(_safe_result("google_gemini", "deferred", f"HTTP {status}"))
        except (ValueError, KeyError) as error:
            reviews.append(_safe_result("google_gemini", "error", str(error)))
    else:
        reviews.append(_safe_result("google_gemini", "skipped", "API key not configured"))

    anthropic_key = variables.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            reviews.append(
                {
                    "provider": "anthropic",
                    "status": "completed",
                    "review": _call_anthropic(anthropic_key, prompt),
                },
            )
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else 0
            reviews.append(_safe_result("anthropic", "deferred", f"HTTP {status}"))
        except (ValueError, KeyError) as error:
            reviews.append(_safe_result("anthropic", "error", str(error)))
    else:
        reviews.append(_safe_result("anthropic", "skipped", "API key not configured"))

    for provider, config in OPENAI_COMPATIBLE_PROVIDERS.items():
        api_key = variables.get(config["key"], "")
        if not api_key:
            reviews.append(_safe_result(provider, "skipped", "API key not configured"))
            continue
        try:
            reviews.append(
                {
                    "provider": provider,
                    "status": "completed",
                    "review": _call_openai_compatible(
                        provider,
                        config,
                        api_key,
                        prompt,
                    ),
                },
            )
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else 0
            reviews.append(_safe_result(provider, "deferred", f"HTTP {status}"))
        except (ValueError, KeyError) as error:
            reviews.append(_safe_result(provider, "error", str(error)))

    completed = [
        item
        for item in reviews
        if item["status"] == "completed"
    ]
    verdicts = [
        item["review"]["verdict"]
        for item in completed
        if isinstance(item.get("review"), Mapping)
        and isinstance(item["review"].get("verdict"), str)
    ]
    consensus = max(set(verdicts), key=verdicts.count) if verdicts else "unavailable"
    return {
        "status": "completed" if completed else "deferred",
        "consensus_verdict": consensus,
        "completed_providers": [item["provider"] for item in completed],
        "reviews": reviews,
        "production_weights_changed": False,
        "verdict_mutated": False,
    }
