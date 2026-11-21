import { afterEach, expect, it, vi } from 'vitest'
import { ApiError, getRun } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

it('reports a non-JSON error response by its status', async () => {
  vi.stubGlobal('fetch', async () => new Response('Internal Server Error', { status: 500 }))
  await expect(getRun('r-1')).rejects.toThrow(new ApiError(500, 'the API answered 500'))
})

it('reports an API that cannot be reached', async () => {
  vi.stubGlobal('fetch', async () => {
    throw new TypeError('Failed to fetch')
  })
  await expect(getRun('r-1')).rejects.toThrow("can't reach the API")
})
