"""Tests for local AI classification fallback behavior."""

from interpreter.ai_planner import AIIntentPlanner
from interpreter.local_classifier import LocalEventClassifier


def test_local_classifier_keyword_auth_path(monkeypatch) -> None:
    """Classifier should map auth-like signals without model downloads."""
    monkeypatch.setenv("KINETICOPS_LOCAL_CLASSIFIER_ENABLED", "0")
    classifier = LocalEventClassifier()

    result = classifier.classify(
        {"signal": "auth_error", "message": "unauthorized token expired"}
    )

    assert result["classification"] == "AuthFailure"
    assert result["source"] == "rules"
    assert result["confidence"] > 0.7


def test_planner_uses_local_fallback_when_remote_unset(monkeypatch) -> None:
    """Planner should return local intent when remote endpoint is not configured."""
    monkeypatch.delenv("KINETICOPS_AI_ENDPOINT", raising=False)
    monkeypatch.delenv("KINETICOPS_AI_API_KEY", raising=False)
    monkeypatch.setenv("KINETICOPS_LOCAL_CLASSIFIER_ENABLED", "0")

    planner = AIIntentPlanner()
    result = planner.plan(
        {"signal": "network_error", "message": "dns lookup timeout connecting to db"}
    )

    assert result["intent"] == "classify_event"
    assert result["classification"] == "NetworkIssue"
    assert result["source"] == "rules"
    assert 0 <= result["confidence"] <= 1


def test_strict_json_parser_rejects_non_json(monkeypatch) -> None:
    """Strict mode should not parse loose key/value text."""
    monkeypatch.setenv("KINETICOPS_LOCAL_CLASSIFIER_STRICT_JSON", "1")
    classifier = LocalEventClassifier()

    parsed = classifier._parse_output("classification: NetworkIssue\nreason: timeout")

    assert parsed is None


def test_strict_json_parser_accepts_json_with_confidence(monkeypatch) -> None:
    """Strict mode should parse valid JSON payloads."""
    monkeypatch.setenv("KINETICOPS_LOCAL_CLASSIFIER_STRICT_JSON", "1")
    classifier = LocalEventClassifier()

    parsed = classifier._parse_output(
        '{"classification":"StorageWarning","reason":"disk usage high","confidence":0.91}'
    )

    assert parsed is not None
    assert parsed["classification"] == "StorageWarning"
    assert parsed["reason"] == "disk usage high"
    assert parsed["confidence"] == 0.91
