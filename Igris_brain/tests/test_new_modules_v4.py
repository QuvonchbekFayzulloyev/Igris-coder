"""
IGRIS — Test Suite: New Modules (§13, §15, §17)
================================================
TaskQueue, ResourceControl, ResponseGenerator uchun to'liq testlar.
"""

import sys
import os
import time
import threading
import concurrent.futures

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_brain = os.path.join(_root, "Igris_brain")
if _brain not in sys.path:
    sys.path.insert(0, _brain)

from task.task_queue import TaskQueue, TaskPriority, TaskStatus, QueueTask
from monitor.resource_monitor import (
    ResourceControl, ResourceLimits, ResourceSnapshot, get_resources,
    ResourceViolation,
)
from agent.response_generator import (
    ResponseGenerator, VoicePolicy,
    format_progress, format_completion, format_failure, format_step_result,
)


# ======================================================================
# §15 — TaskQueue
# ======================================================================

def test_taskqueue_submit():
    """submit() task_id qaytaradi."""
    q = TaskQueue(max_concurrent=2)
    tid = q.submit({"task": "test"})
    assert isinstance(tid, str)
    assert tid.startswith("task-")
    assert q.pending_count == 1


def test_taskqueue_priority_ordering():
    """High priority oldinda bo'lishi kerak."""
    q = TaskQueue()
    q.submit({"t": "low"}, priority="low")
    q.submit({"t": "high"}, priority="high")
    q.submit({"t": "normal"}, priority="normal")

    info = q.queue_info()
    tasks = info["tasks"]
    assert tasks[0]["priority"] == "high"
    assert tasks[1]["priority"] == "normal"
    assert tasks[2]["priority"] == "low"


def test_taskqueue_cancel():
    """cancel() navbatdan o'chiradi."""
    q = TaskQueue()
    tid = q.submit({"t": "cancel-me"})
    assert q.cancel(tid) is True
    assert q.pending_count == 0
    info = q.queue_info()
    assert info["completed"] == 1
    # Cancel qilingan task completed ro'yxatida
    assert info["active_tasks"] == []


def test_taskqueue_cancel_nonexistent():
    """Yo'q task_id cancel qilsa — False."""
    q = TaskQueue()
    assert q.cancel("task-nonexistent") is False


def test_taskqueue_next_task():
    """next_task() birinchi taskni beradi."""
    q = TaskQueue(max_concurrent=1)
    tid = q.submit({"t": "first"})
    task = q.next_task()
    assert task is not None
    assert task.task_id == tid
    assert task.status == TaskStatus.RUNNING
    assert task.started_at is not None
    assert q.active_count == 1
    assert q.pending_count == 0


def test_taskqueue_next_task_concurrency():
    """max_concurrent=2 bo'lsa — 2 ta task active bo'lishi mumkin."""
    q = TaskQueue(max_concurrent=2)
    q.submit({"t": "a"})
    q.submit({"t": "b"})
    t1 = q.next_task()
    t2 = q.next_task()
    assert t1 is not None and t2 is not None
    assert q.active_count == 2
    # Uchinchisini ololmaymiz
    t3 = q.next_task()
    assert t3 is None


def test_taskqueue_complete_task():
    """complete_task() natija bilan yakunlaydi."""
    q = TaskQueue()
    q.submit({"t": "do"})
    task = q.next_task()
    q.complete_task(task.task_id, result={"output": "ok"})
    assert q.active_count == 0
    assert q.completed_count == 1
    info = q.queue_info()
    assert info["active_tasks"] == []


def test_taskqueue_complete_with_error():
    """Xatolik bilan yakunlash."""
    q = TaskQueue()
    q.submit({"t": "fail"})
    task = q.next_task()
    q.complete_task(task.task_id, error="boom")
    assert q.completed_count == 1
    info = q.queue_info()
    assert info["completed"] == 1


def test_taskqueue_queue_info():
    """queue_info() to'liq ma'lumot qaytaradi."""
    q = TaskQueue(max_concurrent=3)
    q.submit({"t": "a"})
    q.submit({"t": "b"})
    info = q.queue_info()
    assert "queued" in info
    assert "active" in info
    assert "completed" in info
    assert "max_concurrent" in info
    assert "tasks" in info
    assert "active_tasks" in info


def test_taskqueue_thread_safety():
    """Bir vaqtda ko'p thread'dan foydalanish — xatosiz."""
    q = TaskQueue()
    errors = []

    def submit_task(i):
        try:
            q.submit({"t": f"thread-{i}"})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=submit_task, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert q.pending_count == 20


def test_queuetask_to_dict():
    """QueueTask.to_dict() barcha maydonlarni qaytaradi."""
    task = QueueTask(task_id="t-1", payload={"x": 1})
    d = task.to_dict()
    assert d["task_id"] == "t-1"
    assert d["priority"] == "normal"
    assert d["status"] == "queued"
    assert "created_at" in d


# ======================================================================
# §15+§17 — ResourceControl
# ======================================================================

def test_get_resources():
    """get_resources() ResourceSnapshot qaytaradi."""
    snap = get_resources()
    assert isinstance(snap, ResourceSnapshot)
    assert snap.timestamp > 0
    assert snap.threads >= 1


def test_resource_snapshot_to_dict():
    """ResourceSnapshot.to_dict() barcha maydonlarni qaytaradi."""
    snap = ResourceSnapshot(cpu_percent=5.5, ram_mb=100.0)
    d = snap.to_dict()
    assert d["cpu_percent"] == 5.5
    assert d["ram_mb"] == 100.0
    assert "threads" in d


def test_resource_control_no_violations():
    """Past resurs ishlatilganda — xatolik yo'q."""
    rc = ResourceControl(ResourceLimits(max_ram_mb=999999, max_cpu_s=999999))
    snap = ResourceSnapshot(ram_mb=10.0, disk_write_mb=0.5)
    violations = rc.check(snap)
    assert len(violations) == 0
    assert rc.should_abort() is False


def test_resource_control_ram_violation():
    """RAM limit oshsa — violation."""
    rc = ResourceControl(ResourceLimits(max_ram_mb=50.0))
    snap = ResourceSnapshot(ram_mb=100.0)
    violations = rc.check(snap)
    assert len(violations) == 1
    assert violations[0].resource == "ram"
    assert violations[0].limit == 50.0
    assert violations[0].actual == 100.0
    assert rc.should_abort() is True


def test_resource_control_cpu_violation():
    """CPU vaqt limit oshsa — violation."""
    rc = ResourceControl(ResourceLimits(max_cpu_s=0.001))
    time.sleep(0.01)  # limitdan oshiramiz
    snap = ResourceSnapshot()
    violations = rc.check(snap)
    assert any(v.resource == "cpu" for v in violations)


def test_resource_control_disk_violation():
    """Disk write limit oshsa — violation."""
    rc = ResourceControl(ResourceLimits(max_disk_mb=0.001))
    snap = ResourceSnapshot(disk_write_mb=1.0)
    violations = rc.check(snap)
    assert len(violations) == 1
    assert violations[0].resource == "disk"


def test_resource_control_multiple_violations():
    """Bir nechta limit bir vaqtda buzilsa."""
    rc = ResourceControl(ResourceLimits(max_ram_mb=10, max_disk_mb=0.001))
    snap = ResourceSnapshot(ram_mb=100.0, disk_write_mb=5.0)
    violations = rc.check(snap)
    assert len(violations) >= 2


def test_resource_control_summary():
    """Summary to'liq hisobot beradi."""
    rc = ResourceControl(ResourceLimits(max_ram_mb=1))
    rc.check(ResourceSnapshot(ram_mb=100.0))
    s = rc.summary()
    assert "limits" in s
    assert "total_violations" in s
    assert "violations" in s
    assert "snapshots_count" in s
    assert s["total_violations"] == 1


def test_resource_control_reset():
    """Reset qilganda — hisob nolga tushadi."""
    rc = ResourceControl(ResourceLimits(max_ram_mb=1))
    rc.check(ResourceSnapshot(ram_mb=100.0))
    assert rc.should_abort() is True
    rc.reset()
    assert rc.should_abort() is False
    assert rc.summary()["total_violations"] == 0


def test_resource_control_limits_to_dict():
    """ResourceLimits.to_dict() barcha maydonlarni qaytaradi."""
    lim = ResourceLimits(max_ram_mb=256, max_cpu_s=60, max_disk_mb=50)
    d = lim.to_dict()
    assert d["max_ram_mb"] == 256
    assert d["max_cpu_s"] == 60
    assert d["max_disk_mb"] == 50


# ======================================================================
# §13 — ResponseGenerator
# ======================================================================

def test_format_progress():
    """format_progress() to'g'ri format qaytaradi."""
    assert format_progress(1, 5) == "Step 1 of 5"
    assert format_progress(3, 10, "Fetching") == "Step 3 of 10: Fetching"


def test_format_completion_ok():
    """format_completion() muvaffaqiyatli natija."""
    result = {"status": "completed", "tool_calls": [{"t": 1}, {"t": 2}]}
    text = format_completion(result)
    assert "completed" in text.lower() or "successfully" in text.lower()
    assert "2 step(s)" in text


def test_format_completion_with_matrix():
    """format_completion() requirement matrix bilan."""
    result = {"status": "completed", "tool_calls": []}
    matrix = {"req1": {"pass": True}, "req2": {"pass": False}}
    text = format_completion(result, matrix)
    assert "1/2" in text


def test_format_failure():
    """format_failure() xato + recovery beradi."""
    text = format_failure("timeout", "retry")
    assert "timeout" in text
    assert "retry" in text


def test_format_step_result():
    """format_step_result() qadam natijasini formatlaydi."""
    step = {"title": "Write file", "ok": True}
    text = format_step_result(0, 3, step)
    assert "Step 1 of 3" in text
    assert "done" in text


def test_format_step_result_failed():
    """Yakunlangan qadam."""
    step = {"title": "Fail here", "ok": False}
    text = format_step_result(0, 3, step)
    assert "failed" in text


def test_voice_policy_no_truncation():
    """Voice mode false bo'lsa — matn o'zgarmaydi."""
    vp = VoicePolicy(voice_mode=False)
    long_text = "word " * 100
    assert vp.apply(long_text) == long_text


def test_voice_policy_truncation():
    """Voice mode true bo'lsa — qisqartiriladi."""
    vp = VoicePolicy(voice_mode=True, max_words=5)
    long_text = "one two three four five six seven eight"
    short = vp.apply(long_text)
    assert len(short.split()) <= 6  # 5 words + "..."
    assert short.endswith("...")


def test_voice_policy_short_enough():
    """Voice mode true, lekin matn qisqa — o'zgarmaydi."""
    vp = VoicePolicy(voice_mode=True, max_words=10)
    short_text = "hello world"
    assert vp.apply(short_text) == short_text


def test_response_generator_generate():
    """ResponseGenerator.generate() to'liq javob beradi."""
    rg = ResponseGenerator(voice_mode=False)
    result = {"status": "completed", "tool_calls": [{"t": 1}]}
    progress = [{"title": "step1", "ok": True}]
    text = rg.generate("test task", result, progress)
    assert isinstance(text, str)
    assert len(text) > 0


def test_response_generator_generate_summary():
    """ResponseGenerator.generate_summary() qisqa javob beradi."""
    rg = ResponseGenerator(voice_mode=False)
    result = {
        "status": "completed",
        "tool_calls": [{"output": {"ok": True, "output": "file saved"}}],
    }
    text = rg.generate_summary(result)
    assert "Done" in text or "file saved" in text


def test_response_generator_history():
    """generate() dan keyin history to'ldiriladi."""
    rg = ResponseGenerator()
    rg.generate("t1", {"status": "completed"})
    assert len(rg.history) == 1
    assert rg.history[0]["task"] == "t1"


def test_response_generator_voice_mode():
    """Voice mode = True bo'lsa — javob qisqartiriladi."""
    rg = ResponseGenerator(voice_mode=True)
    result = {
        "status": "completed",
        "tool_calls": [{"output": {"ok": True, "output": "x" * 500}}],
    }
    text = rg.generate_summary(result)
    words = text.split()
    assert len(words) <= 55  # 50 max + overhead


# ======================================================================
# §17 — ResourceControl Integration
# ======================================================================

def test_resource_control_integration_flow():
    """To'liq sikl: get_resources → check → violations yoki yo'q."""
    rc = ResourceControl(ResourceLimits(max_ram_mb=999999))
    snap = get_resources()
    violations = rc.check(snap)
    summary = rc.summary()
    assert summary["snapshots_count"] == 1
    assert isinstance(violations, list)


def test_resource_control_accumulates_violations():
    """Bir nechta check — violations to'planadi."""
    rc = ResourceControl(ResourceLimits(max_ram_mb=1))
    for _ in range(3):
        rc.check(ResourceSnapshot(ram_mb=100.0))
    s = rc.summary()
    assert s["total_violations"] == 3
    assert s["snapshots_count"] == 3


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
