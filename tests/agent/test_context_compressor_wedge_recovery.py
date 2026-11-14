"""Regression tests for the empty_post_handoff_window wedge (#211014).

A prior compaction leaves the transcript as [system, handoff, ...tail]. When one
oversized tool row blows the tail soft ceiling on the FIRST priced row, the tail
walk collapses the compress window to the handoff row alone; _scan_window_handoffs
strips it and the old code armed the 300s structural backoff every turn while the
session stayed over threshold — the "compression is currently blocked
(structural_backoff:NNN)" warning loop. The fix re-cuts the tail to the minimal
row floor so the turn history becomes summarizable.
"""
from unittest.mock import patch

from agent.context_compressor import ContextCompressor, SUMMARY_PREFIX


def _compressor():
    c = ContextCompressor.__new__(ContextCompressor)
    c.quiet_mode = True
    c.context_length = 1_048_576
    c.threshold_percent = 0.5
    c._threshold_tokens = 524_288
    c._tail_token_budget = None
    c.tail_mode = "lean"
    c.protect_first_n = 2
    c.protect_last_n = 2
    c.compression_count = 1
    c._previous_summary = None
    c.min_tail_user_messages = 1
    c._anti_thrash_recovery_deadline = 0.0
    c._structural_no_op_backoff_until = 0.0
    c._ineffective_compression_count = 0
    c._fallback_compression_streak = 0
    c._summary_failure_cooldown_until = 0.0
    c._last_summary_dropped_count = 0
    return c


def _wedged_messages():
    bigtool = "z" * 100000  # ~25k tokens: alone blows the 25k lean-tail budget
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": SUMMARY_PREFIX + "handoff body. " * 500},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "t1", "type": "function", "function": {"name": "terminal", "arguments": '{"command":"ls"}'}}
        ]},
        {"role": "tool", "tool_call_id": "t1", "name": "terminal", "content": bigtool},
    ]
    for i in range(40):
        messages.append({"role": "user" if i % 2 == 0 else "assistant", "content": "normal turn " * 30})
    return messages


def test_oversized_tail_tool_wedge_recovers_instead_of_backoff():
    c = _compressor()
    messages = _wedged_messages()
    with patch.object(c, "_generate_summary", return_value="SUMMARY OUTPUT") as gs, \
         patch.object(c, "_begin_compression_telemetry", return_value={}):
        result = c.compress(messages, current_tokens=560_000, force=True)
    assert gs.called, "wedge recovery must reach the summarizer instead of a structural no-op"
    assert c._structural_no_op_backoff_until == 0.0, "no structural backoff may be armed"
    assert c._ineffective_compression_count == 0, "recovery is not an ineffectiveness strike"
    assert len(result) < len(messages), "compression must reclaim messages"
    telemetry = getattr(c, "_last_compression_telemetry", None) or {}
    assert telemetry.get("failure_class") != "empty_post_handoff_window"


def test_over_budget_tail_detector():
    c = _compressor()
    messages = _wedged_messages()
    # The collapsed cut puts everything but the handoff in the tail
    assert c._tail_over_budget(messages, 2) is True
    assert c._tail_over_budget(messages, len(messages) - 1) is False


def test_small_healthy_session_still_structural_no_ops():
    """Genuine empty window (tiny transcript, tail within budget) keeps the old behavior."""
    c = _compressor()
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": SUMMARY_PREFIX + "handoff body. " * 500},
        {"role": "assistant", "content": "recent tail response"},
        {"role": "user", "content": "tail request"},
        {"role": "assistant", "content": "tail answer"},
        {"role": "user", "content": "latest tail request"},
        {"role": "assistant", "content": "latest tail answer"},
    ]
    with patch.object(c, "_find_tail_cut_by_tokens", return_value=2), \
         patch.object(c, "_generate_summary") as gs:
        c.provider = "test"
        c.model = "test-model"
        result = c.compress(messages, current_tokens=90_000)
    gs.assert_not_called()
    assert result == messages
    assert c._structural_no_op_backoff_until > 0.0, "healthy structural no-op still defers"
    telemetry = getattr(c, "_last_compression_telemetry", None) or {}
    assert telemetry.get("failure_class") == "empty_post_handoff_window"
