"""Local autonomous coordinator for the research-only agent cycle."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import threading

from src.agent_event_bus import AgentEventBus
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

    def __init__(self, event_bus: AgentEventBus):
        self.event_bus = event_bus

    def run_once(self, cycle_input: CycleInput) -> dict[str, object]:
        tickers, yf_data, features, base_score, evidence_gate = cycle_input
        return run_all_self_learning_agents(
            tickers=tickers,
            yf_data=yf_data,
            features=features,
            base_score=base_score,
            evidence_gate=dict(evidence_gate) if evidence_gate else None,
            event_bus=self.event_bus,
        )

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
