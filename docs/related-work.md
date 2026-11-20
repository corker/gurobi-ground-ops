# Related work: projects and literature

As of 2026-11-20.

## Summary

No public project found combines the three things this repo is built around: airport ground-ops models, live solver telemetry, and tested operational edges (time limits, warm starts, IIS, determinism). Each part exists somewhere, but separately.

- **The models exist.** Academic papers formulate ground-staff task assignment and shift covering, but rarely publish code. Gurobi publishes workforce scheduling examples, but as notebooks without tests.
- **Telemetry exists only after the solve.** Gurobi's gurobi-logtools parses log files once the solve is over. No project was found that streams callback metrics such as gap, bound and incumbent to OpenTelemetry or Prometheus while the solve runs.
- **The commercial suite checked is closed source.** It shows the problem is real, but offers nothing to learn solver behaviour from.

These are references, not competitors. The repo is for learning, so the useful questions are what to read, what to check the models against, and which part no project found here covers: live telemetry.

## Scope

A project counts as related if it is public code or a paper on airport ground-staff assignment or covering, Gurobi learning material on workforce problems, or a tool for watching solver progress. Sources checked: GitHub search and the GitHub API, PyPI, Crossref, and vendor pages.

Paper details come from open abstracts where available, otherwise from titles and Crossref metadata; no full texts were read. A search that finds nothing doesn't prove nothing exists. Read "none found" as "none found in these searches".

## Airport ground-ops optimisation

The academic literature is rich, but public code is thin. The repos found are research code, a single dataset, or tiny projects with no traction.

### Open-source repos

| Repo | What it is | Stars | Last push | Licence |
| --- | --- | --- | --- | --- |
| [RoyalSkye/AGH](https://github.com/RoyalSkye/AGH) | Code for two 2023 papers: learned large-neighbourhood search over an operation-scheduling MILP re-optimised with CPLEX (IEEE TKDE), and a learned construction method for ground-handling vehicle routing (IEEE TITS). | 28 | 2023-03-07 | MIT |
| [spadrona/airport_ground_handling_dataset](https://github.com/spadrona/airport_ground_handling_dataset) | 10 turnaround instances: 65 arrivals in 2 hours, 5 service providers, operations with durations, successors and resource types | 1 | 2025-03-12 | Apache-2.0 |
| [Shuntao-Wang/airport-staff-scheduling-optimization](https://github.com/Shuntao-Wang/airport-staff-scheduling-optimization) | Hybrid greedy heuristic for multi-objective airport staff shift scheduling | 3 | 2026-01-24 | MIT |
| [tasikGHub/AGHO](https://github.com/tasikGHub/AGHO) | "Airport Ground Handling Optimizer" (only the description was checked) | 0 | 2026-04-21 | MIT |

No GitHub results came back for airport baggage optimisation or turnaround scheduling.

### Papers to check the models against

| Paper | Year | Problem | Relevance |
| --- | --- | --- | --- |
| [From gate to runway: a systematic review of airport ground operations optimization](https://doi.org/10.1016/j.jairtraman.2026.103013) (J. Air Transport Management) | 2026 | Reviews 199 papers across 7 areas, including ground workforce planning and scheduling | Best entry point |
| [Tian, Li, Huang, Yuan](https://doi.org/10.1371/journal.pone.0279131) (PLOS ONE, open access) | 2022 | Ground-service task assignment: shifts with qualifications, task time windows, maximise priority × duration. ILP solved by branch-and-price. | Closest to Model 1 |
| [Kiermaier, Frey, Bard](https://doi.org/10.1007/s10951-019-00635-5) (J. Scheduling) | 2020 | Tour scheduling with flexible break assignment at an airport ground handler | Closest to Model 2 |
| [Dall'Olio, Kolisch](https://doi.org/10.1287/trsc.2022.0110) (Transportation Science) | 2023 | Formation and routing of worker teams, branch-and-price-and-check | Richer version of Model 1 |
| [Cappanera, Di Gangi, Lapucci, Pellegrini et al.](https://doi.org/10.1016/j.eswa.2023.121953) (Expert Systems with Applications) | 2024 | Integrated task scheduling and personnel rostering, case study | Links Model 1 and Model 2 |
| [Frey, Kiermaier, Kolisch](https://doi.org/10.1287/trsc.2016.0702) (Transportation Science) | 2017 | Inbound baggage handling | Baggage background |
| [Dowling, Krishnamoorthy, Mackenzie, Sier](https://doi.org/10.1023/A:1018992120116) (Annals of OR) | 1997 | Staff rostering at a large international airport | Classic reference |

The problem descriptions for Tian and for the 2026 review come from their abstracts. For the other papers they come from titles and Crossref metadata only.

## Gurobi learning material

Gurobi's own material is the closest neighbour for the models, but it is notebook-first, and the formulation is the whole point. Telemetry, time-limit behaviour and reproducibility tests aren't its focus.

| Resource | What it covers | Version / activity | Licence |
| --- | --- | --- | --- |
| [Gurobi/modeling-examples](https://github.com/Gurobi/modeling-examples) | Colab notebooks. [workforce](https://github.com/Gurobi/modeling-examples/tree/master/workforce) is a multi-objective workforce scheduling MIP ("advanced level"). `lost_luggage_distribution` is a vehicle routing problem. | 874 stars, pushed 2026-11-20 | Apache-2.0 |
| [gurobi-optimods: Workforce Scheduling](https://gurobi-optimods.readthedocs.io/en/latest/mods/workforce.html) | Data-in, data-out API: shift coverage from worker availability, with min/max shifts and preferences. Starts simple, then adds requirements. | 3.2.0 on PyPI (2026-10-13), 178 stars | Apache-2.0 |
| [Gurobi case study: Swissport airport staff scheduling](https://www.gurobi.com/resources/case-studies/swissport-automating-airport-staff-scheduling) | Monthly schedules for 2,000 staff at Zurich Airport. No code. | Marketing page | Proprietary |

The optimods workforce mod is related to Model 2, but it is a different problem: it assigns named workers to shifts, while Model 2 chooses shift patterns to cover half-hourly demand. It also hides the formulation, which is the part this repo is about.

## Workforce scheduling and rostering tools

General-purpose solvers ship ready-made examples of both model shapes. The open-source fallback backend is HiGHS; [design-decisions.md](design-decisions.md) (D5) compares it with CP-SAT and PuLP.

| Tool | Relevant examples | Version (PyPI) | Licence |
| --- | --- | --- | --- |
| [Google OR-Tools](https://github.com/google/or-tools) (14.4k stars) | `shift_scheduling_sat.py`, `tasks_and_workers_assignment_sat.py`, `assignment_with_constraints_sat.py` in [examples/python](https://github.com/google/or-tools/tree/main/examples/python) | 9.15.6755 (2026-01-14) | Apache-2.0 |
| [CP-SAT Primer](https://github.com/d-krupke/cpsat-primer) (840 stars, pushed 2026-11-07) | A book-length guide to using and understanding CP-SAT, including its log | Docs, not versioned | CC-BY-4.0 |
| [HiGHS](https://github.com/ERGO-Code/HiGHS) via `highspy` (1.9k stars) | Open-source LP/MIP solver with live MIP callbacks (bound, gap, nodes); the chosen fallback | 1.16.0 (2026-11-11) | MIT |
| [PuLP](https://github.com/coin-or/pulp) (2.5k stars) | Modelling layer over CBC, HiGHS and other solvers; no airport examples | 4.3.1 (2026-11-19) | Listed as NOASSERTION on GitHub |
| [Timefold quickstarts](https://github.com/TimefoldAI/timefold-quickstarts) (606 stars, pushed 2026-11-16) | `employee-scheduling`, `task-assigning` and `flight-crew-scheduling` use cases | Python `timefold` 1.24.0b0 (2025-07-08, beta) | Apache-2.0 |

Timefold is the clearest contrast. It uses metaheuristics to produce good rosters quickly rather than to prove optimality, so it has no gap or bound to read.

## Solver telemetry and log analysis

Existing tools read logs after the solve finishes. None were found that export live callback metrics to an observability stack, so that is the part this repo aims to add.

| Tool | What it does | When | Version / activity | Licence |
| --- | --- | --- | --- | --- |
| [gurobi-logtools](https://github.com/Gurobi/gurobi-logtools) | Parses Gurobi log files into pandas DataFrames or Excel. Plots with plotly and ipywidgets. | After the solve | 4.0.1 on PyPI (2025-08-14), 128 stars, pushed 2026-11-12 | Apache-2.0 |
| [CP-SAT-Log-Analyzer](https://github.com/d-krupke/CP-SAT-Log-Analyzer) | Web app that visualises and annotates OR-Tools CP-SAT logs, partly inspired by gurobi-logtools | After the solve | 68 stars, pushed 2026-09-29 | MIT |
| [Gurobi callback example](https://docs.gurobi.com/projects/examples/en/current/examples/python/callback.html) (official docs) | Reads node count, best objective and best bound inside the MIP callback and prints them | During the solve, to stdout and a log file | Docs example | Proprietary |

What was searched and found nothing:

- GitHub repo search for "gurobi opentelemetry", "gurobi prometheus", "gurobi metrics callback", "gurobi monitoring", "solver opentelemetry" and "optimization solver observability": zero results.
- PyPI for `gurobi-telemetry`, `gurobipy-otel` and `gurobi-monitor`: none exist.

Open question: Gurobi's commercial server products may show job progress in a UI. Not checked, and it would sit behind a paid licence anyway.

## Commercial ground-handling products

The established vendor products are closed planning suites. They show that the problem matters in industry, but they offer no way to see or learn the solver behaviour inside them.

| Product | Scope (vendor-stated) | Source |
| --- | --- | --- |
| INFORM GroundStar | Ground-handling resource management: planning, rostering and real-time allocation of ground staff and equipment, with an optimiser in the rostering module | [Vendor page](https://www.inform-software.com/en/solutions/aviation-ground-operations/ground-handling-resource-management) |

Only one vendor was checked. Others in this space weren't researched and aren't listed here, so this table is not a market map.

## Comparison and gaps

Every neighbour focuses on the model, the data or the log after the fact. This repo is the only one found whose focus is what happens around the solve while it runs.

| Project | Ground-ops domain | Solver | Focus | Format | Licence |
| --- | --- | --- | --- | --- | --- |
| gurobi-ground-ops (this repo, planned) | Yes | Gurobi, plus an open-source fallback | Live telemetry, time limits, warm starts, IIS, determinism | Tested Python package | MIT |
| RoyalSkye/AGH | Yes | CPLEX inside a learned LNS | Solving large instances faster | Research code | MIT |
| spadrona dataset | Yes | None | Benchmark instances | Dataset | Apache-2.0 |
| Gurobi workforce notebook | No (services industry) | Gurobi | Formulation | Notebook | Apache-2.0 |
| gurobi-optimods workforce | No (generic) | Gurobi | Ready-made model behind an API | Library | Apache-2.0 |
| OR-Tools scheduling examples | No (generic) | CP-SAT | Formulation | Example scripts | Apache-2.0 |
| gurobi-logtools | No | Gurobi | Log analysis after the solve | Library | Apache-2.0 |
| INFORM GroundStar | Yes | Not disclosed | Running operations | Commercial product | Proprietary |

### What to reuse

- **Check Model 1 against** [Tian et al. 2022](https://doi.org/10.1371/journal.pone.0279131), which is open access and closest in shape.
- **Check Model 2 against** [Kiermaier, Frey, Bard 2020](https://doi.org/10.1007/s10951-019-00635-5) and the classic set-covering tour formulation it builds on.
- **Cross-check telemetry against the solve itself:** the final values the callback emits should equal the model's final attributes. That gives a test that doesn't depend on wall-clock time, without parsing logs.
- **For comparing solver logs**, the [CP-SAT Primer](https://github.com/d-krupke/cpsat-primer) explains how a non-LP solver reports its bound and progress.

## Sources

All sources are linked inline. GitHub metadata came from the GitHub API, versions from PyPI and paper metadata from Crossref, all on 2026-11-20.
