// Pure request/draft builders for the intake UI.
// Vue 3 ESM port of the former app-core.js contract. No DOM or File I/O:
// File-like objects are only read for metadata (name/size/type).

const GENERAL_QUESTIONS = [
  "主要提供哪些产品或服务？",
  "服务范围或适用地区有哪些？",
  "如何获取报价或预约咨询？",
  "项目或订单通常如何推进？",
  "售后支持与常见注意事项有哪些？"
];

const RESTAURANT_QUESTIONS = [
  "提供哪些主要菜品与用餐服务？",
  "营业时间与门店地址是什么？",
  "是否接受预订、外带或配送？",
  "是否提供过敏原或忌口信息？",
  "团体用餐或活动如何咨询？"
];

export function industryDefaultFaq(industry) {
  const text = String(industry || "").trim();
  const questions = /餐饮|饭店|餐厅|咖啡|烘焙/.test(text)
    ? RESTAURANT_QUESTIONS
    : GENERAL_QUESTIONS;
  return questions.map((question) => ({
    question,
    answer: "待补充",
    source: "industry-template",
    generation_note: "仅为行业常见问题主题；请补充并核实企业实际答案。"
  }));
}

function clean(value) {
  return String(value == null ? "" : value).trim();
}

function splitLines(value) {
  return clean(value).split(/\r?\n/).map(clean).filter(Boolean);
}

function splitKeywords(value) {
  return clean(value).split(/[,，\r\n]+/).map(clean).filter(Boolean);
}

function fileMetadata(value) {
  if (!value) return null;
  return {
    field_name: "seo_file",
    original_name: clean(value.name),
    size: Number(value.size) || 0,
    media_type: clean(value.type) || "application/octet-stream"
  };
}

export function buildRequest(state) {
  const source = state || {};
  const customItems = Array.isArray(source.customFaq) ? source.customFaq : [];
  const items = source.faqMode === "custom"
    ? customItems.slice().sort((a, b) =>
        (Number(a.order) || 0) - (Number(b.order) || 0)
      ).map((item) => ({
        question: clean(item.question),
        answer: clean(item.answer) || "待补充",
        source: "user-provided"
      }))
    : industryDefaultFaq(source.industry);
  const references = (Array.isArray(source.references) ? source.references : []).map((item) => {
    const file = item.file || item;
    const clientId = clean(item.client_id);
    return {
      client_id: clientId,
      field_name: "reference:" + clientId,
      purpose: clean(item.purpose),
      notes: clean(item.notes),
      original_name: clean(file.name),
      size: Number(file.size) || 0,
      media_type: clean(file.type) || "application/octet-stream"
    };
  });
  const projectId = clean(source.projectId || source.projectName);
  const brand = clean(source.brand || source.businessName);
  const requiredSections = splitLines(source.requiredSections || source.pages);
  const freeformRequest = clean(source.freeformRequest || source.websiteRequirements);
  return {
    schema_version: "1.0",
    project_id: projectId,
    industry: clean(source.industry),
    site_type: clean(source.siteType),
    brand: brand,
    target_audience: clean(source.targetAudience),
    primary_goal: clean(source.primaryGoal),
    required_sections: requiredSections,
    freeform_request: freeformRequest,
    project: { name: clean(source.projectName || source.projectId) },
    business: {
      name: clean(source.businessName || source.brand),
      industry: clean(source.industry),
      target_audience: clean(source.targetAudience),
      facts: clean(source.facts)
    },
    website: {
      primary_goal: clean(source.primaryGoal),
      requirements: clean(source.websiteRequirements || source.freeformRequest),
      pages: splitLines(source.pages || source.requiredSections),
      style_notes: clean(source.styleNotes)
    },
    faq: { mode: source.faqMode === "custom" ? "custom" : "industry-default", items },
    seo: {
      title: clean(source.seoTitle),
      description: clean(source.seoDescription),
      keywords: splitKeywords(source.seoKeywords),
      upload: fileMetadata(source.seoFile)
    },
    references
  };
}

export function draftSnapshot(state) {
  const source = state || {};
  const draft = {};
  Object.keys(source).forEach((key) => {
    if (key !== "references" && key !== "seoFile") draft[key] = source[key];
  });
  draft.references = (Array.isArray(source.references) ? source.references : []).map((item) => {
    const fileName = clean(item.file && item.file.name ? item.file.name : item.file_name);
    const clientId = clean(item.client_id);
    return {
      client_id: clientId,
      field_name: "reference:" + clientId,
      purpose: clean(item.purpose),
      notes: clean(item.notes),
      file_name: fileName,
      needs_reselect: Boolean(fileName)
    };
  });
  if (source.seoFile && source.seoFile.name) draft.seo_file_name = clean(source.seoFile.name);
  return draft;
}
