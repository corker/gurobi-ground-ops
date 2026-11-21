import type { components } from './api.gen'

export type Schemas = components['schemas']
export type RunView = Schemas['RunView']
export type RunRequest = Schemas['RunRequest']
export type Progress = Schemas['Progress']
export type Finished = Schemas['Finished']

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type ErrorBody = { detail?: string | { msg: string; loc: (string | number)[] }[] }

function message(body: ErrorBody, status: number): string {
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail))
    return body.detail.map((e) => `${e.loc.at(-1)}: ${e.msg}`).join('; ')
  return `the API answered ${status}`
}

function parse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return {}
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init).catch(() => {
    throw new ApiError(0, "can't reach the API; is `ground-ops serve` running?")
  })
  const text = await response.text()
  if (!response.ok)
    throw new ApiError(response.status, message(parse(text) as ErrorBody, response.status))
  return JSON.parse(text) as T
}

/** The message to show for anything a request or a handler throws. */
export function describe(failure: unknown): string {
  return failure instanceof Error ? failure.message : String(failure)
}

export function startRun(run: RunRequest): Promise<RunView> {
  return request('/api/runs', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(run),
  })
}

export function getRun(id: string): Promise<RunView> {
  return request(`/api/runs/${encodeURIComponent(id)}`)
}

export function cancelRun(id: string): Promise<RunView> {
  return request(`/api/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' })
}

/**
 * Follow a run's event stream. The schema types the payloads (Progress | Finished) but not which event carries
 * which, so this is the one place that links them. The stream is closed on `done`: a browser reconnects to a
 * closed stream by itself otherwise. `lost` is called when the browser gives up on the stream, for example after
 * the server restarted and forgot the run. Returns a function that stops following.
 */
export function followRun(
  id: string,
  on: {
    progress: (sample: Progress) => void
    done: (finished: Finished) => void
    lost: () => void
  },
): () => void {
  const source = new EventSource(`/api/runs/${encodeURIComponent(id)}/events`)
  source.addEventListener('progress', (event) => {
    on.progress(JSON.parse((event as MessageEvent<string>).data) as Progress)
  })
  source.addEventListener('done', (event) => {
    source.close()
    on.done(JSON.parse((event as MessageEvent<string>).data) as Finished)
  })
  source.addEventListener('error', () => {
    if (source.readyState === EventSource.CLOSED) on.lost()
  })
  return () => source.close()
}
