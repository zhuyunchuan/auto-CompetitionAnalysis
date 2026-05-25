import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const runId = new Date().toISOString().replaceAll("-","").replaceAll(":","").replaceAll(".","").replace("T","_").slice(0,15);
const outDir = path.join(process.cwd(), "results", `hikvision_pro_test_${runId}`);
await mkdir(outDir, { recursive: true });

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const browser = await chromium.launch({
  headless: true,
  executablePath: CHROME_PATH,
  args: ["--no-sandbox","--disable-dev-shm-usage"]
});
const page = await browser.newPage({
  userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US"
});

const baseProUrl = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/pro-series/";

console.log("=== 检查 Pro 系列 API ===\n");

for (let retry=0; retry<5; retry++) {
  try {
    await page.goto(baseProUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    break;
  } catch {
    await page.waitForTimeout(3000);
  }
}
await page.waitForTimeout(8000);

const result = await page.evaluate(async () => {
  const pathParts = window.location.pathname.split("/").filter(Boolean);
  const idx = pathParts.findIndex((p) => p === "products");
  let apiUrl = null;
  if (idx >= 0) {
    const contentPath = pathParts.join("/");
    apiUrl = `https://www.hikvision.com/content/hikvision/en/${contentPath}/jcr:content/root/responsivegrid/search_list.json`;
  }

  const pageHtml = document.documentElement.outerHTML;
  let apiData = null;

  if (apiUrl) {
    try {
      const res = await fetch(apiUrl, { credentials: "same-origin" });
      if (res.ok) {
        apiData = await res.json();
      } else {
        apiData = { error: "not ok", status: res.status, text: await res.text() };
      }
    } catch (e) {
      apiData = { error: "fetch failed", message: String(e) };
    }
  }

  return { apiUrl, apiData, pageHtml: pageHtml.slice(0, 20000) };
});

const outFile1 = path.join(outDir, "test_result.json");
await writeFile(outFile1, JSON.stringify(result, null, 2), "utf-8");

if (result.apiData && !result.apiData.error && result.apiData.products) {
  const subseriesMap = {};
  for (const p of result.apiData.products) {
    const subseries = p.selectParameters?.Subseries?.[0] || p.subseries || "Unknown";
    if (!subseriesMap[subseries]) subseriesMap[subseries] = [];
    const model = (p.productModel || "").toUpperCase().trim();
    if (model && model.length) {
      subseriesMap[subseries].push({ model, title: p.title, url: `https://www.hikvision.com${p.detailPath}` });
    }
  }

  console.log("\n按子系列分组：");
  const sortedSubs = Object.entries(subseriesMap).sort((a,b) => b[1].length - a[1].length);
  for (const [name, products] of sortedSubs) {
    console.log(`  "${name}": ${products.length} 个型号`);
  }

  const outFile2 = path.join(outDir, "pro_subseries_analysis.json");
  await writeFile(outFile2, JSON.stringify({ bySubseries: subseriesMap }, null, 2), "utf-8");
}

console.log("\n结果保存到:", outDir);

await page.close();
await browser.close();
