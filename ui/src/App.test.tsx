import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { fakeApi, run } from './fakes'
import { navigate } from './router'

afterEach(() => {
  vi.unstubAllGlobals()
  history.replaceState(null, '', '/')
})

it('routes / to the form, /runs/<id> to the run, and anything else to a message', async () => {
  fakeApi({ 'GET /api/runs/r-1': { body: run({ id: 'r-1', state: 'failed', error: 'boom' }) } })
  render(<App />)
  expect(screen.getByRole('heading', { name: 'New run' })).toBeInTheDocument()
  act(() => navigate('/runs/r-1'))
  expect(await screen.findByRole('heading', { name: /Run r-1/ })).toBeInTheDocument()
  act(() => navigate('/elsewhere'))
  expect(screen.getByText("There's no page at /elsewhere.")).toBeInTheDocument()
  act(() => navigate('/runs/%E0'))
  expect(screen.getByText("There's no page at /runs/%E0.")).toBeInTheDocument()
  await userEvent.click(screen.getByRole('link', { name: 'ground-ops' }))
  expect(screen.getByRole('heading', { name: 'New run' })).toBeInTheDocument()
})
