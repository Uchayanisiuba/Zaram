#!/usr/bin/env node
/**
 * Tell the testers a build is up — run by hand, on the day.
 *
 * Why this is a script and not the workflow step it replaces (20 September
 * 2026, from the 15–19 September handoff): the workflow's Buttondown step
 * fired on the *tag*, while the download page flips on `releaseAt`, and those
 * are different moments on purpose. An email that arrives before the page is
 * on sends people to a page that says "soon". A script is run when the page
 * is on, by the person whose name is at the bottom of the email.
 *
 * What it does:
 *   1. reads the release from GitHub (`gh release view`) — tag, installer
 *      size, SHA-256 — so nothing in the email is typed by hand;
 *   2. composes the message, prints it;
 *   3. with `--send` and `BUTTONDOWN_API_KEY` in the environment, queues it
 *      through Buttondown to everyone on the list. Without `--send` it is a
 *      dry run and nothing leaves this machine.
 *
 * The list has to exist first: signups land in Formspree, and Buttondown
 * emails its own subscribers. Importing the one into the other is the
 * maintainer's step, in Buttondown's own interface, before this is run.
 *
 *   node scripts/tell-the-testers.mjs v0.1.0-alpha.1            # dry run
 *   BUTTONDOWN_API_KEY=… node scripts/tell-the-testers.mjs v0.1.0-alpha.1 --send
 */
import { execFileSync } from 'node:child_process';

const REPO = 'Uchayanisiuba/Zaram';
const SIGNATURE = 'Uche';

const args = process.argv.slice(2);
const tag = args.find((a) => !a.startsWith('--'));
const send = args.includes('--send');
if (!tag) {
  console.error('usage: node scripts/tell-the-testers.mjs <tag> [--send]');
  process.exit(2);
}

function release(tag) {
  const raw = execFileSync('gh', ['release', 'view', tag, '--repo', REPO, '--json', 'tagName,url,assets,isDraft'], {
    encoding: 'utf8',
  });
  const view = JSON.parse(raw);
  if (view.isDraft) throw new Error(`${tag} is still a draft`);
  const installer = view.assets.find((a) => /\.exe$/i.test(a.name) && !/portable/i.test(a.name));
  if (!installer) throw new Error(`${tag} has no installer asset`);
  const sums = view.assets.find((a) => a.name === 'SHA256SUMS.txt');
  let sha = '';
  if (sums) {
    const text = execFileSync('curl', ['--fail', '--silent', '--location', sums.url], { encoding: 'utf8' });
    const line = text.split('\n').find((l) => l.includes(installer.name));
    sha = line ? line.trim().split(/\s+/)[0] : '';
  }
  return {
    tag: view.tagName,
    url: view.url,
    installer: installer.name,
    mib: Math.round(installer.size / (1024 * 1024)),
    sha,
  };
}

function compose(r) {
  const subject = `Zaram ${r.tag} is ready to download`;
  const body = [
    `Zaram ${r.tag} is up: ${r.url}`,
    '',
    `Windows, x64, ${r.mib} MiB. It is unsigned, so Windows will warn before it runs — that is expected for a build with no certificate.` +
      (r.sha ? ` The SHA-256 is ${r.sha} if you want to check the file against SHA256SUMS.txt.` : ''),
    '',
    'What to try first: point it at a folder of your own documents and ask it something you would have to look up. It should answer with the file and the line it came from. Then ask it to write something up from those — a summary, a proposal, an invoice — and check it against the source.',
    '',
    'Local is free: a model on your own machine costs nothing per question, and nothing you say to it leaves your device or is trained on. Cloud keys are optional; if you add one, Activity shows every byte that went out.',
    '',
    'You can also watch it work: every step it takes — a file read, a search, a tool called — appears as a row in the reply where it happened, and each row opens to show what that step read, changed and sent. Thinking can be switched off beside the routing choice when you want speed over depth.',
    '',
    'When something goes wrong — and in an alpha something will — Settings → Help → Report a problem copies what I need; the Send feedback button next to it opens a short form that needs no account. Paste the report there with what you expected and what happened instead, or reply to this email. A reply that says "this was confusing" is as useful as one that says "this broke".',
    '',
    'Thank you for trying it this early.',
    '',
    SIGNATURE,
  ].join('\n');
  return { subject, body };
}

const r = release(tag);
const email = compose(r);

console.log(`Subject: ${email.subject}\n`);
console.log(email.body);
console.log('');

if (!send) {
  console.log('(dry run — nothing sent; add --send with BUTTONDOWN_API_KEY set)');
  process.exit(0);
}

const key = process.env.BUTTONDOWN_API_KEY;
if (!key) {
  console.error('--send needs BUTTONDOWN_API_KEY in the environment');
  process.exit(2);
}

const response = await fetch('https://api.buttondown.com/v1/emails', {
  method: 'POST',
  headers: { Authorization: `Token ${key}`, 'Content-Type': 'application/json' },
  body: JSON.stringify({ subject: email.subject, body: email.body, status: 'about_to_send' }),
});
if (!response.ok) {
  console.error(`Buttondown answered ${response.status}: ${await response.text()}`);
  process.exit(1);
}
console.log('queued through Buttondown');
