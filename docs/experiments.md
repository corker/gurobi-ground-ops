# Experiments

Measurements behind the numbers in the README and in [design-decisions.md](design-decisions.md). Each section gives the script in [`experiments/`](../experiments), or the command, that reproduces it.

**Machine and settings for every result below:** Apple M4 Pro (14 cores), macOS 26.6.2, Python 3.12.12, gurobipy 14.0.0 with the free bundled licence, opentelemetry-sdk 1.45.2, one solver thread (`Threads=1`, `Seed=0`). Measured on 2026-11-20 unless a section gives another date.

**About wall-clock time.** Work units and node counts are deterministic: the same run gives the same numbers every time. Wall-clock time isn't: on this machine, the same 3-second solve has taken over 22 seconds when other work was running. So each wall-clock result here is a median of repeated runs with its range, and where two runs disagree, both are shown.

## Root solves (D4)

How often Gurobi solves an instance at the root node, with default settings and with `--expose-search` (`Presolve=0, Cuts=0`). 20 seeds per size.

```sh
uv run python experiments/root_solves.py
```

```
Model 1, 20 tasks, defaults: 20/20 at the root; nodes min 0, median 1, max 1
Model 1, 20 tasks, Presolve=0, Cuts=0: 5/20 at the root; nodes min 1, median 4.5, max 331
Model 1, 30 tasks, defaults: 20/20 at the root; nodes min 0, median 1, max 1
Model 1, 30 tasks, Presolve=0, Cuts=0: 6/20 at the root; nodes min 1, median 31.5, max 1722
Model 1, 40 tasks, defaults: 20/20 at the root; nodes min 1, median 1, max 1
Model 1, 40 tasks, Presolve=0, Cuts=0: 1/20 at the root; nodes min 1, median 2725, max 94294
Model 1, 48 tasks, defaults: 20/20 at the root; nodes min 0, median 1, max 1
Model 1, 48 tasks, Presolve=0, Cuts=0: 1/20 at the root; nodes min 1, median 3811.5, max 170454
Model 2, 48 slots, defaults: 18/20 at the root; nodes min 1, median 1, max 37
Model 2, 48 slots, Presolve=0, Cuts=0: 15/20 at the root; nodes min 1, median 1, max 49
```

Node counts are deterministic, so two runs gave identical output. "0 nodes" means presolve alone solved the instance.

## Callback overhead (D6)

The same Model 1 solve (40 tasks, search exposed) with and without the progress callback, 5 runs each.

```sh
uv run python experiments/callback_overhead.py
```

| Seed | Work units, without / with | Nodes, without / with | Wall-clock median (range), without → with: run 1 | Run 2 |
| --- | --- | --- | --- | --- |
| 1 | 3.170548 / 3.170548 | 32,424 / 32,424 | 3.06 s (2.67–17.42) → 3.00 s (2.76–3.10) | 4.91 s (2.92–22.67) → 3.15 s (2.90–3.83) |
| 3 | 0.537829 / 0.537829 | 4,790 / 4,790 | 0.44 s (0.44–0.46) → 0.46 s (0.45–0.48) | 0.51 s (0.46–0.67) → 0.51 s (0.48–0.53) |

**Finding:** the callback doesn't change the search: identical work units and nodes in all 20 runs. Any wall-clock cost is smaller than this machine's run-to-run noise.

## Flush cost as runs accumulate (D21)

One process, 4,000 runs in a row through `Telemetry`. Median flush time over each window of 50 runs.

```sh
uv run python experiments/flush_cost.py
```

| Runs | Median flush, run 1 | Run 2 |
| --- | --- | --- |
| 51–100 | 0.21 ms | 0.12 ms |
| 451–500 | 0.81 ms | 0.44 ms |
| 951–1,000 | 0.82 ms | 1.03 ms |
| 1,951–2,000 | 2.52 ms | 6.09 ms |
| 3,951–4,000 | 12.96 ms | 16.09 ms |

**Finding:** each run's final flush gets slower as the process accumulates runs, because the OpenTelemetry SDK keeps every attribute set it has seen. The trend is clear in both runs, but the exact numbers vary by about two times between runs.

## Warm start against cold start (D8)

Model 1, 40 tasks, search exposed. For each seed: solve the instance, delay task 4 by 25 minutes, then solve the delayed instance cold, from the full previous schedule, and from the previous schedule without the delayed task (a partial start).

```sh
uv run python experiments/warm_start.py
```

```
seed  cold     full start  partial start  (work units)
   1    1.714       1.714          1.616
   2    0.011       0.010          0.010
   3    0.770       0.718          0.719
   4    3.748      45.630         45.630
   5    0.019       0.019          0.015
   6    0.947       0.945          0.945
   7    0.020       0.012          0.013
   8    0.011       0.011          0.012
   9    0.189       0.189          0.208
  10    0.065       0.061          0.061
  11    0.001       0.000          0.000
  12    0.016       0.016          0.016
  13    1.181       0.954          0.994
  14    0.281       0.432          0.443
  15    0.016       0.016          0.016
  16    2.666       2.666          2.783
  17    0.085       0.085          0.081
  18    0.078       0.103          0.101
  19    2.353       2.353          1.653
  20    2.629       2.661          2.471
cold: median 0.137 (min 0.001, max 3.748)
full start: median 0.146 (min 0.000, max 45.630)
partial start: median 0.155 (min 0.000, max 45.630)
full start: less work than cold on 7 of 20
partial start: less work than cold on 12 of 20
```

**Finding:** no consistent gain. Most seeds differ by a few percent either way, and on seed 4 the warm start took twelve times the work: the start sent the search down a different path, which proved the bound far more slowly. Why that path is slower is unverified. Work units are deterministic, so this table reproduces exactly.

## One thread against four (D7)

Model 1, 40 tasks, search exposed, `Seed=0`. Each configuration runs twice.

```sh
uv run python experiments/threads.py
```

```
seed 1, 1 thread(s): objective 30, nodes 32424, work 3.1705, repeat identical: True
seed 1, 4 thread(s): objective 30, nodes 51238, work 1.2566, repeat identical: True
seed 2, 1 thread(s): objective 84, nodes 3, work 0.0038, repeat identical: True
seed 2, 4 thread(s): objective 84, nodes 3, work 0.0038, repeat identical: True
seed 3, 1 thread(s): objective 23, nodes 4790, work 0.5378, repeat identical: True
seed 3, 4 thread(s): objective 23, nodes 7471, work 0.1874, repeat identical: True
seed 4, 1 thread(s): objective 103, nodes 24436, work 3.6693, repeat identical: True
seed 4, 4 thread(s): objective 103, nodes 33854, work 1.2949, repeat identical: True
seed 5, 1 thread(s): objective 49, nodes 67, work 0.0109, repeat identical: True
seed 5, 4 thread(s): objective 49, nodes 129, work 0.0085, repeat identical: True
```

**Finding:** the thread count changes the search (more nodes on four of five seeds) but not the optimum, and each thread count repeats exactly. With four threads the reported work is lower even though more nodes were explored. Gurobi describes a work unit only as "very roughly" one second on a single thread, so how work is counted across threads is unverified; don't compare work units across thread counts. The repo pins `Threads=1` so a run's search doesn't depend on which settings or machine it was started on.

## Status of infeasible solves (D9)

Which status Gurobi returns for an infeasible Model 1 instance: five sizes, 20 seeds each, with one handler fewer than the peak overlap, with default settings and with the search exposed.

```sh
uv run python experiments/infeasible_status.py
```

```
200 infeasible solves: status 3 (INFEASIBLE) 200 times
```

**Finding:** always status 3, never 4 (`INF_OR_UNBD`), so the models handle only status 3. Three of the 2-task instances (seeds 6, 7 and 9) have a peak overlap of 1, so they're solved with no handlers at all.

## Tied optimal solutions (D10)

How many different schedules share the optimal objective in Model 1. Gurobi's solution pool with `PoolSearchMode=2` searches for the `PoolSolutions` best solutions ([Gurobi: solution pool](https://docs.gurobi.com/projects/optimizer/en/current/features/solutionpool.html)), with `MIPGap=0` as those docs advise. When the worst stored solution is worse than the optimum, every optimal schedule is in the pool and the count is exact; otherwise the count is a lower bound. Measured on 2026-11-21.

```sh
uv run python experiments/tied_optima.py
```

```
Model 1, default settings, PoolSearchMode=2, PoolSolutions=2000, MIPGap=0
10 tasks, seed 1: optimum 0, optimal schedules 192
10 tasks, seed 2: optimum 25, optimal schedules 108
10 tasks, seed 3: optimum 9, optimal schedules at least 2000
10 tasks, seed 4: optimum 50, optimal schedules 432
10 tasks, seed 5: optimum 25, optimal schedules 486
20 tasks, seed 1: optimum 0, optimal schedules at least 2000
20 tasks, seed 2: optimum 56, optimal schedules at least 2000
20 tasks, seed 3: optimum 0, optimal schedules at least 2000
20 tasks, seed 4: optimum 41, optimal schedules at least 2000
20 tasks, seed 5: optimum 99, optimal schedules at least 2000
30 tasks, seed 1: optimum 8, optimal schedules at least 2000
30 tasks, seed 2: optimum 119, optimal schedules at least 2000
30 tasks, seed 3: optimum 0, optimal schedules at least 2000
30 tasks, seed 4: optimum 56, optimal schedules at least 2000
30 tasks, seed 5: optimum 62, optimal schedules at least 2000
```

A brute-force enumeration of every assignment of the four exact 10-task instances found the same counts: 192, 108, 432 and 486.

**Finding:** every instance has more than a hundred optimal schedules, and from 20 tasks on, at least 2,000. So the schedule a solve returns is one of many equally good ones, which is why the tests assert the objective and feasibility, never a specific assignment.

## Pairwise against clique no-overlap (D3, D15)

Model 1's no-overlap rule written pairwise, as in the package, and as one constraint per handler and clique. Two tasks conflict when `[start, end + 10 min)` intervals overlap, so the tasks running at any task's start form a clique, and those cliques cover every conflicting pair. The script builds the clique form itself; the package uses the pairwise form. The LP bound is from `Model.relax()`. Constraint counts include the one cover constraint per task. Measured on 2026-11-21.

```sh
uv run python experiments/clique_no_overlap.py
```

```
Model 1, default settings; constraints include the cover constraints
20 tasks, seed 1, 5 handlers: pairwise 145 constraints, LP bound 0, optimum 0; clique 95 constraints, LP bound 0, optimum 0
20 tasks, seed 2, 5 handlers: pairwise 165 constraints, LP bound 40.5, optimum 56; clique 90 constraints, LP bound 56, optimum 56
20 tasks, seed 3, 6 handlers: pairwise 158 constraints, LP bound 0, optimum 0; clique 86 constraints, LP bound 0, optimum 0
20 tasks, seed 4, 5 handlers: pairwise 140 constraints, LP bound 31, optimum 41; clique 90 constraints, LP bound 41, optimum 41
20 tasks, seed 5, 5 handlers: pairwise 115 constraints, LP bound 87, optimum 99; clique 80 constraints, LP bound 99, optimum 99
30 tasks, seed 1, 6 handlers: pairwise 312 constraints, LP bound 0, optimum 8; clique 174 constraints, LP bound 8, optimum 8
30 tasks, seed 2, 5 handlers: pairwise 255 constraints, LP bound 113.5, optimum 119; clique 155 constraints, LP bound 119, optimum 119
30 tasks, seed 3, 6 handlers: pairwise 276 constraints, LP bound 0, optimum 0; clique 156 constraints, LP bound 0, optimum 0
30 tasks, seed 4, 7 handlers: pairwise 436 constraints, LP bound 0, optimum 56; clique 191 constraints, LP bound 56, optimum 56
30 tasks, seed 5, 5 handlers: pairwise 260 constraints, LP bound 37, optimum 62; clique 140 constraints, LP bound 62, optimum 62
40 tasks, seed 1, 7 handlers: pairwise 593 constraints, LP bound 0, optimum 30; clique 264 constraints, LP bound 30, optimum 30
40 tasks, seed 2, 5 handlers: pairwise 410 constraints, LP bound 71, optimum 84; clique 215 constraints, LP bound 84, optimum 84
40 tasks, seed 3, 8 handlers: pairwise 712 constraints, LP bound 0, optimum 23; clique 264 constraints, LP bound 23, optimum 23
40 tasks, seed 4, 8 handlers: pairwise 864 constraints, LP bound 0, optimum 103; clique 280 constraints, LP bound 103, optimum 103
40 tasks, seed 5, 6 handlers: pairwise 454 constraints, LP bound 0, optimum 49; clique 238 constraints, LP bound 49, optimum 49
```

**Finding:** on all 15 instances the clique form's LP bound equals the optimum, while the pairwise LP bound is below it on all 12 instances with a non-zero optimum, and is 0 on half of those. The clique form needs 32% to 70% as many constraints. Both forms reach the same optimum. This held on every instance tried, but isn't proven in general.

## What fits the free licence (D1)

How many Model 1 instances of each size fit the free licence's 2,000 variables and 2,000 constraints, with the default number of handlers. The script counts the model's size without building it, so it uses no solver. Measured on 2026-11-21.

```sh
uv run python experiments/licence_fit.py
```

```
Model 1, default handlers, 20 seeds per size, limit 2000 of each
40 tasks: 20/20 fit; largest variables or constraints 1130
42 tasks: 20/20 fit; largest variables or constraints 1638
44 tasks: 20/20 fit; largest variables or constraints 1820
46 tasks: 20/20 fit; largest variables or constraints 1858
48 tasks: 20/20 fit; largest variables or constraints 1944
50 tasks: 19/20 fit; largest variables or constraints 2150
52 tasks: 17/20 fit; largest variables or constraints 2224
54 tasks: 17/20 fit; largest variables or constraints 2346
56 tasks: 17/20 fit; largest variables or constraints 2838
58 tasks: 15/20 fit; largest variables or constraints 2853
60 tasks: 13/20 fit; largest variables or constraints 3154
```

**Finding:** every seed fits up to 48 tasks; from 50, some don't, and `ground-ops solve` refuses those with a message instead of solving.

## Exporting to an endpoint with nothing listening

`uv run ground-ops solve --tasks 10` with `OTEL_EXPORTER_OTLP_ENDPOINT` set to a port where nothing listens, three runs each, wall-clock from start to exit, on 2026-11-21:

| Setting | Runs | Median |
| --- | --- | --- |
| SDK default timeout (10 s) | 19.7, 19.7, 20.7 s | 19.7 s |
| `OTEL_EXPORTER_OTLP_TIMEOUT=1` | 1.9, 0.2, 1.2 s | 1.2 s |
| Endpoint not set | 0.2, 0.2, 0.2 s | 0.2 s |

**Finding:** the solve is quick; the wait is the exporters retrying at shutdown. Unset the endpoint when the stack isn't running, or lower the timeout.

