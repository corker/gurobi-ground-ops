# Design decisions

Each topic below lists the alternatives, compares them, recommends one, and rates the confidence in that recommendation. Where confidence isn't high, it says what would raise it.

All measurements come from throwaway proof-of-concept scripts run on 2026-11-20. Settings: Apple M4 Pro, macOS (Darwin 25.6), Python 3.12.12, gurobipy 14.0.0, ortools 9.15.6755, highspy 1.16.0, PuLP 4.3.1, opentelemetry-sdk 1.45.2, `Threads=1` unless stated. Every timing is from one machine, so it shows relative differences only. Work units are Gurobi's deterministic effort measure, so they compare cleanly across runs; wall-clock seconds don't.

**Confidence levels.** **High** (85% or more) means measured here, or confirmed by primary docs, with nothing contradicting it. **Medium** (60–85%) means one instance family, a secondary source, or a judgement call. **Low** (below 60%) means a plausible guess.

## Summary

| # | Topic | Recommendation | Confidence |
| --- | --- | --- | --- |
| 1 | gurobipy version and licence | Pin `gurobipy~=14.0`; document the free licence's 2028-11-29 expiry | High (90%) |
| 2 | Model 1 objective | Overtime: minutes worked outside each handler's shift window, as a per-assignment cost (accepted) | High (90%) |
| 3 | Model 1 no-overlap constraints | Pairwise constraints in the package; the clique form as a documented experiment | High (85%) |
| 4 | Making the search visible | Document that instances solve at the root; demos and early-stop tests use `Presolve=0, Cuts=0` | High (90%) |
| 5 | Fallback backend | HiGHS via `highspy` (accepted) | High (90%) |
| 6 | Telemetry metrics and instruments | A core set every backend reports, plus named optional fields; synchronous gauges and counters | High (85%) |
| 7 | Early-stop test | `WorkLimit`, asserting status `WORK_LIMIT` and a non-zero gap | High (95%) |
| 8 | Warm start | `Start` attribute; report work units across seeds; expect a small effect | Medium (80%) |
| 9 | Infeasibility diagnosis | Gurobi IIS; the fallback reports the capability as unavailable | High (90%) |
| 10 | Golden tests | Assert the objective and feasibility, never a specific assignment | High (95%) |
| 11 | Instance realism | Base task durations on the turnaround dataset in related work | High (85%) |
| 12 | Domain glossary | `docs/domain.md` | High (90%) |
| 13 | Log walkthrough | `docs/reading-the-log.md`, built from a real log produced by this repo | High (85%) |
| 14 | Experiment journal | Scripts in `experiments/`, results in `docs/experiments.md` (accepted) | High (90%) |
| 15 | Where the bound comes from | Teach it through decisions 3 and 4, with no extra code | High (85%) |

## 1. gurobipy version and licence

**Finding.** The pip licence allows 2,000 variables and 2,000 linear constraints, or 200 variables if there are quadratic terms ([Gurobi: model too large](https://support.gurobi.com/hc/en-us/articles/360051597492), updated 2026-03-24). It also expires per major version. Version 13's licence expired on 2026-11-23, version 12's on 2025-11-24 ([Gurobi: licence expired 2026-11-23](https://support.gurobi.com/hc/en-us/articles/19487474933521)). gurobipy 14.0.0 (released 2026-11-10) printed `Restricted license - for non-production use only - expires 2028-11-29` here. Two more things were observed: a model over the limit fails at `optimize()` with `GurobiError: Model too large for size-limited license`, and `NumVars` reads 0 until `update()` is called.

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
| Distance from a handler's home stand (an assignment cost) | Yes | Same as the first option | Doesn't capture "between consecutive tasks", so it would misstate the brief |
| Minimise handlers used | Yes | Similar | Not a cost the brief names |

**Recommendation.** Overtime outside each handler's shift window. Record the choice and the reason in the README.

**Confidence: High (90%).** The sizes are measured, and the recommendation was accepted. [Tian 2022](https://doi.org/10.1371/journal.pone.0279131) also supports it: tasks are assigned to shifts with start times and durations, and it notes that extending a shift by 30 minutes "is very common".

## 3. Model 1 no-overlap constraints

Measured on seeded instances with a uniform 10-minute gap between tasks:

| Instance | Pairwise: constraints / LP bound | Clique per time point: constraints / LP bound | Optimum |
| --- | --- | --- | --- |
| T=20, H=7 | 237 / 60 | 90 / 115 | 115 |
| T=30, H=11 | 987 / 143 | 195 / 236 | 236 |
| T=40, H=13 | 2,562, over the limit | 313 / 285 | 285 |

| Option | Pros | Cons |
| --- | --- | --- |
| **Pairwise:** x[h,a] + x[h,b] ≤ 1 for each conflicting pair | The obvious textbook form; works with any conflict rule, including travel-dependent ones | Weak LP bound; constraint count grows with the square of the overlaps |
| Clique per time point | LP bound equalled the optimum in every case; few constraints | Needs conflicts to form an interval graph, so no travel-dependent gaps; less obvious |
| Time-indexed slots | Uniform with Model 2 | Many more variables; rounds the times |

**Recommendation.** Pairwise in the package, because the brief says textbook and obvious. Run the clique form once as a recorded experiment (decision 14). It is the clearest demonstration in this repo of the formulation affecting the bound.

**Confidence: High (85%).** The bounds are measured. The clique form's "LP equals optimum" result held on every instance tried, but wasn't proven in general.

## 4. Making the search visible

**Finding.** Every variant tried was solved at the root node in milliseconds under default settings. That covered both Model 1 objectives, both conflict rules, sizes up to the free limit, and Model 2 set covering with 593 patterns. Single changes (`Cuts=0`, `Presolve=0` or `Heuristics=0`) still solved at the root. `Cuts=0` and `Presolve=0` together on Model 1 (T=30) took 31,675 nodes and 4.99 work units.

| Option | Pros | Cons |
| --- | --- | --- |
| **Document it; use `Presolve=0, Cuts=0` for demos and early-stop tests** | Honest. It also teaches what presolve and cuts contribute. | The settings are artificial |
| Harder model features (tight per-handler capacity) | Natural difficulty | Most generated instances were infeasible; the feasible ones still solved at the root |
| Bigger instances | Natural | Ruled out by the free licence |

**Recommendation.** The first option. Say in the README that textbook instances at free-licence sizes are easy for Gurobi 14, and that the curves shown come from switching presolve and cuts off.

**Confidence: High (90%).** A follow-up sweep under default settings ran Model 1 at T=20, 30 and 35 and Model 2 at 32 and 48 slots, with 20 seeds each. All 99 instances within the limit solved at the root node, and one T=35 instance exceeded the limit. The remaining doubt is model variants not yet tried.

## 5. Fallback backend

Measured on the same Model 1 instance:

| Option | Live progress available | Deterministic | IIS for a MIP | Licence | Latest release |
| --- | --- | --- | --- | --- | --- |
| **HiGHS (`highspy`)** | Primal and dual bound, gap, node count, simplex iterations, running time (fields of `HighsCallbackOutput` in highspy 1.16) | Yes: 351 nodes and 11,141 iterations on two runs, with presolve off and heuristic effort 0 | No: "can only be used for LPs" ([HiGHS docs](https://ergo-code.github.io/HiGHS/dev/guide/advanced/)); `getIis` returned empty | MIT | 1.16.0, 2026-11-11 |
| CP-SAT (OR-Tools) | Incumbent, bound, wall time, branches, conflicts per solution; a bound callback. No nodes or simplex iterations. | Yes with one worker and a fixed seed: 122,965 branches twice | No | Apache-2.0 | 9.15.6755, 2026-01-14 |
| PuLP with HiGHS | Same as HiGHS, since PuLP passes `callbackTuple` through to highspy | As HiGHS | No | MIT | 4.3.1, 2026-11-19 |
| PuLP with CBC | None found | n/a | No | EPL | CBC wasn't available in this PuLP install |
| Pyomo, python-mip | Not tested | | | BSD-3, EPL-2.0 | 6.11.0, 2.0.2 |

CP-SAT also accepts only integer coefficients ([CP-SAT Primer](https://github.com/d-krupke/cpsat-primer)). That's fine for whole-minute costs, but it means a second way of modelling.

**Recommendation.** HiGHS through `highspy` directly. It's the same kind of solver as Gurobi (LP-based branch-and-cut), it exposes all six metrics from the brief live, it's deterministic and MIT-licensed, and it adds no modelling layer.

Your brief named CP-SAT or PuLP. If you'd rather stay within those two, choose PuLP with HiGHS: it uses the same engine, with an extra layer.

**Confidence: High (90%).** A spike ran Model 1 on both backends behind one `Protocol` with one frozen result type, and the same feasibility checks passed on both. Optimal: both returned objective 55 with gap 0. Early stop: Gurobi `WorkLimit=0.05` gave a feasible result with gap 0.727; HiGHS `mip_max_nodes=20` gave gap 0.364, the same bound on two runs, with HiGHS reporting the status as `kSolutionLimit`. Infeasible: Gurobi returned a 22-constraint IIS; HiGHS returned the IIS as unavailable.

**Design consequence:** the deterministic early stop is backend-specific (`WorkLimit` against `mip_max_nodes`). The protocol takes an abstract effort limit, and each backend maps it to its own option.

## 6. Telemetry metrics and instruments

| Metric | Gurobi | HiGHS | CP-SAT |
| --- | --- | --- | --- |
| Incumbent (best objective) | `MIP_OBJBST` | `mip_primal_bound` | `objective_value` |
| Best bound | `MIP_OBJBND` | `mip_dual_bound` | `best_objective_bound` |
| Gap | Computed | `mip_gap` | Computed |
| Incumbent improvements | Computed in `MIPSOL` | Improving-solution callback | Each solution callback |
| Nodes | `MIP_NODCNT` | `mip_node_count` | None (branches instead) |
| Simplex iterations | `MIP_ITRCNT` | `simplex_iteration_count` | None |
| Elapsed time | `RUNTIME`, `WORK` | `running_time` | `wall_time` |

Gurobi codes are from the [callback codes reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html). Gurobi notes that `MIPSOL_OBJ` is "not necessarily better than the current incumbent" and that `MIP_SOLCNT` counts solutions presented, not improvements. So the improvement count must be computed by comparing values.

| Option | Pros | Cons |
| --- | --- | --- |
| **Core set (incumbent, bound, gap, improvements, elapsed) plus optional named fields (nodes, iterations, work)** | Every backend can report the core; nothing is faked | The optional fields need handling |
| Gurobi's full set, everywhere | Richest | The fallback would have to fake values |
| Only what all backends share | Simplest | Loses nodes and iterations, which the brief asks for |

Instruments, measured with `InMemoryMetricReader` on SDK 1.45.2: a synchronous gauge (`create_gauge`) for gap, incumbent, bound, nodes and iterations, and a counter for improvements. Both export correctly. On the callback itself, Model 1 (T=30, seeds 0–2) took identical work and node counts with and without it, and runtime changed by −2% to +4%. The final sample matched `ObjVal`, `ObjBound` and `NodeCount` exactly. Names: OpenTelemetry's registry has no `solver` namespace, and its rules ask for lowercase, dot-separated, namespaced names with UCUM units ([naming](https://opentelemetry.io/docs/specs/semconv/general/naming/)).

**Recommendation.** The core set plus optional fields. Synchronous instruments recorded from the callback, throttled by elapsed time. A project prefix, for example `groundops.solver.gap`, avoids a future clash. A `solver.backend` attribute.

**Confidence: High (85%).** Measured for Gurobi. HiGHS's improving-solution callback fired; its interrupt-callback sampling rate wasn't measured.

## 7. Early-stop test

| Option | Deterministic? | Measured |
| --- | --- | --- |
| `TimeLimit` | No: Gurobi says wall-clock limits can vary with machine load ([determinism](https://support.gurobi.com/hc/en-us/articles/360031636051)) | Not used |
| **`WorkLimit`** | Yes | `WorkLimit=0.05`: status 16 (`WORK_LIMIT`), feasible, objective 55, bound 15, gap 0.727. `WorkLimit=0.2`: bound 35, gap 0.364. |
| `NodeLimit` or `SolutionLimit` | Yes | Not tested. These stop on counts rather than effort. |

Reproducibility, measured: the same seed and thread count gave identical nodes (31,675), work (4.9858) and iterations (206,354) on two runs. With 4 threads instead of 1, the same model took 81,639 nodes and reached the same optimum.

**Recommendation.** `WorkLimit`, already in `AGENTS.md`. The README still shows `TimeLimit` for interactive use, labelled as non-deterministic.

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

**Confidence: Medium (80%)** that the effect stays small on this repo's instances, across three variants and two settings. Model 2 can't be used to check it: it solved at the root even with presolve, cuts and heuristics off, so there's nothing for a warm start to speed up. **To raise it:** run 20 seeds instead of 3 when the real experiment script exists, and report the distributions.

## 9. Infeasibility diagnosis

Measured: Model 1 with 3 handlers (fewer than the peak overlap) is infeasible. Gurobi's `computeIIS` returned 22 of 324 constraints, with names such as `cover[0]` and `no_overlap[h0,t0,t3]`. `feasRelax` on the cover constraints alone ([Model API](https://docs.gurobi.com/projects/optimizer/en/current/reference/python/model.html)) gave a minimum total violation of 9.

| Option | What it tells you | Available on |
| --- | --- | --- |
| **IIS** | Which constraints conflict | Gurobi only (HiGHS: LP only) |
| `feasRelax` | The cheapest way to violate constraints | Gurobi |
| Elastic cover (penalised slack variables in the model) | Which tasks can't be covered | Any backend |

**Recommendation.** An IIS on Gurobi, as the brief asks, with readable constraint names. The fallback reports "IIS unavailable" in its result. `feasRelax` and an elastic cover are optional later additions.

**Confidence: High (90%).**

## 10. Golden tests

Measured: a T=20 instance has at least 50 different solutions with the optimal objective (100). That's the most the solution pool was allowed to store (`PoolSearchMode=2`, `PoolSolutions=50`).

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
| **`docs/reading-the-log.md`, built from a real log produced by this repo** | Serves your stated goal directly; reproducible | Must be regenerated if the model changes |
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

**Confidence: High (90%).** A top-level `experiments/` directory was accepted. The flat-layout rule applies to the package, not to scripts.

## 15. Where the bound comes from

Measured on Model 1 (T=30): with only the cover constraints, the LP relaxation was integral. Adding the no-overlap constraints gave an LP bound of 15 against an optimum of 55, with 58 fractional variables. Decision 3 shows the clique form closing that gap completely, and decision 4 shows presolve and cuts closing it inside the solver.

**Recommendation.** Teach it through the log walkthrough and the experiment journal. No extra code is needed.

**Confidence: High (85%).**

## Know about, don't build

- **Branch-and-price and column generation:** used by Tian 2022 and Dall'Olio 2023.
- **Gurobi's tuning tool.**
- **OR-Tools MathOpt:** floating-point coefficients over several solvers, per the CP-SAT Primer. Its callbacks weren't tested.
