"""Local append-only event exchange for research-only agent signals."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


SAFETY_FLAGS = (
    "production_weights_changed",
    "verdict_mutated",
    "trades_created",
)


def snapshot_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AgentEventBus:
    """Persist immutable snapshots and typed research events locally."""

    def __init__(self, path: str | Path = "data/runtime/agent_events.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        event_type: str,
        snapshot_id: str,
        payload: Mapping[str, object],
        evidence_class: str = "research",
        provider: str = "",
        model: str = "",
    ) -> dict[str, object]:
        if not event_type.strip() or not snapshot_id.strip():
            raise ValueError("event_type and snapshot_id are required")
        for flag in SAFETY_FLAGS:
            if payload.get(flag, False) is not False:
                raise ValueError(f"unsafe:{flag}")

        records = self.replay()
        previous_hash = str(records[-1]["event_hash"]) if records else ""
        event: dict[str, object] = {
            "event_type": event_type,
            "snapshot_id": snapshot_id,
            "payload": dict(payload),
            "evidence_class": evidence_class,
            "provider": provider,
            "model": model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous_hash,
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        }
        canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
        event["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
        return event

    def replay(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        previous_hash = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            event_hash = record.pop("event_hash", None)
            if record.get("previous_hash", "") != previous_hash:
                raise ValueError("event hash chain is broken")
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
            expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if event_hash != expected_hash:
                raise ValueError("event hash is invalid")
            for flag in SAFETY_FLAGS:
                if record.get(flag) is not False:
                    raise ValueError(f"unsafe:{flag}")
            record["event_hash"] = event_hash
            records.append(record)
            previous_hash = str(event_hash)
        return records

    def publish_snapshot(
        self,
        *,
        payload: Mapping[str, object],
        evidence_class: str = "research",
    ) -> str:
        snapshot_id = snapshot_hash(payload)
        self.append(
            event_type="agent_snapshot",
            snapshot_id=snapshot_id,
            payload=payload,
            evidence_class=evidence_class,
        )
        return snapshot_id

    def publish_signal(
        self,
        *,
        snapshot_id: str,
        agent: str,
        signal: Mapping[str, object],
        evidence_class: str = "research",
    ) -> dict[str, object]:
        payload = {
            "agent": agent,
            "signal": dict(signal),
            "research_only": True,
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        }
        return self.append(
            event_type="agent_signal",
            snapshot_id=snapshot_id,
            payload=payload,
            evidence_class=evidence_class,
        )
