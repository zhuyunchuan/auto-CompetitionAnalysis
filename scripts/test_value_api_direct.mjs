import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { execSync } from "node:child_process";

const runId = new Date().toISOString().replaceAll("-", "").replaceAll(":", "").replaceAll(".", "").replace("T", "_").slice(0, 15);
const outDir = path.join(process.cwd(), "results", `hikvision_value_api_${runId}`);
await mkdir(outDir, { recursive: true });

const apiUrl = "https://www.hikvision.com/content/hikvision/en/products/IP-Products/Network-Cameras/value-series/jcr:content/root/responsivegrid/search_list.json";

console.log("=== 直接请求 Hikvision API ===\n");
console.log(`URL: ${apiUrl}\n`);

let data;
try {
  const response = await fetch(apiUrl);
  data = await response.json();
} catch {
  console.log("Node fetch 失败，尝试 PowerShell...");
  try {
    const psScript = `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (Invoke-WebRequest -Uri '${apiUrl}' -UseBasicParsing -TimeoutSec 60).Content`;
    const result = execSync(`powershell -NoProfile -ExecutionPolicy Bypass -Command "${psScript}"`, {
      maxBuffer: 100 * 1024 * 1024, encoding: "utf8", timeout: 120000,
    });
    data = JSON.parse(result);
  } catch (e) {
    console.log("PowerShell 失败:", e.message);
    process.exit(1);
  }
}

if (!data || !data.products) {
  console.log("API 返回异常:", JSON.stringify(data)?.substring(0, 300));
  process.exit(1);
}

const products = data.products;
console.log(`总产品数: ${products.length}\n`);

const subseriesMap = {};
for (const p of products) {
  const subseries = p.selectParameters?.Subseries?.[0] || p.subseries || "Unknown";
  if (!subseriesMap[subseries]) subseriesMap[subseries] = [];
  const model = (p.productModel || "").toUpperCase().trim();
  const title = (p.title || model).replace(/\s+/g, " ").trim();
  const detailPath = p.detailPath || "";
  const url = detailPath ? `https://www.hikvision.com${detailPath}` : "";
  const desc = (p.description || "").replace(/\s+/g, " ").trim();
  if (model) {
    subseriesMap[subseries].push({ model, name: title, url, description: desc });
  }
}

console.log("=== 各子系列产品数量 ===\n");
const sortedSubs = Object.entries(subseriesMap).sort((a, b) => b[1].length - a[1].length);
for (const [name, prods] of sortedSubs) {
  console.log(`"${name}": ${prods.length} 个型号`);
}

console.log("\n=== 各子系列型号列表示例 ===\n");
for (const [name, prods] of sortedSubs) {
  console.log(`【${name}】(${prods.length}个):`);
  prods.slice(0, 5).forEach((p) => console.log(`  - ${p.model}: ${p.description || p.name}`));
  if (prods.length > 5) console.log(`  ...还有${prods.length - 5}个`);
  console.log();
}

const result = {
  generated_at: new Date().toISOString(),
  api_url: apiUrl,
  total_products: products.length,
  total_subseries: sortedSubs.length,
  by_subseries: {},
};

for (const [name, prods] of sortedSubs) {
  result.by_subseries[name] = { subseries: name, models_count: prods.length, models: prods, sample_models: prods.slice(0, 30) };
}

const outFile = path.join(outDir, "value_subseries_by_api.json");
await writeFile(outFile, JSON.stringify(result, null, 2), "utf-8");
console.log(`结果已保存: ${outFile}`);
