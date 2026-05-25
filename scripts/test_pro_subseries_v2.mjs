const API_URL = "https://www.hikvision.com/content/hikvision/en/products/IP-Products/Network-Cameras/pro-series/jcr:content/root/responsivegrid/search_list.json";

console.log("=== 抓取 Hikvision Pro 系列子系列名称 ===\n");
console.log(`API: ${API_URL}\n`);

async function fetchWithRetry(url, headers = {}, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url, { headers });
      const text = await res.text();
      try {
        return JSON.parse(text);
      } catch {
        console.log(`尝试 ${i + 1}: 返回非JSON (${text.substring(0, 150)}...)`);
        if (i < retries - 1) await new Promise(r => setTimeout(r, 2000));
      }
    } catch (e) {
      console.log(`尝试 ${i + 1}: ${e.message}`);
      if (i < retries - 1) await new Promise(r => setTimeout(r, 2000));
    }
  }
  return null;
}

let data = null;

console.log("方式1: 直接 fetch (无特殊头)...");
data = await fetchWithRetry(API_URL, {}, 1);

if (!data || !data.products) {
  console.log("方式2: fetch + Accept: application/json header...");
  data = await fetchWithRetry(API_URL, {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  }, 1);
}

if (!data || !data.products) {
  console.log("方式3: fetch + X-Requested-With header...");
  data = await fetchWithRetry(API_URL, {
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/pro-series/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  }, 1);
}

if (!data || !data.products) {
  console.log("\n所有 fetch 方式均失败，API 返回内容:");
  if (data) console.log(JSON.stringify(data).substring(0, 500));
  process.exit(1);
}

const products = data.products;
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
