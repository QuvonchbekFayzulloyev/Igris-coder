"""
IGRIS BRAIN — Real Task Tests
================================
Haqiqiy vazifalar bilan pipeline + supervisor tizimini sinash:
  1. PPTX (PowerPoint) yaratish
  2. Mini game (HTML/JS) yaratish

Har bir test:
  - Pipeline tanlash → classify_need + build_pipeline
  - Loop shape tekshirish → max_iter, max_repair
  - DAG planning (LLMDAGPlanner)
  - Checkpoint save/load
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from igris_agent import IgrisAgent, PIPELINE_SPECS  # noqa: E402
from task_supervisor import (  # noqa: E402
    TaskSupervisor, TaskDAG, TaskNode, LLMDAGPlanner,
    CheckpointManager, WorkingContext, NodeStatus,
)


class _FakeIntel:
    def screen(self, message):
        return type("V", (), {"allowed": True, "reason": None, "category": ""})()
    def observe(self, message):
        return None
    def adapt_system(self, system, message):
        return system or "system"
    def reasoning_suffix(self):
        return ""
    def quick_math(self, expr):
        return None
    def evaluate(self, **kwargs):
        class _Eval:
            def to_dict(self):
                return {"confidence": 0.5}
        return _Eval()


def _make_agent():
    agent = IgrisAgent(use_llm=False, memory_enabled=False)
    agent.intelligence = _FakeIntel()
    agent._cag = lambda: None
    return agent


# =================================================================== #
# TEST 1: PPTX yaratish
# =================================================================== #

class TestPPTXTask(unittest.TestCase):
    """PPTX (PowerPoint) yaratish — pipeline + DAG test."""

    def setUp(self):
        self.agent = _make_agent()
        self.tmpdir = tempfile.mkdtemp()

    def test_pptx_pipeline_selection(self):
        """PPTX yaratish → code pipeline tanlanishi (kod yozish so'rovi)."""
        # Classifier "pptx" ni taniymaydi — lekin "kod yoz" taniydi
        p = self.agent._build_pipeline("pptx yaratish uchun kod yoz")
        self.assertEqual(p["need"], "code")

    def test_pptx_loop_fields(self):
        """PPTX pipeline'da loop_shape mavjudligi."""
        p = self.agent._build_pipeline("pptx yarat")
        self.assertIn("loop_shape", p)
        self.assertIn("max_iter", p)
        self.assertIn("max_repair", p)

    def test_pptx_dag_planning(self):
        """PPTX uchun DAG planning."""
        p = self.agent._build_pipeline("powerpoint taqdimot yarat")

        # Supervisor DAG qurishi
        sup = TaskSupervisor()
        dag = sup.build_dag("powerpoint taqdimot yarat", p)
        self.assertIsNotNone(dag)
        self.assertGreaterEqual(len(dag.nodes), 1)

        # Main node mavjudligi
        self.assertIn("main", dag.nodes)
        self.assertEqual(dag.nodes["main"].need, p["need"])

    def test_pptx_dag_topological_order(self):
        """DAG topological order to'g'riligi."""
        p = self.agent._build_pipeline("pptx yarat va kod yoz")
        sup = TaskSupervisor()
        dag = sup.build_dag("pptx yarat va kod yoz", p)
        order = dag.topological_order()
        self.assertIn("main", order)
        # Sub-nodes main'dan keyin kelishi kerak
        main_idx = order.index("main")
        for nid in order:
            if nid != "main":
                self.assertGreater(order.index(nid), main_idx,
                                   f"{nid} main'dan oldin kelmasligi kerak")

    def test_pptx_checkpoint_save_load(self):
        """PPTX task uchun checkpoint saqlash/qayta yuklash."""
        ckpt_dir = os.path.join(self.tmpdir, "checkpoints")
        mgr = CheckpointManager(ckpt_dir)

        p = self.agent._build_pipeline("pptx yarat")
        sup = TaskSupervisor(checkpoint_dir=ckpt_dir)
        dag = sup.build_dag("pptx yarat", p)

        # Simulate execution
        dag.nodes["main"].status = NodeStatus.COMPLETED
        dag.nodes["main"].result = "Created presentation.pptx"

        # Save checkpoint
        from task_supervisor import TaskCheckpoint
        cp = TaskCheckpoint(
            task_id="pptx_test",
            goal="pptx yarat",
            dag=dag.to_dict(),
            budget_remaining=35,
        )
        mgr.save(cp)

        # Load checkpoint
        loaded = mgr.load("pptx_test")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.goal, "pptx yarat")
        self.assertEqual(loaded.budget_remaining, 35)

    def test_pptx_llm_dag_planner(self):
        """LLMDAGPlanner bilan PPTX DAG planning."""
        planner = LLMDAGPlanner()

        # Mock LLM response
        mock_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "PPTX shablonini yaratish",
                 "need": "code", "predecessors": []},
                {"id": "t2", "description": "Slaydlarni to'ldirish",
                 "need": "code", "predecessors": ["t1"]},
                {"id": "t3", "description": "PPTX faylni saqlash",
                 "need": "code", "predecessors": ["t2"]},
            ]
        })

        dag = planner._parse_dag_json(mock_response)
        self.assertIsNotNone(dag)
        self.assertEqual(len(dag.nodes), 3)

        # Topological order: t1 → t2 → t3
        order = dag.topological_order()
        self.assertLess(order.index("t1"), order.index("t2"))
        self.assertLess(order.index("t2"), order.index("t3"))

    def test_pptx_working_context(self):
        """PPTX task uchun working context."""
        ctx = WorkingContext(max_context_chars=1000)
        ctx.set_goal("powerpoint taqdimot yarat")
        ctx.set_plan(["main", "sub_0_code"])

        ctx.add_observation("tool", "Created slide 1: Title")
        ctx.add_observation("tool", "Created slide 2: Content")
        ctx.add_observation("result", "main: PPTX ready")

        block = ctx.build_context_block()
        self.assertIn("powerpoint taqdimot yarat", block)
        self.assertIn("Created slide 1", block)
        self.assertIn("Created slide 2", block)

    def test_pptx_supervisor_run(self):
        """PPTX uchun supervisor run (placeholder agent)."""
        p = self.agent._build_pipeline("pptx yarat")
        sup = TaskSupervisor()
        result = sup.run("pptx yarat", p)
        self.assertIn(result["status"], ("ok", "partial"))
        self.assertIn("main", result["results"])


# =================================================================== #
# TEST 2: Mini game yaratish
# =================================================================== #

class TestMiniGameTask(unittest.TestCase):
    """Mini game (HTML/JS) yaratish — pipeline + DAG test."""

    def setUp(self):
        self.agent = _make_agent()
        self.tmpdir = tempfile.mkdtemp()

    def test_game_pipeline_selection(self):
        """Game yaratish → code pipeline tanlanishi."""
        # Classifier "game" ni taniymaydi — lekin "kod yoz" taniydi
        p = self.agent._build_pipeline("mini game uchun kod yoz")
        self.assertEqual(p["need"], "code")

    def test_game_loop_fields(self):
        """Game pipeline'da loop_shape mavjudligi."""
        p = self.agent._build_pipeline("mini game uchun kod yoz")
        self.assertIn("loop_shape", p)
        # code pipeline → build_verify
        self.assertEqual(p["loop_shape"], "build_verify")

    def test_game_dag_planning(self):
        """Game uchun DAG planning."""
        p = self.agent._build_pipeline("mini game yarat")
        sup = TaskSupervisor()
        dag = sup.build_dag("mini game yarat", p)
        self.assertIsNotNone(dag)
        self.assertIn("main", dag.nodes)

    def test_game_dag_with_sub_pipelines(self):
        """Game + test → DAG with dependencies."""
        # Simulate pipeline with sub_pipelines
        pipeline = {
            "need": "code",
            "label": "Kod vazifasi",
            "loop_shape": "build_verify",
            "max_iter": 8,
            "max_repair": 3,
            "sub_pipelines": [
                {"need": "code", "label": "Test yozish",
                 "loop_shape": "build_verify", "max_iter": 8, "max_repair": 3},
            ],
        }
        sup = TaskSupervisor()
        dag = sup.build_dag("mini game yarat va test yoz", pipeline)
        self.assertEqual(len(dag.nodes), 2)
        self.assertIn("main", dag.nodes)
        self.assertIn("sub_0_code", dag.nodes)
        self.assertEqual(dag.nodes["sub_0_code"].predecessors, ["main"])

    def test_game_checkpoint_save_load(self):
        """Game task uchun checkpoint."""
        ckpt_dir = os.path.join(self.tmpdir, "checkpoints")
        mgr = CheckpointManager(ckpt_dir)

        p = self.agent._build_pipeline("mini game yarat")
        sup = TaskSupervisor(checkpoint_dir=ckpt_dir)
        dag = sup.build_dag("mini game yarat", p)

        from task_supervisor import TaskCheckpoint
        cp = TaskCheckpoint(
            task_id="game_test",
            goal="mini game yarat",
            dag=dag.to_dict(),
            budget_remaining=32,
        )
        mgr.save(cp)

        loaded = mgr.load("game_test")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.goal, "mini game yarat")

    def test_game_llm_dag_planner(self):
        """LLMDAGPlanner bilan Game DAG planning."""
        planner = LLMDAGPlanner()

        mock_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "Game engine qurish (Canvas + game loop)",
                 "need": "code", "predecessors": []},
                {"id": "t2", "description": "Player logikasi yozish",
                 "need": "code", "predecessors": ["t1"]},
                {"id": "t3", "description": "Enemy AI qo'shish",
                 "need": "code", "predecessors": ["t1"]},
                {"id": "t4", "description": "Test yozish",
                 "need": "code", "predecessors": ["t2", "t3"]},
            ]
        })

        dag = planner._parse_dag_json(mock_response)
        self.assertIsNotNone(dag)
        self.assertEqual(len(dag.nodes), 4)

        # t1 before t2 and t3, t2+t3 before t4
        order = dag.topological_order()
        self.assertLess(order.index("t1"), order.index("t2"))
        self.assertLess(order.index("t1"), order.index("t3"))
        self.assertLess(order.index("t2"), order.index("t4"))
        self.assertLess(order.index("t3"), order.index("t4"))

    def test_game_working_context(self):
        """Game task uchun working context."""
        ctx = WorkingContext(max_context_chars=1000)
        ctx.set_goal("mini game yarat")
        ctx.set_plan(["main"])

        ctx.add_observation("tool", "Created index.html with Canvas")
        ctx.add_observation("tool", "Added game.js with player movement")
        ctx.add_observation("result", "main: Game ready")

        block = ctx.build_context_block()
        self.assertIn("mini game yarat", block)
        self.assertIn("Canvas", block)

    def test_game_supervisor_run(self):
        """Game uchun supervisor run."""
        p = self.agent._build_pipeline("mini game yarat")
        sup = TaskSupervisor()
        result = sup.run("mini game yarat", p)
        self.assertIn(result["status"], ("ok", "partial"))
        self.assertIn("main", result["results"])

    def test_game_review_dispatch(self):
        """Game review — build_verify retry."""
        agent = _make_agent()
        called = [0]

        def edit_fn(issues):
            called[0] += 1

        result = agent._review_dispatch(
            {"ok": False, "issues": ["game over not working"]},
            {"loop_shape": "build_verify", "max_repair": 3},
            edit_fn=edit_fn,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["repaired"])
        self.assertEqual(result["method"], "build_verify")
        self.assertEqual(called[0], 1)


# =================================================================== #
# TEST 3: Combined — PPTX + Game together
# =================================================================== #

class TestCombinedTask(unittest.TestCase):
    """PPTX + Game — birlashtirilgan task DAG test."""

    def setUp(self):
        self.agent = _make_agent()

    def test_combined_pipeline_detection(self):
        """Birlashtirilgan so'rov → code pipeline + sub_pipelines."""
        # "rasm chiz va kod yoz" → draw (main) + code (sub)
        p = self.agent._build_pipeline("rasm chiz va kod yoz")
        self.assertEqual(p["need"], "draw")
        subs = p.get("sub_pipelines", [])
        self.assertGreater(len(subs), 0,
                           "Birlashtirilgan so'rovda sub_pipelines bo'lishi kerak")

    def test_combined_dag_planning(self):
        """PPTX + Game uchun DAG."""
        pipeline = {
            "need": "code",
            "label": "Kod vazifasi",
            "loop_shape": "build_verify",
            "max_iter": 8,
            "max_repair": 3,
            "sub_pipelines": [
                {"need": "code", "label": "PPTX yaratish",
                 "loop_shape": "plan_then_execute", "max_iter": 1, "max_repair": 0},
                {"need": "code", "label": "Game yaratish",
                 "loop_shape": "build_verify", "max_iter": 8, "max_repair": 3},
            ],
        }
        sup = TaskSupervisor()
        dag = sup.build_dag("pptx va game yarat", pipeline)
        self.assertEqual(len(dag.nodes), 3)  # main + 2 subs
        order = dag.topological_order()
        self.assertLess(order.index("main"), order.index("sub_0_code"))
        self.assertLess(order.index("main"), order.index("sub_1_code"))

    def test_combined_supervisor_run(self):
        """PPTX + Game supervisor run."""
        pipeline = {
            "need": "code",
            "label": "Kod vazifasi",
            "loop_shape": "build_verify",
            "max_iter": 8,
            "max_repair": 3,
            "sub_pipelines": [
                {"need": "code", "label": "PPTX yaratish",
                 "loop_shape": "plan_then_execute", "max_iter": 1, "max_repair": 0},
                {"need": "code", "label": "Game yaratish",
                 "loop_shape": "build_verify", "max_iter": 8, "max_repair": 3},
            ],
        }
        sup = TaskSupervisor()
        result = sup.run("pptx va game yarat", pipeline)
        self.assertIn(result["status"], ("ok", "partial"))
        self.assertGreaterEqual(len(result["results"]), 2)

    def test_combined_budget_awareness(self):
        """Budget awareness — 3 node = 40/3 ≈ 13 per node."""
        pipeline = {
            "need": "code",
            "label": "Kod",
            "loop_shape": "build_verify",
            "max_iter": 8,
            "max_repair": 3,
            "sub_pipelines": [
                {"need": "code", "label": "PPTX",
                 "loop_shape": "plan_then_execute", "max_iter": 1, "max_repair": 0},
                {"need": "code", "label": "Game",
                 "loop_shape": "build_verify", "max_iter": 8, "max_repair": 3},
            ],
        }
        sup = TaskSupervisor(total_budget=24)
        result = sup.run("pptx va game yarat", pipeline)
        # Budget should not be exceeded
        self.assertLessEqual(result["iterations_used"], 24)


if __name__ == "__main__":
    unittest.main(verbosity=2)
