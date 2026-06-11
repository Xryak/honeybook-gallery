import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GalleryGrid from '../../src/components/GalleryGrid.vue'

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response
}

const photo = (id: string, fav: boolean) => ({
  id,
  thumbnail_url: `/static/photos/thumb/${id}.jpg`,
  full_url: `/static/photos/full/${id}.jpg`,
  is_favorite: fav,
})

const GALLERY = {
  id: 'g_001',
  title: "Anna's Wedding",
  photos: [photo('p_001', false), photo('p_002', false), photo('p_003', true)],
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  localStorage.clear()
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

/** Route GET (gallery) and POST (favourite) responses independently. */
function routeFetch(handlers: {
  gallery?: () => Response
  favourite?: (photoId: string) => Response
}) {
  fetchMock.mockImplementation(async (path: string, init: RequestInit = {}) => {
    const method = (init.method ?? 'GET').toUpperCase()
    if (method === 'GET' && handlers.gallery) return handlers.gallery()
    if (method === 'POST' && handlers.favourite) {
      const body = JSON.parse(String(init.body))
      return handlers.favourite(body.photo_id)
    }
    throw new Error(`unexpected ${method} ${path}`)
  })
}

async function mountLoaded() {
  routeFetch({
    gallery: () => jsonResponse(200, structuredClone(GALLERY)),
    favourite: (photoId) => jsonResponse(200, { photo_id: photoId, is_favorite: true }),
  })
  const w = mount(GalleryGrid, { props: { galleryId: 'g_001' } })
  await flushPromises()
  return w
}

describe('GalleryGrid', () => {
  it('renders the gallery title and one tile per photo', async () => {
    const w = await mountLoaded()
    expect(w.find('h1').text()).toBe("Anna's Wedding")
    expect(w.findAll('.tile')).toHaveLength(3)
  })

  it('reflects server favorite state on first render', async () => {
    const w = await mountLoaded()
    const tiles = w.findAll('.tile')
    expect(tiles[2].classes()).toContain('is-favorite') // p_003 seeded favorite
    expect(tiles[0].classes()).not.toContain('is-favorite')
  })

  it('clicking a photo favorites it (optimistic + server reconcile)', async () => {
    const w = await mountLoaded()
    const tile = w.findAll('.tile')[0]
    await tile.trigger('click')
    await flushPromises()
    expect(tile.classes()).toContain('is-favorite')
    expect(tile.attributes('aria-pressed')).toBe('true')
  })

  it('clicking a favorited photo removes the favorite', async () => {
    routeFetch({
      gallery: () => jsonResponse(200, structuredClone(GALLERY)),
      favourite: (photoId) => jsonResponse(200, { photo_id: photoId, is_favorite: false }),
    })
    const w = mount(GalleryGrid, { props: { galleryId: 'g_001' } })
    await flushPromises()
    const fav = w.findAll('.tile')[2] // p_003 starts favorited
    await fav.trigger('click')
    await flushPromises()
    expect(fav.classes()).not.toContain('is-favorite')
  })

  it('emits session-expired and renders no tiles when the load 401s', async () => {
    routeFetch({ gallery: () => jsonResponse(401, { error: 'expired_session' }) })
    const w = mount(GalleryGrid, { props: { galleryId: 'g_001' } })
    await flushPromises()
    expect(w.emitted('session-expired')).toBeTruthy()
    expect(w.findAll('.tile')).toHaveLength(0)
  })

  it('reverts the optimistic flip and emits session-expired when a toggle 401s', async () => {
    routeFetch({
      gallery: () => jsonResponse(200, structuredClone(GALLERY)),
      favourite: () => jsonResponse(401, { error: 'expired_session' }),
    })
    const w = mount(GalleryGrid, { props: { galleryId: 'g_001' } })
    await flushPromises()

    const tile = w.findAll('.tile')[0]
    await tile.trigger('click')
    await flushPromises()

    expect(tile.classes()).not.toContain('is-favorite') // reverted
    expect(w.emitted('session-expired')).toBeTruthy()
  })

  it('renders the lightweight thumbnail variant in the grid', async () => {
    const w = await mountLoaded()
    const img = w.findAll('.tile img')[0]
    expect(img.attributes('src')).toBe('/static/photos/thumb/p_001.jpg')
  })

  it('expand opens a lightbox with the full-size variant and does not favorite', async () => {
    const w = await mountLoaded()
    expect(w.find('.lightbox').exists()).toBe(false)

    await w.findAll('.expand')[0].trigger('click')

    const lightbox = w.find('.lightbox')
    expect(lightbox.exists()).toBe(true)
    expect(lightbox.find('img').attributes('src')).toBe('/static/photos/full/p_001.jpg')
    // Opening the lightbox must not toggle the favorite.
    expect(w.findAll('.tile')[0].classes()).not.toContain('is-favorite')
  })

  it('clicking the lightbox closes it', async () => {
    const w = await mountLoaded()
    await w.findAll('.expand')[0].trigger('click')
    await w.find('.lightbox').trigger('click')
    expect(w.find('.lightbox').exists()).toBe(false)
  })
})
