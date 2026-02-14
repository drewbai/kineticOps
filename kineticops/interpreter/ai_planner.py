"""AI intent planning stubs for KineticOps."""

import json
import os
from typing import Any

import requests

from interpreter.local_classifier import LocalEventClassifier


class AIIntentPlanner:
    """Minimal LLM-backed planner with safe local fallback."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("KINETICOPS_AI_ENDPOINT", "")
        self.model = os.getenv(
            "KINETICOPS_AI_MODEL", "meta/llama-4-maverick-17b-128e-instruct-fp8"
        )
        self.timeout_seconds = float(os.getenv("KINETICOPS_AI_TIMEOUT", "8"))
        self.api_key = os.getenv("KINETICOPS_AI_API_KEY", os.getenv("GITHUB_TOKEN", ""))
        self.local_classifier = LocalEventClassifier()

    def enabled(self) -> bool:
        """Return whether remote AI planning is configured."""
        # TODO: Add provider presets and stricter endpoint validation.
        return bool(self.endpoint and self.api_key)

    def plan(self, event: dict[str, Any]) -> dict[str, Any]:
        """Return action intent predicted by a model endpoint."""
        if not self.enabled():
            return self.local_plan(event)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only JSON with keys: intent, reason, and optional patch_hint."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"event": event}),
                },
            ],
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # TODO: Add retries and strict response schema validation.
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return self.local_plan(event)

        if isinstance(data.get("intent"), dict):
            return data["intent"]

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            content = choices[0].get("message", {}).get("content")
            if isinstance(content, str):
                try:
                    intent = json.loads(content)
                    if isinstance(intent, dict):
                        if "intent" in intent:
                            return intent
                except json.JSONDecodeError:
                    pass

        return self.local_plan(event)

    def local_plan(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build a local classification-first intent for offline reliability."""
        local = self.local_classifier.classify(event)
        return {
            "intent": "classify_event",
            "classification": local["classification"],
            "reason": local["reason"],
            "source": local["source"],
            "confidence": local["confidence"],
            "event": event,
        }
