import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './api'

function mockFetch(status = 200, body: unknown = {}) {
  const mock = vi.fn(async () => new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', mock)
  return mock
}

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('always sends Content-Type: application/json on POSTs, even with no custom headers', async () => {
    // Regression: `...init` spread after the headers merge let an undefined
    // init.headers erase Content-Type, so browsers sent JSON as text/plain
    // and FastAPI rejected every body with "should be a valid dictionary".
    const fetchMock = mockFetch()
    await api.post('/api/thing', { a: 1 })
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"a":1}')
  })

  it('keeps custom headers alongside the JSON content type', async () => {
    const fetchMock = mockFetch()
    await api.get('/api/care/queue', { 'X-Care-Team': 'nurse-rivera' })
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    const headers = init.headers as Record<string, string>
    expect(headers['X-Care-Team']).toBe('nurse-rivera')
    expect(headers['Content-Type']).toBe('application/json')
  })

  it('surfaces string error details from the server', async () => {
    mockFetch(409, { detail: 'Enrollment already completed.' })
    await expect(api.post('/api/thing')).rejects.toThrow('Enrollment already completed.')
  })

  it('formats FastAPI validation errors (list details) into readable messages', async () => {
    mockFetch(422, {
      detail: [{ loc: ['body', 'email'], msg: 'value is not a valid email address' }],
    })
    await expect(api.post('/api/thing', {})).rejects.toThrow(
      'email: value is not a valid email address',
    )
  })
})
