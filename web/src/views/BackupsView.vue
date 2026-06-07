<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api";
import type { Backup } from "../types";
import { formatBytes, formatDate } from "../format";
import CopyButton from "../components/CopyButton.vue";

const router = useRouter();
const backups = ref<Backup[]>([]);
const error = ref("");

const load = async () => (backups.value = await api.backups.listAll());
onMounted(load);

function clone(b: Backup) {
  const name = prompt("Name for the new server (lowercase, dashes ok):");
  if (!name) return;
  api.backups
    .clone(b.id, name)
    .then((instance) => router.push(`/server/${instance.id}`))
    .catch((e) => (error.value = e instanceof ApiError ? e.message : String(e)));
}

function remove(b: Backup) {
  if (!confirm(`Delete backup of "${b.instance_name}" from ${formatDate(b.created_at)}?`)) return;
  api.backups.delete(b.id).then(load);
}
</script>

<template>
  <div class="page-head"><h1>All backups</h1></div>
  <div v-if="error" class="error-banner">{{ error }}</div>

  <div class="card" style="padding: 0.25rem 1rem">
    <table v-if="backups.length">
      <thead>
        <tr><th>Server</th><th>When</th><th>Version</th><th>Kind</th><th>Size</th><th>Note</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="b in backups" :key="b.id">
          <td>
            <RouterLink v-if="b.instance_id" :to="`/server/${b.instance_id}`">{{ b.instance_name }}</RouterLink>
            <template v-else>
              <span>{{ b.instance_name }}</span> <span class="dim" title="source server was deleted">(orphan)</span>
            </template>
          </td>
          <td>{{ formatDate(b.created_at) }}</td>
          <td class="mono dim">{{ b.mc_version }} {{ b.loader }}</td>
          <td><span class="badge" :class="b.kind === 'manual' ? 'running' : 'not_created'">{{ b.kind }}</span></td>
          <td class="mono dim" :title="b.path">
            {{ formatBytes(b.size_bytes) }}<CopyButton :text="b.path" />
          </td>
          <td class="dim">{{ b.note }}</td>
          <td style="text-align: right; white-space: nowrap">
            <button class="btn btn-sm" @click="clone(b)">Clone to new server</button>
            <button class="btn btn-sm btn-danger" style="margin-left: 0.35rem" @click="remove(b)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No backups anywhere yet.</p>
  </div>
</template>
