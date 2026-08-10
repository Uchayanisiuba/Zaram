/** Inspect the real DOM so the drive script targets it instead of guessing. */
import { chromium } from 'playwright';

const BASE = process.env.ZARAM_URL ?? 'http://localhost:5173';
const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const notFound = [];
page.on('response', (r) => { if (r.status() === 404) notFound.push(`${r.request().method()} ${r.url()}`); });

await page.goto(BASE, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);

console.log('=== elements with data-testid ===');
console.log(await page.evaluate(() =>
  [...document.querySelectorAll('[data-testid]')].map((e) => `${e.tagName.toLowerCase()} [${e.dataset.testid}] ${(e.innerText||'').trim().slice(0,40)}`).join('\n')
));

console.log('\n=== nav-ish clickables (landing) ===');
console.log(await page.evaluate(() =>
  [...document.querySelectorAll('button,[role="button"],a')]
    .map((e) => `${e.tagName.toLowerCase()} class="${(e.className||'').toString().slice(0,60)}" aria=${e.getAttribute('aria-label')} text="${(e.innerText||'').trim().slice(0,30)}"`)
    .join('\n')
));

// Enter chat, then look again — the top nav only exists once a surface opens.
await page.mouse.click(720, 450);
await page.waitForTimeout(1800);

console.log('\n=== clickables after entering chat ===');
console.log(await page.evaluate(() =>
  [...document.querySelectorAll('button,[role="button"],a')]
    .map((e) => `${e.tagName.toLowerCase()} testid=${e.dataset.testid} aria=${e.getAttribute('aria-label')} title="${e.getAttribute('title')||''}" text="${(e.innerText||'').trim().slice(0,30)}"`)
    .join('\n')
));

console.log('\n=== 404s ===');
console.log(notFound.join('\n') || '(none)');

await browser.close();
