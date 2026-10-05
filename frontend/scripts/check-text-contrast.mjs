#!/usr/bin/env node
/**
 * Text that can be read.
 *
 * Measured 4 October 2026: `--color-text-faint` was #3a3f5c, **1.6:1** against
 * the lightest surface it sits on (WCAG AA for text is 4.5:1), and
 * `--color-text-muted` was 3.5:1. The app sets whole sentences in both -- the
 * explanation under every Settings row, hints, footnotes -- so a screen could be
 * "finished" with half its words invisible. Nothing caught it because nothing
 * measured it. This reads the tokens out of `src/index.css` and does the sum on
 * every build.
 *
 * Read from the stylesheet rather than copied here: a number kept in two places
 * disagrees with itself the first time somebody tunes either.
 *
 * A check that cannot fail is worse than none, so it starts by being run on the
 * old values and must reject them (the self-test).
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const CSS = resolve(here, '../src/index.css');

/** Minimum contrast against the *worst* (lightest) surface, per token. */
const TARGETS = {
  'color-text': 7,
  'color-text-muted-light': 7,
  'color-text-muted': 4.5,
  'color-text-secondary': 4.5,
  'color-text-faint': 4.5,
};

/** Dark to light by intent: each must be brighter than the one before. */
const ORDER = ['color-text-faint', 'color-text-secondary', 'color-text-muted', 'color-text-muted-light', 'color-text'];

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

function luminance([r, g, b]) {
  const f = (v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** A translucent white film over a base, the way the panels are built. */
const film = (over, alpha) => over.map((v) => Math.round(255 * alpha + v * (1 - alpha)));

function tokenReader(css) {
  return (name) => {
    const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})\\s*;`));
    if (!match) throw new Error(`--${name} is not a plain hex token in src/index.css`);
    return match[1];
  };
}

export function problemsIn(css) {
  const token = tokenReader(css);
  const base = rgb(token('color-base'));
  const surfaces = {
    base,
    surface: rgb(token('color-surface')),
    elevated: rgb(token('color-elevated')),
    overlay: rgb(token('color-overlay')),
    'glass on base': film(base, 0.04),
    'card on glass': film(film(base, 0.04), 0.04),
  };

  const problems = [];
  for (const [name, minimum] of Object.entries(TARGETS)) {
    for (const [surface, bg] of Object.entries(surfaces)) {
      const got = ratio(rgb(token(name)), bg);
      if (got < minimum) {
        problems.push(`--${name} (${token(name)}) on ${surface}: ${got.toFixed(2)}:1, needs ${minimum}:1`);
      }
    }
  }
  const lums = ORDER.map((n) => luminance(rgb(token(n))));
  for (let i = 1; i < lums.length; i += 1) {
    if (!(lums[i] > lums[i - 1])) problems.push(`--${ORDER[i]} is not lighter than --${ORDER[i - 1]}`);
  }
  return problems;
}

// ---- self-test: the check must reject the values it was written about.
const OLD = `
  --color-base: #080a0e; --color-surface: #0d0f16; --color-elevated: #131620; --color-overlay: #1a1e2e;
  --color-text: #e2e4ee; --color-text-secondary: #4a4f6a; --color-text-muted: #6b7099;
  --color-text-faint: #3a3f5c; --color-text-muted-light: #b0b4cc;
`;
const oldProblems = problemsIn(OLD);
if (oldProblems.length < 5) {
  console.error('check-text-contrast: self-test FAILED -- the old values were not rejected.');
  console.error(oldProblems.join('\n'));
  process.exit(2);
}
console.log(`check-text-contrast: self-test clean -- the old values fail ${oldProblems.length} ways.`);

const problems = problemsIn(readFileSync(CSS, 'utf8'));
if (problems.length) {
  console.error(`\n${problems.length} text-contrast problem(s) in src/index.css:\n`);
  for (const p of problems) console.error(`  ${p}`);
  console.error('\nText below 4.5:1 is not readable, and this app sets sentences in these tokens.');
  process.exit(1);
}
console.log('check-text-contrast: clean -- every text token clears its target on every surface.');
