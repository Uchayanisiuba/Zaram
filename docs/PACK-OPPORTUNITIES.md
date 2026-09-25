# Pack: opportunities — jobs and grants

**Written 25 September 2026.** The second pack, which is the one `CLAUDE.md`
has been waiting for: *"Build two packs by hand before building the pack
system. The abstraction cannot be designed from imagination — only from two
real examples and the friction between them."* The business layer is pack one.
This is pack two, and it is deliberately differently shaped — pack one works on
documents the user already has, this one works on documents that arrive on a
timer from outside.

Read with `CLAUDE.md` (the rules) and `docs/MILESTONES.md` (the status).

---

## The one decision everything else follows from

**Automate discovery, eligibility and the first draft. Never automate
submission.**

This is not caution. It is where the people running the funding have already
drawn the line, and building against their grain would be building on sand.
Grants.gov's own API documentation says it in as many words: write operations
are not supported, *"you cannot apply for funding"* through the API. The EU
Funding & Tenders Portal is the same shape — a public Search API for calls,
topics and metadata, and no submission endpoint anywhere. These are the
funders. They built the discovery half deliberately and did not build the
other half deliberately.

Three of Zaram's own rules land on the same line independently, which is
usually a sign the line is real:

* **Rule 9** — *generation must fail rather than invent.* A cover letter
  claiming twelve direct reports when the CV says five is not an awkward
  sentence, it is a false statement sent to a stranger under the user's name.
  `CLAUDE.md` already says why this case is the dangerous one: *"a wrong reply
  is corrected in the next turn; a wrong document is sent to a client."*
* **Rule 6 and 7j** — autonomy is granted, never defaulted, and the hard stop
  is kept for the case that earns one. An outbound application is that case.
* **The mutative tier** — a submission cannot be undone. There is no sandbox
  for a funder's portal and no rollback for an employer's inbox.

So the deliverable is a **review queue**: the work is done, the draft is
written, the evidence is attached, and a person presses send. One tap, not a
form. The tap is not friction — it is the only part that cannot be delegated,
and everything before it is the product.

**What the user may grant on top of that**, by name, per destination and data
class, under rule 7j: auto-send to a destination they have already reviewed at
least one application to. Never on by default, never for a destination that has
not had a CV before.

---

## Jobs and grants are one pipeline with the weights moved

This is the design finding, and it is what makes the pack abstraction real
rather than imagined. They look like one problem and they are — but the
bottleneck sits in a different place, and a build that treats them identically
gets both wrong.

| | Jobs | Grants |
|---|---|---|
| Volume | hundreds a year | five to twenty |
| Value each | low | very high |
| **Bottleneck** | draft quality at volume | **eligibility**, then reuse |
| Deadlines | rolling | hard, months out, missed means next year |
| Submission | email or an ATS form | authenticated portal, often institutional sign-off |
| Cost of a bad one | ignored | a fortnight gone, sometimes barred from re-applying |
| Memory earns its keep by | *"you applied here in March; Sara replied"* | *"here is the impact statement that won last time"* |

For jobs, discovery is easy and every application is generic. For grants it
inverts: most people do not know what they are eligible for, and the writing is
mostly restating things they have already written.

**One pack, two project types.** `ProjectType.JOBS` and `ProjectType.GRANTS`
activate the same code with different weights. Two packs sharing a pipeline
would be two copies of it within a month.

---

## Eligibility is a gate, never a ranking

The highest-value component in the pack, and the reasoning for it already
exists in this codebase in a different domain. `CLAUDE.md`'s routing section:
*capability is "a binary precondition, never a score"* — a model that cannot
accept an image is not a worse answer to a question about a screenshot, it is
not an answer.

Eligibility is exactly that shape. Country of residence, organisation type,
career stage, sector, whether an institutional host is required: these are
**hard filters**, read from the call text and checked against facts already in
the Spine. Blend eligibility into a relevance score and the user spends a
fortnight on a call that needed a university affiliation they do not have.

This is the same error `CLAUDE.md` records costing this codebase three times —
a score built for ranking used to decide something. It is written down here
before the first line of the matcher, rather than after the fourth time.

**The verdict is a sentence, not a number.** *"Not eligible — this one needs a
registered non-profit, and your profile says sole trader."* Because it names
the clause it read, rule 2 makes it correctable: if the gate is wrong, one
correction fixes it and every future call re-evaluates. A gate that cannot be
argued with is a gate people route around.

**Unknown is a third answer and is not "no".** A criterion the user has no fact
for comes back as a question, never as an exclusion — the same shape
`obligations.Unresolved` already takes, and for the same reason. Silently
excluding on a fact nobody entered is how a product quietly stops showing
somebody the thing they needed.

---

## The reuse library

Grant applications are six components recombined: bio, track record, impact
statement, methodology, budget justification, references. A memory product is
the native home for that, and it is where this pack stops being a job board
with a mail merge.

Each component is a fact with provenance, versions, and a record of which
application it went into. Which means:

* **Rule 9 does real work.** Nothing enters a draft that does not trace to
  something the user wrote. An unanchored claim in a funding application is not
  embarrassing, it is fraud-adjacent.
* **Rule 4 compounds.** Correct how you describe your track record once and the
  next eleven applications inherit it.
* **Rule 7i scopes it.** Components are `project:<id>`; *how the user writes* is
  `global`, promoted on evidence when the same voice correction lands in three
  different projects.

---

## Sources: feeds, not sites

**The poller takes feeds. It does not have a list of websites in it.**

A hardcoded site list is wrong twice over. It makes adding a funder a release,
and it silently makes the product useless outside the countries whose funders
somebody remembered — which for grants, where funding is intensely geographic,
is most of the world. The market this project is closest to is one where every
hardcoded list would be missing.

A feed is one of four things, and each is a row of config a user can add:

| Kind | What it is |
|---|---|
| `json` | A documented REST endpoint — Grants.gov, EU Funding & Tenders |
| `rss` | Any board's feed |
| `ats` | A Greenhouse / Lever / Ashby board token for one company |
| `mail` | A label in the user's own inbox that job or funder alerts land in |

### Why not LinkedIn, Indeed, ArtStation

Not a Zaram rule — their rule. There is no public API to search or read
LinkedIn jobs; the Job Posting API is partner-gated, for *publishing*, and
closed to new partners. Every "LinkedIn Jobs API" on the market is a scraper
wrapping the public pages, at $45 to $30,000 a month.

Three reasons that route is refused, in order of how much they matter:

1. **It gets the user's own account restricted.** A logged-in scrape is
   attributable to the person whose session it is, and the worst outcome for
   somebody job-hunting is losing the account they are hunting with. Zaram
   would be the cause.
2. **It gives Zaram a cost of goods per user** — the structure `CLAUDE.md`
   refuses when it says hosting would *"route user data through its own
   infrastructure and become the trade the product exists to refuse."*
3. **It breaks constantly**, which is the same reasoning already applied to
   driving consumer web apps: *"shatters on every UI change."*

On the law specifically, so this is not overstated: in *hiQ v. LinkedIn* the
Ninth Circuit held that scraping public pages likely does not violate the CFAA.
That means *not a federal crime*. It is not permission — the terms still
prohibit automated access as a matter of contract, and accounts are still
terminated.

**The user gets those sites anyway, by three better routes:**

* **Upstream.** Much of what appears on LinkedIn and Indeed is syndicated
  *from* the company's ATS. Polling the ATS gets the same job earlier, with a
  direct apply link and a clean structured record.
* **Let them push.** LinkedIn, ArtStation and nearly every board send alert
  emails. The user subscribes normally, as themselves, and Zaram reads *their
  own inbox*. No terms broken, no bot detection, no account risk — and it
  scales to every board on earth without a single integration.
* **The ambient surface.** The user is looking at a listing, presses the
  hotkey, Zaram reads the selection. `CLAUDE.md` already specifies this and its
  constraint: *invoked, never passive.* Their screen, their session, their
  click.

### One gotcha, written down before somebody hits it

**UKRI's Gateway to Research is not a feed of open calls.** It is a database of
*already-awarded* funding. A reasonable-looking integration pulls thousands of
records and matches the user against grants that closed years ago — working
code, plausible output, completely useless, and green tests throughout. Open
UKRI opportunities live elsewhere. This is exactly the failure mode the working
agreement is built around, so it is a comment in the source as well as a line
here.

---

## Consent and the log

Nothing here needs new machinery. It is the existing rules applied to a new
kind of traffic:

* **Every fetch is an egress entry** (rule 3). The poller running at 06:00 and
  asking Grants.gov for new calls appears in Activity like anything else.
* **Every feed is a governed source** (rule 5). Default deny; a host nobody
  named is refused. Adding a feed is the per-item decision, revocable in
  Settings.
* **A CV is its own data class** (rule 7j). It carries an address, a phone
  number and an employment history. Connecting an email account for text is not
  consent to send it a CV. Asked once per destination, then remembered, and in
  the log by name.
* **A posting is untrusted third-party text.** `core/untrusted.py` already
  exists and is already called from recall. A job description is written by a
  stranger and lands next to the model's decision; it may never widen what a
  tool is allowed to do. Same rule as a tool description, same scanner.

## The quiet cycle

The poller runs and usually finds nothing. **When it finds nothing it says
nothing.** `CLAUDE.md`: *"Zaram speaks first only when it has something real"*,
and no engagement mechanics, ever — no streaks, no "you haven't applied to
anything this week". The orb shows that it ran. That is the whole report.

Twelve hours is the default interval and it is a setting, not a constant.
Grants move on a scale of months; polling a funder's API every hour is a way to
get rate-limited for no information. Grants.gov allows 60 requests a minute and
10,000 a day per key, which is generous enough that the restraint is about
usefulness rather than about limits.

---

## What ships in what order

Everything before the sender is **generative tier** — it writes new artifacts
and can destroy nothing — so it needs no undo, no confirm and no sandbox, and
each step is useful on its own.

1. **Contracts, eligibility, feeds, source adapters.** Useful alone: *"what am
   I actually eligible for?"* — built 25 September, this document's companion
   commit.
2. **The poller and the matcher.** Membership on relevance alone; ordering may
   blend. Useful alone: a filtered feed that knows your CV.
3. **Deadlines become obligations.** No new machinery — `obligations/` already
   does dated commitments with a source clause and a correction loop.
4. **The reuse library and the drafter**, with claim anchoring, into the review
   queue. **Stop here for v1.** The user copies the letter out themselves, and
   90% of the value has shipped with 10% of the risk.
5. **The sender**, last, because confirm, undo and sandbox are the work rather
   than the permission.

**Grants before jobs**, despite jobs sounding easier. The grant APIs are open
and free, the eligibility gate is the hardest and most valuable piece so it
teaches the most, and the value per successful application is high enough that
a rough first version still earns its place.

---

## Rejected, recorded so they do not return

* **Auto-submission.** See the top of this file. The funders did not build it.
* **Scraping LinkedIn / Indeed, or buying a scraping API.** Account risk, cost
  of goods, permanent breakage.
* **A hardcoded source list.** Makes the product regional by accident.
* **Eligibility as a score.** The documented three-time error, in a new domain.
* **Separate jobs and grants packs.** Two copies of one pipeline within a month.
* **A seventh node.** Opportunities are a project type, and what they produce
  is work, deadlines and facts — which is Work, Activity and Memory, all of
  which exist.

## Sources

* [Simpler.Grants.gov API](https://wiki.simpler.grants.gov/product/api) —
  read-only by design, rate limits, no submission
* [EU Funding & Tenders Portal APIs](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis)
* [UKRI Gateway to Research](https://gtr.ukri.org/) — awarded funding, not open calls
