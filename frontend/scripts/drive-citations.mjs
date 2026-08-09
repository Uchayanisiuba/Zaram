/**
 * Drive the citation UI in a real browser — chips, summary line, panel.
 *
 * Step 3–5 of `docs/UI-SPEC.md` → Citations. Everything real this project has
 * found came from driving the live kernel rather than from unit tests, and the
 * citation backend has never been rendered, so this checks what the *user*
 * sees:
 *
 *   ask something with a fact in it -> ask about it -> chips appear on the reply
 *   -> the summary line leads with the egress split
 *   -> the panel groups by egress and quotes the passage
 *   -> the empty state says so when nothing was used
 *
 * Reports what it observed. A script that ran is not the same as a feature
 * that works.
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
  const file = path.join(SHOTS, `cite-${String(++shotN).padStart(2, '0')}-${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  log(`   [shot] ${path.basename(file)}`);
}

async function waitForReply(page, timeout = 180_000) {
  const started = Date.now();
  await page.waitForTimeout(600);
  while (Date.now() - started < timeout) {
    const streaming = await page.evaluate(() => {
      const input = document.querySelector('textarea, input[type="text"]');
      return input ? input.disabled : false;
    });
    if (!streaming) break;
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(1500);
}

async function ask(page, text) {
  const input = page.locator('textarea, input[type="text"]').first();
  await input.fill(text);
  await input.press('Enter');
  await waitForReply(page);
}

const consoleErrors = [];

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromium.executablePath(),
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });

  step(1, 'Open the conversation');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  // The orb is a canvas or a div depending on the surface, so click whatever
  // is clickable at the centre — the same route drive-conversation.mjs uses.
  const orbHit = await page.evaluate(() => {
    // `orb-tap` is the actual hit target — the orb itself is a decorative
    // image stack and is not the thing that carries the click.
    for (const sel of ['[data-testid="orb-tap"]', '[data-testid="orb"]', 'canvas', '[class*="orb" i]']) {
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
    await page.mouse.click(720, 450);
  }
  await page.waitForTimeout(1800);
  await shot(page, 'conversation');

  step(2, 'The project scope picker is present (rule 7i)');
  const picker = page.locator('#project-scope');
  log(`   picker present: ${(await picker.count()) > 0}`);
  if (await picker.count()) {
    log(`   options: ${JSON.stringify(await picker.locator('option').allTextContents())}`);
  }

  step(3, 'State a fact');
  await ask(page, 'My day rate for Harbour Lane is 425,000 naira.');
  await shot(page, 'fact-stated');

  step(4, 'Ask about it — chips and the summary line');
  await ask(page, 'What is my Harbour Lane day rate?');
  await shot(page, 'cited-reply');

  const summary = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button')];
    const hit = btns.find((b) => /\d+ sources?/.test(b.textContent ?? ''));
    return hit ? hit.textContent.trim() : null;
  });
  log(`   summary line: ${summary ? JSON.stringify(summary) : 'NOT FOUND'}`);

  const chips = await page.evaluate(() =>
    [...document.querySelectorAll('button[aria-label^="Source "]')].map((b) => ({
      label: b.getAttribute('aria-label'),
      colour: getComputedStyle(b).color,
    })),
  );
  log(`   chips: ${chips.length}`);
  chips.forEach((c) => log(`     ${c.label}  colour=${c.colour}`));

  step(5, 'Open the panel — grouped by egress');
  if (summary) {
    await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button')];
      const hit = btns.find((b) => /\d+ sources?/.test(b.textContent ?? ''));
      hit?.click();
    });
    await page.waitForTimeout(700);
    await shot(page, 'panel-open');

    const panel = await page.evaluate(() => {
      const el = document.querySelector('[role="dialog"][aria-label="Sources for this reply"]');
      return el ? el.innerText : null;
    });
    log(panel ? `   panel text:\n${panel.split('\n').map((l) => '     ' + l).join('\n')}` : '   PANEL NOT FOUND');

    step(6, 'Escape closes it');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    const stillOpen = await page.evaluate(
      () => !!document.querySelector('[role="dialog"][aria-label="Sources for this reply"]'),
    );
    log(`   closed on Escape: ${!stillOpen}`);
  }

  step(7, 'The empty state — a question nothing in the Spine answers');
  await ask(page, 'What is the capital of France?');
  await shot(page, 'empty-state');
  const empty = await page.evaluate(() =>
    document.body.innerText.includes('Answered from the model’s own knowledge'),
  );
  log(`   "nothing from your files" shown: ${empty}`);

  step(8, 'Console errors');
  log(consoleErrors.length ? consoleErrors.map((e) => '   ' + e).join('\n') : '   none');

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
