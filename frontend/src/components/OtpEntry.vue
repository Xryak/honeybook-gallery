<script setup lang="ts">
import { computed, ref } from 'vue'
import { verifyOtp } from '../api/client'
import { writeSession } from '../composables/useSession'

const props = defineProps<{ galleryId: string }>()
const emit = defineEmits<{ (e: 'verified'): void }>()

const code = ref('')
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

const codeIsValid = computed(() => /^[0-9]{6}$/.test(code.value))

function onCodeInput(event: Event) {
  const target = event.target as HTMLInputElement
  // Strip non-digits and cap at 6.
  const digitsOnly = target.value.replace(/\D/g, '').slice(0, 6)
  code.value = digitsOnly
  target.value = digitsOnly
  errorMessage.value = null
}

async function submit() {
  if (!codeIsValid.value || submitting.value) return
  submitting.value = true
  errorMessage.value = null

  const result = await verifyOtp(props.galleryId, code.value)
  submitting.value = false

  if (result.ok) {
    writeSession(props.galleryId, result.data.token, result.data.expires_in)
    emit('verified')
    return
  }

  if (result.error.kind === 'network') {
    errorMessage.value = "Couldn't reach the server. Try again."
    return
  }

  if (result.error.status === 401) {
    errorMessage.value = "That code didn't work. Try again."
  } else if (result.error.code === 'not_found') {
    errorMessage.value = 'No such gallery.'
  } else {
    errorMessage.value = 'Something went wrong. Try again.'
  }
}
</script>

<template>
  <section class="otp">
    <div class="card">
      <h1>Enter your code</h1>
      <p class="subtitle">
        We sent a 6-digit code to view this gallery.
      </p>

      <form @submit.prevent="submit">
        <input
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          :value="code"
          @input="onCodeInput"
          placeholder="123456"
          class="code-input"
          :disabled="submitting"
          autofocus
          aria-label="Six digit verification code"
        />
        <button
          type="submit"
          :disabled="!codeIsValid || submitting"
          class="verify"
        >
          {{ submitting ? 'Verifying…' : 'Verify' }}
        </button>
      </form>

      <p v-if="errorMessage" class="error" role="alert">{{ errorMessage }}</p>

      <p class="dev-hint">
        Dev note: your code was logged to the backend terminal. Run
        <code>make otp GALLERY={{ galleryId }}</code> and copy it from there.
      </p>
    </div>
  </section>
</template>

<style scoped>
.otp {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: #fafafa;
}
.card {
  width: 100%;
  max-width: 26rem;
  background: white;
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 2.25rem 2rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  font-family: system-ui, -apple-system, sans-serif;
}
h1 {
  font-size: 1.5rem;
  font-weight: 400;
  margin: 0 0 0.4rem;
}
.subtitle {
  color: #666;
  margin: 0 0 1.5rem;
  font-size: 0.95rem;
}
form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.code-input {
  font-size: 1.6rem;
  letter-spacing: 0.4em;
  text-align: center;
  padding: 0.75rem 0.5rem;
  border: 1px solid #ddd;
  border-radius: 8px;
  outline: none;
  font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.code-input:focus {
  border-color: #1f6feb;
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.15);
}
.code-input:disabled {
  opacity: 0.6;
}
.verify {
  background: #111;
  color: white;
  border: none;
  padding: 0.75rem;
  font-size: 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.verify:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.verify:not(:disabled):hover {
  opacity: 0.88;
}
.error {
  margin: 1rem 0 0;
  color: #c0392b;
  font-size: 0.9rem;
}
.dev-hint {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px dashed #eee;
  font-size: 0.8rem;
  color: #888;
}
code {
  background: #f4f4f4;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
</style>
