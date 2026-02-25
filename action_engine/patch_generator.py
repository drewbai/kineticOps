"""Patch generation helpers for translating intents into GitOps artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class PatchArtifact:
    """Represents a materialized manifest that should be committed via GitOps."""

    filename: str
    content: str
    summary: str


def build_patch(intent: dict[str, Any], *, loop_name: str | None = None) -> PatchArtifact:
    """Generate a lightweight manifest that documents the requested intent.

    The intent payload coming from the rule/AI planners is loosely structured, so the
    generated manifest captures the essential drift signal rather than attempting a
    full strategic merge patch. GitOps operators can use this as a placeholder until
    a richer policy-driven patch engine is available.
    """

    if not isinstance(intent, dict):
        raise ValueError("intent must be a dictionary")

    loop_slug = _sanitize_slug(loop_name or intent.get("loop") or "loop")
    filename = f"{loop_slug}-intent.yaml"
    intent_name = intent.get("intent", "noop")
    classification = intent.get("classification", "unknown")
    summary = intent.get("reason", f"intent={intent_name}")

    manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": loop_slug,
            "labels": {
                "ops.kineticops.dev/intent": intent_name,
                "ops.kineticops.dev/classification": classification,
            },
        },
        "data": {
            "intent": intent_name,
            "classification": classification,
            "reason": summary,
            "source": intent.get("source", "rule-engine"),
        },
    }

    yaml_body = yaml.safe_dump(manifest, sort_keys=False).strip() + "\n"
    return PatchArtifact(filename=filename, content=yaml_body, summary=summary)


def _sanitize_slug(value: str) -> str:
    slug = value.lower().strip()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "loop"
