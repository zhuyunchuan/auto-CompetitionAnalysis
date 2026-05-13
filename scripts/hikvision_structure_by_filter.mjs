import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const urls = {
  pro: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/?category=Network+Products&subCategory=Network+Cameras&series=Pro+Series&checkedSubSeries=NONE",
  value: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/?category=Network+Products&subCategory=Network+Cameras&series=Value+Series&checkedSubSeries=NONE",
  hilook:
    "https://www.hikvision.com/en/products/HiLook-IP-Products/Network-Cameras/Value-Camera/",
};

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = `/workspace/results/hikvision_structure_filtered_${runId}`;
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const page = await browser.newPage({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

async function gotoWithChallengeRetries(target) {
  for (let i = 0; i < 8; i++) {
    try {
      await page.goto(target, { waitUntil: "domcontentloaded", timeout: 180000 });
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

async function trySetPerPage(maxPerPage = "36") {
  try {
    await page.selectOption("select.number-select", maxPerPage);
    await waitForResultsIdle(60000);
    await page.waitForTimeout(800);
  } catch {}
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

async function forceLoadAllProducts(maxRounds = 240) {
  await waitForResultsIdle(90000);
  await trySetPerPage("36");
  await waitForResultsIdle(90000);
  const total = (await getTotalMatchesFromDom()) ?? (await extractProductCountHint());

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
  const items = await page.evaluate(() => {
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
    return Array.from(byUrl.values());
  });

  const out = [];
  for (const it of items) {
    const model = toModelFromUrl(it.url);
    if (!model) continue;
    const name = it.text && it.text.toLowerCase() !== "skip to content" ? it.text : model;
    out.push({ model, name, url: normalizeUrl(it.url) });
  }
  out.sort((a, b) => a.model.localeCompare(b.model));
  return out;
}

async function extractProductCountHint() {
  return await page.evaluate(() => {
    const text = (document.body?.innerText || "").replace(/\s+/g, " ");
    const m = text.match(/\((\d+)\)\s*Category/i);
    if (m) return Number(m[1]);
    const m2 = text.match(/(\d+)\s*Products Matches/i);
    if (m2) return Number(m2[1]);
    return null;
  });
}

async function extractProSubseriesOptions() {
  return [
    "EasyIP 4.0 with ColorVu",
    "EasyIP 4.0 Series ColorVu",
    "EasyIP 4.0 with AcuSense",
    "EasyIP 3.0",
    "EasyIP 2.0 Plus with AcuSense",
    "EasyIP 2.0 Plus",
    "EasyIP 1.0 Plus",
    "EasyIP 4.0 Plus with ColorVu",
    "EasyIP 4.0 Plus with AcuSense",
  ];
}

async function extractValueSubseriesOptions() {
  return await page.evaluate(() => {
    const inputs = Array.from(document.querySelectorAll('input[type="checkbox"][name="enquiryType"]'));
    const labels = Array.from(document.querySelectorAll('input[type="checkbox"][name="enquiryType"] + label'));
    const options = [];
    for (let i = 0; i < inputs.length; i++) {
      const value = inputs[i].getAttribute("value") || "";
      const labelText = labels[i]?.textContent?.trim() || decodeURIComponent(value);
      if (
        value &&
        labelText &&
        labelText.length > 1 &&
        labelText.length < 100 &&
        labelText.startsWith("Value Series")
      ) {
        options.push(labelText);
      }
    }
    return options;
  });
}

async function applySubseriesFilter(subseriesName) {
  const encoded = encodeURIComponent(subseriesName);
  const base = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/";
  const params = "category=Network+Products&subCategory=Network+Cameras&series=Value+Series";
  const target = `${base}?${params}&checkedSubSeries=${encoded}`;
  for (let retry = 0; retry < 5; retry++) {
    try {
      await page.goto(target, { waitUntil: "domcontentloaded", timeout: 60000 });
      break;
    } catch {
      await page.waitForTimeout(3000);
    }
  }
  await page.waitForTimeout(5000);
}

const structure = {
  generated_at: new Date().toISOString(),
  series: {},
  notes: [
    "Pro 通过页面 Subseries 过滤器枚举；Value 系列通过 search_list.json API 按 Subseries 字段分组提取；HiLook 按 Value Camera 页面枚举。",
    "型号列表通过 View More/分页强制加载，尽量拉满页面可提供的全部型号。",
  ],
};

structure.series.Pro = {};
await gotoWithChallengeRetries(urls.pro);
await forceLoadAllProducts(60);
const proSubseries = await extractProSubseriesOptions();

for (const sub of proSubseries) {
  await applySubseriesFilter(sub);
  const totalHint = await forceLoadAllProducts(240);
  const products = await extractVisibleProducts();
  const countHint = (() => {
    const hint = totalHint ?? null;
    if (hint && hint > 0) return hint;
    return products.length;
  })();
  structure.series.Pro[sub] = {
    series_l1: "Pro",
    subseries: sub,
    count_hint: countHint,
    models_count: products.length,
    models: products,
    sample_models: products.slice(0, 20),
  };
}

structure.series.Value = {};
await gotoWithChallengeRetries(urls.value);
await page.waitForTimeout(8000);

const valueApiUrl = await page.evaluate(() => {
  const pathParts = window.location.pathname.split("/").filter(Boolean);
  const idx = pathParts.findIndex((p) => p === "products");
  if (idx < 0) return null;
  const contentPath = pathParts.slice(0, idx + 1).join("/");
  return `https://www.hikvision.com/content/hikvision/en${contentPath}/jcr:content/root/responsivegrid/search_list.json`;
});

if (valueApiUrl) {
  const apiData = await page.evaluate(async (url) => {
    const res = await fetch(url);
    return await res.json();
  }, valueApiUrl);

  if (apiData && apiData.products && Array.isArray(apiData.products)) {
    const subseriesMap = {};
    for (const p of apiData.products) {
      const subseries = p.selectParameters?.Subseries?.[0] || p.subseries || "Value Series";
      if (!subseriesMap[subseries]) subseriesMap[subseries] = [];
      const model = (p.productModel || "").toUpperCase().trim();
      const title = (p.title || model).replace(/\s+/g, " ").trim();
      const detailPath = p.detailPath || "";
      const url = detailPath ? `https://www.hikvision.com${detailPath}` : "";
      const desc = (p.description || "").replace(/\s+/g, " ").trim();
      if (model) {
        subseriesMap[subseries].push({ model, name: title, url, description: desc });
      }
    }

    for (const [subseries, products] of Object.entries(subseriesMap)) {
      structure.series.Value[subseries] = {
        series_l1: "Value",
        subseries,
        models_count: products.length,
        models: products.sort((a, b) => a.model.localeCompare(b.model)),
        sample_models: products.slice(0, 30),
      };
    }
    console.log(`VALUE_SUBSERIES=${Object.keys(subseriesMap).length}`);
  } else {
    const totalHint = await forceLoadAllProducts(240);
    const products = await extractVisibleProducts();
    structure.series.Value["Value Series"] = {
      series_l1: "Value",
      subseries: "Value Series",
      count_hint: totalHint && totalHint > 0 ? totalHint : products.length,
      models_count: products.length,
      models,
      sample_models: products.slice(0, 30),
    };
  }
} else {
  const totalHint = await forceLoadAllProducts(240);
  const products = await extractVisibleProducts();
  structure.series.Value["Value Series"] = {
    series_l1: "Value",
    subseries: "Value Series",
    count_hint: totalHint && totalHint > 0 ? totalHint : products.length,
    models_count: products.length,
    models,
    sample_models: products.slice(0, 30),
  };
}

structure.series.HiLook = {};
await gotoWithChallengeRetries(urls.hilook);
{
  const totalHint = await forceLoadAllProducts(240);
  const products = await extractVisibleProducts();
  structure.series.HiLook["Value Camera"] = {
    series_l1: "HiLook",
    subseries: "Value Camera",
    count_hint: totalHint && totalHint > 0 ? totalHint : products.length,
    models_count: products.length,
    models: products,
    sample_models: products.slice(0, 30),
  };
}

await writeFile(`${outDir}/structure_filtered.json`, JSON.stringify(structure, null, 2), "utf-8");
console.log(`OUT_DIR=${outDir}`);
console.log(
  `PRO_SUBSERIES=${Object.keys(structure.series.Pro).length} VALUE_SUBSERIES=${Object.keys(structure.series.Value).length} HILOOK_MODELS=${structure.series.HiLook['Value Camera'].sample_models.length}`,
);

await page.close();
await browser.close();
