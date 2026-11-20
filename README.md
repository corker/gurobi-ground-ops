# Learning Gurobi on ground-operations problems

I'm a backend/platform engineer picking up Gurobi — I'm not an optimisation modeller. The models here are small and textbook, chosen because airport ground operations has the clearest real-world assignment and covering problems. The part I care about is what surrounds the solve: telemetry, deterministic tests, time limits, warm starts, infeasibility diagnosis.

> **Status: Steps 1 to 4 of 9 done:** project setup, both models with their CLI commands, and solver telemetry. Everything else below is planned. [docs/plan.md](docs/plan.md) says what gets built, in what order, and when each step counts as done. Sections lose their "planned" label as each step lands.

## What it does (planned)

At an airport, ground staff unload and load baggage between flights. Each task has a fixed start time, so someone has to decide **who does which task**, without anyone being in two places at once. Everyone has a shift, and any work outside it is **overtime**, which costs money. The first model (**Model 1**, task assignment) finds the schedule with the least overtime. The second (**Model 2**, shift coverage) answers a simpler question: **how many people to roster on each shift pattern** so there are enough on duty in every half hour of the day.

You describe the rules ("every task gets exactly one person", "nobody does two overlapping tasks", "minimise overtime") and a **solver** searches for the best schedule. While it searches, it tracks two numbers:

- **The incumbent:** the best schedule found so far ("I have a plan with 55 minutes of overtime").
- **The bound:** how good any schedule *could* possibly be ("I can prove nothing beats 35 minutes").

The difference between them is the **gap**. When the gap closes, the solver has proven its plan is the best possible. Often it finds the best plan early and spends most of its time proving it. This repo is planned to let you watch that happen. The first two of these come from the API and UI (plan Steps 8 and 9):

- **Watch a solve:** gap, incumbent and bound update live, and you can cancel at any point and keep the best plan found so far.
- **Inspect the answer:** a timeline per person shows their tasks and highlights the overtime, so you can judge whether the schedule makes operational sense.
- **Diagnose infeasibility:** when no schedule is possible, it shows *which* tasks and people clash, instead of just failing.

## Terms used below

- **Warm start:** starting the solver from a known solution, such as the previous schedule, instead of from nothing.
- **IIS** (irreducible inconsistent subsystem): a smallest set of constraints that can't all hold at once. Remove any one of them and the rest can be satisfied, so it pinpoints why a problem is infeasible.
- **LP relaxation:** the same problem with the whole-number requirements dropped (allowing, say, half a person on a task). It's fast to solve, and its answer is where the bound comes from.
- **Presolve:** simplifications the solver makes before it starts searching.
- **Cuts:** extra constraints the solver adds to tighten the LP relaxation, which raises the bound.
- **Symmetry:** many equivalent solutions, such as two identical handlers swapped, which the solver may waste time exploring separately.
- **Root node:** the first step of the search, before any branching. "Solved at the root" means no search was needed.
- **Work units:** Gurobi's deterministic measure of effort. Unlike seconds, the same run always takes the same work.
- **OTLP:** OpenTelemetry's protocol for sending metrics, traces and logs to a collector.
- **SSE** (server-sent events): a standard way for a web server to push a stream of updates to a browser.

## How it fits together (planned)

```
  browser (React UI) ──HTTP/SSE──▶ FastAPI (/api, 127.0.0.1)
                                      │  one Gurobi environment per run
  CLI (ground-ops solve) ────────▶ core library
                                      ├─ instance generators (seeded)
                                      ├─ Model 1 and Model 2
                                      ├─ Gurobi solve
                                      └─ telemetry (solver callback)
                                            │ OTLP, only when a collector is configured
                                            ▼
                          docker compose: grafana/otel-lgtm
                          (Prometheus, Tempo, Loki, Grafana)
```

- **Core library (Python):** seeded instance generators, the two models, and the Gurobi solve. A solver callback emits the gap, incumbent, bound, incumbent improvements, node count, simplex iterations, elapsed time and work units.
- **Telemetry:** OpenTelemetry metrics, plus traces and logs. They go over OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; when it isn't, nothing is exported. Metric export has been tested in a spike; traces and logs haven't yet.
- **Observability stack:** one [`grafana/otel-lgtm`](https://github.com/grafana/docker-otel-lgtm) container in Docker Compose, with a provisioned dashboard. The image is intended for development, demo and testing.
- **API:** FastAPI on `127.0.0.1`. Start a run, stream its progress over server-sent events, cancel it, fetch the result. Runs live in memory.
- **UI:** React, Vite and TypeScript, in three pages: new run, live run, result.

The core library never imports the API or UI. `uv run pytest` needs no Docker, no Node and no browser; the UI has its own tests in `ui/`.

## How to run

You need [uv](https://docs.astral.sh/uv/). It installs the right Python (3.12) and all dependencies itself. No Gurobi licence file is needed: the `gurobipy` package brings its own free licence.

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

`--tasks` must be even (two baggage tasks per turnaround). H2 does T2 entirely after its shift ends. That's valid: the objective counts only minutes outside the shift, not how far outside, so H2 and H4 (also 9 minutes) tie. An objective that also penalised calling someone back in, or travel, would be a different model.

Up to 48 tasks fit the free licence for every seed tried (20 seeds per size); from 50 on, some seeds don't, and the command says so instead of solving.

Both commands take `--log FILE` to write Gurobi's log, and `--expose-search` to set `Presolve=0` and `Cuts=0` so the branch-and-bound search becomes visible.

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

### Telemetry

Set `OTEL_EXPORTER_OTLP_ENDPOINT` to an OpenTelemetry collector's OTLP/HTTP address and every solve exports its progress once a second while it runs (`OTEL_METRIC_EXPORT_INTERVAL` overrides that); leave it unset and nothing is exported. The command prints the run's `run_id` to stderr.

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

Each point carries `run_id` and `model` (`assignment` or `coverage`) attributes. Prometheus renames them on ingestion: dots become underscores and the unit becomes a suffix, so `groundops.solver.gap` is queried as `groundops_solver_gap_ratio`. A run's last values come from the model's final attributes rather than the last callback, which can fire before the final bound is known.

If the endpoint is set but nothing is listening, the run still completes, but the final export retries for several seconds before giving up; `OTEL_EXPORTER_OTLP_TIMEOUT` shortens that.

This section grows as each plan step lands.

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

In the code ([model1.py](src/ground_ops/model1.py)) the constraints are named like `cover[3]` and `no_overlap[h0,t1,t2]`. The objective is overtime rather than travel time between consecutive tasks, because travel needs variables for task order and exceeds the free licence at about 25 tasks ([design decision 2](docs/design-decisions.md#2-model-1-objective)).

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

For both models, the tests check optima without trusting Gurobi: an independent feasibility checker, brute-force enumeration of every assignment or roster on small instances, and a hand-solved instance per model. The checker and the brute force reuse the same rule functions as the models (the 10-minute gap, overtime, which slots a pattern covers, paid length), so those functions have their own unit tests.

## The free Gurobi licence

The `gurobipy` package from PyPI includes a size-limited licence: **2,000 variables and 2,000 linear constraints** (200 variables if there are quadratic terms), "for research, development, and evaluation purposes only" ([Gurobi: size limits](https://support.gurobi.com/hc/en-us/articles/360051597492), [Gurobi: restricted licence](https://support.gurobi.com/hc/en-us/articles/29682074018833)). Every instance in this repo will fit within it, so nothing will need a paid or academic licence.

The bundled licence **expires per major version**. gurobipy 14.0.0 (released 2026-11-10, maintained by Gurobi Optimization) reports `expires 2028-11-29`. The repo will pin `gurobipy~=14.0`, and the pin will need a bump to the next major version before that date, which brings a new bundled licence.

## Reading the gap and the bound

For a minimisation problem:

- The **incumbent** is the best solution found so far. It only ever goes down.
- The **bound** is a proven floor: no solution can be better. It only ever goes up.
- The **gap** is |incumbent − bound| / |incumbent|. Gurobi stops with "optimal" when the gap is below `MIPGap`, which defaults to 0.01% ([Gurobi parameters](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html)).

A stuck solve means different things depending on which number is stuck:

| What you see | What it means | Where to look |
| --- | --- | --- |
| **Incumbent won't improve** | The solver can't find better solutions | Heuristics, the warm start, or the problem is simply tight |
| **Bound won't move** | The solver can't prove the current answer is good | The formulation: a weak LP relaxation, symmetry. Usually a modelling question. |
| Both stuck, gap large | Both of the above | Try a smaller instance first |

One measured run shows the pattern; [docs/reading-the-log.md](docs/reading-the-log.md) walks through its full log. Model 1 with 40 tasks, seed 1 and `--expose-search`, one thread, on an Apple M4 Pro: a heuristic found the optimal schedule (30 minutes of overtime) at the root, in a fraction of a second. The bound then climbed from 0 to 23, 26, 27 and finally 30 over 32,424 nodes and 3.17 work units. **The answer was found almost at once. Nearly all the work went into proving it.**

With default settings the search is usually invisible. Across 20 seeds each, all 80 Model 1 instances (20, 30, 40 and 48 tasks) solved at the root node, and so did 18 of 20 Model 2 days; the other two needed at most 37 nodes. Presolve does most of the work: on the 40-task instance it removes 539 of 593 constraints, and the LP relaxation of what's left already gives the optimum. That's why the visible-search demos use `--expose-search`, which sets `Presolve=0` and `Cuts=0` ([design decision 4](docs/design-decisions.md#4-making-the-search-visible)). With it, Model 1 needs anywhere from 1 to 170,454 nodes at 48 tasks, while Model 2 stays easy (a median of 1 node).

## What it deliberately doesn't do

- **Model realistic operations.** There are no qualifications, breaks, teams, equipment or labour rules. The models stay textbook on purpose.
- **Scale beyond the free licence,** or make any performance claim beyond what's measured and stated.
- **Persist anything.** There's no database, job queue, authentication or multi-user state. Runs are lost on restart.
- **Support other solvers.** It's about Gurobi; there's no solver abstraction.
- **Deploy anywhere.** No Kubernetes, no CI/CD, and no container for the app itself.
- **Use real data or names.** All instances are synthetic, with task durations based on a published turnaround dataset.

## Docs

Working on the repo? Start with [AGENTS.md](AGENTS.md) for the rules, then [docs/plan.md](docs/plan.md) for what to build.

- [Plan](docs/plan.md): what gets built, step by step.
- [Domain](docs/domain.md): the glossary, where the numbers come from, and what's simplified.
- [Reading a Gurobi log](docs/reading-the-log.md): two real logs from this repo, annotated line by line.
- [Experiments](docs/experiments.md): the measurements behind the numbers quoted here, with their scripts and machine.
- [Design decisions](docs/design-decisions.md): each choice, with alternatives, measurements and confidence.
- [Quality lenses](docs/quality-lenses.md): the checks every feature must pass.
- [Related work](docs/related-work.md): existing projects and papers, and where this repo differs.

## Licence (MIT)

MIT. See [LICENSE](LICENSE).
