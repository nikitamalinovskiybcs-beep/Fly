"""Local autonomous coordinator for the research-only agent cycle."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import threading

from src.agent_event_bus import AgentEventBus
from src.agent_memory import AgentMemory
from src.self_learning_agents import run_all_self_learning_agents


CycleInput = tuple[
    list[str],
    dict[str, dict[str, object]],
    dict[str, float],
    float,
    Mapping[str, object] | None,
]


class AgentCoordinator:
    """Run repeatable local cycles without mutating production state."""

    def __init__(
        self,
        event_bus: AgentEventBus,
        memory: AgentMemory | None = None,
    ):
        self.event_bus = event_bus
        self.memory = memory

    def run_once(self, cycle_input: CycleInput) -> dict[str, object]:
        tickers, yf_data, features, base_score, evidence_gate = cycle_input
        report = run_all_self_learning_agents(
            tickers=tickers,
            yf_data=yf_data,
            features=features,
            base_score=base_score,
            evidence_gate=dict(evidence_gate) if evidence_gate else None,
            event_bus=self.event_bus,
        )
        if self.memory is not None:
            snapshot_id = str(report.get("event_bus", {}).get("snapshot_id", ""))
            if snapshot_id:
                self.memory.append(
                    kind="agent_cycle",
                    snapshot_id=snapshot_id,
                    agent="agent_coordinator",
                    payload={
                        "agents_run": report.get("agents_run", 0),
                        "agents_ok": report.get("agents_ok", 0),
                        "director_status": report.get("director_status", ""),
                        "signal_disagreement": report.get(
                            "signal_disagreement", False
                        ),
                        "research_only": True,
                    },
                )
        return report

    def run_forever(
        self,
        provider: Callable[[], CycleInput],
        stop_event: threading.Event,
        *,
        interval_seconds: float = 60.0,
        max_cycles: int | None = None,
    ) -> int:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        cycles = 0
        while not stop_event.is_set() and (
            max_cycles is None or cycles < max_cycles
        ):
            self.run_once(provider())
            cycles += 1
            if max_cycles is None or cycles < max_cycles:
                stop_event.wait(interval_seconds)
        return cycles
