<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchGallery, toggleFavorite, type Gallery, type Photo } from '../api/client'

const props = defineProps<{ galleryId: string }>()
const emit = defineEmits<{ (e: 'session-expired'): void }>()

const gallery = ref<Gallery | null>(null)
const loadError = ref<string | null>(null)
const loading = ref(true)
// Tracks which photo ids have an in-flight favorite toggle, so we don't
// double-fire on rapid clicks. Each click optimistically flips the local
// state and reconciles to the server's authoritative response.
const pending = ref<Set<string>>(new Set())

async function load() {
  loading.value = true
  loadError.value = null
  const result = await fetchGallery(props.galleryId)
  loading.value = false

  if (result.ok) {
    gallery.value = result.data
    return
  }

  if (result.error.kind === 'http' && result.error.status === 401) {
    emit('session-expired')
    return
  }

  if (result.error.kind === 'network') {
    loadError.value = "Couldn't reach the server."
  } else if (result.error.code === 'not_found') {
    loadError.value = 'Gallery not found.'
  } else {
    loadError.value = 'Something went wrong loading this gallery.'
  }
}

async function onPhotoClick(photo: Photo) {
  // The backend /favourite is a blind server-side toggle, so this is correct
  // under a single-writer (single-tab) assumption. A production version would
  // send the desired target state (PUT { is_favorite }) so client intent — not
  // server parity — decides the outcome across concurrent tabs.
  if (pending.value.has(photo.id)) return
  pending.value.add(photo.id)

  // Optimistic flip so the click feels instant.
  const original = photo.is_favorite
  photo.is_favorite = !original

  const result = await toggleFavorite(props.galleryId, photo.id)

  pending.value.delete(photo.id)

  if (result.ok) {
    photo.is_favorite = result.data.is_favorite
    return
  }

  // Revert on failure.
  photo.is_favorite = original

  if (result.error.kind === 'http' && result.error.status === 401) {
    emit('session-expired')
  }
  // Silent for other errors at this layer — a small toast would be nicer but
  // is out of scope for the mock.
}

onMounted(load)
</script>

<template>
  <section class="grid-view">
    <header class="header">
      <h1 v-if="gallery">{{ gallery.title }}</h1>
      <h1 v-else-if="loading">Loading…</h1>
      <h1 v-else>Gallery</h1>
    </header>

    <p v-if="loadError" class="error" role="alert">{{ loadError }}</p>

    <div v-if="gallery" class="grid">
      <button
        v-for="photo in gallery.photos"
        :key="photo.id"
        type="button"
        class="tile"
        :class="{ 'is-favorite': photo.is_favorite }"
        :aria-pressed="photo.is_favorite"
        :aria-label="`Photo ${photo.id}${photo.is_favorite ? ' (favorited)' : ''}`"
        @click="onPhotoClick(photo)"
      >
        <img :src="photo.thumbnail_url" :alt="photo.id" loading="lazy" />
        <span class="heart" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="22" height="22">
            <path
              d="M12 21s-7-4.35-9.5-9.5C1 8 3 4 7 4c2 0 3.5 1 5 3 1.5-2 3-3 5-3 4 0 6 4 4.5 7.5C19 16.65 12 21 12 21z"
            />
          </svg>
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.grid-view {
  max-width: 72rem;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
  font-family: system-ui, -apple-system, sans-serif;
}
.header {
  margin-bottom: 1.5rem;
}
h1 {
  font-weight: 300;
  font-size: 1.75rem;
  letter-spacing: -0.01em;
  margin: 0;
}
.error {
  color: #c0392b;
  background: #fff4f4;
  border: 1px solid #f5c6cb;
  padding: 0.75rem 1rem;
  border-radius: 6px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
}
.tile {
  position: relative;
  aspect-ratio: 4 / 3;
  border: 2px solid transparent;
  border-radius: 8px;
  overflow: hidden;
  padding: 0;
  background: #f4f4f4;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
.tile:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
.tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.heart {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 50%;
  backdrop-filter: blur(4px);
  transition: transform 0.15s ease;
}
.heart svg {
  fill: none;
  stroke: #333;
  stroke-width: 2;
  transition: fill 0.15s ease, stroke 0.15s ease, transform 0.2s ease;
}
.tile.is-favorite {
  border-color: #e0245e;
  box-shadow: 0 0 0 1px #e0245e;
}
.tile.is-favorite .heart svg {
  fill: #e0245e;
  stroke: #e0245e;
  transform: scale(1.1);
}
</style>
