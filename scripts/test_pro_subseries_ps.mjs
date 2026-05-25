import { execSync } from "node:child_process";

const API_URL = "https://www.hikvision.com/content/hikvision/en/products/IP-Products/Network-Cameras/pro-series/jcr:content/root/responsivegrid/search_list.json";

console.log("=== 抓取 Hikvision Pro 系列子系列名称 ===\n");
console.log(`API: ${API_URL}\n`);

let data;
const psScript = `
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$response = Invoke-WebRequest -Uri '${API_URL}' -UseBasicParsing -TimeoutSec 60
$response.Content
`;

try {
  console.log("正在通过 PowerShell 请求...");
  const result = execSync(`powershell -NoProfile -ExecutionPolicy Bypass -Command "${psScript}"`, {
    maxBuffer: 100 * 1024 * 1024,
    encoding: "utf8",
    timeout: 120000,
  });
  data = JSON.parse(result);
} catch (e) {
  console.log("错误:", e.message);
  if (e.stdout) console.log("stdout:", e.stdout?.toString()?.substring(0, 300));
  if (e.stderr) console.log("stderr:", e.stderr?.toString()?.substring(0, 300));
  process.exit(1);
}

if (!data || !data.products) {
  console.log("API 返回异常:", JSON.stringify(data)?.substring(0, 500));
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
