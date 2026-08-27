// Component behavior tests for App.vue (jsdom + @vue/test-utils).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import App from "../src/App.vue";

const DRAFT_KEY = "site-intake-draft-v1";

async function fillRequired(wrapper) {
  const set = (id, value) => wrapper.find("#" + id).setValue(value);
  await set("project_id", "acme-2026");
  await set("industry", "餐饮");
  await set("site_type", "企业官网");
  await set("brand", "Acme");
  await set("target_audience", "顾客");
  await set("primary_goal", "展示菜单");
  await set("required_sections", "首页\n菜单\n联系");
  await set("freeform_request", "桌面端单页");
}

function fakeFile(name, type, size) {
  return { name, type, size, lastModified: 1 };
}

function setFiles(input, files) {
  Object.defineProperty(input.element, "files", { value: files, configurable: true });
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("critical fields render", () => {
  it("renders header, form and all required intake fields", () => {
    const wrapper = mount(App);
    const text = wrapper.text();
    expect(text).toContain("Site Intake");
    expect(text).toContain("项目 ID");
    expect(text).toContain("行业");
    expect(text).toContain("站点类型");
    expect(text).toContain("品牌");
    expect(text).toContain("目标受众");
    expect(text).toContain("主要目标");
    expect(text).toContain("必需栏目");
    expect(text).toContain("自由需求");
    expect(text).toContain("参考图");
    expect(text).toContain("SEO 标题");
    expect(text).toContain("可选 SEO 文档");
    expect(wrapper.find("form").exists()).toBe(true);
    expect(wrapper.find("#submit").exists()).toBe(true);
    expect(wrapper.find("#element-annotations").exists()).toBe(true);
  });

  it("shows the JSON preview disclosure without any uploaded bytes", () => {
    const wrapper = mount(App);
    expect(wrapper.text()).toContain("只含结构和文件元数据，不含上传文件字节，文件需重新选择。");
    const preview = wrapper.find("#json-preview");
    expect(preview.exists()).toBe(true);
  });
});

describe("element annotations", () => {
  it("requires a note for a selected element and writes the structured annotation", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#annotation-product-grid").setValue(true);
    await wrapper.find("form").trigger("submit");
    expect(wrapper.find("#error-summary").text()).toContain("商品网格");
    await wrapper.find("#annotation-note-product-grid").setValue("桌面端一行 5 个商品，图片尺寸适中");
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.element_annotations).toEqual([{
      element_id: "product-grid",
      page_scope: "category",
      priority: "must",
      note: "桌面端一行 5 个商品，图片尺寸适中"
    }]);
    expect(preview.website.element_annotations).toEqual(preview.element_annotations);
  });
});

describe("FAQ", () => {
  it("industry default mode shows no custom rows but builds 5 template items", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#industry").setValue("餐饮");
    expect(wrapper.findAll(".faq-row")).toHaveLength(0);
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.faq.mode).toBe("industry-default");
    expect(preview.faq.items).toHaveLength(5);
    expect(preview.faq.items[0].source).toBe("industry-template");
    expect(preview.faq.items.every((item) => item.answer === "待补充")).toBe(true);
  });

  it("custom mode shows rows in the order added and empty answers become 待补充", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find('input[name="faq_mode"][value="custom"]').setValue();
    await wrapper.find("#add-faq").trigger("click");
    await wrapper.find("#add-faq").trigger("click");
    const rows = wrapper.findAll(".faq-row");
    expect(rows).toHaveLength(2);
    await rows[0].find(".faq-question").setValue("第一问");
    await rows[0].find(".faq-answer").setValue("答一");
    await rows[1].find(".faq-question").setValue("第二问");
    await rows[1].find(".faq-answer").setValue("");
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.faq.mode).toBe("custom");
    expect(preview.faq.items.map((item) => item.question)).toEqual(["第一问", "第二问"]);
    expect(preview.faq.items[1].answer).toBe("待补充");
    expect(preview.faq.items.every((item) => item.source === "user-provided")).toBe(true);
  });

  it("removing a custom FAQ row keeps remaining order contiguous", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find('input[name="faq_mode"][value="custom"]').setValue();
    await wrapper.find("#add-faq").trigger("click");
    await wrapper.find("#add-faq").trigger("click");
    await wrapper.findAll(".faq-row")[0].find(".faq-question").setValue("要删的");
    await wrapper.findAll(".faq-row")[1].find(".faq-question").setValue("保留的");
    await wrapper.findAll(".faq-row")[0].find("button").trigger("click");
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.faq.items.map((item) => item.question)).toEqual(["保留的"]);
  });
});

describe("reference images", () => {
  it("adds rows up to the 6-image maximum", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    for (let i = 0; i < 7; i++) {
      await wrapper.find("#add-reference").trigger("click");
    }
    expect(wrapper.findAll(".reference-row")).toHaveLength(6);
  });

  it("maps each reference to purpose/notes/client_id metadata without file bytes", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#add-reference").trigger("click");
    const row = wrapper.find(".reference-row");
    await row.find(".ref-purpose").setValue("hero");
    await row.find(".ref-notes").setValue("构图参考");
    const file = row.find(".ref-file");
    setFiles(file, [fakeFile("hero.png", "image/png", 128)]);
    await file.trigger("change");
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.references).toHaveLength(1);
    expect(preview.references[0]).toMatchObject({
      client_id: preview.references[0].client_id,
      field_name: "reference:" + preview.references[0].client_id,
      purpose: "hero",
      notes: "构图参考",
      original_name: "hero.png",
      size: 128,
      media_type: "image/png"
    });
    expect(preview.references[0].client_id).toMatch(/^ref-/);
  });

  it("removes a reference row from state and preview", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#add-reference").trigger("click");
    await wrapper.find("#add-reference").trigger("click");
    expect(wrapper.findAll(".reference-row")).toHaveLength(2);
    await wrapper.findAll(".reference-row")[0].find("button").trigger("click");
    expect(wrapper.findAll(".reference-row")).toHaveLength(1);
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.references).toHaveLength(1);
  });

  it("never serializes file bytes into the preview JSON", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#add-reference").trigger("click");
    const row = wrapper.find(".reference-row");
    const file = row.find(".ref-file");
    const payload = { name: "hero.png", type: "image/png", size: 999, secretBytes: "DO_NOT_STORE", toBase64: () => "AAAA" };
    setFiles(file, [payload]);
    await file.trigger("change");
    const previewText = wrapper.find("#json-preview").text();
    expect(previewText).toContain("hero.png");
    expect(previewText).not.toMatch(/DO_NOT_STORE|toBase64|base64|data:image|\[\s*\d+,\s*\d+/);
  });
});

describe("SEO", () => {
  it("maps title, description and keywords into the request", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#seo_title").setValue("Acme 官网");
    await wrapper.find("#seo_description").setValue("菜品与预订信息");
    await wrapper.find("#seo_keywords").setValue("餐厅，菜单, 预订");
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.seo.title).toBe("Acme 官网");
    expect(preview.seo.description).toBe("菜品与预订信息");
    expect(preview.seo.keywords).toEqual(["餐厅", "菜单", "预订"]);
  });

  it("maps an optional SEO file to seo_file metadata only", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    const seoInput = wrapper.find("#seo_file");
    setFiles(seoInput, [fakeFile("source.csv", "text/csv", 2048)]);
    await seoInput.trigger("change");
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.seo.upload).toEqual({
      field_name: "seo_file",
      original_name: "source.csv",
      size: 2048,
      media_type: "text/csv"
    });
  });

  it("keeps seo.upload null when no file is selected", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    const preview = JSON.parse(wrapper.find("#json-preview").text());
    expect(preview.seo.upload).toBe(null);
  });
});

describe("localStorage draft", () => {
  it("saves a draft that never contains File objects or bytes", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#seo_title").setValue("草稿标题");
    await wrapper.find("#add-reference").trigger("click");
    const row = wrapper.find(".reference-row");
    await row.find(".ref-purpose").setValue("about");
    setFiles(row.find(".ref-file"), [fakeFile("photo.jpg", "image/jpeg", 555)]);
    await row.find(".ref-file").trigger("change");
    setFiles(wrapper.find("#seo_file"), [fakeFile("seo.json", "application/json", 10)]);
    await wrapper.find("#seo_file").trigger("change");

    const raw = localStorage.getItem(DRAFT_KEY);
    expect(raw).not.toBeNull();
    const draft = JSON.parse(raw);
    expect(draft.seoTitle).toBe("草稿标题");
    expect(draft.references).toHaveLength(1);
    expect(draft.references[0]).toEqual({
      client_id: draft.references[0].client_id,
      field_name: "reference:" + draft.references[0].client_id,
      purpose: "about",
      notes: "",
      file_name: "photo.jpg",
      needs_reselect: true
    });
    expect(draft.seo_file_name).toBe("seo.json");
    expect("seoFile" in draft).toBe(false);
    expect("file" in draft.references[0]).toBe(false);
    expect(raw).not.toMatch(/DO_NOT_STORE|bytes|arrayBuffer|base64/);
  });

  it("restores text fields, custom FAQ rows and reference rows from a draft", async () => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      projectId: "restored-1",
      industry: "软件",
      siteType: "官网",
      brand: "恢复的品牌",
      targetAudience: "IT",
      primaryGoal: "演示",
      requiredSections: "首页",
      freeformRequest: "恢复需求",
      faqMode: "custom",
      customFaq: [
        { question: "恢复的问题", answer: "恢复的答案", order: 0 },
        { question: "空答案", answer: "", order: 1 }
      ],
      references: [{
        client_id: "ref-restored", field_name: "reference:ref-restored",
        purpose: "hero", notes: "恢复备注", file_name: "hero.png", needs_reselect: true
      }]
    }));
    const wrapper = mount(App);
    expect(wrapper.find("#project_id").element.value).toBe("restored-1");
    expect(wrapper.find("#brand").element.value).toBe("恢复的品牌");
    expect(wrapper.find('input[name="faq_mode"][value="custom"]').element.checked).toBe(true);
    const faqRows = wrapper.findAll(".faq-row");
    expect(faqRows).toHaveLength(2);
    expect(faqRows[0].find(".faq-question").element.value).toBe("恢复的问题");
    const refRows = wrapper.findAll(".reference-row");
    expect(refRows).toHaveLength(1);
    expect(refRows[0].attributes("data-client-id")).toBe("ref-restored");
    expect(refRows[0].find(".ref-purpose").element.value).toBe("hero");
  });
});

describe("validation and error summary", () => {
  it("blocks submit when required fields are empty and focuses the first error", async () => {
    const wrapper = mount(App, { attachTo: document.body });
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    const summary = wrapper.find("#error-summary");
    expect(summary.isVisible()).toBe(true);
    expect(summary.attributes("tabindex")).toBe("-1");
    const items = summary.findAll("li");
    expect(items.length).toBeGreaterThanOrEqual(8);
    expect(items[0].text()).toBe("请输入项目 ID");
    expect(document.activeElement.id).toBe("project_id");
    wrapper.unmount();
  });

  it("reports a missing reference file and missing purpose together", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#add-reference").trigger("click");
    await wrapper.find("form").trigger("submit");
    const texts = wrapper.findAll("#error-summary li").map((li) => li.text());
    expect(texts).toContain("参考图 1 需要重新选择文件");
    expect(texts).toContain("参考图 1 必须选择用途");
  });

  it("reports an oversized reference image and oversized SEO file", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#add-reference").trigger("click");
    const row = wrapper.find(".reference-row");
    setFiles(row.find(".ref-file"), [fakeFile("big.png", "image/png", 8 * 1024 * 1024 + 1)]);
    await row.find(".ref-file").trigger("change");
    await row.find(".ref-purpose").setValue("hero");
    setFiles(wrapper.find("#seo_file"), [fakeFile("big.csv", "text/csv", 2 * 1024 * 1024 + 1)]);
    await wrapper.find("#seo_file").trigger("change");
    await wrapper.find("form").trigger("submit");
    const texts = wrapper.findAll("#error-summary li").map((li) => li.text());
    expect(texts).toContain("参考图 1 超过 8 MiB");
    expect(texts).toContain("SEO 文档超过 2 MiB");
  });

  it("reports a custom FAQ row without a question", async () => {
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find('input[name="faq_mode"][value="custom"]').setValue();
    await wrapper.find("#add-faq").trigger("click");
    await wrapper.find("form").trigger("submit");
    const texts = wrapper.findAll("#error-summary li").map((li) => li.text());
    expect(texts).toContain("自定义 FAQ 1 需要问题");
  });

  it("clears the error summary once a valid submission succeeds", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ request_id: "req-ok", absolute_path: "C:/requests/req-ok", relative_path: "intake/requests/req-ok" })
    }));
    const wrapper = mount(App, { attachTo: document.body });
    await wrapper.find("form").trigger("submit");
    expect(wrapper.find("#error-summary").isVisible()).toBe(true);
    await fillRequired(wrapper);
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(wrapper.find("#status").text()).toBe("已保存");
    expect(wrapper.find("#error-summary").attributes("style") || "").toContain("display: none");
    expect(wrapper.find("#error-summary").isVisible()).toBe(false);
    expect(wrapper.find("#success").isVisible()).toBe(true);
    wrapper.unmount();
  });
});


describe("submission contract", () => {
  it("POSTs payload and named multipart files, shows saving then receipt identity and path", async () => {
    let resolveFetch;
    const fetchMock = vi.fn(() => new Promise((resolve) => { resolveFetch = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("#add-reference").trigger("click");
    const row = wrapper.find(".reference-row");
    await row.find(".ref-purpose").setValue("hero");
    const image = new File(["png"], "hero.png", { type: "image/png" });
    setFiles(row.find(".ref-file"), [image]);
    await row.find(".ref-file").trigger("change");
    const seo = new File(["title"], "seo.txt", { type: "text/plain" });
    setFiles(wrapper.find("#seo_file"), [seo]);
    await wrapper.find("#seo_file").trigger("change");

    await wrapper.find("form").trigger("submit");
    expect(wrapper.find("#status").text()).toBe("正在保存…");
    expect(wrapper.find("#submit").attributes("disabled")).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/requests");
    expect(options.method).toBe("POST");
    const entries = Array.from(options.body.entries());
    const payload = JSON.parse(entries.find(([name]) => name === "payload")[1]);
    expect(payload.project_id).toBe("acme-2026");
    const referenceEntry = entries.find(([name]) => name.startsWith("reference:"));
    expect(referenceEntry[0]).toBe("reference:" + payload.references[0].client_id);
    expect(referenceEntry[1].name).toBe("hero.png");
    expect(entries.find(([name]) => name === "seo_file")[1].name).toBe("seo.txt");

    resolveFetch({ ok: true, json: async () => ({ request_id: "req-123", absolute_path: "C:/safe/req-123", relative_path: "intake/requests/req-123" }) });
    await flushPromises();
    expect(wrapper.find("#status").text()).toBe("已保存");
    expect(wrapper.find("#result-id").text()).toBe("req-123");
    expect(wrapper.find("#result-absolute").text()).toBe("C:/safe/req-123");
    expect(wrapper.find("#result-relative").text()).toBe("intake/requests/req-123");
  });

  it("shows save failure and removes an old success receipt before retrying", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ request_id: "old", absolute_path: "C:/old", relative_path: "intake/requests/old" }) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({ message: "磁盘已满" }) });
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(wrapper.find("#success").exists()).toBe(true);
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(wrapper.find("#status").text()).toBe("保存失败");
    expect(wrapper.find("#success").exists()).toBe(false);
    expect(wrapper.find("#error-summary").text()).toContain("磁盘已满");
  });

  it("starts the Agent for the immutable request only after a successful save", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ request_id: "req-123", absolute_path: "C:/safe/req-123", relative_path: "intake/requests/req-123" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ run_id: "run-123", request_id: "req-123", status: "running" }) });
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(wrapper.find("#start-agent").exists()).toBe(true);
    await wrapper.find("#start-agent").trigger("click");
    await flushPromises();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/runs");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ request_id: "req-123" });
    expect(wrapper.find("#agent-run-status").text()).toContain("run-123");
    expect(wrapper.find("#start-agent").attributes("disabled")).toBeDefined();
  });

  it("shows an honest error when no Agent provider is configured", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ request_id: "req-123", absolute_path: "C:/safe/req-123", relative_path: "intake/requests/req-123" }) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({ error: "agent_not_configured", message: "Agent 未配置" }) });
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(App);
    await fillRequired(wrapper);
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    await wrapper.find("#start-agent").trigger("click");
    await flushPromises();
    expect(wrapper.find("#agent-run-error").text()).toBe("Agent 未配置");
    expect(wrapper.find("#start-agent").attributes("disabled")).toBeUndefined();
  });
});
