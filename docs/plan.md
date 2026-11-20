# Implementation plan

What to build, in order, and when each step counts as done. The rules for *how* to build live in [AGENTS.md](../AGENTS.md). The reasons behind each choice live in [design-decisions.md](design-decisions.md), referred to below as D1 to D15. Every step is checked against the lenses in [quality-lenses.md](quality-lenses.md) that apply to it.

**The goal.** Afterwards, the owner can talk about solver behaviour without bluffing: read a Gurobi log, explain what the MIP gap and the bound are doing, and tell a formulation problem from an operational one. The code is the means, not the deliverable.

**Stop rule.** If Model 1 takes longer than expected, stop after Model 1. One correct model beats two rushed ones.

## Step 1: Project setup

The licence limits are already verified (D1): 2,000 variables and 2,000 linear constraints, with the gurobipy 14 licence expiring on 2028-11-29.

- `pyproject.toml` managed by `uv`: Python 3.12+, `gurobipy~=14.0`, `highspy~=1.16`, the OpenTelemetry API and SDK, and `pytest` and `ruff` as dev dependencies. Commit `uv.lock`.
- A Python 3.12 pin, a `.gitignore` (virtual environment, caches, Gurobi `*.log` and `*.ilp` files, licence files), and an MIT `LICENSE`.
- A README skeleton with the required opening, the licence-limit note, and the gurobipy version and its maintenance status from PyPI.

**Done when:** `uv sync && uv run pytest` runs on a clean checkout with no licence file.

## Step 2: Model 1, handler-to-task assignment

- `docs/domain.md`: the glossary and the list of simplifications (D12).
- A seeded instance generator with tunable size, using task durations based on the turnaround dataset (D11).
- The model (D2, D3): a binary variable x[h,t] for each handler and task; each task covered exactly once; pairwise no-overlap constraints with a uniform 10-minute gap between a handler's tasks (D3); the objective is minutes worked outside each handler's shift window. The formulation is written out in the README.
- An independent feasibility checker in repo code, which doesn't trust the solver (lens 1).

**Done when:** golden tests pass that assert exact objectives on small fixed instances, plus feasibility (every task covered, no overlaps), never a specific assignment (D10). Every instance fits the free limit.

## Step 3: Model 2, shift coverage

Start only after Model 1 is done and tested.

- Set covering: choose integer staffing per shift pattern so that every half-hour of demand is covered, at minimum cost. Deliberately a different structure from Model 1.
- Parameters based on the D4 proof of concept, without its early-start premium: a 24-hour horizon of 48 half-hour slots; patterns of 4, 6 or 8 hours starting at any slot; one unpaid break slot in patterns of 6 hours or more; cost is the number of paid slots. The demand profile comes from the seeded generator.

**Done when:** the same kinds of tests pass as for Model 1: golden objective plus coverage feasibility.

## Step 4: Solver telemetry (the most important step)

- A Gurobi callback that emits, during the solve: MIP gap, incumbent, best bound, the count of improved incumbents (computed by comparing values, D6), node count, simplex iterations, and elapsed time.
- Export through OpenTelemetry metrics, with a plain-stdout fallback when no collector is configured. Metric names, units and attributes follow D6.
- Check that the final emitted values equal the model's final `ObjVal`, `ObjBound` and `NodeCount` (lens 12). Write a Gurobi log (`LogFile`) for instrumented runs, for the walkthrough below.
- README: the gap-and-bound explainer, written to be understood cold in six months. It must explain that a bound that won't move and an incumbent that won't improve are different problems.
- `docs/reading-the-log.md`: a real log from this repo, annotated (D13).

**Done when:** tests run with an in-memory metric reader and no collector, and the stdout and OpenTelemetry paths report the same values.

## Step 5: Operational edges, each with a test

- **Early stop:** stop after a given effort and return the best solution plus its gap. "Feasible but not proven optimal" is a normal result the caller can distinguish, not an error. Tests use an abstract effort limit, which maps to `WorkLimit` on Gurobi (D7, D5), and assert the shared result status "limit reached, feasible", not a backend's own status code. Because default instances solve at the root (D4), these tests also switch on one solve option that exposes the search: `Presolve=0, Cuts=0` on Gurobi, and presolve off with `mip_heuristic_effort=0` on HiGHS, as in the D5 spike.
- **Warm start:** re-solve a perturbed instance (one task moves) using the previous solution as a `Start`. Report the work-unit difference against a cold start across seeds, honestly, even if it's "no measurable gain" (D8).
- **Infeasibility diagnosis:** compute an IIS on an infeasible instance and report the conflicting constraints readably (D9).
- **Determinism:** pin `Seed` and `Threads`. Document that Gurobi's results depend on the thread count, and which settings make a run reproducible (D7).

## Step 6: Solver-agnostic fallback

- One thin `Protocol` with two implementations: Gurobi and HiGHS (D5).
- A capability one backend lacks, such as IIS, is reported as unavailable in the result.
- The effort limit maps to `mip_max_nodes` on HiGHS.

**Done when:** the same test suite passes on both backends, except that the IIS test asserts "unavailable" on HiGHS. The suite then still runs if the Gurobi licence bundled with gurobipy is missing or expired.

## Step 7: Tests

The required tests are the "Done when" items of Steps 2 to 6: golden objectives, structural feasibility, the early stop returning feasible-but-not-optimal with a non-zero gap, and an IIS naming the right constraints. On top of those, everything passes on the free licence with no collector running.

## Experiments

Each script in `experiments/` re-measures a result from [design-decisions.md](design-decisions.md) and records it in `docs/experiments.md` with the machine and settings (D14). The first set:

| Experiment | Decision |
| --- | --- |
| Pairwise vs clique no-overlap: LP bound and constraint count | D3, D15 |
| Default settings vs `Presolve=0, Cuts=0`: node counts across seeds | D4 |
| Callback overhead in work units, with and without the callback | D6 |
| Warm start vs cold start (full and partial `Start`) over 20 seeds | D8 |
| The same run with 1 and 4 threads | D7 |
| Number of tied optimal solutions | D10 |
