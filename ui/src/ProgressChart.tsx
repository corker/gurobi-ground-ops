import type { Progress } from './api'
import { amount } from './domain'

const WIDTH = 600
const HEIGHT = 200

/** Incumbent and bound over time: the gap is the space between the two lines. */
export function ProgressChart({ samples }: { samples: Progress[] }) {
  const points = samples.filter((s) => s.incumbent !== null || s.bound !== null)
  if (points.length < 2) return null
  const values = points.flatMap((s) => [s.incumbent, s.bound]).filter((v) => v !== null)
  const [low, high] = [Math.min(...values), Math.max(...values)]
  const last = points.at(-1)!
  const end = last.elapsed || 1
  const x = (elapsed: number) => (elapsed / end) * WIDTH
  const y = (value: number) => HEIGHT - ((value - low) / (high - low || 1)) * HEIGHT
  const line = (pick: (s: Progress) => number | null) =>
    points
      .flatMap((s) => {
        const value = pick(s)
        return value === null ? [] : [`${x(s.elapsed)},${y(value)}`]
      })
      .join(' ')
  return (
    <figure>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Incumbent ${amount(last.incumbent)} and bound ${amount(last.bound)} after ${last.elapsed.toFixed(1)} s`}
      >
        <polyline className="incumbent" points={line((s) => s.incumbent)} />
        <polyline className="bound" points={line((s) => s.bound)} />
      </svg>
      <figcaption>
        <span className="incumbent">Incumbent</span> (best found) and{' '}
        <span className="bound">bound</span> (proven floor), from {amount(low)} to {amount(high)}
      </figcaption>
    </figure>
  )
}
