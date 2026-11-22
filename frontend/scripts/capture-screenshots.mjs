// Capture README screenshots of every dashboard page.
// Needs the API (make api) and the dashboard (make web) running, plus a local Chrome.
// Usage: node scripts/capture-screenshots.mjs [baseUrl] [outDir]
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright-core";

const base = process.argv[2] ?? "http://localhost:3000";
const outDir = process.argv[3] ?? "../docs/img";
const pages = [
  ["overview", "/"],
  ["yield-curve", "/yield-curve"],
  ["fx", "/fx"],
  ["policy", "/policy"],
  ["data-quality", "/data-quality"],
  ["catalog", "/catalog"],
];

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });

async function shoot(theme, name, path, viewport = { width: 1440, height: 1000 }) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1.5, colorScheme: theme });
  await ctx.addInitScript((t) => localStorage.setItem("theme", t), theme);
  const page = await ctx.newPage();
  await page.goto(`${base}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const file = `${outDir}/${name}${theme === "dark" ? "-dark" : ""}.png`;
  await page.screenshot({ path: file, fullPage: false });
  console.log("saved", file);
  await ctx.close();
}

for (const [name, path] of pages) await shoot("light", name, path);
await shoot("dark", "overview", "/");
await shoot("light", "overview-mobile", "/", { width: 390, height: 844 });
await browser.close();
