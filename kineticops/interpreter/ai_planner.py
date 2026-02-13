"""AI intent planning stubs for KineticOps."""

import json
import os
from typing import Any

import requests


class AIIntentPlanner:
    """Minimal LLM-backed planner with safe local fallback."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("KINETICOPS_AI_ENDPOINT", "")
        self.model = os.getenv(
            "KINETICOPS_AI_MODEL", "meta/llama-4-maverick-17b-128e-instruct-fp8"
        )
        self.timeout_seconds = float(os.getenv("KINETICOPS_AI_TIMEOUT", "8"))
        self.api_key = os.getenv("KINETICOPS_AI_API_KEY", os.getenv("GITHUB_TOKEN", ""))

    def enabled(self) -> bool:
        """Return whether remote AI planning is configured."""
        # TODO: Add provider presets and stricter endpoint validation.
        return bool(self.endpoint and self.api_key)

    def plan(self, event: dict[str, Any]) -> dict[str, Any]:
        """Return action intent predicted by a model endpoint."""
        if not self.enabled():
            # TODO: Replace with richer local policy fallback for offline runs.
            return self._fallback_intent(event)

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
        response = requests.post(
            self.endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data.get("intent"), dict):
            return data["intent"]

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            content = choices[0].get("message", {}).get("content")
            if isinstance(content, str):
                try:
                    intent = json.loads(content)
                    if isinstance(intent, dict):
                        return intent
                except json.JSONDecodeError:
                    pass

        return self._fallback_intent(event)

    def _fallback_intent(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build a deterministic fallback intent from simple event cues."""
        signal = str(event.get("signal", "unknown"))
        return {
            "intent": "inspect",
            "reason": f"fallback_from_signal:{signal}",
            "event": event,
        }
