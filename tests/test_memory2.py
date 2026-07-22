"""
Tests for igris.core.memory2 unified memory engine.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from igris.core.memory2 import MemoryEngine
from igris.core.memory2.entries import QAEntry, MemoEntry, DecisionEntry, make_id


def test_remember_and_recall():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        me.remember("The sky is blue", tags=["fact", "nature"])
        me.remember("Water is wet", tags=["fact"])
        import asyncio
        r = asyncio.run(me.recall("sky"))
        assert len(r.entries) > 0
        assert "sky" in r.entries[0].content.lower() or "sky" in r.entries[0].topic.lower()


def test_remember_qa():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        eid = me.remember("capital of france", question="What is the capital of France?", answer="Paris")
        assert eid.startswith("qa_")
        import asyncio
        r = asyncio.run(me.recall("France"))
        assert len(r.entries) > 0


def test_session_and_flush():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        me.remember("session note", session_id="test_sesh")
        assert me._session.active_sessions() == ["test_sesh"]
        n = me.flush_session("test_sesh")
        assert n > 0
        assert me._session.active_sessions() == []


def test_decisions():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        dec = me.get_or_decide("Should I use SQLite?", lambda: "Yes, SQLite is perfect for local agents", reasoning="minimal deps, fast, zero config")
        assert dec.question == "Should I use SQLite?"
        dec2 = me.get_or_decide("Should I use SQLite?", lambda: "no")
        assert dec2.id == dec.id


def test_forget():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        eid = me.remember("something to forget")
        me.forget(eid)
        import asyncio
        r = asyncio.run(me.recall("forget"))
        assert len(r.entries) == 0


def test_build_context():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d, model_size="1.5b")
        me.remember("Python is a programming language", tags=["python"])
        ctx = me.build_context("python")
        assert "python" in ctx.lower() or "Python" in ctx


def test_improve_and_feedback():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        eid = me.remember("some data", question="test", answer="result")
        fid = me.improve(eid, score=5, text="Great answer")
        assert fid.startswith("fb_")


def test_persistence():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        me.remember("persistent data", tags=["test"])
        stats1 = me.stats()
        del me
        me2 = MemoryEngine(d)
        stats2 = me2.stats()
        assert stats2["total"] >= stats1["total"]


def test_multiple_entries_search():
    with tempfile.TemporaryDirectory() as d:
        me = MemoryEngine(d)
        me.remember("React is a UI library", tags=["react", "frontend"])
        me.remember("Vue is also a UI framework", tags=["vue", "frontend"])
        me.remember("FastAPI is a Python web framework", tags=["python", "backend"])
        import asyncio
        r = asyncio.run(me.recall("frontend"))
        assert len(r.entries) >= 1


def test_store_entry_directly():
    with tempfile.TemporaryDirectory() as d:
        from igris.core.memory2.store import MemoryStore
        store = MemoryStore(d)
        entry = MemoEntry(id=make_id("mem"), topic="test", content="direct store test")
        store.put(entry)
        results = store.search("direct", top_k=5)
        assert len(results) > 0
        assert results[0][1].id == entry.id
        loaded = store.get(entry.id)
        assert loaded is not None
