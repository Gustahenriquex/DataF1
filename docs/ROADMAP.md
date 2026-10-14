# Roadmap

Each phase ends only when its completion criteria are met **and evidenced** (command
output, test run, report). Effort is in focused hours. Priority: P0 = required for the
portfolio, P1 = strongly desired, P2 = stretch.

## Architecture decisions

| # | Decision | Why |
|---|---|---|
| D1 | Layered ELT: `raw` (immutable source payloads, Parquet/JSON) → `staging` (typed, validated) → `marts` (analytics) | Reprocessing never needs a re-download; every number is traceable to a source payload. |
| D2 | PostgreSQL from the MVP (Docker Compose locally, service container in CI) | Project requirement; a real SQL warehouse from day one. |
| D3 | dbt (`dbt-postgres`) for relational transformations from Phase 1 | Tests, docs and lineage for every model; avoids rewriting ad-hoc SQL later. |
| D4 | One typed service layer (`f1i.services`) used by the dashboard, the API and the AI agent's tools | The AI race engineer can never report a number that differs from the dashboard. |
| D5 | Idempotent ingestion per session (delete + insert by natural key) with a run manifest | Safe re-runs and backfills; auditable loads. |
| D6 | CLI first, Prefect in Phase 7; no Airflow | Airflow needs Docker/WSL on Windows and is oversized for a weekly batch. |
| D7 | uv + lockfile, Python 3.13 (3.12 also supported) | Reproducible installs; 3.13 is the installed interpreter and the whole stack (dbt 1.11, FastF1 3.8, Streamlit) resolves and imports on it. |
| D8 | Statistical/ML code in Python (SciPy, scikit-learn), relational modelling in SQL | Each tool where it is strongest. |

## Phases

### Phase 0 — Foundation · 3–5 h · P0
Repo layout, uv/pyproject, typed settings, logging, `.env.example`, ruff, pytest, CI,
licence and data notice, `f1i doctor`.
- [x] `uv sync` succeeds from a clean clone
- [x] `uv run pytest` passes (offline)
- [x] `uv run ruff check .` and `ruff format --check .` pass
- [x] `uv run f1i --help` / `f1i doctor` run
- [x] PostgreSQL reachable: `f1i doctor` → postgres OK, `pytest -m integration` passes
- [x] CI green on GitHub (lint, unit tests, integration tests against PostgreSQL 17)

### Phase 1 — Executable MVP (vertical slice) · 12–20 h · P0
Season 2025 race sessions: Jolpica results/standings + FastF1 laps, stints, pit stops,
track status → raw Parquet → PostgreSQL → dbt staging/marts → Streamlit pages: Season
Overview, Race Analysis (lap-time evolution, stints), Driver Comparison (race pace,
consistency).
- [ ] One command ingests, one builds, one opens the dashboard **with real data**
- [ ] Transformation tests pass (clean-lap filter, stint derivation)
- [ ] Data coverage report generated for the ingested sessions

### Phase 2 — Data platform · 15–25 h · P0
Backfill 2018–2026 (to date), retries/back-off, rate-limit throttling, run manifest,
pandera contracts on raw data, dbt tests + docs, per-season coverage matrix, schema docs.
- [ ] Re-running any load creates no duplicates
- [ ] `dbt build` green; `docs/data_coverage.md` published

### Phase 3 — Race analytics & pit stops · 15–25 h · P0
Race pace, consistency, per-stint tyre degradation (robust regression with CIs),
sectors, telemetry overlays, pit-loss per circuit (green vs SC/VSC), circuit history.
- [ ] Every metric defined in `docs/metrics.md`, unit-tested on synthetic data with a
      known answer, shown with sample size and caveats

### Phase 4 — Machine learning · 15–20 h · P0
Lap-time / degradation model: baselines → Ridge → gradient boosting; walk-forward
validation by race/season; MAE, RMSE, residuals by compound, interval coverage. Pace
normalisation uses only pre-race information (normalising by the race's own median leaks
future laps).
- [ ] Reproducible evaluation report from one command
- [ ] Automated test asserting no training row is later than any test row
- [ ] Honest comparison against baselines, even if the model loses

### Phase 5 — Strategy simulator · 12–18 h · P1
Race time = pace + degradation (Phase 4) + pit loss (Phase 3); Monte Carlo; SC/VSC
scenarios; backtest against observed strategies.
- [ ] Backtest error reported; assumptions visible in the UI; always labelled
      "counterfactual simulation"

### Phase 6 — API & AI Race Engineer · 15–25 h · P0 (basic) / P1 (full eval)
FastAPI over the service layer; tool-using LLM agent; ~30 reference questions with an
automated check that every number in an answer comes from a tool result.
- [ ] Eval pass rate measured and published; app works without an API key

### Phase 7 — Production · 10–20 h · P1
Full Docker Compose stack, Prefect flows, complete CI, public deploy.
- [ ] `docker compose up` starts everything; demo reachable; costs documented

### Phase 8 — Portfolio packaging · 6–10 h · P0
README, Mermaid architecture diagrams, model card, screenshots/GIFs, CV/LinkedIn text.
- [ ] Every number in README/CV links to a report in the repo

**Stretch (P2):** probabilistic finishing-position model (log loss, Brier, calibration
vs grid-only baseline), MLflow, 1950+ historical backfill.

## Risks

| Risk | Mitigation |
|---|---|
| Low free disk space on the dev machine | Configurable cache dir, telemetry on demand only, compressed Parquet; `f1i doctor` warns below 10 GB |
| Rate limits (Jolpica 4 req/s & 500 req/h; FastF1 500 calls/h) | Cache, throttling, incremental loads; backfill spread across runs |
| Volunteer-run / unofficial APIs may change or go down | Immutable raw layer, offline test fixtures, pinned versions |
| Non-commercial data licence (CC BY-NC-SA 4.0) and trademarks | No raw data in git, attribution, disclaimer, no logos/official fonts |
| Data quality (deleted/inaccurate laps, red flags, 2018 compound names, sprint formats) | Tested clean-lap filter, explicit flags, coverage matrix |
| Fuel load is unobserved and confounds tyre degradation | Configurable, documented fuel-correction assumption + sensitivity analysis |
| Regulation changes (2022, 2026) shift distributions | Era features; 2026 evaluated separately |
| LLM hallucination / cost | Tool-only answers, automated eval, spend cap on the public demo |
| Scope creep | Phase gates; P2 only after P0/P1 |
