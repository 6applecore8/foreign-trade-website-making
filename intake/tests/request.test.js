// Contract tests for the intake request/draft builder.
// Migrated from tests/test_app_core.js; production module now lives at
// src/core/request.js (ESM) instead of app-core.js (UMD).
import { describe, it, expect } from "vitest";
import { industryDefaultFaq, buildRequest, draftSnapshot } from "../src/core/request.js";

describe("industry default FAQ", () => {
  it("returns 5 template items for 餐饮 industry", () => {
    const items = industryDefaultFaq("餐饮");
    expect(items).toHaveLength(5);
    expect(items[0].question).toMatch(/菜品|用餐|服务/);
    for (const item of items) {
      expect(item.question.trim()).toBeTruthy();
      expect(item.answer === "待补充" || Boolean(item.generation_note)).toBe(true);
      expect(item.source).toBe("industry-template");
    }
  });
});

describe("custom FAQ serialization", () => {
  it("preserves custom order and maps empty answers to 待补充", () => {
    const request = buildRequest({
      projectName: "新站项目",
      businessName: "示例企业",
      industry: "专业服务",
      primaryGoal: "获取咨询",
      websiteRequirements: "展示服务并提供联系入口",
      faqMode: "custom",
      customFaq: [
        { question: "如何预约？", answer: "通过表单预约。" },
        { question: "空项会怎样？", answer: "" }
      ],
      references: [],
      seoKeywords: ""
    });
    expect(request.faq.mode).toBe("custom");
    expect(request.faq.items).toEqual([
      { question: "如何预约？", answer: "通过表单预约。", source: "user-provided" },
      { question: "空项会怎样？", answer: "待补充", source: "user-provided" }
    ]);
  });

  it("sorts custom FAQ items by their order field", () => {
    const request = buildRequest({
      projectId: "acme-2026", industry: "软件", siteType: "企业官网",
      brand: "Acme", targetAudience: "IT 负责人", primaryGoal: "获取演示",
      requiredSections: "首页\n方案\n联系", freeformRequest: "只做桌面端",
      faqMode: "custom", customFaq: [
        { question: "第二问", answer: "答二", order: 2 },
        { question: "第一问", answer: "答一", order: 1 }
      ], seoTitle: "Acme 官网", seoDescription: "软件解决方案",
      seoKeywords: "软件,解决方案"
    });
    expect(request.project_id).toBe("acme-2026");
    expect(request.industry).toBe("软件");
    expect(request.site_type).toBe("企业官网");
    expect(request.brand).toBe("Acme");
    expect(request.target_audience).toBe("IT 负责人");
    expect(request.primary_goal).toBe("获取演示");
    expect(request.required_sections).toEqual(["首页", "方案", "联系"]);
    expect(request.freeform_request).toBe("只做桌面端");
    expect(request.faq.items.map((item) => item.question)).toEqual(["第一问", "第二问"]);
  });
});

describe("request serialization contract", () => {
  it("projects canonical intake fields, SEO and reference metadata", () => {
    const request = buildRequest({
      projectName: "品牌官网",
      businessName: "示例企业",
      industry: "制造业",
      primaryGoal: "展示产品",
      websiteRequirements: "桌面端优先；提供询盘入口",
      targetAudience: "采购负责人",
      pages: "首页\n产品\n联系",
      styleNotes: "清晰、可信",
      facts: "成立年份待核实",
      faqMode: "industry-default",
      seoTitle: "制造业产品与服务",
      seoDescription: "介绍经核实的产品与服务信息。",
      seoKeywords: "制造业，产品, 服务",
      references: [{ client_id: "ref-1", purpose: "hero", notes: "构图参考", name: "hero.png", size: 128, type: "image/png" }],
      seoFile: { name: "seo.txt", size: 12, type: "text/plain" }
    });
    expect(request.schema_version).toBe("1.0");
    expect(request.project).toEqual({ name: "品牌官网" });
    expect(request.business.name).toBe("示例企业");
    expect(request.business.industry).toBe("制造业");
    expect(request.website.requirements).toBe("桌面端优先；提供询盘入口");
    expect(request.website.pages).toEqual(["首页", "产品", "联系"]);
    expect(request.faq.mode).toBe("industry-default");
    expect(request.faq.items).toHaveLength(5);
    expect(request.seo.keywords).toEqual(["制造业", "产品", "服务"]);
    expect(request.references[0]).toEqual({
      client_id: "ref-1", field_name: "reference:ref-1", purpose: "hero", notes: "构图参考",
      original_name: "hero.png", size: 128, media_type: "image/png"
    });
    expect(request.seo.upload).toEqual({ field_name: "seo_file", original_name: "seo.txt", size: 12, media_type: "text/plain" });
  });

  it("maps every reference to its multipart field name and SEO upload to seo_file", () => {
    const request = buildRequest({
      projectId: "strict", industry: "制造", siteType: "官网", brand: "品牌",
      targetAudience: "采购", primaryGoal: "询盘", requiredSections: "首页",
      freeformRequest: "需求", faqMode: "industry-default",
      seoTitle: "  ", seoDescription: "", seoKeywords: "",
      references: [{ client_id: "r1", purpose: "hero", file: { name: "hero.png", size: 1, type: "image/png" } }],
      seoFile: { name: "seo.csv", size: 3, type: "text/csv" }
    });
    expect(request.references[0].field_name).toBe("reference:r1");
    expect(request.seo.upload.field_name).toBe("seo_file");
  });
});

describe("draft snapshot", () => {
  it("excludes File objects and bytes from the serialized draft", () => {
    const state = {
      businessName: "草稿企业",
      references: [{
        client_id: "ref-1", purpose: "hero", notes: "保留用途",
        file: { name: "hero.png", size: 999, type: "image/png", secretBytes: "DO_NOT_STORE" }
      }],
      seoFile: { name: "seo.txt", size: 100, secretText: "DO_NOT_STORE" }
    };
    const draft = draftSnapshot(state);
    expect(draft.businessName).toBe("草稿企业");
    expect(draft.references).toEqual([{
      client_id: "ref-1", field_name: "reference:ref-1", purpose: "hero", notes: "保留用途",
      file_name: "hero.png", needs_reselect: true
    }]);
    expect(draft.seo_file_name).toBe("seo.txt");
    expect("seoFile" in draft).toBe(false);
    expect(JSON.stringify(draft)).not.toMatch(/DO_NOT_STORE/);
  });

  it("never serializes file objects or bytes recursively", () => {
    const draft = draftSnapshot({
      projectId: "safe", references: [{ client_id: "r1", purpose: "hero", notes: "n",
        file: { name: "x.jpg", bytes: [1, 2, 3], arrayBuffer() {} } }],
      seoFile: { name: "seo.json", content: "secret" }
    });
    const text = JSON.stringify(draft);
    expect(text).not.toMatch(/secret|bytes|arrayBuffer|content/);
    expect(text).toMatch(/x\.jpg/);
  });
});
