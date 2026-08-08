# The reranker question

**Decision needed before M8.** Measured 8 August 2026 on the dev machine — RTX
3060, 12 GB — with real numbers rather than estimates. Nothing here is decided;
this is the options and what each costs.

---

## Why it is on the table at all

`test_recall_eval.py` measures the gap between what should be recalled and what
should not. After fixing the three scoring bugs it stands at **+0.080** —
related bottoming out at 0.469, unrelated topping out at 0.389, with the 0.42
floor between them.

That is a real margin on **five documents**. The concern is what happens at a
thousand. The negative side of the comparison is a *maximum over the corpus*:
every document added is another chance for something irrelevant to score high.
The positive side does not move. So the margin can only narrow, and a fixed
threshold degrades as the Spine grows — in a product whose entire pitch is that
it grows.

A reranker is the standard answer. A bi-encoder embeds query and document
independently and compares vectors; a cross-encoder reads both together and
scores the pair, which is far better at exactly the near-miss cases that erode
this margin.

This also matters for something already promised. Driving the interface turned
up a reply citing **five sources** for a statement the user had just made,
including a deploy target and an unrelated client. Rule 2 says an answer that
cites nothing is a bug; the converse — citing what the answer did not use — is
a false claim of provenance, and it teaches the user the citations mean
nothing.

---

## What is actually resident today

Measured with `nvidia-smi` and `/api/ps`, not assumed:

| Model | VRAM | Note |
|---|---|---|
| `bge-m3` (embeddings) | **0.66 GB** | Resident for the Spine |
| `gemma3:latest` (chat) | 3.05 GB | The default local answerer |
| **Total in use** | 3.71 GB | of 12 GB |

**CLAUDE.md's "~1.8 GB for embeddings and reranker resident" is wrong in both
directions.** Embeddings are 0.66 GB, not the ~1.3 GB the figure implies, so
there is more headroom than the doc claims — but the reranker half of that
budget was never spent, because it does not run at all.

---

## Option 1 — Ollama. Verified broken.

`qllama/bge-reranker-v2-m3` is pulled: 567.75M parameters, Q8_0, 0.64 GB on
disk. Both routes terminate the server:

```
POST /api/embed     -> llama-server terminated, exit 0xc0000409
POST /api/generate  -> llama-server terminated, exit 0xc0000409
```

`0xc0000409` is a stack buffer overrun. It reproduces on every attempt.

**And the failure is not contained.** After the crash, `/api/ps` returns an
empty list: it takes `bge-m3` and `gemma3` down with it. So a reranking call
that fails does not merely fail — it evicts the entire working set and the next
query pays a full reload of both.

This is not a configuration problem to work around. A reranker is a
cross-encoder producing a single relevance score for a pair; Ollama's API
surface has no cross-encoder verb, so the model is being driven through an
endpoint built for something else. **Do not spend more time here.**

Cost if pursued anyway: 0 MB install, 0.64 GB VRAM, and a crash.

---

## Option 2 — sentence-transformers `CrossEncoder`

The reference implementation. `bge-reranker-v2-m3` at fp16 is roughly
**1.1 GB VRAM** for 568M parameters; int8 roughly 0.6 GB.

**Install cost: 205 MB of wheels** — and the list is the problem, not the
number:

```
torch, scipy, numpy, transformers, scikit-learn, sympy
```

That is the same stack the Docling decision refused a week ago, for the same
reason. Base install is 267 MB; this takes it to roughly 470 MB, and M11's
acceptance is a stranger reaching a cited answer in under ten minutes.

Having just declined 321 MB for OCR — a capability users can *see* — accepting
205 MB for retrieval quality they cannot would need an argument this document
does not have.

| | |
|---|---|
| Install | +205 MB |
| VRAM | +1.1 GB fp16 / +0.6 GB int8 |
| Quality | Best available |
| Fits in 12 GB beside gemma3 | Yes — 4.8 GB total |

---

## Option 3 — ONNX cross-encoder

`onnxruntime` alone is **26 MB**. `flashrank` — a small reranker library that
ships ONNX models — is **35 MB** total including onnxruntime, tokenizers and
huggingface-hub.

The models are much smaller than `bge-reranker-v2-m3`: `ms-marco-MiniLM-L-12-v2`
is ~33M parameters, roughly 130 MB on disk, and runs on **CPU** in a few
milliseconds per pair for the top-20 shortlist retrieval produces.

CPU is the interesting part. The binding constraint in this product is not
absolute quality but *not competing with local inference for VRAM* — the same
constraint that chose Kokoro for TTS. A CPU reranker costs **0 GB VRAM**.

Against it: `onnxruntime` was deliberately **removed** during the packaging
work. Re-adding it needs to be a decision, not a drift back.

| | |
|---|---|
| Install | +35 MB |
| VRAM | **0** (CPU) |
| Quality | Below bge-reranker-v2-m3, well above raw cosine |
| Licence | Apache 2.0 / MIT — clean |

---

## Option 4 — no reranker; fix retrieval instead

Zero install, zero VRAM. Three things are available and none are built:

1. **Chunk-level scoring.** Ingest already chunks documents, and recall
   currently compares the query against whole records. Scoring chunks and
   taking a document's best chunk is a large gain for nothing.
2. **Score normalisation over the corpus.** The margin problem is that the
   *absolute* threshold is fixed while the score distribution shifts with
   corpus size. Comparing a candidate against the distribution of its own
   corpus — a z-score, or a gap-to-runner-up test, which the router already
   does for exemplars — is scale-free in the way a constant is not.
3. **The margin is already instrumented.** `test_recall_eval.py` prints it
   every run. Whether the problem is real at scale is measurable in an
   afternoon rather than arguable.

**This option is not "do nothing".** It is "measure at 10, 100 and 1,000
documents before spending 35 MB or 205 MB and a new dependency". The eval
corpus is five documents; nobody has seen the curve.

---

## What each option costs, together

| Option | Install | VRAM | Quality | Verdict |
|---|---|---|---|---|
| Ollama | 0 | 0.64 GB | — | **Broken**, and evicts the working set |
| sentence-transformers | +205 MB | +1.1 GB | Best | Contradicts the Docling decision |
| ONNX / flashrank | +35 MB | **0** (CPU) | Good | Viable |
| Retrieval fixes only | 0 | 0 | Unknown | **Measure first** |

---

## What the residency budget becomes

Whatever is chosen, **CLAUDE.md's `~1.8 GB` line is wrong today and should be
corrected to measured numbers**, because the fit gate sizes models against it:

- Embeddings resident: **0.66 GB** (measured, not 1.3)
- Reranker resident: **0 GB** — nothing runs
- On a 12 GB card, free for a chat model: **~11.3 GB**, not ~9 GB

That understatement is not harmless. `_vram_bytes` feeds a residency fit gate
that refuses models which do not fit; a budget overstating resident usage by
~1.1 GB refuses models that would have fitted, on the machine class the alpha
targets. The M5 lesson was that a wrong VRAM number silently disabled the gate;
this is the same failure from the other direction.

If Option 3 is taken the budget becomes 0.66 GB VRAM and ~150 MB of system RAM.
If Option 2, 1.76 GB — which is, by coincidence, roughly the number CLAUDE.md
already claims.

---

## Recommendation

**Option 4 now, Option 3 if the measurement justifies it.** In that order, and
the order matters.

The margin problem is real in principle and unmeasured in practice. Building
the eval at 10 / 100 / 1,000 documents costs an afternoon and the harness
already prints the number. Chunk-level scoring is very likely the bigger win
and costs nothing to install.

If the curve shows the margin closing, Option 3: 35 MB, no VRAM, CPU, clean
licence — the same shape of trade as Kokoro, and consistent with a product
that has just refused 321 MB for OCR.

Option 2 needs a stronger argument than "it is the best reranker", because the
thing standing between here and an alpha is an installer a stranger will
finish downloading.

**Do not revisit Option 1.**
