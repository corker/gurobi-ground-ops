import type { Schemas } from './api'
import { clock, overtime, overtimeParts } from './domain'

type Instance = Schemas['AssignmentInstance']
type Handler = Schemas['Handler']

const ROW = 30
const LABEL = 150
const HOUR = 60

/** One row per handler: the shift as a band, tasks as bars, minutes outside the shift in the overtime colour. */
export function Schedule({
  instance,
  solution,
}: {
  instance: Instance
  solution: Record<string, number>
}) {
  const tasksOf = (handler: Handler) =>
    instance.tasks.filter((t) => solution[t.id] === handler.id).sort((a, b) => a.start - b.start)
  const times = [
    ...instance.tasks.flatMap((t) => [t.start, t.end]),
    ...instance.handlers.flatMap((h) => [h.shift_start, h.shift_end]),
  ]
  const from = Math.floor(Math.min(...times) / HOUR) * HOUR
  const to = Math.ceil(Math.max(...times) / HOUR) * HOUR
  const width = LABEL + (to - from)
  const x = (minutes: number) => LABEL + minutes - from
  const overtimeOf = (handler: Handler) =>
    tasksOf(handler).reduce((sum, t) => sum + overtime(t, handler), 0)
  const total = instance.handlers.reduce((sum, h) => sum + overtimeOf(h), 0)
  const hours = Array.from({ length: (to - from) / HOUR + 1 }, (_, i) => from + i * HOUR)
  return (
    <figure>
      <svg
        className="wide"
        viewBox={`0 0 ${width} ${(instance.handlers.length + 1) * ROW}`}
        role="img"
        aria-label={`Schedule of ${instance.handlers.length} handlers and ${instance.tasks.length} tasks, ${total} minutes of overtime in total`}
      >
        {hours.map((h) => (
          <g key={h}>
            <line
              className="grid"
              x1={x(h)}
              x2={x(h)}
              y1={0}
              y2={(instance.handlers.length + 1) * ROW}
            />
            <text x={x(h) + 2} y={ROW - 10}>
              {clock(h)}
            </text>
          </g>
        ))}
        {instance.handlers.map((handler, row) => {
          const y = (row + 1) * ROW
          return (
            <g key={handler.id}>
              <text x={4} y={y + 19}>
                H{handler.id} {clock(handler.shift_start)}-{clock(handler.shift_end)}
              </text>
              <rect
                className="shift"
                x={x(handler.shift_start)}
                y={y + 4}
                width={handler.shift_end - handler.shift_start}
                height={ROW - 8}
              />
              {tasksOf(handler).map((task) => (
                <g key={task.id}>
                  <rect
                    className="task"
                    x={x(task.start)}
                    y={y + 8}
                    width={task.end - task.start}
                    height={ROW - 16}
                  >
                    <title>
                      T{task.id} {clock(task.start)}-{clock(task.end)}
                      {overtime(task, handler) > 0 && `, ${overtime(task, handler)} min overtime`}
                    </title>
                  </rect>
                  {overtimeParts(task, handler).map(([start, end]) => (
                    <rect
                      key={start}
                      className="overtime"
                      x={x(start)}
                      y={y + 8}
                      width={end - start}
                      height={ROW - 16}
                    />
                  ))}
                </g>
              ))}
            </g>
          )
        })}
      </svg>
      <figcaption>
        Bars are tasks over each handler's <span className="shift">shift</span>;{' '}
        <span className="overtime">overtime</span> is the part of a task outside the shift. {total}{' '}
        minutes in total.
      </figcaption>
      <details>
        <summary>The schedule as a table</summary>
        <table>
          <thead>
            <tr>
              <th>Handler</th>
              <th>Shift</th>
              <th>Tasks</th>
              <th>Overtime</th>
            </tr>
          </thead>
          <tbody>
            {instance.handlers.map((handler) => (
              <tr key={handler.id}>
                <td>H{handler.id}</td>
                <td>
                  {clock(handler.shift_start)}-{clock(handler.shift_end)}
                </td>
                <td>
                  {tasksOf(handler)
                    .map((t) => `T${t.id} ${clock(t.start)}-${clock(t.end)}`)
                    .join(', ') || 'none'}
                </td>
                <td>{overtimeOf(handler)} min</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}
