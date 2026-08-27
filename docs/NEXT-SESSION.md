# Next session — start here

A prompt and a state snapshot. Rewritten 27 August 2026 at the end of the
EXL3, local-routing and Knowledge-removal session.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then this file.
> For anything touching voice read `docs/SPEECH.md`; before starting the app
> read `docs/RUNNING.md`, and note that **launching now means three processes,
> not two** — Vite, Electron, and TabbyAPI on port 1234.
>
> The machine has changed since the last handoff. Ollama holds only
> `gemma4:26b-a4b-it-q4_K_M` and `bge-m3`; the main chat model is
> **Qwen3.8-27B EXL3 at 2.20bpw served by TabbyAPI**, which Zaram discovers on
> loopback as "LM Studio". Nothing from this session is committed — read
> "Uncommitted work" below before touching those files.
>
> The first job is the vision path. It is broken in a way that is half fixed
> and half not, and the unfixed half needs a decision rather than a patch.

---

## What happened this session

**Qwen3.8-27B now runs locally at 2.20bpw through TabbyAPI**, and getting
there found three real defects in Zaram rather than in the setup.

### The routing defect, and why it mattered more than the symptom

`RoutedEngine` splits the world into local and cloud and hands everything
local to `OllamaEngine`. That was true while Ollama was the only local server
and stopped being true when the catalogue gained `lm_studio` — an
OpenAI-compatible server on `127.0.0.1:1234`. A model served there was
discovered, catalogued, shown in the picker with a correct
`NEVER_LEAVES_DEVICE` policy, chosen, and then posted to Ollama:

    Ollama refused the request for Qwen3.8-27B-exl3-2.20bpw:
    model 'Qwen3.8-27B-exl3-2.20bpw' not found

Underneath it, `OpenAICompatibleEngine` refused an empty API key with *"A
cloud model needs your own API key"* — written on the assumption that
OpenAI-compatible implies cloud. LM Studio and TabbyAPI both ship auth-free on
loopback, so **the `lm_studio` catalogue entry could never have executed a
single request.** Discoverable, never runnable: the fifteen-unreachable-
subsystems shape, in the routing layer.

Fixed by `engines/local_dispatch_engine.py` (dispatch by **provider id**,
never by model name) and a loopback-only exemption to the key requirement. The
exemption is gated on the address, not on the key being blank, so a cloud
provider still cannot slip through — `tests/test_local_dispatch.py` asserts
that `https://localhost.attacker.example` is refused.

### Two existing tests were asserting the wrong thing

`test_engine_routing.py` had two tests reading `isinstance(engine,
OllamaEngine)` for the no-key case. That pins **which local server answers**
when the contract they exist to protect is *no engine capable of leaving the
device is built without a key*. Rewritten to assert that. Worth remembering as
a pattern: the test was green for the whole time it was wrong, and only a
change it should not have blocked revealed it.

### Reasoning was being rendered as the answer

This model's chat template ends the prompt with a bare `<think>\n`, so
generation begins *inside* the block and the model only ever emits the closing
tag. `ReasoningSplitter` waits for an opening tag that never comes and files
the monologue as the reply — which also meant Kokoro read it aloud, the exact
failure that module's docstring says it exists to prevent.

Two fixes were needed and either alone looks like it did nothing: TabbyAPI's
`reasoning: true` splits it server-side (`start_in_reasoning: auto` detects the
unclosed prefill), and `OpenAICompatibleEngine` now reads `reasoning_content`
as well as `content`, re-wrapping it in the tags the splitter already
understands. That second half also fixes DeepSeek and every other provider
using the same OpenAI extension.

---

## The first job: vision

**Half fixed today, half needs a decision.**

The symptom was:

    Dispatcher: CRITICAL ERROR for vision.analyze:
      AttributeError: 'RoutedEngine' object has no attribute 'stream_vision_response'

*Fixed:* both wrappers now forward the method. `RoutedEngine` never had it —
a pre-existing hole that only appeared once a cloud key was configured — and
`LocalDispatchEngine` inherited it, which briefly widened the bug, because a
keyless setup previously got a bare `OllamaEngine` that had the method.

*Not fixed, and this is the decision:* `OllamaEngine.stream_vision_response`
hardcodes `"model": "qwen2.5vl:7b"`, which **is not installed on this
machine**, and ignores whatever model the user chose. So vision now reaches
the engine and fails at Ollama instead of at the attribute lookup.

The right fix is the modality gate `CLAUDE.md` already describes and it is not
a one-liner:

* `ModelInfo.supports_vision` exists and Ollama discovery populates it from
  `/api/show`. **It is a 0..1 ranking score, not a gate** — `capabilities.py`
  maps `ModelCategory.IMAGE` to `Capability.VISION: 1.0`, the same value a
  model that *reads* images gets, so "can see" and "can draw" are one number.
* Modality is a **precondition**, never a ranking. It filters the candidate
  set; similarity then orders what survives. This codebase has paid three
  times for merging membership with ordering.
* `gemma4:26b-a4b` is vision-capable and installed. Selecting it for a vision
  request is the concrete outcome to aim for.

Do not paper over it by pulling `qwen2.5vl:7b` — that leaves the hardcode in
place and makes a future user's vision request depend on a model they never
chose.

---

## Uncommitted work

Nothing from this session is committed. Thirteen modified files and five new
ones, and they are four independent changes that should land as four commits:

**1. Preview fix.** `frontend/src/components/ArtifactPreview.tsx`.
`WorkWorkspace`'s detail sidebar carries `backdrop-filter: blur(24px)`, which
makes it the containing block for `position: fixed` descendants and then clips
them with its own `overflow: hidden`. The preview panel resolved `right:
panelWidth` — a fraction of the *viewport* — inside a 520px box. Measured: the
same element reported width 816 against the viewport and 202 inside the aside,
and above a viewport of ~1857px it collapses to zero. Fixed with a portal to
`document.body`.

**2. Model picker and dropdown theming.**
`SettingsWorkspace.tsx`, `groupModelsByLocality.test.ts`, `index.css`. The
picker groups by locality with headings that name the consequence ("nothing is
sent" / "leaves this device"). **Four localities, not two** — a `local, else
cloud` split would file a hybrid model under a guarantee nobody checked, and
the test asserts nothing is ever dropped. The CSS fixes every `<select>` in
the app, not just this one: seven of them across five files had no `option`
styling at all, so their popups drew near-white text on the platform's white
surface. `color-scheme: dark` is what makes the popup *chrome* match.

**3. Cloud providers.** `backend/providers/catalogue.py`. NVIDIA NIM,
SambaNova and Cerebras. Every endpoint was probed before being written down —
GitHub Models returned **410 Gone** and is deliberately absent rather than
listed with a dead URL. Cerebras is labelled a trial, not a free tier,
because it requires a verified payment method.

**4. Local routing + reasoning + Knowledge removal.** The backend files, plus
`local_dispatch_engine.py`, `test_local_dispatch.py`,
`test_ingest_remove_file.py`. Described above and below.

`docs/MODEL-ONBOARDING.md` is new and independent of all four — nine ideas read
out of LM Studio's own on-disk state, each mapped to a Zaram rule that already
exists but has nowhere to live. None of it is implemented.

---

## Knowledge: per-file removal

Rule 4 says the user can delete any stored thing. Until today the only unit of
removal was a **whole source**, and every dropped or pasted file shares one
uploads source — so getting rid of one image meant discarding everything ever
pasted. Reported by the maintainer with a PNG they could not remove.

Added: `records.remove_outcome`, `service.withdraw_file`,
`DELETE /ingest/outcomes/{outcome_id}`, `removeFile` in `ingestClient`, and a
Remove control on both outcome sections in `KnowledgeWorkspace`.

Two decisions worth keeping:

* **The source row survives its last file.** An empty uploads directory is
  still where the next drop goes; deleting the row would make the next paste
  re-create it under a fresh id, detaching it from any domain pointing at the
  old one.
* **Only Zaram's own copies are unlinked.** A scanned folder holds the user's
  originals. `_delete_own_copies` checks containment *after* resolving, so a
  symlink inside uploads pointing at a real document is refused.

---

## The machine, as it now stands

| | |
|---|---|
| Ollama | `gemma4:26b-a4b-it-q4_K_M` (17 GB), `bge-m3` (1.2 GB) |
| TabbyAPI on 1234 | `Qwen3.8-27B-exl3-2.20bpw`, 9.61 GiB, 10.2/12.3 GB VRAM |
| Removed | `qwen3.8:27b`, `qwen2.5-coder:14b`, `gemma4:12b`, `bge-reranker-v2-m3` |
| TabbyAPI env | `C:\Users\user\tabbyapi-env` — torch 2.10.0+cu128, exllamav3 1.4.4, triton-windows 3.7.1 |

**Measured, same ~2,500-token prompt, RTX 3060 12 GB / i7-7700:**

| | Time to first token | Generation |
|---|---|---|
| `qwen3.8:27b` (removed) | 19.5 s | 1.96 tok/s |
| Qwen3.8 EXL3 2.20bpw | **0.72 s** | 8.0 tok/s |
| `gemma4:26b-a4b` (MoE) | 4.5 s | **23.75 tok/s** |

The MoE result is the one worth remembering: **two 18 GB models spilling by
the same ~50%, and the MoE generates 9.4× faster**, because only ~4B params
are read per token so the exiled experts sit untouched. Prior advice that
spill would be punishing on a 2017 CPU was too pessimistic — the CPU barely
matters when the spilled weights are not being read.

---

## Smaller things left open

* **Gemma 26B timed out at 120 s** on a cold first request
  (`OllamaEngine.stream_response failed: ReadTimeout`). Spill makes the first
  load slow; the timeout may simply be too tight for a spilling MoE.
* **The ambient surface 401s** against the per-launch secret. A second
  BrowserWindow polls `/health` and `/egress/pending` once a second and never
  authenticates, so Ctrl+Shift+Space likely shows "engine not running". The
  IPC secret handoff was never traced.
* **TabbyAPI shows as "LM Studio (on this machine)"**, because the catalogue's
  only local entry is the generic adapter pinned to 1234. Policy is correct;
  the name is not. Adding a generic "local server" entry would fix it.
* **`ReasoningPanel` uses `--color-text-muted`**, ~4.0:1 contrast. Deliberate
  quietness, possibly too faint. The dropdown headings were raised to
  `--color-text-muted-light` (9.34:1) for the same reason and it may want the
  same treatment.
* **Two Electron trees still unreconciled** (`electron/main.js` versus
  `desktop/`), and **two virtualenvs** (`backend/venv` versus `.venv`, the
  latter CPU-only torch). Both are triage decisions `docs/RUNNING.md` has been
  flagging for over a week.

---

## Working notes worth carrying

**Downloading from HuggingFace on a slow link took five attempts, and four
failures were self-inflicted.** Recorded because the diagnosis order was the
useful part: `huggingface_hub` hung at 0/22 twice with no error; `curl -C -`
managed 0.02 MB/s; a *bounded* range got 1.41 MB/s; headers showed a clean 206
and `X-Cache: Miss from cloudfront`, so the cap was **per-connection**, not
per-account and not the local link. 24 parallel ranges reached 1.7 MB/s.

The self-inflicted ones: a hardcoded byte count rounded off a GiB display
(2–4 MB too large, so the last chunk asked past EOF — and had it "succeeded"
the preallocated file would have been the wrong length, failing at model-load
time instead of download time); a resume marker wiped by a misfiring guard;
an orphaned `curl` retry loop that ran for an hour holding a file lock and
stealing bandwidth *while throughput was being measured around it*; and an
unretried API call.

**The lesson that generalises: never type a number the source will tell you.**
The final downloader takes the file list and every byte count from the API and
verifies each file against it afterwards.
