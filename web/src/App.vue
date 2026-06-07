<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "./api";

const route = useRoute();
const router = useRouter();
const onLogin = computed(() => route.name === "login");

async function logout() {
  await api.auth.logout();
  router.push("/login");
}
</script>

<template>
  <header v-if="!onLogin" class="topbar">
    <RouterLink to="/" class="brand">
      <span class="brand-block">⛏</span> dockercraft
    </RouterLink>
    <nav>
      <RouterLink to="/">Dashboard</RouterLink>
      <RouterLink to="/backups">Backups</RouterLink>
      <RouterLink to="/new" class="btn btn-primary btn-sm">+ New Server</RouterLink>
      <a href="#" class="dim" title="sign out" @click.prevent="logout">⎋</a>
    </nav>
  </header>
  <main class="container">
    <RouterView />
  </main>
</template>
