# Design captures

Screenshots of the interface as built, referenced by `docs/UI-SPEC.md`.

**This directory is currently empty.** The captures were requested but could not
be produced: the session had no browser automation available and Playwright is
not installed in the project. Rather than leave a spec that promises images
which do not exist, the gap is recorded here.

## To fill it

Either drop PNGs in with the names below, or install Playwright and let it
capture them:

```bash
cd frontend
npm i -D playwright && npx playwright install chromium
```

Both the backend and the dev server must be running, and the URL is
`http://localhost:5173` — note `localhost`, not `127.0.0.1`. Vite binds to IPv6
and refuses the loopback address.

## Wanted captures

| File | Shows |
|---|---|
| `landing-at-rest.png` | Orbital landing, quiet, no status label |
| `landing-first-run-hint.png` | The self-dismissing hint, ~3s after first load |
| `conversation-open.png` | Chat at 45%, orb shifted left, status label beneath |
| `conversation-with-sources.png` | A reply with its citations listed |
| `source-panel-open.png` | A citation opened, orb blurred and receded |
| `source-panels-cascaded.png` | Two or more panels at their fixed offsets |
| `source-panel-confirm-delete.png` | "Delete for good?" with "Answers will change" |
| `workspace-shell.png` | Top bar, rail and dock, with the Orb at working size |
| `conversation-beside-workspace.png` | Chat at 28% beside a workspace |
| `orb-warming-up.png` | The cold-start state on a first message |
| `orb-offline.png` | Backend stopped |
| `divider-drag.png` | A division mid-drag |

`orb-warming-up.png` and `orb-offline.png` are the two worth capturing by hand
even if the rest are automated: they are the states a user hits when something
is wrong, and they are the ones least likely to be exercised otherwise.
