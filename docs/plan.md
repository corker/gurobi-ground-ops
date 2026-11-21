# Implementation plan

What to build, in order, and when each step counts as done. The rules for *how* to build are in [AGENTS.md](../AGENTS.md). The reasons behind each choice are in [design-decisions.md](design-decisions.md), referred to below by number (D1, D2, ...). Every step is checked against the lenses in [quality-lenses.md](quality-lenses.md) that apply to it.

**The goal.** Afterwards, the owner can talk about solver behaviour without bluffing: read a Gurobi log, explain what the MIP gap and the bound are doing, and tell a formulation problem from an operational one. The code is the means, not the deliverable.

**Stop rule.** If Model 1 takes longer than expected, stop after Model 1. One correct model beats two rushed ones. Don't describe a step as working until it's done.

## Status

| Step | Goal | Status |
| --- | --- | --- |
| 1 | Project setup: package and a smoke test that proves the free licence works | Done |
| 2 | Model 1, task assignment, with golden tests and the CLI | Done |
| 3 | Model 2, shift coverage | Done |
| 4 | Solver telemetry (the most important step) | Done |
| 5 | Observability stack: LGTM in Docker Compose, dashboard, traces, logs | Done |
| 6 | Operational edges: early stop, warm start, IIS, determinism | Done |
| 7 | Required test set | Done |
| 8 | API with live progress | Done |
| 9 | UI | Done |

Update this table in the same commit that finishes a step.

## Step 1: Project setup

The licence limits are verified (D1): 2,000 variables and 2,000 linear constraints, with the gurobipy 14 licence expiring on 2028-11-29.

- Create the project with `uv init --package --name ground-ops`: a `src/ground_ops/` package, the `uv_build` backend, and a `ground-ops` command. `requires-python = ">=3.12"`, and `.python-version` set to `3.12`. Remove the generated hello-world entry point and stub; Step 2 adds the `ground-ops` command with `solve`.
- Step 1 adds only what Step 1 uses: `gurobipy~=14.0`, plus `pytest`, `ruff` and `mypy` as dev dependencies. The ruff rule set and mypy's strict mode are configured in `pyproject.toml`. Each later step adds its own dependencies when it first needs them: the OpenTelemetry API, SDK and OTLP exporter in Step 4, FastAPI and uvicorn in Step 8. The core library never imports the API or UI. Commit `uv.lock`.
- In `pyproject.toml`, `authors` lists the owner's name only. `uv init` copies the email address from git config, so remove it before committing; the repo is public.
- A `.gitignore` for the virtual environment, caches, Gurobi `*.log` and `*.ilp` files, and `gurobi.lic`. An MIT `LICENSE`: `Copyright (c) 2026` followed by the owner's name as it appears in `git config user.name`.
- Tests live in `tests/`. A first smoke test solves a trivial model with gurobipy and checks that it reports optimal, which proves the free licence is active.
- Keep the existing README. Add a "How to run" section once these commands work.

**Done when:** `uv sync && uv run pytest` passes, with the smoke test, on a checkout with no licence file. (With no tests at all, pytest exits with code 5, which isn't a pass.)

## Step 2: Model 1, handler-to-task assignment

- `docs/domain.md`: the glossary and the list of simplifications (D12).
- A seeded instance generator with tunable size, using task durations based on the turnaround dataset (D11).
- The model (D2, D3): a binary variable x[h,t] for each handler and task; each task covered exactly once; pairwise no-overlap constraints with a uniform 10-minute gap between a handler's tasks (D3); the objective is minutes worked outside each handler's shift window. The formulation is written out in a new "Models" section of the README, with sets, variables, constraints and objective.
- One frozen result type, shared by both models: status, objective, bound, gap and the solution. It starts with the statuses this step can produce (optimal, infeasible); Step 6 adds "limit reached" and the IIS, and Step 8 adds "interrupted", each when first needed.
- An independent feasibility checker in repo code, which doesn't trust the solver (lens 1).
- A CLI, `ground-ops solve`, that runs a seeded instance and prints the result. Experiments and the log walkthrough use it.
- Add `pytest-cov` and branch-coverage reporting (`--cov=ground_ops --cov-branch --cov-report=term-missing`).

**Done when:** golden tests pass that assert exact objectives on small fixed instances, plus feasibility (every task covered, no overlaps), never a specific assignment (D10). Every instance fits the free limit.

## Step 3: Model 2, shift coverage

Start only after Model 1 is done and tested.

- Set covering: choose integer staffing per shift pattern so that every half-hour of demand is covered, at minimum cost. This is a different structure from Model 1.
- Parameters: a 24-hour horizon of 48 half-hour slots; patterns of 4, 6 or 8 hours starting at any slot; one unpaid break slot in patterns of 6 hours or more; cost is the number of paid slots. The demand profile comes from the seeded generator.

**Done when:** the same kinds of tests pass as for Model 1: golden objective plus coverage feasibility.

## Step 4: Solver telemetry (the most important step)

- A Gurobi callback that emits, during the solve: MIP gap, incumbent, best bound, the count of improved incumbents (computed by comparing values, D6), node count, simplex iterations, elapsed time and work units.
- Export OpenTelemetry metrics over OTLP/HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. When it isn't, create no exporter, so nothing is sent anywhere (D16). Metric names, units and attributes follow D6. Per-run values, including the incumbent-improvement count, use observable gauges for active runs, labelled with a `run_id` that is unique across processes (D21).
- Check that the final emitted values equal the model's final `ObjVal`, `ObjBound` and `NodeCount` (lens 12). Write a Gurobi log (`LogFile`) for instrumented runs, for the walkthrough below.
- README: the gap-and-bound explainer, written to be understood cold in six months. It must explain that a bound that won't move and an incumbent that won't improve are different problems.
- `docs/reading-the-log.md`: a real log from this repo, annotated (D13).

**Done when:** tests read the metrics through an in-memory reader with no collector, and a run with the variable unset creates no exporter.

## Step 5: Observability stack

- A `grafana/otel-lgtm` service in `compose.yaml` (D16). The CLI runs on the host and exports to it on port 4318.
- A Grafana dashboard provisioned as JSON: incumbent and bound on one panel, and gap, nodes and incumbent improvements on others, filtered by `run_id`. Queries use Prometheus's renamed metrics, such as `groundops_solver_gap_ratio`.
- Traces with one span per phase (instance generation, model build, solve), carrying `run_id`. Step 6 adds a span for IIS. Gurobi's log lines go to Loki through the `MESSAGE` callback.
- Opt-in integration tests (`uv run pytest -m integration`) that start `grafana/otel-lgtm` with Testcontainers and check that one real run's metrics, trace, log lines and the provisioned dashboard all arrive.

**Done when:** one `docker compose up` plus one CLI run shows the run's curve in Grafana, its spans in Tempo and its log lines in Loki. `uv run pytest` still passes with no Docker.

## Step 6: Operational edges, each with a test

- **Early stop:** stop after a given effort and return the best solution plus its gap. "Feasible but not proven optimal" is a normal result the caller can distinguish, not an error. Tests use `WorkLimit` (D7) and assert the result status "limit reached, feasible". Because default instances solve at the root (D4), these tests also set `Presolve=0, Cuts=0` to expose the search.
- **Warm start:** re-solve a perturbed instance (one task moves) using the previous solution as a `Start`. Report the difference in work units (Gurobi's deterministic measure of solver effort, used instead of seconds) against a cold start across seeds, even if it's "no measurable gain" (D8).
- **Infeasibility diagnosis:** compute an IIS on an infeasible instance and report the conflicting constraints readably (D9). The CLI reports infeasible results with the IIS.
- **Determinism:** pin `Seed` and `Threads`. Document which settings make a run reproducible, and measure whether the thread count changes the search (Gurobi's docs don't say; D7).

The progress recorder takes its final sample from the model after every solve, so an infeasible run's last exported values are its own, not a mid-run bound.

**Done when:** each of the four edges has a test: the early stop returns "limit reached, feasible" with a non-zero gap; the warm-start comparison runs and reports its numbers (`experiments/warm_start.py`; a test checks that the start is used and reaches the cold optimum); the IIS names the conflicting constraints; two runs with the same `Seed` and `Threads` give the same node count.

## Step 7: Tests

The required tests are the "Done when" items of Steps 2 to 6: golden objectives, structural feasibility, the early stop returning feasible-but-not-optimal with a non-zero gap, a warm start that is used and reaches the cold optimum (the comparison itself is `experiments/warm_start.py`), an IIS naming the right constraints, and a reproducibility check.

**Done when:** `uv run pytest` passes all of them on the free licence, with no collector running.

The test set was checked by planting one bug at a time in the code each required test guards, such as reporting a stopped solve as optimal, skipping the warm start, listing every constraint as the IIS, or randomising `Seed`. Every planted bug made a test fail, except `cover >= 1` in place of `== 1`: with overtime costs that are never negative, an optimal solution never gains from a second handler on a task, and `Result.solution` maps each task to one handler, so an optimal result can't show the difference. A limit-reached incumbent could in principle carry a second handler with overtime, which isn't ruled out.

## Step 8: API with live progress

- FastAPI under `/api`, reachable from `127.0.0.1` only (D17): `POST /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/events` (SSE, D18) and `POST /api/runs/{id}/cancel`.
- `POST /api/runs` takes the model, instance size, seed, whether to expose the search (D4), and an optional effort limit. An instance over the free-licence size is rejected before it's built. There are two workers; when both are busy it returns 429.
- The result is the same result type the models return (Step 2). Each SSE `progress` event carries elapsed time, incumbent, bound, gap, nodes and iterations (D6). A final `done` event carries the status.
- One Gurobi environment per run, created and freed under one lock (D17). Cancel calls `terminate()`, and the result reports `interrupted` with the best solution so far.
- A missing run returns 404 before any stream starts. A reconnecting client resumes from `Last-Event-ID`.

**Done when:** `TestClient` tests cover every endpoint, including reading the SSE stream until `done`, cancelling, and a 404 for a missing run. A boundary test imports the core modules and asserts that FastAPI wasn't loaded, so the core can't start depending on the API unnoticed.

## Step 9: UI

- `ui/`: React, Vite and TypeScript (D19), with types generated from the OpenAPI schema (D20).
- Quality checks (D22): `"strict": true` in `tsconfig.app.json` (the template doesn't set it), oxlint with type-aware rules, Prettier and Vitest, run together by `npm run check`. oxlint was compared with ESLint and typescript-eslint on planted bugs before it was chosen (D22).
- Two pages: New run, and a run page that shows live progress (gap, incumbent and bound from SSE, Cancel, a link to Grafana) and then the result (a Gantt chart for Model 1, demand against staffing for Model 2, the IIS explained when infeasible).
- Docker Compose runs the API (uvicorn with `--reload`) and the Vite dev server, with the source mounted (D24). Vite proxies `/api` to the API container.
- The Grafana link opens the provisioned dashboard filtered to the run's `run_id` and its time window.
- The run page closes its `EventSource` on `done`; otherwise the browser reconnects to the closed stream forever. Both event payload types (`Progress` and `Finished`) are in the OpenAPI schema, so the UI's types are generated, not hand-written (D20).

**Done when:** Vitest tests in `ui/` pass with a mocked API and cover all four statuses (optimal, limit reached, infeasible, interrupted). A run started from the UI against the real API reaches each page, and cancelling it shows `interrupted`.

## Experiments

Each script in `experiments/` re-measures a result from [design-decisions.md](design-decisions.md) and records it in `docs/experiments.md` with the machine and settings (D14). The first set:

| Experiment | Decision |
| --- | --- |
| Pairwise vs clique no-overlap: LP bound and constraint count | D3, D15 |
| Default settings vs `Presolve=0, Cuts=0`: node counts across seeds | D4 |
| Callback overhead in work units, with and without the callback | D6 |
| Warm start vs cold start (full and partial `Start`) over 20 seeds | D8 |
| The same run with 1 and 4 threads | D7 |
| Number of tied optimal solutions | D10 |
| Metric export to LGTM: what Grafana shows for a short solve | D16 |
| Run identity: cardinality cap and concurrent runs | D21 |
