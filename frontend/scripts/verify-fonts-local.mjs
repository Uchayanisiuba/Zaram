/**
 * Prove the fonts come from the bundle, with the network to Google blocked.
 *
 * Two things are checked, and the second is the one that matters:
 *
 *  1. No request to fonts.googleapis.com or fonts.gstatic.com is attempted.
 *  2. The text actually renders in Inter / Space Grotesk / JetBrains Mono
 *     rather than silently falling back to system-ui.
 *
 * The second exists because @fontsource-variable registers "Inter Variable",
 * not "Inter" — so a stack that lists only the bare name passes check (1)
 * perfectly while rendering in the system font. Removing the egress and losing
 * the typeface would be a regression dressed as a fix.
 *
 * Dev server must be running.  node scripts/verify-fonts-local.mjs
 */
import { chromium } from 'playwright';

const APP = 'http://localhost:5173';

const main = async () => {
  const browser = await chromium.launch({ channel: 'chromium' });
  const ctx = await browser.newContext();

  const attempted = [];
  // Fail loudly rather than silently allowing: if anything still reaches for
  // Google, record it and let the request die as it would offline.
  await ctx.route('**://fonts.googleapis.com/**', (r) => {
    attempted.push(r.request().url());
    return r.abort();
  });
  await ctx.route('**://fonts.gstatic.com/**', (r) => {
    attempted.push(r.request().url());
    return r.abort();
  });

  const page = await ctx.newPage();
  await page.goto(APP, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500);
  await page.evaluate(() => document.fonts.ready);

  const loaded = await page.evaluate(() =>
    [...document.fonts].map((f) => `${f.family} ${f.weight} ${f.status}`),
  );

  const resolved = await page.evaluate(() => {
    const probe = (family) => {
      const el = document.createElement('span');
      el.textContent = 'Zaram';
      el.style.font = `16px ${family}`;
      document.body.appendChild(el);
      const w = el.getBoundingClientRect().width;
      el.style.font = '16px monospace';
      const fallback = el.getBoundingClientRect().width;
      el.remove();
      return { family, differsFromFallback: Math.abs(w - fallback) > 0.5 };
    };
    const cs = getComputedStyle(document.documentElement);
    return {
      sans: cs.getPropertyValue('--font-sans').trim(),
      display: cs.getPropertyValue('--font-display').trim(),
      mono: cs.getPropertyValue('--font-mono').trim(),
      checks: [
        probe("'Inter Variable'"),
        probe("'Space Grotesk Variable'"),
        probe("'JetBrains Mono Variable'"),
      ],
    };
  });

  await ctx.close();
  await browser.close();

  console.log('font faces the page loaded:');
  const uniq = [...new Set(loaded)];
  uniq.slice(0, 10).forEach((f) => console.log(`  ${f}`));
  if (!uniq.length) console.log('  (none)');

  console.log('\nCSS variables:');
  console.log(`  --font-sans    ${resolved.sans}`);
  console.log(`  --font-display ${resolved.display}`);
  console.log(`  --font-mono    ${resolved.mono}`);

  console.log('\nrendered check (does the family differ from the fallback?):');
  let rendered = true;
  for (const c of resolved.checks) {
    const ok = c.differsFromFallback;
    rendered = rendered && ok;
    console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${c.family}`);
  }

  console.log('\nrequests to Google:');
  if (attempted.length) {
    attempted.forEach((u) => console.log(`  FAIL  ${u}`));
  } else {
    console.log('  PASS  none attempted');
  }

  const ok = attempted.length === 0 && rendered;
  console.log(`\n  ${ok ? 'FONTS ARE LOCAL AND RENDERING' : 'NOT SATISFIED'}`);
  process.exit(ok ? 0 : 1);
};

main().catch((err) => {
  console.error('verification failed:', err.message);
  process.exit(1);
});
