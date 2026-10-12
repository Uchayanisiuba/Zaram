"""The page side of web photos: when the model is asked, and how references are read.

None of this touches the network. It grades the three things a page needs from
`packs/photos/page.py`: that the right requests are offered photographs and the
wrong ones are not, that every spelling a model might write a reference in is
found, and that substitution never invents a picture for a reference nothing
resolved.
"""

from __future__ import annotations

import pytest

from packs.photos.page import (
    MAX_REFERENCES,
    PHOTO_GUIDANCE,
    apply_photos,
    photo_references,
    wants_photos,
)


class TestWantsPhotos:
    @pytest.mark.parametrize(
        "text",
        [
            "build me a tourism website for Lagos",
            "Make a landing page for my bakery",
            "create a portfolio for a wedding photographer",
            "a website for my game studio",
            "design a restaurant homepage with a menu",
            "build a travel agency site",
            "Build a safari lodge page",
            "write a one-page site for a yoga studio",
        ],
    )
    def test_a_page_with_a_public_face_gets_photographs(self, text):
        assert wants_photos(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "build a snake game",
            "make a tic-tac-toe game",
            "build me a calculator",
            "a pomodoro timer",
            "make a unit converter tool",
            "restaurant bill splitter calculator",
            "create a bar chart of my expenses",
            "",
            None,
            "what is the capital of France",
        ],
    )
    def test_an_application_does_not(self, text):
        assert wants_photos(text) is False

    def test_the_word_website_overrides_an_app_word(self):
        # "game" would veto it on its own; "website" says what is being built.
        assert wants_photos("a website about a chess tool") is True


class TestGuidance:
    def test_it_names_the_pattern_the_extractor_reads(self):
        assert 'src="photo:' in PHOTO_GUIDANCE
        assert "photo:Lagos Lekki beach at sunset" in PHOTO_GUIDANCE

    def test_it_states_the_limit_the_finder_enforces(self):
        assert str(MAX_REFERENCES) in PHOTO_GUIDANCE

    def test_it_keeps_private_detail_out_of_descriptions(self):
        assert "private notes" in PHOTO_GUIDANCE

    def test_its_css_example_is_readable_by_the_extractor(self):
        assert "mountain village at dawn" in photo_references(PHOTO_GUIDANCE)

    def test_a_copied_template_is_not_a_description(self):
        # The pattern in the guidance reads `photo:short description of the
        # photo`. A model that pastes it literally has described nothing.
        assert photo_references('<img src="photo:short description of the photo">') == []


class TestReadingReferences:
    def test_img_src(self):
        page = '<img src="photo:Lagos Lekki beach at sunset" alt="Beach">'
        assert photo_references(page) == ["Lagos Lekki beach at sunset"]

    def test_single_quotes_and_odd_spacing(self):
        page = "<img  alt='x'  src = ' photo:old city street '>"
        assert photo_references(page) == ["old city street"]

    def test_percent_encoding_and_entities_decode(self):
        page = '<img src="photo:Lagos%20beach"><img src="photo:St.&#32;Johns church">'
        assert photo_references(page) == ["Lagos beach", "St. Johns church"]

    def test_srcset_keeps_the_descriptor_out_of_the_description(self):
        page = '<img srcset="photo:harbour at dawn 2x" src="x">'
        assert photo_references(page) == ["harbour at dawn"]

    def test_css_url_in_every_quoting_style(self):
        page = (
            "<style>.a{background:url('photo:mountain village at dawn')}"
            '.b{background-image:url("photo:night market lanterns")}'
            ".c{background:url(photo:blue lagoon)}</style>"
        )
        assert photo_references(page) == [
            "mountain village at dawn",
            "night market lanterns",
            "blue lagoon",
        ]

    def test_inline_style_attribute(self):
        page = '<div style="background-image:url(\'photo:rice terraces\')"></div>'
        assert photo_references(page) == ["rice terraces"]

    def test_repeats_are_one_reference_in_first_seen_order(self):
        page = (
            '<img src="photo:A busy market"><img src="photo:b river">'
            '<img src="photo:a  busy   MARKET">'
        )
        assert photo_references(page) == ["A busy market", "b river"]

    def test_a_css_hero_comes_first_when_it_is_first_on_the_page(self):
        # Only the first eight are fetched, and the hero is often a background:
        # on a live page reading attributes first put it last, past the limit.
        page = (
            "<style>.hero{background:url('photo:Lagos skyline at sunset')}</style>"
            '<img src="photo:beach with palm trees">'
        )
        assert photo_references(page) == ["Lagos skyline at sunset", "beach with palm trees"]

    def test_ordinary_images_and_urls_are_not_references(self):
        page = (
            '<img src="https://example.com/a.jpg"><img src="data:image/png;base64,AAAA">'
            '<a href="photographer.html">photo: not a reference</a>'
        )
        assert photo_references(page) == []

    def test_an_empty_page(self):
        assert photo_references("") == []
        assert photo_references(None) == []  # type: ignore[arg-type]


class TestSubstitution:
    def test_resolved_references_are_replaced_and_the_rest_left_alone(self):
        page = '<img src="photo:river at dawn"><img src="photo:unknown thing">'
        out = apply_photos(page, {"River at  dawn": "data:image/jpeg;base64,AAAA"})
        assert 'src="data:image/jpeg;base64,AAAA"' in out
        # Nothing is invented for the one that did not resolve.
        assert 'src="photo:unknown thing"' in out

    def test_css_and_srcset_keep_their_syntax(self):
        page = (
            "<style>.a{background:url('photo:red door')}</style>"
            '<img srcset="photo:red door 2x">'
        )
        out = apply_photos(page, {"red door": "/photos/web/ov-0123456789abcdef.jpg"})
        assert "url('/photos/web/ov-0123456789abcdef.jpg')" in out
        assert 'srcset="/photos/web/ov-0123456789abcdef.jpg 2x"' in out

    def test_a_replacement_cannot_break_out_of_the_attribute(self):
        page = '<img src="photo:x y z">'
        out = apply_photos(page, {"x y z": '"><script>alert(1)</script>'})
        assert "<script>" not in out

    def test_no_replacements_is_the_identity(self):
        page = '<img src="photo:a b c">'
        assert apply_photos(page, {}) == page
