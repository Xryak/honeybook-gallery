// Typed fetch wrapper around the Honeybook API.
//
// All paths are server-relative (`/api/...`). The Vite proxy (added by
// Session C) forwards `/api/*` to the backend on `:8000`. The wrapper:
//   - Attaches `Authorization: Bearer <token>` when a session exists for the
//     gallery being addressed.
//   - Discriminates 2xx from non-2xx into a typed `Result` union so call sites
//     handle errors without try/catch and the compiler reminds them of the
//     three documented error codes.

import type { components } from '../types/api'
import { hasValidSession, readSession } from '../composables/useSession'

export type Gallery = components['schemas']['Gallery']
export type Photo = components['schemas']['Photo']
export type ApiErrorCode = components['schemas']['Error']['error']

export type ApiError =
  | { kind: 'http'; status: number; code: ApiErrorCode | 'unknown' }
  | { kind: 'network' }

export type Result<T> = { ok: true; data: T } | { ok: false; error: ApiError }

async function request<T>(
  path: string,
  init: RequestInit,
  galleryId: string | null,
): Promise<Result<T>> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  // Only attach a *live* token — `hasValidSession` also clears a past-expiry
  // entry, so "do we have auth?" is answered the same way here and in the
  // route-gating logic (no expired token is ever sent).
  if (galleryId && hasValidSession(galleryId)) {
    const session = readSession(galleryId)
    if (session) {
      headers.set('Authorization', `Bearer ${session.token}`)
    }
  }

  let response: Response
  try {
    response = await fetch(path, { ...init, headers })
  } catch {
    return { ok: false, error: { kind: 'network' } }
  }

  if (response.ok) {
    // 204 No Content is not used by this API, but be defensive.
    if (response.status === 204) {
      return { ok: true, data: undefined as unknown as T }
    }
    const data = (await response.json()) as T
    return { ok: true, data }
  }

  let code: ApiErrorCode | 'unknown' = 'unknown'
  try {
    const body = (await response.json()) as { error?: string }
    if (body.error === 'invalid_code' || body.error === 'expired_session' || body.error === 'not_found') {
      code = body.error
    }
  } catch {
    // body was not JSON or was empty; leave code as 'unknown'.
  }

  return { ok: false, error: { kind: 'http', status: response.status, code } }
}

// --- typed endpoint wrappers -------------------------------------------------

export interface OtpResponse {
  expires_in: number
}

export function requestOtp(galleryId: string): Promise<Result<OtpResponse>> {
  return request<OtpResponse>(
    `/api/galleries/${encodeURIComponent(galleryId)}/otp`,
    { method: 'POST' },
    null,
  )
}

export interface VerifyResponse {
  token: string
  expires_in: number
}

export function verifyOtp(galleryId: string, code: string): Promise<Result<VerifyResponse>> {
  return request<VerifyResponse>(
    `/api/galleries/${encodeURIComponent(galleryId)}/verify`,
    { method: 'POST', body: JSON.stringify({ code }) },
    null,
  )
}

export function fetchGallery(galleryId: string): Promise<Result<Gallery>> {
  return request<Gallery>(
    `/api/galleries/${encodeURIComponent(galleryId)}`,
    { method: 'GET' },
    galleryId,
  )
}

export interface FavoriteResponse {
  photo_id: string
  is_favorite: boolean
}

export function toggleFavorite(
  galleryId: string,
  photoId: string,
): Promise<Result<FavoriteResponse>> {
  return request<FavoriteResponse>(
    `/api/galleries/${encodeURIComponent(galleryId)}/favourite`,
    { method: 'POST', body: JSON.stringify({ photo_id: photoId }) },
    galleryId,
  )
}
