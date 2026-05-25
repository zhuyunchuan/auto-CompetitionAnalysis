import { chromium } from "playwright";
import path from "node:path";

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

function buildValueSubseriesUrl(subseriesName) {
  const encoded = encodeURIComponent(subseriesName);
  return `https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/?category=Network+Products&subCategory=Network+Cameras&series=Value+Series&checkedSubSeries=${encoded}`;
}

const VALUE_SUBSERIES_FILTERS = [
  "Value Series with MD 2.0",
  "Value Series with ColorVu & MD 2.0",
  "Value Series with ColorVu",
  "Value Series Essential",
  "Value Series with ColorVu 3.0 & MD 3.0",
];

console.log("=== URL 编码验证 ===\n");
for (const sub of VALUE_SUBSERIES_FILTERS) {
  const encoded = encodeURIComponent(sub);
  console.log(`"${sub}"`);
  console.log(`  -> checkedSubSeries=${encoded}`);
  console.log(`  -> 完整URL: ${buildValueSubseriesUrl(sub)}`);
  console.log();
}

async function getProductCount(page, url) {
  for (let retry = 0; retry < 5; retry++) {
    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
      break;
    } catch {
      await page.waitForTimeout(3000);
    }
  }
  await page.waitForTimeout(8000);

  // 提取页面显示的总产品数
  const totalHint = await page.evaluate(() => {
    const el = document.querySelector(".sum-number-of-products");
    const text = (el?.textContent || "").replace(/[,\s]+/g, "").trim();
    if (!text) return null;
    const n = Number(text);
    return Number.isFinite(n) ? n : null;
  });

  // 提取所有产品链接数
  const loadedCount = await page.evaluate(() => {
    const norm = (u) => (u || "").split("#")[0].split("?")[0];
    const set = new Set();
    for (const a of document.querySelectorAll("a[href]")) {
      const href = norm(a.href || "");
      if (href.toLowerCase().includes("/products/") && href.match(/\/ds-[^/?#]+\/?$/i)) {
        set.add(href);
      }
    }
    return set.size;
  });

  return { totalHint, loadedCount };
}

console.log("\n=== 实际抓取测试 ===\n");

const browser = await chromium.launch({
  headless: true,
  executablePath: CHROME_PATH,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});

const page = await browser.newPage({
  userAgent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  locale: "en-US",
});

for (const subseries of VALUE_SUBSERIES_FILTERS) {
  const url = buildValueSubseriesUrl(subseries);
  const { totalHint, loadedCount } = await getProductCount(page, url);
  console.log(`[${subseries}]`);
  console.log(`  页面显示总数: ${totalHint ?? "未知"}`);
  console.log(`  实际产品链接: ${loadedCount} 个`);
  console.log();
}

await page.close();
await browser.close();
