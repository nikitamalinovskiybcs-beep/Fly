from pathlib import Path
import threading

import pytest

from src.agent_coordinator import AgentCoordinator
from src.agent_event_bus import AgentEventBus
from src.self_learning_agents import run_all_self_learning_agents


def test_event_bus_replays_hash_linked_safe_events(tmp_path: Path) -> None:
    bus = AgentEventBus(tmp_path / "events.jsonl")
    snapshot_id = bus.publish_snapshot(payload={"tickers": ["AAPL"]})
    bus.publish_signal(
        snapshot_id=snapshot_id,
        agent="risk",
        signal={"scoring_adj": -1.0, "confidence": 0.7},
    )
    records = bus.replay()
    assert len(records) == 2
    assert records[1]["previous_hash"] == records[0]["event_hash"]
    assert records[1]["payload"]["research_only"] is True


def test_event_bus_rejects_unsafe_payload(tmp_path: Path) -> None:
    bus = AgentEventBus(tmp_path / "events.jsonl")
    with pytest.raises(ValueError, match="unsafe:trades_created"):
        bus.append(
            event_type="agent_signal",
            snapshot_id="snapshot",
            payload={"trades_created": True},
        )


def test_agent_director_publishes_without_changing_contract(tmp_path: Path) -> None:
    bus = AgentEventBus(tmp_path / "events.jsonl")
    result = run_all_self_learning_agents(
        tickers=["AAPL"],
        yf_data={"AAPL": {"iv30": 20.0}},
        features={"momentum": 0.1},
        base_score=70.0,
        event_bus=bus,
        evidence_gate={"passed": False},
    )
    assert result["decision"] == "BLOCKED"
    assert result["event_bus"]["status"] == "blocked"
    assert bus.replay() == []


def test_coordinator_runs_bounded_autonomous_cycles(tmp_path: Path) -> None:
    bus = AgentEventBus(tmp_path / "events.jsonl")
    coordinator = AgentCoordinator(bus)
    stop_event = threading.Event()
    cycle_input = (
        ["AAPL"],
        {"AAPL": {"iv30": 20.0}},
        {"momentum": 0.1},
        70.0,
        {"passed": False},
    )
    cycles = coordinator.run_forever(
        lambda: cycle_input,
        stop_event,
        interval_seconds=0.01,
        max_cycles=2,
    )
    assert cycles == 2
    assert bus.replay() == []
