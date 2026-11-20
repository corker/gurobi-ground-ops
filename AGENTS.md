# Agent instructions: gurobi-ground-ops

A small public repo for learning Gurobi (MIP solver) on airport ground-operations problems: handler→task assignment and shift-coverage set covering. The models are textbook. The real deliverable is what surrounds the solve: solver telemetry, deterministic tests, effort limits, warm starts and infeasibility diagnosis. The repo has four parts: the core library (models, solve, telemetry), an LGTM observability stack in Docker Compose, a FastAPI service with SSE progress, and a React UI. The core library never imports the API or UI, and its tests need none of the other parts.

The owner is a backend/platform engineer, **not an optimisation modeller**. Nothing in the repo may suggest otherwise.

## Hard rules

- **Verify every Gurobi API against the official docs before using it, and cite the URL** (in the commit/PR or the docstring, wherever it's useful). Don't plan around method names, `where` constants or `cbGet` keys from memory. A wrong `where`/`what` pair raises at runtime.
- If something can't be verified, say so. Never present a guess as fact.
- **No performance claims or benchmark numbers that haven't been measured.** Any timing reported must come from a real run, with the machine and solver settings stated.
- Never claim tests pass without running them and showing the real output.
- Every instance must solve within the **free pip-installed gurobipy licence size limit**, so `uv sync && uv run pytest` works with no licence. If an instance doesn't fit, shrink it. Nothing may require a paid or academic licence.
- All tests must pass with no OpenTelemetry collector running: they read metrics through an in-memory reader. With `OTEL_EXPORTER_OTLP_ENDPOINT` unset, no exporter is created and nothing is exported; there's no stdout fallback. `uv run pytest` must need no Docker, no Node and no browser.
- Call `model.update()` before reading model size (`NumVars`, `NumConstrs`) or calling `copy()` or `relax()`. gurobipy applies changes lazily, so before `update()` the size reads 0 and a copy or relaxation is missing the pending constraints.

## Do NOT build

- No job queue, database, authentication or multi-user state. Runs live in memory and are lost on restart.
- No container for the app itself. Docker Compose runs only the `grafana/otel-lgtm` observability stack.
- No Kubernetes, CI/CD or cloud deployment (single developer, local only).
- No WebSockets. Progress is pushed over SSE; everything else is plain requests.
- No notebooks, and no Sudoku, N-queens or puzzle demos.
- No models beyond the two above, and no second solver: Gurobi only.

## Conventions

- `uv` for dependencies and for running everything. Never `pip install`.
- Python 3.12+. Type hints on all function signatures, enforced by ruff's `ANN` rules and `mypy --strict`. gurobipy ships type stubs, but `setParam` values aren't type-checked, so parameter names and values need tests.
- One package in a src layout (`src/ground_ops/`), with tests in `tests/`. No sub-packages unless a file exceeds ~500 lines. Reproducible experiment scripts live in a top-level `experiments/` directory, outside the package.
- Project docs live in `docs/`: `related-work.md` for existing projects and literature, `quality-lenses.md` for the checks every feature must pass, `plan.md` for what to build and when each step is done, `design-decisions.md` for decisions with their evidence and confidence, plus design docs as they're written.
- The UI lives in `ui/`: React, Vite and strict TypeScript, managed with `npm`, tested with Vitest and Testing Library, linted with oxlint, formatted with Prettier. `npm run check` in `ui/` must pass before a UI change is done (D22). Node is needed only for the UI. TypeScript types for API payloads are generated from FastAPI's OpenAPI schema, not written by hand.
- The API lives under `/api` and binds to `127.0.0.1` only. A streaming endpoint checks that the run exists before it starts streaming.
- MIT licence.

## How to write code

When principles conflict, this is the order of priority: **correct > simple (KISS) > needed now (YAGNI) > SOLID > DRY**. Apply SOLID and DRY to the code that exists today, not to code that might exist later.

### Start simple, then iterate

- Write the most direct solution that meets the current requirement and passes its tests. Use a plain function before a class.
- Add complexity only when a concrete, present need forces it: a failing test, a second real caller, or a measured problem. Name that need in the commit message.
- Choose the smaller diff. Deleting code is better than adding it.

### YAGNI: no hypothetical cases

Don't add any of the following unless a current requirement or test needs it:

- Parameters, options, flags or config values that no caller passes.
- Extension points, registries, factories, plugin hooks or abstraction layers "for later".
- Generalisation beyond the two models, such as a generic "optimisation problem" framework.
- Handling for inputs that can't occur. Validate at the boundaries (instance generation, public entry points) and trust internal calls.
- A `try/except` that only logs or re-raises. Catch an exception only where you can actually handle it.
- Backwards-compatibility shims. Nothing has been released.

If you think something will be needed later, say so in your reply. Don't build it.

### KISS: readable over clever

- A reader should be able to follow a function top to bottom without jumping through layers of indirection.
- Keep functions small and single-purpose, and name them for what they do.
- Use plain data: frozen dataclasses for instances and results. No metaclasses, no decorator magic, no dynamic attribute tricks.
- Use the standard library first. Add a dependency only when it removes substantial code, and justify it.
- Prefer early returns to nested `if`/`else`.

### SOLID, applied lightly

- **Single responsibility:** each module and function has one reason to change. Instance generation, model building, solving, telemetry and reporting live in separate modules. A model builder doesn't print or emit metrics, and a reporter doesn't solve.
- **Open/closed:** there are no extension points. Gurobi is the only solver, so there's no solver abstraction or `Protocol`; one implementation means a concrete class.
- **Interface segregation:** functions take only the data they use, not whole objects "just in case".
- **Dependency inversion:** collaborators such as the telemetry sink are passed in as arguments, not constructed inside the function that uses them. Prefer composition over inheritance: no base classes, no inheritance hierarchies.

### Reuse without duplicate abstractions

- Before writing a helper, search the repo for an existing one and use it.
- **Rule of three:** extract shared code when the third occurrence appears. With only two, keep both inline even if they look similar.
- Give each domain concept one type (one task type, one solve-result type) and share it across both models. No parallel types, and no wrappers that only mirror a type or forward calls.

### Tests

- Every behaviour has a test, including the error and edge paths.
- Assert on behaviour, not structure: what the solution does (every task covered exactly once, no handler with overlapping tasks, objective equal to the golden value), not the model's internals (number of variables, constraint names). The exception is when the internals are the behaviour, such as the constraint names in an IIS.
- Test names describe behaviour: `test_effort_limit_returns_feasible_with_nonzero_gap`, not `test_solve_2`.
- Test at the right level: a pure function gets a unit test, and a solve gets an integration test. Don't solve a MIP to test a formatting function.
- Tests are deterministic: fixed seeds for instance generation, pinned solver `Seed` and `Threads`, no wall-clock assertions, no dependence on test order or network. A test that needs a solve stopped early uses `WorkLimit`, not `TimeLimit`; Gurobi documents wall-clock limits as non-deterministic. Leave `ConcurrentMIP` off (the default), keep `Method` at 0, 1, 2 or 4, and build the model in a fixed order. ([Gurobi: Is Gurobi deterministic?](https://support.gurobi.com/hc/en-us/articles/360031636051))
- Use `pytest.mark.parametrize` for repetitive cases instead of copy-pasted tests.

### Comments

Keep a comment only if a cold reader, who sees just the code, would find the code surprising without it: a hidden constraint, a subtle invariant, a workaround, or a solver quirk. A non-obvious workaround with no comment needs one.

Don't write, and remove, comments that are:

- **Stale:** the comment says X, the code does Y.
- **Over-promising:** they claim an invariant the code doesn't enforce.
- **Dangling:** they name a symbol, file or path that no longer exists.
- **Obvious:** they restate the code or the identifier names.
- **Historical:** they narrate how the code got here instead of what it does.
- **Rot-prone:** they're tied to call sites, line numbers or task IDs instead of invariants.
- **Defending a decision** ("deliberately", "trade-off", "we chose"): rationale belongs in the commit message or the README.

If a comment is borderline, delete it rather than rewording it. Be most sceptical of comments you wrote yourself. No commented-out code, no `TODO` placeholders, no dead code.

## Workflow for every change

Build one module at a time. (These are the steps for each change, not the project steps in `docs/plan.md`.)

1. Write the simplest version that meets the requirement.
2. Fix lint and formatting: `uv run ruff check --fix . && uv run ruff format .`
3. Run the full check, which must pass before a change is done: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`. The ruff rule set and mypy's strict mode are configured in `pyproject.toml`; don't loosen them to make a change pass. From Step 2 on, read the coverage report for untested branches; coverage is a signal, not a target.
4. Run the changed code directly (`uv run python -c "..."` or a throwaway script), covering the normal case and the edges: an empty instance, one handler with one task, zero demand, an infeasible instance, an effort limit too small to prove optimality. Look for what the tests miss: a wrong branch, an off-by-one at a time-slot boundary, a silent `None` or NaN, a raw solver exception leaking out. If code can't be exercised without heavy setup, say so instead of guessing.
5. Check the feature against the lenses in `docs/quality-lenses.md` that apply to it.
6. Reread the diff and remove anything the task didn't require.

When a verification fails, fix it and re-verify before reporting done.

After each plan step, have a reviewer with no context from the work read the step's diff against this file and the lenses, reading every file from disk, and fix what it finds.

## README framing (non-negotiable opening)

> **Learning Gurobi on ground-operations problems.**
> I'm a backend/platform engineer picking up Gurobi — I'm not an optimisation modeller. …

Never write "production-ready".
