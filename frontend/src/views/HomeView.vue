<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <main class="home">
    <h1>Honeybook Gallery</h1>
    <p>A client gallery preview. Open one of the seeded galleries:</p>
    <ul>
      <li><RouterLink :to="{ name: 'gallery', params: { id: 'g_001' } }">Anna's Wedding (g_001)</RouterLink></li>
      <li><RouterLink :to="{ name: 'gallery', params: { id: 'g_002' } }">Marco's Portrait Session (g_002)</RouterLink></li>
    </ul>
    <p class="hint">
      You'll be prompted for a 6-digit code. Generate one with
      <code>make otp GALLERY=g_001</code> and read it from the backend terminal.
    </p>
  </main>
</template>

<style scoped>
.home {
  max-width: 36rem;
  margin: 4rem auto;
  padding: 0 1.5rem;
  font-family: system-ui, -apple-system, sans-serif;
  line-height: 1.5;
}
h1 {
  font-weight: 300;
  letter-spacing: -0.02em;
  margin-bottom: 0.5rem;
}
ul {
  padding-left: 1.25rem;
}
li {
  margin: 0.4rem 0;
}
a {
  color: #1f6feb;
}
.hint {
  margin-top: 2rem;
  font-size: 0.9rem;
  color: #666;
}
code {
  background: #f4f4f4;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.85rem;
}
</style>
