<script setup lang="ts">
</script>

<template>
  <header class="topbar">
    <RouterLink class="brand" to="/">CareLoop</RouterLink>
    <nav aria-label="Main">
      <RouterLink to="/enroll">Enroll</RouterLink>
      <RouterLink to="/checkin">Daily check-in</RouterLink>
      <RouterLink to="/care">Care team</RouterLink>
    </nav>
  </header>
  <main>
    <RouterView />
  </main>
</template>
