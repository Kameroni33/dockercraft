<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, ApiError } from "../api";
import type { HealthCheck, Instance, McVersion, Preflight, UpgradeResult } from "../types";

const props = defineProps<{ server: Instance }>();
const emit = defineEmits<{ changed: [] }>();

// One linear flow: pick -> review the plan -> upgrade -> boot & verify.
type Step = "pick" | "reviewed" | "upgraded" | "checked";

const step = ref<Step>("pick");
const versions = ref<McVersion[]>([]);
const target = ref("latest");
const memory = ref(props.server.memory);
const disableIncompatible = ref(false);
const busy = ref("");
const error = ref("");

const plan = ref<Preflight | null>(null);
const result = ref<UpgradeResult | null>(null);
const health = ref<HealthCheck | null>(null);

onMounted(async () => {
  try {
    versions.value = await api.versions.minecraft();
  } catch {
    /* the list is a nicety; "latest" still works */
  }
});

const blocked = computed(() => plan.value !== null && !plan.value.ready);
const canUpgrade = computed(() => plan.value !== null && (plan.value.ready || disableIncompatible.value));

async function run(label: string, fn: () => Promise<void>) {
  error.value = "";
  busy.value = label;
  try {
    await fn();
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
    // A blocked upgrade still carries the report — show it rather than a bare error.
    const detail = e instanceof ApiError ? (e.data as { preflight?: Preflight }) : undefined;
    if (detail?.preflight) plan.value = detail.preflight;
  } finally {
    busy.value = "";
  }
}

const checkPlan = () =>
  run("Checking compatibility…", async () => {
    plan.value = await api.servers.upgradePreflight(props.server.id, {
      mc_version: target.value,
    });
    step.value = "reviewed";
  });

const doUpgrade = () =>
  run("Backing up, downloading, migrating mods…", async () => {
    result.value = await api.servers.upgrade(props.server.id, {
      mc_version: target.value,
      memory: memory.value !== props.server.memory ? memory.value : null,
      disable_incompatible: disableIncompatible.value,
    });
    step.value = "upgraded";
    emit("changed");
  });

const doHealthCheck = () =>
  run("Starting the server and watching for a clean boot…", async () => {
    health.value = await api.servers.healthCheck(props.server.id, {
      timeout: 300,
      rollback_backup_id: result.value?.backup_id,
    });
    step.value = "checked";
    emit("changed");
  });

function rollback() {
  const id = health.value?.rollback?.backup_id ?? result.value?.backup_id;
  if (id === undefined) return;
  if (!confirm(`Restore backup ${id}? This puts the version, jar, mod set and world back as they were before the upgrade.`)) return;
  run("Rolling back…", async () => {
    await api.backups.restore(id);
    reset();
    emit("changed");
  });
}

function reset() {
  step.value = "pick";
  plan.value = null;
  result.value = null;
  health.value = null;
  error.value = "";
}

const STATUS_LABEL: Record<string, string> = {
  ok: "compatible",
  blocked: "no build yet",
  skipped: "no build (disabled)",
  unknown: "check failed",
};
</script>

<template>
  <div v-if="error" class="error-banner">{{ error }}</div>
  <div v-if="busy" class="notice">{{ busy }} This can take several minutes — leave the page open.</div>

  <!-- 1. Pick a target -->
  <div class="card" style="margin-bottom: 1rem">
    <h2 style="margin-top: 0">Upgrade Minecraft version</h2>
    <p class="dim" style="font-size: 0.82rem; margin-top: 0">
      Currently on <strong>{{ server.mc_version }}</strong> ({{ server.loader }}, Java
      {{ server.java_major }}). A backup is always taken before anything changes.
    </p>
    <div class="field-row" style="align-items: end">
      <div class="field">
        <label for="target">Target version</label>
        <select id="target" v-model="target" :disabled="step !== 'pick'" style="width: 100%">
          <option value="latest">latest{{ versions[0] ? ` (${versions[0].id})` : "" }}</option>
          <option v-for="v in versions.slice(0, 40)" :key="v.id" :value="v.id">{{ v.id }}</option>
        </select>
      </div>
      <div class="field">
        <label for="mem">Memory (heap)</label>
        <input id="mem" v-model="memory" :disabled="step !== 'pick'" placeholder="4G" style="width: 100%" />
      </div>
      <div class="field" style="flex: 0 0 auto">
        <button v-if="step === 'pick'" class="btn btn-primary" :disabled="!!busy" @click="checkPlan">
          Check compatibility
        </button>
        <button v-else class="btn" :disabled="!!busy" @click="reset">Start over</button>
      </div>
    </div>
    <p class="dim" style="font-size: 0.82rem; margin-bottom: 0">
      Newer versions want more heap — the container cap is heap ×1.5. Leave the memory
      field alone to keep {{ server.memory }}.
    </p>
  </div>

  <!-- 2. The plan -->
  <div v-if="plan" class="card" style="margin-bottom: 1rem">
    <h2 style="margin-top: 0">
      {{ plan.current_version }} → {{ plan.target_version }}
      <span class="badge" :class="plan.ready ? 'running' : 'dead'" style="margin-left: 0.5rem">
        {{ plan.ready ? "ready" : "blocked" }}
      </span>
    </h2>

    <dl class="kv" style="margin-bottom: 1rem">
      <dt>Java</dt>
      <dd>
        {{ plan.java?.current }} → {{ plan.java?.target }}
        <span v-if="plan.java?.changed" class="dim">· container image changes</span>
        <span v-else class="dim">· unchanged</span>
      </dd>
      <template v-if="plan.loader_version">
        <dt>Fabric loader</dt>
        <dd>{{ plan.loader_version.current ?? "—" }} → {{ plan.loader_version.target }}</dd>
      </template>
    </dl>

    <ul v-if="plan.blockers.length" class="findings">
      <li v-for="(b, i) in plan.blockers" :key="`b${i}`" class="blocker">{{ b }}</li>
    </ul>
    <ul v-if="plan.warnings.length" class="findings">
      <li v-for="(w, i) in plan.warnings" :key="`w${i}`" class="warning">{{ w }}</li>
    </ul>

    <table v-if="plan.mods.length">
      <thead>
        <tr><th>Mod</th><th>Installed</th><th>For {{ plan.target_version }}</th><th>Status</th></tr>
      </thead>
      <tbody>
        <tr v-for="m in plan.mods" :key="m.project_id">
          <td>{{ m.title }}<span v-if="!m.enabled" class="dim"> (disabled)</span></td>
          <td class="mono dim">{{ m.installed }}</td>
          <td class="mono">{{ m.available ?? "—" }}</td>
          <td>
            <span class="badge" :class="m.status === 'ok' ? 'running' : m.status === 'blocked' ? 'dead' : 'not_created'">
              {{ STATUS_LABEL[m.status] }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="blocked" class="field checkbox" style="margin-top: 1rem">
      <input id="force" v-model="disableIncompatible" type="checkbox" class="toggle" />
      <label for="force">Upgrade anyway and disable the mods with no compatible build</label>
    </div>

    <div class="btn-row" style="margin-top: 1rem">
      <button
        v-if="step === 'reviewed'"
        class="btn btn-primary"
        :disabled="!canUpgrade || !!busy"
        @click="doUpgrade"
      >
        Back up &amp; upgrade to {{ plan.target_version }}
      </button>
    </div>
  </div>

  <!-- 3. What the upgrade did -->
  <div v-if="result" class="card" style="margin-bottom: 1rem">
    <h2 style="margin-top: 0">Upgraded to {{ result.to_version }}</h2>
    <dl class="kv">
      <dt>Backup</dt>
      <dd>#{{ result.backup_id }} <span class="dim">(taken on {{ result.from_version }} — your rollback point)</span></dd>
      <dt>Java</dt>
      <dd>{{ result.java_major }}</dd>
      <dt>Memory</dt>
      <dd>{{ result.memory }}</dd>
      <dt>Mods updated</dt>
      <dd>
        <span v-if="result.mods.updated.length">
          {{ result.mods.updated.map((m) => `${m.title} → ${m.version}`).join(", ") }}
        </span>
        <span v-else class="dim">none needed updating</span>
      </dd>
      <template v-if="result.mods.added.length">
        <dt>New dependencies</dt>
        <dd>{{ result.mods.added.join(", ") }}</dd>
      </template>
      <template v-if="result.mods.disabled.length">
        <dt>Disabled</dt>
        <dd class="blocker-text">{{ result.mods.disabled.join(", ") }}</dd>
      </template>
    </dl>
    <p class="dim" style="font-size: 0.82rem">
      The server is stopped and its container rebuilt. Boot it now to confirm the upgrade took.
    </p>
    <button v-if="step === 'upgraded'" class="btn btn-primary" :disabled="!!busy" @click="doHealthCheck">
      ▶ Start &amp; verify
    </button>
  </div>

  <!-- 4. Did it come up? -->
  <div v-if="health" class="card">
    <h2 style="margin-top: 0">
      Boot check
      <span class="badge" :class="health.healthy ? 'running' : 'dead'" style="margin-left: 0.5rem">
        {{ health.verdict }}
      </span>
    </h2>
    <p>{{ health.summary }}</p>

    <template v-if="!health.healthy">
      <h3 style="margin-bottom: 0.4rem">What to do</h3>
      <ul class="findings">
        <li v-for="(f, i) in health.findings" :key="i" class="warning">
          <strong>{{ f.reason }}</strong><br />{{ f.recommendation }}
        </li>
      </ul>
      <div v-if="health.rollback" class="btn-row" style="margin: 1rem 0">
        <button class="btn btn-danger" :disabled="!!busy" @click="rollback">
          Roll back to backup #{{ health.rollback.backup_id }}
        </button>
        <button class="btn" :disabled="!!busy" @click="doHealthCheck">Try booting again</button>
      </div>
      <h3 style="margin-bottom: 0.4rem">Console tail</h3>
      <pre class="console" style="max-height: 20rem">{{ health.log_tail }}</pre>
    </template>
  </div>
</template>

<style scoped>
.findings {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem;
}
.findings li {
  border-left: 3px solid var(--dim, #666);
  padding: 0.35rem 0 0.35rem 0.7rem;
  margin-bottom: 0.45rem;
  font-size: 0.9rem;
}
.findings li.blocker {
  border-left-color: #e5534b;
}
.findings li.warning {
  border-left-color: #d29922;
}
.blocker-text {
  color: #e5534b;
}
</style>
