<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api";
import type { Backup, BackupPolicy } from "../types";
import { formatBytes, formatDate } from "../format";

const props = defineProps<{ id: number }>();
const router = useRouter();

const backups = ref<Backup[]>([]);
const note = ref("");
const error = ref("");
const notice = ref("");
const busy = ref(false);
const policy = ref<BackupPolicy>({ enabled: false, interval_hours: 6, keep_count: 10, keep_days: 0 });

const load = async () => (backups.value = await api.backups.listFor(props.id));
onMounted(load);

async function act(fn: () => Promise<unknown>) {
  error.value = "";
  notice.value = "";
  busy.value = true;
  try {
    await fn();
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}

const create = () =>
  act(async () => {
    await api.backups.create(props.id, note.value);
    note.value = "";
    notice.value = "Backup created.";
  });

function restore(b: Backup) {
  if (!confirm(`Restore "${b.instance_name}" to ${formatDate(b.created_at)}?\nA safety backup is taken first; the server restarts if running.`)) return;
  act(async () => {
    await api.backups.restore(b.id);
    notice.value = "Restored. A pre_restore safety backup was created.";
  });
}

function clone(b: Backup) {
  const name = prompt("Name for the new server (lowercase, dashes ok):");
  if (!name) return;
  act(async () => {
    const instance = await api.backups.clone(b.id, name);
    router.push(`/server/${instance.id}`);
  });
}

const remove = (b: Backup) =>
  confirm(`Delete backup from ${formatDate(b.created_at)}? The archive file is removed.`) &&
  act(() => api.backups.delete(b.id));

const savePolicy = () =>
  act(async () => {
    const result = await api.backups.setPolicy(props.id, policy.value);
    notice.value = `Policy saved${result.pruned ? ` — ${result.pruned} old backup(s) pruned` : ""}.`;
  });
</script>

<template>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div class="card" style="margin-bottom: 1rem">
    <h2 style="margin-top: 0">Scheduled backups</h2>
    <div class="field-row" style="align-items: end">
      <div class="field checkbox" style="flex: 0 0 auto; margin-bottom: 0.5rem">
        <input id="bp-on" v-model="policy.enabled" type="checkbox" class="toggle" />
        <label for="bp-on">Enabled</label>
      </div>
      <div class="field">
        <label>Every (hours)</label>
        <input v-model.number="policy.interval_hours" type="number" min="1" style="width: 100%" />
      </div>
      <div class="field">
        <label>Keep at most (0 = ∞)</label>
        <input v-model.number="policy.keep_count" type="number" min="0" style="width: 100%" />
      </div>
      <div class="field">
        <label>Keep days (0 = ∞)</label>
        <input v-model.number="policy.keep_days" type="number" min="0" style="width: 100%" />
      </div>
      <div class="field" style="flex: 0 0 auto">
        <button class="btn btn-primary" :disabled="busy" @click="savePolicy">Save policy</button>
      </div>
    </div>
    <p class="dim" style="font-size: 0.82rem; margin: 0">
      Scheduled backups run only while the server is running. Manual backups are never auto-pruned.
    </p>
  </div>

  <div class="card" style="padding: 0.25rem 1rem 1rem">
    <div class="page-head" style="margin: 0.6rem 0">
      <h2 style="margin: 0">Backups ({{ backups.length }})</h2>
      <div style="display: flex; gap: 0.5rem">
        <input v-model="note" placeholder="note (optional)" @keydown.enter="create" />
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="create">Back up now</button>
      </div>
    </div>
    <table v-if="backups.length">
      <thead>
        <tr><th>When</th><th>Kind</th><th>Size</th><th>Note</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="b in backups" :key="b.id">
          <td>{{ formatDate(b.created_at) }}</td>
          <td><span class="badge" :class="b.kind === 'manual' ? 'running' : 'not_created'">{{ b.kind }}</span></td>
          <td class="mono dim">{{ formatBytes(b.size_bytes) }}</td>
          <td class="dim">{{ b.note }}</td>
          <td style="text-align: right; white-space: nowrap">
            <button class="btn btn-sm" :disabled="busy" @click="restore(b)">Restore</button>
            <button class="btn btn-sm" :disabled="busy" style="margin-left: 0.35rem" @click="clone(b)">Clone</button>
            <button class="btn btn-sm btn-danger" :disabled="busy" style="margin-left: 0.35rem" @click="remove(b)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No backups yet.</p>
  </div>
</template>
