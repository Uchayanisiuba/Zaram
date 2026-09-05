/**
 * The artifact preview covers the orb, and stops where the conversation begins.
 *
 * Geometry, measured, because "over the orb area" is a claim about pixels and
 * the alternative is looking at a screenshot and believing it. The panel is
 * resizable, so the check is done at two different divider positions — a
 * hardcoded 55% would pass at the default and be wrong everywhere else, which
 * is exactly the failure this measures against.
 *
 * Needs an artifact to exist. Skips with a clear message rather than failing if
 * the Spine has none, because "no documents generated yet" is an ordinary state
 * of a fresh machine and not a defect in the preview.
 *
 *   node scripts/probe-preview-geometry.mjs
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

async function main() {
  mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  console.log('\n[1] Find a generated document');
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // Work lists every artifact, which is a more reliable way to reach one than
  // hoping the current conversation happens to contain a file card.
  const work = page.getByRole('button', { name: /^Work$/ }).first();
  if (await work.count()) {
    await work.click({ force: true });
    await page.waitForTimeout(1500);
  }

  let preview = page.getByRole('button', { name: /^Preview$/ }).first();
  if ((await preview.count()) === 0) {
    console.log('  no generated document on this machine — nothing to preview.');
    console.log('  Generate one (ask Zaram for an invoice) and re-run.');
    await browser.close();
    return;
  }

  console.log('\n[2] Open it, and measure against the conversation panel');
  await preview.click({ force: true });
  await page.waitForTimeout(900);

  const geometry = async () => {
    const overlay = await page.getByRole('dialog', { name: /Preview of/ }).boundingBox();
    // The conversation panel is the fixed, right-anchored surface.
    const panel = await page
      .locator('div')
      .filter({ has: page.getByLabel('Message Zaram') })
      .last()
      .boundingBox();
    return { overlay, panel };
  };

  let { overlay, panel } = await geometry();
  check('the preview is open', Boolean(overlay));
  check(
    'it starts at the left edge, where the orb is',
    overlay !== null && overlay.x <= 1,
    overlay ? `x=${overlay.x.toFixed(1)}` : '',
  );
  check(
    'it does not reach across the conversation',
    overlay !== null && panel !== null && overlay.x + overlay.width <= panel.x + 1,
    overlay && panel
      ? `preview ends ${(overlay.x + overlay.width).toFixed(0)}px, panel starts ${panel.x.toFixed(0)}px`
      : '',
  );
  await page.screenshot({ path: `${SHOTS}/preview-over-orb.png` });

  console.log('\n[3] Drag the divider, and measure again');
  // The width is derived from the same fraction the panel and the orb offset
  // use. If it were hardcoded this is where it would break.
  await page.evaluate(() => {
    const raw = localStorage.getItem('zaram.layout');
    const parsed = raw ? JSON.parse(raw) : { state: {}, version: 0 };
    parsed.state = { ...parsed.state, chatFraction: 0.62 };
    localStorage.setItem('zaram.layout', JSON.stringify(parsed));
  });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1800);

  if (await page.getByRole('button', { name: /^Work$/ }).count()) {
    await page.getByRole('button', { name: /^Work$/ }).first().click({ force: true });
    await page.waitForTimeout(1200);
  }
  preview = page.getByRole('button', { name: /^Preview$/ }).first();
  if (await preview.count()) {
    await preview.click({ force: true });
    await page.waitForTimeout(900);
    ({ overlay, panel } = await geometry());
    check(
      'it still stops at the panel after the divider moved',
      overlay !== null && panel !== null && overlay.x + overlay.width <= panel.x + 1,
      overlay && panel
        ? `preview ends ${(overlay.x + overlay.width).toFixed(0)}px, panel starts ${panel.x.toFixed(0)}px`
        : '',
    );
    await page.screenshot({ path: `${SHOTS}/preview-over-orb-wide-panel.png` });
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  await browser.close();
  if (failed) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
