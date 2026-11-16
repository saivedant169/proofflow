// ProofFlow film: capture the product stills (stills/*.png + stills/stills.json) from a running ProofFlow app.
//
//   node tools/capture-stills.mjs --base http://localhost:5188 --out stills [--puppeteer <dir with node_modules>]
//
// Drives the real app with headless Chrome (puppeteer-core): the guided sample (EUR → USD 1.10 → 1.20, refresh)
// and the documented two-row CSV (fixtures/browser_csv_v1/valid_non_eu.csv, region NORTH, EUR → USD 1.20 → 1.30:
// create, publish the correction, inspect, refresh, check, copy). Dark theme, reduced motion, no cursor or hover.
// Full frames at device scale 2 on a 1600 CSS px viewport; each crop is re-rendered at scale 3 or 4 from the same
// live state (never upscaled). Writes the flat manifest that tools/stills-shape.mjs and FILM.mountStill read.
// The app must reach a real backend (the hosted one through a dev proxy works); nothing is mocked.
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";

const here = dirname(fileURLToPath(import.meta.url));
const film = resolve(here, "..");
const repo = resolve(film, "..");
const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
};
const BASE = arg("base", "http://localhost:5188");
const OUT = resolve(film, arg("out", "stills"));
const CHROME = arg("chrome", "C:/Program Files/Google/Chrome/Application/chrome.exe");
const ONLY = arg("only", "");
const requireFrom = createRequire(join(resolve(arg("puppeteer", process.env.PUPPETEER_DIR ?? film)), "package.json"));
const puppeteer = requireFrom("puppeteer-core");

const VIEW = { width: 1600, height: 1000 };
const SCALE = 2;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CSV = readFileSync(join(repo, "fixtures/browser_csv_v1/valid_non_eu.csv"), "utf8");

mkdirSync(OUT, { recursive: true });
const manifest = {
  version: 1,
  deviceScaleFactor: SCALE,
  source: `ProofFlow app (frontend/, restyled) at ${BASE}, API proxied to the hosted backend`,
  theme: "dark",
  stills: {},
};

/* ---------- box selectors: one name, one or more elements (union) ---------- */
const WORK = {
  headline: ".intro h1",
  "dataset-bar": ".dataset-bar",
  "workflow-section": ".workspace-workflow",
  workflow: ".workflow-actions",
  "change-source": ".workflow-actions > li:nth-child(1) button",
  "update-csv": ".workflow-actions > li:nth-child(1) button",
  "refresh-affected": ".workflow-actions > li:nth-child(2) button",
  "check-values": ".workflow-actions > li:nth-child(3):not(.workflow-handoff) button, .refresh-banner button",
  handoff: ".workflow-handoff",
  "download-reports": ".workflow-handoff button:nth-child(1)",
  "copy-report": ".workflow-handoff button:nth-child(2)",
  receipt: ".report-export-status",
  "report-panel": ".report-panel",
  "company-revenue": ".report-panel .metric-main",
  "eu-revenue": ".secondary-metrics > .metric:nth-child(1)",
  "regional-revenue": ".secondary-metrics > .metric:nth-child(1)",
  "eu-support": ".secondary-metrics > .metric:nth-child(2)",
  "support-link": ".import-report-note",
  "report-links": ".report-provenance",
  "withheld-notice": ".withheld-notice",
  "withheld-claims": ".report-panel .metric-withheld",
  graph: ".graph-panel",
  "graph-reports": ".graph-node-report",
  "affected-path": ".graph-node-affected",
  "changed-source": ".graph-node-affected.graph-node-source",
  banner: ".impact-banner, .refresh-banner",
  verification: ".verification-banner",
  "verification-text": ".verification-banner > span",
  accounting: ".import-accounting",
  activity: ".activity-panel",
  "activity-rows": ".activity-list",
};
const DRAWER = {
  drawer: ".drawer",
  "drawer-header": ".drawer-header",
  options: ".source-options",
  "fx-option": ".source-option.selected",
  editor: ".source-editor",
  "fx-input": ".source-input-row",
  apply: ".source-form > button[type=submit]",
  csv: "#import-csv",
  "file-actions": ".import-file-actions",
  rates: ".import-rates",
  region: ".import-region",
  preview: ".import-preview",
  submit: ".import-form > button[type=submit]",
  name: ".evidence-name",
  facts: ".evidence-facts",
  path: ".evidence-path",
  why: ".evidence-section",
};
const BENCH = {
  intro: ".benchmark-intro",
  "model-comparison": ".model-comparison",
  "model-table": ".model-comparison-table",
  retail: ".retail-benchmark",
  "pilot-table": ".benchmark-section.panel .benchmark-table",
  "execution-results": ".execution-results",
  "full-context-limit": ".benchmark-limit",
  "recorded-agent": ".recorded-agent",
  disclosure: ".recorded-disclosure",
  "run-1": ".agent-runs > li:nth-child(1)",
  "run-2": ".agent-runs > li:nth-child(2)",
  "refresh-proof": ".agent-refresh-proof",
};

const round = (v) => Math.round(v * 1000) / 1000;

async function measure(page, selectors, { document: inDocument }) {
  return page.evaluate(
    (selectors, inDocument) => {
      const out = {};
      const sx = inDocument ? window.scrollX : 0;
      const sy = inDocument ? window.scrollY : 0;
      for (const [name, sel] of Object.entries(selectors)) {
        const rects = [...document.querySelectorAll(sel)]
          .filter((el) => el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
          .map((el) => el.getBoundingClientRect())
          .filter((r) => r.width > 0 && r.height > 0);
        if (!rects.length) continue;
        const x = Math.min(...rects.map((r) => r.left)) + sx;
        const y = Math.min(...rects.map((r) => r.top)) + sy;
        const r = Math.max(...rects.map((r) => r.right)) + sx;
        const b = Math.max(...rects.map((r) => r.bottom)) + sy;
        out[name] = { x, y, w: r - x, h: b - y };
      }
      return out;
    },
    selectors,
    inDocument,
  );
}

async function settle(page, ms = 900) {
  await page.waitForFunction(() => !document.querySelector(".spin, .drawer-loading"), { timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  await page.mouse.move(1, 1);
  await sleep(ms);
}

const click = (page, selector) =>
  page.$eval(selector, (el) => {
    el.scrollIntoView({ block: "center" });
    el.click();
  });
async function clickText(page, selector, text) {
  const ok = await page.evaluate(
    (selector, text) => {
      const el = [...document.querySelectorAll(selector)].find((e) => e.textContent.trim().includes(text));
      if (!el) return false;
      el.click();
      return true;
    },
    selector,
    text,
  );
  if (!ok) throw new Error(`no ${selector} with text "${text}"`);
}
async function setValue(page, selector, value) {
  await page.$eval(
    selector,
    (el, value) => {
      const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    },
    value,
  );
}
const waitFor = (page, selector) => page.waitForSelector(selector, { visible: true, timeout: 60000 });

/** Shoot one state: a full frame plus its crops. crops: [{ name, boxes: [box names] | rect, pad, scale }]. */
async function shoot(page, id, { title, state, kind = "workspace", crops = [], flagsFrom }) {
  if (ONLY && !id.startsWith(ONLY)) return;
  const fixed = kind === "drawer";
  // a drawer frame names only drawer parts (the page behind it is dimmed under the scrim)
  const selectors = kind === "bench" ? BENCH : fixed ? DRAWER : WORK;
  // drawers are fixed, so the page behind can sit at the top too (puppeteer clips relative to the scroll)
  await page.evaluate(() => window.scrollTo(0, 0));
  await settle(page);
  const view = page.viewport();
  const docH = fixed ? view.height : await page.evaluate(() => Math.ceil(document.documentElement.scrollHeight));
  const width = view.width;
  const height = fixed ? view.height : docH;
  const boxes = await measure(page, selectors, { document: !fixed });
  {
    // keep only boxes that lie inside the frame
    for (const [n, b] of Object.entries(boxes))
      if (b.x < -0.5 || b.y < -0.5 || b.x + b.w > width + 0.5 || b.y + b.h > height + 0.5) delete boxes[n];
  }
  const baseScale = view.deviceScaleFactor;
  const file = `${id}.png`;
  await page.screenshot({ path: join(OUT, file), fullPage: !fixed, captureBeyondViewport: !fixed });
  const flags = [];
  if (flagsFrom) {
    const flag = await page.evaluate((sel) => document.querySelector(sel)?.innerText.replace(/\s*\n\s*/g, " · "), flagsFrom.selector);
    if (flag && boxes[flagsFrom.box]) flags.push({ text: flag, box: boxes[flagsFrom.box] });
  }
  manifest.stills[id] = {
    file,
    state,
    title,
    kind: "full",
    width,
    height,
    scale: baseScale,
    boxes: mapRound(boxes),
    ...(flags.length ? { flags: flags.map((f) => ({ text: f.text, box: mapRound({ b: f.box }).b })) } : {}),
    capture: {
      url: page.url().replace(BASE, "(app)"),
      viewport: { width: view.width, height: view.height },
      fullPage: !fixed,
      capturedAt: new Date().toISOString(),
      colorScheme: "dark",
    },
  };
  for (const crop of crops) {
    let r;
    if (typeof crop.rect === "function") r = crop.rect(boxes);
    else if (crop.rect) r = { ...crop.rect };
    else {
      const parts = crop.boxes.map((n) => boxes[n] ?? fail(`${id}: no box "${n}" for crop ${crop.name}`));
      const x = Math.min(...parts.map((b) => b.x));
      const y = Math.min(...parts.map((b) => b.y));
      r = { x, y, w: Math.max(...parts.map((b) => b.x + b.w)) - x, h: Math.max(...parts.map((b) => b.y + b.h)) - y };
    }
    const pad = crop.pad ?? 8;
    const x0 = Math.max(0, Math.floor(r.x - pad));
    const y0 = Math.max(0, Math.floor(r.y - pad));
    const x1 = Math.min(width, Math.ceil(r.x + r.w + pad));
    const y1 = Math.min(height, Math.ceil(r.y + r.h + pad));
    const clip = { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
    if (clip.width <= 0 || clip.height <= 0) fail(`${id}.${crop.name}: empty crop ${JSON.stringify({ r, clip })}`);
    const scale = crop.scale ?? 4;
    await page.setViewport({ ...view, deviceScaleFactor: scale });
    await settle(page, 500);
    const cropFile = `${id}.${crop.name}@${scale}x.png`;
    await page.screenshot({ path: join(OUT, cropFile), clip, captureBeyondViewport: !fixed });
    await page.setViewport(view);
    await settle(page, 300);
    const inside = {};
    for (const [n, b] of Object.entries(boxes)) {
      if (b.x >= x0 - 0.5 && b.y >= y0 - 0.5 && b.x + b.w <= x1 + 0.5 && b.y + b.h <= y1 + 0.5)
        inside[n] = { x: b.x - x0, y: b.y - y0, w: b.w, h: b.h };
    }
    manifest.stills[`${id}.${crop.name}`] = {
      file: cropFile,
      state,
      kind: "crop",
      width: clip.width,
      height: clip.height,
      scale,
      boxes: mapRound(inside),
      cropOf: id,
      origin: { x: x0, y: y0 },
    };
  }
  console.log(`captured ${id} (${width}x${height}) + ${crops.length} crops`);
}
function mapRound(boxes) {
  return Object.fromEntries(
    Object.entries(boxes).map(([n, b]) => [n, { x: round(b.x), y: round(b.y), w: round(b.w), h: round(b.h) }]),
  );
}
function fail(message) {
  throw new Error(message);
}

async function newPage(browser, viewport = { ...VIEW, deviceScaleFactor: SCALE }, mobile = false) {
  const page = await browser.newPage();
  await page.setViewport({ ...viewport, ...(mobile ? { isMobile: true, hasTouch: true } : {}) });
  await page.emulateMediaFeatures([
    { name: "prefers-color-scheme", value: "dark" },
    { name: "prefers-reduced-motion", value: "reduce" },
  ]);
  await page.evaluateOnNewDocument(() => {
    try {
      localStorage.setItem("proofflow-site-theme", "dark");
    } catch {}
  });
  page.on("pageerror", (e) => console.warn("pageerror:", e.message));
  page.on("console", (m) => m.type() === "error" && console.warn("console:", m.text()));
  return page;
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--hide-scrollbars", "--force-color-profile=srgb", "--font-render-hinting=none"],
});
try {
  const context = browser.defaultBrowserContext();
  await context.overridePermissions(new URL(BASE).origin, ["clipboard-read", "clipboard-write", "clipboard-sanitized-write"]);
  const page = await newPage(browser);
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await waitFor(page, ".report-panel .metric-main");
  const guidedFlag = { selector: ".dataset-bar > div:first-child", box: "dataset-bar" };

  /* ---------------- guided sample ---------------- */
  await shoot(page, "p01-workspace", {
    title: "Guided sample workspace, everything current",
    state: "1",
    flagsFrom: guidedFlag,
    crops: [
      { name: "report", boxes: ["report-panel"], scale: 4 },
      { name: "graph", boxes: ["graph"], scale: 3 },
      { name: "workflow", boxes: ["workflow"], pad: 12, scale: 4 },
      { name: "headline", boxes: ["headline"], pad: 16, scale: 3 },
    ],
  });

  // phone width, same guided state (a second page shares the session cookie)
  if (!ONLY || "p12-mobile".startsWith(ONLY)) {
    const phone = await newPage(browser, { width: 390, height: 844, deviceScaleFactor: 3 }, true);
    await phone.goto(`${BASE}/`, { waitUntil: "networkidle0" });
    await waitFor(phone, ".report-panel .metric-main");
    await shoot(phone, "p12-mobile", {
      title: "Guided sample workspace at phone width (390 CSS px)",
      state: "1",
      crops: [
        { name: "phone-screen", rect: { x: 0, y: 0, w: 390, h: 844 }, pad: 0, scale: 3 },
        { name: "report", boxes: ["report-panel"], scale: 4 },
      ],
    });
    await phone.close();
  }

  await click(page, ".workflow-actions > li:nth-child(1) button");
  await waitFor(page, ".source-editor #fx-value");
  await setValue(page, "#fx-value", "1.20");
  await shoot(page, "p02-change-source", {
    kind: "drawer",
    title: "Change a source drawer: Exchange rate selected, EUR → USD 1.20 entered, not yet applied",
    state: "2",
    crops: [
      { name: "editor", boxes: ["editor", "apply"], scale: 4 },
      { name: "options", boxes: ["drawer-header", "options"], scale: 3 },
      { name: "fx-option", boxes: ["fx-option"], pad: 4, scale: 4 },
    ],
  });
  await click(page, ".source-form > button[type=submit]");
  await page.waitForSelector(".drawer", { hidden: true, timeout: 60000 });
  await waitFor(page, ".impact-banner");
  await shoot(page, "p03-stale", {
    title: "After the EUR → USD 1.20 correction: affected figures withheld, affected path highlighted",
    state: "3",
    flagsFrom: guidedFlag,
    crops: [
      { name: "banner", boxes: ["banner"], scale: 4 },
      { name: "report", boxes: ["report-panel"], scale: 4 },
      { name: "graph", boxes: ["graph"], scale: 3 },
      { name: "workflow", boxes: ["workflow"], pad: 12, scale: 4 },
    ],
  });
  await click(page, ".secondary-metrics > .metric:nth-child(1)");
  await waitFor(page, ".evidence-path");
  await shoot(page, "p04-evidence", {
    kind: "drawer",
    title: "Inspect evidence for the withheld EU revenue figure: the native HydraDB dependency path",
    state: "3",
    crops: [
      { name: "path", boxes: ["path"], scale: 4 },
      { name: "header", boxes: ["drawer-header", "name", "facts"], scale: 3 },
    ],
  });
  await page.keyboard.press("Escape");
  await page.waitForSelector(".drawer", { hidden: true });
  await click(page, ".workflow-actions > li:nth-child(2) button");
  await waitFor(page, ".refresh-banner");
  await shoot(page, "p05-refreshed", {
    title: "After Refresh affected: current values, four tool calls, support unchanged",
    state: "4",
    flagsFrom: guidedFlag,
    crops: [
      { name: "banner", boxes: ["banner"], scale: 4 },
      { name: "report", boxes: ["report-panel"], scale: 4 },
      { name: "activity", boxes: ["activity"], scale: 3 },
      { name: "graph", boxes: ["graph"], scale: 3 },
    ],
  });

  /* ---------------- the documented two-row CSV ---------------- */
  await page.evaluate(() => window.scrollTo(0, 0));
  await clickText(page, ".intro-actions button", "Use your data");
  await waitFor(page, "#import-csv");
  const tmp = join(tmpdir(), `proofflow-film-${process.pid}`);
  mkdirSync(tmp, { recursive: true });
  const csvFile = join(tmp, "orders.csv");
  writeFileSync(csvFile, CSV);
  const input = await page.$(".import-file-actions input[type=file]");
  await input.uploadFile(csvFile);
  await page.waitForFunction(() => document.querySelector("#import-csv").value.includes("NORTH"));
  await setValue(page, ".import-rates label:nth-child(1) input", "1.20");
  await setValue(page, "#import-region", "NORTH");
  await page.$eval(".drawer", (d) => (d.scrollTop = 0));
  await shoot(page, "p06-csv-form", {
    kind: "drawer",
    title: "Use your data: the two-row orders CSV uploaded, EUR → USD 1.20, region NORTH, before validation",
    state: "5",
    crops: [
      { name: "csv", boxes: ["file-actions", "csv"], scale: 4 },
      { name: "rates", boxes: ["rates", "region"], scale: 4 },
    ],
  });
  await click(page, ".import-form > button[type=submit]");
  await waitFor(page, ".import-preview");
  await page.$eval(".drawer", (d) => {
    const p = d.querySelector(".import-preview");
    d.scrollTop = p.offsetTop - 360;
  });
  await shoot(page, "p06-csv-preview", {
    kind: "drawer",
    title: "After Validate CSV: a preview that saves nothing, ready to create",
    state: "6",
    crops: [
      { name: "preview", boxes: ["preview"], scale: 4 },
      { name: "preview-create", boxes: ["preview", "submit"], scale: 3 },
    ],
  });
  await click(page, ".import-form > button[type=submit]");
  await page.waitForSelector(".drawer", { hidden: true, timeout: 60000 });
  await waitFor(page, ".import-accounting");
  await shoot(page, "p07-csv-created", {
    title: "The CSV workspace after Create reports: both reports current",
    state: "7",
    flagsFrom: guidedFlag,
    crops: [
      { name: "report", boxes: ["report-panel"], scale: 4 },
      { name: "accounting", boxes: ["accounting"], scale: 4 },
      { name: "graph", boxes: ["graph"], scale: 3 },
      { name: "workflow", boxes: ["workflow"], pad: 12, scale: 4 },
    ],
  });
  await click(page, ".workflow-actions > li:nth-child(1) button");
  await waitFor(page, "#import-csv");
  await page.waitForFunction(() => document.querySelector("#import-csv").value.includes("NORTH"));
  await setValue(page, ".import-rates label:nth-child(1) input", "1.30");
  await click(page, ".import-form > button[type=submit]");
  await waitFor(page, ".import-preview");
  await page.$eval(".drawer", (d) => {
    const p = d.querySelector(".import-rates");
    d.scrollTop = p.offsetTop - 140;
  });
  await shoot(page, "p08-csv-update", {
    kind: "drawer",
    title: "Update your CSV: the same rows, EUR → USD corrected to 1.30, validated and ready to publish",
    state: "8",
    crops: [
      { name: "rates", boxes: ["rates"], scale: 4 },
      { name: "publish", boxes: ["rates", "preview", "submit"], scale: 4 },
      { name: "preview-publish", boxes: ["preview", "submit"], scale: 3 },
    ],
  });
  await click(page, ".import-form > button[type=submit]");
  await page.waitForSelector(".drawer", { hidden: true, timeout: 60000 });
  await waitFor(page, ".impact-banner");
  await shoot(page, "p08-csv-stale", {
    title: "After Publish correction: the affected CSV figures withheld until refresh",
    state: "9",
    flagsFrom: guidedFlag,
    crops: [
      { name: "banner", boxes: ["banner"], scale: 4 },
      { name: "report", boxes: ["report-panel"], scale: 4 },
      { name: "graph", boxes: ["graph"], scale: 3 },
      { name: "accounting", boxes: ["accounting"], scale: 4 },
    ],
  });
  await click(page, ".report-provenance button:nth-of-type(2)");
  await waitFor(page, ".evidence-path");
  await shoot(page, "p08-csv-evidence", {
    kind: "drawer",
    title: "Inspect evidence for the withheld regional report: its native path back to the corrected rate",
    state: "9",
    crops: [
      { name: "path", boxes: ["path"], scale: 4 },
      { name: "header", boxes: ["drawer-header", "name", "facts"], scale: 3 },
    ],
  });
  await page.keyboard.press("Escape");
  await page.waitForSelector(".drawer", { hidden: true });
  await click(page, ".workflow-actions > li:nth-child(2) button");
  await waitFor(page, ".refresh-banner");
  await shoot(page, "p09-csv-refreshed-unchecked", {
    title: "After Refresh affected, before Check values: refreshed CSV figures",
    state: "10",
    flagsFrom: guidedFlag,
    crops: [
      { name: "banner", boxes: ["banner"], scale: 4 },
      { name: "report", boxes: ["report-panel"], scale: 4 },
    ],
  });
  await click(page, ".refresh-banner button");
  await waitFor(page, ".verification-banner");
  await shoot(page, "p09-csv-refreshed", {
    title: "After Check values: verified current figures, handoff controls enabled",
    state: "11",
    flagsFrom: guidedFlag,
    crops: [
      { name: "report", boxes: ["report-panel"], scale: 4 },
      { name: "handoff", boxes: ["workflow-section"], scale: 4 },
      { name: "verification", boxes: ["verification"], scale: 4 },
      { name: "accounting", boxes: ["accounting"], scale: 4 },
      { name: "graph", boxes: ["graph"], scale: 3 },
      { name: "activity", boxes: ["activity"], scale: 3 },
    ],
  });
  await click(page, ".workflow-handoff button:nth-child(2)");
  await waitFor(page, ".report-export-status");
  await shoot(page, "p09-csv-copied", {
    title: "Copy checked report: the server checked every figure current, then copied the snapshot",
    state: "12",
    flagsFrom: guidedFlag,
    crops: [
      { name: "handoff", boxes: ["workflow-section"], scale: 4 },
      { name: "receipt", boxes: ["receipt"], scale: 4 },
      // the two controls alone, and the verified line alone (icon + words, the banner's full height)
      { name: "copy", boxes: ["handoff"], scale: 4 },
      {
        name: "verified",
        rect: (b) => ({ x: b.verification.x, y: b.verification.y, w: b["verification-text"].x + b["verification-text"].w + 24 - b.verification.x, h: b.verification.h }),
        scale: 4,
      },
    ],
  });

  /* ---------------- benchmark ---------------- */
  await page.evaluate(() => window.scrollTo(0, 0));
  await clickText(page, "nav button", "Benchmark");
  await waitFor(page, ".model-comparison");
  await shoot(page, "p10-benchmark", {
    kind: "bench",
    title: "Benchmark view: recorded model comparison, retail benchmark and original pilot",
    state: "bench",
    crops: [
      { name: "top", rect: { x: 0, y: 0, w: 1600, h: 1000 }, pad: 0, scale: 3 },
      { name: "model-comparison", boxes: ["model-comparison"], scale: 3 },
      { name: "model-table", boxes: ["model-table"], scale: 4 },
      { name: "retail", boxes: ["retail"], scale: 3 },
      { name: "execution-results", boxes: ["execution-results", "full-context-limit"], scale: 4 },
    ],
  });
  await page.$eval(".recorded-agent", (d) => (d.open = true));
  await waitFor(page, ".agent-refresh-proof");
  await shoot(page, "p11-agent", {
    kind: "bench",
    title: "Benchmark view with the recorded agent workflow expanded",
    state: "bench",
    crops: [
      { name: "agent", boxes: ["recorded-agent"], scale: 3 },
      { name: "runs", boxes: ["run-1", "run-2"], scale: 4 },
      { name: "proof", boxes: ["refresh-proof"], scale: 4 },
    ],
  });
  rmSync(tmp, { recursive: true, force: true });
} finally {
  await browser.close();
}

const path = join(OUT, "stills.json");
if (ONLY) {
  const old = JSON.parse(readFileSync(path, "utf8"));
  Object.assign(old.stills, manifest.stills);
  writeFileSync(path, JSON.stringify(old, null, 2) + "\n");
} else writeFileSync(path, JSON.stringify(manifest, null, 2) + "\n");
console.log(`wrote ${Object.keys(manifest.stills).length} stills to ${path}`);
