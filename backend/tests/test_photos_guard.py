"""What may be written into a photo search.

Rule 8 -- nothing derived from the Spine may appear in an outbound query -- is
held for web search by construction: the query is the user's own prompt
(`test_outbound_query_invariant.py`). A photo description is *model-written*,
so the same property is held by checking, and this file is the equivalent of
that one for photos: a marker string that exists only in the Spine must never
reach a description that is sent.
"""

from __future__ import annotations

import pytest

from packs.photos.guard import (
    MAX_CHARS,
    MAX_WORDS,
    DescriptionRefused,
    check_against_spine,
    clean_description,
    description_key,
    prepare,
)

#: A string that exists only in the Spine. If it ever reaches a description that
#: is sent, memory has leaked into a network request.
SECRET = "zzq-spine-only-marker-8f2a"


class TestCleaning:
    def test_a_plain_description_is_unchanged(self):
        assert clean_description("Lagos Lekki beach at sunset") == "Lagos Lekki beach at sunset"

    def test_words_are_capped(self):
        text = clean_description("one two three four five six seven eight nine ten eleven")
        assert len(text.split()) == MAX_WORDS
        assert text == "one two three four five six seven eight"

    def test_characters_are_capped_on_a_word_boundary(self):
        text = clean_description(" ".join(["abcdefghij"] * 8))
        assert len(text) <= MAX_CHARS
        assert not text.endswith("abcdef")  # no word cut in half
        assert text.split()[-1] == "abcdefghij"

    def test_markup_and_symbols_are_stripped(self):
        assert clean_description('<b>old</b> "harbour" {at} dawn!') == "b old b harbour at dawn"

    def test_whitespace_and_control_characters_collapse(self):
        assert clean_description("  river\n\n\tat\x00   dawn ") == "river at dawn"

    @pytest.mark.parametrize(
        "text",
        [
            "office of ada@example.com",
            "see https://client.example/brief",
            "photo from www.northwind.com",
            "northwind.io headquarters",
            "call +234 803 555 0142 beach",
            "invoice 20260412 beach",
            "account 1234 5678 9012 street",
        ],
    )
    def test_what_no_picture_needs_is_refused_not_trimmed(self, text):
        with pytest.raises(DescriptionRefused):
            clean_description(text)

    @pytest.mark.parametrize("text", ["", "  ", "ab", "123", "...", None, 7])
    def test_nothing_to_search_for_is_refused(self, text):
        with pytest.raises(DescriptionRefused):
            clean_description(text)

    def test_a_year_is_fine(self):
        assert clean_description("1920s street market") == "1920s street market"

    def test_the_key_ignores_case_and_spacing(self):
        assert description_key("A  Busy MARKET") == description_key("a busy market")


class TestSpineCheck:
    SPINE = [
        f"The user's private note: {SECRET}",
        "Client Adaeze Okafor of Northwind pays 450000 naira on net 30 terms",
        "Prefers sunsets and calm blue colour palettes",
    ]

    def test_a_marker_that_exists_only_in_the_spine_never_gets_through(self):
        with pytest.raises(DescriptionRefused) as exc:
            prepare(f"beach {SECRET}", self.SPINE)
        assert exc.value.code == "spine_derived"

    def test_a_copied_clause_is_refused_even_with_a_word_changed_around_it(self):
        with pytest.raises(DescriptionRefused):
            prepare("office where Okafor of Northwind pays on net 30 terms", self.SPINE)

    def test_a_name_from_memory_is_refused(self):
        with pytest.raises(DescriptionRefused):
            prepare("Adaeze Okafor office lobby", self.SPINE)

    def test_a_capitalised_place_from_memory_that_the_request_never_named_is_refused(self):
        with pytest.raises(DescriptionRefused):
            prepare("hotel lobby in Northwind", self.SPINE)

    def test_the_users_own_request_words_are_exempt(self):
        # They typed it, so it is not recalled. Same reason the search query may
        # be exactly the user's prompt.
        request = "build a website for Northwind, a harbour hotel"
        assert prepare("hotel lobby in Northwind", self.SPINE, request) == "hotel lobby in Northwind"

    def test_an_ordinary_description_passes_when_the_spine_is_full(self):
        assert prepare("Lagos Lekki beach at sunset", self.SPINE) == "Lagos Lekki beach at sunset"

    def test_a_sentence_opening_capital_alone_is_not_a_name(self):
        spine = ["Busy weeks are normal for this client"]
        assert prepare("Busy street market at night", spine) == "Busy street market at night"

    def test_two_facts_do_not_combine_into_a_run(self):
        spine = ["the harbour at", "dawn was quiet"]
        # "harbour at dawn" never occurs in order inside either fact.
        check_against_spine("harbour at dawn", spine)

    def test_an_empty_spine_checks_nothing(self):
        check_against_spine("anything at all here", [])

    def test_an_unreadable_spine_fails_closed(self):
        with pytest.raises(DescriptionRefused) as exc:
            prepare("river at dawn", None)
        assert exc.value.code == "spine_unreadable"
