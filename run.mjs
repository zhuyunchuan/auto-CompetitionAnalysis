import { spawn, execSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, mkdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname);
const SCRIPTS = join(ROOT, "scripts");
const RESULTS = join(ROOT, "results");

// ─── Chromium auto-detect ───────────────────────────────────────────
function detectChromium() {
  const homedir = process.env.USERPROFILE || "C:\\Users\\12298";
  const playwrightDir = join(homedir, "AppData", "Local", "ms-playwright");
  if (!existsSync(playwrightDir)) return null;
  const dirs = readdirSync(playwrightDir).filter((d) => d.startsWith("chromium-") && !d.includes("headless"));
  dirs.sort().reverse();
  for (const d of dirs) {
    const exe = join(playwrightDir, d, "chrome-win64", "chrome.exe");
    if (existsSync(exe)) return exe;
  }
  return null;
}

const CHROMIUM_PATH = detectChromium();

// ─── Python auto-detect ─────────────────────────────────────────────
function detectPython() {
  for (const cmd of ["python", "python3"]) {
    try {
      const out = execSync(`${cmd} --version`, { encoding: "utf-8", stdio: "pipe" });
      if (out.match(/Python (3\.\d+)/)) return cmd;
    } catch {}
  }
  return "python";
}

const PYTHON = detectPython();

// ─── CLI help ───────────────────────────────────────────────────────
const HELP = `
Usage: node run.mjs <command> [options]

Commands:
  all                   Run full pipeline (discover → specs → wide)
  discover:hikvision    Discover Hikvision Pro/Value/HiLook structure
  discover:dahua        Discover Dahua WizSense 2/3 structure
  specs:hikvision       Batch-scrape Hikvision product specs
  specs:dahua           Batch-scrape Dahua product specs
  wide:hikvision        Generate Hikvision wide table from specs
  wide:dahua            Generate Dahua wide table from specs
  check                 Check environment dependencies
  help                  Show this help

Options:
  --concurrency=N       Concurrency for batch scraping (default: 4, max: 6)
  --limit=N             Limit number of products for batch scraping
  --structure=PATH      Custom structure JSON path for specs scraping

Examples:
  node run.mjs all
  node run.mjs discover:hikvision
  node run.mjs specs:hikvision --concurrency=6 --limit=50
  node run.mjs wide:dahua
`;

// ─── Logging ────────────────────────────────────────────────────────
function step(msg) {
  const line = "=".repeat(Math.max(0, 60 - msg.length));
  console.log(`\n  ${msg} ${line}`);
}

function ok(msg) {
  console.log(`  \u2705 ${msg}`);
}

// ─── Script runners ─────────────────────────────────────────────────
function runNode(script, args = []) {
  return new Promise((resolve, reject) => {
    const scriptPath = join(SCRIPTS, script);
    if (!existsSync(scriptPath)) return reject(new Error(`Script not found: ${scriptPath}`));
    console.log(`  $ node ${script} ${args.join(" ")}`);
    const proc = spawn("node", [scriptPath, ...args], { cwd: ROOT, stdio: ["ignore", "inherit", "inherit"], shell: true });
    proc.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`Exit code ${code}`))));
    proc.on("error", reject);
  });
}

function runPython(script, args = []) {
  return new Promise((resolve, reject) => {
    const scriptPath = join(SCRIPTS, script);
    if (!existsSync(scriptPath)) return reject(new Error(`Script not found: ${scriptPath}`));
    console.log(`  $ ${PYTHON} ${script} ${args.join(" ")}`);
    const proc = spawn(PYTHON, [scriptPath, ...args], { cwd: ROOT, stdio: ["ignore", "inherit", "inherit"], shell: true });
    proc.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`Exit code ${code}`))));
    proc.on("error", reject);
  });
}

function findLatest(dir, prefix) {
  if (!existsSync(dir)) return null;
  const dirs = readdirSync(dir).filter((d) => d.startsWith(prefix)).sort().reverse();
  return dirs.length ? join(dir, dirs[0]) : null;
}

function formatBytes(bytes) {
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

// ─── Environment check ──────────────────────────────────────────────
async function checkEnv() {
  console.log(`\n${"=".repeat(70)}`);
  console.log("  竞品参数自动抓取系统 \u2014 环境检查");
  console.log(`${"=".repeat(70)}\n`);

  console.log(`  Project root: ${ROOT}`);

  if (CHROMIUM_PATH) {
    ok(`Chromium: ${CHROMIUM_PATH}`);
  } else {
    console.log("  \u274c Chromium not found \u2014 run: npx playwright install chromium");
  }

  try {
    const v = execSync("node --version", { encoding: "utf-8" }).trim();
    ok(`Node.js: ${v}`);
  } catch {
    console.log("  \u274c Node.js not found");
  }

  try {
    const v = execSync(`${PYTHON} --version`, { encoding: "utf-8" }).trim();
    ok(`Python: ${v}`);
  } catch {
    console.log("  \u274c Python not found");
  }

  console.log(`\n  Scripts:`);
  const checks = [
    "hikvision_structure_by_filter.mjs", "dahua_wizsense_structure.mjs",
    "hikvision_batch_specs_from_structure.mjs", "dahua_batch_specs_from_structure.mjs",
    "normalize_specs.py",
  ];
  for (const s of checks) {
    ok(existsSync(join(SCRIPTS, s)) ? s : `${s} \u2014 MISSING`);
  }

  if (!existsSync(RESULTS)) {
    mkdirSync(RESULTS, { recursive: true });
  }
  const items = readdirSync(RESULTS).filter((d) => !d.startsWith(".")).length;
  ok(`Results dir: ${RESULTS} (${items} items)`);

  console.log(`\n  Run: node run.mjs help`);
  console.log(`${"=".repeat(70)}\n`);
}

// ─── Commands ───────────────────────────────────────────────────────
async function discoverHikvision() {
  step("Discovering Hikvision Pro/Value/HiLook hierarchy");
  await runNode("hikvision_structure_by_filter.mjs");
  const dir = findLatest(RESULTS, "hikvision_structure_filtered_");
  if (!dir) throw new Error("No Hikvision structure output found");
  const meta = JSON.parse(readFileSync(join(dir, "structure_filtered.json"), "utf-8"));
  const pro = Object.keys(meta.series?.Pro || {}).length;
  const value = Object.keys(meta.series?.Value || {}).length;
  const hilook = Object.keys(meta.series?.HiLook || {}).length;
  ok(`Pro: ${pro} sub-series, Value: ${value} sub-series, HiLook: ${hilook} sub-series`);
  ok(`Output: ${dir}`);
  return dir;
}

async function discoverDahua() {
  step("Discovering Dahua WizSense 2/3 hierarchy");
  await runNode("dahua_wizsense_structure.mjs");
  const dir = findLatest(RESULTS, "dahua_wizsense_structure_");
  if (!dir) throw new Error("No Dahua structure output found");
  const meta = JSON.parse(readFileSync(join(dir, "dahua_wizsense_structure.json"), "utf-8"));
  const ws2 = Object.keys(meta.series?.["WizSense 2"]?.subseries || {}).length;
  const ws3 = Object.keys(meta.series?.["WizSense 3"]?.subseries || {}).length;
  ok(`WizSense 2: ${ws2} sub-series, WizSense 3: ${ws3} sub-series`);
  ok(`Output: ${dir}`);
  return dir;
}

async function specsHikvision(args, opts = {}) {
  const conc = opts.concurrency || 4;
  step("Batch-scraping Hikvision product specs");
  const cliArgs = [`--concurrency=${conc}`];
  if (opts.limit) cliArgs.push(`--limit=${opts.limit}`);
  const structArg = args.find((a) => a.startsWith("--structure="));
  if (structArg) cliArgs.push(structArg);
  await runNode("hikvision_batch_specs_from_structure.mjs", cliArgs);
  const dir = findLatest(RESULTS, "hikvision_specs_all_");
  if (!dir) throw new Error("No Hikvision specs output found");
  const csv = join(dir, "specs_long.csv");
  if (existsSync(csv)) ok(`specs_long.csv: ${formatBytes(statSync(csv).size)}`);
  ok(`Output: ${dir}`);
  return dir;
}

async function specsDahua(args, opts = {}) {
  const conc = opts.concurrency || 4;
  step("Batch-scraping Dahua WizSense product specs");
  const cliArgs = [`--concurrency=${conc}`];
  if (opts.limit) cliArgs.push(`--limit=${opts.limit}`);
  const structArg = args.find((a) => a.startsWith("--structure="));
  if (structArg) cliArgs.push(structArg);
  await runNode("dahua_batch_specs_from_structure.mjs", cliArgs);
  const dir = findLatest(RESULTS, "dahua_specs_all_");
  if (!dir) throw new Error("No Dahua specs output found");
  const csv = join(dir, "specs_long.csv");
  if (existsSync(csv)) ok(`specs_long.csv: ${formatBytes(statSync(csv).size)}`);
  ok(`Output: ${dir}`);
  return dir;
}

async function wideHikvision() {
  step("Generating Hikvision wide table");
  const dir = findLatest(RESULTS, "hikvision_specs_all_");
  if (!dir) throw new Error("No Hikvision specs found \u2014 run specs:hikvision first");
  const csvPath = join(dir, "specs_long.csv");
  if (!existsSync(csvPath)) throw new Error(`No specs_long.csv in ${dir}`);
  await runPython("normalize_specs.py", [csvPath, dir]);
  const widePath = join(dir, "specs_wide.csv");
  if (existsSync(widePath)) ok(`specs_wide.csv: ${formatBytes(statSync(widePath).size)}`);
  ok(`Output: ${widePath}`);
  return widePath;
}

async function wideDahua() {
  step("Generating Dahua wide table");
  const dir = findLatest(RESULTS, "dahua_specs_all_");
  if (!dir) throw new Error("No Dahua specs found \u2014 run specs:dahua first");
  const csvPath = join(dir, "specs_long.csv");
  if (!existsSync(csvPath)) throw new Error(`No specs_long.csv in ${dir}`);
  await runPython("normalize_specs.py", [csvPath, dir]);
  const widePath = join(dir, "specs_wide.csv");
  if (existsSync(widePath)) ok(`specs_wide.csv: ${formatBytes(statSync(widePath).size)}`);
  ok(`Output: ${widePath}`);
  return widePath;
}

// ─── Main ───────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  const cmd = args[0] || "help";

  if (cmd === "check" || cmd === "--check") {
    await checkEnv();
    return;
  }

  if (cmd === "help" || cmd === "--help" || cmd === "-h") {
    console.log(HELP);
    return;
  }

  const opts = {};
  const concArg = args.find((a) => a.startsWith("--concurrency="));
  if (concArg) opts.concurrency = parseInt(concArg.split("=")[1], 10) || 4;
  const limitArg = args.find((a) => a.startsWith("--limit="));
  if (limitArg) opts.limit = parseInt(limitArg.split("=")[1], 10) || null;

  const start = Date.now();
  const summary = [];

  try {
    switch (cmd) {
      case "all":
        console.log(`\n${"\u2550".repeat(70)}`);
        console.log("  竞品参数自动抓取系统 \u2014 全流程执行");
        console.log(`${"\u2550".repeat(70)}`);
        summary.push(["Hikvision \u5c42\u7ea7\u53d1\u73b0", await discoverHikvision()]);
        summary.push(["Dahua \u5c42\u7ea7\u53d1\u73b0", await discoverDahua()]);
        summary.push(["Hikvision \u89c4\u683c\u6293\u53d6", await specsHikvision(args, opts)]);
        summary.push(["Dahua \u89c4\u683c\u6293\u53d6", await specsDahua(args, opts)]);
        summary.push(["Hikvision \u5bbd\u8868", await wideHikvision()]);
        summary.push(["Dahua \u5bbd\u8868", await wideDahua()]);
        break;

      case "discover:hikvision":
        summary.push(["Hikvision \u5c42\u7ea7\u53d1\u73b0", await discoverHikvision()]);
        break;

      case "discover:dahua":
        summary.push(["Dahua \u5c42\u7ea7\u53d1\u73b0", await discoverDahua()]);
        break;

      case "specs:hikvision":
        summary.push(["Hikvision \u89c4\u683c\u6293\u53d6", await specsHikvision(args, opts)]);
        break;

      case "specs:dahua":
        summary.push(["Dahua \u89c4\u683c\u6293\u53d6", await specsDahua(args, opts)]);
        break;

      case "wide:hikvision":
        summary.push(["Hikvision \u5bbd\u8868", await wideHikvision()]);
        break;

      case "wide:dahua":
        summary.push(["Dahua \u5bbd\u8868", await wideDahua()]);
        break;

      default:
        console.log(`\n  Unknown command: ${cmd}\n`);
        console.log(HELP);
        process.exit(1);
    }

    const mins = ((Date.now() - start) / 60000).toFixed(1);
    console.log(`\n${"\u2550".repeat(70)}`);
    console.log(`  \u2705 \u5168\u90e8\u5b8c\u6210 | \u8017\u65f6 ${mins} \u5206\u949f | ${summary.length} \u4e2a\u6b65\u9aa4`);
    console.log(`${"\u2550".repeat(70)}`);
    for (const [name, path] of summary) {
      console.log(`    ${name}: ${path}`);
    }
    console.log();
  } catch (err) {
    const mins = ((Date.now() - start) / 60000).toFixed(1);
    console.error(`\n  \u274c \u6267\u884c\u5931\u8d25 (${mins} \u5206\u949f): ${err.message}`);
    if (summary.length) {
      console.log("  \u5df2\u5b8c\u6210:");
      for (const [name, path] of summary) {
        console.log(`    \u2705 ${name}: ${path}`);
      }
    }
    console.log();
    process.exit(1);
  }
}

main();
