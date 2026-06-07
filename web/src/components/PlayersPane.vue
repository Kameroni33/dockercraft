<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, ApiError } from "../api";
import type { OpEntry, Player, WhitelistEntry } from "../types";

const props = defineProps<{ id: number }>();

const whitelist = ref<WhitelistEntry[]>([]);
const ops = ref<OpEntry[]>([]);
const known = ref<Player[]>([]);
const wlInput = ref("");
const opInput = ref("");
const error = ref("");

async function load() {
  [whitelist.value, ops.value, known.value] = await Promise.all([
    api.servers.whitelist(props.id),
    api.servers.ops(props.id),
    api.players.list(),
  ]);
}
onMounted(load);

async function run(fn: () => Promise<unknown>) {
  error.value = "";
  try {
    await fn();
    await load();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  }
}

const addWl = () => {
  const u = wlInput.value.trim();
  if (u) run(() => api.servers.addWhitelist(props.id, u)).then(() => (wlInput.value = ""));
};
const addOp = () => {
  const u = opInput.value.trim();
  if (u) run(() => api.servers.addOp(props.id, u)).then(() => (opInput.value = ""));
};

function quickAdd(username: string) {
  run(() => api.servers.addWhitelist(props.id, username));
}

const onWhitelist = (u: string) => whitelist.value.some((w) => w.name.toLowerCase() === u.toLowerCase());
</script>

<template>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <div class="grid" style="grid-template-columns: 1fr 1fr; align-items: start">
    <div class="card">
      <h2 style="margin-top: 0">Whitelist</h2>
      <div style="display: flex; gap: 0.5rem; margin-bottom: 0.75rem">
        <input v-model="wlInput" placeholder="java username" style="flex: 1" @keydown.enter="addWl" />
        <button class="btn" @click="addWl">Add</button>
      </div>
      <div class="chips">
        <span v-for="w in whitelist" :key="w.uuid" class="chip">
          {{ w.name }}
          <button title="remove" @click="run(() => api.servers.removeWhitelist(id, w.name))">✕</button>
        </span>
        <span v-if="!whitelist.length" class="dim">empty — anyone can join unless white-list=true</span>
      </div>

      <template v-if="known.filter((p) => !onWhitelist(p.username)).length">
        <h2 style="font-size: 0.85rem; color: var(--text-dim)">Known players (click to whitelist)</h2>
        <div class="chips">
          <span
            v-for="p in known.filter((p) => !onWhitelist(p.username))"
            :key="p.uuid"
            class="chip"
            style="cursor: pointer"
            @click="quickAdd(p.username)"
          >＋ {{ p.username }}</span>
        </div>
      </template>
    </div>

    <div class="card">
      <h2 style="margin-top: 0">Operators</h2>
      <div style="display: flex; gap: 0.5rem; margin-bottom: 0.75rem">
        <input v-model="opInput" placeholder="java username" style="flex: 1" @keydown.enter="addOp" />
        <button class="btn" @click="addOp">Add op</button>
      </div>
      <div class="chips">
        <span v-for="o in ops" :key="o.uuid" class="chip">
          {{ o.name }} <span class="dim">lv{{ o.level }}</span>
          <button title="de-op" @click="run(() => api.servers.removeOp(id, o.name))">✕</button>
        </span>
        <span v-if="!ops.length" class="dim">no operators</span>
      </div>
    </div>
  </div>
</template>
