import { describe, expect, it } from 'vitest';

import { changeRequest, describe as named, explainRequest, fixRequest, readPick } from './askAboutPage';

const raw = {
  tag: 'BUTTON',
  selector: 'body > div#overlay > button#start',
  text: 'Start',
  html: '<button id="start">Start</button>',
  rect: { x: 1, y: 2, w: 3, h: 4 },
};

describe('what the frame reports is page text, checked and bounded', () => {
  it('reads a pick', () => {
    const p = readPick(JSON.stringify(raw))!;
    expect(p.tag).toBe('button');
    expect(named(p)).toBe('button#start');
  });

  it('refuses what is not one, and bounds what is', () => {
    expect(readPick('not json')).toBeNull();
    expect(readPick(JSON.stringify({ selector: 'x' }))).toBeNull();
    const huge = readPick(JSON.stringify({ ...raw, html: 'x'.repeat(10_000), text: 'y'.repeat(1000), rect: { x: 'no' } }))!;
    expect(huge.html.length).toBeLessThanOrEqual(800);
    expect(huge.text.length).toBeLessThanOrEqual(160);
    expect(huge.rect.x).toBe(0);
  });
});

describe('every request that changes the page asks for all of it back', () => {
  // 5 October 2026: a change came back as only the changed lines.
  const p = readPick(JSON.stringify(raw))!;

  it('a change names the part and the words', () => {
    const text = changeRequest(p, '  make it red ');
    expect(text).toContain('What to change: make it red');
    expect(text).toContain('`body > div#overlay > button#start`');
    expect(text).toContain('reply with the whole updated page in one ```html block');
  });

  it('a fix carries the error and the hosts it could not load', () => {
    const text = fixRequest('THREE is not defined', ['cdn.example.com']);
    expect(text).toContain('THREE is not defined');
    expect(text).toContain('cdn.example.com');
    expect(text).toContain('whole page in one ```html block');
  });

  it('an explanation does not ask for a rewrite', () => {
    expect(explainRequest(p)).toContain('do not rewrite the page');
  });
});
