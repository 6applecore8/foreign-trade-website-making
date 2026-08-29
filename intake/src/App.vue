<script setup>
import { ref, reactive, computed, nextTick } from "vue";
import ReferenceRow from "./components/ReferenceRow.vue";
import FaqRow from "./components/FaqRow.vue";
import ErrorSummary from "./components/ErrorSummary.vue";
import SuccessReceipt from "./components/SuccessReceipt.vue";
import { buildRequest, draftSnapshot } from "./core/request.js";
import { validateForm } from "./core/validation.js";
import { loadDraft, saveDraft, clearDraft } from "./core/storage.js";
import { submitRequest, startAgent, getAgentRun } from "./core/api.js";

const DRAFT_KEY = "site-intake-draft-v1";
const MAX_REFERENCES = 6;
const ELEMENT_OPTIONS = [
  ["header-navigation", "顶部导航", "全站菜单、Logo 与操作入口", "global"],
  ["hero", "首页首屏", "主标题、卖点、CTA 与首屏图片", "home"],
  ["category-menu", "商品分类", "分类下拉与分类页跳转", "global"],
  ["featured-products", "热销产品", "首页热销区及多张产品图", "home"],
  ["product-grid", "商品网格", "分类页列数、间距与图片尺寸", "category"],
  ["product-card", "商品卡片", "产品标题、介绍、图片与链接", "category"],
  ["about", "公司介绍", "品牌故事、实力与可信信息", "home"],
  ["faq", "常见问题", "FAQ 内容、顺序与交互", "home"],
  ["contact", "联系与询盘", "表单、联系方式与 CTA", "global"],
  ["footer", "页脚", "链接、版权与政策信息", "global"],
  ["colors-typography", "颜色与字体", "全站视觉基调和可读性", "global"],
  ["imagery", "图片风格", "产品图比例、背景与整体风格", "global"]
];

const form = reactive({
  projectId: "", industry: "", siteType: "", brand: "", targetAudience: "",
  primaryGoal: "", requiredSections: "", freeformRequest: "",
  faqMode: "industry-default", seoTitle: "", seoDescription: "", seoKeywords: ""
});
const references = ref([]);
const customFaq = ref([]);
const seoFile = ref(null);
const errors = ref([]);
const statusText = ref("");
const submitting = ref(false);
const result = ref(null);
const startingAgent = ref(false);
const agentRun = ref(null);
const agentError = ref("");
const elementAnnotations = ref(ELEMENT_OPTIONS.map(([element_id, label, description, page_scope]) => ({
  element_id, label, description, page_scope, priority: "must", note: "", selected: false
})));
let referenceCounter = 0;

const previewText = computed(() => JSON.stringify(buildRequest(currentState()), null, 2));

function currentState() {
  return {
    ...form,
    references: references.value.map((row) => ({
      client_id: row.clientId,
      purpose: row.purpose,
      notes: row.notes,
      file: row.file
    })),
    customFaq: customFaq.value.map((row, index) => ({
      question: row.question,
      answer: row.answer,
      order: index
    })),
    elementAnnotations: elementAnnotations.value.map((item) => ({ ...item })),
    seoFile: seoFile.value
  };
}

function addReference(saved) {
  if (references.value.length >= MAX_REFERENCES) return;
  const clientId = (saved && saved.client_id) || "ref-" + (++referenceCounter);
  references.value.push({
    clientId,
    purpose: (saved && saved.purpose) || "",
    notes: (saved && saved.notes) || "",
    file: null
  });
}

function removeReference(index) {
  references.value.splice(index, 1);
  changed();
}

function addFaq(saved) {
  customFaq.value.push({
    question: (saved && saved.question) || "",
    answer: (saved && saved.answer) || ""
  });
}

function removeFaq(index) {
  customFaq.value.splice(index, 1);
  changed();
}

function hideSuccess() {
  result.value = null;
  agentRun.value = null;
  agentError.value = "";
}

function downloadJson() {
  const blob = new Blob([previewText.value + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = (form.projectId.trim() || "site-request") + ".json";
  link.click();
  URL.revokeObjectURL(url);
}

function changed() {
  hideSuccess();
  const current = currentState();
  try {
    saveDraft(DRAFT_KEY, draftSnapshot(current));
  } catch (_) {
    /* localStorage unavailable: draft is best-effort */
  }
}

function restore() {
  const draft = loadDraft(DRAFT_KEY);
  if (!draft) return;
  const ids = {
    projectId: "projectId", industry: "industry", siteType: "siteType",
    brand: "brand", targetAudience: "targetAudience", primaryGoal: "primaryGoal",
    requiredSections: "requiredSections", freeformRequest: "freeformRequest",
    seoTitle: "seoTitle", seoDescription: "seoDescription", seoKeywords: "seoKeywords"
  };
  Object.keys(ids).forEach((key) => {
    if (typeof draft[key] === "string") form[key] = draft[key];
  });
  if (draft.faqMode === "custom") {
    form.faqMode = "custom";
    (draft.customFaq || []).forEach(addFaq);
  }
  (draft.references || []).forEach(addReference);
  (draft.elementAnnotations || []).forEach((saved) => {
    const item = elementAnnotations.value.find((candidate) => candidate.element_id === saved.element_id);
    if (!item) return;
    item.selected = saved.selected === true;
    item.priority = ["must", "should", "optional"].includes(saved.priority) ? saved.priority : "must";
    item.note = typeof saved.note === "string" ? saved.note : "";
  });
}

function clearErrors() {
  errors.value = [];
}

function showErrors(list) {
  errors.value = list;
}

function validate(current) {
  return validateForm(current, {
    references,
    customFaq,
    seoFile: () => seoFile.value
  });
}

async function onSubmit(event) {
  event.preventDefault();
  hideSuccess();
  clearErrors();
  const current = currentState();
  const list = validate(current);
  if (list.length) {
    showErrors(list);
    await nextTick();
    const idByKey = {
      projectId: "project_id", siteType: "site_type", targetAudience: "target_audience",
      primaryGoal: "primary_goal", requiredSections: "required_sections", freeformRequest: "freeform_request"
    };
    const firstId = idByKey[list[0].element] || list[0].element;
    document.getElementById(firstId)?.focus();
    return;
  }
  const payload = buildRequest(current);
  submitting.value = true;
  statusText.value = "正在保存…";
  try {
    const outcome = await submitRequest(payload, current.references, current.seoFile);
    result.value = outcome;
    clearDraft(DRAFT_KEY);
    statusText.value = "已保存";
  } catch (error) {
    hideSuccess();
    showErrors([{ element: "submit", message: error.message }]);
    statusText.value = "保存失败";
  } finally {
    submitting.value = false;
  }
}

async function onStartAgent() {
  if (!result.value || startingAgent.value) return;
  startingAgent.value = true;
  agentError.value = "";
  try {
    agentRun.value = await startAgent(result.value.request_id);
    const runId = agentRun.value.run_id;
    while (agentRun.value?.run_id === runId && agentRun.value.status === "running") {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      agentRun.value = await getAgentRun(runId);
    }
    if (agentRun.value?.status === "failed") {
      agentError.value = `Agent 执行失败（退出码 ${agentRun.value.exit_code ?? "未知"}），请查看本次运行日志。`;
    }
  } catch (error) {
    agentError.value = error.message;
  } finally {
    startingAgent.value = false;
  }
}

restore();
changed();
</script>

<template>
  <main class="desktop-shell">
    <header>
      <p class="eyebrow">LOCAL WORKFLOW</p>
      <h1>Site Intake</h1>
      <p>桌面端网站需求采集与本地不可变发布</p>
    </header>
    <ErrorSummary :errors="errors" />
    <form id="intake-form" novalidate @submit="onSubmit" @input="changed">
      <section>
        <h2>项目合同</h2>
        <div class="grid">
          <label>项目 ID *<input id="project_id" name="project_id" v-model="form.projectId" required autocomplete="off"></label>
          <label>行业 *<input id="industry" name="industry" v-model="form.industry" required></label>
          <label>站点类型 *<input id="site_type" name="site_type" v-model="form.siteType" required placeholder="企业官网"></label>
          <label>品牌 *<input id="brand" name="brand" v-model="form.brand" required></label>
          <label>目标受众 *<input id="target_audience" name="target_audience" v-model="form.targetAudience" required></label>
          <label>主要目标 *<input id="primary_goal" name="primary_goal" v-model="form.primaryGoal" required></label>
        </div>
        <label>必需栏目（每行一项）*<textarea id="required_sections" name="required_sections" v-model="form.requiredSections" required></textarea></label>
        <label>自由需求 *<textarea id="freeform_request" name="freeform_request" v-model="form.freeformRequest" required></textarea></label>
      </section>

      <section id="element-annotations">
        <div class="section-title annotation-heading">
          <div>
            <h2>页面元素选择与批注</h2>
            <p>勾选希望调整的区域，并写清改动。选中的备注会作为结构化需求交给 Agent。</p>
          </div>
          <span class="selection-count">已选择 {{ elementAnnotations.filter((item) => item.selected).length }} 项</span>
        </div>
        <div class="annotation-grid">
          <article
            v-for="item in elementAnnotations"
            :key="item.element_id"
            class="annotation-card"
            :class="{ selected: item.selected }"
          >
            <label class="annotation-toggle">
              <input
                :id="`annotation-${item.element_id}`"
                type="checkbox"
                v-model="item.selected"
                @change="changed"
              >
              <span><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span>
            </label>
          </article>
        </div>
        <div v-if="elementAnnotations.some((item) => item.selected)" class="annotation-editors">
          <h3>已选元素的修改备注</h3>
          <article
            v-for="item in elementAnnotations.filter((candidate) => candidate.selected)"
            :key="`editor-${item.element_id}`"
            class="annotation-editor"
          >
            <div class="annotation-editor-title">
              <strong>{{ item.label }}</strong>
              <small>{{ item.description }}</small>
            </div>
            <div class="annotation-detail">
              <label>优先级
                <select v-model="item.priority" @change="changed">
                  <option value="must">必须实现</option>
                  <option value="should">应当实现</option>
                  <option value="optional">可选优化</option>
                </select>
              </label>
              <label>修改备注 *
                <textarea
                  :id="`annotation-note-${item.element_id}`"
                  v-model="item.note"
                  maxlength="800"
                  placeholder="例如：桌面端商品区一行展示 5 个，图片不要过大。"
                  @input="changed"
                ></textarea>
              </label>
            </div>
          </article>
        </div>
      </section>

      <section>
        <div class="section-title">
          <h2>参考图（最多 6 张，每张 ≤ 8 MiB）</h2>
          <button type="button" id="add-reference" @click="addReference(); changed()">添加参考图</button>
        </div>
        <div id="references">
          <ReferenceRow
            v-for="(row, index) in references"
            :key="row.clientId"
            :row="row"
            :index="index"
            @remove="removeReference(index)"
            @change="changed"
          />
        </div>
      </section>

      <section>
        <h2>FAQ</h2>
        <div class="choice">
          <label><input type="radio" name="faq_mode" value="industry-default" v-model="form.faqMode"> 行业默认</label>
          <label><input type="radio" name="faq_mode" value="custom" v-model="form.faqMode"> 自定义（按当前顺序保存）</label>
        </div>
        <div id="custom-faq" v-show="form.faqMode === 'custom'">
          <button type="button" id="add-faq" @click="addFaq(); changed()">添加问题</button>
          <div id="faq-items">
            <FaqRow
              v-for="(row, index) in customFaq"
              :key="index"
              :row="row"
              :index="index"
              @remove="removeFaq(index)"
              @change="changed"
            />
          </div>
        </div>
      </section>

      <section>
        <h2>SEO</h2>
        <div class="grid">
          <label>SEO 标题<input id="seo_title" v-model="form.seoTitle"></label>
          <label>SEO 描述<input id="seo_description" v-model="form.seoDescription"></label>
        </div>
        <label>关键词（逗号或换行分隔）<textarea id="seo_keywords" v-model="form.seoKeywords"></textarea></label>
        <label>可选 SEO 文档（UTF-8 txt/json/csv，≤ 2 MiB）<input id="seo_file" type="file" accept=".txt,.json,.csv,text/plain,text/csv,application/json" @change="(e) => { seoFile = e.target.files[0] || null; changed(); }"></label>
      </section>

      <section>
        <div class="section-title">
          <h2>结构 JSON 预览</h2>
          <button id="download-json" type="button" @click="downloadJson">下载结构 JSON</button>
        </div>
        <p class="preview-note">只含结构和文件元数据，不含上传文件字节，文件需重新选择。</p>
        <pre id="json-preview">{{ previewText }}</pre>
      </section>

      <div class="actions">
        <button type="submit" id="submit" :disabled="submitting">保存请求</button>
        <span id="status" role="status">{{ statusText }}</span>
      </div>
    </form>
    <SuccessReceipt
      v-if="result"
      :result="result"
      :starting-agent="startingAgent"
      :agent-run="agentRun"
      :agent-error="agentError"
      @start-agent="onStartAgent"
    />
  </main>
</template>
