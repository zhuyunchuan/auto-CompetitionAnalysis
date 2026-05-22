import { chromium } from "playwright";
import { mkdir, writeFile, appendFile, access } from "node:fs/promises";
import { createWriteStream } from "node:fs";

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = `D:\\work\\auto-CompetitionAnalysis\\results\\hikvision_missing_models_${runId}`;
await mkdir(outDir, { recursive: true });

function safeCsvCell(v) {
  return JSON.stringify(v == null ? "" : String(v));
}

const missing = [
  {
    brand: "hikvision",
    series_l1: "Pro",
    subseries: "Value Series with MD 2.0",
    model: "DS-2CD1343G2-I(UF)",
    name: "4 MP MD 2.0 Fixed Turret Network Camera",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd1343g2-i-uf-/"
  },
  {
    brand: "hikvision",
    series_l1: "Pro",
    subseries: "EasyIP 4.0 Plus with ColorVu",
    model: "DS-2CD2187G3-LI(S2U)Y",
    name: "8 MP Smart Hybrid Light with ColorVu Fixed Mini Dome Network Camera",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd2187g3-li-s2u-y/"
  },
  {
    brand: "hikvision",
    series_l1: "Pro",
    subseries: "EasyIP 4.0 Plus with AcuSense",
    model: "DS-2CD23126G3-IS2UY/S(L)(RB)",
    name: "12MP Acusense Strobe Light and Audible Warning Fixed Turret Network Camera",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd23126g3-is2uy-s-l--rb-/"
  },
  {
    brand: "hikvision",
    series_l1: "Pro",
    subseries: "EasyIP 4.0 Plus with ColorVu",
    model: "DS-2CD2387G3-LIS2UY/SL#EU",
    name: "8 MP Smart Hybrid Light with ColorVu Fixed Turret Network Camera",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd2387g3-lis2uy-sl-eu/"
  },
  {
    brand: "hikvision",
    series_l1: "Pro",
    subseries: "EasyIP 4.0 with AcuSense",
    model: "DS-2CD2666G2H-IZS2U/S(L)(RB)",
    name: "6 MP Powered by Darkfighter Motorized Varifocal Bullet Network Camera",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd2666g2h-izs2u-s-l--rb-/"
  },
  {
    brand: "hikvision",
    series_l1: "Pro",
    subseries: "EasyIP 4.0 Plus with AcuSense",
    model: "DS-2CD27126G3-IPTRZS2UY/S(L)(RB)",
    name: "12MP Acusense Strobe Light and Audible Warning Motorized Varifocal Dome Network Camera",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd27126g3-iptrzs2uy-s-l--rb-/"
  },
  {
    brand: "hikvision",
    series_l1: "Pro",
    subseries: "EasyIP 4.0 Plus with AcuSense",
    model: "DS-2CD27126G3-IPTRZSY",
    name: "12MP Acusense Powered by Darkfighter Motorized Varifocal Dome Network Camera",
    url: "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd27126g3-iptrzsy/"
  }
];

async function fileExists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

const csvPath = `${outDir}/specs_long.csv`;
const jsonlPath = `${outDir}/specs_long.jsonl`;
if (!(await fileExists(csvPath))) {
  await writeFile(
    csvPath,
    ["brand,series_l1,subseries,model,name,url,field,value"].join("\n") + "\n",
    "utf-8"
  );
}
if (!(await fileExists(jsonlPath))) await writeFile(jsonlPath, "", "utf-8");
const csvStream = createWriteStream(csvPath, { flags: "a" });
const jsonlStream = createWriteStream(jsonlPath, { flags: "a" });

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:\\Users\\12298\\AppData\\Local\\ms-playwright\\chromium-1223\\chrome-win64\\chrome.exe",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const context = await browser.newContext({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

let okModels = 0, zeroModels = 0, errModels = 0;
for (let i = 0; i < missing.length; i++) {
  const t = missing[i];
  const page = await context.newPage();
  const header = `[${i + 1}/${missing.length}] ${t.model}`;
  let extracted = [];
  try {
    let ok = false;
    for (let retry = 0; retry < 10; retry++) {
      try {
        await page.goto(t.url, { waitUntil: "domcontentloaded", timeout: 90000 });
      } catch {
        await page.waitForTimeout(3000);
        continue;
      }
      await page.waitForTimeout(2500);
      const html = await page.content();
      if (!html.includes("EO_Bot_Ssid") && html.length > 8000) {
        ok = true;
        break;
      }
      await page.waitForTimeout(6000);
    }
    if (!ok) throw new Error("challenge retries exhausted");

    try {
      await page.waitForSelector(".tech-specs-accordion-container", { timeout: 15000 });
    } catch {}

    extracted = await page.evaluate(() => {
      const normalizeKey = (s) => (s || "").replace(/\s+/g, " ").replace(/\u00a0/g, " ").trim();
      const normalizeVal = (s) => (s || "").replace(/\u00a0/g, " ").replace(/\s+\n/g, "\n").replace(/\n\s+/g, "\n").replace(/[ \t]+/g, " ").trim();
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

    if (!Array.isArray(extracted)) extracted = [];
    if (extracted.length === 0) {
      zeroModels += 1;
      const html = await page.content();
      await writeFile(`${outDir}/zero_${t.model.replace(/\//g, "_")}.html`, html, "utf-8");
    } else {
      okModels += 1;
    }

    for (const row of extracted) {
      const rec = { brand: t.brand, series_l1: t.series_l1, subseries: t.subseries, model: t.model, name: t.name, url: t.url, field: row.field, value: row.value };
      jsonlStream.write(JSON.stringify(rec) + "\n");
      csvStream.write(
        [safeCsvCell(rec.brand), safeCsvCell(rec.series_l1), safeCsvCell(rec.subseries), safeCsvCell(rec.model), safeCsvCell(rec.name), safeCsvCell(rec.url), safeCsvCell(rec.field), safeCsvCell(rec.value)].join(",") + "\n"
      );
    }
    console.log(`${header} specs=${extracted.length} OK`);
  } catch (e) {
    errModels += 1;
    await appendFile(`${outDir}/errors.log`, `${new Date().toISOString()} ${header} error=${String(e)}\n`, "utf-8");
    console.error(`${header} ERROR:`, String(e));
  } finally {
    await page.close();
    await new Promise(r => setTimeout(r, 800));
  }
}

csvStream.end();
jsonlStream.end();
await context.close();
await browser.close();

console.log(`OUT_DIR=${outDir}`);
console.log(`OK=${okModels} ZERO=${zeroModels} ERR=${errModels}`);
