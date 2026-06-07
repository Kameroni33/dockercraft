<script setup lang="ts">
</script>

<template>
  <header class="topbar">
    <RouterLink to="/" class="brand">
      <span class="brand-block">⛏</span> dockercraft
    </RouterLink>
    <nav>
      <RouterLink to="/">Dashboard</RouterLink>
      <RouterLink to="/backups">Backups</RouterLink>
      <RouterLink to="/new" class="btn btn-primary btn-sm">+ New Server</RouterLink>
    </nav>
  </header>
  <main class="container">
    <RouterView />
  </main>
</template>
