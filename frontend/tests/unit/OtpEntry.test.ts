import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import OtpEntry from '../../src/components/OtpEntry.vue'
import { readSession } from '../../src/composables/useSession'

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

function mountOtp() {
  return mount(OtpEntry, { props: { galleryId: 'g_001' } })
}

describe('OtpEntry', () => {
  it('strips non-digits and caps the input at 6 digits', async () => {
    const w = mountOtp()
    const input = w.find('input')
    await input.setValue('12ab34cd5678')
    expect((input.element as HTMLInputElement).value).toBe('123456')
  })

  it('keeps Verify disabled until exactly 6 digits are present', async () => {
    const w = mountOtp()
    const button = w.find('button[type="submit"]')
    expect(button.attributes('disabled')).toBeDefined()

    await w.find('input').setValue('12345')
    expect(button.attributes('disabled')).toBeDefined()

    await w.find('input').setValue('123456')
    expect(button.attributes('disabled')).toBeUndefined()
  })

  it('on success: stores the session and emits "verified"', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { token: 'tok-xyz', expires_in: 600 }))
    const w = mountOtp()
    await w.find('input').setValue('123456')
    await w.find('form').trigger('submit')
    await flushPromises()

    expect(w.emitted('verified')).toBeTruthy()
    expect(readSession('g_001')?.token).toBe('tok-xyz')
  })

  it('on 401: shows the generic retry message and does not store a session', async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { error: 'invalid_code' }))
    const w = mountOtp()
    await w.find('input').setValue('000000')
    await w.find('form').trigger('submit')
    await flushPromises()

    expect(w.find('.error').text()).toContain("That code didn't work")
    expect(w.emitted('verified')).toBeFalsy()
    expect(readSession('g_001')).toBeNull()
  })

  it('on not_found: shows a no-such-gallery message', async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { error: 'not_found' }))
    const w = mountOtp()
    await w.find('input').setValue('123456')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.error').text()).toContain('No such gallery')
  })

  it('on network failure: shows an unreachable message', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const w = mountOtp()
    await w.find('input').setValue('123456')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.error').text().toLowerCase()).toContain("couldn't reach")
  })
})
