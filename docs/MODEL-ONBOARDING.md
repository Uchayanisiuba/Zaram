# Getting a stranger to a working model

**Written 27 August 2026, from reading LM Studio's own state on the dev
machine** — not from its marketing, and not from its UI. Every claim below is
read out of `~/.lmstudio/.internal/*.json` on a working install, and the file
is named where it matters.

The reason to look: `CLAUDE.md` ends with *"the actual blocker: a stranger
cannot install this."* LM Studio has solved exactly that problem for exactly
this audience, and it keeps its answer in flat JSON on disk where it can be
read rather than guessed at.

**What is worth taking is the *shape* of their state, not their product.**
Several of these are things Zaram already half-does, where the missing half is
a field.

---

## 1. A hardware survey is a result, not a value

`internal-engine-index.json` carries:

```json
"hardwareSurveyResult": {
  "gpuSurveyResult": {
    "result": { "code": "Success", "message": "" },
    "gpuInfo": [{ "name": "NVIDIA GeForce RTX 3060",
                  "totalMemoryCapacityBytes": 12884377600,
                  "dedicatedMemoryCapacityBytes": 12884377600,
                  "integrationType": "Discrete",
                  "detectionPlatform": "CUDA",
                  "otherInfo": { "computeCapability": "8.6",
                                 "driverVersion": "13010" } }]
  },
  "cpuSurveyResult": { "result": { "code": "Success", "message": "" },
                       "cpuInfo": { "name": "Intel(R) Core(TM) i7-7700 ...",
                                    "supportedInstructionSetExtensions": ["AVX","AVX2"] } }
}
```

The `result` object sits **beside** the data, not inside it. So three states
are distinguishable: detection succeeded and found a card; detection succeeded
and found none; detection failed and we do not know.

Zaram already refuses to collapse the third into the second — `vram_bytes` is
`None` rather than `0`, and `CLAUDE.md` explains why at length. **This is the
same instinct with somewhere to put the reason.** Today a `None` tells a caller
that the number is unknown and nothing tells the *user* whether that is because
they have no GPU, because nvidia-smi was missing, or because the registry read
failed — and those want three different sentences on screen.

Take: a survey result carrying `code` + `message` alongside the figure. It
costs one dataclass and it is the difference between "no GPU detected" and
"couldn't ask your GPU", which is the difference between a true statement and a
false one.

Note also `integrationType: "Discrete"` and `computeCapability`. Apple and
DirectML return `None` for VRAM in Zaram because the pool is shared — which is
correct, and `integrationType` is the field that would let the UI *say so*
rather than showing a blank.

## 2. `totalMemory` is a real number and Zaram does not have it

The same file records:

```
ramCapacity   34286313472   (31.9 GiB)
vramCapacity  12884377600   (12.0 GiB)
totalMemory   47170691072   (43.9 GiB)
```

`totalMemory` is simply the sum, and it is the number that decides whether a
model **runs slowly** rather than **not at all**. Zaram's
`resident_budget_bytes` answers "what fits on the card" and nothing answers
"what will load if we accept spill", so a 17 GB model on a 12 GB card is
currently just *unselectable* — with no way to offer the honest third option:
*"this will run, at about a fifth of the speed."*

Take it, with one rule attached: **it is a spill ceiling, never a capability
figure.** A model that fits in `totalMemory` runs; it does not run *well*. It
belongs in the sentence that explains a refusal, not in the gate that produces
one.

**And spill quality depends on the CPU, which is why the survey stores that
too.** This machine is an i7-7700 — four cores, 2017, DDR4. Advice of the form
"MoE spills gently because only the idle experts are in system memory" assumes
fast memory to spill into. It is much weaker here than the general claim
suggests, and the survey is what would let Zaram know that instead of repeating
the general claim.

## 3. Engines are graded per machine, with a verdict object

Each engine entry carries `backendCompatibility: {"status": "compatible"}`, and
the engines themselves are keyed by hardware:
`llama.cpp-win-x86_64-nvidia-cuda-avx2`. Platform, CPU instruction set, GPU
vendor and framework are all in the name, and the manifest repeats them
structurally:

```json
"cpu": { "architecture": "x86_64", "instruction_set_extensions": ["AVX2"] },
"gpu": { "make": "Nvidia", "framework": "CUDA" }
```

This is `CLAUDE.md`'s *"unavailable packs shown greyed out and honestly graded
against the user's hardware"*, already built. The transferable part is that the
verdict is **an object attached to the candidate**, not a boolean filter
applied before the user sees it. Nothing disappears; things arrive labelled.

## 4. The index keeps its failures

`model-index-cache.json` is not a list of models. It is:

```
models · conflicts · unclassifiedFiles · unresolvedVirtualModels · badModels · errors
```

Five of those six buckets exist to hold things that did **not** work. Nothing is
silently dropped.

This is the single most directly applicable idea in the file, and it does not
belong to the model layer at all — it belongs to **ingestion**. `CLAUDE.md`
already requires that a scan Zaram cannot read lands in Knowledge with its
reason and the size of the fix, rather than vanishing. That rule currently
depends on remembering to implement it per parser. **A result object with
`indexed` / `unreadable` / `conflicts` / `errors` buckets makes it structural**,
and the Knowledge surface renders the buckets instead of being told about
them.

## 5. A download is a job of tasks, each verifiable and resumable

From `download-jobs-info.json`, per task:

```json
"sha256": "2734eb42…", "fileSizeBytes": 352,
"progress": 100, "speedBytesPerSecond": 0,
"totalSizeBytes": 352, "downloadedSizeBytes": 352,
"status": "completed", "errorMessage": null,
"autoRetryNextTimestamp": null
```

Size and checksum are declared **before** the transfer; progress, speed, error
and a scheduled retry are tracked during it; the job carries its own state
machine (`jobState: {type, completedTimestamp}`).

`CLAUDE.md` says *"never block on a download — a user on metered data asked to
pull 7GB before their first answer closes the app."* That rule is currently a
prohibition with no machinery behind it. This is the machinery: **state the
size before starting, resume rather than restart, retry on a schedule, and
survive the app closing.**

Measured tonight on this machine: **2.3 MB/s**, making a 17 GB model a **2h08m**
download. That is not a hypothetical metered user. It is the maintainer's own
connection, and it means a non-resumable download is a broken feature here.

## 6. JIT loading with a TTL solves the co-residency problem

`settings.json`:

```json
"jitModelTTL": { "enabled": true, "ttlSeconds": 3600 },
"unloadPreviousJITModelOnLoad": true,
"unloadPreviousModelOnSelect": true
```

Models load on demand and unload after an hour idle. Zaram has a harder version
of this problem than LM Studio does, because bge-m3 must stay resident for the
Spine while a chat model comes and goes — 0.66 GB permanently spoken for, and
on a 12 GB card that is the difference between two models fitting and one.

`CLAUDE.md` already requires that *"a route that requires a swap must be visible
in the orb's state — an invisible swap reads as a broken product."* TTL-based
unloading is the other half of that: the swap becomes a **scheduled, explicable
event** rather than a mysterious pause. The orb has a `swapping` state already.

## 7. Tool confirmation is remembered as patterns

```json
"neverAskForToolConfirmation": false,
"skipToolConfirmationPatterns": []
```

This is rule 7j — *"confirm once per destination and data class, then
remember"* — as a concrete storage shape. A default of "ask", an explicit
escape hatch, and a **pattern list** rather than a blanket toggle, so a user
can grant one class without granting all of them.

Worth copying nearly verbatim, with Zaram's own addition intact: the hard stop
the rule reserves for the first time Spine facts reach a destination that has
not had them.

## 8. Capability is read from the artifact and stored as a field

Indexed models carry `domain: "embedding"` alongside `"llm"`, and metadata read
straight out of the GGUF header: `arch`, `contextLength`, `supportsMtp`,
`embeddingLength`.

`CLAUDE.md`'s images entry says the missing pieces are that nothing records
whether a model *emits* an image, and that modality exists only as a 0..1
ranking score when it needs to be a **gate**. This is how a gate gets built:
read the capability off the artifact at index time, store it as a field, and
filter the candidate set on it before any score is computed.

## 9. Two smaller ones

`"aiNamingMode": "auto"` — conversations are named by the model rather than by
the user. Relevant to the conversation-history work: a scrollback is only
navigable if the entries have names, and asking the user to name each one is
rule 7e ("never ask the user a question the system can answer from behaviour").

`"imageInputs": { "userMaxImageDimensionPixels": 2048 }` — images are
downscaled before they are sent. For Zaram this is not a bandwidth setting, it
is an **egress** setting: a smaller image is less of the user's data leaving,
and the cap belongs next to the per-destination image consent rule 7j already
requires.

---

## What not to take

**Their model browser is a live remote catalogue.** Zaram cannot have that:
rule 7g forbids a network call before consent, and browsing models is exactly
the kind of "helpful" fetch the rule was written against. The dated local
manifest stays, and it is the better design for this product even though it is
the worse one for theirs.

**They bundle a model** (`bundled-models/nomic-ai/nomic-embed-text-v1.5`).
Tempting, and it conflicts with a 186 MB installer and with the packaging rule
that already put Docling behind an extra. Zaram's answer is
`start with what you have`, which is stronger.

---

## The order these are worth doing

1. **Survey result object** (§1) — smallest, and it makes every later message
   about hardware truthful instead of approximate.
2. **Index error buckets for ingestion** (§4) — largest user-visible win, and
   it turns an existing written rule into a structure.
3. **Download jobs** (§5) — the one the maintainer's own 2.3 MB/s connection
   proves is not optional.
4. **`totalMemory` as a stated spill ceiling** (§2) — unlocks the honest third
   answer between "fits" and "unselectable".
5. **JIT TTL + swap visibility** (§6).
6. **Confirmation patterns** (§7) and **modality as a field** (§8) — both are
   rules already written that currently have nowhere to live.

None of this is implemented. This document is the study, not the change.
