<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api";
import type { McVersion } from "../types";

const router = useRouter();

const versions = ref<McVersion[]>([]);
const error = ref("");
const submitting = ref(false);

const name = ref("");
const mcVersion = ref("latest");
const loader = ref<"vanilla" | "fabric">("fabric");
const memory = ref("2G");
const motd = ref("");
const maxPlayers = ref(10);
const whitelistInput = ref("");
const whitelist = ref<string[]>([]);
const crossPlatform = ref(false);
const acceptEula = ref(false);
const startNow = ref(true);

onMounted(async () => {
  try {
    versions.value = await api.versions.minecraft();
  } catch {
    /* version list is a nicety; "latest" still works */
  }
});

function addWhitelist() {
  const names = whitelistInput.value.split(/[\s,]+/).filter(Boolean);
  for (const n of names) if (!whitelist.value.includes(n)) whitelist.value.push(n);
  whitelistInput.value = "";
}

async function submit() {
  error.value = "";
  submitting.value = true;
  try {
    const properties: Record<string, string | number | boolean> = {
      "max-players": maxPlayers.value,
    };
    if (motd.value) properties.motd = motd.value;

    const instance = await api.servers.setup({
      name: name.value.trim(),
      mc_version: mcVersion.value,
      loader: loader.value,
      memory: memory.value,
      accept_eula: acceptEula.value,
      properties,
      whitelist: whitelist.value,
      ops: [],
      start: false, // start after optional mod install below
    });

    if (crossPlatform.value && loader.value === "fabric") {
      await api.mods.install(instance.id, "geyser"); // pulls Fabric API as required dep
      await api.mods.install(instance.id, "floodgate");
      await api.servers.setExtraPorts(instance.id, [
        { host: 19132, container: 19132, proto: "udp" },
      ]);
    }
    if (startNow.value) await api.servers.start(instance.id);
    router.push(`/server/${instance.id}`);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="page-head"><h1>New Server</h1></div>
  <div v-if="error" class="error-banner">{{ error }}</div>

  <form class="card" style="max-width: 640px" @submit.prevent="submit">
    <div class="field">
      <label for="name">Name (lowercase, dashes ok)</label>
      <input id="name" v-model="name" required pattern="[a-z0-9][a-z0-9-]*" placeholder="brothers-smp" style="width: 100%" />
    </div>

    <div class="field-row">
      <div class="field">
        <label for="version">Minecraft version</label>
        <select id="version" v-model="mcVersion" style="width: 100%">
          <option value="latest">latest{{ versions[0] ? ` (${versions[0].id})` : "" }}</option>
          <option v-for="v in versions.slice(0, 30)" :key="v.id" :value="v.id">{{ v.id }}</option>
        </select>
      </div>
      <div class="field">
        <label for="loader">Loader</label>
        <select id="loader" v-model="loader" style="width: 100%">
          <option value="fabric">Fabric (mods supported)</option>
          <option value="vanilla">Vanilla</option>
        </select>
      </div>
      <div class="field">
        <label for="memory">Memory</label>
        <select id="memory" v-model="memory" style="width: 100%">
          <option>1G</option><option>2G</option><option>4G</option><option>6G</option><option>8G</option>
        </select>
      </div>
    </div>

    <div class="field-row">
      <div class="field">
        <label for="motd">MOTD (server list description)</label>
        <input id="motd" v-model="motd" placeholder="A dockercraft server" style="width: 100%" />
      </div>
      <div class="field" style="flex: 0 0 110px">
        <label for="maxp">Max players</label>
        <input id="maxp" v-model.number="maxPlayers" type="number" min="1" style="width: 100%" />
      </div>
    </div>

    <div class="field">
      <label for="wl">Whitelist (java usernames — enables whitelist when non-empty)</label>
      <div style="display: flex; gap: 0.5rem">
        <input id="wl" v-model="whitelistInput" placeholder="username, username…" style="flex: 1"
               @keydown.enter.prevent="addWhitelist" />
        <button type="button" class="btn" @click="addWhitelist">Add</button>
      </div>
      <div v-if="whitelist.length" class="chips" style="margin-top: 0.5rem">
        <span v-for="(u, i) in whitelist" :key="u" class="chip">
          {{ u }} <button type="button" @click="whitelist.splice(i, 1)">✕</button>
        </span>
      </div>
    </div>

    <div v-if="loader === 'fabric'" class="field checkbox">
      <input id="xplat" v-model="crossPlatform" type="checkbox" class="toggle" />
      <label for="xplat">
        Cross-platform support — installs Geyser + Floodgate so Bedrock players
        (consoles/phones) can join via UDP 19132
      </label>
    </div>

    <div class="field checkbox">
      <input id="start" v-model="startNow" type="checkbox" class="toggle" />
      <label for="start">Start the server after setup</label>
    </div>

    <div class="field checkbox">
      <input id="eula" v-model="acceptEula" type="checkbox" class="toggle" required />
      <label for="eula">
        I accept the <a href="https://aka.ms/MinecraftEULA" target="_blank">Minecraft EULA</a>
      </label>
    </div>

    <button class="btn btn-primary" :disabled="submitting || !acceptEula || !name">
      {{ submitting ? "Setting up… (downloads the server jar)" : "Create server" }}
    </button>
  </form>
</template>
