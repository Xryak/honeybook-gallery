import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  fetchGallery,
  requestOtp,
  toggleFavorite,
  verifyOtp,
} from '../../src/api/client'
import { writeSession } from '../../src/composables/useSession'

/** Minimal Response stand-in for the fetch wrapper. */
function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  localStorage.clear()
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

describe('api client — requests', () => {
  it('requestOtp POSTs to the OTP path with no auth header', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { expires_in: 600 }))
    const res = await requestOtp('g_001')

    expect(res).toEqual({ ok: true, data: { expires_in: 600 } })
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/galleries/g_001/otp')
    expect(init.method).toBe('POST')
    expect(new Headers(init.headers).get('Authorization')).toBeNull()
  })

  it('verifyOtp sends the code in the body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { token: 'T', expires_in: 600 }))
    const res = await verifyOtp('g_001', '123456')

    expect(res).toEqual({ ok: true, data: { token: 'T', expires_in: 600 } })
    const [, init] = fetchMock.mock.calls[0]
    expect(JSON.parse(init.body)).toEqual({ code: '123456' })
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
  })

  it('attaches the bearer token when a session exists for the gallery', async () => {
    writeSession('g_001', 'secret-token', 600)
    fetchMock.mockResolvedValue(jsonResponse(200, { id: 'g_001', title: 'x', photos: [] }))
    await fetchGallery('g_001')

    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer secret-token')
  })

  it('omits the bearer header when no session exists', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { id: 'g_001', title: 'x', photos: [] }))
    await fetchGallery('g_001')
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBeNull()
  })

  it('toggleFavorite posts the photo_id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { photo_id: 'p_001', is_favorite: true }))
    const res = await toggleFavorite('g_001', 'p_001')
    expect(res).toEqual({ ok: true, data: { photo_id: 'p_001', is_favorite: true } })
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/galleries/g_001/favourite')
    expect(JSON.parse(init.body)).toEqual({ photo_id: 'p_001' })
  })
})

describe('api client — error mapping', () => {
  it('maps a known error code from a non-2xx body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { error: 'invalid_code' }))
    const res = await verifyOtp('g_001', '000000')
    expect(res).toEqual({
      ok: false,
      error: { kind: 'http', status: 401, code: 'invalid_code' },
    })
  })

  it('maps not_found', async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { error: 'not_found' }))
    const res = await fetchGallery('g_404')
    expect(res).toMatchObject({ ok: false, error: { status: 404, code: 'not_found' } })
  })

  it('falls back to "unknown" for an unrecognized error code', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, { error: 'kaboom' }))
    const res = await fetchGallery('g_001')
    expect(res).toMatchObject({ ok: false, error: { status: 500, code: 'unknown' } })
  })

  it('falls back to "unknown" when the error body is not JSON', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('not json')
      },
    } as unknown as Response)
    const res = await fetchGallery('g_001')
    expect(res).toMatchObject({ ok: false, error: { kind: 'http', code: 'unknown' } })
  })

  it('returns a network error when fetch rejects', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const res = await fetchGallery('g_001')
    expect(res).toEqual({ ok: false, error: { kind: 'network' } })
  })
})
