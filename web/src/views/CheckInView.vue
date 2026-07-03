<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api, ApiError, memberToken } from '../api'
import { emptyScores, isComplete, missingSymptoms, SCALE, SYMPTOMS } from '../lib/checkin'
import type { CheckIn } from '../types'

const DEMO_TOKEN = 'demo-member-token'

const scores = ref(emptyScores())
const freeText = ref('')
const submitting = ref(false)
const submitted = ref<CheckIn | null>(null)
const error = ref('')
const history = ref<CheckIn[]>([])
const tokenMissing = ref(false)

const canSubmit = computed(() => isComplete(scores.value) && !submitting.value)
const missing = computed(() => missingSymptoms(scores.value))

onMounted(load)

async function load() {
  const token = memberToken.get()
  if (!token) {
    tokenMissing.value = true
    return
  }
  try {
    history.value = await api.get<CheckIn[]>(`/api/members/${token}/checkins`)
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 403)) tokenMissing.value = true
    else error.value = (e as Error).message
  }
}

function useDemoMember() {
  memberToken.set(DEMO_TOKEN)
  tokenMissing.value = false
  load()
}

async function submit() {
  const token = memberToken.get()
  if (!token) return
  submitting.value = true
  error.value = ''
  try {
    submitted.value = await api.post<CheckIn>(`/api/members/${token}/checkins`, {
      ...scores.value,
      free_text: freeText.value.trim() || null,
    })
    scores.value = emptyScores()
    freeText.value = ''
    await load()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}

function fmt(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}
</script>

<template>
  <h1>Daily check-in</h1>

  <div v-if="tokenMissing" class="notice warn">
    <p>
      Check-ins are for enrolled members.
      <RouterLink to="/enroll">Enroll first</RouterLink>, or use the seeded demo member to
      explore.
    </p>
    <button class="secondary" @click="useDemoMember">Use the demo member (Rosa)</button>
  </div>

  <template v-else>
    <div v-if="submitted" class="notice ok" role="status">
      <strong>Thank you — your check-in was sent to your care team.</strong>
      <p v-if="submitted.flagged" style="margin: 0.4rem 0 0">
        A nurse will look at this one soon and may reach out to you.
      </p>
    </div>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>

    <div class="card">
      <p>Five quick questions about today. There are no wrong answers.</p>

      <div v-for="s in SYMPTOMS" :key="s.key" class="field">
        <label :id="`q-${s.key}`">{{ s.question }}</label>
        <div class="choice-row" role="group" :aria-labelledby="`q-${s.key}`">
          <button
            v-for="opt in SCALE"
            :key="opt.value"
            class="choice"
            :aria-pressed="scores[s.key] === opt.value"
            @click="scores[s.key] = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <div class="field">
        <label for="free">Anything else you want your care team to know?</label>
        <textarea
          id="free"
          v-model="freeText"
          placeholder="Optional — in your own words"
          maxlength="2000"
        />
      </div>

      <button :disabled="!canSubmit" @click="submit">
        {{ submitting ? 'Sending…' : 'Send to my care team' }}
      </button>
      <p v-if="missing.length" class="hint">Still to answer: {{ missing.join(', ') }}</p>
    </div>

    <div v-if="history.length" class="card">
      <h2>Your recent check-ins</h2>
      <table>
        <thead>
          <tr><th>When</th><th>Summary</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="c in history" :key="c.id">
            <td>{{ fmt(c.created_at) }}</td>
            <td>
              pain {{ c.pain }}, fatigue {{ c.fatigue }}, nausea {{ c.nausea }},
              appetite {{ c.appetite }}, mood {{ c.mood }}
            </td>
            <td>
              <span v-if="c.flagged" class="badge moderate">care team notified</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
