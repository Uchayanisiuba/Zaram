/**
 * The composer's controls do not overlap, and a message can be copied.
 *
 * Written from a reported defect that only appeared on hover, which is the
 * kind a screenshot at rest cannot show and a jsdom test cannot see at all.
 * The mic and send buttons each positioned themselves with their own `right-*`
 * offset — 8–36px and 36–64px — so they were adjacent with a gap of exactly
 * zero, and `whileHover={{ scale: 1.05 }}` grew whichever one the pointer was
 * over into its neighbour.
 *
 * So this measures **geometry, hovered**, which is the only state the bug
 * exists in. Numbers from `getBoundingClientRect`, not from reading the CSS.
 *
 *   node scripts/drive-composer.mjs
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.ZARAM_URL || 'http://localhost:5173';
const SHOTS = 'scripts/drive-shots';

const results = [];
const check = (name, ok, detail = '') => {
  results.push({ ok });
  console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
};

/** Both control boxes, in viewport pixels. */
const boxes = async (page) => {
  const mic = await page.getByLabel(/Record a message|Stop recording|Transcribing/).first().boundingBox();
  const send = await page.getByLabel('Send message').boundingBox();
  return { mic, send };
};

const overlap = (a, b) =>
  a && b ? Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) : null;

async function main() {
  mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  console.log('\n[1] Open the conversation');
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await page.getByTestId('orb-tap').click({ force: true });
  await page.waitForTimeout(1200);

  const input = page.getByLabel('Message Zaram');
  check('the composer is present', (await input.count()) > 0);

  console.log('\n[2] At rest');
  let { mic, send } = await boxes(page);
  check('both controls are rendered', Boolean(mic && send), mic && send ? '' : 'one is missing');
  const restGap = mic && send ? mic.x + mic.width <= send.x + 0.5 : false;
  check(
    'the mic sits entirely left of send, with a gap',
    restGap,
    mic && send ? `gap ${(send.x - (mic.x + mic.width)).toFixed(1)}px` : '',
  );

  console.log('\n[3] Hovered — the state the defect lived in');
  await page.getByLabel('Send message').hover({ force: true });
  await page.waitForTimeout(500);
  ({ mic, send } = await boxes(page));
  const hoveredOverlap = overlap(mic, send);
  check(
    'hovering send does not push it under the mic',
    hoveredOverlap !== null && hoveredOverlap <= 0,
    `overlap ${hoveredOverlap?.toFixed(1)}px`,
  );

  await page.getByLabel(/Record a message|Stop recording|Transcribing/).first().hover({ force: true });
  await page.waitForTimeout(500);
  ({ mic, send } = await boxes(page));
  const micHoverOverlap = overlap(mic, send);
  check(
    'hovering the mic does not push it over send',
    micHoverOverlap !== null && micHoverOverlap <= 0,
    `overlap ${micHoverOverlap?.toFixed(1)}px`,
  );

  console.log('\n[4] Neither control covers the text');
  await input.fill('A reasonably long message typed all the way along the composer to the end');
  await page.waitForTimeout(300);
  const inputBox = await input.boundingBox();
  ({ mic } = await boxes(page));
  // The input's right padding must clear the leftmost control, or the caret
  // runs underneath it — the reason `pr-16` became `pr-20`.
  const padding = await input.evaluate((el) => parseFloat(getComputedStyle(el).paddingRight));
  const controlsWidth = inputBox && mic ? inputBox.x + inputBox.width - mic.x : 0;
  check(
    'the input reserves room for both controls',
    padding >= controlsWidth,
    `padding ${padding}px vs controls ${controlsWidth.toFixed(1)}px`,
  );
  await page.screenshot({ path: `${SHOTS}/composer-hovered.png` });

  console.log('\n[5] A message carries a copy control');
  await input.fill('Say the single word: ping');
  await input.press('Enter');
  // The user's own message is in the list immediately; no need to wait for a
  // reply, which would make this test depend on a local model being warm.
  await page.waitForTimeout(1500);
  const copyButtons = await page.getByRole('button', { name: /Copy this message/ }).count();
  check('copy is offered while a reply is still streaming', copyButtons > 0, `${copyButtons} found`);

  // Retry is deliberately withheld mid-stream — it would race the request in
  // flight — so checking for it straight after sending measured the wrong
  // moment and reported a working control as missing. Wait for the reply to
  // finish. Generous, because this is a cold local model on a real machine and
  // the alternative is a test that fails on a slow morning.
  await page
    .getByRole('button', { name: 'Ask again' })
    .first()
    .waitFor({ timeout: 120000 })
    .catch(() => {});
  const retry = await page.getByRole('button', { name: 'Ask again' }).count();
  check('ask-again appears once the reply is done', retry > 0, `${retry} found`);

  // No thumbs, ever — rule 7f. Asserted rather than trusted, because this is
  // the row where every other product puts them and the pressure to add one
  // arrives with the next person who compares Zaram to ChatGPT.
  const thumbs = await page.getByRole('button', { name: /thumbs|helpful|Good response|Bad response/i }).count();
  check('no thumbs-up/down feedback control exists', thumbs === 0);

  await page.screenshot({ path: `${SHOTS}/message-actions.png` });

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  await browser.close();
  if (failed) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
