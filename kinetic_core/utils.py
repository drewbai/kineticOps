"""Utility helpers shared across KineticOps modules."""

from datetime import datetime, timezone


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    # TODO: Centralize logging/trace formatting helpers.
    return datetime.now(timezone.utc).isoformat()
