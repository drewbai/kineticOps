"""CLI presentation layer using rich."""

from rich.console import Console


def run_cli_banner() -> None:
    """Render a startup banner for local runs."""
    # TODO: Add command parsing and interactive controls.
    Console().print("[bold cyan]KineticOps[/bold cyan] - hackathon scaffold ready")
