# Experiments

Measurements that back numbers quoted in the README and in [design-decisions.md](design-decisions.md). Each has a script in [`experiments/`](../experiments) that reproduces it.

**Machine and settings for every result below:** Apple M4 Pro (14 cores), macOS 26.6.2, Python 3.12.12, gurobipy 14.0.0 with the free bundled licence, opentelemetry-sdk 1.45.2, one solver thread (`Threads=1`, `Seed=0`). Measured on 2026-11-20.

**About wall-clock time.** Work units and node counts are deterministic: the same run gives the same numbers every time. Wall-clock time isn't. On this machine, the same 3-second solve has taken over 22 seconds when other work was running. So every wall-clock result here is a median of repeated runs, reported with its range, and two separate runs are shown where they disagree.

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

## Planned

Still to come, from [plan.md](plan.md): pairwise versus clique no-overlap (D3, D15) and the number of tied optimal solutions (D10).
