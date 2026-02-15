"""Basic scaffold tests for KineticOps."""

from interpreter.rule_engine import RuleEngine
from kinetic_core.event_loop import KineticEventLoop


def test_event_loop_starts_and_stops() -> None:
    """Ensure the event loop toggles running state."""
    # TODO: Expand into golden-path integration tests for the sprint demo.
    loop = KineticEventLoop()
    loop.start()
    assert loop.running is True
    loop.stop()
    assert loop.running is False


def test_rule_engine_returns_intent() -> None:
    """Ensure the rule engine produces a minimal intent shape."""
    # TODO: Add tests for configured remote planner behavior.
    engine = RuleEngine()
    result = engine.evaluate({"signal": "cpu_high", "value": 90})
    assert "intent" in result
