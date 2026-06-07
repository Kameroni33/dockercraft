import { onBeforeUnmount, onMounted } from "vue";

/** Run `fn` immediately and then every `ms`, pausing while a run is in flight. */
export function usePolling(fn: () => Promise<void>, ms = 4000) {
  let timer: number | undefined;
  let stopped = false;

  async function tick() {
    try {
      await fn();
    } finally {
      if (!stopped) timer = window.setTimeout(tick, ms);
    }
  }

  onMounted(tick);
  onBeforeUnmount(() => {
    stopped = true;
    if (timer !== undefined) clearTimeout(timer);
  });
}
