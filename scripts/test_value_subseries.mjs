import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const valueUrl =
  "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/?category=Network+Products&subCategory=Network+Cameras&series=Value+Series&checkedSubSeries=NONE";

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = path.join(process.cwd(), "results", `hikvision_value_test_${runId}`);
await mkdir(outDir, { recursive: true });

console.log("Launching Chromium...");
const browser = await chromium.launch({
  headless: true,
  executablePath: CHROME_PATH,
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-web-security",
  ],
});

const page = await browser.newPage({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

async function gotoWithChallengeRetries(target) {
  for (let i = 0; i < 8; i++) {
    try {
      await page.goto(target, { waitUntil: "domcontentloaded", timeout: 60000 });
    } catch {
      await page.waitForTimeout(5000);
      continue;
    }
    await page.waitForTimeout(9000);
    const html = await page.content();
    if (!html.includes("EO_Bot_Ssid") && html.length > 8000) return;
    await page.waitForTimeout(9000);
  }
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

async function extractValueSubseriesOptions() {
  return await page.evaluate(() => {
    const inputs = Array.from(document.querySelectorAll('input[type="checkbox"][name="enquiryType"]'));
    const labels = Array.from(document.querySelectorAll('input[type="checkbox"][name="enquiryType"] + label'));
    const options = [];
    for (let i = 0; i < inputs.length; i++) {
      const value = inputs[i].getAttribute("value") || "";
      const labelText = labels[i]?.textContent?.trim() || decodeURIComponent(value);
      if (value && labelText && labelText.length > 1 && labelText.length < 100) {
        options.push({ label: labelText, value });
      }
    }
    return options;
  });
}

async function applySubseriesFilter(value) {
  const encoded = encodeURIComponent(value);
  await page.evaluate((encoded) => {
    const all = Array.from(document.querySelectorAll('input[type="checkbox"][name="enquiryType"]'));
    for (const el of all) {
      el.checked = false;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
    const target = document.querySelector(`input[type="checkbox"][value="${encoded}"]`);
    if (target) {
      target.checked = true;
      target.dispatchEvent(new Event("change", { bubbles: true }));
      target.dispatchEvent(new Event("click", { bubbles: true }));
    }
  }, encoded);

  await page.evaluate(() => {
    const btn =
      document.querySelector("button.advanced-filter-submit") ||
      Array.from(document.querySelectorAll("button, input[type=submit], a")).find((el) => {
        const t = (el.textContent || "").trim().toLowerCase();
        return t === "submit";
      });
    if (btn && typeof btn.click === "function") btn.click();
  });
  await page.waitForTimeout(5000);
}

async function extractVisibleProducts() {
  return await page.evaluate(() => {
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
      const model = m ? m[1].toUpperCase() : null;
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

console.log(`\n=== Hikvision Value 系列子系列抓取测试 ===`);
console.log(`URL: ${valueUrl}\n`);

await gotoWithChallengeRetries(valueUrl);
console.log("页面加载完成，等待内容渲染...");
await page.waitForTimeout(5000);
await scrollToLoadAll();

const options = await extractValueSubseriesOptions();
console.log(`\n发现 ${options.length} 个子系列过滤器选项:`);
for (const opt of options) {
  console.log(`  - [${opt.value}] "${opt.label}"`);
}

const result = {
  generated_at: new Date().toISOString(),
  url: valueUrl,
  total_subseries: options.length,
  subseries: {},
};

if (options.length > 0) {
  for (const opt of options) {
    console.log(`\n正在抓取子系列: "${opt.label}"...`);
    await applySubseriesFilter(opt.value);
    await page.waitForTimeout(3000);
    const totalHint = await forceLoadAllProducts(120);
    const products = await extractVisibleProducts();
    console.log(`  -> 找到 ${products.length} 个产品`);
    result.subseries[opt.label] = {
      subseries: opt.label,
      filter_value: opt.value,
      count_hint: totalHint,
      models_count: products.length,
      sample_models: products.slice(0, 10),
    };
  }
} else {
  console.log("\n未发现过滤器选项，尝试直接提取页面所有产品...");
  await forceLoadAllProducts(120);
  const products = await extractVisibleProducts();
  console.log(`  -> 找到 ${products.length} 个产品`);
  result.subseries["Value Series (default)"] = {
    subseries: "Value Series",
    count_hint: products.length,
    models_count: products.length,
    sample_models: products.slice(0, 10),
  };
}

const outFile = path.join(outDir, "value_subseries_result.json");
await writeFile(outFile, JSON.stringify(result, null, 2), "utf-8");

console.log(`\n=== 结果汇总 ===`);
console.log(`子系列数量: ${options.length}`);
let totalModels = 0;
for (const [name, data] of Object.entries(result.subseries)) {
  console.log(`  "${name}": ${data.models_count} 个产品`);
  totalModels += data.models_count;
}
console.log(`产品总数: ${totalModels}`);
console.log(`输出文件: ${outFile}`);

await page.close();
await browser.close();
