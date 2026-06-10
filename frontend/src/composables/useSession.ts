// Per-gallery session token storage backed by localStorage.
//
// Keyed by gallery id so two galleries' tokens coexist (open `/galleries/g_001`
// and `/galleries/g_002` in two tabs and each maintains its own auth state).
//
// Stores `expires_at` as an absolute epoch-ms timestamp computed from the
// server's `expires_in` at the moment of mint. We treat a stored token as
// invalid as soon as its `expires_at` is in the past — no need to round-trip
// to the server to learn it's stale.

const KEY_PREFIX = 'honeybook:session:'

export interface StoredSession {
  token: string
  expires_at: number // epoch ms
}

function key(galleryId: string): string {
  return `${KEY_PREFIX}${galleryId}`
}

export function readSession(galleryId: string): StoredSession | null {
  const raw = localStorage.getItem(key(galleryId))
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as StoredSession
    if (typeof parsed.token !== 'string' || typeof parsed.expires_at !== 'number') {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function writeSession(galleryId: string, token: string, expiresInSeconds: number): void {
  const session: StoredSession = {
    token,
    expires_at: Date.now() + expiresInSeconds * 1000,
  }
  localStorage.setItem(key(galleryId), JSON.stringify(session))
}

export function clearSession(galleryId: string): void {
  localStorage.removeItem(key(galleryId))
}

export function hasValidSession(galleryId: string): boolean {
  const session = readSession(galleryId)
  if (!session) return false
  if (session.expires_at <= Date.now()) {
    clearSession(galleryId)
    return false
  }
  return true
}
