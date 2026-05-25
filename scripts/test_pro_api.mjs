import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const runId = new Date().toISOString().replaceAll("-","").replaceAll(":","").replaceAll(".","").replace("T","_").slice(0,15);
const outDir = path.join(process.cwd(), "results", `hikvision_pro_test_${runId}`);
await mkdir(outDir, { recursive: true });

const proApiUrl = "https://www.hikvision.com/content/hikvision/en/products/IP-Products/Network-Cameras/pro-series/jcr:content/root/responsivegrid/search_list.json";

console.log("=== 检查 Pro 系列 search_list.json API ===\n");
console.log("API URL:", proApiUrl);

let data;
try {
  const res = await fetch(proApiUrl);
  data = await res.json();
} catch (e) {
  console.log("请求失败:", e.message);
  process.exit(1);
}

const outFile1 = path.join(outDir, "pro_api_raw.json");
await writeFile(outFile1, JSON.stringify(data, null, 2), "utf-8");

if (data && data.products && Array.isArray(data.products)) {
  console.log("\nAPI 返回产品总数:", data.products.length);

  const subseriesMap = {};
  for (const p of data.products) {
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
  await writeFile(outFile2, JSON.stringify({ bySubseries: subseriesMap, rawDataFile: outFile1 }, null, 2), "utf-8");
  console.log("\n结果保存到:", outFile2);
}
