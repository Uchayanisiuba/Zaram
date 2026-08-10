/**
 * Capture the landing page with Activity added, and the Activity surface itself.
 *
 * Both the backend (8420) and the dev server (5173) must be running.
 *   node scripts/capture-activity.mjs
 */
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(__dirname, '../../docs/design');
const APP = 'http://localhost:5173';

const main = async () => {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: 'chromium' });
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  // Fonts now ship in the bundle, so these should never fire. Kept as a
  // regression guard: if a remote font reference ever comes back, the capture
  // silently stops depending on the network rather than quietly restoring it.
  await ctx.route('**fonts.googleapis.com**', (r) => r.abort());
  await ctx.route('**fonts.gstatic.com**', (r) => r.abort());
  await ctx.addInitScript(() => {
    try { localStorage.clear(); } catch { /* nothing stored yet */ }
  });

  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));

  // Not networkidle: the app polls /health, so the network never goes quiet.
  await page.goto(APP, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, 'landing-four-nodes.png'), timeout: 15000 });
  console.log('  captured landing-four-nodes.png');

  // The hint appears on a delay so anyone who acts at once never sees it.
  await page.waitForTimeout(2400);
  await page.screenshot({ path: path.join(OUT, 'landing-click-to-begin.png'), timeout: 15000 });
  console.log('  captured landing-click-to-begin.png');

  // force: the orbital nodes animate continuously, so "stable" never arrives.
  await page.getByRole('button', { name: /Activity/ }).first().click({ force: true });
  await page.waitForTimeout(1600);
  await page.screenshot({ path: path.join(OUT, 'activity-log.png'), timeout: 15000 });
  console.log('  captured activity-log.png');

  // Clicking a row is what turns a claim into evidence: the literal text.
  const row = page.locator('tbody tr').first();
  if (await row.count()) {
    await row.click({ force: true });
    await page.waitForTimeout(900);
    await page.screenshot({ path: path.join(OUT, 'activity-literal-text.png'), timeout: 15000 });
    console.log('  captured activity-literal-text.png');
  } else {
    console.log('  no rows in the log — skipped the literal-text capture');
  }

  await ctx.close();
  await browser.close();

  if (errors.length) {
    console.log(`\n${errors.length} console error(s):`);
    errors.slice(0, 10).forEach((e) => console.log(`  ${e.slice(0, 200)}`));
    process.exit(1);
  }
  console.log('\nno console errors');
};

main().catch((err) => {
  console.error('capture failed:', err.message);
  process.exit(1);
});
