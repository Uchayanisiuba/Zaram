/**
 * Capture the interface into docs/design/.
 *
 * Both the backend and the dev server must already be running. The URL is
 * localhost, not 127.0.0.1 — Vite binds to IPv6 and refuses the loopback
 * address, which is a good hour of confusion if you hit it.
 *
 *   node scripts/capture.mjs
 */
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, '../../docs/design');
const APP = 'http://localhost:5173';

const shots = [];
const shot = async (page, name, note) => {
  // timeout: the page pulls three fonts from fonts.googleapis.com, and
  // Playwright waits for webfonts before capturing. That request is also
  // unlogged egress on every launch — bundling the fonts locally would fix
  // both problems.
  await page.screenshot({ path: path.join(OUT, `${name}.png`), timeout: 15000 });
  shots.push(`${name}.png — ${note}`);
  console.log(`  captured ${name}.png`);
};

/** The landing hint appears on a timer and only before first use, so state has
 *  to be cleared between runs or most captures show a post-first-run app. */
const freshContext = async (browser) => {
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  // index.css pulls three fonts from fonts.googleapis.com. Playwright blocks on
  // webfonts before capturing, and that request does not resolve here — which
  // is also what a packaged app would face offline. Blocked so the page falls
  // back immediately. Bundling the fonts locally would fix the capture, the
  // offline case, and the unlogged egress on every launch.
  await ctx.route('**fonts.googleapis.com**', (r) => r.abort());
  await ctx.route('**fonts.gstatic.com**', (r) => r.abort());

  await ctx.addInitScript(() => {
    try {
      localStorage.clear();
    } catch {
      /* nothing stored yet */
    }
  });
  return ctx;
};

const main = async () => {
  await mkdir(OUT, { recursive: true });
  // channel: 'chromium' runs the full bundled browser. The default is the
  // separate chrome-headless-shell download, which is not always present.
  const browser = await chromium.launch({ channel: 'chromium' });

  // --- Landing, first run -------------------------------------------------
  let ctx = await freshContext(browser);
  let page = await ctx.newPage();
  // Not networkidle: the app polls /health on a timer, so the network never
  // goes quiet.
  await page.goto(APP, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  await shot(page, 'landing-at-rest', 'Orbital landing, quiet, no status label');

  // The hint is deliberately delayed so anyone who acts at once never sees it.
  await page.waitForTimeout(2600);
  await shot(page, 'landing-first-run-hint', 'Self-dismissing hint, ~3s after load');

  // --- Conversation -------------------------------------------------------
  // force: the orb animates continuously, so waiting for it to be "stable"
  // never succeeds.
  await page.getByTestId('orb-tap').click({ force: true });
  await page.waitForTimeout(900);
  await shot(page, 'conversation-open', 'Chat at 45%, orb shifted left, status beneath');

  const input = page.getByLabel('Message Zaram');
  await input.fill('Remember: the launch is 9 September in Bristol.');
  await input.press('Enter');
  // Local models are slow on a cold start; this is the warming state.
  await page.waitForTimeout(2800);
  await shot(page, 'orb-warming-up', 'Cold-start state on a first message');

  await page.waitForTimeout(30000);
  await input.fill('When is the launch?');
  await input.press('Enter');
  await page.waitForTimeout(25000);
  await shot(page, 'conversation-with-sources', 'A reply with its citations listed');

  // --- Source panel -------------------------------------------------------
  const citation = page.locator('button[title="Open this source"]').first();
  if (await citation.count()) {
    await citation.click({ force: true });
    await page.waitForTimeout(1500);
    await shot(page, 'source-panel-open', 'Citation opened, orb blurred and receded');

    const forget = page.getByRole('button', { name: /forget this/i });
    if (await forget.count()) {
      await forget.click({ force: true });
      await page.waitForTimeout(400);
      await shot(page, 'source-panel-confirm-delete', '"Delete for good?" with the consequence stated');
      const cancel = page.getByRole('button', { name: /^cancel$/i });
      if (await cancel.count()) await cancel.click({ force: true });
    }
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
  } else {
    console.log('  no citation present — skipped the source panel captures');
  }

  // --- Workspace shell ----------------------------------------------------
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  const memory = page.getByRole('button', { name: /^Memory$/ }).first();
  if (await memory.count()) {
    await memory.click({ force: true });
    await page.waitForTimeout(800);
    await shot(page, 'workspace-shell', 'Top bar, rail and dock, with the Orb at working size');
  }

  await ctx.close();

  // --- Offline ------------------------------------------------------------
  // Captured by blocking the health probe rather than stopping the backend, so
  // the run does not depend on process control.
  ctx = await freshContext(browser);
  page = await ctx.newPage();
  await page.route('**/health', (r) => r.abort());
  await page.goto(APP, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  // force: the orb animates continuously, so waiting for it to be "stable"
  // never succeeds.
  await page.getByTestId('orb-tap').click({ force: true });
  await page.waitForTimeout(1200);
  await shot(page, 'orb-offline', 'Backend unreachable');

  await ctx.close();
  await browser.close();

  console.log(`\n${shots.length} captures in docs/design/\n`);
  shots.forEach((s) => console.log(`  ${s}`));
};

main().catch((err) => {
  console.error('capture failed:', err.message);
  process.exit(1);
});
