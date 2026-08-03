"""Versioned, append-only research memory for agent coordination."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


SAFETY_FLAGS = (
    "production_weights_changed",
    "verdict_mutated",
    "trades_created",
)
MEMORY_SCHEMA_VERSION = "1.0"
VALID_STATUSES = {"completed", "timeout", "error", "unavailable", "deferred"}


def _hash_record(record: Mapping[str, object]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AgentMemory:
    """Persist typed agent memory without treating it as market evidence."""

    def __init__(
        self,
        path: str | Path = "data/runtime/agent_memory.jsonl",
        manifest_path: str | Path = "data/runtime/agent_memory_manifest.json",
    ) -> None:
        self.path = Path(path)
        self.manifest_path = Path(manifest_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def write_manifest(self, items: Iterable[Mapping[str, object]]) -> dict[str, object]:
        normalized = [dict(item) for item in items]
        ids = [str(item.get("id", "")) for item in normalized]
        if not normalized or any(not item_id for item_id in ids):
            raise ValueError("manifest items require ids")
        if len(ids) != len(set(ids)):
            raise ValueError("manifest ids must be unique")
        manifest = {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "item_count": len(normalized),
            "items": normalized,
            "manifest_hash": _hash_record(
                {
                    "schema_version": MEMORY_SCHEMA_VERSION,
                    "item_count": len(normalized),
                    "items": normalized,
                }
            ),
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        }
        self.manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        return manifest

    def read_manifest(self) -> dict[str, object]:
        if not self.manifest_path.exists():
            return {}
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        expected = _hash_record(
            {
                "schema_version": manifest["schema_version"],
                "item_count": manifest["item_count"],
                "items": manifest["items"],
            }
        )
        if manifest.get("manifest_hash") != expected:
            raise ValueError("memory manifest hash is invalid")
        self._check_safety(manifest)
        return manifest

    def append(
        self,
        *,
        kind: str,
        snapshot_id: str,
        agent: str,
        payload: Mapping[str, object],
        status: str = "completed",
        provider: str = "",
        model: str = "",
        evidence_class: str = "research",
    ) -> dict[str, object]:
        if not kind.strip() or not snapshot_id.strip() or not agent.strip():
            raise ValueError("kind, snapshot_id, and agent are required")
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid memory status: {status}")
        self._check_safety(payload)
        records = self.replay()
        record: dict[str, object] = {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "memory_id": f"{snapshot_id}:{agent}:{len(records)}",
            "kind": kind,
            "snapshot_id": snapshot_id,
            "agent": agent,
            "payload": dict(payload),
            "status": status,
            "provider": provider,
            "model": model,
            "evidence_class": evidence_class,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": str(records[-1]["record_hash"]) if records else "",
            "production_weights_changed": False,
            "verdict_mutated": False,
            "trades_created": False,
        }
        record["record_hash"] = _hash_record(record)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
        return record

    def replay(
        self,
        *,
        snapshot_id: str | None = None,
        agent: str | None = None,
    ) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        previous_hash = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            record_hash = record.pop("record_hash", None)
            if record.get("previous_hash", "") != previous_hash:
                raise ValueError("agent memory chain is broken")
            if record_hash != _hash_record(record):
                raise ValueError("agent memory record hash is invalid")
            self._check_safety(record)
            record["record_hash"] = record_hash
            records.append(record)
            previous_hash = str(record_hash)
        return [
            record
            for record in records
            if (snapshot_id is None or record["snapshot_id"] == snapshot_id)
            and (agent is None or record["agent"] == agent)
        ]

    @staticmethod
    def _check_safety(payload: Mapping[str, object]) -> None:
        for flag in SAFETY_FLAGS:
            if payload.get(flag, False) is not False:
                raise ValueError(f"unsafe:{flag}")
