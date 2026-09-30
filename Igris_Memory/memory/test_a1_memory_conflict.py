"""
Roadmap v4 A1 — MEMORY CONFLICT + PRIORITY + FILTER testlari
============================================================
v1 §5 qoldiqlari qamrovi:
  - contradiction detection ("X bor" vs "X yo'q", true/false, installed/not)
  - [CONFLICT] belgilash (mark_conflicts)
  - layer priority (L1 > L2 > retrieval, tie-break bilan)
  - relevance filter (task-aloqasiz natijalar tashlanadi)

Run: python test_a1_memory_conflict.py | pytest test_a1_memory_conflict.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_conflict import (  # noqa: E402
    detect_contradictions, mark_conflicts, apply_layer_priority,
    filter_relevant, ConflictPair,
)


class TestContradictionDetection(unittest.TestCase):
    def test_bor_yoq_uz(self):
        items = [
            {"text": "server yangilanishi bor.", "source": "a"},
            {"text": "server yangilanishi yo'q.", "source": "b"},
        ]
        cs = detect_contradictions(items)
        self.assertEqual(len(cs), 1)
        self.assertIsInstance(cs[0], ConflictPair)

    def test_installed_not_installed(self):
        items = [
            {"text": "psutil is installed on the server.", "source": "a"},
            {"text": "psutil is not installed on the server.", "source": "b"},
        ]
        cs = detect_contradictions(items)
        self.assertEqual(len(cs), 1)
        self.assertIn("installed", cs[0].reason)

    def test_true_false_same_subject(self):
        items = [
            {"text": "cache.enabled: true", "source": "a"},
            {"text": "cache.enabled: false", "source": "b"},
        ]
        cs = detect_contradictions(items)
        self.assertEqual(len(cs), 1)
        self.assertIn("cache.enabled", cs[0].subject)

    def test_works_vs_does_not_work(self):
        items = [
            {"text": "the bridge works after restart.", "source": "a"},
            {"text": "the bridge does not work after restart.", "source": "b"},
        ]
        cs = detect_contradictions(items)
        self.assertEqual(len(cs), 1)

    def test_no_contradiction_in_agreement(self):
        items = [
            {"text": "psutil is installed on the server.", "source": "a"},
            {"text": "the psutil version is 7.2.2.", "source": "b"},
        ]
        self.assertEqual(detect_contradictions(items), [])

    def test_empty_input(self):
        self.assertEqual(detect_contradictions([]), [])
        self.assertEqual(detect_contradictions([{"text": ""}]), [])


class TestMarkConflicts(unittest.TestCase):
    def test_conflicted_results_flagged(self):
        results = [
            {"content": "feature is enabled in config", "score": 0.9,
             "metadata": {"source": "r1"}},
            {"content": "feature is disabled in config", "score": 0.8,
             "metadata": {"source": "r2"}},
            {"content": "pandas merge pivot", "score": 0.7,
             "metadata": {"source": "r3"}},
        ]
        out = mark_conflicts(results)
        flagged = [r for r in out if r.get("conflict")]
        self.assertEqual(len(flagged), 2)
        self.assertTrue(all("conflicts" in r for r in flagged))
        # uchinchi (aloqasiz) belgilanmagan
        third = next(r for r in out if r["metadata"]["source"] == "r3")
        self.assertNotIn("conflict", third)

    def test_no_conflicts_unchanged(self):
        results = [{"content": "a b c", "score": 1.0}]
        self.assertEqual(mark_conflicts(results), results)


class TestLayerPriority(unittest.TestCase):
    def test_higher_score_wins_regardless_of_layer(self):
        ranked = apply_layer_priority([
            {"source": "retrieval-x", "score": 0.9},
            {"source": "l1-runtime", "score": 0.5},
        ])
        self.assertEqual(ranked[0]["source"], "retrieval-x")

    def test_tie_break_prefers_runtime(self):
        ranked = apply_layer_priority([
            {"source": "retrieval-x", "score": 0.5},
            {"source": "l1-runtime", "score": 0.5},
        ])
        self.assertEqual(ranked[0]["source"], "l1-runtime")

    def test_layer_bonus_fields(self):
        ranked = apply_layer_priority([
            {"source": "l2-persistent", "score": 0.4}])
        self.assertAlmostEqual(ranked[0]["layer_bonus"], 0.15)
        self.assertAlmostEqual(ranked[0]["final_score"], 0.55)


class TestRelevanceFilter(unittest.TestCase):
    def test_irrelevant_dropped(self):
        results = [
            {"content": "pandas dataframe merge pivot groupby",
             "score": 0.2, "source": "r1"},
        ]
        kept, dropped = filter_relevant(
            results, "check psutil monitoring works", min_overlap=0.3)
        self.assertEqual(dropped, 1)
        self.assertEqual(kept, [])

    def test_relevant_kept_with_overlap(self):
        results = [
            {"content": "psutil monitoring CPU RAM threads",
             "score": 0.3, "source": "r1"},
        ]
        kept, dropped = filter_relevant(
            results, "check psutil monitoring works", min_overlap=0.3)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(kept), 1)
        self.assertGreater(kept[0]["relevance"], 0.0)

    def test_high_score_survives_low_overlap(self):
        results = [
            {"content": "pandas dataframe merge pivot",
             "score": 0.6, "source": "r1"},
        ]
        kept, _ = filter_relevant(
            results, "check psutil monitoring works", min_overlap=0.3)
        self.assertEqual(len(kept), 1)  # score >= 0.5 — saqlanadi

    def test_below_min_score_dropped_even_if_relevant(self):
        results = [
            {"content": "psutil monitoring", "score": 0.01, "source": "r1"},
        ]
        kept, dropped = filter_relevant(
            results, "psutil monitoring", min_score=0.05)
        self.assertEqual(dropped, 1)
        self.assertEqual(kept, [])

    def test_keep_limit(self):
        results = [{"content": "psutil monitoring cpu", "score": 0.3,
                    "source": f"r{i}"} for i in range(10)]
        kept, _ = filter_relevant(results, "psutil monitoring",
                                  min_overlap=0.3, keep=3)
        self.assertEqual(len(kept), 3)


if __name__ == "__main__":
    unittest.main()
