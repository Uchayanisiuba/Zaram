# Design captures

Screenshots of the interface as built, referenced by `docs/UI-SPEC.md`.

Regenerate with the backend and dev server both running:

```bash
cd frontend && node scripts/capture.mjs
```

The URL is `http://localhost:5173` — **not** `127.0.0.1`. Vite binds to IPv6 and
refuses the loopback address.

Captured at 1440×900, 2× device pixel ratio, so the files are large. If the repo
size becomes a problem, drop `deviceScaleFactor` to 1 in the script.

## Current captures

| File | Shows |
|---|---|
| `landing-at-rest.png` | Orbital landing, quiet, no status label |
| `landing-first-run-hint.png` | The self-dismissing hint, ~3s after first load |
| `conversation-open.png` | Chat at 45%, orb shifted left, status label beneath |
| `conversation-with-sources.png` | A reply with its citations listed |
| `source-panel-open.png` | A citation opened, orb blurred and receded |
| `workspace-shell.png` | Top bar, rail and dock, with the Orb at working size |
| `orb-warming-up.png` | Cold-start state on a first message |
| `orb-offline.png` | Backend unreachable |

## Not yet captured

`source-panel-confirm-delete.png` and `source-panels-cascaded.png` need a
citation present and the record loaded; the run reaches the panel but the
confirm state is timing-dependent. `divider-drag.png` and
`conversation-beside-workspace.png` are not yet scripted.

## Notes for whoever runs this next

Two things the script has to work around, both of which are findings in their
own right:

- **Every click needs `force: true`.** The orb breathes continuously and the
  orbital satellites rotate continuously, so Playwright's "wait for the element
  to be stable" check never succeeds. An interface that never stops moving is
  an interface that cannot be driven by a test.
- **`waitUntil: 'networkidle'` hangs on the offline capture**, because the app
  keeps re-polling the blocked health probe. That capture uses
  `domcontentloaded`.
