"""Searching a codebase by the name of the thing you are looking for.

`content_tokens` lowercased before splitting on `\\w+`, which made every
camelCase identifier a single opaque token: `chunkCode` became `chunkcode`, and
*"where is chunk code"* matched nothing. Silently — no error, no empty state,
just a thin answer — across every symbol in a TypeScript project.
`snake_case` failed in the mirror image: `resident_budget_bytes` matched only
an exact repetition of itself.

This is the one retrieval change `CLAUDE.md` predicts by name: *"the rare
tokens in a project, a client name or a reference number, are exactly what a
lexical index is good at and a dense embedding is worst at."* An identifier is
the rare token, and code is made of nothing else.

**What this does not touch** is the similarity a citation is judged against.
Tokens decide candidate membership and the keyword term in the ranking blend;
the cosine stays the vector's answer on the vector's scale. Merging those is
the defect this repository has already paid for three times.
"""

from __future__ import annotations

import pytest

from runtimes.memory.index import content_tokens, identifier_parts


class TestAnIdentifierIsIndexedWholeAndInParts:
    @pytest.mark.parametrize(
        "identifier,parts",
        [
            ("resident_budget_bytes", {"resident", "budget", "bytes"}),
            ("chunkCode", {"chunk", "code"}),
            ("ModelPull", {"model", "pull"}),
            ("useReadiness", {"use", "readiness"}),
            ("stream_pull", {"stream", "pull"}),
            ("firstRunPanel", {"first", "run", "panel"}),
        ],
    )
    def test_the_parts_are_searchable(self, identifier, parts):
        tokens = content_tokens(identifier)

        assert parts <= tokens, f"{identifier} lost {parts - tokens}"

    @pytest.mark.parametrize(
        "identifier",
        ["resident_budget_bytes", "chunkCode", "ModelPull", "PullUnavailable"],
    )
    def test_the_whole_identifier_is_still_a_token(self, identifier):
        """Pasting a symbol exactly is the strongest possible signal that you
        mean *that* symbol, and it must not be diluted into its parts."""
        assert identifier.lower() in content_tokens(identifier)

    def test_an_acronym_is_not_shattered_into_letters(self):
        """`HTTPServer` is `http` and `server`, not `h`, `t`, `t`, `p`."""
        tokens = content_tokens("HTTPServer")

        assert {"http", "server"} <= tokens
        assert "h" not in tokens

    def test_a_half_remembered_name_finds_the_symbol(self):
        """The behaviour a person actually has: they remember two words of it."""
        asked = content_tokens("where is the budget bytes thing")
        indexed = content_tokens("def resident_budget_bytes(self) -> Optional[int]:")

        assert {"budget", "bytes"} <= asked & indexed

    def test_camel_case_was_previously_unreachable(self):
        """The regression this file exists for, stated as the query that
        failed: nothing in a TypeScript codebase could be found by two words."""
        asked = content_tokens("chunk code")
        indexed = content_tokens("export function chunkCode(text: string) {")

        assert {"chunk", "code"} <= asked & indexed


class TestOrdinaryProseIsUnchanged:
    def test_a_plain_word_is_not_split(self):
        assert identifier_parts("readiness") == []
        assert content_tokens("readiness") == {"readiness"}

    def test_stopwords_are_still_dropped(self):
        """The live recall bug this tokenizer was written to fix: "What is the
        capital of France?" matched an unrelated brief on `is`, `of` and
        `the`."""
        tokens = content_tokens("What is the capital of France?")

        assert tokens == {"capital", "france"}

    def test_bare_digits_are_still_dropped(self):
        assert content_tokens("page 42 of 100") == {"page"}

    def test_a_single_letter_part_is_noise(self):
        """The `i` in `iPhone` ranks nothing and matches everything."""
        tokens = content_tokens("iPhone")

        assert "i" not in tokens
        assert "phone" in tokens

    def test_a_short_meaningful_part_survives(self):
        """Two letters is the floor precisely so `db`, `os` and `id` live."""
        assert {"user", "id"} <= content_tokens("user_id")
        assert {"os", "path"} <= content_tokens("os_path")


class TestTheSplitIsSymmetric:
    """Query and document go through the same function, which is the only
    reason any of this works — a tokenizer applied to one side is a filter."""

    def test_a_query_and_a_document_meet_on_the_parts(self):
        document = content_tokens(
            "class ProviderManager:\n    def resident_budget_bytes(self): ..."
        )
        for query in ("resident budget", "budget bytes", "provider manager"):
            assert content_tokens(query) & document, query
