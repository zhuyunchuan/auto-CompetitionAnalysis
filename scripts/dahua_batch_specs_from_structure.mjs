import { chromium } from "playwright";
import { mkdir, writeFile, appendFile, readFile, access } from "node:fs/promises";
import { createWriteStream } from "node:fs";

const structurePath =
  process.argv.find((a) => a.startsWith("--structure="))?.split("=", 2)[1] ||
  "/workspace/results/dahua_wizsense_structure_20260511_130618/dahua_wizsense_structure.json";

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

const outDir = `/workspace/results/dahua_specs_all_${runId}`;
await mkdir(outDir, { recursive: true });

async function fileExists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

function safeCsvCell(v) {
  return JSON.stringify(v == null ? "" : String(v));
}

function normalizeUrl(u) {
  return (u || "").split("#")[0].split("?")[0];
}

async function loadTasks() {
  const raw = await readFile(structurePath, "utf-8");
  const j = JSON.parse(raw);
  const tasks = [];

  for (const [seriesKey, sObj] of Object.entries(j.series || {})) {
    for (const [subKey, subObj] of Object.entries(sObj.subseries || {})) {
      const models = subObj.models || subObj.sample_models || [];
      for (const m of models) {
        const url = normalizeUrl(m.url || "");
        if (!url) continue;
        if (!url.includes("dahuasecurity.com/products/network-products/network-cameras/")) continue;
        tasks.push({
          brand: "dahua",
          series_l1: seriesKey,
          subseries: subKey,
          model: (m.model || "").toUpperCase(),
          name: m.name || "",
          url,
        });
      }
    }
  }

  const byUrl = new Map();
  for (const t of tasks) if (!byUrl.has(t.url)) byUrl.set(t.url, t);
  return Array.from(byUrl.values()).sort((a, b) => a.url.localeCompare(b.url));
}

async function gotoWithRetries(page, target) {
  for (let i = 0; i < 8; i++) {
    try {
      await page.goto(target, { waitUntil: "networkidle", timeout: 90000 });
      await page.waitForTimeout(2500);
      const html = await page.content();
      if (html.length > 5000) return true;
    } catch {
      await page.waitForTimeout(3000);
    }
  }
  return false;
}

async function clickSpecificationsIfPresent(page) {
  const clicked = await page.evaluate(() => {
    const norm = (s) => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
    const targets = ["specification", "specifications", "spec"];
    const nodes = Array.from(document.querySelectorAll("a, button, div"));
    for (const el of nodes) {
      const t = norm(el.textContent);
      if (!t) continue;
      if (targets.includes(t)) {
        if (typeof el.click === "function") {
          el.click();
          return true;
        }
      }
    }
    return false;
  });
  if (clicked) await page.waitForTimeout(2000);
  return clicked;
}

async function extractSpecsFromTables(page) {
  return await page.evaluate(() => {
    const clean = (s) => (s || "").replace(/\s+/g, " ").trim();
    const tables = Array.from(document.querySelectorAll("table"));
    const out = [];
    for (const table of tables) {
      for (const tr of Array.from(table.querySelectorAll("tr"))) {
        const th = tr.querySelector("th");
        const td = tr.querySelector("td");
        let k = "";
        let v = "";
        if (th && td) {
          k = clean(th.innerText || th.textContent);
          v = clean(td.innerText || td.textContent);
        } else {
          const cells = Array.from(tr.querySelectorAll("td, th")).map((c) => clean(c.innerText || c.textContent));
          if (cells.length >= 2) {
            k = cells[0];
            v = cells[1];
          }
        }
        if (!k || !v) continue;
        out.push({ field: k, value: v });
      }
    }
    return out;
  });
}

const tasksAll = await loadTasks();
const tasks = limit ? tasksAll.slice(0, limit) : tasksAll;

await writeFile(
  `${outDir}/run_meta.json`,
  JSON.stringify(
    {
      structurePath,
      concurrency,
      limit,
      total_models: tasksAll.length,
      run_started_at: new Date().toISOString(),
    },
    null,
    2,
  ),
  "utf-8",
);
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
    ["brand,series_l1,subseries,model,name,url,field,value"].join("\n") + "\n",
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

    const header = `[W${workerId}] ${myIdx + 1}/${tasks.length} ${t.model}`;
    try {
      const ok = await gotoWithRetries(page, t.url);
      if (!ok) throw new Error("fetch retries exhausted");

      let specs = [];
      try {
        await clickSpecificationsIfPresent(page);
        specs = await extractSpecsFromTables(page);
        if (!Array.isArray(specs)) specs = [];
      } catch {
        specs = [];
      }

      if (!specs.length) {
        zeroModels += 1;
        const html = await page.content();
        await writeFile(`${outDir}/zero_${t.model}_${workerId}.html`, html, "utf-8");
      } else {
        okModels += 1;
      }

      for (const row of specs) {
        const rec = {
          brand: t.brand,
          series_l1: t.series_l1,
          subseries: t.subseries,
          model: t.model,
          name: t.name,
          url: t.url,
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

      await appendFile(donePath, t.url + "\n", "utf-8");
      done.add(t.url);

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
        console.log(`${header} specs=${specs.length} OK=${okModels} ZERO=${zeroModels} ERR=${errModels}`);
      }

      await page.waitForTimeout(900);
    } catch (e) {
      errModels += 1;
      await appendFile(donePath, t.url + "\n", "utf-8");
      done.add(t.url);
      await appendFile(
        `${outDir}/errors.log`,
        `${new Date().toISOString()} ${header} url=${t.url} error=${String(e && e.message ? e.message : e)}\n`,
        "utf-8",
      );
      await page.waitForTimeout(1500);
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
