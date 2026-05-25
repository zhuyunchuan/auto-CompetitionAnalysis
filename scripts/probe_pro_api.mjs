import { chromium } from "playwright";

const URL = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/";
const browser = await chromium.launch({
  headless: true,
  executablePath: "C:\\Users\\12298\\AppData\\Local\\ms-playwright\\chromium-1223\\chrome-win64\\chrome.exe",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const page = await browser.newPage({
  userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
});

const allUrls = [];

page.on("response", (res) => {
  const url = res.url();
  if (url.includes("json") || url.includes("search_list") || url.includes("jcr:content")) {
    allUrls.push(url);
  }
});

console.log("Navigating to Pro page...");
await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 180000 });
await page.waitForTimeout(15000);

console.log("\n=== Page URL ===");
console.log(page.url());

console.log("\n=== Pathname ===");
const pathname = await page.evaluate(() => window.location.pathname);
console.log(pathname);

console.log("\n=== Detected API URLs ===");
for (const url of allUrls) {
  console.log("  " + url);
}

console.log("\n=== Trying API with page.evaluate fetch ===");
const pathParts = pathname.split("/").filter(Boolean);
const fullPath = pathParts.join("/");
const apiUrl = `https://www.hikvision.com/content/hikvision/${fullPath}/jcr:content/root/responsivegrid/search_list.json`;
console.log("  " + apiUrl);

const result = await page.evaluate(async (url) => {
  try {
    const res = await fetch(url);
    const text = await res.text();
    return { ok: res.ok, status: res.status, text: text.substring(0, 300) };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}, apiUrl);
console.log("  Result:", JSON.stringify(result, null, 2));

console.log("\n=== Search for .json in page source ===");
const jsonRefs = await page.evaluate(() => {
  const html = document.documentElement.innerHTML;
  const matches = html.match(/["'][^"']*\.json[^"']*["']/gi) || [];
  return matches.map(m => m.replace(/["']/g, "")).slice(0, 20);
});
if (jsonRefs.length) {
  jsonRefs.forEach((r, i) => console.log(`  ${i + 1}: ${r}`));
} else {
  console.log("  No .json references found");
}

console.log("\n=== Search for 'search_list' in page source ===");
const slRefs = await page.evaluate(() => {
  const html = document.documentElement.innerHTML;
  const matches = html.match(/["'][^"']*search_list[^"']*["']/gi) || [];
  return matches.map(m => m.replace(/["']/g, "")).slice(0, 20);
});
if (slRefs.length) {
  slRefs.forEach((r, i) => console.log(`  ${i + 1}: ${r}`));
} else {
  console.log("  No search_list references found");
}

await browser.close();
