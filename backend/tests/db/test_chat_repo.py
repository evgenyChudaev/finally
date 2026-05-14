"""Tests for chat_repo."""

from __future__ import annotations

import pytest

from app.db.chat_repo import append_message, recent_messages


class TestAppendMessage:
    def test_user_message(self, db_path):
        msg = append_message("user", "Hello FinAlly")
        assert msg.role == "user"
        assert msg.content == "Hello FinAlly"
        assert msg.actions is None
        assert msg.created_at.endswith("Z")

    def test_assistant_with_actions(self, db_path):
        actions = {
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [],
            "errors": [],
        }
        msg = append_message("assistant", "Bought 10 AAPL", actions=actions)
        assert msg.role == "assistant"
        assert msg.actions == actions

    def test_actions_roundtrip(self, db_path):
        actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]}
        append_message("assistant", "ok", actions=actions)
        loaded = recent_messages()
        assert loaded[0].actions == actions

    def test_rejects_bad_role(self, db_path):
        with pytest.raises(ValueError):
            append_message("system", "hi")

    def test_rejects_empty_content(self, db_path):
        with pytest.raises(ValueError):
            append_message("user", "")


class TestRecentMessages:
    def test_empty(self, db_path):
        assert recent_messages() == []

    def test_chronological_order(self, db_path):
        m1 = append_message("user", "first")
        m2 = append_message("assistant", "second")
        m3 = append_message("user", "third")
        msgs = recent_messages()
        assert [m.id for m in msgs] == [m1.id, m2.id, m3.id]
        assert [m.content for m in msgs] == ["first", "second", "third"]

    def test_limit_returns_most_recent_chronologically(self, db_path):
        ids = []
        for i in range(5):
            ids.append(append_message("user", f"msg-{i}").id)
        msgs = recent_messages(limit=3)
        # Last three by recency, ordered chronologically (oldest of the three first).
        assert [m.id for m in msgs] == ids[-3:]
        assert [m.content for m in msgs] == ["msg-2", "msg-3", "msg-4"]

    def test_zero_limit(self, db_path):
        append_message("user", "x")
        assert recent_messages(limit=0) == []

    def test_actions_decoded(self, db_path):
        append_message("assistant", "done", actions={"trades": []})
        msg = recent_messages()[0]
        assert msg.actions == {"trades": []}
