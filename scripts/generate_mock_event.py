"""Script to generate mock telemetry events."""

from telemetry.mock_adapter import fetch_mock_event


def main() -> None:
    """Print one mock event to stdout."""
    # TODO: Support event type flags and continuous generation mode.
    print(fetch_mock_event())


if __name__ == "__main__":
    main()
