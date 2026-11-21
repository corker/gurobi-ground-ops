import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { fakeApi, run } from './fakes'
import { NewRun } from './NewRun'

afterEach(() => {
  vi.unstubAllGlobals()
  history.replaceState(null, '', '/')
})

function sentBody(fetch: ReturnType<typeof fakeApi>): unknown {
  return JSON.parse(fetch.mock.calls[0][1]!.body as string)
}

it('starts a Model 1 run with the form values and opens its page', async () => {
  const fetch = fakeApi({
    'POST /api/runs': { status: 202, body: run({ id: 'r-7', state: 'running' }) },
  })
  render(<NewRun />)
  await userEvent.clear(screen.getByLabelText(/Tasks/))
  await userEvent.type(screen.getByLabelText(/Tasks/), '40')
  await userEvent.click(screen.getByLabelText(/Expose the search/))
  await userEvent.type(screen.getByLabelText(/Work limit/), '0.5')
  await userEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(sentBody(fetch)).toEqual({
    model: 'assignment',
    tasks: 40,
    handlers: null,
    seed: 1,
    expose_search: true,
    work_limit: 0.5,
  })
  expect(location.pathname).toBe('/runs/r-7')
})

it('a Model 2 run sends no task or handler count', async () => {
  const fetch = fakeApi({
    'POST /api/runs': { status: 202, body: run({ id: 'r-8', model: 'coverage' }) },
  })
  render(<NewRun />)
  await userEvent.click(screen.getByLabelText(/Model 2/))
  expect(screen.queryByLabelText(/Tasks/)).toBeNull()
  await userEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(sentBody(fetch)).toEqual({
    model: 'coverage',
    seed: 1,
    expose_search: false,
    work_limit: null,
  })
})

it('an empty seed leaves the seed to the API default', async () => {
  const fetch = fakeApi({ 'POST /api/runs': { status: 202, body: run({ id: 'r-9' }) } })
  render(<NewRun />)
  await userEvent.clear(screen.getByLabelText(/Seed/))
  await userEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(sentBody(fetch)).not.toHaveProperty('seed')
})

it.each([
  [429, { detail: 'all 2 workers are busy; try again when a run ends' }, 'all 2 workers are busy'],
  [
    422,
    { detail: [{ loc: ['body', 'tasks'], msg: 'Input should be less than or equal to 2000' }] },
    'tasks: Input should be less than or equal to 2000',
  ],
])('shows the API refusal %i and stays on the form', async (status, body, text) => {
  fakeApi({ 'POST /api/runs': { status, body } })
  render(<NewRun />)
  await userEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(text)
  expect(location.pathname).toBe('/')
  expect(screen.getByRole('button', { name: 'Start' })).toBeEnabled()
})
