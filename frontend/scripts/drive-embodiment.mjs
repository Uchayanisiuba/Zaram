/**
 * Drives the embodiment spike in a real browser.
 *
 * The MCP Playwright server wants a chromium build that will not download on
 * this connection; the package already in frontend/node_modules has one, so
 * this uses that with an explicit executablePath — the same route
 * drive-citations.mjs takes. Re-runnable.
 *
 * What it proves, in order:
 *   1. the renderer toggle actually swaps what is mounted
 *   2. the VRM loads, and every expression it carries is named in the console
 *      (a missing viseme must not be silently indistinguishable from a bug)
 *   3. each state renders, captured as a screenshot to compare by eye
 *   4. useEmbodimentState() resolves activity over locality
 *
 *   node scripts/drive-embodiment.mjs
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.ZARAM_URL || 'http://localhost:5173';
const SHOTS = 'scripts/drive-shots';

const log = [];
function step(n, s) {
  console.log(`\n[${n}] ${s}`);
}

async function main() {
  mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromium.executablePath(),
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleErrors = [];
  // A bare "Failed to load resource: 500" names nothing actionable, and the
  // avatar failing silently is exactly the thing this spike must not do. Keep
  // the URL and any uncaught exception alongside it.
  const badResponses = [];
  const pageErrors = [];
  const assetRequests = [];
  const chunkRequests = [];
  page.on('response', (r) => {
    if (r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`);
    if (r.url().includes('.vrm')) assetRequests.push(`${r.status()} ${r.url()}`);
    if (r.url().includes('VrmAvatar')) chunkRequests.push(`${r.status()} ${r.url()}`);
  });
  page.on('pageerror', (e) => pageErrors.push(e.message));
  page.on('console', (m) => {
    const t = m.text();
    if (t.includes('[embodiment]')) log.push(t);
    if (m.type() === 'error') consoleErrors.push(t);
  });

  step(1, 'Open the landing');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  const panel = page.locator('[data-testid="embodiment-spike-controls"]');
  await panel.waitFor({ timeout: 10000 });
  console.log('    spike panel present:', await panel.isVisible());

  step(2, 'Switch renderer to avatar');
  await page.getByRole('button', { name: 'avatar', exact: true }).click();
  // Wait for an artefact, never for the *absence* of one. "Loading avatar…" is
  // also absent in the instant before the component mounts, so waiting for it
  // to disappear passes immediately and measures the wrong moment — which is
  // exactly what it did, and made a working renderer look like a dead one.
  // A canvas, or a stated failure, are the only two real outcomes.
  await page.waitForFunction(
    () => !!document.querySelector('canvas') || document.body.innerText.includes('Avatar unavailable'),
    { timeout: 90000 },
  ).catch(() => console.log('    !! neither a canvas nor a failure after 90s'));

  // "No error on screen" is not evidence the avatar mounted — an adapter that
  // never rendered shows no error either. Assert the artefacts instead: a GL
  // canvas in the DOM, and a request for the model actually leaving.
  // Walk the chain so a break is located rather than guessed: did the store
  // take the preference, did the lazy chunk get fetched, did a canvas mount.
  console.log('    store preference:', await page.evaluate(() => localStorage.getItem('zaram.embodiment.renderer')));
  console.log('    VrmAvatar chunk fetched:', chunkRequests.length > 0, chunkRequests[0] ?? '');
  console.log('    <canvas> present:', await page.locator('canvas').count());
  console.log('    model requested:', assetRequests.length > 0, assetRequests[0] ?? '');

  const failed = await page.getByText('Avatar unavailable').count();
  console.log('    avatar failed to load:', failed > 0);
  if (failed > 0) {
    console.log('    reason:', await page.getByText('Avatar unavailable').first().innerText());
  }

  // The canvas mounts the instant the effect runs, which is well before 16 MB
  // has parsed. Waiting on the canvas alone measures the wrong moment for the
  // same reason the "Loading avatar…" wait did — poll for the load callback's
  // own output, which is the only signal that the VRM is actually in the scene.
  for (let i = 0; i < 120 && log.length === 0; i++) {
    if (await page.getByText('Avatar unavailable').count()) break;
    await page.waitForTimeout(500);
  }

  step(3, 'Expressions the model actually carries');
  for (const line of log) console.log(line.split('\n').map((l) => '    ' + l).join('\n'));
  if (log.length === 0) console.log('    !! nothing logged — the load callback never ran');

  step(4, 'Each state, captured');
  for (const state of ['idle', 'thinking', 'listening', 'speaking', 'swapping']) {
    await page.getByRole('button', { name: state, exact: true }).click();
    await page.waitForTimeout(700);
    const derived = await page.locator('text=useEmbodimentState()').innerText();
    console.log(`    ${state.padEnd(10)} -> ${derived.replace(/\s+/g, ' ')}`);
    await page.screenshot({ path: `${SHOTS}/embodiment-${state}.png` });
  }

  step(5, 'Locality only surfaces at rest');
  await page.getByRole('button', { name: 'idle', exact: true }).click();
  await page.getByRole('button', { name: 'cloud', exact: true }).click();
  await page.waitForTimeout(500);
  console.log('    idle + cloud  ->', (await page.locator('text=useEmbodimentState()').innerText()).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SHOTS}/embodiment-cloud.png` });

  await page.getByRole('button', { name: 'thinking', exact: true }).click();
  await page.waitForTimeout(500);
  console.log('    thinking+cloud->', (await page.locator('text=useEmbodimentState()').innerText()).replace(/\s+/g, ' '));

  step(6, 'Back to the orb');
  await page.getByRole('button', { name: 'orb', exact: true }).click();
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${SHOTS}/embodiment-orb.png` });

  console.log('\nconsole errors:', consoleErrors.length);
  for (const e of consoleErrors.slice(0, 8)) console.log('   ', e);
  console.log('failing requests:', badResponses.length);
  for (const e of badResponses.slice(0, 10)) console.log('   ', e);
  console.log('uncaught exceptions:', pageErrors.length);
  for (const e of pageErrors.slice(0, 6)) console.log('   ', e.split('\n')[0]);

  await browser.close();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
