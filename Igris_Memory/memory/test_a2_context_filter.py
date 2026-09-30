"""
Roadmap v4 A2 — CONTEXT FILTER testlari (§6)
=============================================
Run: python test_a2_context_filter.py | pytest test_a2_context_filter.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from context_filter import (  # noqa: E402
    score_context, rank_context_layers, dedup_layers, build_context,
)


class TestScoring(unittest.TestCase):
    def test_relevant_content_scores_higher(self):
        rel = score_context("fix psutil monitoring", "memory",
                            "psutil monitoring threads cpu")
        irrel = score_context("fix psutil monitoring", "memory",
                              "pandas dataframe merge pivot")
        self.assertGreater(rel, irrel)
        self.assertGreater(rel, 0.3)

    def test_layer_bonus_small(self):
        s_sys = score_context("fix bug", "system", "totally unrelated text")
        s_mem = score_context("fix bug", "memory", "totally unrelated text")
        self.assertGreater(s_sys, s_mem)

    def test_empty_task_returns_small_bonus(self):
        s = score_context("", "system", "anything")
        self.assertLess(s, 0.05)


class TestRanking(unittest.TestCase):
    def test_cross_layer_order(self):
        layers = {
            "system": "You are Igris agent. psutil monitoring required.",
            "user": "please check psutil monitoring on the server",
            "memory": ["pandas dataframe notes", "psutil monitoring notes"],
            "history": ["old chat about weather"],
        }
        ranked = rank_context_layers(layers, "check psutil monitoring")
        self.assertGreater(len(ranked), 0)
        # user task bilan TO'LIQ overlap (1.0+) — eng yuqori;
        # relevant memory/system keyin; aloqasiz chiqariladi
        self.assertEqual(ranked[0]["layer"], "user")
        self.assertIn("psutil", ranked[0]["content"])
        # aloqasiz 'weather' top-2 da yo'q
        top2 = " ".join(it["content"] for it in ranked[:2])
        self.assertNotIn("weather", top2)

    def test_irrelevant_filtered(self):
        layers = {
            "user": "check psutil monitoring",
            "history": ["completely unrelated cooking recipe text"],
        }
        ranked = rank_context_layers(layers, "check psutil monitoring",
                                     min_score=0.12)
        self.assertTrue(all("cooking" not in it["content"] or it["score"] >= 0.12
                            for it in ranked))

    def test_empty_layers_skipped(self):
        ranked = rank_context_layers({"system": "", "user": None},
                                     "some task")
        self.assertEqual(ranked, [])


class TestDedup(unittest.TestCase):
    def test_duplicate_across_layers_marked(self):
        ranked = [
            {"layer": "system", "content": "psutil monitoring is required",
             "score": 0.5},
            {"layer": "memory", "content": "PSUTIL MONITORING IS REQUIRED",
             "score": 0.3},
        ]
        out = dedup_layers(ranked)
        dups = [it for it in out if "dup_of" in it]
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0]["dup_of"], "system")

    def test_unique_content_untouched(self):
        ranked = [
            {"layer": "system", "content": "aaa bbb", "score": 0.5},
            {"layer": "user", "content": "ccc ddd", "score": 0.4},
        ]
        out = dedup_layers(ranked)
        self.assertEqual(len(out), 2)
        self.assertTrue(all("dup_of" not in it for it in out))


class TestBuildContext(unittest.TestCase):
    def test_full_pipeline(self):
        layers = {
            "system": "psutil monitoring agent instructions",
            "user": "check psutil monitoring",
            "memory": ["psutil monitoring notes",  # dup semantik emas — boshqa
                       "check psutil monitoring"],  # user bilan bir xil
            "history": ["weather chat unrelated"],
        }
        kept, stats = build_context(layers, "check psutil monitoring",
                                    max_items=5)
        self.assertGreater(len(kept), 0)
        self.assertGreaterEqual(stats["duplicates"], 1)
        self.assertLessEqual(len(kept), 5)
        # eng yuqori score birinchi (user: to'liq overlap)
        self.assertEqual(kept[0]["layer"], "user")

    def test_limit_applied(self):
        layers = {"memory": [f"psutil monitoring item {i}" for i in range(10)]}
        kept, stats = build_context(layers, "psutil monitoring",
                                    max_items=3)
        self.assertEqual(len(kept), 3)
        self.assertEqual(stats["dropped_limit"], 7)


if __name__ == "__main__":
    unittest.main()
