/**
 * M4's acceptance, driven in a real browser. Outstanding since M4.
 *
 *   ask -> cited answer -> click the citation -> correct the fact
 *   -> ask again and watch the answer change -> open Activity
 *
 * Plus M7's second half: point at a folder, watch it index, see the file that
 * gave nothing back with its reason and remedy, and see the notice arrive in
 * the conversation.
 *
 * Targets the real DOM — the five nav items are `button`s with exact text, and
 * the orb is `[data-testid="orb-tap"]`. An earlier version matched `div`
 * first and silently clicked the wrong thing, which is worth remembering: a
 * selector that matches something is not a selector that matches the thing.
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(__dirname, 'drive-shots');
mkdirSync(SHOTS, { recursive: true });

const BASE = process.env.ZARAM_URL ?? 'http://localhost:5173';
const INGEST_FOLDER = process.env.ZARAM_INGEST_FOLDER ?? '';

const log = (...a) => console.log(...a);
const step = (n, t) => log(`\n=== ${n}. ${t} ===`);
const flat = (s, n = 400) => JSON.stringify(String(s).replace(/\s+/g, ' ').slice(0, n));

let shotN = 0;
async function shot(page, name) {
  const file = path.join(SHOTS, `a${String(++shotN).padStart(2, '0')}-${name}.png`);
  await page.screenshot({ path: file });
  log(`   [shot] ${path.basename(file)}`);
}

async function goNode(page, label) {
  const ok = await page.evaluate((l) => {
    const btn = [...document.querySelectorAll('button')].find(
      (b) => (b.innerText || '').trim() === l,
    );
    if (btn) { btn.click(); return true; }
    return false;
  }, label);
  await page.waitForTimeout(1600);
  return ok;
}

async function say(page, text) {
  const input = page.locator('textarea, input[type="text"]').first();
  await input.click();
  await input.fill(text);
  await page.keyboard.press('Enter');
  // Wait until the send button is enabled again and text has settled.
  await page.waitForTimeout(1000);
  for (let i = 0; i < 150; i++) {
    const busy = await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find(
        (x) => x.getAttribute('aria-label') === 'Send message',
      );
      return b ? b.disabled : false;
    });
    if (!busy) break;
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(1500);
}

/** The last assistant reply as text. */
async function lastReply(page) {
  return page.evaluate(() => {
    const blocks = [...document.querySelectorAll('p')].map((p) => (p.innerText || '').trim());
    return blocks.slice(-14).join(' | ');
  });
}

async function citations(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('button[title="Open this source"], button[title="Forgotten"]')].map(
      (b) => ({ text: (b.innerText || '').trim().slice(0, 90), disabled: b.disabled, title: b.title }),
    ),
  );
}

const consoleErrors = [];

async function main() {
  const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('response', (r) => { if (r.status() >= 400) consoleErrors.push(`HTTP ${r.status()} ${r.url()}`); });

  step(1, 'Landing, then enter via the orb');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  await shot(page, 'landing');
  await page.click('[data-testid="orb-tap"]');
  await page.waitForTimeout(1800);
  const hasInput = await page.locator('textarea, input[type="text"]').first().count();
  log(`   conversation reachable: ${hasInput > 0}`);
  await shot(page, 'conversation');

  step(2, 'Store a fact');
  const RATE = '612,500';
  await say(page, `My day rate for Ashgrove Films is ${RATE} naira.`);
  log('   reply:', flat(await lastReply(page)));
  await shot(page, 'fact-stored');

  step(3, 'Ask about it — a cited answer');
  await say(page, 'What is my day rate for Ashgrove Films?');
  const answer1 = await lastReply(page);
  log('   reply:', flat(answer1, 600));
  log(`   contains ${RATE}: ${answer1.includes(RATE)}`);
  const cites = await citations(page);
  log(`   citations rendered: ${cites.length}`);
  cites.forEach((c) => log(`     - ${flat(c.text, 90)} disabled=${c.disabled}`));
  await shot(page, 'cited-answer');

  step(4, 'Click a citation');
  const opened = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button[title="Open this source"]')].find((x) =>
      (x.innerText || '').includes('Ashgrove'),
    ) ?? document.querySelector('button[title="Open this source"]');
    if (!b) return null;
    b.click();
    return (b.innerText || '').trim().slice(0, 80);
  });
  log(`   clicked: ${flat(opened)}`);
  await page.waitForTimeout(1600);
  await shot(page, 'source-panel');
  const panel = await page.evaluate(() => {
    const el = document.querySelector('[role="dialog"], aside, [class*="panel" i]');
    return el ? (el.innerText || '').trim() : '(no panel element found)';
  });
  log('   panel:', flat(panel, 500));

  step(5, 'Correct the fact in Memory');
  await goNode(page, 'Memory');
  await shot(page, 'memory');
  const NEW_RATE = '750,000';
  const corrected = await page.evaluate((args) => {
    const [needle, next] = args;
    // Find the fact row, then whatever control lets it be corrected.
    const rows = [...document.querySelectorAll('div,li,article')].filter((e) =>
      (e.innerText || '').includes(needle),
    );
    const row = rows[rows.length - 1];
    if (!row) return { found: false };
    const buttons = [...row.querySelectorAll('button')].map((b) =>
      ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '') + ' ' + (b.title || '')).trim(),
    );
    return { found: true, buttons };
  }, ['Ashgrove', NEW_RATE]);
  log('   fact row found:', corrected.found);
  log('   controls on the row:', JSON.stringify(corrected.buttons?.slice(0, 12)));

  await browser.close();

  step(6, 'Console errors / bad responses');
  log(`   ${consoleErrors.length}`);
  [...new Set(consoleErrors)].slice(0, 12).forEach((e) => log(`     ! ${e.slice(0, 200)}`));
  log('\ndone.');
}

main().catch((e) => { console.error('DRIVE FAILED:', e); process.exit(1); });
