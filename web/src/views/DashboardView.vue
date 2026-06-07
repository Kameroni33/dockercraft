<script setup lang="ts">
import { ref } from "vue";
import { api, ApiError } from "../api";
import type { Addresses, Instance } from "../types";
import CopyButton from "../components/CopyButton.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { usePolling } from "../composables/usePolling";

const servers = ref<Instance[]>([]);
const addresses = ref<Addresses | null>(null);
const error = ref("");
const busy = ref<Record<number, boolean>>({});

usePolling(async () => {
  try {
    [servers.value, addresses.value] = await Promise.all([api.servers.list(), api.addresses()]);
    error.value = "";
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "manager unreachable";
  }
});

async function lifecycle(s: Instance, action: "start" | "stop" | "restart") {
  busy.value[s.id] = true;
  try {
    const updated = await api.servers[action](s.id);
    servers.value = servers.value.map((x) => (x.id === s.id ? updated : x));
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e);
  } finally {
    busy.value[s.id] = false;
  }
}

function addressFor(s: Instance): string {
  return addresses.value
    ? `${addresses.value.lan_ip}:${s.game_port}`
    : `…:${s.game_port}`;
}

function publicAddressFor(s: Instance): string | null {
  return addresses.value?.public_ip ? `${addresses.value.public_ip}:${s.game_port}` : null;
}

/** Host port of the Bedrock (Geyser) UDP mapping, if this server has one. */
function bedrockPort(s: Instance): number | null {
  try {
    const extra: { host: number; container: number; proto: string }[] = JSON.parse(
      s.extra_ports_json,
    );
    return extra.find((p) => p.proto === "udp" && p.container === 19132)?.host ?? null;
  } catch {
    return null;
  }
}

function bedrockAddressFor(s: Instance, ip: string | null | undefined): string | null {
  const port = bedrockPort(s);
  return port && ip ? `${ip}:${port}` : null;
}
</script>

<template>
  <div class="page-head">
    <h1>Servers</h1>
    <span v-if="addresses" class="dim mono">LAN {{ addresses.lan_ip }}</span>
  </div>
  <div v-if="error" class="error-banner">{{ error }}</div>

  <div v-if="servers.length" class="grid">
    <div v-for="s in servers" :key="s.id" class="card">
      <div class="page-head" style="margin-bottom: 0.4rem">
        <h2 style="margin: 0">
          <RouterLink :to="`/server/${s.id}`">{{ s.name }}</RouterLink>
        </h2>
        <StatusBadge :status="s.status" />
      </div>
      <dl class="kv" style="margin: 0.5rem 0 0.9rem">
        <dt>Version</dt>
        <dd>
          {{ s.mc_version }} <span class="dim">· {{ s.loader }}</span>
          <span v-if="s.loader_version" class="dim">&nbsp;{{ s.loader_version }}</span>
        </dd>
        <dt>LAN</dt>
        <dd class="mono">{{ addressFor(s) }}<CopyButton :text="addressFor(s)" /></dd>
        <dt v-if="publicAddressFor(s)">Public</dt>
        <dd v-if="publicAddressFor(s)" class="mono" title="share with friends — needs the router port-forward rule below">
          {{ publicAddressFor(s) }}<CopyButton :text="publicAddressFor(s)!" />
        </dd>
        <template v-if="bedrockPort(s)">
          <dt>Bedrock</dt>
          <dd class="mono" :title="`iOS/console players: UDP ${bedrockPort(s)} — forward it on the router for external play`">
            {{ bedrockAddressFor(s, addresses?.lan_ip) ?? `…:${bedrockPort(s)}` }}
            <CopyButton v-if="bedrockAddressFor(s, addresses?.lan_ip)" :text="bedrockAddressFor(s, addresses?.lan_ip)!" />
            <span v-if="bedrockAddressFor(s, addresses?.public_ip)" class="dim">
              · pub {{ bedrockAddressFor(s, addresses?.public_ip)
              }}<CopyButton :text="bedrockAddressFor(s, addresses?.public_ip)!" />
            </span>
          </dd>
        </template>
        <dt>Memory</dt>
        <dd>{{ s.memory }}</dd>
      </dl>
      <div class="btn-row">
        <button
          v-if="s.status !== 'running'"
          class="btn btn-primary btn-sm"
          :disabled="busy[s.id]"
          @click="lifecycle(s, 'start')"
        >
          ▶ Start
        </button>
        <template v-else>
          <button class="btn btn-sm" :disabled="busy[s.id]" @click="lifecycle(s, 'stop')">
            ■ Stop
          </button>
          <button class="btn btn-sm" :disabled="busy[s.id]" @click="lifecycle(s, 'restart')">
            ↻ Restart
          </button>
        </template>
        <RouterLink :to="`/server/${s.id}`" class="btn btn-sm">Manage</RouterLink>
      </div>
    </div>
  </div>
  <div v-else-if="!error" class="empty">
    No servers yet — <RouterLink to="/new">create your first one</RouterLink>.
  </div>

  <template v-if="addresses && addresses.servers.length">
    <h2 style="margin-top: 2rem">Port forwarding</h2>
    <div class="card" style="padding: 0.25rem 1rem">
      <table>
        <thead>
          <tr><th>Server</th><th>LAN</th><th>Public (share this)</th><th>Router rule</th></tr>
        </thead>
        <tbody>
          <tr v-for="a in addresses.servers" :key="a.name">
            <td>{{ a.name }}</td>
            <td class="mono">{{ a.address }}<CopyButton :text="a.address" /></td>
            <td class="mono">
              <template v-if="a.public_address">
                {{ a.public_address }}<CopyButton :text="a.public_address" />
              </template>
              <span v-else class="dim">unknown (offline?)</span>
            </td>
            <td class="mono dim">{{ a.port_forward_hint }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
</template>
