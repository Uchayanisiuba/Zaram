#!/usr/bin/env node
/**
 * The release page, written in the site's voice.
 *
 * GitHub's page cannot be restyled, but the notes are most of what a person
 * sees when the download link lands them there — and until 21 September 2026
 * they were four lines of prose and an auto-generated commit list. This
 * prints the notes for one tag: the site's banner, what the build brought,
 * how to install past SmartScreen, how to verify the file, and how to send
 * feedback without an account. The release workflow pipes it into the
 * release body; run by hand it updates a release that already exists.
 *
 *   node scripts/release-notes.mjs <tag> <sha256> <size-mib>           # print
 *   node scripts/release-notes.mjs <tag> <sha256> <size-mib> --apply   # gh release edit
 *
 * `--apply` shells out to `gh`, which is the maintainer's own credential.
 * Nothing here contacts the network otherwise.
 */
import { execFileSync } from 'node:child_process';

const [tag, sha, size, flag] = process.argv.slice(2);
if (!tag || !sha || !size) {
  console.error('usage: node scripts/release-notes.mjs <tag> <sha256> <size-mib> [--apply]');
  process.exit(2);
}

const version = tag.replace(/^v/, '').replace(/-.*$/, '');
const site = 'https://uchayanisiuba.github.io/Zaram';
const repo = 'https://github.com/Uchayanisiuba/Zaram';

/** What each build brought, in the site's own words — the same list the
 *  Milestones panel carries. Add the next tag above the last. */
const BROUGHT = {
  'v0.1.0-alpha.4': [
    '**Type to find a model.** OpenRouter alone offers 549 of them, and the last build made you scroll all of it. Now you type — the name, the provider, what it is good at, or just “free” — on the settings page and in the conversation, and the list narrows as you go.',
    '**The free ones are marked, and so is the deal.** A green *Free* badge where a model costs nothing, and four words on every row saying what it does with what you send: *not kept*, *kept 30 days*, *trains on this*. Every free tier is paid for in data by somebody, and this is the product that tells you which.',
    '**Zaram checks its own work.** Ask it to fix something in a coding project and it can open the page in a browser, click through to the state that was broken, read what is actually on screen and say whether the change worked — rather than reporting that it edited a file and leaving the checking to you. Localhost only, in a browser of its own carrying none of your sign-ins.',
    '**And you can watch it do that.** The page it is driving, and the last thing it pressed, live under the reply.',
    '**Driving asks separately.** Running your project’s tests and pressing whatever happens to be on its page are different things to agree to — the second one is how a dev build pointed at something live gets a button pressed. So it is its own switch, off by default, beside the other two. While it was being split, the gate turned out to be letting the browser open under no permission at all, because the tool is called `open_in_browser` and something in that name read as *browse*. Fixed, and the test now asserts the verdict for every tool by name.',
    '**A create that fails says so.** Pointing a new coding project at a folder and pressing Create could leave the button dead and the screen silent if the backend was still starting. It now says what went wrong and lets you press it again.',
    '**Nothing of yours is in the installer**, and nothing of yours can reach the repository by accident — every database the app writes is ignored by kind rather than by path, wherever it lands, and a test asks git itself about each one.',
    '**Choose a voice.** All 54 of the speech pack’s voices are listed in Settings, each with the pack author’s own rating of how well it was trained, and a voice is fetched once, only when you pick it, and logged like anything else that leaves. One that needs a language pack you do not have is shown greyed with what it needs rather than offered and left to fail.',
    '**A terminal you can watch.** Switch it on per project and what Zaram runs in your folder appears in a panel, beside anything you type yourself, each line marked with who caused it. It is for setting a project up — an environment, an install, a build — not a full terminal, and it says so.',
    '**Pushing a repository is its own permission.** Allowing a site for chat does not allow a push to it: the first push asks, by name, and what is logged is how many commits went where, never what they said. A send — an email, a post — always asks again, however much you have allowed, and a plan you let run without stopping does not cover one.',
    '**Forget by date.** Remove everything from before a date, from a date onwards, between two dates, or all of it. You are told how many facts first — and how many earlier wordings of corrected ones — and nothing is removed until you press the button that says the number.',
    '**A reopened conversation keeps its sources, and tells you what became of them.** A fact you have since deleted shows struck through, one you corrected is marked, and one Zaram could not check is never called deleted. What is kept is which fact an answer leaned on, never the fact’s words.',
    '**Browsing is one switch**, off by default, in Settings — a page fetches from dozens of companies you never chose, so asking per site was a control to click through. Every page is still recorded.',
    '**Text you can read.** The hint under each setting and the footnotes were set in greys measured at 1.6:1 and 3.5:1 against the page — below the 4.5:1 that counts as readable. They are lifted, and a check on every build now refuses to let them slip back.',
    '**The model browser says what a model can do** — reads images, uses tools, thinks first — with a Details panel behind each row, and lists TabbyAPI builds graded against your card. Those it shows the command for, rather than fetching them: where TabbyAPI keeps its models is its own setting.',
    '**Drawing hands the card back.** When a picture has to unload your chat model to make room, the model is loaded again as soon as the picture is saved, so the next question is not the one that waits.',
  ],
  'v0.1.0-alpha.3': [
    '**A project that won’t start, started.** Zaram reads the repository’s own `package.json` and offers the scripts that are actually in it — the install, the migration, the build, the tests, the dev server. The last build could work out which commands you needed and then hand them back as text to paste; this one runs them.',
    '**Installing always asks**, whatever you have granted. Fetching packages runs whatever code those packages ask to run on arrival, and that code comes from a registry rather than from your project. Anything that reaches past this machine — a deploy, a publish, a release — asks on the same terms. There is still no shell: a runner is a named program and its arguments.',
    '**Pictures out.** Ask for one and it goes to a model that can draw, with the request shown before it leaves and the model named in the reply. A card too full to draw now refuses instead of starting an hour-long picture, and the refusal names the cheapest way round first — somewhere you already have, then a free key, then a paid one.',
    '**Jobs and grants.** Paste a posting or a funding call and it comes back as fields, checked against what Zaram already knows about you. A criterion with no fact behind it is a question to ask you, never a no applied on your behalf. It drafts the letter and never submits anything.',
    '**ZCode: the Spine from a terminal.** Installing Zaram puts `zcode` on your PATH. `zcode recall`, `remember`, `correct`, `show`, `projects` — the same memory the app uses, from any directory, holding a pairing credential you issued and can revoke. Human text goes to stderr and data to stdout, so `zcode recall \"the rate\" --json | jq` is a pipe.',
    '**Pick the folder yourself.** Opening a folder as a coding project now opens a real file dialog, and the offer says what pressing it actually grants rather than leaving you to find out.',
    '**A tool server that is shut out says so.** Attached, reachable and allowed to act are three different things, and the card now names which of the three failed instead of showing a tool that quietly never fires.',
    '**A fact goes into the Spine whole**, and a provider-qualified model name now finds its own context window instead of falling back to the smallest one there is.',
  ],
  'v0.1.0-alpha.2': [
    '**You can watch it work.** A row for every step — a file read, a search, a tool called — between the paragraphs, in the order it happened. Each row opens to what that step read, changed and sent, or *"Nothing left this device for this step"*, read from the log.',
    '**Thinking on/off**, beside the routing choice. Off is a few tenths of a second to the first word instead of several; the answer is usually the same for ordinary questions.',
    '**A model that can call tools chooses its own.** You do not name the tool; Zaram still asks before anything changes or leaves.',
    '**Name a folder and it opens.** Say where something is and Zaram offers, with one button, to open it as a coding project and ask again.',
    '**Work that runs on its own** — a question on a schedule, or one run per obligation coming due, drafting the message that should go out. The first thing that needs your say-so stops it; nothing unattended can approve itself or send anything.',
    '**The graphics card comes back.** *Release the card* unloads what every local server can unload, and closing Zaram does the same on its way out.',
    '**Send feedback** from Settings → Help, to a form that needs no account.',
  ],
  'v0.1.0-alpha.1': [
    'The first installer: memory with sources, the egress log, documents, code projects, the manual under Help.',
  ],
};

const brought = BROUGHT[tag] ?? [];

const lines = [
  `<p align="center"><a href="${site}"><img src="${site}/img/og.png" width="720" alt="Zaram — the memory and control layer for people who use more than one AI"></a></p>`,
  '',
  `**Windows, x64, ${size} MiB. An alpha, unsigned.** Every AI you use, in one place — that remembers you. Change the model, keep the memory. A model on your own machine answers first, free and private; add your own keys when you want more reach, and every byte that leaves is logged.`,
  '',
  ...(brought.length
    ? ['## What this build brought', '', ...brought.map((b) => `- ${b}`), '']
    : []),
  '## Install',
  '',
  `1. Download **\`Zaram-${version}-x64.exe\`** below (or the portable build, which needs no install).`,
  '2. Windows SmartScreen will say *"Windows protected your PC"*. That is expected for a build with no signing certificate — press **More info → Run anyway**.',
  '3. Zaram starts with whatever you have. Best with [Ollama](https://ollama.com) and one local model; a cloud key is optional and framed that way inside.',
  '',
  '## Verify the file',
  '',
  'The SHA-256 of the installer, also in `SHA256SUMS.txt` below:',
  '',
  '```',
  sha,
  '```',
  '',
  'In PowerShell, before you run it:',
  '',
  '```powershell',
  `Get-FileHash .\\Zaram-${version}-x64.exe -Algorithm SHA256`,
  '```',
  '',
  '## When something goes wrong',
  '',
  `In an alpha something will. **Settings → Help → Report a problem** copies a short report — version, hardware, the models found, what left the machine, and nothing else: no conversation, no document names, no keys. **Send feedback** next to it opens [a form](${site}/#feedback) that needs no account; paste the report there with what you expected and what happened instead. An [issue](${repo}/issues) works too.`,
  '',
  `[What Zaram is](${site}) · [Milestones](${site}/#milestones) · [Source](${repo}) — source-available, all rights reserved; read every line, the claim is that you can.`,
];

const body = lines.join('\n');

if (flag === '--apply') {
  execFileSync('gh', ['release', 'edit', tag, '--notes-file', '-'], { input: body, stdio: ['pipe', 'inherit', 'inherit'] });
  console.error(`release notes applied to ${tag}`);
} else {
  process.stdout.write(body + '\n');
}
