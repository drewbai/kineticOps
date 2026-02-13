"""Patch generation stubs for Kubernetes manifest changes."""

from typing import Any


def build_patch(intent: dict[str, Any]) -> str:
    """Create a text patch from an action intent."""
    # TODO: Generate strategic merge/JSON patches from normalized intents.
    return "# TODO: generated patch"
