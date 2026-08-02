"""Base agent abstract class."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base for all Fly agents."""

    @abstractmethod
    def fit(self, data: Any) -> None:
        """Train or fit the agent on data."""

    @abstractmethod
    def predict(self, data: Any) -> dict:
        """Generate predictions/signals."""

    @abstractmethod
    def evaluate(self) -> dict:
        """Evaluate agent performance."""

    @abstractmethod
    def retrain(self) -> None:
        """Retrain the agent with updated data."""
