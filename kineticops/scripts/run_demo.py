"""Run a compact KineticOps demo with predefined event scenarios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interpreter.rule_engine import RuleEngine
from telemetry.mock_adapter import fetch_mock_event

SCENARIOS: dict[str, dict[str, Any]] = {
    "network": {
        "source": "demo",
        "signal": "network_error",
        "message": "dns timeout connecting to db",
        "value": 1,
    },
    "auth": {
        "source": "demo",
        "signal": "auth_error",
        "message": "unauthorized token expired",
        "value": 1,
    },
    "storage": {
        "source": "demo",
        "signal": "storage_warning",
        "message": "filesystem capacity over 92%",
        "value": 92,
    },
    "service": {
        "source": "demo",
        "signal": "service_down",
        "message": "api worker crashed with exit code 137",
        "value": 137,
    },
}


def run_single(name: str, event: dict[str, Any], rule_engine: RuleEngine) -> None:
    """Evaluate one event and print a compact result block."""
    intent = rule_engine.evaluate(event)
    print(f"\n=== Scenario: {name} ===")
    print("event:")
    print(json.dumps(event, indent=2, sort_keys=True))
    print("intent:")
    print(json.dumps(intent, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    """Parse CLI flags for scenario selection."""
    parser = argparse.ArgumentParser(description="Run KineticOps demo scenarios.")
    parser.add_argument(
        "--scenario",
        choices=["all", "mock", *sorted(SCENARIOS.keys())],
        default="all",
        help="Choose which scenario to run.",
    )
    return parser.parse_args()


def main() -> None:
    """Execute one or more demo scenarios."""
    args = parse_args()
    rule_engine = RuleEngine()

    if args.scenario == "mock":
        run_single("mock", fetch_mock_event(), rule_engine)
        return

    if args.scenario == "all":
        for name in sorted(SCENARIOS.keys()):
            run_single(name, SCENARIOS[name], rule_engine)
        return

    run_single(args.scenario, SCENARIOS[args.scenario], rule_engine)


if __name__ == "__main__":
    main()
