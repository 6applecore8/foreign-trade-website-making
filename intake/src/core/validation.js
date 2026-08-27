// Client-side validation. Mirrors the native-app.js rules; server-side
// schema validation remains authoritative.

const REQUIRED_CHECKS = [
  ["projectId", "请输入项目 ID"],
  ["industry", "请输入行业"],
  ["siteType", "请输入站点类型"],
  ["brand", "请输入品牌"],
  ["targetAudience", "请输入目标受众"],
  ["primaryGoal", "请输入主要目标"],
  ["requiredSections", "请输入至少一个必需栏目"],
  ["freeformRequest", "请输入自由需求"]
];

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const MAX_SEO_BYTES = 2 * 1024 * 1024;

export function validateForm(current, deps) {
  const errors = [];
  REQUIRED_CHECKS.forEach(([key, message]) => {
    const value = current[key];
    if (typeof value !== "string" || !value.trim()) {
      errors.push({ element: key, message });
    }
  });
  const referenceRows = deps.references.value;
  current.references.forEach((ref, index) => {
    const file = ref.file;
    const row = referenceRows[index];
    if (!file) {
      errors.push({ element: `ref-file-${row.clientId}`, message: `参考图 ${index + 1} 需要重新选择文件` });
    } else if (file.size > MAX_IMAGE_BYTES) {
      errors.push({ element: `ref-file-${row.clientId}`, message: `参考图 ${index + 1} 超过 8 MiB` });
    }
    if (!ref.purpose) {
      errors.push({ element: `ref-purpose-${row.clientId}`, message: `参考图 ${index + 1} 必须选择用途` });
    }
  });
  if (current.seoFile && current.seoFile.size > MAX_SEO_BYTES) {
    errors.push({ element: "seo_file", message: "SEO 文档超过 2 MiB" });
  }
  if (current.faqMode === "custom") {
    deps.customFaq.value.forEach((row, index) => {
      if (!String(row.question || "").trim()) {
        errors.push({ element: `faq-question-${index}`, message: `自定义 FAQ ${index + 1} 需要问题` });
      }
    });
  }
  (current.elementAnnotations || []).forEach((item) => {
    if (item.selected && !String(item.note || "").trim()) {
      errors.push({
        element: `annotation-note-${item.element_id}`,
        message: `请为“${item.label}”填写修改备注`
      });
    }
  });
  return errors;
}
