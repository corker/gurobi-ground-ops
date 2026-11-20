"""The `ground-ops` command."""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from ground_ops.domain import AssignmentInstance, CoverageInstance, Result, ShiftPattern, covers, overtime
from ground_ops.instances import generate_assignment, generate_coverage
from ground_ops.model1 import solve_assignment
from ground_ops.model2 import solve_coverage
from ground_ops.progress import ProgressRecorder, phase
from ground_ops.telemetry import telemetry_from_environment


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _schedule_lines(instance: AssignmentInstance, result: Result) -> list[str]:
    lines = []
    for handler in instance.handlers:
        shift = f"{_clock(handler.shift_start)}-{_clock(handler.shift_end)}"
        tasks = sorted((t for t in instance.tasks if result.solution.get(t.id) == handler.id), key=lambda t: t.start)
        parts = []
        for t in tasks:
            extra = overtime(t, handler)
            parts.append(f"T{t.id} {_clock(t.start)}-{_clock(t.end)}" + (f" (+{extra} overtime)" if extra else ""))
        lines.append(f"H{handler.id} shift {shift}: " + (", ".join(parts) or "no tasks"))
    return lines


def report(instance: AssignmentInstance, seed: int, result: Result) -> str:
    """The text `ground-ops solve` prints for an optimal result."""
    header = f"Model 1: {len(instance.tasks)} tasks, {len(instance.handlers)} handlers, seed {seed}"
    summary = (
        f"status: {result.status}  overtime: {result.objective:g} min  "
        f"bound: {result.bound:g} min  gap: {(result.gap or 0.0) * 100:.2f}%"
    )
    return "\n".join([header, summary, *_schedule_lines(instance, result)])


def _slot_clock(slot: int) -> str:
    return _clock(slot * 30)


def _pattern_label(pattern: ShiftPattern) -> str:
    shift = f"{_slot_clock(pattern.start)}-{_slot_clock(pattern.start + pattern.length)}"
    return shift + (f" (break {_slot_clock(pattern.break_slot)})" if pattern.break_slot is not None else "")


def coverage_report(instance: CoverageInstance, seed: int, result: Result) -> str:
    """The text `ground-ops cover` prints for an optimal result."""
    patterns = {p.id: p for p in instance.patterns}
    lines = [
        f"Model 2: {len(instance.demand)} half-hour slots, {len(instance.patterns)} shift patterns, seed {seed}",
        f"status: {result.status}  cost: {result.objective:g} paid half-hours  "
        f"bound: {result.bound:g} paid half-hours  gap: {(result.gap or 0.0) * 100:.2f}%",
        "roster:",
    ]
    for pattern_id, people in sorted(result.solution.items(), key=lambda item: patterns[item[0]].start):
        lines.append(f"  {people} x {_pattern_label(patterns[pattern_id])}")
    lines.append("slot   demand  on duty")
    for slot, needed in enumerate(instance.demand):
        on_duty = sum(n for p, n in result.solution.items() if covers(patterns[p], slot))
        surplus = f"  (+{on_duty - needed})" if on_duty > needed else ""
        lines.append(f"{_slot_clock(slot)}  {needed:>6}  {on_duty:>7}{surplus}")
    return "\n".join(lines)


def _with_telemetry[T](model: str, solve: Callable[[ProgressRecorder | None], T]) -> T:
    telemetry = telemetry_from_environment()
    if telemetry is None:
        return solve(None)
    try:
        with telemetry.run(model) as recorder:
            print(f"ground-ops: exporting telemetry for run_id {recorder.run_id}", file=sys.stderr)
            return solve(recorder)
    finally:
        telemetry.shutdown()


def main(argv: list[str] | None = None) -> int:
    solver_options = argparse.ArgumentParser(add_help=False)
    solver_options.add_argument("--seed", type=int, default=1, help="instance seed (default: 1)")
    solver_options.add_argument("--log", type=Path, help="append Gurobi's log to this file")
    solver_options.add_argument(
        "--expose-search", action="store_true", help="set Presolve=0 and Cuts=0 so the search is visible"
    )
    parser = argparse.ArgumentParser(prog="ground-ops")
    commands = parser.add_subparsers(dest="command", required=True)
    solve = commands.add_parser(
        "solve", parents=[solver_options], help="solve a seeded Model 1 instance and print the schedule"
    )
    solve.add_argument("--tasks", type=int, default=30, help="number of tasks, even (default: 30)")
    commands.add_parser("cover", parents=[solver_options], help="solve a seeded Model 2 instance and print the roster")
    args = parser.parse_args(argv)

    try:
        if args.command == "cover":

            def solve_cover(recorder: ProgressRecorder | None) -> tuple[CoverageInstance, Result]:
                with phase(recorder, "generate instance"):
                    coverage = generate_coverage(args.seed)
                return coverage, solve_coverage(
                    coverage, recorder=recorder, log_file=args.log, expose_search=args.expose_search
                )

            coverage, result = _with_telemetry("coverage", solve_cover)
            print(coverage_report(coverage, args.seed, result))
            return 0

        def solve_tasks(recorder: ProgressRecorder | None) -> tuple[AssignmentInstance, Result]:
            with phase(recorder, "generate instance"):
                instance = generate_assignment(args.tasks, args.seed)
            result = solve_assignment(instance, recorder=recorder, log_file=args.log, expose_search=args.expose_search)
            return instance, result

        instance, result = _with_telemetry("assignment", solve_tasks)
        print(report(instance, args.seed, result))
        return 0
    except ValueError as error:
        print(f"ground-ops: {error}", file=sys.stderr)
        return 2
