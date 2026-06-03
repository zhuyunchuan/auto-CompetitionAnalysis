import { chromium } from "playwright";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, join } from "path";
import { createWriteStream } from "fs";
import https from "https";
import http from "http";

const HK_WIDE_PATH = resolve("d:/work/auto-CompetitionAnalysis/delivery/宽表/hikvision_specs_wide.csv");
const IMAGE_DIR = resolve("d:/work/product_images");
const MAPPING_PATH = resolve("d:/work/product_image_mapping.json");

mkdirSync(IMAGE_DIR, { recursive: true });

function parseCsv(path) {
  const lines = readFileSync(path, "utf-8").replace(/^\uFEFF/, "").split("\n").filter(Boolean);
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const vals = line.split(",");
    const obj = {};
    headers.forEach((h, i) => (obj[h.trim()] = (vals[i] || "").trim()));
    return obj;
  });
}

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    if (existsSync(dest)) {
      resolve(dest);
      return;
    }
    const file = createWriteStream(dest);
    const mod = url.startsWith("https") ? https : http;
    mod
      .get(url, { timeout: 30000 }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          downloadFile(res.headers.location, dest).then(resolve).catch(reject);
          return;
        }
        res.pipe(file);
        file.on("finish", () => {
          file.close();
          resolve(dest);
        });
      })
      .on("error", (e) => {
        file.close();
        reject(e);
      });
  });
}

function safeName(model) {
  return model.replace(/[\\/:*?"<>|]/g, "_");
}

(async () => {
  const rows = parseCsv(HK_WIDE_PATH).filter((r) => r.series_l1 === "Pro");
  console.log(`HK Pro products: ${rows.length}`);

  let mapping = {};
  if (existsSync(MAPPING_PATH)) {
    mapping = JSON.parse(readFileSync(MAPPING_PATH, "utf-8"));
  }
  const existingCount = Object.keys(mapping).length;
  console.log(`Existing mappings: ${existingCount}`);

  const todo = rows.filter((r) => !mapping[r.model] || !mapping[r.model].local);
  console.log(`HK products to fetch: ${todo.length}`);

  if (todo.length === 0) {
    console.log("All done.");
    return;
  }

  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:\\Users\\12298\\AppData\\Local\\ms-playwright\\chromium-1223\\chrome-win64\\chrome.exe",
  });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0",
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  let ok = 0;
  let fail = 0;

  for (let i = 0; i < todo.length; i++) {
    const { model, url } = todo[i];
    process.stdout.write(`  [${i + 1}/${todo.length}] ${model} ...`);
    try {
      await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
      await page.waitForTimeout(2000);

      const imgUrl = await page.evaluate(() => {
        const og = document.querySelector('meta[property="og:image"]');
        if (og && og.content) return og.content;
        const selectors = [
          ".product-banner img",
          ".product-detail img",
          ".product-image img",
          ".hero-banner img",
          ".product-hero img",
          ".pdp-image img",
          'img[class*="product"]',
          'img[class*="hero"]',
          'img[class*="banner"]',
        ];
        for (const sel of selectors) {
          const img = document.querySelector(sel);
          if (img && (img.src || img.dataset.src)) return img.src || img.dataset.src;
        }
        const imgs = document.querySelectorAll("img");
        for (const img of imgs) {
          const src = img.src || img.dataset.src || "";
          if (
            src &&
            (src.includes("upload") || src.includes("product") || src.includes("img"))
          ) {
            if (
              !src.includes("logo") &&
              !src.includes("icon") &&
              !src.includes("menu")
            ) {
              const rect = img.getBoundingClientRect();
              if (rect.width > 100 && rect.height > 100) return src;
            }
          }
        }
        return null;
      });

      if (imgUrl) {
        const ext = imgUrl.toLowerCase().includes(".png")
          ? ".png"
          : imgUrl.toLowerCase().includes(".webp")
          ? ".webp"
          : ".jpg";
        const dest = join(IMAGE_DIR, safeName(model) + ext);
        await downloadFile(imgUrl, dest);
        mapping[model] = { url: imgUrl, local: dest };
        ok++;
        console.log(" OK");
      } else {
        mapping[model] = { url: "", local: "" };
        fail++;
        console.log(" NO IMG");
      }
    } catch (e) {
      mapping[model] = { url: "", local: "" };
      fail++;
      console.log(` ERR: ${e.message.slice(0, 80)}`);
    }

    if ((i + 1) % 20 === 0) {
      writeFileSync(MAPPING_PATH, JSON.stringify(mapping, null, 2));
    }
  }

  await browser.close();
  writeFileSync(MAPPING_PATH, JSON.stringify(mapping, null, 2));

  const total = Object.keys(mapping).length;
  const totalOk = Object.values(mapping).filter((v) => v.local).length;
  console.log(`\nHK Done: ${ok} OK, ${fail} failed`);
  console.log(`Total mapping: ${totalOk}/${total} images saved to ${MAPPING_PATH}`);
})();
