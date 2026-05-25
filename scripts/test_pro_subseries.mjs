import { chromium } from "playwright";

const PRO_PAGE_URL = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/pro-series/";
const API_URL = "https://www.hikvision.com/content/hikvision/en/products/IP-Products/Network-Cameras/pro-series/jcr:content/root/responsivegrid/search_list.json";

console.log("=== 抓取 Hikvision Pro 系列子系列名称 ===\n");
console.log(`页面: ${PRO_PAGE_URL}`);
console.log(`API:  ${API_URL}\n`);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

try {
  console.log("正在打开 Pro 系列页面...");
  await page.goto(PRO_PAGE_URL, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);

  console.log("正在请求 API 数据...");
  const apiData = await page.evaluate(async (url) => {
    const res = await fetch(url);
    return await res.json();
  }, API_URL);

  if (!apiData || !apiData.products) {
    console.log("API 返回异常:", JSON.stringify(apiData)?.substring(0, 500));
    process.exit(1);
  }

  const products = apiData.products;
  console.log(`总产品数: ${products.length}\n`);

  const subseriesMap = {};
  for (const p of products) {
    const sub = p.selectParameters?.Subseries?.[0] || "Unknown";
    if (!subseriesMap[sub]) subseriesMap[sub] = [];
    const model = (p.productModel || "").toUpperCase().trim();
    if (model) subseriesMap[sub].push(model);
  }

  console.log("=== Pro 系列子系列列表 (按型号数量排序) ===\n");
  const sorted = Object.entries(subseriesMap).sort((a, b) => b[1].length - a[1].length);
  for (let i = 0; i < sorted.length; i++) {
    const [name, models] = sorted[i];
    console.log(`  ${i + 1}. ${name}`);
    console.log(`     型号数量: ${models.length}`);
    console.log();
  }

  console.log(`共 ${sorted.length} 个子系列`);
  console.log(`型号总数: ${products.length}`);

} catch (err) {
  console.error("错误:", err.message);
} finally {
  await browser.close();
}
