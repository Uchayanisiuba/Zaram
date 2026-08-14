/**
 * Every reply says which model answered, and whether it left the machine.
 *
 * `CLAUDE.md` has required this for as long as routing has existed — *"Every
 * reply names the model that answered and why"*, *"Never hide the model"* —
 * and nothing did it. The cost was reported rather than theorised: the
 * maintainer connected a cloud provider and had no way to tell whether any
 * reply had ever reached it.
 *
 * Driven in a real browser rather than asserted in jsdom, because the failure
 * this guards against is *the line does not render*. The store can hold a
 * correct attribution, the parser can emit a correct event, every unit test
 * can pass, and the element can be absent — that exact shape has now cost this
 * project ten times, and the pointer-gaze lesson is the same one twice: the
 * maths had unit tests and nothing had looked at the screen.
 *
 * Needs the backend on 8420 and the frontend on 5173. It sends a real message,
 * so a local model answers and this takes as long as a reply takes.
 *
 *   node scripts/drive-attribution.mjs
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
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromium.executablePath(),
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  console.log('\n[1] Open the conversation');
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  await page.getByTestId('orb-tap').click({ force: true });
  await page.waitForTimeout(1200);

  const input = page.getByLabel('Message Zaram');
  check('the composer is present', (await input.count()) > 0);

  console.log('\n[2] Ask something short, and watch what the reply says about itself');
  await input.fill('Reply with exactly the word: alive');
  await page.keyboard.press('Enter');

  // The attribution is sent before the first token, so it should appear well
  // before the answer does. Waited for by content rather than by a fixed sleep:
  // a cold model can take a while and a warm one is immediate.
  const attribution = page.getByTestId('answered-by').first();
  let appeared = false;
  try {
    await attribution.waitFor({ state: 'visible', timeout: 180000 });
    appeared = true;
  } catch {
    appeared = false;
  }
  check('the reply names what answered it', appeared);

  let text = '';
  if (appeared) {
    text = (await attribution.innerText()).trim();
    console.log(`        "${text}"`);
  }

  check('it names a model', /\w/.test(text) && text.length > 0, text);
  // One of the two sentences, in words. A colour cannot make this distinction
  // and `OrbStatusLabel` already argues why it must not try.
  check(
    'it says in words whether the request left the device',
    /on this machine|left this device/.test(text),
    text,
  );

  console.log('\n[3] The answer arrives underneath it');
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `${SHOTS}/answered-by.png` });
  console.log(`        wrote ${SHOTS}/answered-by.png`);

  await browser.close();

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed\n`);
  process.exit(failed ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
