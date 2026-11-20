# Learning Gurobi on ground-operations problems

I'm a backend/platform engineer picking up Gurobi — I'm not an optimisation modeller. The models here are small and textbook, chosen because airport ground operations has the clearest real-world assignment and covering problems. The part I care about is what surrounds the solve: telemetry, deterministic tests, time limits, warm starts, infeasibility diagnosis.

> **Status: planning.** Nothing below is built yet. [docs/plan.md](docs/plan.md) says what gets built, in what order, and when each step counts as done. Sections lose their "planned" label as each step lands.

## What it does (planned)

At an airport, ground staff unload and load baggage between flights. Each task has a fixed start time, so someone has to decide **who does which task**, without anyone being in two places at once. Everyone has a shift, and any work outside it is **overtime**, which costs money. The first model finds the schedule with the least overtime. The second answers a simpler question: **how many people to roster on each shift pattern** so there are enough on duty in every half hour of the day.

You describe the rules ("every task gets exactly one person", "nobody does two overlapping tasks", "minimise overtime") and a **solver** searches for the best schedule. While it searches, it tracks two numbers:

- **The incumbent:** the best schedule found so far ("I have a plan with 55 minutes of overtime").
- **The bound:** how good any schedule *could* possibly be ("I can prove nothing beats 35 minutes").

The difference between them is the **gap**. When the gap closes, the solver has proven its plan is the best possible. Often it finds the best plan early and spends most of its time proving it. This repo is built to let you watch that happen:

- **Watch a solve:** gap, incumbent and bound update live, and you can cancel at any point and keep the best plan found so far.
- **Inspect the answer:** a timeline per person shows their tasks and highlights the overtime, so you can judge whether the schedule makes operational sense.
- **Diagnose infeasibility:** when no schedule is possible, it shows *which* tasks and people clash, instead of just failing.

## How it fits together (planned)

```
  browser (React UI) ──HTTP/SSE──▶ FastAPI (/api, 127.0.0.1)
                                      │  one Gurobi environment per run
  CLI (ground-ops solve) ────────▶ core library
                                      ├─ instance generators (seeded)
                                      ├─ Model 1 and Model 2
                                      ├─ Backend protocol: Gurobi | HiGHS
                                      └─ telemetry (solver callback)
                                            │ OTLP                │ no collector
                                            ▼                     ▼
                          docker compose: grafana/otel-lgtm     stdout
                          (Prometheus, Tempo, Loki, Grafana)
```

- **Core library (Python):** seeded instance generators, the two models, and one thin backend protocol with two implementations: Gurobi, and [HiGHS](https://github.com/ERGO-Code/HiGHS) as the open-source fallback. A solver callback emits the gap, incumbent, bound, incumbent improvements, node count, simplex iterations and elapsed time.
- **Telemetry:** OpenTelemetry metrics, plus traces and logs. They go over OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, and to stdout when it isn't. Metric export has been tested in a spike; traces and logs haven't yet.
- **Observability stack (optional):** one [`grafana/otel-lgtm`](https://github.com/grafana/docker-otel-lgtm) container in Docker Compose, with a provisioned dashboard. The image is intended for development, demo and testing.
- **API (optional):** FastAPI on `127.0.0.1`. Start a run, stream its progress over server-sent events, cancel it, fetch the result. Runs live in memory.
- **UI (optional):** React, Vite and TypeScript, in three pages: new run, live run, result.

The core never depends on the optional layers. `uv run pytest` needs no Docker, no Node and no browser.

## The free licence

The `gurobipy` package from PyPI includes a size-limited licence: **2,000 variables and 2,000 linear constraints** (200 variables if there are quadratic terms), "for research, development, and evaluation purposes only" ([Gurobi: size limits](https://support.gurobi.com/hc/en-us/articles/360051597492), [Gurobi: restricted licence](https://support.gurobi.com/hc/en-us/articles/29682074018833)). Every instance in this repo will fit within it, so nothing will need a paid or academic licence.

The bundled licence **expires per major version**. gurobipy 14.0.0 (released 2026-11-10, maintained by Gurobi Optimization) reports `expires 2028-11-29`. The repo will pin `gurobipy~=14.0`, and the pin will need a bump before that date. If the Gurobi licence is missing or expired, the same test suite is planned to run on HiGHS, apart from IIS, which HiGHS can't compute for a MIP.

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

One measured run shows the pattern. Model 1 with 30 tasks, presolve and cuts switched off so the search is visible, one thread, on an Apple M4 Pro: by 0.2 seconds the incumbent had fallen from 405 to 55, which turned out to be optimal, and the bound had risen from 0 to 35. Closing the rest of the gap, raising the bound from 35 to 55, took another 3.5 seconds. **The answer was found almost at once. Nearly all the time went into proving it.** With default settings, Gurobi 14 solved all 99 instances tried at the root node, in milliseconds (Model 1 with 20 to 35 tasks and Model 2 with 32 or 48 slots, 20 seeds each). That's why the visible-search demos switch presolve and cuts off ([design decision 4](docs/design-decisions.md)).

## What it deliberately doesn't do

- **Model realistic operations.** There are no qualifications, breaks, teams, equipment or labour rules. The models stay textbook on purpose.
- **Scale beyond the free licence,** or make any performance claim beyond what's measured and stated.
- **Persist anything.** There's no database, job queue, authentication or multi-user state. Runs are lost on restart.
- **Deploy anywhere.** No Kubernetes, no CI/CD, and no container for the app itself.
- **Use real data or names.** All instances are synthetic, with task durations based on a published turnaround dataset.

## Docs

- [Plan](docs/plan.md): what gets built, step by step.
- [Design decisions](docs/design-decisions.md): each choice, with alternatives, measurements and confidence.
- [Quality lenses](docs/quality-lenses.md): the checks every feature must pass.
- [Related work](docs/related-work.md): existing projects and papers, and where this repo differs.

## Licence

MIT. The licence file arrives with the project setup in Step 1.
