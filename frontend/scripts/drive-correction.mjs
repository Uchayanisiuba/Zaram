/**
 * The rest of M4's acceptance: correct a fact and watch the answer change.
 *
 * Plus Activity (the egress log) and Knowledge (M7's second half), so the five
 * nodes are all actually opened rather than assumed.
 *
 * The Memory controls live inside an *expanded* row — an earlier probe found
 * "no controls" because it never clicked the fact open. Worth remembering: a
 * selector that finds nothing is as often the script's fault as the app's.
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(__dirname, 'drive-shots');
mkdirSync(SHOTS, { recursive: true });

const BASE = process.env.ZARAM_URL ?? 'http://localhost:5173';
const FOLDER = process.env.ZARAM_INGEST_FOLDER ?? '';

const log = (...a) => console.log(...a);
const step = (n, t) => log(`\n=== ${n}. ${t} ===`);
const flat = (s, n = 420) => JSON.stringify(String(s).replace(/\s+/g, ' ').slice(0, n));

let shotN = 0;
async function shot(page, name) {
  const f = path.join(SHOTS, `c${String(++shotN).padStart(2, '0')}-${name}.png`);
  await page.screenshot({ path: f });
  log(`   [shot] ${path.basename(f)}`);
}

async function goNode(page, label) {
  // By accessible name, not innerText: the left rail hides its labels when
  // collapsed, so matching on visible text found nothing from inside a
  // workspace even though the button was right there.
  const ok = await page.evaluate((l) => {
    const byName = [...document.querySelectorAll('button')].find(
      (x) => (x.getAttribute('aria-label') || '').trim() === l);
    const byText = [...document.querySelectorAll('button')].find(
      (x) => (x.innerText || '').trim() === l);
    const b = byName ?? byText;
    if (b) { b.click(); return true; }
    return false;
  }, label);
  await page.waitForTimeout(1800);
  return ok;
}

async function say(page, text) {
  const input = page.locator('textarea, input[type="text"]').first();
  await input.click();
  await input.fill(text);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(1000);
  for (let i = 0; i < 150; i++) {
    const busy = await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find(
        (x) => x.getAttribute('aria-label') === 'Send message');
      return b ? b.disabled : false;
    });
    if (!busy) break;
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(1500);
}


/** Return to the conversation. Inside a workspace this is the OrbStatus in the
 *  header, not the landing orb — `orb-tap` only exists on the landing. */
async function toConversation(page) {
  const ok = await page.evaluate(() => {
    const o = [...document.querySelectorAll('button,[role="button"]')].find((b) =>
      (b.getAttribute('aria-label') || '').includes('Open conversation'));
    if (o) { o.click(); return true; }
    const t = document.querySelector('[data-testid="orb-tap"]');
    if (t) { t.click(); return true; }
    return false;
  });
  await page.waitForTimeout(1800);
  return ok;
}

const problems = [];

async function main() {
  const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  page.on('console', (m) => { if (m.type() === 'error') problems.push(m.text()); });
  page.on('response', (r) => { if (r.status() >= 400) problems.push(`HTTP ${r.status()} ${r.url()}`); });

  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2500);
  await page.click('[data-testid="orb-tap"]');
  await page.waitForTimeout(1800);

  const CLIENT = 'Ashgrove Films';
  const OLD = '612,500';
  const NEW = '750,000';

  step(1, `Ask before correcting — expect ${OLD}`);
  await say(page, `What is my day rate for ${CLIENT}?`);
  const before = await page.evaluate(() => document.body.innerText);
  log(`   answer mentions ${OLD}: ${before.includes(OLD)}`);
  log('   tail:', flat(before.slice(-320)));

  step(2, 'Open Memory and expand the fact');
  await goNode(page, 'Memory');
  const expanded = await page.evaluate((needle) => {
    const rows = [...document.querySelectorAll('div,li,article')].filter((e) => {
      const t = (e.innerText || '');
      return t.includes(needle) && t.length < 400;
    });
    const row = rows[rows.length - 1];
    if (!row) return false;
    row.click();
    return true;
  }, CLIENT);
  await page.waitForTimeout(1200);
  log(`   fact row expanded: ${expanded}`);
  await shot(page, 'memory-expanded');

  const controls = await page.evaluate(() =>
    [...document.querySelectorAll('button')].map((b) => (b.innerText || '').trim()).filter(Boolean));
  log('   buttons now visible:', JSON.stringify(controls.slice(0, 20)));

  step(3, 'Correct it');
  const clickedCorrect = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find((x) => (x.innerText || '').trim() === 'Correct');
    if (b) { b.click(); return true; }
    return false;
  });
  log(`   Correct clicked: ${clickedCorrect}`);
  await page.waitForTimeout(1000);
  await shot(page, 'correction-editor');

  if (clickedCorrect) {
    const box = page.locator('textarea').last();
    await box.click();
    await box.fill(`My day rate for ${CLIENT} is ${NEW} naira.`);
    await page.waitForTimeout(400);
    const saved = await page.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find((x) =>
        /^(save|save correction|correct)$/i.test((x.innerText || '').trim()));
      if (b) { b.click(); return (b.innerText || '').trim(); }
      return null;
    });
    log(`   saved via: ${flat(saved)}`);
    await page.waitForTimeout(2500);
    await shot(page, 'after-correction');
    const memText = await page.evaluate(() => document.body.innerText);
    log(`   old value still shown struck through: ${memText.includes(OLD)}`);
    log(`   new value present: ${memText.includes(NEW)}`);
  }

  step(4, 'Ask again — the answer must change');
  log(`   back to conversation: ${await toConversation(page)}`);
  await say(page, `Remind me, what is my day rate for ${CLIENT}?`);
  const after = await page.evaluate(() => document.body.innerText);
  const tail = after.slice(-500);
  log('   tail:', flat(tail, 500));
  log(`   answer now mentions ${NEW}: ${tail.includes(NEW)}`);
  log(`   answer still mentions ${OLD}: ${tail.includes(OLD)}`);
  await shot(page, 'answer-changed');

  step(5, 'Activity — the egress log');
  const act = await goNode(page, 'Activity');
  const activity = await page.evaluate(() => document.body.innerText);
  log(`   reachable: ${act}`);
  log('   content:', flat(activity, 500));
  await shot(page, 'activity');

  step(6, 'Knowledge — M7 second half');
  const kn = await goNode(page, 'Knowledge');
  log(`   reachable: ${kn}`);
  await shot(page, 'knowledge-empty');
  log('   content:', flat(await page.evaluate(() => document.body.innerText), 400));

  if (FOLDER) {
    const input = page.locator('[data-testid="ingest-path"]');
    if (await input.count()) {
      await input.click();
      await input.fill(FOLDER);
      await page.click('[data-testid="ingest-start"]');
      log('   indexing…');
      for (let i = 0; i < 120; i++) {
        const done = await page.evaluate(() => !document.querySelector('[data-testid="ingest-progress"]'));
        if (done && i > 2) break;
        await page.waitForTimeout(500);
      }
      await page.waitForTimeout(2000);
      await shot(page, 'knowledge-indexed');
      const kText = await page.evaluate(() => document.body.innerText);
      log('   after indexing:', flat(kText, 900));

      const reasons = await page.evaluate(() =>
        [...document.querySelectorAll('[data-testid^="reason-"]')].map((e) => e.innerText.trim()));
      const remedies = await page.evaluate(() =>
        [...document.querySelectorAll('[data-testid^="remedy-"]')].map((e) => e.innerText.trim()));
      log(`   reasons shown: ${reasons.length}`);
      reasons.forEach((r) => log(`     - ${flat(r, 160)}`));
      log(`   remedies shown: ${remedies.length}`);
      remedies.forEach((r) => log(`     - ${flat(r, 160)}`));

      step(7, 'Back to chat — the notice should arrive once');
      log(`   back to conversation: ${await toConversation(page)}`);
      await say(page, 'What do you know about my invoices?');
      const notices = await page.evaluate(() =>
        [...document.querySelectorAll('[data-testid="chat-notice"]')].map((e) => e.innerText.trim()));
      log(`   notices in the transcript: ${notices.length}`);
      notices.forEach((n) => log(`     * ${flat(n, 300)}`));
      await shot(page, 'chat-notice');

      await say(page, 'And what are my payment terms?');
      const again = await page.evaluate(() =>
        [...document.querySelectorAll('[data-testid="chat-notice"]')].map((e) => e.innerText.trim()));
      log(`   notices after a second question: ${again.length} (must not grow)`);
      await shot(page, 'chat-notice-once');
    } else {
      log('   !! ingest input not found on Knowledge');
    }
  } else {
    log('   (ZARAM_INGEST_FOLDER not set — skipping the ingest drive)');
  }

  step(8, 'Errors');
  const unique = [...new Set(problems)];
  log(`   ${unique.length}`);
  unique.slice(0, 15).forEach((p) => log(`     ! ${p.slice(0, 200)}`));

  await browser.close();
  log('\ndone.');
}

main().catch((e) => { console.error('DRIVE FAILED:', e); process.exit(1); });
