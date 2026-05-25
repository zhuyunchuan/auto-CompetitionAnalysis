import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = path.join(process.cwd(), "results", `hikvision_value_test_${runId}`);
await mkdir(outDir, { recursive: true });

const VALUE_SUBSERIES_FILTERS = [
  "Value Series with MD 2.0",
  "Value Series with ColorVu & MD 2.0",
  "Value Series with ColorVu",
  "Value Series Essential",
  "Value Series with ColorVu 3.0 & MD 3.0",
];

function buildValueSubseriesUrl(subseriesName) {
  const encoded = encodeURIComponent(subseriesName);
  return `https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/?category=Network+Products&subCategory=Network+Cameras&series=Value+Series&checkedSubSeries=${encoded}`;
}

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

function toModelFromUrl(u) {
  const url = normalizeUrl(u).toLowerCase();
  const m = url.match(/\/((ds|ids|ipc)-[^/?#]+)\/?$/i);
  if (m) return m[1].toUpperCase();
  const last = url.match(/\/([^/?#]+)\/?$/i);
  if (!last) return null;
  return decodeURIComponent(last[1]).toUpperCase();
}

async function extractVisibleProducts() {
  return await page.evaluate(() => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
    const toModelFromUrl = (u) => {
      const url = norm(u).toLowerCase();
      const m = url.match(/\/((ds|ids|ipc)-[^/?#]+)\/?$/i);
      if (m) return m[1].toUpperCase();
      const last = url.match(/\/([^/?#]+)\/?$/i);
      if (!last) return null;
      return decodeURIComponent(last[1]).toUpperCase();
    };
    const primary = Array.from(document.querySelectorAll("a.btn-details-link[href]"));
    const anchors = primary.length > 0 ? primary : Array.from(document.querySelectorAll("a[href]"));
    const byUrl = new Map();
    for (const a of anchors) {
      const href = norm(a.href || "");
      if (!href.toLowerCase().includes("/products/")) continue;
      if (!byUrl.has(href)) {
        const text = (a.textContent || "").replace(/\s+/g, " ").trim();
        byUrl.set(href, { url: href, text });
      }
    }
    const out = [];
    for (const it of byUrl.values()) {
      const model = toModelFromUrl(it.url);
      if (!model) continue;
      const name = it.text && it.text.toLowerCase() !== "skip to content" ? it.text : model;
      out.push({ model, name, url: norm(it.url) });
    }
    out.sort((a, b) => a.model.localeCompare(b.model));
    return out;
  });
}

async function getTotalMatchesFromDom() {
  return await page.evaluate(() => {
    const el = document.querySelector(".sum-number-of-products");
    const text = (el?.textContent || "").replace(/[,\s]+/g, "").trim();
    if (!text) return null;
    const n = Number(text);
    return Number.isFinite(n) ? n : null;
  });
}

async function getLoadedProductCountFromDom() {
  return await page.evaluate(() => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
    const primary = Array.from(document.querySelectorAll("a.btn-details-link[href]"));
    const anchors = primary.length > 0 ? primary : Array.from(document.querySelectorAll("a[href]"));
    const set = new Set();
    for (const a of anchors) {
      const href = norm(a.href || "");
      if (!href.toLowerCase().includes("/products/")) continue;
      set.add(href);
    }
    return set.size;
  });
}

async function clickViewMore() {
  return await page.evaluate(() => {
    const el = document.querySelector(".product-view-more-btn");
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
    if (typeof el.click === "function") {
      el.click();
      return true;
    }
    return false;
  });
}

async function clickNextPageIfAny() {
  return await page.evaluate(() => {
    const normalize = (t) => (t || "").replace(/\s+/g, " ").trim().toLowerCase();
    const root = document.querySelector("#layout-pagination-wrapper");
    if (!root) return false;
    const candidates = Array.from(root.querySelectorAll("a, button")).filter((el) => {
      const t = normalize(el.textContent);
      const aria = normalize(el.getAttribute("aria-label"));
      return t === "next" || aria === "next";
    });
    const el = candidates[0];
    if (el && typeof el.click === "function") {
      el.click();
      return true;
    }
    return false;
  });
}

async function waitForResultsIdle(timeoutMs = 60000) {
  await page.waitForFunction(
    () => {
      const el = document.querySelector(".product-loading");
      if (!el) return true;
      const style = window.getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return true;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return true;
      return false;
    },
    { timeout: timeoutMs },
  );
}

async function scrollToLoadAll() {
  let lastCount = 0;
  let stableRounds = 0;
  for (let i = 0; i < 80; i++) {
    const count = await page.evaluate(() => document.querySelectorAll("a[href]").length);
    if (count === lastCount) stableRounds += 1;
    else stableRounds = 0;
    lastCount = count;
    if (stableRounds >= 5) break;

    const clicked = await page.evaluate(() => {
      const candidates = Array.from(document.querySelectorAll("button, a")).filter((el) => {
        const t = (el.textContent || "").trim().toLowerCase();
        return t === "load more" || t === "more" || t === "show more";
      });
      const el = candidates[0];
      if (el && typeof el.click === "function") {
        el.click();
        return true;
      }
      return false;
    });

    if (!clicked) await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);
  }
}

async function forceLoadAllProducts(maxRounds = 120) {
  await waitForResultsIdle(90000);
  const total = (await getTotalMatchesFromDom()) ?? null;

  let stableRounds = 0;
  for (let i = 0; i < maxRounds; i++) {
    const loaded = await getLoadedProductCountFromDom();
    if (total && loaded >= total) break;

    let progressed = false;

    if (await clickViewMore()) {
      progressed = true;
    } else if (await clickNextPageIfAny()) {
      progressed = true;
    } else {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      progressed = true;
    }

    if (!progressed) break;

    await waitForResultsIdle(90000);
    await page.waitForTimeout(1200);

    const loaded2 = await getLoadedProductCountFromDom();
    if (loaded2 <= loaded) stableRounds += 1;
    else stableRounds = 0;
    if (stableRounds >= 6) break;
  }
  return total;
}

console.log("Launching Chromium...");
const browser = await chromium.launch({
  headless: true,
  executablePath: CHROME_PATH,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});

const page = await browser.newPage({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

const result = {
  generated_at: new Date().toISOString(),
  series_l1: "Value",
  subseries_results: {},
};

console.log("\n=== Hikvision Value 系列子系列抓取测试 ===");
console.log("子系列列表:", VALUE_SUBSERIES_FILTERS);

for (const subseries of VALUE_SUBSERIES_FILTERS) {
  const url = buildValueSubseriesUrl(subseries);
  console.log(`\n[${subseries}]`);
  console.log(`  URL: ${url}`);

  for (let retry = 0; retry < 5; retry++) {
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      break;
    } catch {
      await page.waitForTimeout(5000);
    }
  }

  await page.waitForTimeout(8000);
  await scrollToLoadAll();

  const totalHint = await forceLoadAllProducts(120);
  const products = await extractVisibleProducts();
  const loadedCount = await getLoadedProductCountFromDom();

  console.log(`  总数提示: ${totalHint}`);
  console.log(`  实际加载: ${loadedCount} 个链接`);
  console.log(`  有效型号: ${products.length} 个`);

  if (products.length > 0) {
    console.log(`  示例型号: ${products.slice(0, 3).map((p) => p.model).join(", ")}`);
  }

  result.subseries_results[subseries] = {
    subseries,
    url,
    total_hint: totalHint,
    loaded_links: loadedCount,
    models_count: products.length,
    models: products,
    sample_models: products.slice(0, 20),
  };
}

const outFile = path.join(outDir, "value_subseries_result.json");
await writeFile(outFile, JSON.stringify(result, null, 2), "utf-8");

console.log(`\n=== 结果汇总 ===`);
let totalModels = 0;
for (const [name, data] of Object.entries(result.subseries_results)) {
  console.log(`  "${name}": ${data.models_count} 个型号`);
  totalModels += data.models_count;
}
console.log(`型号总数: ${totalModels}`);
console.log(`输出文件: ${outFile}`);

await page.close();
await browser.close();
