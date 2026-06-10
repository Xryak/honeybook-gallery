import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GalleryView from '../../src/views/GalleryView.vue'
import { writeSession } from '../../src/composables/useSession'

// GalleryView only needs the route param; stub the rest of vue-router.
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'g_001' } }),
}))

const OtpStub = { name: 'OtpEntry', template: '<div class="otp-stub" />', emits: ['verified'] }
const GridStub = {
  name: 'GalleryGrid',
  template: '<div class="grid-stub" />',
  emits: ['session-expired'],
}

function mountView() {
  return mount(GalleryView, {
    global: { stubs: { OtpEntry: OtpStub, GalleryGrid: GridStub } },
  })
}

describe('GalleryView auth gating', () => {
  beforeEach(() => localStorage.clear())

  it('shows the OTP entry when there is no valid session', () => {
    const w = mountView()
    expect(w.find('.otp-stub').exists()).toBe(true)
    expect(w.find('.grid-stub').exists()).toBe(false)
  })

  it('shows the gallery grid when a valid session exists', () => {
    writeSession('g_001', 'tok', 600)
    const w = mountView()
    expect(w.find('.grid-stub').exists()).toBe(true)
    expect(w.find('.otp-stub').exists()).toBe(false)
  })

  it('switches from OTP to grid after a verified session is written', async () => {
    const w = mountView()
    writeSession('g_001', 'tok', 600) // OtpEntry would have done this before emitting
    w.findComponent(OtpStub).vm.$emit('verified')
    await flushPromises()
    expect(w.find('.grid-stub').exists()).toBe(true)
  })

  it('clears the token and returns to OTP when the grid reports an expired session', async () => {
    writeSession('g_001', 'tok', 600)
    const w = mountView()
    expect(w.find('.grid-stub').exists()).toBe(true)

    w.findComponent(GridStub).vm.$emit('session-expired')
    await flushPromises()
    expect(w.find('.otp-stub').exists()).toBe(true)
    expect(localStorage.getItem('honeybook:session:g_001')).toBeNull()
  })
})
