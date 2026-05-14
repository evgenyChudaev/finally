"""Tests for snapshots_repo."""

from __future__ import annotations

import pytest

from app.db.snapshots_repo import list_snapshots, record_snapshot


class TestRecordSnapshot:
    def test_record(self, db_path):
        snap = record_snapshot(10000.0)
        assert snap.total_value == 10000.0
        assert snap.recorded_at.endswith("Z")
        assert snap.id > 0

    def test_rejects_negative(self, db_path):
        with pytest.raises(ValueError):
            record_snapshot(-1.0)

    def test_zero_allowed(self, db_path):
        snap = record_snapshot(0.0)
        assert snap.total_value == 0.0


class TestListSnapshots:
    def test_empty(self, db_path):
        assert list_snapshots() == []

    def test_chronological_order(self, db_path):
        s1 = record_snapshot(100.0)
        s2 = record_snapshot(200.0)
        s3 = record_snapshot(150.0)
        snaps = list_snapshots()
        # Oldest first.
        assert [s.id for s in snaps] == [s1.id, s2.id, s3.id]
        assert [s.total_value for s in snaps] == [100.0, 200.0, 150.0]

    def test_limit_keeps_most_recent_in_chronological_order(self, db_path):
        ids = [record_snapshot(float(i)).id for i in range(5)]
        snaps = list_snapshots(limit=3)
        # Last three in chronological order.
        assert [s.id for s in snaps] == ids[2:]

    def test_zero_limit(self, db_path):
        record_snapshot(100.0)
        assert list_snapshots(limit=0) == []
