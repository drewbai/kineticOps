"""Mock telemetry adapter for local development and demos."""

from typing import Any


def fetch_mock_event() -> dict[str, Any]:
    """Return a synthetic telemetry event."""
    # TODO: Expand with richer mock payloads and scenario generators.
    return {"source": "mock", "signal": "cpu_high", "value": 92}
