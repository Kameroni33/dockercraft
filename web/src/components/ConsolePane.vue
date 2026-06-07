<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api } from "../api";

const props = defineProps<{ id: number; running: boolean }>();

const RECONNECT_MS = 2000;

const lines = ref("");
const command = ref("");
const connected = ref(false);
const pane = ref<HTMLElement | null>(null);
let ws: WebSocket | null = null;
let reconnectTimer: number | undefined;
let unmounted = false;
let everConnected = false;

function append(text: string) {
  lines.value += text.endsWith("\n") ? text : text + "\n";
  // Trim the buffer so a chatty server can't eat the tab's memory.
  if (lines.value.length > 200_000) lines.value = lines.value.slice(-150_000);
  nextTick(() => pane.value?.scrollTo({ top: pane.value.scrollHeight }));
}

function connect() {
  if (ws || unmounted) return;
  // Full history on first attach; just a little context after a reconnect
  // (the pane already holds the earlier scrollback).
  ws = new WebSocket(api.servers.consoleUrl(props.id, everConnected ? 10 : 100));
  ws.onopen = () => {
    connected.value = true;
    if (everConnected) append("— console reconnected —");
    everConnected = true;
  };
  ws.onmessage = (ev) => append(ev.data);
  ws.onclose = (ev) => {
    const wasConnected = connected.value;
    connected.value = false;
    ws = null;
    if (ev.reason) append(`— ${ev.reason} —`);
    else if (wasConnected) append("— console disconnected —");
    // The attach socket dies on every restart/crash while the server is meant
    // to be up (a restart often never shows a non-running status to the
    // 5s poll) — keep retrying until it's back or the tab/server goes away.
    if (props.running) scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (reconnectTimer !== undefined || unmounted) return;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = undefined;
    if (props.running) connect();
  }, RECONNECT_MS);
}

function teardown() {
  if (reconnectTimer !== undefined) {
    clearTimeout(reconnectTimer);
    reconnectTimer = undefined;
  }
  ws?.close();
  ws = null;
  connected.value = false;
}

function send() {
  const cmd = command.value.trim();
  if (!cmd) return;
  if (connected.value && ws) {
    ws.send(cmd);
  } else {
    // Fallback: one-shot RCON when the live console isn't attached.
    api.servers
      .command(props.id, cmd)
      .then((r) => append(`> ${cmd}\n${r.response}`))
      .catch((e) => append(`! ${e.message}`));
  }
  command.value = "";
}

onMounted(() => {
  if (props.running) connect();
});
onBeforeUnmount(() => {
  unmounted = true;
  teardown();
});
watch(
  () => props.running,
  (running) => {
    if (running) connect();
    else teardown();
  },
);
</script>

<template>
  <div v-if="!running" class="notice">Server is not running — console will attach on start.</div>
  <div ref="pane" class="console">{{ lines || "…" }}</div>
  <div class="console-input">
    <input
      v-model="command"
      placeholder="server command, e.g. say hi / list / whitelist reload"
      @keydown.enter="send"
    />
    <button class="btn" @click="send">Send</button>
    <span class="dim" style="align-self: center; font-size: 0.8rem">
      {{ connected ? "● live" : "○ rcon" }}
    </span>
  </div>
</template>
