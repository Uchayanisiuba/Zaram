"""One transcript, projected per provider, fitted to the target's real window.

The rule under test: **the transcript is canonical, a provider's format is a
projection.** Storing messages in the shape one vendor's API wanted is how a
transcript comes to belong to that vendor, and switching model stops being free
— which is the product.

The fitting half matters as much as the projecting half, because the windows
are not comparable. A local model is loaded with 4,096 tokens (Ollama's default,
whatever the weights advertise) and Claude has 200,000. The same conversation
has to arrive whole at one and trimmed at the other.
"""

from __future__ import annotations

import pytest

from core.transcript import (
    ASSISTANT,
    USER,
    Turn,
    as_messages,
    as_prompt,
    fit,
    from_messages,
)


def _turns(*pairs) -> list[Turn]:
    return [Turn(role=role, text=text) for role, text in pairs]


class TestTheProjectionsAreGenuinelyDifferent:
    """If these two agreed, there would be nothing to project and this module
    would be a list with extra steps."""

    def test_a_completion_endpoint_gets_a_flattened_string(self):
        prompt = as_prompt(_turns((USER, "what is my rate"), (ASSISTANT, "400 a day.")))

        assert prompt == "User: what is my rate\n\nAssistant: 400 a day."

    def test_a_chat_endpoint_gets_role_tagged_messages(self):
        messages = as_messages(_turns((USER, "what is my rate"), (ASSISTANT, "400 a day.")))

        assert messages == [
            {"role": "user", "content": "what is my rate"},
            {"role": "assistant", "content": "400 a day."},
        ]

    def test_an_empty_transcript_flattens_to_nothing(self):
        """Not a header with nothing under it. A caller concatenating this onto
        a question must not get a stray "User:" with no exchange behind it."""
        assert as_prompt([]) == ""
        assert as_messages([]) == []

    def test_no_system_message_is_invented(self):
        """The system prompt is composed per request from identity, character
        settings and the date. One carried in a stored transcript would have
        been true when written and false now."""
        messages = as_messages(_turns((USER, "hi"), (ASSISTANT, "hello")))

        assert all(m["role"] != "system" for m in messages)

    def test_the_flattening_does_not_use_the_assistant_s_name(self):
        """The user may have called it Ada. A transcript that says "Ada:"
        teaches the model that the name is part of the format rather than a
        fact about this person — and identity is supplied once, in front."""
        prompt = as_prompt(_turns((ASSISTANT, "hello")))

        assert prompt.startswith("Assistant:")


class TestFittingDropsWholeTurns:
    def test_the_recent_end_is_what_survives(self):
        turns = _turns(
            (USER, "oldest question"),
            (ASSISTANT, "oldest answer"),
            (USER, "newest question"),
        )

        kept, dropped = fit(turns, budget_tokens=Turn(USER, "newest question").tokens)

        assert [t.text for t in kept] == ["newest question"]
        assert dropped == 2

    def test_a_transcript_that_fits_is_left_alone(self):
        turns = _turns((USER, "a"), (ASSISTANT, "b"), (USER, "c"))

        kept, dropped = fit(turns, budget_tokens=10_000)

        assert kept == turns
        assert dropped == 0

    def test_nothing_is_ever_cut_mid_message(self):
        """Half a message attributed to a person is a fabrication. A transcript
        saying the user asked *"what is the rate for"* is worse than one that
        omits the exchange, because the model answers the truncated question —
        rule 9's failure arriving through the context window."""
        long_turn = Turn(USER, "what is the rate for the Northwind job and when is it due")
        kept, _ = fit([long_turn], budget_tokens=long_turn.tokens // 2)

        assert kept == []
        assert all(t.text == long_turn.text for t in kept)

    def test_a_budget_nothing_fits_in_is_a_real_answer(self):
        """Returned as "nothing fits", not softened into a truncated turn. A
        caller should say the conversation is too long for this model."""
        turns = _turns((USER, "a question long enough to matter"))

        kept, dropped = fit(turns, budget_tokens=1)

        assert kept == []
        assert dropped == 1

    def test_a_zero_budget_keeps_nothing(self):
        turns = _turns((USER, "a"))

        assert fit(turns, budget_tokens=0) == ([], 1)

    def test_an_empty_transcript_needs_no_fitting(self):
        assert fit([], budget_tokens=1000) == ([], 0)


class TestTheKeptTranscriptNeverStartsWithAReply:
    """A reply whose question was dropped reads as context from nowhere, and a
    model handed one answers as though it had already been asked something."""

    def test_an_orphaned_answer_is_dropped_too(self):
        turns = _turns(
            (USER, "the question that will be dropped"),
            (ASSISTANT, "an answer with no question"),
            (USER, "the newest question"),
        )
        # A budget that fits the last two turns but not the first.
        budget = turns[1].tokens + turns[2].tokens

        kept, dropped = fit(turns, budget_tokens=budget)

        assert [t.role for t in kept] == [USER]
        assert kept[0].text == "the newest question"
        assert dropped == 2

    def test_a_transcript_already_starting_with_a_question_is_untouched(self):
        turns = _turns((USER, "a"), (ASSISTANT, "b"))

        kept, _ = fit(turns, budget_tokens=10_000)

        assert kept == turns


class TestTheSameTranscriptFitsTwoWindowsDifferently:
    """The reason fitting belongs here rather than in an engine: one
    conversation, two targets, two different amounts of it."""

    def test_a_small_window_trims_what_a_large_one_keeps(self):
        turns = _turns(*[(USER if i % 2 == 0 else ASSISTANT, f"turn number {i}") for i in range(40)])

        local, local_dropped = fit(turns, budget_tokens=60)
        cloud, cloud_dropped = fit(turns, budget_tokens=100_000)

        assert len(local) < len(cloud)
        assert local_dropped > 0
        assert cloud_dropped == 0
        # And the trimmed one is a suffix of the whole, never a rearrangement.
        assert [t.text for t in local] == [t.text for t in cloud[-len(local):]]


class TestReadingTheStoredRecords:
    def test_stored_messages_become_turns_in_order(self, tmp_path):
        from conversations import ConversationRecords

        store = ConversationRecords(str(tmp_path / "c.db"))
        conversation = store.start()
        store.append(conversation.id, "user", "what is my rate")
        store.append(conversation.id, "assistant", "400 a day.", model="gemma4:12b")

        turns = from_messages(store.messages(conversation.id))

        assert [(t.role, t.text) for t in turns] == [
            ("user", "what is my rate"),
            ("assistant", "400 a day."),
        ]

    def test_the_model_that_answered_does_not_travel_into_the_projection(self, tmp_path):
        """Which model answered is a fact about the *record*. Putting it on the
        wire is noise at best, and a claim the next model has no reason to
        trust at worst."""
        from conversations import ConversationRecords

        store = ConversationRecords(str(tmp_path / "c.db"))
        conversation = store.start()
        store.append(conversation.id, "user", "hi")
        store.append(conversation.id, "assistant", "hello", model="claude-sonnet-4.5")

        rendered = as_prompt(from_messages(store.messages(conversation.id)))

        assert "claude" not in rendered.lower()

    def test_an_empty_message_is_not_a_turn(self, tmp_path):
        from conversations import ConversationRecords

        store = ConversationRecords(str(tmp_path / "c.db"))
        conversation = store.start()
        store.append(conversation.id, "user", "real question")
        store.append(conversation.id, "assistant", "   ")

        assert len(from_messages(store.messages(conversation.id))) == 1

    def test_a_row_with_an_unknown_role_is_dropped_not_coerced(self):
        class Row:
            role = "system"
            text = "You are Zaram."

        assert from_messages([Row()]) == []
