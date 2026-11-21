import type { Schemas } from './api'
import { clock, covers } from './domain'

type Instance = Schemas['CoverageInstance']

const SLOT = 12
const UNIT = 12

/** Demand against people on duty in each half-hour slot, then the roster that produces it. */
export function Coverage({
  instance,
  staffing,
}: {
  instance: Instance
  staffing: Record<string, number>
}) {
  const patterns = new Map(instance.patterns.map((p) => [p.id, p]))
  const roster = Object.entries(staffing)
    .map(([id, people]) => ({ pattern: patterns.get(Number(id))!, people }))
    .sort((a, b) => a.pattern.start - b.pattern.start)
  const onDuty = instance.demand.map((_, slot) =>
    roster.reduce((sum, { pattern, people }) => sum + (covers(pattern, slot) ? people : 0), 0),
  )
  const short = onDuty.filter((n, slot) => n < instance.demand[slot]).length
  const surplus = onDuty.filter((n, slot) => n > instance.demand[slot]).length
  const top = Math.max(...instance.demand, ...onDuty)
  const height = top * UNIT
  return (
    <>
      <figure>
        <svg
          viewBox={`0 0 ${instance.demand.length * SLOT} ${height + 14}`}
          role="img"
          aria-label={`People on duty against demand in ${instance.demand.length} half-hour slots: ${short} slots short, ${surplus} with more people than needed`}
        >
          {onDuty.map((people, slot) => (
            <g key={slot}>
              <rect
                className="on-duty"
                x={slot * SLOT}
                y={height - people * UNIT}
                width={SLOT - 2}
                height={people * UNIT}
              />
              <rect
                className="demand"
                x={slot * SLOT}
                y={height - instance.demand[slot] * UNIT}
                width={SLOT - 2}
                height={instance.demand[slot] * UNIT}
              />
              {slot % 4 === 0 && (
                <text x={slot * SLOT} y={height + 12}>
                  {clock(slot * 30).slice(0, 2)}
                </text>
              )}
            </g>
          ))}
        </svg>
        <figcaption>
          <span className="on-duty">On duty</span> against <span className="demand">demand</span>{' '}
          (outline) per half hour: {short} slots short, {surplus} with more people than needed.
        </figcaption>
        <details>
          <summary>Demand and people on duty as a table</summary>
          <table>
            <thead>
              <tr>
                <th>Slot</th>
                <th>Demand</th>
                <th>On duty</th>
              </tr>
            </thead>
            <tbody>
              {instance.demand.map((needed, slot) => (
                <tr key={slot}>
                  <td>{clock(slot * 30)}</td>
                  <td>{needed}</td>
                  <td>{onDuty[slot]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </figure>
      <h2>Roster</h2>
      <ul>
        {roster.map(({ pattern, people }) => (
          <li key={pattern.id}>
            {people} × {clock(pattern.start * 30)}-{clock((pattern.start + pattern.length) * 30)}
            {pattern.break_slot !== null && ` (break ${clock(pattern.break_slot * 30)})`}
          </li>
        ))}
      </ul>
    </>
  )
}
