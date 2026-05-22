import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const urls = {
  wizsense2: "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-2-series",
  wizsense3: "https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series",
};

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = `D:\\work\\auto-CompetitionAnalysis\\results\\dahua_wizsense_structure_${runId}`;
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:\\Users\\12298\\AppData\\Local\\ms-playwright\\chromium-1223\\chrome-win64\\chrome.exe",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const page = await browser.newPage({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

async function gotoWithRetries(target) {
  for (let i = 0; i < 8; i++) {
    try {
      await page.goto(target, { waitUntil: "networkidle", timeout: 90000 });
    } catch {
      await page.waitForTimeout(3000);
      continue;
    }
    await page.waitForTimeout(5000);
    const html = await page.content();
    if (html.length > 5000) return;
    await page.waitForTimeout(4000);
  }
}

async function discoverTabs() {
  const tabs = await page.evaluate(() => {
    const els = Array.from(document.querySelectorAll("div.tabs-li"));
    const out = [];
    for (const el of els) {
      const t = (el.getAttribute("title") || el.innerText || el.textContent || "")
        .replace(/\s+/g, " ")
        .trim();
      if (!t) continue;
      if (t.length > 80) continue;
      out.push(t);
    }
    return Array.from(new Set(out));
  });
  return tabs.length ? tabs : ["default"];
}

async function clickTab(tabName) {
  if (tabName === "default") return;
  await page.evaluate((tabName) => {
    const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
    const els = Array.from(document.querySelectorAll("div.tabs-li"));
    for (const el of els) {
      const t = norm(el.innerText || el.textContent || "");
      if (t === tabName) {
        el.click();
        return;
      }
    }
  }, tabName);
  await page.waitForTimeout(1800);
}

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

function modelFromUrl(u) {
  const url = normalizeUrl(u).toLowerCase();
  const m = url.match(/\/(ipc-[^/?#]+|dh-[^/?#]+)\/?$/i);
  if (!m) return null;
  return m[1].toUpperCase();
}

async function extractProducts() {
  const items = await page.evaluate(() => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const byUrl = new Map();
    for (const a of anchors) {
      const raw = a.getAttribute("href") || "";
      const abs = raw.startsWith("http") ? raw : `${location.origin}${raw.startsWith("/") ? "" : "/"}${raw}`;
      const href = norm(abs);
      const l = href.toLowerCase();
      if (!l.includes("/products/network-products/network-cameras/")) continue;
      if (!l.match(/\/(ipc-[^/?#]+|dh-[^/?#]+)\/?$/i)) continue;
      if (!byUrl.has(href)) {
        const text = (a.textContent || "").replace(/\s+/g, " ").trim();
        byUrl.set(href, { url: href, text });
      }
    }
    return Array.from(byUrl.values());
  });

  const out = [];
  for (const it of items) {
    const model = modelFromUrl(it.url);
    if (!model) continue;
    const name = it.text && it.text.toLowerCase() !== "skip to content" ? it.text : model;
    out.push({ model, name, url: normalizeUrl(it.url) });
  }
  out.sort((a, b) => a.model.localeCompare(b.model));
  return out;
}

async function collectAllProductsByPagination(maxPages = 200) {
  const byUrl = new Map();
  let stable = 0;

  for (let i = 0; i < maxPages; i++) {
    const products = await extractProducts();
    for (const p of products) {
      if (!byUrl.has(p.url)) byUrl.set(p.url, p);
    }

    const state = await page.evaluate(() => {
      const next = document.querySelector(".pagination .btn-next");
      const nextDisabled = !!next?.classList?.contains("disabled");
      const active = document.querySelector(".pagination .el-pager li.active");
      const activePage = Number((active?.textContent || "").trim() || "0") || 0;
      return { nextDisabled, activePage };
    });

    if (state.nextDisabled) break;

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(200);

    await page.evaluate(() => {
      const next = document.querySelector(".pagination .btn-next");
      if (next && !next.classList.contains("disabled")) next.click();
    });

    await page.waitForFunction(
      (prev) => {
        const active = document.querySelector(".pagination .el-pager li.active");
        const cur = Number((active?.textContent || "").trim() || "0") || 0;
        return cur && cur !== prev;
      },
      state.activePage,
      { timeout: 30000 },
    ).catch(() => {});

    await page.waitForTimeout(1200);

    const sizeNow = byUrl.size;
    const productsAfter = await extractProducts();
    for (const p of productsAfter) {
      if (!byUrl.has(p.url)) byUrl.set(p.url, p);
    }
    if (byUrl.size <= sizeNow) stable += 1;
    else stable = 0;
    if (stable >= 5) break;
  }

  return Array.from(byUrl.values()).sort((a, b) => a.model.localeCompare(b.model));
}

function normalizeSeriesNameFromUrl(seriesUrl) {
  if (seriesUrl.includes("wizsense-2-series")) return { series_key: "WizSense 2", series_raw: "WizSense 2 Series" };
  if (seriesUrl.includes("wizsense-3-series")) return { series_key: "WizSense 3", series_raw: "WizSense 3 Series" };
  return { series_key: seriesUrl, series_raw: seriesUrl };
}

const structure = {
  generated_at: new Date().toISOString(),
  brand: "dahua",
  entry: urls,
  series: {},
};

async function buildSeries(seriesUrl) {
  const { series_key, series_raw } = normalizeSeriesNameFromUrl(seriesUrl);
  await gotoWithRetries(seriesUrl);
  await writeFile(
    `${outDir}/${series_key.replaceAll(" ", "_").toLowerCase()}_page.html`,
    await page.content(),
    "utf-8",
  );
  const tabs = await discoverTabs();

  const selectedTabs = tabs;

  structure.series[series_key] = {
    series_l1: series_key,
    series_l1_raw: series_raw,
    series_page: seriesUrl,
    discovered_tabs: tabs,
    subseries: {},
  };

  for (const tab of selectedTabs) {
    await clickTab(tab);
    const products = await collectAllProductsByPagination();
    structure.series[series_key].subseries[tab] = {
      series_l1: series_key,
      subseries: tab,
      models_count: products.length,
      models: products,
      sample_models: products.slice(0, 20),
    };
  }
}

await buildSeries(urls.wizsense2);
await buildSeries(urls.wizsense3);

await writeFile(`${outDir}/dahua_wizsense_structure.json`, JSON.stringify(structure, null, 2), "utf-8");

console.log(`OUT_DIR=${outDir}`);
console.log(
  `WIZSENSE2_SUBSERIES=${Object.keys(structure.series["WizSense 2"]?.subseries || {}).length} WIZSENSE3_SUBSERIES=${Object.keys(structure.series["WizSense 3"]?.subseries || {}).length}`,
);
console.log("WIZSENSE2_NAMES=" + JSON.stringify(Object.keys(structure.series["WizSense 2"]?.subseries || {})));
console.log("WIZSENSE3_NAMES=" + JSON.stringify(Object.keys(structure.series["WizSense 3"]?.subseries || {})));
console.log("WIZSENSE2_COUNTS=" + JSON.stringify(
  Object.fromEntries(Object.entries(structure.series["WizSense 2"]?.subseries || {}).map(([k, v]) => [k, v.models_count]))
));
console.log("WIZSENSE3_COUNTS=" + JSON.stringify(
  Object.fromEntries(Object.entries(structure.series["WizSense 3"]?.subseries || {}).map(([k, v]) => [k, v.models_count]))
));

await page.close();
await browser.close();
