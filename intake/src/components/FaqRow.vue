<script setup>
defineProps({
  row: { type: Object, required: true },
  index: { type: Number, required: true }
});
const emit = defineEmits(["remove", "change"]);
</script>

<template>
  <div class="faq-row">
    <label>问题 *<input class="faq-question" required v-model="row.question" @input="emit('change')"></label>
    <label>答案（空缺保存为“待补充”）<input class="faq-answer" v-model="row.answer" @input="emit('change')"></label>
    <button type="button" class="secondary" @click="emit('remove')">移除</button>
  </div>
</template>
