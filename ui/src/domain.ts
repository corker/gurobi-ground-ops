import type { Schemas } from './api'

/** The gap between two tasks of one handler: GAP_MINUTES in domain.py. */
export const GAP_MINUTES = 10

type Task = Schemas['Task']
type Handler = Schemas['Handler']
type ShiftPattern = Schemas['ShiftPattern']

/** The parts of a task outside the handler's shift, as [start, end) minutes: before it and after it. */
export function overtimeParts(task: Task, handler: Handler): [number, number][] {
  const parts: [number, number][] = [
    [task.start, Math.min(task.end, handler.shift_start)],
    [Math.max(task.start, handler.shift_end), task.end],
  ]
  return parts.filter(([start, end]) => end > start)
}

/** Minutes of the task outside the handler's shift: the same rule as `overtime` in domain.py. */
export function overtime(task: Task, handler: Handler): number {
  return overtimeParts(task, handler).reduce((sum, [start, end]) => sum + end - start, 0)
}

/** Whether a pattern has someone on duty in a half-hour slot: the same rule as `covers` in domain.py. */
export function covers(pattern: ShiftPattern, slot: number): boolean {
  return (
    pattern.start <= slot && slot < pattern.start + pattern.length && slot !== pattern.break_slot
  )
}

export function clock(minutes: number): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`
}

/** An objective or bound to six significant digits, as the CLI prints it: 23.000000000000004 is 23. */
export function amount(value: number | null): string {
  return value === null ? 'none yet' : String(Number(value.toPrecision(6)))
}

export function percent(gap: number | null): string {
  return gap === null ? 'undefined' : `${(gap * 100).toFixed(2)}%`
}

const GRAFANA = 'http://localhost:3000'
// Metrics are exported once a second, so a little margin keeps the first and last samples in view.
const MARGIN_MS = 5_000

/** The provisioned dashboard, filtered to one run and its time window. */
export function grafanaUrl(run: {
  id: string
  started_at: number
  ended_at: number | null
}): string {
  const from = Math.floor(run.started_at * 1000) - MARGIN_MS
  const to = run.ended_at === null ? 'now' : String(Math.ceil(run.ended_at * 1000) + MARGIN_MS)
  const query = new URLSearchParams({ 'var-run_id': run.id, from: String(from), to })
  return `${GRAFANA}/d/ground-ops-solver?${query}`
}
