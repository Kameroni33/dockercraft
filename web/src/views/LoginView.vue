<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api";

const router = useRouter();
const setupMode = ref(false);
const username = ref("");
const password = ref("");
const confirm = ref("");
const error = ref("");
const busy = ref(false);

onMounted(async () => {
  const status = await api.auth.status();
  if (status.authenticated) {
    router.replace("/");
    return;
  }
  setupMode.value = status.setup_required;
});

async function submit() {
  error.value = "";
  if (setupMode.value && password.value !== confirm.value) {
    error.value = "passwords don't match";
    return;
  }
  busy.value = true;
  try {
    if (setupMode.value) await api.auth.setup(username.value, password.value);
    else await api.auth.login(username.value, password.value);
    router.replace("/");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div style="max-width: 380px; margin: 8vh auto 0">
    <h1 style="text-align: center">⛏ dockercraft</h1>
    <div class="card">
      <h2 style="margin-top: 0">{{ setupMode ? "Create admin account" : "Sign in" }}</h2>
      <p v-if="setupMode" class="dim" style="font-size: 0.85rem">
        First run — this account will manage all servers.
      </p>
      <div v-if="error" class="error-banner">{{ error }}</div>
      <form @submit.prevent="submit">
        <div class="field">
          <label for="u">Username</label>
          <input id="u" v-model="username" required autocomplete="username" style="width: 100%" />
        </div>
        <div class="field">
          <label for="p">Password{{ setupMode ? " (8+ characters)" : "" }}</label>
          <input id="p" v-model="password" type="password" required minlength="8"
                 :autocomplete="setupMode ? 'new-password' : 'current-password'" style="width: 100%" />
        </div>
        <div v-if="setupMode" class="field">
          <label for="c">Confirm password</label>
          <input id="c" v-model="confirm" type="password" required style="width: 100%" />
        </div>
        <button class="btn btn-primary" style="width: 100%" :disabled="busy">
          {{ setupMode ? "Create account" : "Sign in" }}
        </button>
      </form>
    </div>
  </div>
</template>
