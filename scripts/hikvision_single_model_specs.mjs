import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const url =
  process.argv[2] ||
  "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd20123g2-li-u-y/?subName=DS-2CD20123G2-LIUY";

const runId = new Date()
  .toISOString()
  .replaceAll("-", "")
  .replaceAll(":", "")
  .replaceAll(".", "")
  .replace("T", "_")
  .slice(0, 15);

const outDir = `/workspace/results/hikvision_single_model_${runId}`;
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
    await page.waitForTimeout(5000);
    const html = await page.content();
    if (!html.includes("EO_Bot_Ssid") && html.length > 8000) return html;
    await page.waitForTimeout(7000);
  }
  return await page.content();
}

await gotoWithChallengeRetries(url);

await page.waitForTimeout(4000);

const specs = await page.evaluate(() => {
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
    if (k && v) out.push([k, v]);
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
      out.push([key, value]);
    }
  }
  return out;
});

const html = await page.content();

await writeFile(`${outDir}/page.html`, html, "utf-8");
await writeFile(`${outDir}/specs.json`, JSON.stringify(specs, null, 2), "utf-8");
await writeFile(
  `${outDir}/specs.csv`,
  ["field,value", ...specs.map(([k, v]) => `${JSON.stringify(k)},${JSON.stringify(v)}`)].join("\n"),
  "utf-8",
);

console.log(`OUT_DIR=${outDir}`);
console.log(`SPEC_COUNT=${specs.length}`);

await page.close();
await browser.close();
