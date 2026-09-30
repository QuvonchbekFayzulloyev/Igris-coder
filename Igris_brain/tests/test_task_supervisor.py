"""
IGRIS BRAIN — Task Supervisor tests (§9 Scaling to Complex Tasks)
==================================================================

Qamrov:
  - TaskNode       : status, serialization
  - TaskDAG        : add/get_ready/topological_order/predecessor_results
  - WorkingContext  : context rot prevention (compact)
  - CheckpointManager: save/load/clear
  - TaskSupervisor : is_atomic, build_dag, run (with placeholder agent)
"""

import json
import os
import sys
import tempfile
import unittest

_test_dir = os.path.dirname(os.path.abspath(__file__))
_brain = os.path.dirname(_test_dir)
sys.path.insert(0, _brain)
sys.path.insert(0, os.path.join(os.path.dirname(_brain), "Igris_Memory"))

from task.task_supervisor import (  # noqa: E402
    TaskNode,
    NodeStatus,
    TaskDAG,
    WorkingContext,
    TaskCheckpoint,
    CheckpointManager,
    TaskSupervisor,
)


class TestTaskNode(unittest.TestCase):
    def test_default_status_is_pending(self):
        n = TaskNode(id="a", description="test", need="code")
        self.assertEqual(n.status, NodeStatus.PENDING)

    def test_serialization_roundtrip(self):
        n = TaskNode(id="a", description="test", need="code", predecessors=["b"])
        n.status = NodeStatus.COMPLETED
        n.result = "done"
        d = n.to_dict()
        n2 = TaskNode.from_dict(d)
        self.assertEqual(n2.id, "a")
        self.assertEqual(n2.status, NodeStatus.COMPLETED)
        self.assertEqual(n2.result, "done")
        self.assertEqual(n2.predecessors, ["b"])


class TestTaskDAG(unittest.TestCase):
    def test_empty_dag_is_complete(self):
        dag = TaskDAG()
        self.assertTrue(dag.is_complete())

    def test_single_node_ready(self):
        dag = TaskDAG([TaskNode(id="a", description="a", need="code")])
        ready = dag.get_ready()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].id, "a")

    def test_dependent_node_not_ready_until_predecessor_completed(self):
        a = TaskNode(id="a", description="a", need="code")
        b = TaskNode(id="b", description="b", need="code", predecessors=["a"])
        dag = TaskDAG([a, b])

        ready = dag.get_ready()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].id, "a")

        a.status = NodeStatus.COMPLETED
        ready = dag.get_ready()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].id, "b")

    def test_topological_order(self):
        a = TaskNode(id="a", description="a", need="code")
        b = TaskNode(id="b", description="b", need="code", predecessors=["a"])
        c = TaskNode(id="c", description="c", need="code", predecessors=["a", "b"])
        dag = TaskDAG([a, b, c])
        order = dag.topological_order()
        self.assertIn("a", order)
        self.assertIn("b", order)
        self.assertIn("c", order)
        # a before b, b before c
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("b"), order.index("c"))

    def test_predecessor_results(self):
        a = TaskNode(id="a", description="a", need="code", result="a_result")
        b = TaskNode(id="b", description="b", need="code", predecessors=["a"])
        dag = TaskDAG([a, b])
        results = dag.predecessor_results("b")
        self.assertEqual(results, {"a": "a_result"})

    def test_serialization_roundtrip(self):
        a = TaskNode(id="a", description="a", need="code")
        b = TaskNode(id="b", description="b", need="code", predecessors=["a"])
        dag = TaskDAG([a, b])
        d = dag.to_dict()
        dag2 = TaskDAG.from_dict(d)
        self.assertEqual(set(dag2.nodes.keys()), {"a", "b"})
        self.assertEqual(dag2.nodes["b"].predecessors, ["a"])

    def test_has_failures(self):
        a = TaskNode(id="a", description="a", need="code")
        a.status = NodeStatus.FAILED
        dag = TaskDAG([a])
        self.assertTrue(dag.has_failures())

    def test_parallel_ready_nodes(self):
        a = TaskNode(id="a", description="a", need="code")
        b = TaskNode(id="b", description="b", need="code")
        dag = TaskDAG([a, b])
        ready = dag.get_ready()
        self.assertEqual(len(ready), 2)


class TestWorkingContext(unittest.TestCase):
    def test_build_context_block(self):
        ctx = WorkingContext()
        ctx.set_goal("build a dashboard")
        ctx.set_plan(["plan", "code", "test"])
        ctx.add_observation("tool", "wrote file.ts")
        block = ctx.build_context_block()
        self.assertIn("build a dashboard", block)
        self.assertIn("plan → code → test", block)
        self.assertIn("wrote file.ts", block)

    def test_compaction_reduces_size(self):
        ctx = WorkingContext(max_context_chars=500)
        ctx.set_goal("test")
        # Add many observations to trigger compaction
        for i in range(20):
            ctx.add_observation("tool", f"observation {i}: " + "x" * 100)
        # Should be compacted — fewer observations
        self.assertLess(len(ctx.observations), 20)
        # Recent observations should still be there
        self.assertIn("observation 19", ctx.observations[-1]["content"])

    def test_dependency_tracking(self):
        ctx = WorkingContext()
        ctx.update_dependency("node_a", "completed")
        ctx.update_dependency("node_b", "failed")
        block = ctx.build_context_block()
        self.assertIn("node_a=completed", block)
        self.assertIn("node_b=failed", block)

    def test_total_chars(self):
        ctx = WorkingContext()
        ctx.add_observation("tool", "hello")
        self.assertEqual(ctx.total_chars(), 5)


class TestCheckpointManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_and_load(self):
        mgr = CheckpointManager(self.tmpdir)
        dag = TaskDAG([TaskNode(id="a", description="a", need="code")])
        cp = TaskCheckpoint(
            task_id="t1",
            goal="test goal",
            dag=dag.to_dict(),
            active_node_id="a",
            active_stage="edit",
            budget_remaining=30,
        )
        mgr.save(cp)
        loaded = mgr.load("t1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.goal, "test goal")
        self.assertEqual(loaded.active_node_id, "a")
        self.assertEqual(loaded.budget_remaining, 30)

    def test_load_nonexistent_returns_none(self):
        mgr = CheckpointManager(self.tmpdir)
        self.assertIsNone(mgr.load("nonexistent"))

    def test_clear(self):
        mgr = CheckpointManager(self.tmpdir)
        cp = TaskCheckpoint(task_id="t1", goal="g", dag={})
        mgr.save(cp)
        mgr.clear("t1")
        self.assertIsNone(mgr.load("t1"))

    def test_task_and_exec_files_separate(self):
        mgr = CheckpointManager(self.tmpdir)
        cp = TaskCheckpoint(
            task_id="t1", goal="g", dag={},
            active_node_id="a", active_stage="edit",
        )
        mgr.save(cp)
        task_file = os.path.join(self.tmpdir, "task_t1.json")
        exec_file = os.path.join(self.tmpdir, "exec_t1.json")
        self.assertTrue(os.path.exists(task_file))
        self.assertTrue(os.path.exists(exec_file))
        # task file has goal/dag, exec file has active_node_id
        with open(task_file) as f:
            td = json.load(f)
        self.assertEqual(td["goal"], "g")
        with open(exec_file) as f:
            ed = json.load(f)
        self.assertEqual(ed["active_node_id"], "a")


class TestTaskSupervisor(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_is_atomic_simple_chat(self):
        sup = TaskSupervisor()
        pipeline = {"need": "chat", "sub_pipelines": []}
        self.assertTrue(sup.is_atomic("salom", pipeline))

    def test_is_atomic_with_subs(self):
        sup = TaskSupervisor()
        pipeline = {
            "need": "draw",
            "sub_pipelines": [{"need": "code"}],
        }
        self.assertFalse(sup.is_atomic("rasm chiz va kod yoz", pipeline))

    def test_build_dag_single_node(self):
        sup = TaskSupervisor()
        pipeline = {"need": "chat", "label": "Suhbat"}
        dag = sup.build_dag("salom", pipeline)
        self.assertEqual(len(dag.nodes), 1)
        self.assertIn("main", dag.nodes)

    def test_build_dag_with_sub_pipelines(self):
        sup = TaskSupervisor()
        pipeline = {
            "need": "draw",
            "label": "Chizma",
            "sub_pipelines": [
                {"need": "code", "label": "Kod"},
            ],
        }
        dag = sup.build_dag("rasm chiz va kod yoz", pipeline)
        self.assertEqual(len(dag.nodes), 2)
        self.assertIn("main", dag.nodes)
        self.assertIn("sub_0_code", dag.nodes)
        # code sub depends on main
        self.assertEqual(dag.nodes["sub_0_code"].predecessors, ["main"])

    def test_run_atomic_placeholder(self):
        sup = TaskSupervisor()
        pipeline = {"need": "chat", "label": "Suhbat", "sub_pipelines": []}
        result = sup.run("salom", pipeline)
        self.assertEqual(result["status"], "ok")
        self.assertIn("main", result["results"])

    def test_run_with_checkpoint(self):
        sup = TaskSupervisor(checkpoint_dir=self.tmpdir)
        pipeline = {"need": "chat", "label": "Suhbat", "sub_pipelines": []}
        result = sup.run("salom", pipeline)
        self.assertEqual(result["status"], "ok")
        # Checkpoint should exist
        loaded = sup.checkpoint_mgr.load(sup._task_id)
        self.assertIsNotNone(loaded)

    def test_budget_tracking(self):
        sup = TaskSupervisor(total_budget=10)
        pipeline = {"need": "chat", "label": "Suhbat", "sub_pipelines": []}
        result = sup.run("salom", pipeline)
        self.assertLessEqual(result["iterations_used"], 10)

    def test_resume_from_checkpoint(self):
        sup1 = TaskSupervisor(checkpoint_dir=self.tmpdir)
        pipeline = {"need": "chat", "label": "Suhbat", "sub_pipelines": []}
        result1 = sup1.run("salom", pipeline)
        task_id = sup1._task_id

        # Resume
        sup2 = TaskSupervisor(checkpoint_dir=self.tmpdir)
        result2 = sup2.resume(task_id)
        self.assertIsNotNone(result2)
        self.assertEqual(result2["resumed_from"], task_id)
        self.assertEqual(result2["status"], "ok")  # M14: to'liq tugallangan

    def test_dag_complete_with_all_completed(self):
        sup = TaskSupervisor()
        dag = TaskDAG([
            TaskNode(id="a", description="a", need="code"),
            TaskNode(id="b", description="b", need="code", predecessors=["a"]),
        ])
        sup.dag = dag
        dag.nodes["a"].status = NodeStatus.COMPLETED
        dag.nodes["b"].status = NodeStatus.COMPLETED
        self.assertTrue(dag.is_complete())

    def test_aggregation(self):
        sup = TaskSupervisor()
        sup.dag = TaskDAG([
            TaskNode(id="a", description="a", need="code", result="result_a"),
            TaskNode(id="b", description="b", need="code", result="result_b"),
        ])
        summary = sup._aggregate({"a": "result_a", "b": "result_b"})
        self.assertIn("result_a", summary)
        self.assertIn("result_b", summary)



# ------------------------------------------------------------------
# LLMDAGPlanner tests
# ------------------------------------------------------------------

class TestLLMDAGPlanner(unittest.TestCase):
    """LLM orqali DAG planning."""

    def test_plan_returns_none_without_llm(self):
        from task.task_supervisor import LLMDAGPlanner
        planner = LLMDAGPlanner(llm=None)
        result = planner.plan("complex task", {"need": "code"})
        self.assertIsNone(result)

    def test_parse_dag_json_valid(self):
        from task.task_supervisor import LLMDAGPlanner
        planner = LLMDAGPlanner()
        json_str = '{"tasks": [{"id": "t1", "description": "scaffold", "need": "code", "predecessors": []}, {"id": "t2", "description": "test", "need": "code", "predecessors": ["t1"]}]}'
        dag = planner._parse_dag_json(json_str)
        self.assertIsNotNone(dag)
        self.assertEqual(len(dag.nodes), 2)
        self.assertEqual(dag.nodes["t1"].predecessors, [])
        self.assertEqual(dag.nodes["t2"].predecessors, ["t1"])

    def test_parse_dag_json_with_code_block(self):
        from task.task_supervisor import LLMDAGPlanner
        planner = LLMDAGPlanner()
        json_str = '```json\n{"tasks": [{"id": "t1", "description": "draw", "need": "draw", "predecessors": []}]}```'
        dag = planner._parse_dag_json(json_str)
        self.assertIsNotNone(dag)
        self.assertEqual(len(dag.nodes), 1)

    def test_parse_dag_json_invalid_returns_none(self):
        from task.task_supervisor import LLMDAGPlanner
        planner = LLMDAGPlanner()
        self.assertIsNone(planner._parse_dag_json("not json at all"))

    def test_parse_dag_json_invalid_need_falls_back_to_chat(self):
        from task.task_supervisor import LLMDAGPlanner
        planner = LLMDAGPlanner()
        json_str = '{"tasks": [{"id": "t1", "description": "x", "need": "unknown_type", "predecessors": []}]}'
        dag = planner._parse_dag_json(json_str)
        self.assertIsNotNone(dag)
        self.assertEqual(dag.nodes["t1"].need, "chat")

    def test_parse_dag_json_filters_bad_predecessors(self):
        from task.task_supervisor import LLMDAGPlanner
        planner = LLMDAGPlanner()
        json_str = '{"tasks": [{"id": "t1", "description": "x", "need": "code", "predecessors": ["nonexistent"]}]}'
        dag = planner._parse_dag_json(json_str)
        self.assertIsNotNone(dag)
        self.assertEqual(dag.nodes["t1"].predecessors, [])

    def test_plan_with_mock_llm(self):
        from task.task_supervisor import LLMDAGPlanner

        class MockLLM:
            def complete(self, prompt, system=None):
                return '{"tasks": [{"id": "t1", "description": "code", "need": "code", "predecessors": []}, {"id": "t2", "description": "test", "need": "code", "predecessors": ["t1"]}]}'

        planner = LLMDAGPlanner(llm=MockLLM())
        dag = planner.plan("yoz va test qil", {"need": "code"})
        self.assertIsNotNone(dag)
        self.assertEqual(len(dag.nodes), 2)


class TestGitCheckpointManager(unittest.TestCase):
    """Git commit at checkpoint — rollback support."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_inherits_from_checkpoint_manager(self):
        from task.task_supervisor import GitCheckpointManager, CheckpointManager
        mgr = GitCheckpointManager(self.tmpdir)
        self.assertIsInstance(mgr, CheckpointManager)

    def test_save_without_git_still_works(self):
        from task.task_supervisor import GitCheckpointManager, TaskCheckpoint
        # Non-git directory — save should still work
        mgr = GitCheckpointManager(self.tmpdir, repo_dir=self.tmpdir)
        cp = TaskCheckpoint(task_id="t1", goal="test", dag={})
        mgr.save(cp)  # Should not raise
        loaded = mgr.load("t1")
        self.assertIsNotNone(loaded)

    def test_list_checkpoints_empty(self):
        from task.task_supervisor import GitCheckpointManager
        mgr = GitCheckpointManager(self.tmpdir, repo_dir=self.tmpdir)
        # Non-git dir — should return empty list
        result = mgr.list_checkpoints()
        self.assertEqual(result, [])

    def test_get_last_commit_nonexistent(self):
        from task.task_supervisor import GitCheckpointManager
        mgr = GitCheckpointManager(self.tmpdir, repo_dir=self.tmpdir)
        result = mgr.get_last_checkpoint_commit("nonexistent")
        self.assertIsNone(result)


class TestSupervisorFailureBudget(unittest.TestCase):
    """M1: FAILED node budget YEGI + cheksiz retry yo'q + halol "partial".

    Eski xato: budget faqat SUCCESS'da kamayardi, `_self_revise` esa
    deterministik xato bilan yiqilayotgan node'ni cheksiz PENDING ga
    qaytarardi → while hech qachon tugamasdi (hang).
    """

    class _BoomAgent:
        """Har chaqiruvda yiqiladigan agent — deterministik xato."""

        def __init__(self):
            self.calls = 0

        def llm_available(self):
            return False

        def chat(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("deterministik xato")

    def test_failed_node_consumes_budget_and_terminates(self):
        agent = self._BoomAgent()
        sup = TaskSupervisor(agent=agent, total_budget=10)
        pipeline = {"need": "code", "label": "Kod", "sub_pipelines": []}
        result = sup.run("kod yoz", pipeline)  # cheksiz loop BO'LMAYDI
        # 1 initial + 1 retry (repairs_used < 1) — keyin skip
        self.assertEqual(agent.calls, 2)
        self.assertEqual(result["status"], "partial")  # halol yakun
        self.assertGreaterEqual(result["iterations_used"], 1)
        self.assertEqual(result["nodes"]["main"]["status"], "failed")

    def test_failed_node_skip_keeps_failed_status(self):
        """Skip = vazifa bajarilmadi → FAILED (soxta COMPLETED emas)."""
        agent = self._BoomAgent()
        sup = TaskSupervisor(agent=agent, total_budget=10)
        pipeline = {"need": "code", "label": "Kod", "sub_pipelines": []}
        result = sup.run("kod yoz", pipeline)
        node = result["nodes"]["main"]
        self.assertEqual(node["status"], "failed")
        self.assertIn("skipped", str(node.get("result") or ""))
        self.assertNotEqual(node["status"], "completed")

    def test_budget_actually_decreases_on_failures(self):
        agent = self._BoomAgent()
        sup = TaskSupervisor(agent=agent, total_budget=10)
        pipeline = {"need": "code", "label": "Kod", "sub_pipelines": []}
        sup.run("kod yoz", pipeline)
        self.assertLess(sup.budget_remaining, 10)
        self.assertGreaterEqual(sup.budget_remaining, 0)

    def test_zero_budget_terminates_immediately(self):
        sup = TaskSupervisor(total_budget=0)
        pipeline = {"need": "chat", "label": "Suhbat", "sub_pipelines": []}
        result = sup.run("salom", pipeline)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["iterations_used"], 0)


class TestLLMFixNodeCollision(unittest.TestCase):
    """M11: LLM DAG tuzatishda mavjud ID berlsa — mavjud node OVERWRITE
    bo'lmasligi kerak ("main" ga tushib qolsa butun DAG buzar edi)."""

    def test_add_fix_node_existing_id_gets_unique_suffix(self):
        sup = TaskSupervisor()
        sup.dag = TaskDAG([TaskNode(id="main", description="m", need="code")])
        failed = sup.dag.nodes["main"]
        failed.status = NodeStatus.FAILED
        failed.error = "xato"

        class _FixLLM:
            model = "test"

            @staticmethod
            def complete(prompt, system=None):
                return '{"action": "add_fix_node", "id": "main", ' \
                       '"description": "dupe", "need": "code"}'

        sup.agent = type("A", (), {"llm": _FixLLM(),
                                   "llm_available": lambda self: True})()
        revised = sup._llm_self_revise(failed)
        self.assertTrue(revised)
        self.assertNotIn("main", [p for p in failed.predecessors if p == "main"],
                         "failed node o'ziga predecessor bo'lmasligi kerak")
        # main endi fix node bilan emas — unique ID bilan qo'shilgan
        self.assertIn("main_1", sup.dag.nodes)
        self.assertEqual(sup.dag.nodes["main"].description, "m")


class TestSupervisorResumeBudget(unittest.TestCase):
    """M13/M14: resume() ham budget guard + halol status qaytaradi.

    Eski xato: budget 0 bo'lsa ham node'lar bajarilaverardi va qolgan
    pending node'lar bilan soxta "ok" qaytardi.
    """

    def test_resume_stops_when_budget_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp:
            sup1 = TaskSupervisor(checkpoint_dir=tmp)
            pipeline = {"need": "code", "label": "Kod", "sub_pipelines": []}
            sup1.run("kod yoz", pipeline)
            task_id = sup1._task_id
            # resume() budgetni checkpoint'dan tiklaydi — shuning uchun
            # checkpoint'ning o'zida budgetni 0 ga tushiramiz.
            cp = sup1.checkpoint_mgr.load(task_id)
            base_used = int(cp.total_iterations_used or 0)
            cp.budget_remaining = 0
            sup1.checkpoint_mgr.save(cp)

            sup2 = TaskSupervisor(checkpoint_dir=tmp)
            result2 = sup2.resume(task_id)
            self.assertIsNotNone(result2)
            # Yangi ish BAJARILMAGAN — faqat base'dan qolgan iteratsiyalar
            self.assertEqual(result2["iterations_used"], base_used)
            # M14b: resume natijasi run() bilan BIR XIL kontrat
            self.assertIn("nodes", result2)
            self.assertIn("tool_calls", result2)
            self.assertIn("files_changed", result2)

    def test_resume_incomplete_dag_reports_partial(self):
        """Pending node qolsa (budget tugashi) — "ok" EMAS "partial"."""
        with tempfile.TemporaryDirectory() as tmp:
            sup = TaskSupervisor(checkpoint_dir=tmp, total_budget=5)
            dag = TaskDAG([
                TaskNode(id="main", description="m", need="code"),
                TaskNode(id="sub_0_code", description="s", need="code",
                         predecessors=["main"]),
            ])
            # main tugallangan, sub hali pending — DAG to'liq emas
            dag.nodes["main"].status = NodeStatus.COMPLETED
            dag.nodes["main"].result = "main natija"
            dag.nodes["sub_0_code"].status = NodeStatus.PENDING
            sup.dag = dag
            sup.context.set_goal("test")
            sup._task_id = "task_test_partial"
            sup._save_checkpoint()
            # Checkpoint'da budget 0 — resume hech narsa bajarolmaydi
            cp = sup.checkpoint_mgr.load("task_test_partial")
            cp.budget_remaining = 0
            sup.checkpoint_mgr.save(cp)

            sup2 = TaskSupervisor(checkpoint_dir=tmp)
            result = sup2.resume("task_test_partial")
            self.assertEqual(result["status"], "partial")
            self.assertNotIn("sub_0_code", result["results"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
