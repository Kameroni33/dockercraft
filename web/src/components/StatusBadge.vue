<script setup lang="ts">
defineProps<{ status: string }>();
</script>

<template>
  <span class="badge" :class="status">{{ status.replace("_", " ") }}</span>
</template>
