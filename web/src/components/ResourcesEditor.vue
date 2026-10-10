<script setup lang="ts">
import { ref, watch } from "vue";
import { api, ApiError } from "../api";
import type { Instance } from "../types";

const props = defineProps<{ server: Instance }>();
const emit = defineEmits<{ changed: [] }>();

const memory = ref(props.server.memory);
const cpus = ref(props.server.cpus);
const jvmFlags = ref(props.server.jvm_flags);
const error = ref("");
const notice = ref("");
const busy = ref(false);

// The detail view polls every 5s; don't clobber fields the user is editing.
watch(
  () => props.server.id,
  () => {
    memory.value = props.server.memory;
    cpus.value = props.server.cpus;
    jvmFlags.value = props.server.jvm_flags;
  },
);

async function save() {
  error.value = "";
  notice.value = "";
  busy.value = true;
  try {
    await api.servers.patchResources(props.server.id, {
      memory: memory.value,
      cpus: cpus.value,
      jvm_flags: jvmFlags.value,
    });
    notice.value =
      props.server.status === "running"
        ? "Saved — the container was recreated and restarted."
        : "Saved. Applies when the server next starts.";
    emit("changed");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="card" style="margin-bottom: 1rem">
    <h2 style="margin-top: 0">Resources</h2>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="notice" class="notice">{{ notice }}</div>
    <div class="field-row" style="align-items: end">
      <div class="field">
        <label for="res-mem">Memory (JVM heap)</label>
        <input id="res-mem" v-model="memory" placeholder="4G" style="width: 100%" />
      </div>
      <div class="field">
        <label for="res-cpu">CPU cores (0 = unlimited)</label>
        <input id="res-cpu" v-model.number="cpus" type="number" min="0" step="0.5" style="width: 100%" />
      </div>
      <div class="field" style="flex: 2">
        <label for="res-flags">Extra JVM flags</label>
        <input id="res-flags" v-model="jvmFlags" placeholder="-XX:+UseG1GC" style="width: 100%" />
      </div>
      <div class="field" style="flex: 0 0 auto">
        <button class="btn btn-primary" :disabled="busy" @click="save">Save</button>
      </div>
    </div>
    <p class="dim" style="font-size: 0.82rem; margin: 0">
      Sizes look like <span class="mono">2G</span> or <span class="mono">2048M</span>. The container
      memory cap is the heap ×1.5 to leave room for metaspace and native allocations. Saving
      recreates the container — a running server restarts.
    </p>
  </div>
</template>
