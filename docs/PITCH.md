# Zaram — Pitch

For grant applications and investor conversations. The vision lives in
`docs/VISION.md`; this is the version with a number attached.

**The blank in "Traction" is deliberate. Do not fill it with an estimate.**

---

## The opening

> **Zaram is the assistant you open every day, and the only one that keeps what
> it learns.**
>
> Everyone now uses three or four AIs and re-explains themselves to each. The
> memory lives with the vendor, locked to their model, and moving costs you
> everything you taught it.
>
> Zaram is the memory that stays put while the model changes. One knowledge base
> on your machine; your local models and your cloud keys both recall from it, and
> Zaram routes between them per question. You see what was recalled, you can
> correct it, and every byte that leaves is logged.
>
> **It never buys inference** — you bring the key or the model — so the cost of
> goods is approximately zero and the free tier is uncapped permanently rather
> than promotionally. Nothing funded by token margin can answer that.
>
> **The first vertical pack is obligations**, because it is the sharpest proof
> that memory is worth having: payment terms in an invoice, milestones in a
> contract, expiry on a quote — dates that live in a PDF in a folder and reach no
> calendar. Zaram extracts what you owe and what you're owed with the source
> clause attached, and acts before it's late. That is a pack on a universal base,
> not the product's boundary.

## Why this shape

Analysis of recent YC batches is blunt about the bar: an application that opens with
"AI for [vertical]" should be rewritten to lead with **the concrete job, the concrete
pain, and the dollar figure that pain costs the buyer this quarter.**

And the 2026 thesis shift: application-layer startups no longer pitch "AI that helps
your team work faster." They pitch **a function replaced entirely.**

So: narrow the wedge, never the vision. "Zaram is for freelancers" is wrong and
limiting. "Zaram starts with freelancers because that is where we prove it fastest,
and the mechanism is universal" is accurate and it is what gets funded.

> **Sharpened 16 August 2026.** Even that is now too narrow, and the daily-driver
> work is what showed it. The wedge is **not a segment, it is a demonstration**:
> point Zaram at a folder and have it tell you something true you did not know.
> That lands identically on a freelancer's invoices, a researcher's grant letters
> and a student's reading list, and it does not require picking one of them.
>
> The pitch that follows from it: **"every AI you use, in one place, that
> remembers you and tells you the truth about each one."** Universal,
> demonstrable in ten seconds, and structurally unavailable to any lab whose
> business is that your words leave. The invoice layer is the first *pack* on
> top — it is what proves the pack abstraction, not what defines the audience.
> See `CLAUDE.md`.

> **The second clause changed on 3 September 2026, and the line is now: "Every
> AI you use, in one place — that remembers you. Change the model, keep the
> memory."** The first half was never the problem. *"Tells you the truth about
> each one"* was carrying the data-policy labels, the routing attribution and
> the egress log, and it carried them badly: "each one" only resolves to "AI"
> on a second read, "truth" is a claim about our integrity rather than a
> benefit to the reader, and it puts the give-something-up framing in the one
> sentence that has to earn attention — which is the trade this file already
> says has capped every privacy product at a niche.
>
> **What replaced it is the product, stated as an instruction.** Change the
> model, keep the memory: portable, demonstrable in ten seconds, and it is what
> `CLAUDE.md` means by *"a model switch is not a leak in the story, it is the
> story"*. It also passes the test the old headline failed on 29 August — it
> makes no claim about what does or does not leave, so no future feature can
> make it false.
>
> The disclosure argument is not lost, it is **moved to where it is earned**:
> the site's "You should know what you're paying with" and "You can see exactly
> what left" sections, which state it with the evidence beside it rather than
> as an adjective. `CLAUDE.md` still carries the older phrasing in its
> acquisition-story paragraph; that version is not wrong, only earlier, and
> syncing it is a judgement for whoever next edits that file.

> **Corrected 29 August 2026, and the wrong version is worth keeping because it
> is the one that got out.** This line read *"…that remembers you and sends
> nothing anywhere"* for thirteen days, and it had been false since the cloud
> engine landed. Zaram routes to OpenRouter, sends images on the
> OpenAI-compatible path, and the acquisition story in `CLAUDE.md` is a
> first-run offer to paste a free Gemini key. A product that does all three
> cannot claim nothing leaves. Rule 7j says it from the other end: consent is
> granted per destination **and data class** and then *remembered* — a sentence
> that only makes sense about bytes going somewhere.
>
> **`CLAUDE.md` already had the right version and this file kept the wrong
> one.** There: *"everything you already use, in one place, and it tells you the
> truth about each one"*, with the reason attached — the privacy framing "asks
> someone to give something up", and that is the trade that has capped every
> privacy product at a niche. The honest pitch is the stronger pitch, which is
> what makes keeping the weak one expensive rather than merely untidy.
>
> **It reached a public page before anybody noticed**, which is the part worth
> recording. Two pitches sat in two files for thirteen days; a session building
> the launch site read both, used the correct line for a supporting claim, and
> put the false one in the `<h1>`. External framing is where a stale claim does
> its damage, so this file is the one that cannot carry a second version of the
> pitch "for now".

## The pain

> A working freelancer loses **___ hours a month** to unpaid admin and carries
> **___ in late invoices** at any moment.

**Get these from your own users, not from a report.** Ask fifteen people two
questions: how long did you spend on admin last month, and what are you owed right
now that is past due. Invented figures are the fastest way to lose a room.

## Why now

Small models finally run on hardware people already own, and document extraction
became reliable in the last eighteen months. The admin half of a small business is
finally automatable at zero marginal cost — because the user brings their own compute.

**Four things became true in 2026 that were not true in 2023. Every figure here is
sourced; check them before quoting them, because two of the four move.**

1. **Local crossed the "good enough" line — not the frontier line, and it does not
   need to.** Five of the eight jobs people actually use AI for — writing, editing,
   summarising, rewriting, translating — run well on a 12B model on hardware people
   already own. Measured here, not estimated: `gemma4` reads a full statement of
   work and an invoice photograph at **23.75 tok/s on a 12 GB RTX 3060**.

   > **The harness is the other half of "good enough", and this document did not
   > say so until 3 September 2026.** A model's score is a property of the model
   > *and the scaffolding around it*: the same weights move double digits on
   > public benchmarks depending on how the question is assembled — what context
   > is retrieved, in what order, how much of it fits, what the model is told
   > about itself, and what it is instructed to do when it does not know. That
   > scaffolding is called a harness, and it is most of the distance between a
   > good answer and a confident wrong one.
   >
   > **Zaram is a harness that arrives with the user's documents already in
   > it.** Not a plan — the parts are in the build and each one is a decision
   > somebody made: recall with a relevance floor and a shortlist cut, citations
   > numbered at the one point every source passes through, origin tagging so a
   > restatement is not mistaken for a source, a context budget computed per
   > model, identity and the date supplied as facts because a model cannot know
   > either, intent routing by embedding rather than by a second model call, and
   > a refusal path for the case where the context needed was not found.
   >
   > Two consequences, and the second is the one that is easy to miss.
   >
   > It is **why the "good enough" line above holds**: the 12B is not being
   > asked cold, and the comparison people imagine — small local model versus
   > frontier model — is not the comparison being run.
   >
   > And **it raises the cloud models too.** This is not a local-versus-cloud
   > argument. The same paid model answers better through Zaram than in its own
   > tab, because in its own tab it does not have the user's files, their last
   > three turns, or an instruction to stop when it does not know. That matters
   > for the reason the rest of this section already commits to: the claim is
   > additive and does not require anyone else to do badly.
   >
   > **No number is attached, deliberately.** The retrieval half is measured —
   > `test_recall_eval.py` and `test_recall_at_scale.py`, including at a
   > thousand documents. Answer quality end to end is **not**, and inventing a
   > figure here would be the same failure as filling in the Traction blank
   > below. An answer-level eval is two to three days of work; the version
   > worth having scores a model on *the user's own documents*, which is a
   > measurement no public leaderboard can offer and nobody without the files on
   > the device is positioned to make.

2. **AI conversations stopped being private, in court, this year.** In **January
   2026** a federal court affirmed an order requiring OpenAI to produce **20 million
   consumer chat logs**. OpenAI argued for a new *"AI privilege"* to shield them and
   was **refused**. In **February 2026** a court held that AI chats are **not**
   covered by attorney-client privilege. Courts have ordered the preservation of
   conversations users had already deleted. This is not a forecast about
   surveillance; it is the current legal position, and it is the strongest argument
   the product has ever had.

3. **The subscription price is not the cost.** Microsoft loses **more than $20 per
   user per month** on GitHub Copilot and up to **$80** on heavy users; OpenAI does
   not expect to break even before 2030.

   > **Do not say "cloud AI will get more expensive". It is the obvious claim and it
   > is false.** Per-token prices are collapsing — GPT-4-class went from ~$20 per
   > million tokens in late 2022 to ~$0.40 in early 2026, a median **50× decline per
   > year** by Epoch AI's measure. A reviewer who follows this will correct you.
   >
   > The true version is narrower and survives a price cut: **total spend rises
   > faster than prices fall, because usage grows** — Uber exhausted its *annual*
   > token budget in four months — and **frontier pricing has doubled since January
   > 2026** even while budget tiers fall. Whatever the headline rate does, the bill
   > is metered and outside the user's control. A model on your own machine is a
   > fixed cost already paid. That argument cannot be falsified by a price war;
   > the prediction can.

   **The subsidy is real; the "and then they raise prices" is not — and the
   sharper reading is better for us anyway.** The losses are documented: Microsoft
   loses **$20–80 per user per month** on Copilot, OpenAI does not break even
   before 2030, Anthropic's gross margin was **−94% in 2024**. But the
   loss-leader-then-extract play needs a monopoly at the end of it, and there
   isn't one: five credible labs, OpenAI reportedly weighing *price cuts* to fight
   Anthropic, and Anthropic reaching ~60% margin through **efficiency rather than
   price rises**. Above all, **open weights are a permanent ceiling** — a user who
   can run Gemma on their own disk cannot be gouged, because the substitute is
   already installed.

   So they may never need to raise the price, **because the price was never the
   point**. The return on subsidising a user is their data now
   (`DataPolicy.LOGGED_AND_TRAINED_ON` — *"every free tier is this"*) and a
   switching cost that compounds daily. The lock-in is **memory**, not money, and
   it is being built deliberately.

   **State this as the position, because it is the one that cannot be argued
   down: Zaram does not need cloud AI to fail.** Cheaper and better cloud is a
   destination Zaram routes to, with the memory still on the user's machine.
   Expensive or restrictive cloud is a reason to stay local. Either way people use
   more than one and the memory should be theirs. A thesis that requires
   competitors to do badly is fragile; this one does not.

4. **Memory is the lock-in, and no vendor will unlock it.** Every provider is
   building memory that works only with their own model. That is not an oversight,
   it is the switching cost. A memory layer that works *across* competitors is
   against every vendor's interest permanently — so it can only come from outside
   them, which is the whole reason this company can exist at all.

## Why us

A working 3D artist in Lagos who has this problem daily, building for a market where
dollar-priced tools are unaffordable and the admin gap is widest. Solo is not a
disqualifier — 22 of 199 companies in YC W26 were solo founders.

## Why it cannot be copied

Project tools require you to type the data; that is why they are abandoned. Zaram
extracts it from documents it helped produce.

No model provider will ship a memory that works equally well with a competitor's
model. No company whose business is that your data leaves can promise that it did not.

**And a harness is copyable; a harness with the user's documents in it is not.**
Anyone can write better scaffolding — prompt construction, retrieval, a tool loop.
What decides the answer is what that scaffolding has to reach for, and that is the
user's own material, indexed on their machine. A wrapper around somebody's API can
copy every technique in the build and still start every conversation with nothing
to retrieve.

## Traction

> ____

---

## The honest gap

Of the top 20 companies in YC W26 by traction, **18 had paying customers at Demo Day**,
and three times as many companies reached $1M annualised revenue as the batch before.

A pitch with no users does not get read, however good the prose. Everything else here
is strong — a working artifact, verified cross-model recall, an architecture nobody has,
real domain expertise. The missing element is the only one that cannot be written.

**Shortest path:** ship the invoicing and expenses layer, get fifteen freelancers using
it, and after sixty days write:

> *"Users recovered £___ in invoices they would have chased late, and cut ___ hours of
> admin a month."*

That sentence is worth more than every other paragraph combined. It is four to eight
weeks of work already on the roadmap.

## Sequence: grants first, then users, then venture

88% of AI venture dollars in H1 2026 went to US companies, and non-US AI startups face
a structural disadvantage in accessing growth capital. YC recruits internationally, but
the pool outside the US is smaller and more risk-averse.

Grants screen on mission, novelty and open source rather than traction — and Zaram fits
unusually well. Targets worth researching:

- **NLnet / NGI Zero** (EU) — open-source privacy and internet-freedom tech, grants
  roughly €5k–50k, genuinely accessible to solo developers. Provable non-egress is
  squarely their thesis.
- **Mozilla Foundation** — open source, trustworthy AI
- **Open Technology Fund** — privacy and data sovereignty
- **African tech and Global South funds** — where being in Lagos is an advantage
  rather than a discount

A grant buys runway without dilution and funds the months needed to produce the
traction number that makes the venture pitch land. Trying it in the other order means
pitching without the one thing being screened for.

*Verify every programme's current status and terms before applying — these change.*

## The ownership argument — added 29 August 2026

**A hosted model is rented, and in June 2026 the rent was cancelled with three
days' notice.**

Anthropic shipped Claude Fable 5 and Mythos 5 on 9 June — its two most capable
models. On 12 June a US federal export-control order barred access by any foreign
national anywhere, including Anthropic's own foreign-national staff. Nationality
cannot be verified live, so **both models were disabled worldwide, for everyone,
paying US customers included.** The order was lifted on 30 June and access
restored on 1 July: eighteen days, no appeal, no warning.

This is the strongest version of the argument because it is none of the things a
sceptic can dismiss. Not a poor-connectivity story, not an authoritarian-government
story, not a developing-market story. The best model in the world, switched off
globally, by the government of the country that built it.

It is not the only door, and the others matter for this market specifically:
sanctions cut Iran, Cuba, North Korea and Syria off entirely; OpenAI withdrew from
Hong Kong in July 2024; **fifteen African countries shut the internet off
thirty-six times in 2025**, and Nigeria blocked Twitter for **seven months** in
2021–22, a ban the ECOWAS Court later found unlawful — after it had run its course.

**Be exact about what survives, because overclaiming here would be the same
failure the product exists to refuse.** Zaram's cloud routing stops in every one
of those scenarios; that half was always somebody else's. What keeps working is
the model on the disk, the documents, and everything Zaram has learned about the
work — and rule 7 makes the Spine exportable in an open format, so the memory
outlives the provider, the order, and Zaram itself.
