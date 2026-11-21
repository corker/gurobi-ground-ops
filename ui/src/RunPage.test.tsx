import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { RunView } from './api'
import { ASSIGNMENT, FakeEventSource, PROGRESS, fakeApi, run } from './fakes'
import { RunPage } from './RunPage'

const ID = '1795214339-57938-1'
const PATH = `/api/runs/${ID}`
const SOLUTION = { '0': 0, '1': 1, '2': 0 }

afterEach(() => {
  vi.unstubAllGlobals()
  FakeEventSource.last = null
})

it('shows live progress from the stream, then the final result, and closes the stream on done', async () => {
  let view = run({ state: 'running', ended_at: null })
  fakeApi({ [`GET ${PATH}`]: () => ({ body: view }) })
  render(<RunPage id={ID} />)
  expect(await screen.findByText('Solving…')).toBeInTheDocument()
  const stream = FakeEventSource.last!
  expect(stream.url).toBe(`${PATH}/events`)

  act(() => stream.emit('progress', PROGRESS))
  expect(screen.getByText('43.33%')).toBeInTheDocument()
  expect(screen.getByText('4475')).toBeInTheDocument()

  view = run({
    result: { status: 'optimal', objective: 15, bound: 15, gap: 0, solution: SOLUTION, iis: [] },
  })
  act(() => stream.emit('done', { status: 'optimal', error: null }))
  expect(await screen.findByText('optimal')).toBeInTheDocument()
  expect(stream.closed).toBe(true)
})

it('cancel asks the API to stop the run', async () => {
  const fetch = fakeApi({
    [`GET ${PATH}`]: { body: run({ state: 'running', ended_at: null }) },
    [`POST ${PATH}/cancel`]: { status: 202, body: run({ state: 'running', ended_at: null }) },
  })
  render(<RunPage id={ID} />)
  await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
  expect(fetch).toHaveBeenCalledWith(`${PATH}/cancel`, { method: 'POST' })
  expect(screen.getByRole('button', { name: 'Cancelling…' })).toBeDisabled()
})

const RESULTS: [string, Partial<RunView>, string[]][] = [
  [
    'optimal',
    {
      result: { status: 'optimal', objective: 15, bound: 15, gap: 0, solution: SOLUTION, iis: [] },
    },
    ['Proven best: no schedule can beat it.', 'T0 06:00-06:40, T2 09:50-10:15'],
  ],
  [
    'limit reached',
    {
      result: {
        status: 'limit reached',
        objective: 30,
        bound: 17,
        gap: 0.4333,
        solution: SOLUTION,
        iis: [],
      },
    },
    ['43.33%', '17 min overtime'],
  ],
  [
    'limit reached with no solution',
    {
      result: {
        status: 'limit reached',
        objective: null,
        bound: null,
        gap: null,
        solution: {},
        iis: [],
      },
    },
    ['the best found so far, if any', 'no solution found', 'none yet'],
  ],
  [
    'infeasible',
    {
      instance: { ...ASSIGNMENT, handlers: [ASSIGNMENT.handlers[0]] },
      result: {
        status: 'infeasible',
        objective: null,
        bound: null,
        gap: null,
        solution: {},
        iis: ['cover[0]', 'cover[1]', 'no_overlap[h0,t0,t1]'],
      },
    },
    [
      'No schedule can satisfy every rule.',
      "H0 can't do both T0 (06:00-06:40) and T1 (06:20-07:00)",
      'less than 10 minutes apart',
    ],
  ],
  [
    'interrupted',
    {
      result: {
        status: 'interrupted',
        objective: 30,
        bound: 0,
        gap: 1,
        solution: SOLUTION,
        iis: [],
      },
    },
    ['Cancelled. This is the best found before the cancel, if any.', '100.00%'],
  ],
]

it.each(RESULTS)('shows a finished %s run', async (_status, overrides, texts) => {
  fakeApi({ [`GET ${PATH}`]: { body: run(overrides) } })
  render(<RunPage id={ID} />)
  for (const text of texts)
    expect(await screen.findByText(text, { exact: false })).toBeInTheDocument()
  expect(FakeEventSource.last).toBeNull()
})

it('shows why a run failed', async () => {
  fakeApi({
    [`GET ${PATH}`]: {
      body: run({ state: 'failed', error: 'Gurobi stopped with status code 12' }),
    },
  })
  render(<RunPage id={ID} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Gurobi stopped with status code 12')
})

it('shows a coverage run as a roster against demand', async () => {
  const instance = {
    demand: [1, 2, 1],
    patterns: [
      { id: 0, start: 0, length: 3, break_slot: null },
      { id: 1, start: 1, length: 1, break_slot: null },
    ],
  }
  const result = {
    status: 'optimal' as const,
    objective: 4,
    bound: 4,
    gap: 0,
    solution: { '0': 1, '1': 1 },
    iis: [],
  }
  fakeApi({ [`GET ${PATH}`]: { body: run({ model: 'coverage', instance, result }) } })
  render(<RunPage id={ID} />)
  expect(await screen.findByText('1 × 00:00-01:30')).toBeInTheDocument()
  expect(screen.getByRole('img')).toHaveAccessibleName(
    /0 slots short, 0 with more people than needed/,
  )
})

it('links an exported run to Grafana', async () => {
  fakeApi({ [`GET ${PATH}`]: { body: run({ exported: true, result: RESULTS[0][1].result! }) } })
  render(<RunPage id={ID} />)
  const link = await screen.findByRole('link', { name: 'Open this run in Grafana' })
  expect(new URL(link.getAttribute('href')!).searchParams.get('var-run_id')).toBe(ID)
})

it('when the stream is lost, shows what the API says about the run', async () => {
  let view: { status?: number; body: unknown } = { body: run({ state: 'running', ended_at: null }) }
  fakeApi({ [`GET ${PATH}`]: () => view })
  render(<RunPage id={ID} />)
  expect(await screen.findByText('Solving…')).toBeInTheDocument()
  view = { status: 404, body: { detail: `there is no run ${ID}` } }
  act(() => FakeEventSource.last!.fail())
  expect(await screen.findByRole('alert')).toHaveTextContent(`there is no run ${ID}`)
})

it('shows why a cancel failed and lets it be tried again', async () => {
  fakeApi({
    [`GET ${PATH}`]: { body: run({ state: 'running', ended_at: null }) },
    [`POST ${PATH}/cancel`]: { status: 409, body: { detail: `run ${ID} has already ended` } },
  })
  render(<RunPage id={ID} />)
  await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    `Cancel failed: run ${ID} has already ended`,
  )
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled()
})

it('shows a missing run as an error', async () => {
  fakeApi({ [`GET ${PATH}`]: { status: 404, body: { detail: `there is no run ${ID}` } } })
  render(<RunPage id={ID} />)
  expect(await screen.findByRole('alert')).toHaveTextContent(`there is no run ${ID}`)
})
