"""Application entrypoint for KineticOps."""

from interpreter.rule_engine import RuleEngine
from kinetic_core.event_loop import KineticEventLoop
from telemetry.mock_adapter import fetch_mock_event
from ui.cli import run_cli_banner


def main() -> None:
    """Wire core components and start the stubbed runtime."""
    # TODO: Inject adapters and engines through a lightweight composition root.
    run_cli_banner()
    event_loop = KineticEventLoop()
    rule_engine = RuleEngine()
    event_loop.start()
    event = fetch_mock_event()
    intent = rule_engine.evaluate(event)
    event_loop.tick({"event": event, "intent": intent})


if __name__ == "__main__":
    main()
