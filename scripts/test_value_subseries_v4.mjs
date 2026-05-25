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

console.log("=== 深入调试：检查页面实际内容 ===\n");

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

// 监听网络请求
page.on("request", (req) => {
  const url = req.url();
  if (url.includes("hikvision") && (url.includes("json") || url.includes("api") || url.includes("filter"))) {
    console.log(`  [请求] ${url.substring(0, 200)}`);
  }
});

page.on("response", (res) => {
  const url = res.url();
  if (url.includes("hikvision") && (url.includes("json") || url.includes("api") || url.includes("filter"))) {
    console.log(`  [响应] ${res.status()} ${url.substring(0, 150)}`);
  }
});

for (const subseries of VALUE_SUBSERIES_FILTERS) {
  const url = buildValueSubseriesUrl(subseries);
  console.log(`\n=== [${subseries}] ===`);
  console.log(`URL: ${url}`);

  for (let retry = 0; retry < 5; retry++) {
    try {
      await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
      break;
    } catch {
      await page.waitForTimeout(3000);
    }
  }

  await page.waitForTimeout(5000);

  // 检查页面标题
  const title = await page.title();
  console.log(`页面标题: ${title}`);

  // 检查 product list 容器是否存在
  const hasProductList = await page.evaluate(() => {
    const el = document.querySelector(".product-list, .product-grid, #product-list, [class*=product]");
    return el ? `存在 (${el.className.substring(0, 50)})` : "不存在";
  });
  console.log(`产品列表容器: ${hasProductList}`);

  // 检查 sum-number-of-products
  const sumEl = await page.evaluate(() => {
    const el = document.querySelector(".sum-number-of-products, .result-count, [class*=count]");
    if (!el) return "未找到";
    return `${el.className}: "${el.textContent.trim()}"`;
  });
  console.log(`总数元素: ${sumEl}`);

  // 检查所有包含 "ds-" 的链接
  const dsLinks = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll("a[href]"));
    const dsLinks = links
      .filter((a) => a.href.toLowerCase().includes("/ds-"))
      .map((a) => a.href.split("?")[0].split("#")[0])
      .filter(Boolean);
    return [...new Set(dsLinks)];
  });
  console.log(`包含 "/ds-" 的链接数量: ${dsLinks.length}`);
  if (dsLinks.length > 0 && dsLinks.length <= 30) {
    dsLinks.forEach((l) => console.log(`  - ${l}`));
  }

  // 截图
  await page.screenshot({ path: `D:/work/results/debug_${subseries.replace(/[^a-z0-9]/gi, "_")}.png` });
  console.log(`截图已保存: debug_${subseries.replace(/[^a-z0-9]/gi, "_")}.png`);

  await page.waitForTimeout(2000);
}

await page.close();
await browser.close();
