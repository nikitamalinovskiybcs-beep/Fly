from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from src.agent_memory import AgentMemory


def test_manifest_and_replay_are_versioned_and_filterable(tmp_path: Path) -> None:
    memory = AgentMemory(tmp_path / "memory.jsonl", tmp_path / "manifest.json")
    manifest = memory.write_manifest([{"id": "improvement-01", "status": "pending"}])
    assert manifest["schema_version"] == "1.0"
    event = memory.append(
        kind="committee_finding",
        snapshot_id="snapshot-1",
        agent="quant_payoff",
        payload={"finding": "needs provenance"},
        provider="mistral",
        model="mistral-small-latest",
    )
    assert event["production_weights_changed"] is False
    assert len(memory.replay(snapshot_id="snapshot-1", agent="quant_payoff")) == 1


def test_missing_provider_is_preserved_and_not_approval(tmp_path: Path) -> None:
    memory = AgentMemory(tmp_path / "memory.jsonl")
    event = memory.append(
        kind="committee_finding",
        snapshot_id="snapshot-1",
        agent="calibration_oos",
        payload={"counts_as_approval": False},
        status="timeout",
        provider="ollama",
        model="qwen",
    )
    assert event["status"] == "timeout"
    assert event["payload"]["counts_as_approval"] is False


def test_tampering_and_unsafe_flags_are_rejected(tmp_path: Path) -> None:
    memory = AgentMemory(tmp_path / "memory.jsonl")
    memory.append(
        kind="signal",
        snapshot_id="snapshot-1",
        agent="guardian",
        payload={},
    )
    (tmp_path / "memory.jsonl").write_text(
        (tmp_path / "memory.jsonl").read_text().replace('"kind": "signal"', '"kind": "tampered"'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash"):
        memory.replay()
    with pytest.raises(ValueError, match="unsafe"):
        memory.append(
            kind="signal",
            snapshot_id="snapshot-2",
            agent="guardian",
            payload={"trades_created": True},
        )


def test_encrypted_backup_round_trip_and_wrong_key_rejected(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    source = AgentMemory(tmp_path / "source.jsonl", tmp_path / "source.json")
    source.write_manifest([{"id": "improvement-01", "status": "pending"}])
    source.append(
        kind="signal",
        snapshot_id="snapshot-1",
        agent="guardian",
        payload={"finding": "safe"},
    )
    bundle = tmp_path / "memory.bundle"
    result = source.export_encrypted_bundle(bundle, key=key)
    assert result["encrypted"] is True

    restored = AgentMemory(tmp_path / "restored.jsonl", tmp_path / "restored.json")
    assert restored.restore_encrypted_bundle(bundle, key=key)["restored"] is True
    assert len(restored.replay()) == 1
    with pytest.raises(ValueError, match="encrypted"):
        restored.restore_encrypted_bundle(bundle, key=Fernet.generate_key())
