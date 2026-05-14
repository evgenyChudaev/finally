"""Tests for trades_repo."""

from __future__ import annotations

import pytest

from app.db.trades_repo import list_trades, record_trade


class TestRecordTrade:
    def test_buy(self, db_path):
        trade = record_trade("AAPL", "buy", 10.0, 190.5)
        assert trade.ticker == "AAPL"
        assert trade.side == "buy"
        assert trade.quantity == 10.0
        assert trade.price == 190.5
        assert trade.executed_at.endswith("Z")
        assert trade.id > 0

    def test_sell(self, db_path):
        trade = record_trade("AAPL", "sell", 5.0, 200.0)
        assert trade.side == "sell"

    def test_normalizes_ticker(self, db_path):
        trade = record_trade(" aapl ", "buy", 1.0, 100.0)
        assert trade.ticker == "AAPL"

    def test_rejects_bad_side(self, db_path):
        with pytest.raises(ValueError):
            record_trade("AAPL", "short", 1.0, 100.0)

    def test_rejects_zero_quantity(self, db_path):
        with pytest.raises(ValueError):
            record_trade("AAPL", "buy", 0.0, 100.0)

    def test_rejects_negative_quantity(self, db_path):
        with pytest.raises(ValueError):
            record_trade("AAPL", "buy", -1.0, 100.0)

    def test_rejects_negative_price(self, db_path):
        with pytest.raises(ValueError):
            record_trade("AAPL", "buy", 1.0, -1.0)

    def test_rejects_empty_ticker(self, db_path):
        with pytest.raises(ValueError):
            record_trade("  ", "buy", 1.0, 100.0)


class TestListTrades:
    def test_empty(self, db_path):
        assert list_trades() == []

    def test_recent_first(self, db_path):
        t1 = record_trade("AAPL", "buy", 1.0, 100.0)
        t2 = record_trade("MSFT", "buy", 1.0, 400.0)
        t3 = record_trade("AAPL", "sell", 1.0, 110.0)
        trades = list_trades()
        # Newest first; record_trade preserves insertion order via id tiebreaker.
        assert [t.id for t in trades] == [t3.id, t2.id, t1.id]

    def test_limit(self, db_path):
        for i in range(5):
            record_trade("AAPL", "buy", 1.0, 100.0 + i)
        trades = list_trades(limit=2)
        assert len(trades) == 2

    def test_zero_limit(self, db_path):
        record_trade("AAPL", "buy", 1.0, 100.0)
        assert list_trades(limit=0) == []
