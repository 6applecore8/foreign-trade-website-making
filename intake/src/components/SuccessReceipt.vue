<script setup>
defineProps({
  result: { type: Object, required: true }
});
</script>

<template>
  <section id="success" class="success">
    <h2>保存成功</h2>
    <dl>
      <dt>request_id</dt><dd id="result-id">{{ result.request_id }}</dd>
      <dt>绝对路径</dt><dd id="result-absolute">{{ result.absolute_path }}</dd>
      <dt>相对路径</dt><dd id="result-relative">{{ result.relative_path }}</dd>
    </dl>
  </section>
</template>
