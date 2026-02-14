"""Local event classification helpers for offline-friendly AI paths."""

from __future__ import annotations

import json
import os
import re
from typing import Any

LABELS = ("NetworkIssue", "ServiceFailure", "AuthFailure", "StorageWarning")


class LocalEventClassifier:
    """Classify events using a local model first, then deterministic rules."""

    def __init__(self) -> None:
        self.model_enabled = os.getenv("KINETICOPS_LOCAL_CLASSIFIER_ENABLED", "1") == "1"
        self.strict_json = os.getenv("KINETICOPS_LOCAL_CLASSIFIER_STRICT_JSON", "1") == "1"
        self.primary_model = os.getenv(
            "KINETICOPS_LOCAL_CLASSIFIER_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        )
        self.max_new_tokens = int(os.getenv("KINETICOPS_LOCAL_CLASSIFIER_MAX_TOKENS", "64"))
        self._tokenizer: Any | None = None
        self._model: Any | None = None

    def classify(self, event: dict[str, Any]) -> dict[str, Any]:
        """Return normalized classification and reason for an event."""
        event_text = self._event_text(event)

        if self.model_enabled:
            model_result = self._classify_with_primary_model(event_text)
            if model_result is not None:
                model_result["source"] = "tinyllama"
                return model_result

        rule_result = self._classify_with_rules(event_text)
        rule_result["source"] = "rules"
        return rule_result

    def _classify_with_primary_model(self, event_text: str) -> dict[str, Any] | None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception:
            return None

        try:
            if self._tokenizer is None:
                self._tokenizer = AutoTokenizer.from_pretrained(self.primary_model)
            if self._model is None:
                self._model = AutoModelForCausalLM.from_pretrained(self.primary_model)

            prompt = (
                "Classify this event into one label: "
                "NetworkIssue, ServiceFailure, AuthFailure, StorageWarning. "
                "Return ONLY JSON with keys classification, reason, and confidence (0..1). "
                f"Event: {event_text}"
            )
            inputs = self._tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                outputs = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens)
            decoded = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            return self._parse_output(decoded)
        except Exception:
            return None

    def _parse_output(self, text: str) -> dict[str, Any] | None:
        json_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if isinstance(data, dict):
                    label = self._normalize_label(str(data.get("classification", "")))
                    reason = str(data.get("reason", "model_classification"))
                    if label is not None:
                        confidence = self._normalize_confidence(data.get("confidence"), 0.85)
                        return {
                            "classification": label,
                            "reason": reason,
                            "confidence": confidence,
                        }
            except json.JSONDecodeError:
                pass

        if self.strict_json:
            return None

        label_match = re.search(r"classification\s*:\s*([A-Za-z]+)", text, flags=re.IGNORECASE)
        reason_match = re.search(r"reason\s*:\s*(.+)", text, flags=re.IGNORECASE)
        if label_match:
            label = self._normalize_label(label_match.group(1))
            if label is not None:
                reason = reason_match.group(1).strip() if reason_match else "model_classification"
                return {"classification": label, "reason": reason, "confidence": 0.6}

        return None

    def _classify_with_rules(self, event_text: str) -> dict[str, Any]:
        lowered = event_text.lower()

        auth_terms = ("auth", "token", "unauthorized", "forbidden", "permission", "login")
        network_terms = ("network", "dns", "timeout connecting", "connection reset", "unreachable")
        storage_terms = ("disk", "storage", "volume", "i/o", "filesystem", "capacity")

        if any(term in lowered for term in auth_terms):
            return {
                "classification": "AuthFailure",
                "reason": "keyword_auth_signal",
                "confidence": 0.82,
            }
        if any(term in lowered for term in storage_terms):
            return {
                "classification": "StorageWarning",
                "reason": "keyword_storage_signal",
                "confidence": 0.78,
            }
        if any(term in lowered for term in network_terms):
            return {
                "classification": "NetworkIssue",
                "reason": "keyword_network_signal",
                "confidence": 0.8,
            }
        return {
            "classification": "ServiceFailure",
            "reason": "default_service_fallback",
            "confidence": 0.55,
        }

    def _event_text(self, event: dict[str, Any]) -> str:
        signal = str(event.get("signal", ""))
        message = str(event.get("message", event.get("error", "")))
        payload = str(event)
        return f"signal={signal}; message={message}; payload={payload}"

    def _normalize_label(self, label: str) -> str | None:
        cleaned = label.strip().lower()
        mapping = {
            "networkissue": "NetworkIssue",
            "servicefailure": "ServiceFailure",
            "authfailure": "AuthFailure",
            "storagewarning": "StorageWarning",
        }
        if cleaned in mapping:
            return mapping[cleaned]

        for candidate in LABELS:
            if cleaned == candidate.lower():
                return candidate
        return None

    def _normalize_confidence(self, value: Any, default: float) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        if parsed < 0:
            return 0.0
        if parsed > 1:
            return 1.0
        return parsed
