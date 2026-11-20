# Quality lenses

Check each feature through the lenses that apply to it before calling it done. When a question has no good answer, the feature isn't finished.

## Lenses that apply

Apply the first group to every feature, then the groups that match what the feature touches. Several lenses point to rules in [AGENTS.md](../AGENTS.md) rather than repeating them.

### Every feature

| # | Lens | Questions | Origin |
| --- | --- | --- | --- |
| 1 | **Correctness** | Does the solution satisfy every constraint, and does the objective match a golden value? Is feasibility checked by repo code that doesn't trust the solver, at an explicit tolerance? Gurobi accepts violations up to `FeasibilityTol`, which defaults to 1e-6. | ISO: functional suitability |
| 2 | **Failure modes** | Is every solver status handled on purpose: optimal, limit reached with or without an incumbent, infeasible, unbounded? Is "feasible but not proven optimal" a normal result with its gap? What happens with no licence or no collector? Each case should give a clear result or a readable message, never a raw traceback. | ISO: reliability; repo purpose |
| 3 | **Reproducibility** | Same inputs, same machine, same Gurobi version: same result? Are the solver settings and build order in AGENTS.md: Tests followed, and is `uv.lock` committed? | [Gurobi determinism article](https://support.gurobi.com/hc/en-us/articles/360031636051); [uv docs](https://docs.astral.sh/uv/concepts/projects/layout/) |
| 4 | **Code quality** | Is it the simplest version that meets the requirement, in scope, readable top to bottom, with one reason to change per module and no duplicate abstractions? See AGENTS.md: How to write code, Do NOT build. | ISO: maintainability; Google: design, complexity, naming |
| 5 | **Tests** | Does every behaviour have a test that asserts on behaviour, at the right level, deterministically? See AGENTS.md: Tests. | ISO: testability; Google: tests |
| 6 | **Installability** | Does `uv sync && uv run pytest` work on a clean machine with no licence, no collector, no network, no Docker and no Node? | ISO: flexibility (installability); AGH's CPLEX dependency |
| 7 | **Security** | Are licence files and secrets kept out of git? Are dependencies pinned? Is untrusted input confined to the API (lens 17)? | ISO: security |
| 8 | **Documentation** | Would a backend engineer understand the feature cold in six months? Are modelling choices recorded in the README rather than in code comments? | Google: documentation |
| 9 | **Honesty and licensing** | Is every claim verified, or labelled unverified, and every Gurobi API checked with its URL cited? No unmeasured numbers? Are new dependencies' licences compatible with MIT? See AGENTS.md: Hard rules. | Repo purpose |

### Model and instance features

| # | Lens | Questions | Origin |
| --- | --- | --- | --- |
| 10 | **Formulation quality** | Is the model the textbook form, written out mathematically in the README and matching the code one-to-one? No big-M where a direct constraint works? Coefficients in a small range, with consistent units? Does symmetry between identical handlers stall the bound, and is that explained? | Papers; [Gurobi numerics guide](https://docs.gurobi.com/projects/optimizer/en/current/concepts/numericguide.html); `Symmetry` parameter |
| 11 | **Instances** | Does every instance fit the free-licence size limit, with size set by a parameter of the seeded generator? Are the durations and time windows plausible against a paper or dataset in [related-work.md](related-work.md), and are the simplifications stated? | ISO: performance efficiency (capacity); papers use real data |

### Solve and telemetry features

| # | Lens | Questions | Origin |
| --- | --- | --- | --- |
| 12 | **Observability** | Do the metrics alone show what the solve did: gap, incumbent, bound, incumbent improvements, nodes, iterations, elapsed time and work units? Are names namespaced and lowercase, with UCUM units (`s`)? Are attributes low-cardinality, with one ID per run, unique across processes, on active-only instruments with an explicit cap (D21)? Do the final emitted values equal the model's final attributes? | Repo purpose; [OpenTelemetry conventions](https://opentelemetry.io/docs/specs/semconv/general/metrics/); the gap gurobi-logtools leaves |
| 13 | **Measurement discipline** | Is any timing comparison, such as warm start versus cold start, repeated across several `Seed` values, with the spread reported? Are the machine, Gurobi version and parameters stated? | [Gurobi on comparisons](https://support.gurobi.com/hc/en-us/articles/26992650628369) |
| 14 | **Usability of outputs** | Is the IIS report readable without knowing Gurobi? Do public functions take and return plain dataclasses? | ISO: interaction capability |

### API and UI features

| # | Lens | Questions | Origin |
| --- | --- | --- | --- |
| 15 | **API contract** | Does every solver status (optimal, limit reached, infeasible, interrupted) map to exactly one API status that the UI handles? Does a missing run return 404 before any stream starts? Are the TypeScript types generated from the OpenAPI schema? | Repo purpose; D17, D20 |
| 16 | **Concurrency safety** | Does each run get its own Gurobi environment, created and freed under one lock (D17)? Is shared state (the run table, the samples) guarded? Can a cancel race with a run that has just finished? | [Gurobi race conditions](https://support.gurobi.com/hc/en-us/articles/40912136522129); Google: parallel programming |
| 17 | **Input safety** | Is every request validated, and is an instance over the free-licence size rejected before it's built? Does the API bind to `127.0.0.1` only? | ISO: security |
| 18 | **Solution inspection** | Can a non-modeller judge from the views alone whether the answer makes operational sense: who works when, where the overtime comes from, which tasks and handlers clash? | Repo purpose: formulation vs operational questions |
| 19 | **Basic accessibility** | Semantic HTML, keyboard-reachable controls, readable contrast, and charts with a text label? | ISO: interaction capability (inclusivity) |

## Considered and out of scope

These lenses matter in related work, but not for this repo's purpose. If the scope changes, move the affected lens into the table above.

| Lens | Where it matters | Why it's out here |
| --- | --- | --- |
| Rich operational constraints (qualifications, breaks, teams, labour rules) | Tian, Kiermaier, Dall'Olio, commercial suites | The models stay textbook on purpose. Their absence must be stated in the README, not hidden. |
| Solution stability under re-planning (how much a re-solve changes the schedule) | Commercial suites, disruption-management papers | Warm start measures solve time, not schedule change. Not requested. |
| Fairness and preferences | Gurobi workforce examples, optimods | Single objective, chosen and documented. |
| Scale (hundreds of flights, decomposition, learned search) | AGH, branch-and-price papers | Instances must fit the free licence. |
| Uncertainty (stochastic demand, delays) | Disruption-management literature | Deterministic textbook models only. |
| Safety | ISO: safety | Synthetic data that drives no real people or equipment. |
| Availability, scalability of a service | ISO: reliability, flexibility | Local, single-user, run on demand. Runs are lost on restart. |
| Solver independence (running the same suite on a second solver) | Research code tied to one commercial solver | Gurobi only, by choice (D5). The pip package's bundled licence already lets anyone run the tests. |
| Authentication and multi-user state | ISO: security | Bound to `127.0.0.1`; one user. |
| Privacy | ISO: security | No personal data. Generated IDs only, never real names. |
| Cost, sustainability, internationalisation | Common architecture frameworks | No hosted infrastructure, no spend, English only. |

## Where the lenses come from

- **General software quality:** the nine product-quality characteristics of [ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html) (names as listed by the [arc42 quality model](https://quality.arc42.org/standards/iso-25010)) and [Google's code-review guide](https://google.github.io/eng-practices/review/reviewer/looking-for.html).
- **Optimisation practice:** Gurobi's [numerics guide](https://docs.gurobi.com/projects/optimizer/en/current/concepts/numericguide.html), its articles on [determinism](https://support.gurobi.com/hc/en-us/articles/360031636051) and [making accurate comparisons](https://support.gurobi.com/hc/en-us/articles/26992650628369), and the [parameter reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html).
- **Telemetry:** OpenTelemetry's [metric semantic conventions](https://opentelemetry.io/docs/specs/semconv/general/metrics/) and [naming rules](https://opentelemetry.io/docs/specs/semconv/general/naming/).
- **The related work** in [related-work.md](related-work.md): what each family of projects pays attention to, and what it leaves out.

### What related work covers and misses

| Family | Lenses it covers well | Lenses it misses | What this repo takes from it |
| --- | --- | --- | --- |
| Academic papers (Tian 2022, Kiermaier 2020, Dall'Olio 2023, ...) | Formulation quality, solution methods for scale, realistic constraints (qualifications, breaks, teams) | Runnable code, reproducibility, telemetry, tests | Check the formulations and objectives against them |
| Research code (AGH) | Performance at scale | Depends on CPLEX, a commercial solver. Tests and telemetry weren't checked. | Installability: everything must run on free tools |
| Gurobi notebooks and optimods | Clear formulations, a gentle progression from simple to complex | Tests, determinism, time-limit and infeasibility handling and telemetry aren't their focus. Optimods hides the model. | Readable formulations, documented step by step |
| OR-Tools examples, CP-SAT Primer | Breadth of model shapes, explanation of solver logs and parameters | Observability during the solve | Log literacy |
| Timefold | Fast, practical rosters | No bound or gap, so no proof of optimality | Contrast for the gap-and-bound explainer |
| gurobi-logtools, CP-SAT-Log-Analyzer | Reading solver progress after the fact | Live metrics, integration with an observability stack | Contrast: live metrics during the solve instead of parsing logs afterwards |
| Commercial suite (INFORM GroundStar) | Operational fit: real-time re-planning, real labour rules | Everything is closed, so solver behaviour can't be inspected | Motivates warm start as a re-planning edge |

The gap across all of them is the same one: no project treats solve behaviour (status, gap, bound, reproducibility, diagnosis) as something to observe and test.
