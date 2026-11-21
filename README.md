# Learning Gurobi on ground-operations problems

I'm a backend/platform engineer picking up Gurobi — I'm not an optimisation modeller. The models here are small and textbook, chosen because airport ground operations has clear real-world assignment and covering problems. The part I care about is what surrounds the solve: telemetry, deterministic tests, effort limits, warm starts and infeasibility diagnosis.

## What it does

At an airport, ground staff unload and load baggage between flights. Each task has a fixed start time, so someone has to decide **who does which task**, without anyone being in two places at once. Everyone has a shift, and any work outside it is **overtime**, which costs money. The first model (**Model 1**, task assignment) finds the schedule with the least overtime. The second (**Model 2**, shift coverage) answers a simpler question: **how many people to roster on each shift pattern** so there are enough on duty in every half hour of the day.

You describe the rules ("every task gets exactly one person", "nobody does two overlapping tasks", "minimise overtime") and a **solver** searches for the best schedule. While it searches, it tracks two numbers:

- **The incumbent:** the best schedule found so far ("I have a plan with 55 minutes of overtime").
- **The bound:** how good any schedule *could* possibly be ("I can prove nothing beats 35 minutes").

The difference between them is the **gap**. When the gap closes, the solver has proven its plan is the best possible. Often it finds the best plan early and spends most of its time proving it. The UI lets you watch this:

- **Watch a solve:** gap, incumbent and bound update live. You can cancel at any point and keep the best plan found so far.
- **Inspect the answer:** a timeline per person shows their tasks and marks the overtime.
- **Diagnose infeasibility:** when no schedule is possible, it shows *which* tasks and people clash.

## Quick start

With [Docker](https://docs.docker.com/get-started/get-docker/) (Engine 25 or later) running:

```sh
docker compose up --wait   # the observability stack, the API and the UI
docker compose down        # stop everything; the stack's telemetry goes with it
```

Open the UI at http://127.0.0.1:5173 and Grafana at http://localhost:3000. The source is mounted into the containers: the API reloads when a Python file changes, and the UI updates in the browser when a UI file changes. With Docker Desktop, a change can take a while to reach the container. `docker compose logs -f api` follows the API's output. On the machine in [docs/experiments.md](docs/experiments.md), with the images already pulled, `up --wait` took 28 s the first time (it installs the packages into the containers) and 10 s after that ([D24](docs/design-decisions.md#24-the-app-in-docker-for-local-development)).

The CLI, the tests and the UI's checks run on the host: see [How to run](#how-to-run).

## Terms used below

- **Warm start:** starting the solver from a known solution, such as the previous schedule, instead of from nothing.
- **IIS** (irreducible inconsistent subsystem): a set of constraints that can't all hold at once, where removing any one of them lets the rest hold. It shows why a problem is infeasible. It's irreducible, not necessarily the smallest such set.
- **LP relaxation:** the same problem with the whole-number requirements dropped (allowing, say, half a person on a task). It's fast to solve, and the bound comes from its answer.
- **Presolve:** simplifications the solver makes before it starts searching.
- **Cuts:** extra constraints the solver adds to tighten the LP relaxation, which raises the bound.
- **Symmetry:** many equivalent solutions, such as two identical handlers swapped, which the solver may explore separately.
- **Root node:** the first step of the search, before any branching. "Solved at the root" means no search was needed.
- **Work units:** Gurobi's deterministic measure of effort. Unlike seconds, the same run always takes the same work.
- **OTLP:** OpenTelemetry's protocol for sending metrics, traces and logs to a collector.
- **SSE** (server-sent events): a standard way for a web server to push a stream of updates to a browser.

## How it fits together

```
  browser ─▶ Vite (React UI) ──HTTP/SSE──▶ FastAPI (/api)
                                      │  one Gurobi environment per run
  CLI (ground-ops solve) ────────▶ core library
                                      ├─ instance generators (seeded)
                                      ├─ Model 1 and Model 2
                                      ├─ Gurobi solve
                                      └─ telemetry (solver callback)
                                            │ OTLP, only when a collector is configured
                                            ▼
                          grafana/otel-lgtm
                          (Prometheus, Tempo, Loki, Grafana)

  docker compose runs lgtm, the API and the UI; the CLI and the tests run on the host.
```

- **Core library (Python):** seeded instance generators, the two models, and the Gurobi solve. A solver callback emits the gap, incumbent, bound, incumbent improvements, node count, simplex iterations, elapsed time and work units.
- **Telemetry:** OpenTelemetry metrics, traces and logs, sent over OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. When it isn't set, nothing is exported.
- **Observability stack:** one [`grafana/otel-lgtm`](https://github.com/grafana/docker-otel-lgtm) container with a provisioned dashboard. The image is meant for development, demos and testing.
- **API:** FastAPI, reachable from `127.0.0.1` only. Start a run, stream its progress over SSE, cancel it, fetch the result. Runs live in memory.
- **UI:** React, Vite and TypeScript, with two pages: a new-run form, and a run page that shows live progress and then the result.

The core library never imports the API or UI. `uv run pytest` needs no Docker, no Node and no browser; the UI has its own tests in `ui/`.

## How to run

The core needs only [uv](https://docs.astral.sh/uv/), which installs Python 3.12 and all dependencies. No Gurobi licence file is needed: the `gurobipy` package brings its own free licence.

```sh
uv sync
uv run pytest
```

Solve a seeded Model 1 instance and print the schedule:

```sh
uv run ground-ops solve --tasks 10 --seed 3
```

```
Model 1: 10 tasks, 6 handlers, seed 3
status: optimal  overtime: 9 min  bound: 9 min  gap: 0.00%
H0 shift 08:00-16:00: T1 08:45-09:02, T4 11:00-11:11, T3 11:24-11:33
H1 shift 05:00-13:00: T9 07:43-08:01, T0 08:30-08:40, T7 11:18-11:31
H2 shift 05:30-09:30: T2 11:00-11:09 (+9 overtime)
H3 shift 09:30-13:30: T6 11:00-11:14
H4 shift 07:00-11:00: no tasks
H5 shift 07:00-13:00: T8 07:35-07:45, T5 11:08-11:27
```

`--tasks` must be even (two baggage tasks per turnaround). H2 does T2 entirely after its shift ends. That's valid: the objective counts only minutes outside the shift, not how far outside, so H2 and H4 (also 9 minutes) tie.

Up to 48 tasks fit the free licence for every seed tried (20 seeds per size). From 50 on, some seeds don't, and the command says so instead of solving ([measured](docs/experiments.md#what-fits-the-free-licence-d1)).

Roster a seeded Model 2 day (48 half-hour slots, 111 shift patterns) and print demand against people on duty:

```sh
uv run ground-ops cover --seed 2
```

```
Model 2: 48 half-hour slots, 111 shift patterns, seed 2
status: optimal  cost: 228 paid half-hours  bound: 228 paid half-hours  gap: 0.00%
roster:
  1 x 00:00-04:00
  1 x 02:00-08:00 (break 05:00)
  ...
slot   demand  on duty
...
```

`solve` and `cover` both take `--log FILE` to append Gurobi's log to a file, and `--expose-search` to set `Presolve=0` and `Cuts=0` so the branch-and-bound search becomes visible.

### Telemetry

Set `OTEL_EXPORTER_OTLP_ENDPOINT` to an OpenTelemetry collector's OTLP/HTTP address, and every solve exports its progress once a second while it runs (`OTEL_METRIC_EXPORT_INTERVAL` changes that). Leave it unset and nothing is exported. The command prints the run's `run_id` to stderr.

```sh
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 uv run ground-ops solve --tasks 40 --expose-search
```

| Metric (OpenTelemetry name) | Unit | From |
| --- | --- | --- |
| `groundops.solver.gap` | ratio | incumbent and bound |
| `groundops.solver.incumbent` | objective | best solution so far |
| `groundops.solver.bound` | objective | best proven bound |
| `groundops.solver.incumbent_improvements` | solutions | count of better solutions found |
| `groundops.solver.nodes` | nodes | branch-and-bound nodes explored |
| `groundops.solver.simplex_iterations` | iterations | simplex iterations so far |
| `groundops.solver.elapsed` | seconds | wall-clock time |
| `groundops.solver.work` | work units | Gurobi's deterministic effort measure |

Each point carries `run_id` and `model` (`assignment` or `coverage`) attributes. In Prometheus, dots become underscores and a real unit becomes a suffix: `groundops.solver.gap` is `groundops_solver_gap_ratio`. Units in braces add no suffix, so `groundops.solver.bound` is `groundops_solver_bound`. A run's last values come from the model's final attributes, not the last callback, because the last callback can fire before the final bound is known.

### Watching a solve in Grafana

The `lgtm` service in `compose.yaml` runs an OpenTelemetry Collector with Prometheus (metrics), Tempo (traces), Loki (logs) and Grafana. The CLI runs on your machine and exports to it on port 4318.

```sh
docker compose up --wait
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 uv run ground-ops solve --tasks 40 --seed 1 --expose-search
```

Open Grafana at http://localhost:3000 (if it asks you to log in, the image's default user is `admin` with password `admin`), go to the **ground-ops: solver progress** dashboard, and pick the `run_id` the command printed. It shows incumbent against bound, the gap, nodes, simplex iterations, work units, and Gurobi's log lines for that run. Each run is also a trace in Tempo, with one span per phase (generate instance, build model, solve); Tempo's search can take tens of seconds to find a new trace. The stack keeps data only while its container lives.

If the endpoint is set but nothing is listening, the run still completes, but the result appears only after the exporters give up retrying. A 10-task solve took a median of 19.7 s, against 1.2 s with `OTEL_EXPORTER_OTLP_TIMEOUT=1` (the SDK's default is 10 s) and 0.2 s with the endpoint unset ([measured](docs/experiments.md#exporting-to-an-endpoint-with-nothing-listening)). Unset `OTEL_EXPORTER_OTLP_ENDPOINT` when the stack isn't running.

### Integration tests

The integration tests start their own `grafana/otel-lgtm` container, run a real solve through the real exporter, and check that the metrics, logs, trace and dashboard all arrive. They need Docker and are excluded from `uv run pytest`:

```sh
uv run pytest -m integration
```

### The HTTP API

`docker compose up --wait` runs the API on http://127.0.0.1:8000, reachable from this machine only, with no authentication. Runs live in memory and are lost when the API restarts, including when it reloads after a code change. A reload waits at most 1 s for open event streams, then closes them. FastAPI serves the OpenAPI docs at `/docs`.

```sh
curl -s -X POST localhost:8000/api/runs -H 'content-type: application/json' \
  -d '{"model": "assignment", "tasks": 40, "seed": 1, "expose_search": true}'
curl -sN localhost:8000/api/runs/<id>/events
```

| Endpoint | What it does |
| --- | --- |
| `POST /api/runs` | Starts a run: `model` (`assignment` or `coverage`), `tasks`, `handlers`, `seed`, `expose_search`, `work_limit`. Returns 202 with the run. An invalid request, or one too big for the free licence, gets 422 before anything is built. With two runs already going, it returns 429. |
| `GET /api/runs/{id}` | The run: its instance, latest progress, the result once it ends, its start and end times, and whether its telemetry is exported |
| `GET /api/runs/{id}/events` | SSE: `progress` at most every 0.2 s, a final `progress`, then `done` with the status. A reconnecting client sends `Last-Event-ID` and gets only the events after it. The stream closes after `done`; a browser `EventSource` reconnects to a closed stream by itself, so a client should call `close()` when it receives `done`. |
| `POST /api/runs/{id}/cancel` | Asks the run to stop at the solver's next callback; the result is then `interrupted`, with the best schedule found so far. If the solve has already finished (or the run is computing an IIS), the result is unchanged. 409 if the run has already ended. |

A run that doesn't exist is a 404 on every endpoint, before any stream starts. A run ends with one of the four solver statuses (`optimal`, `limit reached`, `infeasible`, `interrupted`), or as `failed` with an error message if the solve stops any other way. With `OTEL_EXPORTER_OTLP_ENDPOINT` set, each run is exported like a CLI run, and its API id is its `run_id` in Grafana.

### Stopping early, warm starts, infeasibility, reproducibility

**Stopping early.** `--work-limit N` stops the solve after N work units and reports the best schedule so far with its bound and gap. "Limit reached" is a normal result, not an error. The limit is in work units, not seconds, because Gurobi documents work limits as deterministic and time limits as not:

```sh
uv run ground-ops solve --tasks 40 --seed 1 --expose-search --work-limit 0.5
```

```
Model 1: 40 tasks, 7 handlers, seed 1
status: limit reached  overtime: 30 min  bound: 17 min  gap: 43.33%
H0 shift 09:30-17:30: T13 10:19-10:34, T38 11:10-11:23, ...
```

This schedule is already optimal (30 minutes, as the full solve proves), but at this point the solver can only prove that nothing beats 17. With `--work-limit 0` the solve stops before the root relaxation, so there's a first schedule but no bound, and the gap is reported as undefined.

**Infeasibility.** `--handlers N` sets the number of handlers. The default is one more than the most tasks that overlap at any moment. With fewer than that overlap count, no schedule exists, and the command prints an IIS instead:

```sh
uv run ground-ops solve --tasks 10 --seed 1 --handlers 2
```

```
Model 1: 10 tasks, 2 handlers, seed 1
status: infeasible
these constraints can't all hold, though any one fewer can (there may be other conflicts too):
  cover[0]
  cover[1]
  cover[3]
  no_overlap[h0,t0,t1]
  ...
(cover[t]: task t needs one handler; no_overlap[hH,tA,tB]: handler H can't do both A and B)
```

Read: tasks 0, 1 and 3 overlap pairwise, and two handlers can't cover three overlapping tasks.

**Warm starts.** `solve_assignment(..., start=previous.solution)` passes a previous schedule to Gurobi as a MIP start (there's no CLI option for it). Measured over 20 seeds with one task delayed by 25 minutes, it brought **no consistent gain**: a median of 0.146 work units against 0.137 cold, less work on only 7 of 20 seeds, and on one seed 45.6 work units against 3.7. The start changes the search path, and on these instances nearly all the work is proving the bound, which a good first schedule doesn't help with. Details in [docs/experiments.md](docs/experiments.md#warm-start-against-cold-start-d8).

**Reproducibility.** Every solve pins `Threads=1` and `Seed=0`. Gurobi says it returns the same results for the same model and parameters on the same computer with the same Gurobi version ([Gurobi: determinism](https://support.gurobi.com/hc/en-us/articles/360031636051)); it doesn't promise the same search on another machine. A test solves the same instance twice and checks that the node count, iterations and work units are identical. Measured on five seeds, four threads explored a different number of nodes from one thread on four of them, reached the same optimum, and repeated exactly when run again ([docs/experiments.md](docs/experiments.md#one-thread-against-four-d7)).

### The UI

The UI is a React app in `ui/`, served by Vite at http://127.0.0.1:5173. Vite passes `/api` through to the API container. **New run** starts a Model 1 or Model 2 run. The **run page** shows the incumbent, bound, gap and node count live, with a chart of incumbent against bound and a Cancel button. When the run ends, the same page shows the result:

- Model 1: a timeline per handler with each task and the minutes of overtime marked.
- Model 2: people on duty against demand per half hour, with the roster.
- Infeasible: the conflicting rules in plain words and the tasks involved on one time axis.

Each run page links to the run in Grafana, filtered to its `run_id` and time window.

Solves started from the UI run on Linux in the API container, so their node counts and work units can differ from the ones in this README and in [docs/experiments.md](docs/experiments.md), which come from the CLI on macOS. The 40-task, seed 1 solve with the search exposed took 32,741 nodes in the container against 32,424 on the host, with the same optimum.

To check a UI change, install the UI's packages on the host (`cd ui && npm ci`, which also gives your editor the types) and run `npm run check` in `ui/`. It checks that the generated API types are current, then runs `tsc` in strict mode, oxlint with type-aware rules, Prettier and Vitest. After an API change, `npm run types` regenerates `src/api.gen.ts` from the API's OpenAPI schema (`uv run ground-ops openapi`).

## Models

### Model 1: who does which task

Each task gets exactly one handler, no handler does two conflicting tasks, and total overtime is as small as possible. The terms are defined in [docs/domain.md](docs/domain.md).

- $T$: tasks, each with a start $s_t$ and end $e_t$ in minutes.
- $H$: handlers, each with a shift window.
- $o_{ht}$: minutes of task $t$ outside handler $h$'s shift window.
- $C$: pairs of tasks that conflict, because they're less than $g = 10$ minutes apart: $s_a < e_b + g$ and $s_b < e_a + g$.
- $x_{ht} \in \{0, 1\}$: 1 if handler $h$ does task $t$.

```math
\min \sum_{h \in H} \sum_{t \in T} o_{ht} \, x_{ht}
```

```math
\sum_{h \in H} x_{ht} = 1 \quad \forall t \in T \qquad \text{(cover)}
```

```math
x_{ha} + x_{hb} \le 1 \quad \forall h \in H,\ (a, b) \in C \qquad \text{(no overlap)}
```

In the code ([model1.py](src/ground_ops/model1.py)) the constraints are named like `cover[3]` and `no_overlap[h0,t1,t2]`. The objective is overtime, not travel time between consecutive tasks: travel needs variables for task order and exceeds the free licence at about 25 tasks ([design decision 2](docs/design-decisions.md#2-model-1-objective)).

### Model 2: how many people on each shift

Choose how many people to roster on each shift pattern so that every half hour has enough people on duty, at the lowest total paid time. It's a set-covering problem: a different shape from Model 1.

- $S$: half-hour slots of the day, each needing $d_s$ people.
- $P$: shift patterns (every 4-, 6- and 8-hour shift that fits the day; those of 6 hours or more have an unpaid half-hour break at the half-way slot).
- $a_{ps} = 1$ if pattern $p$ has someone on duty in slot $s$: inside the shift and not on the break.
- $c_p$: paid half-hours of pattern $p$.
- $y_p \in \{0, 1, 2, \dots\}$: people rostered on pattern $p$.

```math
\min \sum_{p \in P} c_p \, y_p
```

```math
\sum_{p \in P} a_{ps} \, y_p \ge d_s \quad \forall s \in S \qquad \text{(demand)}
```

In the code ([model2.py](src/ground_ops/model2.py)) the constraints are named like `demand[12]`.

### How the optima are tested

For both models, the tests check optima without trusting Gurobi: an independent feasibility checker, brute-force enumeration of every assignment or roster on small instances, and a hand-solved instance per model. The checker and the brute force reuse the models' rule functions (the 10-minute gap, overtime, which slots a pattern covers, paid length), so those functions have their own unit tests.

## The free Gurobi licence

The `gurobipy` package from PyPI includes a size-limited licence: **2,000 variables and 2,000 linear constraints** (200 variables if there are quadratic terms), "for research, development, and evaluation purposes only" ([Gurobi: size limits](https://support.gurobi.com/hc/en-us/articles/360051597492), [Gurobi: restricted licence](https://support.gurobi.com/hc/en-us/articles/29682074018833)). Every instance in this repo fits within it.

The bundled licence **expires per major version**. gurobipy 14.0.0 (released 2026-11-10, maintained by Gurobi Optimization) reports `expires 2028-11-29`. The repo pins `gurobipy~=14.0`; before that date, bump the pin to the next major version, which brings a new bundled licence.

## Reading the gap and the bound

For a minimisation problem, the incumbent only goes down and the bound only goes up. The **gap** is |incumbent − bound| / |incumbent|. Gurobi stops with "optimal" when the gap is below `MIPGap`, which defaults to 0.01% ([Gurobi parameters](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html)).

A stuck solve means different things depending on which number is stuck:

| What you see | What it means | Where to look |
| --- | --- | --- |
| **Incumbent won't improve** | The solver can't find better solutions | Heuristics, the warm start, or the problem is simply tight |
| **Bound won't move** | The solver can't prove the current answer is good | The formulation: a weak LP relaxation, symmetry. Usually a modelling question. |
| Both stuck, gap large | Both of the above | Try a smaller instance first |

One measured run shows the pattern; [docs/reading-the-log.md](docs/reading-the-log.md) walks through its full log. Model 1 with 40 tasks, seed 1 and `--expose-search`, one thread, on an Apple M4 Pro: a heuristic found the optimal schedule (30 minutes of overtime) at the root, in a fraction of a second. The bound then climbed from 0 to 23, 26, 27 and finally 30 over 32,424 nodes and 3.17 work units. **The answer was found almost at once. Nearly all the work went into proving it.**

With default settings the search is usually invisible. Across 20 seeds each, all 80 Model 1 instances (20, 30, 40 and 48 tasks) solved at the root node, and so did 18 of 20 Model 2 days; the other two needed at most 37 nodes. Presolve does most of the work: on the 40-task instance it removes 539 of 593 constraints, and the LP relaxation of what's left already gives the optimum. That's why the visible-search demos use `--expose-search`, which sets `Presolve=0` and `Cuts=0` ([design decision 4](docs/design-decisions.md#4-making-the-search-visible)). With it, Model 1 needs anywhere from 1 to 170,454 nodes at 48 tasks, while Model 2 stays easy (a median of 1 node).

## What it doesn't do

- **Model realistic operations.** There are no qualifications, breaks, teams, equipment or labour rules. The models stay textbook.
- **Scale beyond the free licence,** or make any performance claim beyond what's measured and stated.
- **Persist anything.** There's no database, job queue, authentication or multi-user state. Runs are lost on restart.
- **Support other solvers.** It's about Gurobi; there's no solver abstraction.
- **Deploy anywhere.** Docker Compose is for local development only. No production image, no Kubernetes, no CI/CD.
- **Use real data or names.** All instances are synthetic, with task durations based on a published turnaround dataset ([where the numbers come from](docs/domain.md)).

## Docs

Working on the repo? Start with [AGENTS.md](AGENTS.md) for the rules, then [docs/plan.md](docs/plan.md) for the build steps.

- [Plan](docs/plan.md): the build steps and what each step had to do to count as done.
- [Domain](docs/domain.md): the glossary, where the numbers come from, and what's simplified.
- [Reading a Gurobi log](docs/reading-the-log.md): two real logs from this repo, annotated line by line.
- [Experiments](docs/experiments.md): the measurements behind the numbers quoted here, with their scripts and machine.
- [Design decisions](docs/design-decisions.md): each choice, with alternatives, measurements and confidence.
- [Quality lenses](docs/quality-lenses.md): the checks every feature must pass.
- [Related work](docs/related-work.md): existing projects and papers, and where this repo differs.

## Licence

MIT. See [LICENSE](LICENSE).
