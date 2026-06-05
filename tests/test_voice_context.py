"""Tests for voice conversation context."""

from aurion.hermes import VoiceConversationContext


def test_context_begin_and_end():
    ctx = VoiceConversationContext(max_turns=3)
    assert not ctx.active
    ctx.begin()
    assert ctx.active
    ctx.append_turn("oi", "olá")
    assert len(ctx.snapshot()) == 2
    ctx.end()
    assert not ctx.active
    assert ctx.snapshot() == []


def test_context_trims_old_turns():
    ctx = VoiceConversationContext(max_turns=2)
    ctx.begin()
    ctx.append_turn("um", "1")
    ctx.append_turn("dois", "2")
    ctx.append_turn("tres", "3")
    history = ctx.snapshot()
    assert len(history) == 4
    assert history[0]["content"] == "dois"
    assert history[-1]["content"] == "3"
