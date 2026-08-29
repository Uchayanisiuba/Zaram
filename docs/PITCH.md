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
