import createClient from 'openapi-fetch'

import type { paths } from './schema'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function describe(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const detail = (error as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === 'object' && item !== null && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : 'invalid value',
        )
        .join('; ')
    }
  }
  return fallback
}

function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data
  throw new ApiError(result.response.status, describe(result.error, result.response.statusText))
}

export function createApi(baseUrl: string, fetchImpl?: typeof fetch) {
  const client = createClient<paths>({ baseUrl, fetch: fetchImpl })

  return {
    async health() {
      return unwrap(await client.GET('/health'))
    },
    async model() {
      return unwrap(await client.GET('/v1/model'))
    },
    async detect(file: File, conf?: number) {
      return unwrap(
        await client.POST('/v1/detect', {
          params: { query: { conf } },
          // The generated type calls the upload a string. The serializer sends the real file.
          body: { file: '' },
          bodySerializer: () => {
            const form = new FormData()
            form.append('file', file)
            return form
          },
        }),
      )
    },
    async detections(limit = 20, offset = 0) {
      return unwrap(await client.GET('/v1/detections', { params: { query: { limit, offset } } }))
    },
    async detection(id: number) {
      return unwrap(
        await client.GET('/v1/detections/{detection_id}', {
          params: { path: { detection_id: id } },
        }),
      )
    },
    async stats(start?: string, end?: string) {
      return unwrap(await client.GET('/v1/stats', { params: { query: { start, end } } }))
    },
  }
}

export const api = createApi(import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000')