import { describe, expect, it } from 'vitest'
import { amount, clock, covers, grafanaUrl, overtime, overtimeParts, percent } from './domain'

const HANDLER = { id: 0, shift_start: 360, shift_end: 600 }

describe('overtime, with the same cases as tests/test_domain.py', () => {
  it.each([
    [400, 420, 0, []],
    [350, 370, 10, [[350, 360]]],
    [590, 610, 10, [[600, 610]]],
    [300, 320, 20, [[300, 320]]],
    [
      350,
      610,
      20,
      [
        [350, 360],
        [600, 610],
      ],
    ],
  ])('a task from %i to %i has %i minutes outside the shift', (start, end, minutes, parts) => {
    const task = { id: 0, start, end }
    expect(overtime(task, HANDLER)).toBe(minutes)
    expect(overtimeParts(task, HANDLER)).toEqual(parts)
  })
})

it('a pattern covers its slots except its break', () => {
  const pattern = { id: 0, start: 2, length: 4, break_slot: 3 }
  expect([1, 2, 3, 4, 5, 6].map((slot) => covers(pattern, slot))).toEqual([
    false,
    true,
    false,
    true,
    true,
    false,
  ])
})

it('formats minutes as a clock time and a gap as a percentage', () => {
  expect([clock(0), clock(425), clock(1439)]).toEqual(['00:00', '07:05', '23:59'])
  expect([percent(0.4333), percent(null)]).toEqual(['43.33%', 'undefined'])
})

it('formats an objective or bound without solver noise, or as none yet', () => {
  expect([amount(23.000000000000004), amount(17), amount(0), amount(239.5), amount(null)]).toEqual([
    '23',
    '17',
    '0',
    '239.5',
    'none yet',
  ])
})

it('links to the dashboard filtered to the run and its time window, open-ended while it runs', () => {
  const ended = new URL(grafanaUrl({ id: 'r-1', started_at: 100, ended_at: 103.5 }))
  expect(ended.pathname).toBe('/d/ground-ops-solver')
  expect(Object.fromEntries(ended.searchParams)).toEqual({
    'var-run_id': 'r-1',
    from: '95000',
    to: '108500',
  })
  const running = new URL(grafanaUrl({ id: 'r-1', started_at: 100, ended_at: null }))
  expect(running.searchParams.get('to')).toBe('now')
})
