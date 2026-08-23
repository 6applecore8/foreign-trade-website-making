<script setup>
defineProps({
  errors: { type: Array, default: () => [] }
});
</script>

<template>
  <div id="error-summary" class="error-summary" tabindex="-1" v-show="errors.length">
    <strong>请修正以下问题</strong>
    <ul>
      <li v-for="(error, i) in errors" :key="i">{{ error.message }}</li>
    </ul>
  </div>
</template>
