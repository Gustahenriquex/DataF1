"""Command-line entry point: `f1i <command>` (run `f1i --help`)."""

from __future__ import annotations

import typer

from f1i import __version__
from f1i.config import Settings, get_settings
from f1i.doctor import Status, run_checks
from f1i.log import configure_logging

app = typer.Typer(
    name="f1i",
    help="F1 Intelligence: data pipeline and analytics CLI.",
    no_args_is_help=True,
    add_completion=False,
)

_STATUS_TAG = {Status.OK: "[ OK ]", Status.WARN: "[WARN]", Status.FAIL: "[FAIL]"}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"f1i {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    configure_logging(get_settings())


@app.command("config")
def show_config() -> None:
    """Print the effective settings (secrets masked)."""
    settings: Settings = get_settings()
    for key, value in settings.model_dump().items():
        typer.echo(f"{key:<34} {value}")
    typer.echo(f"{'database_url':<34} {settings.database_url}")
    typer.echo(f"{'fastf1_cache_path':<34} {settings.fastf1_cache_path}")


@app.command()
def doctor(
    offline: bool = typer.Option(False, "--offline", help="Skip checks that call external APIs."),
) -> None:
    """Check Python, packages, folders, disk space, PostgreSQL and API reachability."""
    results = run_checks(get_settings(), offline=offline)
    for result in results:
        typer.echo(f"{_STATUS_TAG[result.status]} {result.name:<13} {result.detail}")
    failed = sum(r.status is Status.FAIL for r in results)
    warned = sum(r.status is Status.WARN for r in results)
    typer.echo(f"\n{len(results)} checks: {failed} failed, {warned} warnings")
    if failed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
