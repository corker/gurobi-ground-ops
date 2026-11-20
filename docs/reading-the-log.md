# Reading a Gurobi log

Two real logs of the same Model 1 instance (40 tasks, seed 1), annotated line by line. One uses Gurobi's default settings; the other turns off presolve and cuts so the search is visible. Both were produced on 2026-11-20 by gurobipy 14.0.0 on an Apple M4 Pro with one thread:

```sh
uv run ground-ops solve --tasks 40 --seed 1 --expose-search --log exposed.log
uv run ground-ops solve --tasks 40 --seed 1 --log default.log
```

The column meanings below follow [Gurobi's MIP logging documentation](https://docs.gurobi.com/projects/optimizer/en/current/concepts/logging/mip.html).

## The search made visible (`--expose-search`)

### Header: what ran, where, with which settings

```
Gurobi 14.0.0 (mac64[arm], Python) logging started Fri Nov 20 22:07:00 2026

Set parameter LogToConsole to value 0
Set parameter Cuts to value 0
Set parameter DisplayInterval to value 1
Set parameter LogFile to value "exposed.log"
Set parameter Presolve to value 0
Set parameter Threads to value 1
Restricted license - for non-production use only - expires 2028-11-29
Gurobi Optimizer version 14.0.0 build v14.0.0rc1 (mac64[arm] - Darwin 25.6.0 25G83)

CPU model: Apple M4 Pro
Thread count: 14 physical cores, 14 logical processors, using up to 1 threads

Non-default parameters:
Cuts  0
DisplayInterval  1
LogToConsole  0
Presolve  0
Threads  1
```

- **`Restricted license … expires 2028-11-29`:** the free licence bundled with gurobipy is in use, not a full one. Any log without this line came from a different licence.
- **`Non-default parameters`:** the first place to look when two runs of "the same model" behave differently. Here: one thread (for reproducibility), presolve and cuts off (to expose the search), one log line a second.

### The model as Gurobi sees it

```
Optimize a model with 593 rows, 280 columns and 1386 nonzeros (Min)
Model fingerprint: 0x32cf5a86
Model has 106 linear objective coefficients
Variable types: 0 continuous, 280 integer (280 binary)
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [1e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
```

- **Rows are constraints, columns are variables.** 280 columns are the 7 handlers × 40 tasks; 593 rows are 40 `cover` constraints plus 553 `no_overlap` constraints (79 conflicting task pairs × 7 handlers). Both are well under the free limit of 2,000.
- **`Model fingerprint`:** a hash of the model. If two runs show the same fingerprint, they solved the same model; if their results differ, look at the parameters or the machine.
- **`Coefficient statistics`:** every range is small (1 to 20), so there's no numerical risk here. Ranges spanning many orders of magnitude would be a warning sign.

### Before the search

```
Found heuristic solution: objective 189.0000000
Variable types: 0 continuous, 280 integer (280 binary)

Root relaxation: objective 0.000000e+00, 85 iterations, 0.00 seconds (0.00 work units)
```

- **`Found heuristic solution`:** a first feasible schedule, 189 minutes of overtime, found before any LP was solved. It's the first incumbent.
- **`Root relaxation: objective 0`:** the LP relaxation (the same model with "whole numbers only" dropped) says overtime could be as low as 0. That's the first bound, and it's weak: the true answer turns out to be 30. A weak root bound is a formulation property, not a solver failure.

### The node table: incumbent against bound

```
    Nodes    |    Current Node    |     Objective Bounds      |     Work
 Expl Unexpl |  Obj  Depth IntInf | Incumbent    BestBd   Gap | It/Node Time

     0     0    0.00000    0   42  189.00000    0.00000   100%     -    0s
H    0     0                      30.0000000    0.00000   100%     -    0s
     0     0    0.00000    0   42   30.00000    0.00000   100%     -    0s
     0     0    0.00000    0   30   30.00000    0.00000   100%     -    0s
     0     2    0.00000    0   30   30.00000    0.00000   100%     -    0s
  9389  1178   23.00000   29   18   30.00000   23.00000  23.3%   6.2    1s
 20720   862   26.00000   25   17   30.00000   26.00000  13.3%   6.4    2s
 23902   800   26.00000   30   12   30.00000   26.00000  13.3%   6.5    3s
 26609   789   27.00000   25   12   30.00000   27.00000  10.0%   6.5    4s
```

| Column | Meaning |
| --- | --- |
| `Expl`, `Unexpl` | Nodes explored so far, and leaf nodes still waiting |
| `Obj` | The LP objective at the node being explored |
| `Depth` | How deep in the tree that node is |
| `IntInf` | How many integer variables are fractional at that node |
| `Incumbent` | The best schedule found so far (the upper bound, for a minimisation) |
| `BestBd` | The best bound: no schedule can beat it |
| `Gap` | `(Incumbent − BestBd) / Incumbent` |
| `It/Node`, `Time` | Average simplex iterations per node, and elapsed wall-clock time |

- **`H` at the start of a line** means a heuristic found a new incumbent; **`*`** means one was found by branching. Here, an `H` line at the root brings the incumbent from 189 to 30, and it never changes again.
- **Read the two bound columns separately.** The incumbent is fine from the second line on. Everything after that is the bound climbing (0, then 23, 26, 27, finally 30) while the gap shrinks from 100% to 0. This is the "bound won't move" problem from the README, solved by brute force: 32,424 nodes to prove an answer found in the first fraction of a second.

### The summary

```
Cutting planes:
  Gomory: 18
  Clique: 16
  Flow cover: 1
  Zero half: 4
  RLT: 2
  BQP: 5

Explored 32424 nodes (212486 simplex iterations) in 4.94 seconds (3.17 work units)
Thread count was 1 (of 14 available processors)

Solution count 2: 30 189

Optimal solution found (tolerance 1.00e-04)
Best objective 3.000000000000e+01, best bound 3.000000000000e+01, gap 0.0000%
```

- **`Cutting planes` despite `Cuts 0`:** Gurobi 14 still reports some cuts with `Cuts=0`, a different set from the default run. Gurobi's [parameter reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/parameters.html) says `Cuts=0` shuts off cuts, and I couldn't find documentation explaining these lines, so their cause is **unverified**. What is measured is the effect: with `Presolve=0, Cuts=0` this instance needs 32,424 nodes; with defaults it needs 1.
- **Seconds against work units:** the same solve has taken anywhere from about 2.6 s to 17 s of wall time on this machine, depending on what else was running, but exactly 3.17 work units every time. Work units are Gurobi's deterministic effort measure; compare runs with them, not with seconds.
- **`Solution count 2: 30 189`:** the solutions kept in the pool, best first.
- **`Optimal solution found (tolerance 1.00e-04)`:** "optimal" means the gap fell below `MIPGap`, 0.01% by default, not that it's exactly zero.

## The same instance with default settings

```
Found heuristic solution: objective 189.0000000
Presolve removed 539 rows and 196 columns
Presolve time: 0.01s
Presolved: 54 rows, 84 columns, 238 nonzeros
Found heuristic solution: objective 80.0000000
Variable types: 0 continuous, 84 integer (84 binary)

Root relaxation: objective 3.000000e+01, 29 iterations, 0.00 seconds (0.00 work units)

    Nodes    |    Current Node    |     Objective Bounds      |     Work
 Expl Unexpl |  Obj  Depth IntInf | Incumbent    BestBd   Gap | It/Node Time

*    0     0               0      30.0000000   30.00000  0.00%     -    0s

Explored 1 nodes (29 simplex iterations) in 0.01 seconds (0.00 work units)
```

- **`Presolve removed 539 rows and 196 columns`:** before the search, presolve shrank the model from 593 constraints and 280 variables to 54 and 84.
- **`Root relaxation: objective 30`:** on the presolved model, the LP relaxation already gives the optimum. The bound starts where it needs to end, so no branching is needed.
- **`*` on the only node line:** the root LP solution itself was a whole-number schedule, so the first branch-and-bound node produced the optimal incumbent and the gap closed at once.

The two logs show the same lesson from both sides: how hard a MIP is depends as much on how tight its bound is as on its size. Presolve turned a weak formulation into a tight one here; with presolve off, the search had to make up the difference node by node.

## What the telemetry adds to the log

The `groundops.solver.*` metrics carry the same numbers as the node table, recorded at every callback and exported once a second (the OpenTelemetry SDK's own default is once a minute), and labelled by `run_id` so runs can be compared in Grafana. One difference matters: Gurobi's progress callback can run for the last time before the final bound and incumbent are known (in this repo it reported a final bound of 0 when the true bound was 8). So the telemetry always takes its last sample from the model's final attributes, which match the log's `Best objective … best bound` line.
