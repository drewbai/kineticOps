"""Optional Prometheus telemetry adapter stub."""

from typing import Any


def fetch_prometheus_metrics() -> list[dict[str, Any]]:
    """Fetch and normalize Prometheus metric samples."""
    # TODO: Implement Prometheus query and mapping logic.
    return []
