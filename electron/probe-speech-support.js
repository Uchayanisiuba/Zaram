/**
 * Does the Web Speech API actually work inside Electron?
 *
 * The question matters because offering cloud speech recognition as a Settings
 * option is only honest if the option functions. Chromium implements
 * `webkitSpeechRecognition` by calling Google's speech service with an API key
 * compiled into the browser; Electron builds do not carry Google's key, so the
 * constructor can exist while every attempt fails. A control that is present
 * and broken is worse than one that is absent, and it would fail *only* in the
 * packaged app — the dev browser surface would work fine and hide it.
 *
 * This probes rather than asserts, and is re-runnable because the answer can
 * change with an Electron upgrade:
 *
 *   npx electron electron/probe-speech-support.js
 *
 * It never grants microphone permission and captures no audio. The worst case
 * is a recognition session that errors immediately, which is the answer.
 */
const { app, BrowserWindow, session } = require('electron');

app.disableHardwareAcceleration();

app.whenReady().then(async () => {
  // Deny every permission request outright. This probe asks whether the API is
  // *wired to a backend service*, not whether a microphone exists, and a
  // product that bans cloud speech must not open a microphone to find out.
  session.defaultSession.setPermissionRequestHandler((_wc, _perm, cb) => cb(false));

  const win = new BrowserWindow({ show: false, webPreferences: { offscreen: true } });
  await win.loadURL('data:text/html,<html><body></body></html>');

  const result = await win.webContents.executeJavaScript(`
    new Promise((resolve) => {
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Ctor) return resolve({ constructorPresent: false });

      let rec;
      try {
        rec = new Ctor();
      } catch (e) {
        return resolve({ constructorPresent: true, constructed: false, error: String(e) });
      }

      const done = (outcome) => resolve(Object.assign({
        constructorPresent: true, constructed: true,
      }, outcome));

      rec.onerror = (e) => done({ event: 'error', error: e.error, message: e.message || '' });
      rec.onstart = () => done({ event: 'start' });
      rec.onend = () => done({ event: 'end' });

      try {
        rec.start();
      } catch (e) {
        return done({ event: 'throw', error: String(e) });
      }
      // 'network' is the documented Electron symptom: no Google API key, so the
      // session dies before it ever reaches onstart.
      setTimeout(() => done({ event: 'timeout' }), 6000);
    });
  `);

  console.log('\nWeb Speech API in Electron ' + process.versions.electron + ':');
  console.log(JSON.stringify(result, null, 2));

  const usable = result.constructed && result.event === 'start';

  // Be honest about what this run can and cannot distinguish. The probe denies
  // every permission, so `not-allowed` is fully explained by that handler and
  // says nothing about whether Electron carries Google's API key. Separating
  // the two would mean granting microphone access and letting a real recording
  // reach Google — which is the exact thing this product bans, so the probe
  // stops here rather than performing it to find out.
  if (result.error === 'not-allowed') {
    console.log(
      '\nINCONCLUSIVE on the API-key question: this probe denies all permissions,\n' +
        'so `not-allowed` is its own doing. Distinguishing "no Google key" from\n' +
        '"no microphone permission" would require sending real audio to Google.',
    );
  }

  // The decision does not depend on resolving that, which is worth stating so
  // nobody re-runs this expecting it to change the answer:
  //   - if it is broken, offering it in Settings ships a dead control;
  //   - if it works, it streams microphone audio to Google, which
  //     check-no-cloud-speech.mjs bans outright and Rules 3, 5 and 8 forbid.
  console.log(
    '\nVERDICT: ' +
      (usable
        ? 'the session started. Note this still means audio reaches Google.'
        : 'not usable as configured.') +
      '\nEither way: do not offer cloud speech in Settings. Broken means a dead\n' +
      'control; working means microphone audio leaving the device unlogged.',
  );

  await win.destroy();
  app.exit(usable ? 0 : 1);
});
