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

## Planned

Still to come, from [plan.md](plan.md): pairwise versus clique no-overlap (D3, D15), warm start versus cold start over 20 seeds (D8), one thread against four (D7), and the number of tied optimal solutions (D10).
