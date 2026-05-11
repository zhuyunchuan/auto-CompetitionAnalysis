import { chromium } from "playwright";
import { mkdir, writeFile, appendFile, readFile, access } from "node:fs/promises";
import { createWriteStream } from "node:fs";

const structurePath =
  process.argv.find((a) => a.startsWith("--structure="))?.split("=", 2)[1] ||
  "/workspace/results/hikvision_structure_filtered_20260511_102116/structure_filtered.json";

const concurrencyArg = process.argv.find((a) => a.startsWith("--concurrency="))?.split("=", 2)[1];
const concurrency = Math.max(1, Math.min(6, Number(concurrencyArg || "3") || 3));

const limitArg = process.argv.find((a) => a.startsWith("--limit="))?.split("=", 2)[1];
const limit = limitArg ? Math.max(1, Number(limitArg) || 0) : null;

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = `/workspace/results/hikvision_specs_all_${runId}`;
await mkdir(outDir, { recursive: true });

async function fileExists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

function safeCsvCell(v) {
  return JSON.stringify(v == null ? "" : String(v));
}

async function loadTasks() {
  const raw = await readFile(structurePath, "utf-8");
  const j = JSON.parse(raw);

  const tasks = [];
  const add = (series_l1, subseries, m) => {
    const url = normalizeUrl(m.url);
    if (!url) return;
    if (!url.startsWith("https://www.hikvision.com/en/products/")) return;
    if (url.includes("/content/dam/")) return;
    if (url.match(/\.(pdf|jpg|jpeg|png|gif|zip)$/i)) return;
    if (!url.toLowerCase().includes("/network-cameras/")) return;
    const inferredModel = (m.model || extractModelFromUrl(url) || "").toUpperCase();
    if (!inferredModel.match(/^(DS|IDS|IPC)-/)) return;
    tasks.push({
      brand: "hikvision",
      series_l1,
      subseries,
      model: m.model || inferredModel,
      name: m.name || "",
      url,
    });
  };

  for (const [sub, obj] of Object.entries(j.series?.Pro || {})) {
    const ms = obj.models || obj.sample_models || [];
    for (const m of ms) add("Pro", sub, m);
  }
  for (const [sub, obj] of Object.entries(j.series?.Value || {})) {
    const ms = obj.models || obj.sample_models || [];
    for (const m of ms) add("Value", sub, m);
  }
  for (const [sub, obj] of Object.entries(j.series?.HiLook || {})) {
    const ms = obj.models || obj.sample_models || [];
    for (const m of ms) add("HiLook", sub, m);
  }

  const byUrl = new Map();
  for (const t of tasks) {
    if (!byUrl.has(t.url)) byUrl.set(t.url, t);
  }
  return Array.from(byUrl.values()).sort((a, b) => a.url.localeCompare(b.url));
}

function extractModelFromUrl(u) {
  const m = normalizeUrl(u).match(/\/((ds|ids|ipc)-[^/?#]+)\/?$/i);
  if (m) return m[1].toUpperCase();
  const last = normalizeUrl(u).match(/\/([^/?#]+)\/?$/i);
  if (!last) return "";
  try {
    return decodeURIComponent(last[1]).toUpperCase();
  } catch {
    return last[1].toUpperCase();
  }
}

async function gotoWithChallengeRetries(page, target) {
  for (let i = 0; i < 10; i++) {
    try {
      await page.goto(target, { waitUntil: "domcontentloaded", timeout: 90000 });
    } catch {
      await page.waitForTimeout(3000);
      continue;
    }
    await page.waitForTimeout(2500);
    const html = await page.content();
    if (!html.includes("EO_Bot_Ssid") && html.length > 8000) return true;
    await page.waitForTimeout(6000);
  }
  return false;
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

const tasksAll = await loadTasks();
const tasks = limit ? tasksAll.slice(0, limit) : tasksAll;

await writeFile(`${outDir}/run_meta.json`, JSON.stringify({ structurePath, concurrency, limit, total_models: tasksAll.length, run_started_at: new Date().toISOString() }, null, 2), "utf-8");
await writeFile(`${outDir}/models.json`, JSON.stringify(tasks, null, 2), "utf-8");

const donePath = `${outDir}/done_urls.txt`;
const done = new Set();
if (await fileExists(donePath)) {
  const txt = await readFile(donePath, "utf-8");
  for (const line of txt.split("\n")) {
    const u = line.trim();
    if (u) done.add(u);
  }
}

const csvPath = `${outDir}/specs_long.csv`;
const jsonlPath = `${outDir}/specs_long.jsonl`;

if (!(await fileExists(csvPath))) {
  await writeFile(
    csvPath,
    [
      "brand,series_l1,subseries,model,name,url,field,value",
    ].join("\n") + "\n",
    "utf-8",
  );
}
if (!(await fileExists(jsonlPath))) await writeFile(jsonlPath, "", "utf-8");

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

let idx = 0;
let okModels = 0;
let zeroModels = 0;
let errModels = 0;

async function worker(workerId) {
  const page = await context.newPage();
  while (true) {
    const myIdx = idx++;
    if (myIdx >= tasks.length) break;
    const t = tasks[myIdx];
    if (done.has(t.url)) continue;

    const url = t.url;
    const model = t.model || extractModelFromUrl(url);
    const header = `[W${workerId}] ${myIdx + 1}/${tasks.length} ${model}`;

    let extracted = null;
    try {
      const ok = await gotoWithChallengeRetries(page, url);
      if (!ok) throw new Error("challenge retries exhausted");

      try {
        await page.waitForSelector(".tech-specs-accordion-container", { timeout: 15000 });
      } catch {}

      extracted = await extractSpecs(page);
      if (!Array.isArray(extracted)) extracted = [];

      if (extracted.length === 0) {
        zeroModels += 1;
        const html = await page.content();
        await writeFile(`${outDir}/zero_${model}_${workerId}.html`, html, "utf-8");
      } else {
        okModels += 1;
      }

      for (const row of extracted) {
        const rec = {
          brand: t.brand,
          series_l1: t.series_l1,
          subseries: t.subseries,
          model,
          name: t.name,
          url,
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

      await appendFile(donePath, url + "\n", "utf-8");
      done.add(url);

      if ((myIdx + 1) % 20 === 0) {
        await writeFile(
          `${outDir}/progress.json`,
          JSON.stringify(
            {
              processed: done.size,
              total: tasks.length,
              ok_models: okModels,
              zero_models: zeroModels,
              err_models: errModels,
              updated_at: new Date().toISOString(),
            },
            null,
            2,
          ),
          "utf-8",
        );
      }

      if ((myIdx + 1) % 10 === 0) {
        console.log(`${header} specs=${extracted.length} OK=${okModels} ZERO=${zeroModels} ERR=${errModels}`);
      }
      await page.waitForTimeout(800);
    } catch (e) {
      errModels += 1;
      await appendFile(donePath, url + "\n", "utf-8");
      done.add(url);
      await appendFile(
        `${outDir}/errors.log`,
        `${new Date().toISOString()} ${header} url=${url} error=${String(e && e.message ? e.message : e)}\n`,
        "utf-8",
      );
      await page.waitForTimeout(1200);
    }
  }
  await page.close();
}

await Promise.all(Array.from({ length: concurrency }, (_, i) => worker(i + 1)));

csvStream.end();
jsonlStream.end();
await context.close();
await browser.close();

await writeFile(
  `${outDir}/progress.json`,
  JSON.stringify(
    {
      processed: done.size,
      total: tasks.length,
      ok_models: okModels,
      zero_models: zeroModels,
      err_models: errModels,
      updated_at: new Date().toISOString(),
      finished: true,
    },
    null,
    2,
  ),
  "utf-8",
);

console.log(`OUT_DIR=${outDir}`);
console.log(`TOTAL_MODELS=${tasksAll.length} TARGET_MODELS=${tasks.length} PROCESSED=${done.size} OK=${okModels} ZERO=${zeroModels} ERR=${errModels}`);
