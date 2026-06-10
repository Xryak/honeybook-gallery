<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import OtpEntry from '../components/OtpEntry.vue'
import GalleryGrid from '../components/GalleryGrid.vue'
import { hasValidSession, clearSession } from '../composables/useSession'

const route = useRoute()
const galleryId = computed(() => String(route.params.id))

// `authToken` is just a re-render trigger: it's bumped whenever auth state
// changes (verify success, 401 elsewhere). The actual token lives in
// localStorage; the components consult `hasValidSession` against the current
// gallery id on each render.
const authVersion = ref(0)
const isAuthed = computed(() => {
  // re-read on each bump
  void authVersion.value
  return hasValidSession(galleryId.value)
})

function onVerified() {
  authVersion.value++
}

function onSessionExpired() {
  clearSession(galleryId.value)
  authVersion.value++
}
</script>

<template>
  <main class="gallery-view">
    <OtpEntry
      v-if="!isAuthed"
      :key="`otp-${galleryId}`"
      :gallery-id="galleryId"
      @verified="onVerified"
    />
    <GalleryGrid
      v-else
      :key="`grid-${galleryId}`"
      :gallery-id="galleryId"
      @session-expired="onSessionExpired"
    />
  </main>
</template>

<style scoped>
.gallery-view {
  min-height: 100vh;
}
</style>
