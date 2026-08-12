/**
 * Refuse to publish an unsigned build, and refuse to sign from a key file.
 *
 * Unsigned costs Zaram more than it costs a typical app. SmartScreen's warning
 * lands on a product whose entire claim is that your data stays yours and you
 * can see what leaves — and the first thing it teaches a new user is to click
 * through a security warning without reading it. That is the exact reflex the
 * product depends on breaking.
 *
 * So this is a gate rather than a reminder. A development build is unsigned and
 * that is correct; a *release* build that is unsigned should not exist, and the
 * difference between the two must not be somebody's memory at 2am.
 *
 * Set ZARAM_RELEASE=1 for anything a stranger will run.
 *
 * The second half matters as much as the first. Since June 2023 a
 * publicly-trusted code signing key has to sit on certified hardware — a token,
 * an HSM, or a cloud signing service — so a `.pfx` on disk is either a test
 * certificate that will not be trusted or a private key that should never have
 * been exportable. Either way it must not sign a release, and either way the
 * failure is silent without a check: electron-builder will happily use it.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const isRelease = process.env.ZARAM_RELEASE === '1';
const subject = (process.env.ZARAM_SIGN_SUBJECT || '').trim();

/** Ways a private key could reach the signer that must not be used. */
const FILE_BASED = ['CSC_LINK', 'CSC_KEY_PASSWORD', 'WIN_CSC_LINK', 'WIN_CSC_KEY_PASSWORD'];
const fileBasedInUse = FILE_BASED.filter((v) => (process.env[v] || '').trim() !== '');

function fail(lines) {
  console.error(`\n${lines.join('\n')}\n`);
  process.exit(1);
}

if (fileBasedInUse.length > 0) {
  fail([
    `  Signing is configured from a key file (${fileBasedInUse.join(', ')}).`,
    '',
    '  A publicly-trusted signing key has had to live on a hardware token, an',
    '  HSM or a cloud signing service since June 2023. A key in a file is',
    '  either a test certificate nobody will trust, or a real key that should',
    '  not have been exportable — and a real key that has touched a disk or a',
    '  CI variable should be treated as compromised.',
    '',
    '  Use ZARAM_SIGN_SUBJECT with the certificate installed in the Windows',
    '  certificate store. See docs/CODE-SIGNING.md.',
  ]);
}

if (!isRelease) {
  console.log(
    subject
      ? `check:signing — development build; would sign as "${subject}" under ZARAM_RELEASE=1.`
      : 'check:signing — development build, unsigned. Set ZARAM_RELEASE=1 to require signing.',
  );
  process.exit(0);
}

if (!subject) {
  fail([
    '  ZARAM_RELEASE=1 but no signing identity is configured.',
    '',
    '  This build would go out unsigned, and every person who runs it would be',
    '  told by Windows that the publisher cannot be verified — on a product',
    '  whose whole claim is that it can be trusted with your documents.',
    '',
    '  Set ZARAM_SIGN_SUBJECT to the certificate subject, exactly as it appears',
    '  in the Windows certificate store. See docs/CODE-SIGNING.md.',
  ]);
}

// A timestamp server has to be configured or the signature dies with the
// certificate — including on machines where it is already installed.
const config = fs.readFileSync(path.join(ROOT, 'electron-builder.yml'), 'utf8');
if (!/rfc3161TimeStampServer:\s*\S+/.test(config)) {
  fail([
    '  No RFC 3161 timestamp server is configured.',
    '',
    '  Without a timestamp, every signature stops validating the day the',
    '  certificate expires — including copies already installed on other',
    '  people\'s machines. A one-year certificate would quietly break the alpha',
    '  a year after it shipped.',
  ]);
}

console.log(`check:signing — release build, signing as "${subject}", timestamped.`);
