import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { readFile, realpath, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import playwright from "../intake/node_modules/playwright-core/index.js";

const { chromium } = playwright;

const [siteArgument, evidenceArgument, screenshotArgument, browserExecutable, rootArgument] = process.argv.slice(2);
if (![siteArgument, evidenceArgument, screenshotArgument, browserExecutable, rootArgument].every(Boolean)) {
  throw new Error("usage: collect_browser_evidence <site> <evidence> <screenshot> <browser> <project-root>");
}

const siteRoot = await realpath(siteArgument);
const projectRoot = await realpath(rootArgument);
const evidencePath = path.resolve(evidenceArgument);
const screenshotPath = path.resolve(screenshotArgument);
const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".webp", "image/webp"],
  [".svg", "image/svg+xml"]
]);

function contained(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative !== "" && !relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative);
}

if (!contained(evidencePath, projectRoot) || !contained(screenshotPath, projectRoot)) {
  throw new Error("browser evidence outputs must stay inside the project root");
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    const decoded = decodeURIComponent(url.pathname);
    if (decoded === "/favicon.ico") {
      response.writeHead(204, { "Cache-Control": "no-store" });
      response.end();
      return;
    }
    const relative = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
    const candidate = path.resolve(siteRoot, relative);
    if (!contained(candidate, siteRoot)) throw new Error("unsafe static path");
    const canonical = await realpath(candidate);
    if (!contained(canonical, siteRoot)) throw new Error("static path escaped site root");
    const body = await readFile(canonical);
    response.writeHead(200, {
      "Content-Type": mimeTypes.get(path.extname(canonical).toLowerCase()) || "application/octet-stream",
      "X-Content-Type-Options": "nosniff",
      "Cache-Control": "no-store"
    });
    response.end(body);
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
});

await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});

let browser;
try {
  const address = server.address();
  const url = `http://127.0.0.1:${address.port}/`;
  browser = await chromium.launch({
    executablePath: browserExecutable,
    headless: true,
    args: ["--disable-gpu", "--no-first-run", "--disable-background-networking"]
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) consoleErrors.push(`${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));
  await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
  const browserFacts = await page.evaluate(() => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const bounds = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && bounds.width > 0 && bounds.height > 0;
    };
    const rectValue = (rect) => ({
      left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
      width: rect.width, height: rect.height
    });
    const headings = [...document.querySelectorAll("h1,h2,h3")].filter(visible).map((heading, index) => {
      const container = heading.closest(".container,section,header,main") || heading.parentElement || document.body;
      const range = document.createRange();
      range.selectNodeContents(heading);
      const fragments = [...range.getClientRects()]
        .filter((rect) => rect.width > 0 && rect.height > 0)
        .map(rectValue)
        .sort((left, right) => left.top - right.top || left.left - right.left);
      const lines = [];
      for (const fragment of fragments) {
        const fragmentCenter = (fragment.top + fragment.bottom) / 2;
        const line = lines.find((candidate) => {
          const candidateCenter = (candidate.top + candidate.bottom) / 2;
          const overlap = Math.min(candidate.bottom, fragment.bottom) - Math.max(candidate.top, fragment.top);
          return overlap >= Math.min(candidate.height, fragment.height) * 0.5
            || Math.abs(candidateCenter - fragmentCenter) <= 10;
        });
        if (!line) {
          lines.push({ ...fragment });
          continue;
        }
        line.left = Math.min(line.left, fragment.left);
        line.right = Math.max(line.right, fragment.right);
        line.top = Math.min(line.top, fragment.top);
        line.bottom = Math.max(line.bottom, fragment.bottom);
        line.width = line.right - line.left;
        line.height = line.bottom - line.top;
      }
      // Range rectangles describe glyph ink, which can legitimately extend
      // outside the CSS line box for display fonts.  Normalise the evidence to
      // the browser's computed line-height so the validator measures layout
      // overlap instead of ascender/descender ink overlap.
      const computedLineHeight = Number.parseFloat(getComputedStyle(heading).lineHeight);
      if (Number.isFinite(computedLineHeight) && computedLineHeight > 0) {
        for (const line of lines) {
          const center = (line.top + line.bottom) / 2;
          line.top = center - computedLineHeight / 2;
          line.bottom = center + computedLineHeight / 2;
          line.height = computedLineHeight;
        }
      }
      return {
        id: heading.id || `${heading.tagName.toLowerCase()}-${index + 1}`,
        text: heading.textContent.trim(),
        bounds: rectValue(heading.getBoundingClientRect()),
        container: rectValue(container.getBoundingClientRect()),
        lines
      };
    });
    const actionPattern = /shop|discover|explore|contact|buy|view|选购|查看|咨询|联系|了解|立即/i;
    const actions = [...document.querySelectorAll("a,button")].filter(visible);
    return {
      title: document.title,
      document: {
        scroll_width: document.documentElement.scrollWidth,
        client_width: document.documentElement.clientWidth,
        scroll_height: document.documentElement.scrollHeight,
        client_height: document.documentElement.clientHeight
      },
      dom: {
        headings: headings.length,
        links: document.querySelectorAll("a[href]").length,
        buttons: document.querySelectorAll("button").length,
        sections: document.querySelectorAll("section").length,
        product_cards: document.querySelectorAll(".catalog-card,.product-card,[data-product]").length
      },
      overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      cta: actions.some((element) => actionPattern.test(element.textContent || "")),
      headings
    };
  });
  await page.screenshot({ path: screenshotPath, fullPage: true, type: "png" });
  const screenshotBytes = await readFile(screenshotPath);
  const relativeScreenshot = path.relative(projectRoot, screenshotPath).split(path.sep).join("/");
  const evidence = {
    url,
    viewport: { width: 1440, height: 900 },
    document: browserFacts.document,
    dom: browserFacts.dom,
    overflow: browserFacts.overflow,
    cta: browserFacts.cta,
    console_errors: consoleErrors,
    screenshot_path: relativeScreenshot,
    screenshot_sha256: createHash("sha256").update(screenshotBytes).digest("hex"),
    headings: browserFacts.headings,
    page_title: browserFacts.title
  };
  await writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, { encoding: "utf8", flag: "wx" });
  process.stdout.write(`${JSON.stringify({ status: "success", evidence: evidencePath, screenshot: screenshotPath })}\n`);
} finally {
  if (browser) await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
