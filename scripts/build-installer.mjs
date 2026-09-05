/**
 * Run electron-builder with signing configured only when it can actually sign.
 *
 * `electron-builder.yml` cannot express "this key is absent". Writing
 *
 *     certificateSubjectName: "${env.ZARAM_SIGN_SUBJECT}"
 *
 * does not resolve to empty when the variable is unset — electron-builder
 * passes the literal `${env.ZARAM_SIGN_SUBJECT}` through to the signer, which
 * then looks in the Windows certificate store for a certificate by that name,
 * does not find it, and fails the build:
 *
 *     ⨯ Cannot find certificate ${env.ZARAM_SIGN_SUBJECT}, all certs:
 *
 * The config carried a comment claiming the opposite ("empty unless the
 * environment provides it; electron-builder then skips signing"), and the
 * failure is at the *end* of a ten-minute build, in the step that signs the
 * uninstaller — after packaging has already succeeded. That is why
 * `win-unpacked` and a working `Zaram.exe` existed for a while and an installer
 * never did: nothing before the last minute of the build goes wrong.
 *
 * So the subject is injected here instead, and only when there is one. Absent,
 * the field never reaches electron-builder at all and signing is skipped, which
 * is correct for a development build. `check:signing` is what decides whether
 * an unsigned build is allowed to exist; this script only makes it buildable.
 *
 * Extra arguments are forwarded, so the symlink-privilege workaround still
 * works:
 *
 *     npm run build:desktop -- --config.win.signAndEditExecutable=false
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const subject = (process.env.ZARAM_SIGN_SUBJECT || '').trim();
const forwarded = process.argv.slice(2);

const args = ['--win'];
if (subject) {
  // Quoting is not our problem here: spawn without a shell passes this as one
  // argv entry, so a subject with spaces in it — which every certificate
  // subject has — arrives intact.
  args.push(`--config.win.certificateSubjectName=${subject}`);
}
args.push(...forwarded);

console.log(
  subject
    ? `build:installer — signing as "${subject}".`
    : 'build:installer — unsigned development build; no certificate subject in the environment.',
);

// `electron-builder` is a .cmd shim on Windows, which cannot be exec'd
// directly. Resolving it inside node_modules/.bin and running it through the
// shell is the portable way to call it from a script.
const bin = path.join(ROOT, 'node_modules', '.bin', 'electron-builder');
const child = spawn(bin, args, { cwd: ROOT, stdio: 'inherit', shell: true });

child.on('exit', (code, signal) => {
  if (signal) {
    console.error(`\nbuild:installer — electron-builder was killed by ${signal}.`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});

child.on('error', (err) => {
  console.error(`\nbuild:installer — could not start electron-builder: ${err.message}`);
  process.exit(1);
});
