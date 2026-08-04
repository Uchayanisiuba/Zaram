/**
 * Capture the Memory surface, including a real correction.
 *
 * Drives the actual controls rather than seeding the database, so what is
 * captured is what a user would get. Backend (8420) and dev server (5173) must
 * both be running.
 *
 *   node scripts/capture-memory.mjs
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
  // regression guard.
  await ctx.route('**fonts.googleapis.com**', (r) => r.abort());
  await ctx.route('**fonts.gstatic.com**', (r) => r.abort());
  await ctx.addInitScript(() => {
    try { localStorage.clear(); } catch { /* nothing stored yet */ }
  });

  const page = await ctx.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto(APP, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1400);

  // force: the orbital nodes animate continuously, so "stable" never arrives.
  await page.getByRole('button', { name: /Memory/ }).first().click({ force: true });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, 'memory-list.png'), timeout: 15000 });
  console.log('  captured memory-list.png');

  const firstRow = page.locator('ul > li button').first();
  if (!(await firstRow.count())) {
    console.log('  Spine is empty — nothing to correct. Store a fact first.');
    await ctx.close();
    await browser.close();
    return;
  }

  await firstRow.click({ force: true });
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(OUT, 'memory-actions.png'), timeout: 15000 });
  console.log('  captured memory-actions.png');

  // Drive a real correction through the real endpoint.
  const correct = page.getByRole('button', { name: /^Correct$/ });
  if (await correct.count()) {
    await correct.first().click({ force: true });
    await page.waitForTimeout(400);
    const box = page.getByLabel('Corrected fact');
    await box.fill('The launch is 14 November 2027 in Bristol.');
    await page.screenshot({ path: path.join(OUT, 'memory-correcting.png'), timeout: 15000 });
    console.log('  captured memory-correcting.png');

    await page.getByRole('button', { name: /Save correction/ }).click({ force: true });
    await page.waitForTimeout(1800);
    await page.screenshot({ path: path.join(OUT, 'memory-superseded.png'), timeout: 15000 });
    console.log('  captured memory-superseded.png');
  } else {
    console.log('  no Correct button — the first row may already be superseded');
  }

  await ctx.close();
  await browser.close();

  if (errors.length) {
    console.log(`\n${errors.length} console error(s):`);
    errors.slice(0, 8).forEach((e) => console.log(`  ${e.slice(0, 180)}`));
  } else {
    console.log('\nno console errors');
  }
};

main().catch((err) => {
  console.error('capture failed:', err.message);
  process.exit(1);
});
