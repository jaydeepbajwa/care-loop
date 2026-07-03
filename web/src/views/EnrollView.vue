<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api, ApiError, memberToken } from '../api'
import type { EligibilityAnswers, EnrollmentState } from '../types'

const state = ref<EnrollmentState | null>(null)
const error = ref('')
const saving = ref(false)
const savedAt = ref<Date | null>(null)

// Local working copies of form fields (autosaved on step changes).
// Insurance starts empty so a real choice is required — a pre-selected
// default reads as "answered" to the button gate but not to the user.
const answers = ref<{
  cancer_diagnosis: boolean
  age_18_or_over: boolean
  insurance: EligibilityAnswers['insurance'] | ''
}>({
  cancer_diagnosis: false,
  age_18_or_over: false,
  insurance: '',
})
const answered = ref({ diagnosis: false, age: false })
const contact = ref({
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  contact_preference: 'sms' as 'sms' | 'email' | 'phone',
})

const step = computed(() => state.value?.current_step ?? 'eligibility')
const stepIndex = computed(
  () => ({ eligibility: 0, consent: 1, contact: 2, done: 3, ineligible: 0 })[step.value] ?? 0,
)

onMounted(async () => {
  const token = memberToken.get()
  if (!token) return
  try {
    state.value = await api.get<EnrollmentState>(`/api/enrollment/${token}`)
    hydrate()
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) memberToken.clear()
    else showError(e)
  }
})

function hydrate() {
  const s = state.value
  if (!s) return
  if (s.eligibility_answers) {
    answers.value = s.eligibility_answers
    answered.value = { diagnosis: true, age: true }
  }
  contact.value = {
    first_name: s.first_name ?? '',
    last_name: s.last_name ?? '',
    phone: s.phone ?? '',
    email: s.email ?? '',
    contact_preference: s.contact_preference ?? 'sms',
  }
}

function showError(e: unknown) {
  error.value = e instanceof Error ? e.message : 'Something went wrong. Please try again.'
}

async function start() {
  error.value = ''
  try {
    state.value = await api.post<EnrollmentState>('/api/enrollment/start')
    memberToken.set(state.value.token)
  } catch (e) {
    showError(e)
  }
}

async function autosave(fields: object) {
  const s = state.value
  if (!s) return
  saving.value = true
  try {
    state.value = await api.patch<EnrollmentState>(`/api/enrollment/${s.token}`, fields)
    savedAt.value = new Date()
  } catch {
    /* autosave is best-effort; submission re-sends everything */
  } finally {
    saving.value = false
  }
}

const eligibilityComplete = computed(
  () => answered.value.diagnosis && answered.value.age && answers.value.insurance !== '',
)

async function submitEligibility() {
  const s = state.value
  if (!s) return
  error.value = ''
  try {
    state.value = await api.post<EnrollmentState>(
      `/api/enrollment/${s.token}/eligibility`,
      answers.value,
    )
  } catch (e) {
    showError(e)
  }
}

async function giveConsent() {
  const s = state.value
  if (!s) return
  error.value = ''
  try {
    state.value = await api.post<EnrollmentState>(`/api/enrollment/${s.token}/consent`)
  } catch (e) {
    showError(e)
  }
}

// Mirrors the server's validation closely enough that the button being
// enabled means the submit will succeed (server-side EmailStr needs a
// dotted domain, not just an @).
const contactComplete = computed(
  () =>
    contact.value.first_name.trim() &&
    contact.value.last_name.trim() &&
    contact.value.phone.trim().length >= 7 &&
    /.+@.+\..+/.test(contact.value.email),
)

async function complete() {
  const s = state.value
  if (!s) return
  error.value = ''
  try {
    state.value = await api.post<EnrollmentState>(
      `/api/enrollment/${s.token}/complete`,
      contact.value,
    )
  } catch (e) {
    showError(e)
  }
}

function startOver() {
  memberToken.clear()
  state.value = null
  error.value = ''
}
</script>

<template>
  <h1>Enrollment</h1>

  <p v-if="error" class="notice error" role="alert">{{ error }}</p>

  <!-- Not started -->
  <div v-if="!state" class="card">
    <h2>Let's get you set up</h2>
    <p>
      Three short steps: a few questions to confirm the program is right for you, your
      consent, and how you'd like us to reach you. Your progress saves automatically —
      you can close this page and come back any time.
    </p>
    <button @click="start">Begin — takes about 2 minutes</button>
  </div>

  <template v-else>
    <ol class="steps" aria-label="Enrollment progress">
      <li :class="{ done: stepIndex >= 0 }" />
      <li :class="{ done: stepIndex >= 1 }" />
      <li :class="{ done: stepIndex >= 2 }" />
      <li :class="{ done: stepIndex >= 3 }" />
    </ol>
    <p class="autosave" aria-live="polite">
      <template v-if="saving">Saving…</template>
      <template v-else-if="savedAt">Progress saved automatically.</template>
      <template v-else>Your answers save automatically as you go.</template>
    </p>

    <!-- Step 1: eligibility -->
    <div v-if="step === 'eligibility'" class="card">
      <h2>A few questions first</h2>

      <div class="field">
        <label id="q-dx">Have you been diagnosed with cancer?</label>
        <div class="choice-row" role="group" aria-labelledby="q-dx">
          <button class="choice" :aria-pressed="answered.diagnosis && answers.cancer_diagnosis"
            @click="answers.cancer_diagnosis = true; answered.diagnosis = true">Yes</button>
          <button class="choice" :aria-pressed="answered.diagnosis && !answers.cancer_diagnosis"
            @click="answers.cancer_diagnosis = false; answered.diagnosis = true">No</button>
        </div>
      </div>

      <div class="field">
        <label id="q-age">Are you 18 or older?</label>
        <div class="choice-row" role="group" aria-labelledby="q-age">
          <button class="choice" :aria-pressed="answered.age && answers.age_18_or_over"
            @click="answers.age_18_or_over = true; answered.age = true">Yes</button>
          <button class="choice" :aria-pressed="answered.age && !answers.age_18_or_over"
            @click="answers.age_18_or_over = false; answered.age = true">No</button>
        </div>
      </div>

      <div class="field">
        <label for="q-ins">What kind of health insurance do you have?</label>
        <select id="q-ins" v-model="answers.insurance">
          <option value="" disabled>Choose one…</option>
          <option value="medicare_advantage">Medicare Advantage</option>
          <option value="medicaid">Medicaid</option>
          <option value="commercial">Through work / private</option>
          <option value="other">Something else</option>
          <option value="none">No insurance right now</option>
        </select>
      </div>

      <button :disabled="!eligibilityComplete" @click="submitEligibility">Continue</button>
      <p v-if="!eligibilityComplete" class="hint">Please answer all three questions to continue.</p>
    </div>

    <!-- Ineligible -->
    <div v-else-if="step === 'ineligible'" class="card">
      <h2>This program isn't the right fit right now</h2>
      <p>
        Based on your answers, CareLoop can't enroll you today. If your situation changes, you
        are always welcome to try again — or talk with your care provider about other support
        programs.
      </p>
      <button class="secondary" @click="startOver">Start over</button>
    </div>

    <!-- Step 2: consent -->
    <div v-else-if="step === 'consent'" class="card">
      <h2>Your consent</h2>
      <p>
        CareLoop's nurses will review the symptoms you share and may call, text, or email you
        about them. We only use your information to support your care. You can leave the
        program at any time by telling any member of the care team.
      </p>
      <button @click="giveConsent">I understand and consent</button>
    </div>

    <!-- Step 3: contact -->
    <div v-else-if="step === 'contact'" class="card">
      <h2>How should we reach you?</h2>

      <div class="field">
        <label for="fn">First name</label>
        <input id="fn" v-model="contact.first_name" type="text" autocomplete="given-name"
          @blur="autosave({ first_name: contact.first_name })" />
      </div>
      <div class="field">
        <label for="ln">Last name</label>
        <input id="ln" v-model="contact.last_name" type="text" autocomplete="family-name"
          @blur="autosave({ last_name: contact.last_name })" />
      </div>
      <div class="field">
        <label for="ph">Phone number</label>
        <input id="ph" v-model="contact.phone" type="tel" autocomplete="tel"
          @blur="autosave({ phone: contact.phone })" />
      </div>
      <div class="field">
        <label for="em">Email</label>
        <input id="em" v-model="contact.email" type="email" autocomplete="email"
          @blur="autosave({ email: contact.email })" />
      </div>
      <div class="field">
        <label id="pref">What's the best way to contact you?</label>
        <div class="choice-row" role="group" aria-labelledby="pref">
          <button v-for="p in (['sms', 'phone', 'email'] as const)" :key="p" class="choice"
            :aria-pressed="contact.contact_preference === p"
            @click="contact.contact_preference = p">
            {{ p === 'sms' ? 'Text message' : p === 'phone' ? 'Phone call' : 'Email' }}
          </button>
        </div>
      </div>

      <button :disabled="!contactComplete" @click="complete">Finish enrollment</button>
    </div>

    <!-- Done -->
    <div v-else-if="step === 'done'" class="card">
      <h2>You're enrolled, {{ state.first_name }} 🎉</h2>
      <p>
        Your care team will reach out by {{ state.contact_preference === 'sms' ? 'text message' : state.contact_preference }} to
        introduce themselves. In the meantime, the daily check-in takes less than a minute and
        helps them spot problems early.
      </p>
      <RouterLink to="/checkin">Do your first check-in →</RouterLink>
    </div>
  </template>
</template>
