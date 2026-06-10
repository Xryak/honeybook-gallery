import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearSession,
  hasValidSession,
  readSession,
  writeSession,
} from '../../src/composables/useSession'

describe('useSession', () => {
  beforeEach(() => localStorage.clear())

  it('round-trips a written session', () => {
    writeSession('g_001', 'tok-abc', 600)
    const s = readSession('g_001')
    expect(s?.token).toBe('tok-abc')
    expect(typeof s?.expires_at).toBe('number')
  })

  it('keys sessions per gallery so they coexist', () => {
    writeSession('g_001', 'tok-1', 600)
    writeSession('g_002', 'tok-2', 600)
    expect(readSession('g_001')?.token).toBe('tok-1')
    expect(readSession('g_002')?.token).toBe('tok-2')
  })

  it('returns null for an absent session', () => {
    expect(readSession('g_999')).toBeNull()
  })

  it('returns null for malformed JSON', () => {
    localStorage.setItem('honeybook:session:g_001', '{not json')
    expect(readSession('g_001')).toBeNull()
  })

  it('returns null when the stored shape is wrong', () => {
    localStorage.setItem('honeybook:session:g_001', JSON.stringify({ token: 123 }))
    expect(readSession('g_001')).toBeNull()
  })

  it('computes expires_at from expires_in at write time', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
    writeSession('g_001', 'tok', 600)
    expect(readSession('g_001')?.expires_at).toBe(1_000_000 + 600 * 1000)
  })

  it('hasValidSession is true within the window, false past expiry', () => {
    const now = 1_000_000
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(now)
    writeSession('g_001', 'tok', 600)
    expect(hasValidSession('g_001')).toBe(true)

    nowSpy.mockReturnValue(now + 601 * 1000) // 1s past expiry
    expect(hasValidSession('g_001')).toBe(false)
  })

  it('hasValidSession clears the token once expired (self-healing)', () => {
    const now = 1_000_000
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(now)
    writeSession('g_001', 'tok', 600)
    nowSpy.mockReturnValue(now + 10_000_000)
    hasValidSession('g_001')
    expect(localStorage.getItem('honeybook:session:g_001')).toBeNull()
  })

  it('clearSession removes only that gallery', () => {
    writeSession('g_001', 'tok-1', 600)
    writeSession('g_002', 'tok-2', 600)
    clearSession('g_001')
    expect(readSession('g_001')).toBeNull()
    expect(readSession('g_002')?.token).toBe('tok-2')
  })
})
