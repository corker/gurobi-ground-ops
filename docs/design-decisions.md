# Design decisions

Each topic below lists the alternatives, compares them, recommends one, and rates the confidence in that recommendation. Where confidence isn't high, it says what would raise it.

**Contributors:** you don't need to read this file end to end. [plan.md](plan.md) cites a decision number (D1 to D23) wherever one applies; read those sections only.

All measurements come from throwaway proof-of-concept scripts run on 2026-11-20. Those scripts aren't in the repo. The key numbers will be re-measured by reproducible scripts in `experiments/`, as listed in [plan.md](plan.md). Settings: Apple M4 Pro, macOS (Darwin 25.6), Python 3.12.12, gurobipy 14.0.0, ortools 9.15.6755, highspy 1.16.0, PuLP 4.3.1, opentelemetry-sdk 1.45.2, `Threads=1` unless stated. Every timing is from one machine, so it shows relative differences only. Work units are Gurobi's deterministic effort measure, so they compare cleanly across runs; wall-clock seconds don't.

**Confidence levels.** **High** (85% or more) means measured here, or confirmed by primary docs, with nothing contradicting it. **Medium** (60–85%) means one instance family, a secondary source, or a judgement call. **Low** (below 60%) means a plausible guess.

## Summary

| # | Area | Topic | Recommendation | Confidence |
| --- | --- | --- | --- | --- |
| 1 | Licence and models | gurobipy version and licence | Pin `gurobipy~=14.0`; document the free licence's 2028-11-29 expiry | High (90%) |
| 2 | Licence and models | Model 1 objective | Overtime: minutes worked outside each handler's shift window, as a per-assignment cost (decided) | High (90%) |
| 3 | Licence and models | Model 1 no-overlap constraints | Pairwise constraints in the package; the clique form as a documented experiment | High (85%) |
| 4 | Solver behaviour and tests | Making the search visible | Document that instances solve at the root; demos and early-stop tests use `Presolve=0, Cuts=0` | High (90%) |
| 5 | Solver behaviour and tests | Second solver backend | None: Gurobi only (decided) | High (95%) |
| 6 | Solver behaviour and tests | Telemetry metrics and instruments | Seven Gurobi callback metrics; observable gauges for active runs (D21) | High (85%) |
| 7 | Solver behaviour and tests | Early-stop test | `WorkLimit`, asserting a "limit reached, feasible" status and a non-zero gap | High (95%) |
| 8 | Solver behaviour and tests | Warm start | `Start` attribute; report work units across seeds; measured: no consistent gain | High (85%) |
| 9 | Solver behaviour and tests | Infeasibility diagnosis | Gurobi IIS with readable constraint names | High (90%) |
| 10 | Solver behaviour and tests | Golden tests | Assert the objective and feasibility, never a specific assignment | High (95%) |
| 11 | Licence and models | Instance realism | Base task durations on the turnaround dataset in related work | High (85%) |
| 12 | Licence and models | Domain glossary | `docs/domain.md` | High (90%) |
| 13 | Docs and experiments | Log walkthrough | `docs/reading-the-log.md`, built from a real log produced by this repo | High (85%) |
| 14 | Docs and experiments | Experiment journal | Scripts in `experiments/`, results in `docs/experiments.md` (decided) | High (90%) |
| 15 | Docs and experiments | Where the bound comes from | Teach it through decisions 3 and 4, with no extra code | High (85%) |
| 16 | Observability, API and UI | Observability stack | `grafana/otel-lgtm` in Docker Compose; OTLP over HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; no export otherwise | High (85%) |
| 17 | Observability, API and UI | API | FastAPI under `/api` on `127.0.0.1`; one Gurobi environment per run; cancel through `terminate()` | High (90%) |
| 18 | Observability, API and UI | Progress transport | SSE for progress; plain requests for everything else | High (85%) |
| 19 | Observability, API and UI | UI library | React with Vite and TypeScript | Medium (75%) |
| 20 | Observability, API and UI | UI serving and API types | Vite dev proxy while developing; FastAPI serves the built UI; types generated with openapi-typescript | High (85%) |
| 21 | Observability, API and UI | Run identity in telemetry | A `run_id` unique across processes, as a metric attribute on observable gauges for active runs only, with a raised cap | High (85%) |
| 22 | Observability, API and UI | TypeScript quality checks | `tsc` with `strict: true`, oxlint with type-aware rules, Prettier, Vitest; one `npm run check` | High (85%) |
| 23 | Licence and models | Data types | Frozen, strict Pydantic models everywhere, core and API (decided) | High (85%) |

## 1. gurobipy version and licence

**Finding.** The pip licence allows 2,000 variables and 2,000 linear constraints, or 200 variables if there are quadratic terms ([Gurobi: model too large](https://support.gurobi.com/hc/en-us/articles/360051597492), updated 2026-03-24). It also expires per major version. Version 13's licence expires on 2026-11-23, version 12's on 2025-11-24 ([Gurobi: licence expired 2026-11-23](https://support.gurobi.com/hc/en-us/articles/19487474933521)). gurobipy 14.0.0 (released 2026-11-10) printed `Restricted license - for non-production use only - expires 2028-11-29` here. Two more things were observed: a model over the limit fails at `optimize()` with `GurobiError: Model too large for size-limited license`, and `NumVars` reads 0 until `update()` is called.

| Option | Pros | Cons |
| --- | --- | --- |
| `gurobipy==14.0.0` | Fully fixed | Misses 14.0.x bug fixes |
| **`gurobipy~=14.0` plus `uv.lock`** | Bug fixes come in, the lockfile fixes the exact build, and the licence stays on version 14 | Needs a deliberate bump before 2028-11-29 |
| `gurobipy>=14` | Picks up new licences automatically | Can jump a major version and its API changes without anyone noticing |

**Recommendation.** `~=14.0` with `uv.lock`. The README states the expiry date. Tests and helpers call `update()` before reading model size.

**Confidence: High (90%).** The expiry and limits are measured and documented by Gurobi.

## 2. Model 1 objective

| Option | Fits "binary staff × task"? | Size at the free limit (measured) | Comment |
| --- | --- | --- | --- |
| **Overtime outside the shift window** (cost per handler–task pair) | Yes | T=35 tasks, H=12 handlers: 420 variables, 1,787 constraints | Textbook assignment with costs |
| Overtime as total load beyond regular hours (a continuous variable per handler) | Yes, plus H variables | Similar | Convex; the LP relaxation solved it exactly in every run |
| Travel between consecutive tasks (successor arcs) | No, needs arc variables | Over 2,000 variables already at T=25 (2,547), and 1,344 at T=20 | Close to vehicle routing |
| Distance from a handler's home stand (an assignment cost) | Yes | Same as the first option | Doesn't capture "between consecutive tasks", so it would misstate the plan |
| Minimise handlers used | Yes | Similar | Not a cost the plan names |

**Recommendation.** Overtime outside each handler's shift window. Record the choice and the reason in the README.

**Confidence: High (90%).** The sizes are measured, and the choice is decided. [Tian 2022](https://doi.org/10.1371/journal.pone.0279131) also supports it: tasks are assigned to shifts with start times and durations, and it notes that extending a shift by 30 minutes "is very common".

## 3. Model 1 no-overlap constraints

Measured with [`experiments/clique_no_overlap.py`](../experiments/clique_no_overlap.py) on 15 seeded instances of 20, 30 and 40 tasks ([experiments.md](experiments.md#pairwise-against-clique-no-overlap-d3-d15)). Two examples:

| Instance | Pairwise: constraints / LP bound | Clique per time point: constraints / LP bound | Optimum |
| --- | --- | --- | --- |
| T=30, seed 4, H=7 | 436 / 0 | 191 / 56 | 56 |
| T=40, seed 4, H=8 | 864 / 0 | 280 / 103 | 103 |

| Option | Pros | Cons |
| --- | --- | --- |
| **Pairwise:** x[h,a] + x[h,b] ≤ 1 for each conflicting pair | The obvious textbook form; works with any conflict rule, including travel-dependent ones | Weak LP bound; constraint count grows with the square of the overlaps |
| Clique per time point | LP bound equalled the optimum on all 15 instances; 32% to 70% as many constraints | Needs conflicts to form an interval graph, so no travel-dependent gaps; less obvious |
| Time-indexed slots | Uniform with Model 2 | Many more variables; rounds the times |

**Recommendation.** Pairwise in the package, because the plan asks for a textbook, obvious formulation. The clique form is a recorded experiment (decision 14). It is the clearest demonstration in this repo of the formulation affecting the bound.

**Confidence: High (85%).** The bounds are measured. The clique form's "LP equals optimum" result held on every instance tried, but wasn't proven in general.

## 4. Making the search visible

**Finding.** Every variant tried was solved at the root node in milliseconds under default settings. That covered both Model 1 objectives, both conflict rules, sizes up to the free limit, and Model 2 set covering with 593 patterns. Single changes (`Cuts=0`, `Presolve=0` or `Heuristics=0`) still solved at the root. `Cuts=0` and `Presolve=0` together on Model 1 (T=30) took 31,675 nodes and 4.99 work units.

| Option | Pros | Cons |
| --- | --- | --- |
| **Document it; use `Presolve=0, Cuts=0` for demos and early-stop tests** | Honest. It also teaches what presolve and cuts contribute. | The settings are artificial |
| Harder model features (tight per-handler capacity) | Natural difficulty | Most generated instances were infeasible; the feasible ones still solved at the root |
| Bigger instances | Natural | Ruled out by the free licence |

**Recommendation.** The first option. Say in the README that textbook instances at free-licence sizes are easy for Gurobi 14, and that the curves shown come from switching presolve and cuts off.

**Re-measured in Step 4 with the repo's own generators** (the numbers above came from proof-of-concept variants): across 20 seeds each, all 80 Model 1 instances of 20 to 48 tasks solved at the root, and 18 of 20 Model 2 days did (at most 37 nodes otherwise). With `Presolve=0, Cuts=0`, Model 1 at 48 tasks needed 1 to 170,454 nodes, but Model 2 stayed easy (median 1 node), so the visible-search demos use Model 1. Gurobi 14 still reports a few cuts in the log with `Cuts=0`; the cause is unverified (see [reading-the-log.md](reading-the-log.md)).

**Confidence: High (90%).** A follow-up sweep under default settings ran Model 1 at T=20, 30 and 35 and Model 2 at 32 and 48 slots, with 20 seeds each. All 99 instances within the limit solved at the root node, and one T=35 instance exceeded the limit. The remaining doubt is model variants not yet tried.

## 5. Second solver backend

**Decided: none. The repo uses Gurobi only.**

The original requirements asked for a second, open-source backend so that the repo would run without a Gurobi licence. Two findings removed that need: the pip `gurobipy` package bundles a free licence that covers every instance here (D1), and the owner's interest is Gurobi specifically. When the bundled licence nears expiry (2028-11-29 for version 14), bumping the pin to the next major version renews it.

Before the decision, the candidates were measured on the same Model 1 instance. The data is kept here in case the question comes back:

| Candidate | Live progress | Deterministic | IIS for a MIP | Licence | Latest release |
| --- | --- | --- | --- | --- | --- |
| HiGHS (`highspy`) | Primal and dual bound, gap, nodes, simplex iterations, running time | Yes: 351 nodes, 11,141 iterations on two runs (presolve off, heuristic effort 0) | No: "can only be used for LPs" ([HiGHS docs](https://ergo-code.github.io/HiGHS/dev/guide/advanced/)) | MIT | 1.16.0, 2026-11-11 |
| CP-SAT (OR-Tools) | Incumbent, bound, wall time, branches; no nodes or simplex iterations | Yes with one worker and a fixed seed | No | Apache-2.0 | 9.15.6755, 2026-01-14 |
| PuLP | Passes callbacks through to HiGHS; none found for CBC | As its solver | No | MIT | 4.3.1, 2026-11-19 |

A spike (a throwaway proof of concept) ran Model 1 on Gurobi and HiGHS behind one `Protocol` and passed the same feasibility checks on both, with objective 55 on each.

**What this removes:** the backend `Protocol`, capability flags such as "IIS unavailable", a second effort-limit mapping, and a backend choice in the API and UI.

**Confidence: High (95%).** It's a scope decision, and the facts it rests on are measured.

## 6. Telemetry metrics and instruments

| Metric | Gurobi callback source |
| --- | --- |
| Incumbent (best objective) | `MIP_OBJBST` |
| Best bound | `MIP_OBJBND` |
| Gap | Computed from incumbent and bound |
| Incumbent improvements | Computed in `MIPSOL` |
| Nodes | `MIP_NODCNT` |
| Simplex iterations | `MIP_ITRCNT` |
| Elapsed time and effort | `RUNTIME`, `WORK` |

Gurobi codes are from the [callback codes reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html). Gurobi notes that `MIPSOL_OBJ` is "not necessarily better than the current incumbent" and that `MIP_SOLCNT` counts solutions presented, not improvements. So the improvement count must be computed by comparing values.

Instruments, measured with `InMemoryMetricReader` on SDK 1.45.2: a synchronous gauge (`create_gauge`) for gap, incumbent, bound, nodes and iterations, and a counter for improvements. Both export correctly. Those two measurements came from the proof of concept. Re-measured in Step 4 on the real callback ([experiments.md](experiments.md)): Model 1 with 40 tasks and the search exposed took identical work units and node counts in every run with and without it, and the median wall-clock difference was smaller than this machine's run-to-run noise. The last callback sample did **not** always match the final attributes, so the recorder takes its final sample from `ObjVal`, `ObjBound`, `NodeCount` and `IterCount` after the solve. Names: OpenTelemetry's registry has no `solver` namespace, and its rules ask for lowercase, dot-separated, namespaced names with UCUM units ([naming](https://opentelemetry.io/docs/specs/semconv/general/naming/)).

**Recommendation.** All seven metrics above. The callback records the latest values at every MIP callback, the exporter sends them once a second, and observable gauges report them for active runs only (D21 explains why not synchronous gauges). A project prefix, for example `groundops.solver.gap`, avoids a future clash.

**Confidence: High (85%).** Measured.

## 7. Early-stop test

| Option | Deterministic? | Measured |
| --- | --- | --- |
| `TimeLimit` | No: Gurobi says wall-clock limits can vary with machine load ([determinism](https://support.gurobi.com/hc/en-us/articles/360031636051)) | Not used |
| **`WorkLimit`** | Yes | `WorkLimit=0.05`: status 16 (`WORK_LIMIT`), feasible, objective 55, bound 15, gap 0.727. `WorkLimit=0.2`: bound 35, gap 0.364. |
| `NodeLimit` or `SolutionLimit` | Yes | Not tested. These stop on counts rather than effort. |

Reproducibility, measured: the same seed and thread count gave identical nodes (31,675), work (4.9858) and iterations (206,354) on two runs. With 4 threads instead of 1, the same model took 81,639 nodes and reached the same optimum.

Re-measured by [`experiments/threads.py`](../experiments/threads.py) on five 40-task instances with the search exposed (results in [experiments.md](experiments.md#one-thread-against-four-d7)): four threads explored a different number of nodes from one thread on four of the five, reached the same optimum on all five, and every run repeated exactly. Gurobi's [WorkLimit reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html) says work limits are deterministic, and its [determinism article](https://support.gurobi.com/hc/en-us/articles/360031636051) says the same model and parameters give the same results on the same computer and Gurobi version, with multiple threads too. Neither says results depend on the thread count; that part is measured, not documented.

**Recommendation.** `WorkLimit`, already in `AGENTS.md`. Built in Step 6: a solve stopped by `WorkLimit` (status 16, `WORK_LIMIT`) returns "limit reached" with its best solution, bound and gap; a bound or gap Gurobi reports as infinite (no bound yet) becomes "none".

**Confidence: High (95%).**

## 8. Warm start

Measured: three different tasks each moved separately by 25 minutes, with 3 seeds each and `Presolve=0, Cuts=0`, giving 9 runs per mode.

| Mode | Work, median (min–max) | With `Heuristics=0` as well |
| --- | --- | --- |
| Cold | 4.76 (3.28–6.37) | 3.62 (2.45–5.10) |
| **`Start` (previous solution)** | 4.52 (3.47–6.77) | 3.77 (2.43–4.09) |
| `VarHintVal` (hints) | 4.56 (3.42–5.79) | 3.59 (2.49–3.93) |

The differences are within the spread between seeds. On these instances the incumbent appears almost immediately, and nearly all the work goes into proving the bound, which a warm start can't speed up.

A partial `Start`, which leaves the moved task's variables undefined, gave a median of 4.35 (3.28–5.53) on the same 9 runs, also within the spread. Fixing the unaffected assignments wasn't measured, because it changes the problem being solved.

**Recommendation.** Use `Start` (Gurobi's [variable attribute](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/variable.html), which may be partial). Report the work-unit distribution across seeds, as lens 13 requires. State the result honestly, even if it's "no measurable gain", with the explanation above. It makes a good lesson on incumbent versus bound.

Re-measured by [`experiments/warm_start.py`](../experiments/warm_start.py) on 20 seeds of 40 tasks, one task delayed 25 minutes, search exposed ([results](experiments.md#warm-start-against-cold-start-d8)): median work 0.137 cold, 0.146 with the full previous schedule and 0.155 with a partial one. The full start needed less work on 7 of 20 seeds and the partial one on 12. On seed 4 both starts took 45.6 work units against 3.7 cold: the start changed the search path, and that path proved the bound far more slowly. Gurobi's [determinism article](https://support.gurobi.com/hc/en-us/articles/360031636051) lists a starting solution among the inputs that may change results. Why this path is slower is unverified.

**Confidence: High (85%)** that a warm start brings no consistent gain on this repo's instances: 20 seeds, two start variants, and the earlier 9-run measurement agree. Model 2 can't be used to check it: it solved at the root even with presolve, cuts and heuristics off, so there's nothing for a warm start to speed up.

## 9. Infeasibility diagnosis

Measured: Model 1 with 3 handlers (fewer than the peak overlap) is infeasible. Gurobi's `computeIIS` returned 22 of 324 constraints, with names such as `cover[0]` and `no_overlap[h0,t0,t3]`. `feasRelax` on the cover constraints alone ([Model API](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html)) gave a minimum total violation of 9.

| Option | What it reports | Available on |
| --- | --- | --- |
| **IIS** | Which constraints conflict | Gurobi |
| `feasRelax` | The cheapest way to violate constraints | Gurobi |
| Elastic cover (penalised slack variables in the model) | Which tasks can't be covered | Any solver |

**Recommendation.** An IIS on Gurobi, as the plan requires, with readable constraint names. `feasRelax` and an elastic cover are optional later additions.

Built in Step 6 for Model 1: an infeasible solve calls [`computeIIS`](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html) and returns the names of the constraints with [`IISConstr`](https://docs.gurobi.com/projects/optimizer/en/current/reference/attributes/constraintlinear.html) set. Gurobi says the IIS it returns "is not necessarily the smallest one"; every IIS computed here without a work limit reported `IISMinimal = 1`, and none included variable bounds (Gurobi's variable reference says binary bounds never do). All 200 infeasible solves in [`experiments/infeasible_status.py`](../experiments/infeasible_status.py) (five sizes, 20 seeds, with and without the search exposed) returned status 3, `INFEASIBLE`, never 4, `INF_OR_UNBD`. `computeIIS` obeys `WorkLimit` too, and a cut-short IIS is reported with `IISMinimal = 0` and more constraints than needed (111 instead of 45 on one instance), so the limit is lifted before the IIS is computed. Model 2 can only be infeasible when a slot has demand that no pattern covers, which the generated instances never have, so it reports infeasible without an IIS.

**Confidence: High (90%).**

## 10. Golden tests

Measured with [`experiments/tied_optima.py`](../experiments/tied_optima.py) ([experiments.md](experiments.md#tied-optimal-solutions-d10)): every 10-task instance tried has between 108 and at least 2,000 optimal schedules, confirmed by brute force where exact, and every 20- and 30-task instance has at least 2,000.

| Option | Robust? |
| --- | --- |
| Assert one exact assignment | No: any valid path can return a different optimum |
| **Assert the objective plus independent feasibility checks** | Yes |
| Add a tie-breaking secondary objective to make the solution unique | It changes the model just for tests |

**Recommendation.** Assert the objective plus feasibility, as `AGENTS.md` and lens 1 already require. Objectives are whole minutes, so compare them exactly.

**Confidence: High (95%).**

## 11. Instance realism

The [turnaround dataset](https://github.com/spadrona/airport_ground_handling_dataset) (file `FE.csv`, 65 turnarounds) gives durations in minutes: unloading baggage 7–24 (median 10), loading baggage 8–20 (median 13), and ground time 26–52 (median 28). The proof of concept used 20–60 minute tasks, which is longer than real baggage tasks.

| Option | Pros | Cons |
| --- | --- | --- |
| **Seeded generator with duration ranges taken from the dataset, citing it** | Plausible and reproducible, and it fits the limit (15–20 turnarounds × 2 baggage tasks = 30–40 tasks) | It simplifies: no precedence between tasks, no equipment |
| Load the dataset directly | Real data | 65 turnarounds × 10 operations is far over the limit; adds precedence and equipment |
| Uniform random durations | Simplest | Arbitrary |

**Recommendation.** The first option. List the simplifications in `docs/domain.md`.

**Confidence: High (85%).** [Tian 2022](https://doi.org/10.1371/journal.pone.0279131) (real instances from a ground-handling provider) corroborates the shape of the problem: hundreds of tasks a day assigned to shifts, task durations in tens of minutes (for example 30), and qualifications per task. It doesn't publish a full duration distribution, so the dataset remains the source for the numbers.

## 12. Domain glossary

| Option | Pros | Cons |
| --- | --- | --- |
| **`docs/domain.md`** | Fits the `docs/` convention; the instance generator and the realism lens can point to it | One more file |
| A README section | One place to read | Crowds the README's learning content |
| `CONTEXT.md` at the root | Used by some agent workflows | Not a convention this repo has adopted |

**Recommendation.** `docs/domain.md`: turnaround, task, stand, handler, shift window, overtime, shift pattern, demand slot, and what's simplified.

**Confidence: High (90%).** It's low-stakes and easy to change.

## 13. Log walkthrough

| Option | Pros | Cons |
| --- | --- | --- |
| **`docs/reading-the-log.md`, built from a real log produced by this repo** | Serves the repo's stated goal directly; reproducible | Must be regenerated if the model changes |
| Link to [Gurobi's MIP logging docs](https://docs.gurobi.com/projects/optimizer/en/current/concepts/logging/mip.html) only | No upkeep | Not tied to this repo's models |
| gurobi-logtools plots | Visual | Adds a dependency and a plotting stack |

**Recommendation.** The first option. Annotate the presolve summary, the root relaxation, the node table columns (`Expl`, `Unexpl`, `Obj`, `Depth`, `IntInf`, `Incumbent`, `BestBd`, `Gap`, `It/Node`, `Time`), the `H` lines that mark heuristic incumbents, and the final status. Use the decision 4 instance with presolve and cuts on and off.

**Confidence: High (85%).**

## 14. Experiment journal

| Option | Pros | Cons |
| --- | --- | --- |
| **Scripts in `experiments/`, results in `docs/experiments.md` with machine and settings** | Reproducible; satisfies the honesty rule | Two places to keep in sync |
| Results only, written by hand | Simplest | Can't be reproduced |
| `pytest-benchmark` | Built-in statistics | Mixes measurements with tests; wall-clock based |

**Recommendation.** The first option. The measurements in this doc are the first entries.

**Confidence: High (90%).** A top-level `experiments/` directory is decided. The flat-layout rule applies to the package, not to scripts.

## 15. Where the bound comes from

With only the cover constraints, Model 1's LP relaxation is integral: each task takes its cheapest handler. The pairwise no-overlap constraints are what open the gap: at T=30 their LP bound is below the optimum on all four seeds with a non-zero optimum, for example 0 against 56 ([experiments.md](experiments.md#pairwise-against-clique-no-overlap-d3-d15)). The clique form (decision 3) closed that gap completely on every instance tried, and decision 4 shows presolve and cuts closing it inside the solver.

**Recommendation.** Teach it through the log walkthrough and the experiment journal. No extra code is needed.

**Confidence: High (85%).**

## 16. Observability stack

Measured on 2026-11-20 with `grafana/otel-lgtm:0.41.1` and opentelemetry-sdk 1.45.2: callback metrics exported over OTLP/HTTP to port 4318 arrived in Prometheus, and Grafana's Prometheus data source returned them. The image bundles an OpenTelemetry Collector, Prometheus, Tempo, Loki, Pyroscope and Grafana, and is "intended for development, demo, and testing environments" ([LGTM README](https://github.com/grafana/docker-otel-lgtm)).

Observed details that shape the design:

- With `OTEL_EXPORTER_OTLP_ENDPOINT` unset, the SDK's HTTP exporter still defaults to `http://localhost:4318/v1/metrics`. So with the variable unset, the repo must not create an exporter at all. The original requirements asked for a plain-stdout fallback; it was dropped, because tests use an in-memory reader and the SSE stream and the Gurobi log cover watching a solve without a collector.
- Prometheus renames metrics: dots become underscores and the unit becomes a suffix. `groundops.solver.gap` with unit `1` is queried as `groundops_solver_gap_ratio`, and unit `min` adds `_minutes`.
- Grafana is coarse for short solves. With a 500 ms export interval, the first half-second of a 3.7-second solve (bound 0 and 15) never reached Prometheus. At 1-second query resolution the bound showed 35 then 55. The SSE stream (D18) is the fine-grained view; Grafana is the overview.

| Option | Pros | Cons |
| --- | --- | --- |
| **`grafana/otel-lgtm`, one container** | Metrics, traces, logs and dashboards with one `docker compose up` | Not for production (by its own README); Prometheus is coarse for sub-second detail |
| Separate collector, Prometheus, Tempo, Loki and Grafana containers | Closer to a real deployment | Five services to configure for a local learning tool |
| No stack; stdout only | Nothing to run | No dashboards, which the plan requires |

**Recommendation.** One `grafana/otel-lgtm` service in `compose.yaml`, with the dashboard provisioned as JSON. The app runs on the host, not in a container.

Measured in Step 5 against `grafana/otel-lgtm:0.41.1`:

- **Metric names:** Prometheus adds a unit suffix only for real units (`1` gives `_ratio`, `s` gives `_seconds`); a `{…}` annotation adds none, so `groundops.solver.bound` is `groundops_solver_bound`.
- **Curve:** with a 1-second export interval, a 2.6-second solve arrived as bound 23, 26, 30. The first second of the solve isn't sampled.
- **Traces:** one trace per run, root span `ground-ops run` with `generate instance`, `build model` and `solve` children. Fetching by trace id works at once; Tempo's search found a new trace only after tens of seconds.
- **Logs:** Gurobi delivers every log line to the `MESSAGE` callback even with `OutputFlag=0`. The lines reach Loki with `run_id` and the run's trace id, so a line links to its trace. The OpenTelemetry Python logs SDK is in [Development status](https://opentelemetry.io/docs/languages/python/) (traces and metrics are stable), so its exact version is locked in `uv.lock` (the `~=1.45` specifier alone would allow later 1.x releases).
- **Dashboard provisioning:** mount the dashboards *directory*, not single files. A single-file bind mount keeps the original file, so an editor that saves by replacing the file leaves Grafana showing the old version.

**Confidence: High (85%).** The opt-in integration tests (`uv run pytest -m integration`) check, against a real container: the run's final bound in Prometheus under its translated name, Gurobi log lines in Loki, the trace in Tempo with all four span names, and the provisioned dashboard. The in-memory tests check that log records carry the run's trace id. Observed once by hand, not automated: the exact curve values, Loki's side of the log-to-trace link, and the stale single-file mount.

## 17. API

Measured with the free licence: two solves in parallel threads, each with its own environment, both completed (3.9 s each, 3.96 s wall clock). `terminate()` called from another thread after 0.5 s ended the solve with status `INTERRUPTED`, keeping the incumbent and a gap of 0.364. Gurobi's documented rule ([race conditions article](https://support.gurobi.com/hc/en-us/articles/40912136522129)) is that creating and freeing environments isn't thread-safe; using one environment per thread is. `terminate()` "can be called at any time during an optimization (from a callback, from another thread…)" ([Model API](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html)).

Two bugs found in the spike, which become rules:

- `model.copy()` before `update()` copied an empty model, so the solve "finished" instantly with objective 0. (`AGENTS.md` now requires `update()` first.)
- A streaming endpoint returned `200 text/event-stream` for a run that didn't exist, because the response starts before the generator body runs. The existence check must happen before streaming starts.

| Option | Pros | Cons |
| --- | --- | --- |
| **FastAPI 0.165.0 (MIT)** | Native SSE since 0.135.0; OpenAPI schema for type generation; `TestClient` | One more dependency |
| Starlette directly | Smaller | Hand-written SSE and no generated schema |
| No API; CLI only | Simplest | No cancel from the UI; no live progress |

**Recommendation.** FastAPI under `/api`, bound to `127.0.0.1`, no auth. Endpoints: `POST /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/events`, `POST /api/runs/{id}/cancel`. Runs execute in a thread pool. Each run gets its own environment. Creating and freeing environments happens under one process-wide lock, because Gurobi documents both as not thread-safe and FastAPI runs sync handlers on pool threads. The spike created environments on the request thread without a lock, which is safe only while requests don't overlap. Two workers; when both are busy, `POST /api/runs` returns 429. Runs are kept in memory.

**Confidence: High (90%)**, measured in a spike and then built in Step 8. Tests run two solves at once, each to its own optimum, and check the 429 when both workers are busy. Cancelling sets a flag that the progress callback checks before calling `terminate()`, which Gurobi documents as callable "from a callback, from another thread", so the API never holds a model from another thread. A cancel only takes effect inside `optimize`: one that arrives after the solve has returned, or while the IIS is computed, leaves the result unchanged, and one after the run has ended returns 409. The lock covers creating, starting and freeing each environment. Gurobi's article doesn't say whether `env.start()` must be serialised, or whether freeing a model on its worker thread outside the lock is safe (its C example frees models in the worker thread); both are unverified. The existence check is a FastAPI dependency, which runs before the response starts; with the lookup moved inside the stream, the 404 test fails.

## 18. Progress transport

Measured against a running server: 20 progress events over 3.7 seconds for a full solve (throttled to one per 0.2 s), then `done: optimal`. By 0.21 s the incumbent had fallen from 405 to 55 (the optimum) and the bound had risen from 0 to 35; the bound reached 55 at 3.68 s. A cancelled run sent 7 events, then `done: interrupted`. Through Vite's dev proxy the events still arrived spread over 3.7 seconds (21 events), so the proxy doesn't buffer them. A pytest `TestClient` test that reads the stream until `done` passes. FastAPI's SSE support is documented at [Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/).

| Option | Pros | Cons |
| --- | --- | --- |
| Polling | Simplest server | Up to one interval stale; timer code in the UI |
| **SSE** | Server push; browser `EventSource` reconnects automatically; `Last-Event-ID` for resuming | `EventSource` only does GET, so cancel stays a separate POST |
| WebSockets | Two-way | More than needed; reconnection is hand-written |

**Recommendation.** SSE for progress. The solver thread appends samples and wakes the stream through a `threading.Condition`. On reconnect, resume from `Last-Event-ID`. Built in Step 8 with FastAPI's native SSE (`EventSourceResponse`, added in 0.135.0); a test checks that a client resuming from an event id gets exactly the events after it.

**Confidence: High (85%).**

## 19. UI library

Measured by building the same Run view in both libraries: it polls a mocked API, shows gap, incumbent and bound, has a Cancel button and an SVG chart, and has the same two behaviour tests.

| Measured | React 19.3.1 | Vue 3.5.46 |
| --- | --- | --- |
| Component code | 57 lines | 62 lines |
| Behaviour tests | 28 lines, 2 of 2 pass | 32 lines, 2 of 2 pass |
| Type error in markup caught at build | Yes | Yes, including in templates |
| TypeScript in the Vite template | 7.0.2 | 6.0.3 (pinned for `vue-tsc`) |
| Installed packages, total / runtime | 114 / 6 | 222 / 27 |
| Production bundle, gzipped | 69 kB | 26 kB |

Svelte, Solid and Preact were compared on adoption only: npm weekly downloads of 10M, 13M and 63M, against React's 275M and Vue's 27M.

**Recommendation.** React with Vite 8 and TypeScript. The code is equally clear in both. React wins on a smaller dependency tree, current TypeScript, and how reliably AI agents generate it. Vue's smaller bundle doesn't matter for a local app. The Vite React template ships oxlint and strict TypeScript, and the spike's tests used Vitest with Testing Library; `AGENTS.md` adopts those.

**Confidence: Medium (75%).** This is close to a matter of taste. **To raise it:** nothing more to measure. Revisit only if the UI grows well beyond three pages.

## 20. UI serving and API types

Measured: FastAPI served the built UI. A catch-all route returning `index.html` let a client-side route like `/runs/7` load the app instead of returning 404, and the API under `/api` didn't collide with it. Vite's dev server listened on `localhost` by default, and a client connecting to `127.0.0.1:5173` was refused; started with `--host 127.0.0.1`, it worked. The proxy target `http://127.0.0.1:8765` reached the API either way. Why `localhost` didn't answer on `127.0.0.1` wasn't investigated. With typed SSE models, openapi-typescript 7.13.0 generated a `Progress` type, but typed the stream response itself as `unknown`.

| Option | Pros | Cons |
| --- | --- | --- |
| **Vite dev server and proxy while developing; FastAPI serves `ui/dist` for a single-command run** | Fast UI iteration, plus one process to run | The build output must exist before `serve` |
| Vite dev server only | Simplest | Two processes every time |
| FastAPI only | One process | No hot reload while developing |

**Recommendation.** The first option. The build output stays out of git. TypeScript types come from the OpenAPI schema; the SSE payload type is wired to the stream in one place in the UI.

Built in Step 9. The events endpoint is annotated `Iterator[Progress | Finished]`, which makes FastAPI 0.165.0 document both payload types under the stream's `itemSchema` while still sending the `ServerSentEvent` wrappers it yields (a `cast` tells mypy). openapi-typescript 7.13.0 then generates `Progress` and `Finished`; `ui/src/api.ts` links each event name to its type, the one hand-written link. Two findings: openapi-typescript declares TypeScript `^5.x` as a peer, and with the template's TypeScript 7.0.2 it fails at startup, because TypeScript 7 has no JavaScript compiler API (`ts.factory` is undefined), so the UI uses TypeScript 5.9.3. And by default openapi-typescript treats any field with a default as required, which made the optional request fields required; `--default-non-nullable false` fixes it. A run started from the built UI against the real API, driven in Chrome by a one-off Playwright script (not kept in the repo), reached every page: optimal, limit reached, infeasible and a Model 2 roster; a 40-task run with the search exposed showed live progress and, cancelled from its page, ended as `interrupted`; loading a run's page by its URL worked. The run page's Grafana link was checked in Chrome against the Grafana in `grafana/otel-lgtm:0.41.1`: `/d/ground-ops-solver` without the slug redirected to the slugged URL, `from` and `to` in epoch milliseconds were applied as the time range, and `var-run_id` selected the run. Grafana's docs state the `var-` prefix and that `from` and `to` take "ms, epoch, or relative time" ([URL variables](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/create-dashboard-url-variables/)); the slug-less form isn't documented there, only observed.

**Confidence: High (85%).** Measured end to end. The TypeScript 5 pin lasts until openapi-typescript supports TypeScript 7.

## 21. Run identity in telemetry

Measured with opentelemetry-sdk 1.45.2's in-memory reader, plus one run against LGTM:

| # | Option | Result | Verdict |
| --- | --- | --- | --- |
| 1 | No run label on metrics; `run_id` on traces only | Two concurrent runs overwrote each other on one series | Reject |
| 2 | `run_id` on a synchronous gauge | Finished runs kept exporting their last value forever; after 2,000 runs the SDK's default cap (`_DEFAULT_CARDINALITY_LIMIT = 2000`) folded new data into an `otel.metric.overflow` series | Reject |
| 3 | **`run_id` on an observable gauge reporting active runs only, cap raised with `View(aggregation_cardinality_limit=…)`** | Finished runs dropped out at the next collection; 5,000 runs, no overflow; concurrent runs on separate series | **Recommended** |
| 4 | Worker-slot label, with a time-window link per run | Bounded series, no overflow, but between runs Prometheus still returned the previous run's last value, so a run's window could start with its predecessor's data | Second choice |
| 5 | Exemplars linking metric points to traces | Not tested; needs exemplar storage enabled | Too complex for now |
| 6 | Progress as structured logs in Loki | Not tested; plotting needs LogQL `unwrap` | Too complex for now |

Even with an observable gauge, the default cap still overflowed after 2,000 runs, because the SDK keeps every attribute set it has seen. That's why option 3 needs the raised cap.

Measured in Step 4 with the real `Telemetry` class: the wildcard view `groundops.solver.*` does lift the cap (2,100 runs in one process, no overflow). The cost of keeping every attribute set is that each run's final flush walks all of them. Median flush time over 50 runs, Apple M4 Pro, two separate runs ([experiments.md](experiments.md)): 0.1 to 0.2 ms around run 100, 2.5 to 6.1 ms around run 2,000, and 13 to 16 ms around run 4,000. That's fine for a local tool, but a process serving many thousands of runs would want to be restarted.

**Recommendation.** Option 3. The run ID is the process start time plus a counter (for example `1795203617-3`), so it stays unique when each CLI run is its own process. A plain counter would restart at 1 in every process and put every CLI run on the same series. Grafana filters on `run_id`. Lens 12 states the rule: one ID per run, unique across processes, on active-only instruments, with an explicit cap.

**Confidence: High (85%).** Measured. The open question is Prometheus with many short-lived series over long periods, which doesn't affect a local tool.

## 22. TypeScript quality checks

The UI needs the same kind of enforced check as the Python side (`ruff`, `mypy --strict`, `pytest`). Measured on the throwaway React app from D19: the Vite `react-ts` template's `tsconfig.app.json` sets `noUnusedLocals`, `noUnusedParameters` and `noFallthroughCasesInSwitch`, but **not** `strict`. With `"strict": true` added, the app still compiled, and `tsc` caught a planted implicit-`any` parameter (`TS7006`) and a type mismatch (`TS2322`). The template ships oxlint with its React and TypeScript plugins; on the planted file oxlint reported nothing, which wasn't investigated. Prettier flagged 7 unformatted files, as expected for code written without a formatter.

| Concern | Options (version, 2026-11-20) | Choice |
| --- | --- | --- |
| Type checking | `tsc` | `strict: true` added to the template's settings |
| Linting | oxlint 1.94.0 (template default); ESLint 10.15.0 with typescript-eslint 8.73.0; Biome 2.6.8 | oxlint |
| Formatting | Prettier 3.10.1; oxfmt 0.79.0 (pre-1.0); Biome 2.6.8 | Prettier |
| Tests and coverage | Vitest 5.1.1 with Testing Library; `@vitest/coverage-v8` 5.1.1 | Vitest; coverage as a report, not a gate |

**Recommendation.** One command, `npm run check` (`types:check`, then `tsc -b`, `oxlint --type-aware`, `prettier --check .` and `vitest run`), which must pass before a UI change is done, like the Python check.

Measured once in Step 9 (2026-11-21, Apple M4 Pro, Node 25.1.0), on a scratch copy of the real UI with one file of six planted bugs. ESLint and its plugins were installed only in that copy, so this table isn't reproducible from the repo:

| Planted bug | oxlint 1.94.0, template config | oxlint `--type-aware` (oxlint-tsgolint 7.0.2007), six rules enabled | ESLint 10.15.0, typescript-eslint 8.73.0 `recommendedTypeChecked`, react-hooks 7.1.1 |
| --- | --- | --- | --- |
| Hook called conditionally | Yes | Yes | Yes |
| Missing effect dependency | Yes | Yes | Yes |
| Floating promise | No | Yes | Yes |
| `await` of a non-promise | No | Yes | Yes |
| Async function passed as `onClick` | No | Yes | Yes |
| Unchecked `any` | No | Yes | Yes |

On the real UI code, ESLint and the configured oxlint found the same two real bugs (an async `onSubmit` handler, and the stream's `done` callback returning a promise), both fixed; ESLint also flagged one async test helper without `await`. The template's oxlint has the type-aware rules but doesn't enable them, which is why it reported nothing on the D19 planted file.

**Recommendation, revised.** oxlint only, run as `oxlint --type-aware` with `no-floating-promises`, `await-thenable`, `no-misused-promises`, `no-unsafe-assignment`, `no-unsafe-member-access` and `no-explicit-any` enabled. It matched ESLint on every planted bug, so a second linter adds nothing measured.

**Confidence: High (85%).** Measured on six kinds of bug and the real code.

## 23. Data types

Measured on 2026-11-20 (Apple M4 Pro, Python 3.12.12, Pydantic 2.14.4, best of five runs of 200,000 constructions): a frozen stdlib dataclass with `Progress`'s fields took 0.44 µs to build, a frozen Pydantic model 0.53 µs. The 40-task exposed solve records 32,447 progress samples, so the difference is about 3 ms of a solve of about 3 s. Pydantic is already installed for every user, because FastAPI depends on it.

| Option | One way to declare types? | Notes |
| --- | --- | --- |
| Dataclasses in the core, Pydantic in the API | No | Smallest code; one mirror type (`ProgressView`) because Pydantic doesn't serialise a dataclass property |
| Dataclasses everywhere | Yes | FastAPI accepts dataclasses as request bodies and responses ([Using Dataclasses](https://fastapi.tiangolo.com/advanced/dataclasses/)), but warns they "can't do everything Pydantic models can do" |
| **Pydantic everywhere** | Yes | `gap` becomes a computed field, so the mirror type goes away and the OpenAPI schema carries it; values from Gurobi's callbacks, which gurobipy types as `Any`, are checked at runtime |

Measured with Pydantic 2.14.4: in its default (lax) mode, `Task(id="3", start="360", end=400.0)` is silently converted, so the repo's models are **strict** (`ConfigDict(frozen=True, strict=True)`): a string for an int, a float for an int or a bool for an int is refused, while an int is accepted for a float. Neither mode checks domain rules: `Task(id=0, start=400, end=360)` is accepted. `model_copy(update=...)` doesn't validate, so a copy is used only for trusted updates. mypy reports `prop-decorator` for `@computed_field` on a property, so that line carries a targeted ignore. `BaseModel` takes keyword arguments only, so all 77 constructor calls were rewritten.

**Recommendation.** Pydantic everywhere, with one shared strict, frozen config (decided by the owner). After the change the full check passed unchanged (161 tests), and the 40-task exposed solve still took 32,424 nodes and 3.170548 work units.

**Confidence: High (85%)** that it works as described: measured and tested here. The trade-off against dataclasses was close; the choice ties the core's types to Pydantic's major versions.

## Know about, don't build

- **Branch-and-price and column generation:** used by Tian 2022 and Dall'Olio 2023.
- **Gurobi's tuning tool.**
- **OR-Tools MathOpt:** floating-point coefficients over several solvers, per the CP-SAT Primer. Its callbacks weren't tested.
