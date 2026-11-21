import { vi } from 'vitest'
import type { RunView, Schemas } from './api'

/** jsdom has no EventSource; this one lets a test emit server-sent events by hand. */
export class FakeEventSource {
  static readonly CLOSED = 2
  static last: FakeEventSource | null = null
  readonly url: string
  readyState = 1
  closed = false
  private readonly listeners = new Map<string, (event: MessageEvent<string>) => void>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.last = this
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void {
    this.listeners.set(type, listener)
  }

  close(): void {
    this.closed = true
  }

  /** What a browser does when it gives up on a stream: it closes it, then fires `error`. */
  fail(): void {
    this.readyState = FakeEventSource.CLOSED
    this.listeners.get('error')?.(new MessageEvent('error'))
  }

  emit(type: string, data: unknown): void {
    this.listeners.get(type)?.(new MessageEvent(type, { data: JSON.stringify(data) }))
  }
}

type Route = { status?: number; body: unknown }

/** Answers `fetch` from a table keyed by "METHOD path"; anything else is a test error. */
export function fakeApi(routes: Record<string, Route | (() => Route)>) {
  const fetch = vi.fn(async (path: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${path}`
    const route = routes[key]
    if (!route) throw new Error(`unexpected request ${key}`)
    const { status = 200, body } = typeof route === 'function' ? route() : route
    return new Response(JSON.stringify(body), { status })
  })
  vi.stubGlobal('fetch', fetch)
  vi.stubGlobal('EventSource', FakeEventSource)
  return fetch
}

export const ASSIGNMENT: Schemas['AssignmentInstance'] = {
  tasks: [
    { id: 0, start: 360, end: 400 },
    { id: 1, start: 380, end: 420 },
    { id: 2, start: 590, end: 615 },
  ],
  handlers: [
    { id: 0, shift_start: 360, shift_end: 600 },
    { id: 1, shift_start: 360, shift_end: 600 },
  ],
}

export function run(overrides: Partial<RunView>): RunView {
  return {
    id: '1795214339-57938-1',
    model: 'assignment',
    state: 'done',
    instance: ASSIGNMENT,
    progress: null,
    result: null,
    error: null,
    started_at: 1_795_214_339,
    ended_at: 1_795_214_342,
    exported: false,
    ...overrides,
  }
}

export const PROGRESS: Schemas['Progress'] = {
  elapsed: 1.2,
  work: 0.9,
  incumbent: 30,
  bound: 17,
  gap: 0.4333,
  nodes: 4475,
  iterations: 21000,
  improvements: 2,
}
