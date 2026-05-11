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

async function scrollToLoadAll(maxRounds = 40) {
  let lastCount = 0;
  let stableRounds = 0;
  for (let i = 0; i < maxRounds; i++) {
    const count = await page.evaluate(() => document.querySelectorAll("a[href]").length);
    if (count === lastCount) stableRounds += 1;
    else stableRounds = 0;
    lastCount = count;
    if (stableRounds >= 5) break;

    const clicked = await page.evaluate(() => {
      const candidates = Array.from(document.querySelectorAll("button, a")).filter((el) => {
        const t = (el.textContent || "").trim().toLowerCase();
        return t === "view more" || t === "load more" || t === "more" || t === "show more";
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

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

function toModelFromUrl(u) {
  const url = normalizeUrl(u).toLowerCase();
  const m = url.match(/\/((ds|ipc)-[^/?#]+)\/?$/i);
  if (!m) return null;
  return m[1].toUpperCase();
}

async function extractVisibleProducts() {
  const items = await page.evaluate(() => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const byUrl = new Map();
    for (const a of anchors) {
      const href = norm(a.href || "");
      if (!href.toLowerCase().includes("/products/")) continue;
      if (!href.toLowerCase().match(/\/(ds|ipc)-[^/?#]+\/?$/)) continue;
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

async function applySubseriesFilter(subseriesName) {
  const encoded = encodeURIComponent(subseriesName);
  await page.evaluate((encoded) => {
    const all = Array.from(document.querySelectorAll('input[type=\"checkbox\"][name=\"enquiryType\"]'));
    for (const el of all) {
      el.checked = false;
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const target = document.querySelector(`input[type=\"checkbox\"][value=\"${encoded}\"]`);
    if (target) {
      target.checked = true;
      target.dispatchEvent(new Event('change', { bubbles: true }));
      target.dispatchEvent(new Event('click', { bubbles: true }));
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

const structure = {
  generated_at: new Date().toISOString(),
  series: {},
  notes: [
    "本结构为首次组织尝试：Pro 通过页面 Subseries 过滤器枚举；Value 暂按单一子系列；HiLook 按 Value Camera 页面枚举。",
    "每个 subseries 目前只抓取了页面可见范围内的型号（用于结构核对），并未强制翻完全部分页。",
  ],
};

structure.series.Pro = {};
await gotoWithChallengeRetries(urls.pro);
await scrollToLoadAll(30);
const proSubseries = await extractProSubseriesOptions();

for (const sub of proSubseries) {
  await applySubseriesFilter(sub);
  await scrollToLoadAll(20);
  const countHint = await extractProductCountHint();
  const products = await extractVisibleProducts();
  structure.series.Pro[sub] = {
    series_l1: "Pro",
    subseries: sub,
    count_hint: countHint,
    sample_models: products.slice(0, 20),
  };
}

structure.series.Value = {};
await gotoWithChallengeRetries(urls.value);
await scrollToLoadAll(30);
structure.series.Value["Value Series"] = {
  series_l1: "Value",
  subseries: "Value Series",
  count_hint: await extractProductCountHint(),
  sample_models: (await extractVisibleProducts()).slice(0, 30),
};

structure.series.HiLook = {};
await gotoWithChallengeRetries(urls.hilook);
await scrollToLoadAll(30);
structure.series.HiLook["Value Camera"] = {
  series_l1: "HiLook",
  subseries: "Value Camera",
  count_hint: await extractProductCountHint(),
  sample_models: (await extractVisibleProducts()).slice(0, 30),
};

await writeFile(`${outDir}/structure_filtered.json`, JSON.stringify(structure, null, 2), "utf-8");
console.log(`OUT_DIR=${outDir}`);
console.log(
  `PRO_SUBSERIES=${Object.keys(structure.series.Pro).length} VALUE_MODELS=${structure.series.Value['Value Series'].sample_models.length} HILOOK_MODELS=${structure.series.HiLook['Value Camera'].sample_models.length}`,
);

await page.close();
await browser.close();
