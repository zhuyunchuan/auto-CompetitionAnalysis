import { chromium } from "playwright";
import { readFile, writeFile, appendFile } from "node:fs/promises";
import { createWriteStream, existsSync } from "node:fs";

const outDir =
  process.argv.find((a) => a.startsWith("--outDir="))?.split("=", 2)[1] ||
  "/workspace/results/hikvision_specs_all_20260511_123532";

function safeCsvCell(v) {
  return JSON.stringify(v == null ? "" : String(v));
}

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

async function loadJson(p) {
  return JSON.parse(await readFile(p, "utf-8"));
}

function parseErrorUrls(text) {
  const urls = [];
  for (const line of (text || "").split("\n")) {
    const m = line.match(/url=([^\s]+)\s+error=/);
    if (m) urls.push(m[1]);
  }
  return Array.from(new Set(urls));
}

async function extractSpecs(page) {
  return await page.evaluate(() => {
    const normalizeKey = (s) =>
      (s || "")
        .replace(/\s+/g, " ")
        .replace(/\u00a0/g, " ")
        .trim();
    const normalizeVal = (s) =>
      (s || "")
        .replace(/\u00a0/g, " ")
        .replace(/\s+\n/g, "\n")
        .replace(/\n\s+/g, "\n")
        .replace(/[ \t]+/g, " ")
        .trim();
    const allText = (el) => normalizeVal(el?.innerText || el?.textContent || "");

    const root = document.querySelector(".tech-specs-accordion-container") || document.body;
    const titles = Array.from(root.querySelectorAll(".tech-specs-items-description__title"));
    const details = Array.from(root.querySelectorAll(".tech-specs-items-description__title-details"));
    const out = [];

    for (let i = 0; i < Math.min(titles.length, details.length); i++) {
      const k = normalizeKey(allText(titles[i]));
      const v = normalizeVal(allText(details[i]));
      if (k && v) out.push({ field: k, value: v });
    }

    if (out.length) return out;

    const tables = Array.from(root.querySelectorAll("table"));
    for (const table of tables) {
      for (const tr of Array.from(table.querySelectorAll("tr"))) {
        const th = tr.querySelector("th");
        const td = tr.querySelector("td");
        if (!th || !td) continue;
        const key = normalizeKey(allText(th));
        const value = normalizeVal(allText(td));
        if (!key || !value) continue;
        out.push({ field: key, value });
      }
    }
    return out;
  });
}

async function gotoWithRetries(page, target) {
  for (let i = 0; i < 8; i++) {
    try {
      await page.goto(target, { waitUntil: "domcontentloaded", timeout: 90000 });
      await page.waitForLoadState("networkidle", { timeout: 90000 }).catch(() => {});
      await page.waitForTimeout(2500);
      const html = await page.content();
      if (!html.includes("EO_Bot_Ssid") && html.length > 8000) return true;
    } catch {
      await page.waitForTimeout(3000);
    }
  }
  return false;
}

const models = await loadJson(`${outDir}/models.json`);
const byUrl = new Map(models.map((m) => [m.url, m]));

const errorLog = existsSync(`${outDir}/errors.log`) ? await readFile(`${outDir}/errors.log`, "utf-8") : "";
const errorUrls = parseErrorUrls(errorLog);

const zeroFiles = existsSync(outDir)
  ? (await import("node:fs/promises")).readdir(outDir)
  : [];

const zeroModels = [];
for (const f of await zeroFiles) {
  if (!f.startsWith("zero_") || !f.endsWith(".html")) continue;
  const model = f.slice("zero_".length, -".html".length).replace(/_[0-9]+$/, "");
  zeroModels.push(model);
}

const zeroUrls = zeroModels
  .map((m) => models.find((x) => x.model === m)?.url)
  .filter(Boolean);

const targets = Array.from(new Set([...errorUrls, ...zeroUrls]));

const csvPath = `${outDir}/specs_long.csv`;
const jsonlPath = `${outDir}/specs_long.jsonl`;
const retryLog = `${outDir}/retry.log`;
const unavailablePath = `${outDir}/unavailable_models.json`;

const csvStream = createWriteStream(csvPath, { flags: "a" });
const jsonlStream = createWriteStream(jsonlPath, { flags: "a" });

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const context = await browser.newContext({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

const page = await context.newPage();
const unavailable = [];
let fixed = 0;
let stillFailed = 0;

for (const url of targets) {
  const meta = byUrl.get(url) || { url, brand: "hikvision", series_l1: "", subseries: "", model: "", name: "" };
  const ok = await gotoWithRetries(page, url);
  const finalUrl = page.url();
  const canonical = await page.evaluate(() => document.querySelector('link[rel="canonical"]')?.href || "");

  const looksRedirectedToList =
    finalUrl.includes("checkedSubSeries=NONE") ||
    (canonical && canonical.endsWith("/value-series/")) ||
    (canonical && canonical.endsWith("/Pro-Series-EasyIP-/"));

  if (!ok || looksRedirectedToList) {
    unavailable.push({
      ...meta,
      final_url: finalUrl,
      canonical,
      reason: looksRedirectedToList ? "redirected_to_series_list" : "fetch_failed",
    });
    stillFailed += 1;
    await appendFile(retryLog, `${new Date().toISOString()} FAIL model=${meta.model} url=${url} final=${finalUrl}\n`, "utf-8");
    continue;
  }

  let specs = [];
  try {
    await page.waitForSelector(".tech-specs-accordion-container", { timeout: 15000 }).catch(() => {});
    specs = await extractSpecs(page);
    if (!Array.isArray(specs)) specs = [];
  } catch {
    specs = [];
  }

  if (!specs.length) {
    const html = await page.content().catch(() => "");
    if (html) await writeFile(`${outDir}/retry_zero_${meta.model}.html`, html, "utf-8");
    unavailable.push({
      ...meta,
      final_url: finalUrl,
      canonical,
      reason: "specs_empty",
    });
    stillFailed += 1;
    await appendFile(retryLog, `${new Date().toISOString()} EMPTY model=${meta.model} url=${url} final=${finalUrl}\n`, "utf-8");
    continue;
  }

  for (const row of specs) {
    const rec = {
      brand: meta.brand,
      series_l1: meta.series_l1,
      subseries: meta.subseries,
      model: meta.model,
      name: meta.name,
      url: meta.url,
      field: row.field,
      value: row.value,
    };
    jsonlStream.write(JSON.stringify(rec) + "\n");
    csvStream.write(
      [
        safeCsvCell(rec.brand),
        safeCsvCell(rec.series_l1),
        safeCsvCell(rec.subseries),
        safeCsvCell(rec.model),
        safeCsvCell(rec.name),
        safeCsvCell(rec.url),
        safeCsvCell(rec.field),
        safeCsvCell(rec.value),
      ].join(",") + "\n",
    );
  }

  fixed += 1;
  await appendFile(retryLog, `${new Date().toISOString()} OK model=${meta.model} url=${url} specs=${specs.length}\n`, "utf-8");
  await page.waitForTimeout(800);
}

csvStream.end();
jsonlStream.end();
await page.close();
await context.close();
await browser.close();

await writeFile(unavailablePath, JSON.stringify(unavailable, null, 2), "utf-8");

console.log(`OUT_DIR=${outDir}`);
console.log(`TARGETS=${targets.length} FIXED=${fixed} STILL_FAILED=${stillFailed}`);

