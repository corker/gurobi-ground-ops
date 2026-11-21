import type { Schemas } from './api'
import { GAP_MINUTES, clock } from './domain'

type Instance = Schemas['AssignmentInstance']

const ROW = 24
const LABEL = 40
const PX = 4
const TICK = 15

/** The IIS in plain words, with the tasks it involves on one time axis so their overlap is visible. */
export function Conflicts({ instance, iis }: { instance: Instance; iis: string[] }) {
  const tasks = new Map(instance.tasks.map((t) => [t.id, t]))
  const label = (id: number) => {
    const task = tasks.get(id)
    return task ? `T${id} (${clock(task.start)}-${clock(task.end)})` : `T${id}`
  }
  const involved = new Set<number>()
  const sentences = iis.map((name) => {
    const cover = /^cover\[(\d+)\]$/.exec(name)
    if (cover) {
      involved.add(Number(cover[1]))
      return `${label(Number(cover[1]))} needs a handler`
    }
    const clash = /^no_overlap\[h(\d+),t(\d+),t(\d+)\]$/.exec(name)
    if (clash) {
      const [a, b] = [Number(clash[2]), Number(clash[3])]
      involved.add(a).add(b)
      return `H${clash[1]} can't do both ${label(a)} and ${label(b)}`
    }
    return name
  })
  const shown = [...involved].flatMap((id) => tasks.get(id) ?? []).sort((a, b) => a.start - b.start)
  const from = Math.floor(Math.min(...shown.map((t) => t.start)) / TICK) * TICK
  const to = Math.ceil(Math.max(...shown.map((t) => t.end)) / TICK) * TICK
  const x = (minutes: number) => LABEL + (minutes - from) * PX
  const ticks = Array.from({ length: (to - from) / TICK + 1 }, (_, i) => from + i * TICK)
  return (
    <section aria-label="Why no schedule exists">
      <h2>Why no schedule exists</h2>
      <p>
        These {iis.length} rules can't all hold at once, though any one fewer can. The instance may
        have other conflicts too.
      </p>
      <p>
        One handler can't do two tasks that overlap or are less than {GAP_MINUTES} minutes apart:
        the time it takes to move between aircraft.
      </p>
      <ul>
        {iis.map((name, i) => (
          <li key={name}>
            {sentences[i]} <code>{name}</code>
          </li>
        ))}
      </ul>
      {shown.length > 0 && (
        <svg
          className="actual-size"
          width={LABEL + (to - from) * PX}
          height={(shown.length + 1) * ROW}
          role="img"
          aria-label={`The ${shown.length} tasks involved, on one time axis from ${clock(from)} to ${clock(to)}`}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line className="grid" x1={x(t)} x2={x(t)} y1={0} y2={(shown.length + 1) * ROW} />
              <text x={x(t) + 2} y={14}>
                {clock(t)}
              </text>
            </g>
          ))}
          {shown.map((task, row) => (
            <g key={task.id}>
              <text x={0} y={(row + 1) * ROW + 16}>
                T{task.id}
              </text>
              <rect
                className="conflict"
                x={x(task.start)}
                y={(row + 1) * ROW + 4}
                width={(task.end - task.start) * PX}
                height={ROW - 8}
              >
                <title>{label(task.id)}</title>
              </rect>
            </g>
          ))}
        </svg>
      )}
    </section>
  )
}
