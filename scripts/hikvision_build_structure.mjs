import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const entryUrl =
  "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/?category=Network+Products&subCategory=Network+Cameras&checkedSubSeries=NONE";

const seeds = [
  {
    series_l1: "Pro",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/?category=Network+Products&subCategory=Network+Cameras&series=Pro+Series&checkedSubSeries=NONE",
  },
  {
    series_l1: "Value",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/?category=Network+Products&subCategory=Network+Cameras&series=Value+Series&checkedSubSeries=NONE",
  },
  {
    series_l1: "HiLook",
    url: "https://www.hikvision.com/en/products/HiLook-IP-Products/Network-Cameras/Value-Camera/",
  },
];

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = `/workspace/results/hikvision_structure_${runId}`;
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
    await page.goto(target, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(6000);
    const html = await page.content();
    if (!html.includes("EO_Bot_Ssid") && html.length > 8000) return html;
    await page.waitForTimeout(7000);
  }
  return await page.content();
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

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

async function discoverSeriesPagesFromEntry() {
  await gotoWithChallengeRetries(entryUrl);
  await scrollToLoadAll();
  const urls = await page.evaluate(() => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const out = [];
    for (const a of anchors) {
      const href = norm(a.href || "");
      const l = href.toLowerCase();
      if (!l.includes("/products/ip-products/network-cameras/")) continue;
      if (l.match(/\/ds-[^/?#]+\/?$/)) continue;
      out.push(href);
    }
    return Array.from(new Set(out));
  });
  return urls;
}

async function extractSeriesMeta(seriesUrl) {
  await gotoWithChallengeRetries(seriesUrl);
  await scrollToLoadAll();
  const meta = await page.evaluate((seriesUrl) => {
    const pick = (...sels) => {
      for (const s of sels) {
        const el = document.querySelector(s);
        if (el && el.textContent) return el.textContent.trim();
      }
      return "";
    };
    const h1 = pick("h1", ".page-title", ".title h1", ".title h2");
    const breadcrumb = Array.from(document.querySelectorAll("nav a, .breadcrumb a"))
      .map((x) => (x.textContent || "").trim())
      .filter(Boolean)
      .slice(-3);
    return { h1, breadcrumb };
  }, seriesUrl);

  const products = await page.evaluate((seriesUrl) => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const byUrl = new Map();
    for (const a of anchors) {
      const href = norm(a.href || "");
      const l = href.toLowerCase();
      if (!l.includes("/products/")) continue;
      if (!l.match(/\/ds-[^/?#]+\/?$/)) continue;
      if (!byUrl.has(href)) {
        const text = (a.textContent || "").replace(/\s+/g, " ").trim();
        byUrl.set(href, { url: href, text });
      }
    }
    const out = [];
    for (const it of byUrl.values()) {
      const m = it.url.match(/\/(ds-[^/?#]+)\/?$/i);
      const model = m ? m[1].toUpperCase() : it.url;
      const name = it.text && it.text.toLowerCase() !== "skip to content" ? it.text : model;
      out.push({ model, name, url: it.url, series_page: seriesUrl });
    }
    out.sort((a, b) => a.model.localeCompare(b.model));
    return out;
  }, seriesUrl);

  return { meta, products };
}

const discovered = await discoverSeriesPagesFromEntry();
const proPages = discovered.filter((u) => u.toLowerCase().includes("pro-series"));
const valuePages = discovered.filter((u) => u.toLowerCase().includes("value"));

const pageTasks = [];
for (const s of seeds) pageTasks.push({ series_l1: s.series_l1, url: s.url });
for (const u of proPages) pageTasks.push({ series_l1: "Pro", url: u });
for (const u of valuePages) pageTasks.push({ series_l1: "Value", url: u });

const uniq = new Map();
for (const t of pageTasks) {
  const nu = normalizeUrl(t.url);
  if (!nu) continue;
  if (!uniq.has(nu)) uniq.set(nu, { series_l1: t.series_l1, url: nu });
}

const structure = {
  generated_at: new Date().toISOString(),
  entry_url: entryUrl,
  series: {},
};

for (const t of uniq.values()) {
  const { meta, products } = await extractSeriesMeta(t.url);
  const urlParts = t.url.split("/").filter(Boolean);
  const idx = urlParts.findIndex((p) => p.toLowerCase() === "network-cameras");
  const slug = idx >= 0 ? urlParts[idx + 1] || "" : "";
  const series_l2 = meta.h1 || (slug ? slug : t.url);

  if (!structure.series[t.series_l1]) structure.series[t.series_l1] = {};
  if (!structure.series[t.series_l1][series_l2]) {
    structure.series[t.series_l1][series_l2] = {
      series_l1: t.series_l1,
      series_l2,
      series_l2_slug: slug,
      series_page: t.url,
      breadcrumb: meta.breadcrumb,
      products: [],
    };
  }

  const bucket = structure.series[t.series_l1][series_l2];
  const byModel = new Map(bucket.products.map((p) => [p.model, p]));
  for (const p of products) {
    if (!byModel.has(p.model)) byModel.set(p.model, p);
  }
  bucket.products = Array.from(byModel.values()).sort((a, b) => a.model.localeCompare(b.model));
}

await writeFile(`${outDir}/structure.json`, JSON.stringify(structure, null, 2), "utf-8");

console.log(`OUT_DIR=${outDir}`);
console.log(
  `SERIES_L1=${Object.keys(structure.series).length} SUBSERIES=${Object.values(structure.series).reduce((a, v) => a + Object.keys(v).length, 0)}`,
);

await page.close();
await browser.close();
