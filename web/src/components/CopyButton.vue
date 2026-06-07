<script setup lang="ts">
import { ref } from "vue";
import { copyText } from "../format";

const props = defineProps<{ text: string }>();
const copied = ref(false);

async function copy() {
  if (await copyText(props.text)) {
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  }
}
</script>

<template>
  <button class="copy-btn" :class="{ copied }" :title="`Copy ${text}`" @click.stop="copy">
    {{ copied ? "✓ copied" : "⧉" }}
  </button>
</template>
