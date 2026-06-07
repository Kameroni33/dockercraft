<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api";
import type { Instance } from "../types";
import StatusBadge from "../components/StatusBadge.vue";
import { usePolling } from "../composables/usePolling";
import ConsolePane from "../components/ConsolePane.vue";
import PropertiesEditor from "../components/PropertiesEditor.vue";
import PlayersPane from "../components/PlayersPane.vue";
import ModsPane from "../components/ModsPane.vue";
import BackupsPane from "../components/BackupsPane.vue";

const props = defineProps<{ id: number }>();
const router = useRouter();

const server = ref<Instance | null>(null);
const error = ref("");
const tab = ref<"console" | "settings" | "players" | "mods" | "backups">("console");
const busy = ref(false);

usePolling(async () => {
  try {
    server.value = await api.servers.get(props.id);
    error.value = "";
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      router.replace("/");
      return;
    }
    error.value = e instanceof ApiError ? e.message : "manager unreachable";
  }
}, 5000);

async function lifecycle(action: "start" | "stop" | "restart") {
  if (!server.value) return;
  busy.value = true;
  try {
    server.value = await api.servers[action](props.id);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}

async function destroy() {
  const name = server.value?.name ?? "";
  const answer = prompt(
    `This deletes the container AND ALL WORLD DATA for "${name}" ` +
      `(backups are kept). Type the server name to confirm:`,
  );
  if (answer !== name) return;
  await api.servers.delete(props.id, true);
  router.replace("/");
}
</script>

<template>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <template v-if="server">
    <div class="page-head">
      <h1>
        {{ server.name }}
        <StatusBadge :status="server.status" style="vertical-align: middle; margin-left: 0.5rem" />
      </h1>
      <div class="btn-row">
        <button v-if="server.status !== 'running'" class="btn btn-primary" :disabled="busy" @click="lifecycle('start')">▶ Start</button>
        <template v-else>
          <button class="btn" :disabled="busy" @click="lifecycle('stop')">■ Stop</button>
          <button class="btn" :disabled="busy" @click="lifecycle('restart')">↻ Restart</button>
        </template>
        <button class="btn btn-danger" :disabled="busy" @click="destroy">Delete</button>
      </div>
    </div>

    <dl class="kv card" style="margin-bottom: 1.25rem">
      <dt>Version</dt>
      <dd>{{ server.mc_version }} · {{ server.loader }}<span v-if="server.loader_version"> {{ server.loader_version }}</span> · Java {{ server.java_major }}</dd>
      <dt>Game port</dt>
      <dd class="mono">{{ server.game_port }}</dd>
      <dt>Memory</dt>
      <dd>{{ server.memory }}</dd>
    </dl>

    <div class="tabs">
      <button :class="{ active: tab === 'console' }" @click="tab = 'console'">Console</button>
      <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">Settings</button>
      <button :class="{ active: tab === 'players' }" @click="tab = 'players'">Players</button>
      <button v-if="server.loader === 'fabric'" :class="{ active: tab === 'mods' }" @click="tab = 'mods'">Mods</button>
      <button :class="{ active: tab === 'backups' }" @click="tab = 'backups'">Backups</button>
    </div>

    <ConsolePane v-if="tab === 'console'" :id="id" :running="server.status === 'running'" />
    <PropertiesEditor v-else-if="tab === 'settings'" :id="id" :running="server.status === 'running'" />
    <PlayersPane v-else-if="tab === 'players'" :id="id" />
    <ModsPane v-else-if="tab === 'mods'" :id="id" :mc-version="server.mc_version" :running="server.status === 'running'" />
    <BackupsPane v-else-if="tab === 'backups'" :id="id" />
  </template>
</template>
