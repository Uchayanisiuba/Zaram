/**
 * Drives the Settings screen in a real browser and captures what it looks like.
 *
 * Both the backend and the dev server must already be running.
 *
 * Why this exists rather than another jsdom test: the screen's whole job is to
 * report the running system, so every interesting failure is a wiring failure —
 * a route not proxied, a field named differently on the wire, a control that
 * renders and saves nothing. jsdom mocks `fetch`, so it can see none of them.
 * This repo has now been bitten five times by a feature whose tests passed and
 * which could not happen; twice this week.
 *
 * It asserts, and it also screenshots, because those answer different
 * questions. The assertions say the controls reached the backend. The
 * screenshots are for a person to look at, which is the check that caught the
 * avatar gate blocking the avatar when twelve unit tests did not.
 *
 *   node scripts/drive-settings.mjs
 */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = process.env.ZARAM_URL || 'http://localhost:5173';
const SHOTS = 'scripts/drive-shots';

const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
};

async function main() {
  mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromium.executablePath(),
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

  const failedRequests = [];
  const consoleErrors = [];
  // A route missing from the Vite proxy answers 200 with index.html, so a
  // status check alone would not catch it. Record what came back as well.
  const apiResponses = [];
  page.on('response', async (r) => {
    const url = r.url();
    if (r.status() >= 400) failedRequests.push(`${r.status()} ${url}`);
    if (/\/(providers|routing|egress)\b/.test(url)) {
      apiResponses.push({
        url: url.replace(BASE, ''),
        status: r.status(),
        type: r.headers()['content-type'] ?? '',
      });
    }
  });
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });

  console.log('\n[1] Open Settings');
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // The rail's button, not a URL: this app has no routing, and reaching the
  // surface the way a user does is the point of driving it.
  const settings = page.getByRole('button', { name: /^Settings$/ }).first();
  await settings.click({ force: true });
  await page.waitForTimeout(2500);

  const heading = await page.getByRole('heading', { name: 'Settings' }).count();
  check('the Settings surface opens', heading > 0);

  console.log('\n[2] The backend answered, and with JSON');
  const html = apiResponses.filter((r) => r.type.includes('text/html'));
  check(
    'every settings API call returned JSON, not the SPA shell',
    html.length === 0,
    html.length ? `HTML from ${html.map((r) => r.url).join(', ')}` : `${apiResponses.length} calls`,
  );
  check(
    'no failing requests',
    failedRequests.length === 0,
    failedRequests.slice(0, 3).join(' · '),
  );

  console.log('\n[3] The catalogue reached the picker');
  const providerSelect = page.getByLabel('Provider', { exact: true });
  const optionCount = await providerSelect.locator('option').count();
  check('the provider list is populated', optionCount > 5, `${optionCount} options`);
  const claudeOption = await providerSelect
    .locator('option', { hasText: 'Claude' })
    .first()
    .textContent();
  check(
    'an unreachable provider is shown and labelled, not hidden',
    (claudeOption ?? '').includes('not reachable yet'),
    (claudeOption ?? '').trim(),
  );

  console.log('\n[4] Picking an unreachable provider states why');
  await providerSelect.selectOption('anthropic');
  await page.waitForTimeout(400);
  const noteShown = await page.getByText(/different request format/i).count();
  check('the catalogue’s reason is shown at the moment of choosing', noteShown > 0);
  await page.screenshot({ path: `${SHOTS}/settings-provider-refused.png`, fullPage: true });

  console.log('\n[5] Connect a provider that needs no key and no network');
  // LM Studio is loopback: it exercises connect, adapter registration and the
  // engine rebuild without a credential and without a byte leaving.
  await providerSelect.selectOption('lm_studio');
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: /^Connect$/ }).click({ force: true });
  await page.waitForTimeout(1500);
  const connected = await page.getByText('LM Studio (on this machine)').count();
  check('the connection appears in the connected list', connected > 0);

  console.log('\n[6] The kill switch round-trips');
  await page.getByRole('button', { name: 'Cut everything' }).click({ force: true });
  await page.waitForTimeout(1200);
  const onState = await page.getByText(/ON — nothing may leave/).count();
  check('turning it on is reflected by the backend’s own answer', onState > 0);
  await page.screenshot({ path: `${SHOTS}/settings-killswitch-on.png`, fullPage: true });

  await page.getByRole('button', { name: 'Allow, per the rules below' }).click({ force: true });
  await page.waitForTimeout(1200);
  const offState = await page.getByText(/ON — nothing may leave/).count();
  check('turning it off again is reflected too', offState === 0);

  console.log('\n[6b] The web search toggle round-trips, and is honest about the rest');
  const searchToggle = page.getByTestId('web-search-toggle');
  await searchToggle.getByRole('button', { name: 'On', exact: true }).click({ force: true });
  await page.waitForTimeout(1200);
  const searchOn = await searchToggle
    .getByRole('button', { name: 'On', exact: true })
    .getAttribute('aria-pressed');
  check('turning search on is read back from the backend', searchOn === 'true');

  // The point of the row: "on" alone would be a misleading answer, because the
  // per-host rule still decides. Whichever caveat applies must be stated.
  const caveat = await page
    .getByText(/Searches go to|kill switch is on, so no search|ZARAM_WEB_SEARCH is set/)
    .count();
  const hostAllowed = await page.getByText('duckduckgo.com').count();
  check(
    'either the remaining obstacle is named, or the host already has a rule',
    caveat > 0 || hostAllowed > 0,
    caveat > 0 ? 'obstacle stated' : 'host already ruled',
  );
  await page.screenshot({ path: `${SHOTS}/settings-web-search.png` });

  console.log('\n[7] The routing preference round-trips');
  await page.getByRole('button', { name: 'Prefer local' }).click({ force: true });
  await page.waitForTimeout(1200);
  const pressed = await page.getByRole('button', { name: 'Prefer local' }).getAttribute('aria-pressed');
  check('the preference is saved and read back', pressed === 'true', `aria-pressed=${pressed}`);
  await page.getByRole('button', { name: 'Auto' }).click({ force: true });
  await page.waitForTimeout(800);

  console.log('\n[8] Tidy up, then capture the screen at rest');
  const disconnect = page.getByRole('button', { name: /Disconnect/ }).first();
  if (await disconnect.count()) {
    await disconnect.click({ force: true });
    await page.waitForTimeout(1200);
  }

  // `fullPage` does not do what it sounds like here. The surface scrolls in its
  // own `overflow-y-auto` container rather than on the document, so the page
  // itself is exactly one viewport tall and `fullPage` captures wherever that
  // container happens to be scrolled to. Clicking controls in the steps above
  // scrolls them into view, so the "whole screen" shot silently began below
  // the Privacy section — the section it most needed to show. Scroll the
  // container back, then capture it in two labelled halves.
  const scrollSettingsTo = (offset) =>
    page.evaluate((top) => {
      const pane = [...document.querySelectorAll('div')].find(
        (el) => el.scrollHeight > el.clientHeight + 40 && el.className.includes('overflow-y-auto'),
      );
      if (pane) pane.scrollTop = top;
      return pane ? { scrollHeight: pane.scrollHeight, clientHeight: pane.clientHeight } : null;
    }, offset);

  const pane = await scrollSettingsTo(0);
  await page.waitForTimeout(500);
  check('the settings pane is scrollable, so both halves exist', pane !== null, JSON.stringify(pane));
  await page.screenshot({ path: `${SHOTS}/settings-top.png` });

  await scrollSettingsTo(100000);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SHOTS}/settings-bottom.png` });

  await scrollSettingsTo(0);
  await page.waitForTimeout(300);
  const privacyVisible = await page.getByText('Kill switch').isVisible();
  check('Privacy is the first thing the screen shows', privacyVisible);

  console.log('\nconsole errors:', consoleErrors.length);
  for (const e of consoleErrors.slice(0, 5)) console.log('   ', e);

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  console.log(`screenshots in ${SHOTS}/`);

  await browser.close();
  if (failed.length) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
