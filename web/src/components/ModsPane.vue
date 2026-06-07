<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, ApiError } from "../api";
import type { InstalledMod, ModSearchHit, ModUpdate } from "../types";

const props = defineProps<{ id: number; mcVersion: string; running: boolean }>();

const installed = ref<InstalledMod[]>([]);
const query = ref("");
const hits = ref<ModSearchHit[]>([]);
const updates = ref<ModUpdate[]>([]);
const error = ref("");
const notice = ref("");
const busy = ref(false);
const checking = ref(false);

const load = async () => (installed.value = await api.mods.list(props.id));
onMounted(load);

const isInstalled = (projectId: string) => installed.value.some((m) => m.project_id === projectId);

async function search() {
  if (!query.value.trim()) return;
  error.value = "";
  try {
    hits.value = await api.mods.search(query.value.trim(), props.mcVersion);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  }
}

async function act(fn: () => Promise<unknown>, okNotice = "") {
  error.value = "";
  notice.value = "";
  busy.value = true;
  try {
    await fn();
    await load();
    if (okNotice) notice.value = okNotice + (props.running ? " Restart to apply." : "");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}

const install = (project: string) =>
  act(async () => {
    const result = await api.mods.install(props.id, project);
    const names = result.installed.map((m) => m.title).join(", ");
    notice.value = `Installed: ${names || "nothing (already present)"}.`;
  }, "");

function uninstall(mod: InstalledMod) {
  act(async () => {
    try {
      await api.mods.uninstall(props.id, mod.project_id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && confirm(`${e.message}\n\nForce removal?`)) {
        await api.mods.uninstall(props.id, mod.project_id, true);
      } else {
        throw e;
      }
    }
  }, `Removed ${mod.title}.`);
}

async function checkUpdates() {
  checking.value = true;
  error.value = "";
  try {
    updates.value = await api.mods.checkUpdates(props.id);
    if (!updates.value.length) notice.value = "All mods are up to date.";
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    checking.value = false;
  }
}

const applyUpdate = (u: ModUpdate) =>
  act(async () => {
    await api.mods.update(props.id, u.project_id);
    updates.value = updates.value.filter((x) => x.project_id !== u.project_id);
  }, `Updated ${u.title} to ${u.available}.`);

const toggle = (mod: InstalledMod, field: "enabled" | "auto_update") =>
  act(() => api.mods.patch(props.id, mod.project_id, { [field]: !mod[field] }), "");
</script>

<template>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div class="card" style="margin-bottom: 1rem; padding: 0.25rem 1rem 0.5rem">
    <div class="page-head" style="margin: 0.6rem 0">
      <h2 style="margin: 0">Installed ({{ installed.length }})</h2>
      <button class="btn btn-sm" :disabled="checking" @click="checkUpdates">
        {{ checking ? "Checking…" : "Check for updates" }}
      </button>
    </div>
    <table v-if="installed.length">
      <thead>
        <tr><th>Mod</th><th>Version</th><th>Enabled</th><th>Auto-update</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="m in installed" :key="m.project_id">
          <td>
            {{ m.title }}
            <span v-if="m.dependency_of" class="dim" title="installed automatically as a dependency">(dep)</span>
          </td>
          <td class="mono dim">{{ m.version_number }}</td>
          <td><input type="checkbox" class="toggle" :checked="m.enabled" :disabled="busy" @change="toggle(m, 'enabled')" /></td>
          <td><input type="checkbox" class="toggle" :checked="m.auto_update" :disabled="busy" @change="toggle(m, 'auto_update')" /></td>
          <td style="text-align: right">
            <button class="btn btn-sm btn-danger" :disabled="busy" @click="uninstall(m)">Remove</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No mods installed.</p>

    <table v-if="updates.length" style="margin-top: 0.5rem">
      <thead><tr><th>Update available</th><th>Installed</th><th>Latest</th><th></th></tr></thead>
      <tbody>
        <tr v-for="u in updates" :key="u.project_id">
          <td>{{ u.title }}</td>
          <td class="mono dim">{{ u.installed }}</td>
          <td class="mono">{{ u.available }}</td>
          <td style="text-align: right">
            <button class="btn btn-sm btn-primary" :disabled="busy" @click="applyUpdate(u)">Update</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2 style="margin-top: 0">Browse Modrinth</h2>
    <div style="display: flex; gap: 0.5rem; margin-bottom: 0.75rem">
      <input v-model="query" placeholder="search mods compatible with this server…" style="flex: 1" @keydown.enter="search" />
      <button class="btn" @click="search">Search</button>
    </div>
    <table v-if="hits.length">
      <tbody>
        <tr v-for="h in hits" :key="h.project_id">
          <td style="width: 2.5rem">
            <img v-if="h.icon_url" :src="h.icon_url" width="28" height="28" style="border-radius: 6px; display: block" />
          </td>
          <td>
            <strong>{{ h.title }}</strong>
            <span class="dim" style="font-size: 0.82rem"> · {{ h.downloads.toLocaleString() }} downloads</span>
            <div class="dim" style="font-size: 0.84rem">{{ h.description }}</div>
          </td>
          <td style="text-align: right; width: 7rem">
            <button v-if="!isInstalled(h.project_id)" class="btn btn-sm btn-primary" :disabled="busy" @click="install(h.slug)">Install</button>
            <span v-else class="dim" style="font-size: 0.82rem">installed</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
