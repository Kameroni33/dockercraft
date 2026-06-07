<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, ApiError } from "../api";

const props = defineProps<{ id: number; running: boolean }>();

// Keys the manager owns; shown but locked (the API rejects edits anyway).
const MANAGED = new Set(["server-port", "query.port", "enable-rcon", "rcon.port", "rcon.password"]);

const rows = ref<{ key: string; value: string }[]>([]);
const original = ref<Record<string, string>>({});
const newKey = ref("");
const newValue = ref("");
const error = ref("");
const saved = ref(false);
const restartRequired = ref(false);

async function load() {
  original.value = await api.servers.properties(props.id);
  rows.value = Object.entries(original.value)
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => a.key.localeCompare(b.key));
}
onMounted(load);

function addRow() {
  if (!newKey.value.trim()) return;
  rows.value.push({ key: newKey.value.trim(), value: newValue.value });
  newKey.value = newValue.value = "";
}

async function save() {
  error.value = "";
  saved.value = false;
  const updates: Record<string, string> = {};
  for (const row of rows.value) {
    if (MANAGED.has(row.key)) continue;
    if (original.value[row.key] !== row.value) updates[row.key] = row.value;
  }
  if (!Object.keys(updates).length) return;
  try {
    const result = await api.servers.patchProperties(props.id, updates);
    restartRequired.value = result.restart_required;
    saved.value = true;
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  }
}
</script>

<template>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <div v-if="saved" class="notice">
    Saved{{ restartRequired ? " — restart the server to apply" : "" }}.
  </div>

  <div class="card" style="padding: 0.25rem 1rem 1rem">
    <table>
      <thead>
        <tr><th style="width: 40%">Property</th><th>Value</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.key">
          <td class="mono">{{ row.key }}<span v-if="MANAGED.has(row.key)" class="dim" title="managed by dockercraft"> 🔒</span></td>
          <td>
            <span v-if="MANAGED.has(row.key)" class="mono dim">
              {{ row.key === "rcon.password" ? "••••••••" : row.value }}
            </span>
            <input v-else v-model="row.value" style="width: 100%" />
          </td>
        </tr>
        <tr>
          <td><input v-model="newKey" placeholder="new property" class="mono" style="width: 100%" @keydown.enter="addRow" /></td>
          <td style="display: flex; gap: 0.5rem">
            <input v-model="newValue" placeholder="value" style="flex: 1" @keydown.enter="addRow" />
            <button class="btn btn-sm" @click="addRow">Add</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div style="margin-top: 0.9rem">
      <button class="btn btn-primary" @click="save">Save changes</button>
      <span class="dim" style="margin-left: 0.75rem; font-size: 0.82rem">
        An empty file is normal before first start — Minecraft fills in defaults.
      </span>
    </div>
  </div>
</template>
