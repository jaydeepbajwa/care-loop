<script setup lang="ts">
import { memberToken } from '../api'

const hasToken = Boolean(memberToken.get())
</script>

<template>
  <h1>Welcome to CareLoop</h1>
  <p>
    CareLoop connects people going through cancer treatment with a care team that checks in on
    them between appointments. Everything here is a demo with synthetic data.
  </p>

  <div class="card">
    <h2>I'm a member (or want to be)</h2>
    <p v-if="hasToken">
      Welcome back — you can pick up your enrollment where you left off, or do today's
      check-in.
    </p>
    <p v-else>Enrolling takes about two minutes, and you can stop and resume any time.</p>
    <div class="choice-row">
      <RouterLink class="btn" to="/enroll" style="text-decoration: none; display: inline-flex; align-items: center; justify-content: center; background: var(--teal); color: #fff; border: 2px solid var(--teal); border-radius: 10px; min-height: 52px; padding: 0.6rem 1.4rem">
        {{ hasToken ? 'Continue enrollment' : 'Start enrollment' }}
      </RouterLink>
      <RouterLink class="btn" to="/checkin" style="text-decoration: none; display: inline-flex; align-items: center; justify-content: center; background: #fff; color: var(--teal-dark); border: 2px solid var(--teal); border-radius: 10px; min-height: 52px; padding: 0.6rem 1.4rem">
        Do a check-in
      </RouterLink>
    </div>
  </div>

  <div class="card">
    <h2>I'm on the care team</h2>
    <p>
      Review flagged check-ins, see the AI's suggested next step, and accept or override it.
      Nothing happens to a member until a human decides.
    </p>
    <RouterLink to="/care">Open the care-team console →</RouterLink>
  </div>
</template>
