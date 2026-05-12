import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const entryUrl =
  "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/?category=Network+Products&subCategory=Network+Cameras&checkedSubSeries=NONE";
const seedProUrl =
  "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/?category=Network+Products&subCategory=Network+Cameras&series=Pro+Series&checkedSubSeries=NONE";

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = `/workspace/results/hikvision_pro_playwright_${runId}`;
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

async function gotoWithChallengeRetries(url) {
  for (let i = 0; i < 6; i++) {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(4000);
    const html = await page.content();
    if (!html.includes("EO_Bot_Ssid") && html.length > 5000) return html;
    await page.waitForTimeout(5000);
  }
  return await page.content();
}

async function scrollToLoadAll() {
  let lastCount = 0;
  let stableRounds = 0;
  for (let i = 0; i < 60; i++) {
    const count = await page.evaluate(() => document.querySelectorAll("a[href]").length);
    if (count === lastCount) stableRounds += 1;
    else stableRounds = 0;
    lastCount = count;
    if (stableRounds >= 4) break;

    const loadMoreClicked = await page.evaluate(() => {
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

    if (!loadMoreClicked) await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);
  }
}

async function getProSeriesPages() {
  await gotoWithChallengeRetries(entryUrl);
  await page.waitForTimeout(4000);
  const urls = await page.evaluate(() => {
    const normalize = (u) => u.split("#")[0].split("?")[0];
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const out = [];
    for (const a of anchors) {
      const href = normalize(a.href || "");
      const hrefLower = href.toLowerCase();
      const text = (a.textContent || "").trim().toLowerCase();
      if (!href.includes("/products/IP-Products/Network-Cameras/")) continue;
      if (hrefLower.match(/\/ds-[^/?#]+\/?$/)) continue;
      if (hrefLower.includes("pro-series") || text.includes("pro")) out.push(href);
    }
    return Array.from(new Set(out));
  });

  const set = new Set(urls);
  set.add(seedProUrl);
  return Array.from(set);
}

async function extractProductsFromCurrentPage(seriesPage) {
  const products = await page.evaluate((seriesPage) => {
    const normalize = (u) => u.split("#")[0].split("?")[0];
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const byUrl = new Map();
    for (const a of anchors) {
      const href = normalize(a.href || "");
      if (!href.includes("/products/IP-Products/Network-Cameras/")) continue;
      if (!href.match(/\/ds-[^/?#]+\/?$/i)) continue;
      const h3 = a.querySelector("h3");
      const text = (h3 ? h3.textContent : a.textContent || "").trim();
      if (!byUrl.has(href)) byUrl.set(href, { url: href, text });
    }
    const out = [];
    for (const it of byUrl.values()) {
      const m = it.url.match(/\/(ds-[^/?#]+)\/?$/i);
      const model = m ? m[1].toUpperCase() : it.url;
      const name = it.text && it.text.toLowerCase() !== "skip to content" ? it.text : model;
      out.push({ model, name, url: it.url, series_page: seriesPage });
    }
    out.sort((a, b) => a.model.localeCompare(b.model));
    return out;
  }, seriesPage);
  return products;
}

const seriesPages = await getProSeriesPages();
const allByUrl = new Map();

for (const seriesPage of seriesPages) {
  await gotoWithChallengeRetries(seriesPage);
  await scrollToLoadAll();
  const products = await extractProductsFromCurrentPage(seriesPage);
  for (const p of products) {
    if (!allByUrl.has(p.url)) allByUrl.set(p.url, p);
  }
}

const products = Array.from(allByUrl.values()).sort((a, b) => a.model.localeCompare(b.model));

await writeFile(`${outDir}/hikvision_pro_products.json`, JSON.stringify(products, null, 2), "utf-8");
await writeFile(
  `${outDir}/hikvision_pro_products.csv`,
  ["model,name,url,series_page", ...products.map((p) => `${JSON.stringify(p.model)},${JSON.stringify(p.name)},${JSON.stringify(p.url)},${JSON.stringify(p.series_page)}`)].join("\n"),
  "utf-8",
);

console.log(`OUT_DIR=${outDir}`);
console.log(`PRODUCT_COUNT=${products.length}`);

await page.close();
await browser.close();
