<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '../api'
import { scaleLabel } from '../lib/checkin'
import type { FunnelReport, MemberSummary, QueueItem, Severity } from '../types'

const nurse = ref(localStorage.getItem('careloop.nurse') ?? 'nurse-rivera')
const tab = ref<'queue' | 'members' | 'funnel'>('queue')
const queue = ref<QueueItem[]>([])
const members = ref<MemberSummary[]>([])
const funnel = ref<FunnelReport | null>(null)
const error = ref('')
const decidingId = ref('')
const override = ref({ severity: 'high' as Severity, suggested_action: '', note: '' })

const headers = computed(() => ({ 'X-Care-Team': nurse.value || 'nurse-demo' }))

onMounted(refresh)

async function refresh() {
  localStorage.setItem('careloop.nurse', nurse.value)
  error.value = ''
  try {
    ;[queue.value, members.value, funnel.value] = await Promise.all([
      api.get<QueueItem[]>('/api/care/queue', headers.value),
      api.get<MemberSummary[]>('/api/care/members', headers.value),
      api.get<FunnelReport>('/api/care/funnel', headers.value),
    ])
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function accept(item: QueueItem) {
  await decide(item, { action: 'accept' })
}

function startOverride(item: QueueItem) {
  decidingId.value = item.suggestion.id
  override.value = {
    severity: item.suggestion.severity,
    suggested_action: item.suggestion.suggested_action,
    note: '',
  }
}

async function submitOverride(item: QueueItem) {
  await decide(item, { action: 'override', ...override.value })
  decidingId.value = ''
}

async function decide(item: QueueItem, body: object) {
  error.value = ''
  try {
    await api.post(`/api/care/suggestions/${item.suggestion.id}/decision`, body, headers.value)
    await refresh()
  } catch (e) {
    error.value = (e as Error).message
  }
}

const funnelRows = computed(() => {
  const f = funnel.value
  if (!f) return []
  const max = Math.max(f.started, 1)
  return [
    { label: 'Started', value: f.started },
    { label: 'Passed eligibility', value: f.eligibility_passed },
    { label: 'Consented', value: f.consented },
    { label: 'Enrolled', value: f.enrolled },
  ].map((r) => ({ ...r, width: `${(r.value / max) * 100}%` }))
})

function fmt(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<template>
  <h1>Care-team console</h1>

  <div class="card" style="display: flex; gap: 1rem; align-items: end; flex-wrap: wrap">
    <div style="flex: 1; min-width: 220px">
      <label for="nurse">Signed in as (stub auth — see README)</label>
      <input id="nurse" v-model="nurse" type="text" @change="refresh" />
    </div>
    <div class="choice-row" style="flex: 2">
      <button class="choice" :aria-pressed="tab === 'queue'" @click="tab = 'queue'">
        Flagged queue ({{ queue.length }})
      </button>
      <button class="choice" :aria-pressed="tab === 'members'" @click="tab = 'members'">
        Members ({{ members.length }})
      </button>
      <button class="choice" :aria-pressed="tab === 'funnel'" @click="tab = 'funnel'">
        Enrollment funnel
      </button>
    </div>
  </div>

  <p v-if="error" class="notice error" role="alert">{{ error }}</p>

  <!-- Flagged queue -->
  <template v-if="tab === 'queue'">
    <p v-if="!queue.length" class="notice ok">No pending flags. 🎉</p>
    <div v-for="item in queue" :key="item.suggestion.id" class="card">
      <div style="display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap">
        <h2 style="margin: 0">{{ item.member_name }}</h2>
        <div>
          <span class="badge" :class="item.suggestion.severity">{{ item.suggestion.severity }}</span>
          <span class="badge source" style="margin-left: 0.4rem">
            {{ item.suggestion.source === 'llm' ? `AI suggestion (${item.suggestion.model})` : 'rules suggestion' }}
          </span>
        </div>
      </div>

      <div class="scores">
        <span v-for="(label, key) in { pain: 'Pain', fatigue: 'Fatigue', nausea: 'Nausea', appetite: 'Appetite', mood: 'Mood' }"
          :key="key" :class="{ hot: item.check_in[key] >= 2 }">
          {{ label }}: {{ scaleLabel(item.check_in[key]) }}
        </span>
      </div>
      <p v-if="item.check_in.free_text" class="free-text">“{{ item.check_in.free_text }}”</p>
      <p class="hint">Flagged because: {{ item.check_in.flag_reason }}</p>

      <div class="notice warn" style="margin-top: 0.75rem">
        <strong>Suggested next step:</strong> {{ item.suggestion.suggested_action }}
        <p class="hint" style="margin: 0.3rem 0 0">{{ item.suggestion.rationale }}</p>
      </div>

      <div v-if="decidingId !== item.suggestion.id" class="choice-row">
        <button @click="accept(item)">Accept suggestion</button>
        <button class="secondary" @click="startOverride(item)">Override…</button>
      </div>

      <div v-else style="margin-top: 0.75rem">
        <div class="field">
          <label :for="`sev-${item.suggestion.id}`">Corrected severity</label>
          <select :id="`sev-${item.suggestion.id}`" v-model="override.severity">
            <option value="low">low</option>
            <option value="moderate">moderate</option>
            <option value="high">high</option>
            <option value="urgent">urgent</option>
          </select>
        </div>
        <div class="field">
          <label :for="`act-${item.suggestion.id}`">What should happen instead?</label>
          <textarea :id="`act-${item.suggestion.id}`" v-model="override.suggested_action" />
        </div>
        <div class="field">
          <label :for="`note-${item.suggestion.id}`">Note (why)</label>
          <input :id="`note-${item.suggestion.id}`" v-model="override.note" type="text" />
        </div>
        <div class="choice-row">
          <button :disabled="!override.suggested_action.trim()" @click="submitOverride(item)">
            Save override
          </button>
          <button class="secondary" @click="decidingId = ''">Cancel</button>
        </div>
      </div>
    </div>
  </template>

  <!-- Members -->
  <div v-else-if="tab === 'members'" class="card">
    <table>
      <thead>
        <tr><th>Member</th><th>Enrolled</th><th>Last check-in</th><th>Open flags</th></tr>
      </thead>
      <tbody>
        <tr v-for="m in members" :key="m.id">
          <td>{{ m.name }}</td>
          <td>{{ fmt(m.enrolled_at) }}</td>
          <td>{{ fmt(m.last_check_in_at) }}</td>
          <td>
            <span v-if="m.open_flags" class="badge high">{{ m.open_flags }}</span>
            <span v-else>—</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Funnel -->
  <div v-else-if="tab === 'funnel'" class="card">
    <h2>Enrollment funnel</h2>
    <p class="hint">
      started → eligible → consented → enrolled. This is the table an enrollment experiment
      gets scored against.
    </p>
    <div v-for="row in funnelRows" :key="row.label" class="funnel-bar">
      <span class="label">{{ row.label }}</span>
      <div class="bar" :style="{ width: row.width }" />
      <strong>{{ row.value }}</strong>
    </div>
    <p v-if="funnel" class="hint">({{ funnel.eligibility_failed }} did not pass eligibility)</p>
  </div>
</template>
