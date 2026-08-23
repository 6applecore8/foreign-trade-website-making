<script setup>
const props = defineProps({
  row: { type: Object, required: true },
  index: { type: Number, required: true }
});
const emit = defineEmits(["remove", "change"]);
const purposes = ["hero", "product-service", "about", "faq", "background-style", "custom"];
const purposeLabels = {
  hero: "首屏",
  "product-service": "产品/服务",
  about: "关于",
  faq: "FAQ",
  "background-style": "背景/风格",
  custom: "其他"
};
</script>

<template>
  <div class="reference-row" :data-client-id="row.clientId">
    <label>图片 *<input class="ref-file" type="file" accept="image/png,image/jpeg,image/gif,image/webp" required @change="(e) => { row.file = e.target.files[0] || null; emit('change'); }"></label>
    <label>用途 *<select class="ref-purpose" required v-model="row.purpose">
      <option value="">请选择</option>
      <option v-for="p in purposes" :key="p" :value="p">{{ purposeLabels[p] }}</option>
    </select></label>
    <label>备注（可选）<input class="ref-notes" v-model="row.notes" @input="emit('change')"></label>
    <button type="button" class="secondary" @click="emit('remove')">移除</button>
  </div>
</template>
