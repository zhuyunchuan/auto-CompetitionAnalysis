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

const outDir = path.join(process.cwd(), "results", `hikvision_value_api_${runId}`);
await mkdir(outDir, { recursive: true });

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

function toModelFromUrl(u) {
  const url = normalizeUrl(u).toLowerCase();
  const m = url.match(/\/((ds|ids|ipc)-[^/?#]+)\/?$/i);
  if (m) return m[1].toUpperCase();
  return null;
}

async function fetchAllProductsViaBrowser(page) {
  // Call the internal API via page.evaluate to get the full JSON
  const apiUrl = await page.evaluate(() => {
    // Find the search_list.json URL from network requests or construct it
    const pathParts = window.location.pathname.split("/").filter(Boolean);
    // e.g. /en/products/IP-Products/Network-Cameras/value-series
    const idx = pathParts.findIndex((p) => p === "products");
    if (idx < 0) return null;
    const contentPath = pathParts.slice(0, idx + 1).join("/");
    return `https://www.hikvision.com/content/hikvision/en${contentPath}/jcr:content/root/responsivegrid/search_list.json`;
  });

  if (!apiUrl) return [];

  const response = await page.evaluate(async (url) => {
    const res = await fetch(url);
    const data = await res.json();
    return data;
  }, apiUrl);

  return response;
}

async function extractAllProducts(page) {
  // Method 1: From the page DOM
  const domProducts = await page.evaluate(() => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
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
      const model = (() => {
        const url = norm(it.url).toLowerCase();
        const m = url.match(/\/((ds|ids|ipc)-[^/?#]+)\/?$/i);
        if (m) return m[1].toUpperCase();
        return null;
      })();
      if (!model) continue;
      const name = it.text && it.text.toLowerCase() !== "skip to content" ? it.text : model;
      out.push({ model, name, url: norm(it.url) });
    }
    out.sort((a, b) => a.model.localeCompare(b.model));
    return out;
  });

  // Method 2: From the JSON API (more reliable)
  const apiData = await fetchAllProductsViaBrowser(page);
  const apiProducts = [];
  if (apiData && apiData.products && Array.isArray(apiData.products)) {
    for (const p of apiData.products) {
      const model = (p.productModel || "").toUpperCase().trim();
      const title = (p.title || model).replace(/\s+/g, " ").trim();
      const subseries = p.selectParameters?.Subseries?.[0] || p.subseries || "Unknown";
      const detailPath = p.detailPath || p.pagePath || "";
      const url = detailPath ? `https://www.hikvision.com${detailPath}` : "";
      if (model) {
        apiProducts.push({ model, name: title, url, subseries });
      }
    }
    apiProducts.sort((a, b) => a.model.localeCompare(b.model));
  }

  return { domProducts, apiProducts, apiData };
}

async function clickViewMore() {
  return await page.evaluate(() => {
    const el = document.querySelector(".product-view-more-btn");
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
    if (typeof el.click === "function") { el.click(); return true; }
    return false;
  });
}

async function clickNextPage() {
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
    if (el && typeof el.click === "function") { el.click(); return true; }
    return false;
  });
}

async function waitForResultsIdle(timeoutMs = 90000) {
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

async function forceLoadAllProducts() {
  await waitForResultsIdle(90000);
  const total = await page.evaluate(() => {
    const el = document.querySelector(".sum-number-of-products");
    const text = (el?.textContent || "").replace(/[,\s]+/g, "").trim();
    if (!text) return null;
    const n = Number(text);
    return Number.isFinite(n) ? n : null;
  });

  let stableRounds = 0;
  for (let i = 0; i < 120; i++) {
    const loadedBefore = await page.evaluate(() => document.querySelectorAll("a.btn-details-link[href], .product-item").length);

    let progressed = false;
    if (await clickViewMore()) progressed = true;
    else if (await clickNextPage()) progressed = true;
    else {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      progressed = true;
    }

    if (!progressed) break;
    await waitForResultsIdle(90000);
    await page.waitForTimeout(1500);

    const loadedAfter = await page.evaluate(() => document.querySelectorAll("a.btn-details-link[href], .product-item").length);
    if (loadedAfter <= loadedBefore) stableRounds += 1;
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
  userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

// Navigate to the base Value Series page (no subseries filter)
const baseUrl = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/";

console.log("\n=== 加载 Value 系列全量页面 ===");
for (let retry = 0; retry < 5; retry++) {
  try {
    await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    break;
  } catch {
    await page.waitForTimeout(3000);
  }
}
await page.waitForTimeout(10000);

console.log("加载全部产品...");
await forceLoadAllProducts();

console.log("\n提取产品数据...");
// Method 1: API (most reliable - has subseries info)
const apiData = await page.evaluate(async () => {
  const url = window.location.pathname;
  const idx = url.split("/").findIndex((p) => p === "products");
  if (idx < 0) return null;
  const contentPath = url.split("/").slice(0, idx + 1).join("/");
  const apiUrl = `https://www.hikvision.com/content/hikvision/en${contentPath}/jcr:content/root/responsivegrid/search_list.json`;
  try {
    const res = await fetch(apiUrl);
    return await res.json();
  } catch (e) {
    return { error: e.message, url: apiUrl };
  }
});

const result = {
  generated_at: new Date().toISOString(),
  url: baseUrl,
  api_data_summary: null,
  by_subseries: {},
  by_subseries_dom: {},
};

if (apiData && apiData.products && Array.isArray(apiData.products)) {
  const totalProducts = apiData.products.length;
  console.log(`\n=== API 数据分析 ===`);
  console.log(`API 总产品数: ${totalProducts}`);

  // Group by subseries
  const subseriesMap = {};
  for (const p of apiData.products) {
    const subseries = p.selectParameters?.Subseries?.[0] || p.subseries || "Unknown";
    if (!subseriesMap[subseries]) subseriesMap[subseries] = [];
    const model = (p.productModel || "").toUpperCase().trim();
    const title = (p.title || model).replace(/\s+/g, " ").trim();
    const detailPath = p.detailPath || "";
    const url = detailPath ? `https://www.hikvision.com${detailPath}` : "";
    if (model) {
      subseriesMap[subseries].push({ model, name: title, url });
    }
  }

  console.log(`\n各子系列产品数量（按 API 数据）:`);
  const sortedSubs = Object.entries(subseriesMap).sort((a, b) => b[1].length - a[1].length);
  for (const [name, products] of sortedSubs) {
    console.log(`  "${name}": ${products.length} 个型号`);
  }

  result.api_data_summary = {
    total_products: totalProducts,
    total_subseries: sortedSubs.length,
  };

  result.by_subseries = {};
  for (const [name, products] of sortedSubs) {
    result.by_subseries[name] = {
      subseries: name,
      models_count: products.length,
      models: products,
      sample_models: products.slice(0, 30),
    };
  }
} else {
  console.log("API 调用失败:", JSON.stringify(apiData));
}

// Also extract from DOM for comparison
const domProducts = await page.evaluate(() => {
  const norm = (u) => (u || "").split("#")[0].split("?")[0];
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
    const url = norm(it.url).toLowerCase();
    const m = url.match(/\/((ds|ids|ipc)-[^/?#]+)\/?$/i);
    if (!m) continue;
    const model = m[1].toUpperCase();
    const name = it.text && it.text.toLowerCase() !== "skip to content" ? it.text : model;
    out.push({ model, name, url: norm(it.url) });
  }
  out.sort((a, b) => a.model.localeCompare(b.model));
  return out;
});

console.log(`\nDOM 提取产品数: ${domProducts.length}`);

// Extract subseries from each product page (sample)
console.log("\n尝试从产品详情页提取子系列信息（抽样10个）...");
const samples = domProducts.slice(0, 10);
for (const sample of samples) {
  try {
    await page.goto(sample.url, { waitUntil: "domcontentloaded", timeout: 15000 });
    await page.waitForTimeout(3000);
    const subseries = await page.evaluate(() => {
      const selectors = [
        ".subseries-name", ".product-subseries",
        "[data-subseries]", ".product-info .subseries",
        ...Array.from(document.querySelectorAll("[class*=subseries]")).map((el) => el.className),
      ];
      // Look in product specifications table
      const allText = document.body.innerText;
      const match = allText.match(/subseries[:\s]+([^\n\r]{3,60})/i);
      if (match) return match[1].trim();
      // Look in breadcrumb or product header
      const crumbs = Array.from(document.querySelectorAll("a[href*='value'], [class*=breadcrumb] a"));
      for (const c of crumbs) {
        const text = (c.textContent || "").trim();
        if (text.toLowerCase().includes("value series") && text.length > 5) return text;
      }
      return null;
    });
    console.log(`  ${sample.model}: subseries="${subseries}"`);
  } catch {
    console.log(`  ${sample.model}: 跳转失败`);
  }
}

const outFile = path.join(outDir, "value_subseries_analysis.json");
await writeFile(outFile, JSON.stringify(result, null, 2), "utf-8");
console.log(`\n结果已保存: ${outFile}`);

await page.close();
await browser.close();
