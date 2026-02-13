"""State models and in-memory state tracking for KineticOps."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    """Placeholder runtime state container."""

    last_event: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_from_event(self, event: dict[str, Any]) -> None:
        """Update state from an incoming event."""
        # TODO: Define canonical event/state schema and persistence strategy.
        self.last_event = event
