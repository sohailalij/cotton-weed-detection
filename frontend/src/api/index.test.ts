// @vitest-environment node

import { describe, expect, it, vi } from 'vitest'

import { ApiError, createApi } from './index'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function makeApi(respond: () => Response) {
  const calls: Request[] = []
  const mock = vi.fn(async (input: Request) => {
    calls.push(input)
    return respond()
  })
  return { api: createApi('http://api.test', mock as unknown as typeof fetch), calls }
}

describe('api client', () => {
  it('calls /health and returns typed data', async () => {
    const { api, calls } = makeApi(() => jsonResponse({ status: 'ok', model_loaded: true }))
    const result = await api.health()
    expect(result.model_loaded).toBe(true)
    expect(new URL(calls[0].url).pathname).toBe('/health')
  })

  it('sends the file as multipart and omits conf when not given', async () => {
    const { api, calls } = makeApi(() =>
      jsonResponse({ id: 7, count: 1, box_coverage: 0.1, counts_by_class: { waterhemp: 1 } }),
    )
    const file = new File(['abc'], 'photo.jpg', { type: 'image/jpeg' })
    const result = await api.detect(file)
    expect(result.id).toBe(7)
    const request = calls[0]
    expect(request.method).toBe('POST')
    expect(new URL(request.url).search).toBe('')
    expect(request.headers.get('content-type')).toMatch(/^multipart\/form-data; boundary=/)
    const form = await request.formData()
    const sent = form.get('file') as File
    expect(sent.name).toBe('photo.jpg')
    expect(await sent.text()).toBe('abc')
  })

  it('passes conf as a query parameter', async () => {
    const { api, calls } = makeApi(() =>
      jsonResponse({ id: 1, count: 0, box_coverage: 0, counts_by_class: {} }),
    )
    await api.detect(new File(['x'], 'a.jpg'), 0.4)
    expect(new URL(calls[0].url).searchParams.get('conf')).toBe('0.4')
  })

  it('builds the detection history query and path parameters', async () => {
    const { api, calls } = makeApi(() => jsonResponse({ items: [], total: 0, limit: 5, offset: 10 }))
    await api.detections(5, 10)
    const url = new URL(calls[0].url)
    expect(url.pathname).toBe('/v1/detections')
    expect(url.searchParams.get('limit')).toBe('5')
    expect(url.searchParams.get('offset')).toBe('10')
  })

  it('turns an API error with a text detail into an ApiError', async () => {
    const { api } = makeApi(() => jsonResponse({ detail: 'file is not a readable image' }, 400))
    const error = await api.detect(new File(['x'], 'a.txt')).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(400)
    expect((error as ApiError).message).toBe('file is not a readable image')
  })

  it('joins validation messages from a 422 response', async () => {
    const { api } = makeApi(() =>
      jsonResponse({ detail: [{ loc: ['query', 'conf'], msg: 'too big', type: 'x' }] }, 422),
    )
    const error = await api.detect(new File(['x'], 'a.jpg'), 5).catch((e: unknown) => e)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).message).toBe('too big')
  })

  it('deletes a detection and treats 204 as success', async () => {
    const { api, calls } = makeApi(() => new Response(null, { status: 204 }))
    await expect(api.remove(5)).resolves.toBeUndefined()
    expect(calls[0].method).toBe('DELETE')
    expect(new URL(calls[0].url).pathname).toBe('/v1/detections/5')
  })

  it('turns a failed delete into an ApiError', async () => {
    const { api } = makeApi(() => jsonResponse({ detail: 'detection not found' }, 404))
    const error = await api.remove(5).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
    expect((error as ApiError).message).toBe('detection not found')
  })

  it('builds image URLs without a double slash', () => {
    expect(createApi('http://api.test/').imageUrl(7)).toBe('http://api.test/v1/detections/7/image')
  })

  it('asks for the daily series, with and without a date range', async () => {
    const { api, calls } = makeApi(() => jsonResponse({ start: null, end: null, days: [] }))
    const result = await api.statsDaily()
    expect(result.days).toEqual([])
    expect(new URL(calls[0].url).pathname).toBe('/v1/stats/daily')
    expect(new URL(calls[0].url).search).toBe('')
    await api.statsDaily('2026-10-01T00:00:00Z', '2026-10-31T00:00:00Z')
    const query = new URL(calls[1].url).searchParams
    expect(query.get('start')).toBe('2026-10-01T00:00:00Z')
    expect(query.get('end')).toBe('2026-10-31T00:00:00Z')
  })
})