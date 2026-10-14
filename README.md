# F1 Intelligence

Strategic analytics platform for Formula 1: a reproducible data pipeline over public
F1 data, race and tyre-strategy analytics, machine-learning models evaluated with
leakage-safe temporal validation, and an AI race engineer whose answers are grounded
in queried data.

> **Status:** Phase 0 (foundation). See [docs/ROADMAP.md](docs/ROADMAP.md) for phases,
> completion criteria and risks. This README will be expanded as phases are delivered;
> it only describes what already exists.

> **Disclaimer:** This is an unofficial, non-commercial portfolio project. It is not
> associated in any way with Formula 1 companies. F1, FORMULA ONE, FORMULA 1, FIA FORMULA
> ONE WORLD CHAMPIONSHIP, GRAND PRIX and related marks are trademarks of Formula One
> Licensing B.V.

## Quickstart

Requirements: Python 3.12 or 3.13, [uv](https://docs.astral.sh/uv/), Git, and
PostgreSQL 17 (via Docker Desktop, or a native install).

```bash
# 1. Install the locked dependencies into .venv
uv sync

# 2. Create your local config and set F1I_DB_PASSWORD
cp .env.example .env

# 3. Start PostgreSQL (Docker); skip if you run a native PostgreSQL
docker compose up -d postgres

# 4. Verify the environment
uv run f1i doctor

# 5. Run the test suite
uv run pytest
```

`f1i doctor` checks the Python version, key packages, writable data folders, free
disk space, PostgreSQL connectivity and Jolpica-F1 reachability, and exits non-zero
if any check fails.

## Project layout

```
src/f1i/          Python package (config, logging, CLI, pipeline modules)
tests/            pytest suite (offline by default)
docs/             roadmap, architecture, data coverage, metric definitions
data/             local raw data + caches (git-ignored)
```

## Tests

```bash
uv run pytest                  # offline unit tests (default)
uv run pytest -m network       # tests that call live public APIs
uv run pytest -m integration   # tests that need a running PostgreSQL
uv run ruff check . && uv run ruff format --check .
```

## Data sources & licensing

| Source | Used for | Licence / terms |
|---|---|---|
| [FastF1](https://docs.fastf1.dev/) | Lap timing, tyres, pit in/out, track status, weather, telemetry (2018+) | Library: MIT. Data comes from the F1 live-timing service; FastF1 is unofficial. |
| [Jolpica-F1](https://github.com/jolpica/jolpica-f1) (Ergast-compatible) | Historical results, standings, drivers, constructors, circuits | Data: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), non-commercial use only; rate limited (4 req/s, 500 req/h). |

Raw data is **never** committed to this repository. Any derived data published with
the demo is shared under CC BY-NC-SA 4.0 with attribution to the sources above.

## License

Code: [MIT](LICENSE). Data: see the table above.
