/**
 * Drive the conversation surface end to end, in a real browser.
 *
 * M4's acceptance has been outstanding for four milestones — "no UI
 * walkthrough, the interface has never been driven" — because the Playwright
 * browser install kept failing on this connection. The MCP server wants a
 * chromium build that will not download here; the package in `node_modules`
 * already has one, so this uses that.
 *
 * The route is the recall demo, which is the closest-to-done and
 * least-verified asset in the repo:
 *
 *   ask something with a fact in it -> ask about it -> cited answer
 *   -> open the citation -> correct the fact -> ask again, answer changes
 *   -> open Activity and see the log
 *
 * Screenshots land in `scripts/drive-shots/`. Every step prints what it
 * actually observed, because the point is to report what the interface does,
 * not that a script ran.
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(__dirname, 'drive-shots');
mkdirSync(SHOTS, { recursive: true });

const BASE = process.env.ZARAM_URL ?? 'http://localhost:5173';
const log = (...a) => console.log(...a);
const step = (n, t) => log(`\n=== ${n}. ${t} ===`);

let shotN = 0;
async function shot(page, name) {
  const file = path.join(SHOTS, `${String(++shotN).padStart(2, '0')}-${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  log(`   [shot] ${path.basename(file)}`);
}

/** Wait for the reply to finish: the send button re-enables, or timeout. */
async function waitForReply(page, timeout = 120_000) {
  const started = Date.now();
  // The store flips `isStreaming`; the surface shows it by disabling input.
  await page.waitForTimeout(500);
  while (Date.now() - started < timeout) {
    const streaming = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="chat-streaming"]');
      if (el) return true;
      // Fall back to the disabled input, which is what the user sees.
      const input = document.querySelector('textarea, input[type="text"]');
      return input ? input.disabled : false;
    });
    if (!streaming) break;
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(1200); // let the last tokens paint
}

async function transcript(page) {
  return page.evaluate(() => document.body.innerText);
}

const consoleErrors = [];
const failedRequests = [];

async function main() {
  // Explicit executable: Playwright's default headless path wants
  // `chrome-headless-shell`, which is not downloaded here, while the full
  // chromium build is. The full binary runs headless perfectly well.
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromium.executablePath(),
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  page.on('requestfailed', (r) =>
    failedRequests.push(`${r.method()} ${r.url()} — ${r.failure()?.errorText}`),
  );

  step(1, 'Load the landing state');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  await shot(page, 'landing');
  const landingText = await transcript(page);
  log('   visible:', JSON.stringify(landingText.slice(0, 220).replace(/\s+/g, ' ')));

  step(2, 'Enter the conversation via the Orb');
  // The landing hint says "Click Orb to Chat". Find whatever is clickable at
  // the centre; the orb is a canvas or a div, so try a few routes.
  const orbHit = await page.evaluate(() => {
    const candidates = [
      '[data-testid="orb"]',
      'canvas',
      '[class*="orb" i]',
      '[class*="Orb"]',
    ];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      if (el) {
        const r = el.getBoundingClientRect();
        if (r.width > 20 && r.height > 20) return { sel, x: r.x + r.width / 2, y: r.y + r.height / 2 };
      }
    }
    return null;
  });
  if (orbHit) {
    log(`   orb found via ${orbHit.sel}`);
    await page.mouse.click(orbHit.x, orbHit.y);
  } else {
    log('   !! no orb element found; clicking viewport centre');
    await page.mouse.click(720, 450);
  }
  await page.waitForTimeout(1800);
  await shot(page, 'after-orb-click');

  const input = page.locator('textarea, input[type="text"]').first();
  const haveInput = await input.count();
  log(`   chat input present: ${haveInput > 0}`);
  if (!haveInput) {
    log('   !! could not reach the conversation surface — stopping here');
    await browser.close();
    return;
  }

  step(3, 'Tell Zaram a fact');
  await input.click();
  await input.fill('My day rate for Harbour Lane Studio is 425,000 naira.');
  await shot(page, 'typed-fact');
  await page.keyboard.press('Enter');
  await waitForReply(page);
  await shot(page, 'fact-stored');
  log('   reply:', JSON.stringify((await transcript(page)).slice(-400).replace(/\s+/g, ' ')));

  step(4, 'Ask about it — expect a cited answer');
  await input.click();
  await input.fill('What is my day rate for Harbour Lane?');
  await page.keyboard.press('Enter');
  await waitForReply(page);
  await shot(page, 'cited-answer');
  const answer = await transcript(page);
  log('   reply:', JSON.stringify(answer.slice(-600).replace(/\s+/g, ' ')));
  const mentions425 = /425|425,000/.test(answer);
  log(`   answer contains the stored figure: ${mentions425}`);

  step(5, 'Look for citations, and click one');
  const citations = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('button, [role="button"], a').forEach((el) => {
      const t = (el.innerText || '').trim();
      if (!t) return;
      if (/memory|source|recall|\[\d+\]|cited/i.test(t) || el.dataset.testid?.includes('source')) {
        out.push({ text: t.slice(0, 80), testid: el.dataset.testid ?? '' });
      }
    });
    return out;
  });
  log(`   citation-like elements: ${citations.length}`);
  citations.slice(0, 8).forEach((c) => log(`     - ${JSON.stringify(c.text)} ${c.testid}`));

  if (citations.length) {
    const clicked = await page.evaluate(() => {
      const el = [...document.querySelectorAll('button, [role="button"], a')].find((e) => {
        const t = (e.innerText || '').trim();
        return t && (/memory|source|recall/i.test(t) || e.dataset.testid?.includes('source'));
      });
      if (el) { el.click(); return (el.innerText || '').trim().slice(0, 60); }
      return null;
    });
    log(`   clicked: ${JSON.stringify(clicked)}`);
    await page.waitForTimeout(1500);
    await shot(page, 'citation-panel');
    const panel = await transcript(page);
    log('   panel text:', JSON.stringify(panel.slice(-500).replace(/\s+/g, ' ')));
  } else {
    log('   !! no citation affordance found in the reply');
  }

  step(6, 'Navigate the five nodes');
  for (const node of ['Work', 'Memory', 'Knowledge', 'Activity', 'Settings']) {
    const found = await page.evaluate((label) => {
      const el = [...document.querySelectorAll('button, [role="button"], a, div')].find(
        (e) => (e.innerText || '').trim() === label,
      );
      if (el) { el.click(); return true; }
      return false;
    }, node);
    await page.waitForTimeout(1400);
    const body = await transcript(page);
    log(`   ${node}: reachable=${found} — ${JSON.stringify(body.slice(0, 160).replace(/\s+/g, ' '))}`);
    await shot(page, `node-${node.toLowerCase()}`);
  }

  step(7, 'Console errors and failed requests');
  log(`   console errors: ${consoleErrors.length}`);
  consoleErrors.slice(0, 10).forEach((e) => log(`     ! ${e.slice(0, 200)}`));
  log(`   failed requests: ${failedRequests.length}`);
  failedRequests.slice(0, 10).forEach((r) => log(`     ! ${r.slice(0, 200)}`));

  await browser.close();
  log('\ndone.');
}

main().catch((err) => {
  console.error('DRIVE FAILED:', err);
  process.exit(1);
});
