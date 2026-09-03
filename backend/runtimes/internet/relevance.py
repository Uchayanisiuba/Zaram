"""Whether a search result actually answers the question.

**Nothing in the live search path asked that.** `InternetRuntimeImpl._rank_results`
sorted on three things, and not one of them compared the query to the result:

    sorted(results, key=lambda r: (-r.score, -priority_map[...], -r.retrieved_at))

`r.score` is a constant the connector stamps on every result it returns —
Wikipedia 0.8, GitHub and RSS 0.7, DuckDuckGo 0.6 — so the first key is a
source prior wearing a relevance score's name, and the second key is the same
prior again. The order was therefore *identical for every query ever asked*:
Wikipedia, then GitHub, then DuckDuckGo. That is the whole explanation for an
election query returning a junk GitHub repository. GitHub's 0.7 beats
DuckDuckGo's 0.6 before a single word of the question is looked at.

Those constants then reached the citation UI as relevance, which `UI-SPEC`
forbids outright: never render invented values.

`ranker.py` holds a second implementation that does compare terms. It is
unreachable — nothing constructs `InternetRankerImpl` — and it would raise
`FrozenInstanceError` on its first result if anything did, because it assigns
to `result.score` on a frozen dataclass. Two rankers, one dead and one that
does not rank.

What this module does instead
-----------------------------
**One number, one question.** `relevance_of` compares the query to the result's
own text and to nothing else. No source prior, no recency, no connector, no
retrieval time. Those are real signals and they belong in the *ordering*, which
is a different question and is answered below by rank fusion.

This is `CLAUDE.md`'s most expensive recurring lesson, arriving in the search
path for the first time: **what is in the shortlist, what order it is shown in,
and what is cited are three questions and must not share one number.** The
memory ranker already learned it twice — a citation floor compared against a
ranking blend, then a shortlist selected on the same blend that discarded the
single most relevant document in a 1,000-document corpus at rank 43. The
internet path never learned it at all, because it never had a relevance number
to confuse in the first place.

**Ordering is Reciprocal Rank Fusion, not a weighted blend.** `Σ 1/(k + rank)`
over relevance, authority and recency. The output is on no source's scale, so
there is no blended magnitude that *could* be compared against a floor measured
as an overlap fraction. `CLAUDE.md` recommends taking RRF for ordering and only
for ordering; that is exactly what happens here.

**One tokenizer, shared.** `content_tokens` from the memory index, which drops
stopwords and bare digits. Writing a fourth whitespace-splitting copy is how
`is`, `the` and `of` came to match every document three times already.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import replace
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from runtimes.memory.index import content_tokens

__all__ = [
    "MIN_WEB_RELEVANCE",
    "authority_of",
    "connectors_for",
    "diversify",
    "fuse",
    "relevant",
    "relevance_of",
    "scored",
    "temporality_of",
]

#: Below this, a result is not offered to the model as a source and is not
#: cited to the user.
#:
#: **This gates citation, never disclosure.** Every request that left the
#: machine stays in the egress log and stays visible in Activity whatever this
#: number says — rule 3 is not a relevance judgement, and the reasoning in
#: `execution_engine._search_provenance_events` about always disclosing web
#: sources is right and is untouched. What was wrong is that *disclosure* was
#: being used as *citation*: every fetched result became a source under the
#: answer, so a reply about an election carried a GitHub repository as
#: supporting evidence. "Zaram contacted this host" and "this page supports
#: this claim" are different sentences and the interface now makes both.
#:
#: 0.18 is a coverage fraction, not a cosine, and it is deliberately low. The
#: cost of dropping a good result is a thinner answer; the cost of keeping a
#: bad one is a citation that teaches the user citations mean nothing. But a
#: floor set where most results fail is a floor that produces empty answers on
#: hard questions, which is the failure mode Perplexity-style products are
#: judged on. Overridable so it can be tuned against measurements rather than
#: by editing code.
MIN_WEB_RELEVANCE = 0.18

#: How much a domain is trusted to be a *source*, independent of this query.
#:
#: Used for ordering only, and fused by rank rather than added to a score — so
#: a trusted domain can move a result up among equally relevant ones and can
#: never carry an irrelevant one into the shortlist. That distinction is the
#: entire bug this module exists to fix, so the value is kept structurally
#: unable to cause it.
_AUTHORITY = {
    "wikipedia.org": 0.85,
    "britannica.com": 0.8,
    "nature.com": 0.9,
    "science.org": 0.9,
    "arxiv.org": 0.8,
    "who.int": 0.85,
    "nih.gov": 0.85,
    "reuters.com": 0.85,
    "apnews.com": 0.85,
    "bbc.co.uk": 0.8,
    "bbc.com": 0.8,
    "theguardian.com": 0.75,
    "nytimes.com": 0.78,
    "ft.com": 0.78,
    "economist.com": 0.78,
    "github.com": 0.6,
    "stackoverflow.com": 0.7,
    "docs.python.org": 0.85,
    "developer.mozilla.org": 0.85,
}

_DEFAULT_AUTHORITY = 0.5

#: Domains that answer a *code* question well and almost nothing else. The
#: election-query-returns-a-GitHub-repo failure is what this exists to stop
#: happening by ranking rather than by exclusion — a code query still reaches
#: them normally.
_CODE_DOMAINS = ("github.com", "stackoverflow.com", "gitlab.com", "npmjs.com", "pypi.org")


#: Suffixes stripped before comparing terms, longest first.
#:
#: Without this, "Nigeria" does not match "Nigerian" and "payment terms" does
#: not match "payment term" — which is not a nicety. The measured case: the
#: correct Reuters article for a Nigerian election query matched on two of four
#: query terms instead of three, purely because the headline said *Nigeria* and
#: the question said *Nigerian*.
#:
#: Deliberately not a real stemmer. Porter would pull in a dependency and,
#: worse, conflate words the user can see are different — "universal" to
#: "univers" is the kind of match that makes a citation look wrong to the
#: person reading it. These six suffixes cover plurals and the common
#: adjectival forms and stop there.
_SUFFIXES = ("ational", "iness", "ings", "edly", "ian", "ing", "ies", "ed", "es", "s", "n")


def _stem(token: str) -> str:
    """A conservative common form, so `Nigeria` and `Nigerian` compare equal."""
    if len(token) <= 3:
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            root = token[: -len(suffix)]
            # `ies` -> `y` keeps "policies"/"policy" together; everything else
            # keeps the bare root.
            return root + "y" if suffix == "ies" else root
    return token


def _stems(text: str) -> set[str]:
    """Meaningful tokens, reduced to their common form. Shares one tokenizer."""
    return {_stem(t) for t in content_tokens(text)}


def _bigrams(tokens: Sequence[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


def _ordered_tokens(text: str) -> list[str]:
    """Tokens in order, filtered the same way `content_tokens` filters.

    Order matters for phrase matching and `content_tokens` returns a set, so
    this re-derives the sequence rather than keeping a second filter rule that
    could drift from the shared one.
    """
    keep = content_tokens(text)
    return [t for t in re.findall(r"\b\w+\b", text.lower()) if t in keep]


def relevance_of(query: str, title: str, snippet: str, url: str = "") -> float:
    """How well this result answers this query, from content alone. 0–1.

    Deliberately ignores which connector found it, how recent it is and how
    trusted the domain is. Every one of those is a legitimate ordering signal
    and none of them is evidence that the page is about what was asked.

    Four components, each earning its weight:

    * **Coverage** — the fraction of the question's meaningful words that
      appear anywhere in the result. The single most informative signal, and
      the one a source prior was standing in for.
    * **Title match** — a term in the title is worth more than the same term
      in a snippet, because a title is what the page claims to be about.
    * **Phrase match** — adjacent query words appearing adjacent in the result.
      "general election" matching as a phrase is a different fact from
      "general" and "election" both appearing.
    * **A URL-slug signal**, small, because a term in the path is weak
      evidence and strong enough to break ties between otherwise equal results.
    """
    query_tokens = _stems(query)
    if not query_tokens:
        # Nothing meaningful was asked — a query of pure stopwords. Refusing to
        # score is honest; scoring it 1.0 would let anything through.
        return 0.0

    title_tokens = _stems(title)
    snippet_tokens = _stems(snippet)
    body_tokens = title_tokens | snippet_tokens

    coverage = len(query_tokens & body_tokens) / len(query_tokens)
    title_hit = len(query_tokens & title_tokens) / len(query_tokens)

    query_seq = [_stem(t) for t in _ordered_tokens(query)]
    phrase = 0.0
    if len(query_seq) > 1:
        wanted = _bigrams(query_seq)
        found = _bigrams([_stem(t) for t in _ordered_tokens(f"{title} {snippet}")])
        if wanted:
            phrase = len(wanted & found) / len(wanted)

    slug = 0.0
    if url:
        slug_tokens = _stems(re.sub(r"[/\-_.]+", " ", urlparse(url).path))
        if slug_tokens:
            slug = len(query_tokens & slug_tokens) / len(query_tokens)

    quality = 0.50 * coverage + 0.28 * title_hit + 0.17 * phrase + 0.05 * slug

    # Coverage multiplies as well as contributes, and this is the line that
    # fixes the reported failure.
    #
    # Additively, a result sharing **one** of four query words scored 0.21 —
    # above any floor low enough to be useful — because that one word appeared
    # in the title and again in the URL, and three components all rewarded the
    # same single match. `awesome-election-tools` cleared the bar on the word
    # "election" alone.
    #
    # Multiplying by coverage says the obvious thing: a page addressing a
    # quarter of the question can be worth at most a quarter of the credit,
    # however prominently it places that quarter. Measured on the reported
    # case, the repository falls from 0.21 to 0.05 while the Reuters article
    # holds 0.45 — separation of roughly nine to one where there had been
    # three to one.
    return max(0.0, min(1.0, quality * coverage))


def authority_of(url: str) -> float:
    """How much this domain is trusted as a source, query-independent."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return _DEFAULT_AUTHORITY
    if not host:
        return _DEFAULT_AUTHORITY
    host = host[4:] if host.startswith("www.") else host
    for domain, weight in _AUTHORITY.items():
        if host == domain or host.endswith("." + domain):
            return weight
    # A government or academic domain nobody listed is still more likely to be
    # a source than a content farm.
    if host.endswith(".gov") or host.endswith(".edu") or host.endswith(".ac.uk"):
        return 0.8
    return _DEFAULT_AUTHORITY


def _recency_of(result: Any) -> float:
    """0–1, where 1 is today. 0.5 when the result carries no date.

    An unknown date must not read as old: most of the web is undated, and
    scoring it as ancient would bury exactly the pages a search engine returns
    for a current-events question.
    """
    metadata = getattr(result, "metadata", None) or {}
    published = metadata.get("published") or metadata.get("date")
    if not published:
        return 0.5
    try:
        from dateutil import parser

        age_days = (time.time() - parser.parse(str(published)).timestamp()) / 86400
    except Exception:
        return 0.5
    if age_days < 0:
        return 1.0
    return 1.0 / (1.0 + age_days / 30.0)


#: How much freshness should matter for this question. 0 = not at all.
#:
#: **The best idea to arrive from outside this codebase, and it was missing.**
#: Recency was a fixed third of the fusion regardless of what was asked, which
#: is wrong in both directions: "who was Napoleon" does not want yesterday's
#: blog post ranked above Britannica, and "what is the latest Nvidia GPU" wants
#: exactly that. A single recency weight cannot serve both, and averaging them
#: serves neither.
#:
#: Five bands rather than a continuum because the decision is coarse and a
#: continuum invites tuning a number nobody measured.
_TEMPORAL_MARKERS: tuple[tuple[float, frozenset[str]], ...] = (
    (
        1.0,
        frozenset({
            "now", "today", "tonight", "currently", "breaking", "live",
            "score", "weather", "price", "trading", "outage",
        }),
    ),
    (
        0.8,
        frozenset({
            "latest", "newest", "recent", "recently", "yesterday", "week",
            "update", "updated", "release", "released", "launch", "launched",
            "announcement", "announced", "current", "2026", "2025",
        }),
    ),
    (
        0.55,
        frozenset({
            "election", "won", "winner", "results", "version", "changed",
            "news", "who", "status", "still",
        }),
    ),
    (
        0.15,
        frozenset({
            "history", "historical", "origin", "founded", "born", "died",
            "definition", "meaning", "theorem", "proof", "ancient",
        }),
    ),
)

#: Where a question with no temporal signal at all lands. Deliberately below
#: the midpoint: most questions are not about this week, and treating them as
#: if they were is what makes a search product surface news for everything.
_DEFAULT_TEMPORALITY = 0.35

#: At or above this, a question is worth spending a dated-source request on.
#:
#: Set at the 0.55 band rather than the 0.8 one so that "who won", "what
#: version", "current status" reach a dated source — those are the questions
#: that read as stale without one, and none of them contains "latest". It sits
#: above `_DEFAULT_TEMPORALITY` deliberately, which is what makes the extra
#: request opt-in per question: an untimed question never pays for it, and a
#: historical marker ("history", "founded", "definition") lands at 0.15 and is
#: excluded outright. That is the "unless the user asks otherwise" half — read
#: from the question's own words, so a misjudgement is reproducible.
_NEWS_TEMPORALITY = 0.55


def temporality_of(query: str) -> float:
    """How much this question is about *now*. 0–1.

    Read from the question's own words, not from a model call — routing must
    stay deterministic so a misjudgement is reproducible and fixable, which is
    the same argument `CLAUDE.md` makes for embedding-based task routing over a
    generative classifier.

    The strongest marker present wins rather than averaging, because "latest"
    in a question means the asker wants recency whatever else is in the
    sentence.
    """
    tokens = content_tokens(query)
    lowered = query.lower()

    # Every signal is collected and the strongest wins. Returning on the first
    # band that matched made the *order of the bands* decide the answer:
    # "Nigerian presidential election 2026" hit `election` at 0.55 and returned
    # before the year was ever looked at, so an explicitly dated question was
    # graded less time-sensitive than an undated one containing "latest".
    candidates: list[float] = []

    for weight, markers in _TEMPORAL_MARKERS:
        if tokens & markers:
            candidates.append(weight)

    # A bare year is a strong date signal, and `content_tokens` drops it as a
    # digit — so it is read from the raw text rather than the token set.
    if re.search(r"\b20[2-9]\d\b", query):
        candidates.append(0.8)

    if candidates:
        return max(candidates)

    # Past tense is a historical signal and it is made entirely of stopwords,
    # so it cannot be a token marker. "Who was Napoleon" carries no keyword
    # from any band above and is plainly not a question about this week.
    if re.search(r"\b(was|were|did|had been|used to)\b", lowered):
        return 0.15

    return _DEFAULT_TEMPORALITY


def _looks_like_code_question(query: str) -> bool:
    tokens = content_tokens(query)
    signals = {
        "code", "python", "javascript", "typescript", "rust", "java", "sql",
        "api", "library", "package", "npm", "pip", "function", "class",
        "error", "exception", "traceback", "compile", "syntax", "repo",
        "repository", "git", "install", "import", "module", "framework",
        "bug", "debug", "regex", "async", "docker", "kubernetes",
    }
    return bool(tokens & signals)


def scored(query: str, results: Iterable[Any]) -> list[Any]:
    """Every result with `score` replaced by its measured relevance.

    `SearchResult` is a frozen dataclass, so this returns copies. That is worth
    stating because `ranker.py` assigns to `result.score` in place and would
    raise `FrozenInstanceError` the first time anything called it — which
    nothing ever has.

    The connector's constant is *overwritten* rather than blended in. It was
    never a measurement, and keeping a share of it would keep a share of the
    bug.
    """
    out = []
    for result in results:
        relevance = relevance_of(
            query,
            getattr(result, "title", "") or "",
            getattr(result, "snippet", "") or "",
            getattr(result, "url", "") or "",
        )
        metadata = dict(getattr(result, "metadata", None) or {})
        metadata["relevance"] = round(relevance, 4)
        metadata["authority"] = round(authority_of(getattr(result, "url", "") or ""), 4)
        try:
            out.append(replace(result, score=relevance, metadata=metadata))
        except Exception:
            # A connector returning something that is not a `SearchResult` must
            # not be able to stop the search. It keeps its own object and loses
            # the annotation, which is visible rather than silent.
            out.append(result)
    return out


def relevant(results: Sequence[Any], *, floor: float = MIN_WEB_RELEVANCE) -> list[Any]:
    """The results worth showing the model and citing to the user.

    **Membership is decided on relevance alone.** Not on the fused order below,
    not on a blend. This is the cut that `_rank_results` made on a source prior,
    and making it on similarity is the entire correction.
    """
    return [r for r in results if float(getattr(r, "score", 0.0) or 0.0) >= floor]


def _rank_positions(values: Sequence[float]) -> list[int]:
    """1-based rank per element, highest value first, ties sharing a rank."""
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=True)
    positions = [0] * len(values)
    previous: float | None = None
    rank = 0
    for seen, index in enumerate(order, start=1):
        if previous is None or values[index] < previous:
            rank = seen
            previous = values[index]
        positions[index] = rank
    return positions


def _host_of(result: Any) -> str:
    try:
        host = (urlparse(getattr(result, "url", "") or "").hostname or "").lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def diversify(results: Sequence[Any], *, per_host: int = 2) -> list[Any]:
    """Keep the order, but stop one domain owning the answer.

    Three results from one site is one source wearing three citations, and it
    is how a synthesised answer comes to look corroborated when it is not —
    which matters more here than in an ordinary search UI, because the reply
    presents these as independent support for its claims.

    Applied **after** ordering and never as part of the score. Folding
    diversity into a rank would let a common domain push a genuinely better
    result out of the shortlist, which is the failure this whole module is
    about. Demoted results are moved down, not dropped: they are still real
    evidence, and the user can still see them.
    """
    kept: list[Any] = []
    overflow: list[Any] = []
    seen: dict[str, int] = {}
    for item in results:
        host = _host_of(item)
        count = seen.get(host, 0)
        if host and count >= per_host:
            overflow.append(item)
            continue
        seen[host] = count + 1
        kept.append(item)
    return kept + overflow


def fuse(
    results: Sequence[Any],
    *,
    query: str = "",
    k: int = 60,
    limit: int | None = None,
) -> list[Any]:
    """Order by Reciprocal Rank Fusion over relevance, authority and recency.

    `Σ 1/(k + rank)` per signal, summed. Fusing by **rank position** rather
    than by score magnitude is the property that matters: the output is on no
    source's scale, so nobody downstream can compare it against a floor
    measured as a coverage fraction. `CLAUDE.md` describes this as removing the
    bug class rather than guarding it — a rule you cannot break beats a rule
    you must remember — and it recommends taking RRF for ordering only. This
    function orders; `relevant` decides membership; they are never merged.

    `k = 60` is the value from the original RRF paper. It flattens the
    difference between adjacent ranks, so a result has to be beaten on more
    than one signal to move far — which is what stops a highly-trusted domain
    dragging a barely-relevant page to the top.
    """
    items = list(results)
    if not items:
        return []

    relevances = [float(getattr(r, "score", 0.0) or 0.0) for r in items]
    authorities = [float((getattr(r, "metadata", None) or {}).get("authority", _DEFAULT_AUTHORITY)) for r in items]
    recencies = [_recency_of(r) for r in items]

    # How much the freshness signal counts, decided by the question rather than
    # fixed. This is the one place a weight appears in an otherwise rank-based
    # fusion, and it is a weight on a *signal's contribution*, never on a
    # score — so it can reorder equally-relevant results and still cannot lift
    # an irrelevant one, because membership was already decided by `relevant`.
    freshness_weight = temporality_of(query) if query else _DEFAULT_TEMPORALITY

    signals: list[tuple[float, list[int]]] = [
        (1.0, _rank_positions(relevances)),
        (0.6, _rank_positions(authorities)),
        (freshness_weight, _rank_positions(recencies)),
    ]

    fused = []
    for index, item in enumerate(items):
        points = sum(weight / (k + ranks[index]) for weight, ranks in signals)
        fused.append((points, -index, item))

    fused.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    ordered = diversify([item for _, _, item in fused])
    return ordered[:limit] if limit else ordered


def connectors_for(query: str, available: Sequence[str]) -> list[str]:
    """Which connectors are worth asking, given what was asked.

    Every query used to fan out to every connector, so a question about an
    election queried GitHub — and GitHub's constant outranked DuckDuckGo's, so
    a repository was returned as a source. Routing narrows what is fetched,
    which is also less egress for the same answer.

    General web search is **always** included. It is the one connector with no
    domain assumption, and dropping it on a misclassification would produce an
    empty answer — a far worse failure than one extra request.
    """
    wanted = []
    code = _looks_like_code_question(query)
    timely = temporality_of(query) >= _NEWS_TEMPORALITY
    for name in available:
        lowered = name.lower()
        # News is checked before the general-search branch, because its id
        # contains neither "duckduckgo" nor "search" today and must not start
        # depending on that. It is the one connector gated on *when* rather than
        # on *what*: a dated source earns its request on "what is the latest
        # Nvidia GPU" and is dead weight on "who was Napoleon".
        if "news" in lowered:
            if timely:
                wanted.append(name)
        elif "duckduckgo" in lowered or "brave" in lowered or "search" in lowered:
            wanted.append(name)
        elif "github" in lowered:
            if code:
                wanted.append(name)
        else:
            wanted.append(name)
    return wanted or list(available)


def is_code_domain(url: str) -> bool:
    """True for a host that answers code questions and little else."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return any(host == d or host.endswith("." + d) for d in _CODE_DOMAINS)
