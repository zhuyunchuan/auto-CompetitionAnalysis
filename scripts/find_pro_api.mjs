import https from "node:https";

const PRO_PAGE = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/";

function fetchHtml(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { rejectUnauthorized: false, headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" } }, (res) => {
      let data = "";
      res.on("data", (chunk) => data += chunk);
      res.on("end", () => resolve(data));
    }).on("error", reject);
  });
}

console.log("Fetching Pro page...");
try {
  const html = await fetchHtml(PRO_PAGE);
  console.log(`HTML length: ${html.length}`);

  const matches = html.match(/search_list[^"'\s]*/gi) || [];
  console.log("\n=== search_list references ===");
  matches.forEach((m, i) => console.log(`  ${i + 1}: ${m}`));

  const apiMatches = html.match(/["'][^"']*search_list[^"']*["']/gi) || [];
  console.log("\n=== API URL candidates ===");
  apiMatches.forEach((m, i) => console.log(`  ${i + 1}: ${m}`));

  const jsonMatches = html.match(/["'][^"']*\.json[^"']*["']/gi) || [];
  console.log("\n=== .json references ===");
  jsonMatches.forEach((m, i) => console.log(`  ${i + 1}: ${m}`));
} catch (e) {
  console.log("Error:", e.message);
}
