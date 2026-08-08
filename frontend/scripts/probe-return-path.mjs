/** What is the one-click route back to conversation from a workspace? */
import { chromium } from 'playwright';

const BASE = process.env.ZARAM_URL ?? 'http://localhost:5173';
const browser = await chromium.launch({ headless: true, executablePath: chromium.executablePath() });
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });

const inventory = () =>
  page.evaluate(() => ({
    orb: !!document.querySelector('[data-testid="orb-tap"]'),
    orbClickable: (() => {
      const o = document.querySelector('[data-testid="orb-tap"]');
      if (!o) return 'absent';
      const r = o.getBoundingClientRect();
      const cs = getComputedStyle(o);
      return `box=${Math.round(r.width)}x${Math.round(r.height)} cursor=${cs.cursor} opacity=${cs.opacity} tabindex=${o.getAttribute('tabindex')}`;
    })(),
    input: !!document.querySelector('textarea, input[type="text"]'),
    buttons: [...document.querySelectorAll('button')]
      .map((b) => (b.innerText || b.getAttribute('aria-label') || '').trim().split('\n')[0])
      .filter(Boolean)
      .slice(0, 14),
  }));

await page.goto(BASE, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);
console.log('LANDING       ', JSON.stringify(await inventory()));

await page.click('[data-testid="orb-tap"]');
await page.waitForTimeout(1800);
console.log('IN CHAT       ', JSON.stringify(await inventory()));

// Open Memory
await page.evaluate(() => {
  [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === 'Memory')?.click();
});
await page.waitForTimeout(1800);
console.log('IN MEMORY     ', JSON.stringify(await inventory()));

// Route 1: the top-nav orb. `orb-tap` is the *landing* orb; inside a
// workspace the route back is OrbStatus in the header, whose aria-label ends
// "Open conversation."
const orbBack = await page.evaluate(() => {
  const o = [...document.querySelectorAll('button,[role="button"]')].find((b) =>
    (b.getAttribute('aria-label') || '').includes('Open conversation'));
  if (!o) return 'no orb';
  o.click();
  return `clicked: ${(o.getAttribute('aria-label')||'').slice(0,60)}`;
});
await page.waitForTimeout(1600);
console.log(`ORB CLICK (${orbBack})`, JSON.stringify(await inventory()));

// Route 2: click the active nav item again (toggle off)
await page.evaluate(() => {
  [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === 'Memory')?.click();
});
await page.waitForTimeout(1200);
await page.evaluate(() => {
  [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === 'Memory')?.click();
});
await page.waitForTimeout(1600);
console.log('NAV TOGGLE    ', JSON.stringify(await inventory()));

// Route 3: Escape
await page.keyboard.press('Escape');
await page.waitForTimeout(1400);
console.log('ESCAPE        ', JSON.stringify(await inventory()));

await browser.close();
