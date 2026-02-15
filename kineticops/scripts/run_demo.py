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
    "cpu": {
        "source": "demo",
        "signal": "cpu_hotspot",
        "message": "worker node CPU sustained above 95%",
        "value": 95,
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
    "queue": {
        "source": "demo",
        "signal": "queue_backlog",
        "message": "deployment queue stalled with 42 pending jobs",
        "value": 42,
    },
}

DEFAULT_OUTPUT_PATH = Path("assets/demo-results.json")


def run_single(name: str, event: dict[str, Any], rule_engine: RuleEngine) -> dict[str, Any]:
    """Evaluate one event, print output, and return structured result."""
    intent = rule_engine.evaluate(event)
    result = {"scenario": name, "event": event, "intent": intent}
    print(f"\n=== Scenario: {name} ===")
    print("event:")
    print(json.dumps(event, indent=2, sort_keys=True))
    print("intent:")
    print(json.dumps(intent, indent=2, sort_keys=True))
    return result


def parse_args() -> argparse.Namespace:
    """Parse CLI flags for scenario selection."""
    parser = argparse.ArgumentParser(description="Run KineticOps demo scenarios.")
    parser.add_argument(
        "--scenario",
        choices=["all", "mock", *sorted(SCENARIOS.keys())],
        default="all",
        help="Choose which scenario to run.",
    )
    parser.add_argument(
        "--output",
        nargs="?",
        type=Path,
        const=DEFAULT_OUTPUT_PATH,
        help="Optional path to write JSON results (defaults to assets/demo-results.json).",
    )
    return parser.parse_args()


def main() -> None:
    """Execute one or more demo scenarios."""
    args = parse_args()
    rule_engine = RuleEngine()
    results: list[dict[str, Any]] = []

    if args.scenario == "mock":
        results.append(run_single("mock", fetch_mock_event(), rule_engine))
    elif args.scenario == "all":
        for name in sorted(SCENARIOS.keys()):
            results.append(run_single(name, SCENARIOS[name], rule_engine))
    else:
        results.append(run_single(args.scenario, SCENARIOS[args.scenario], rule_engine))

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{json.dumps(results, indent=2, sort_keys=True)}\n", encoding="utf-8")
        print(f"\nWrote demo results to: {args.output}")


if __name__ == "__main__":
    main()
