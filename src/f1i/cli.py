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


@app.command()
def ingest(
    season: str = typer.Option(..., help="Season(s): '2025', '2022-2026' or '2022,2024'."),
    rounds: str = typer.Option(None, help="Rounds like '1-3,7' (default: all completed)."),
    refresh: bool = typer.Option(False, help="Re-download instead of using raw files."),
) -> None:
    """Download season(s) (Jolpica + FastF1) and load them into the raw schema."""
    from f1i.keep_awake import keep_awake
    from f1i.pipeline import ingest_season, parse_rounds

    failed = 0
    with keep_awake():  # backfills take hours; idle sleep would freeze the process
        for year in parse_rounds(season, []):
            report = ingest_season(get_settings(), year, rounds, refresh)
            typer.echo(f"{year}: loaded rounds {report.loaded_rounds}")
            for round_, reason in report.failed_rounds.items():
                typer.echo(f"[FAIL] {year} round {round_}: {reason}")
            failed += len(report.failed_rounds)
    if failed:
        typer.echo(
            f"{failed} round(s) failed; re-run the same command to retry "
            "(downloaded rounds are not fetched again)"
        )
        raise typer.Exit(code=1)


@app.command()
def build() -> None:
    """Run dbt (models + tests) to rebuild the staging and marts schemas."""
    from f1i.pipeline import run_dbt

    if not run_dbt(get_settings(), ["build"]):
        raise typer.Exit(code=1)


@app.command("app")
def run_app() -> None:
    """Open the Streamlit dashboard."""
    import subprocess
    import sys

    from f1i.config import PROJECT_ROOT

    script = PROJECT_ROOT / "app" / "streamlit_app.py"
    command = [sys.executable, "-m", "streamlit", "run", str(script)]
    raise typer.Exit(subprocess.call(command, cwd=PROJECT_ROOT))  # cwd: .streamlit/config.toml


if __name__ == "__main__":
    app()
