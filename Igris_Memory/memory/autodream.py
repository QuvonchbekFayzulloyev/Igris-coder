"""
CODER AGENT MEMORY — AutoDream Pipeline (Background Consolidation)
L1 -> L2 konsolidatsiya, 5-pass consolidation.

Pass 1: Session summary yaratish
Pass 2: Pattern aniqlash
Pass 3: Error/qiyinchiliklarni ajratish
Pass 4: Solution indekslash
Pass 5: Archive qilish
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional


class AutoDream:
    """
    AutoDream — L1 Runtime -> L2 Persistent konsolidatsiya tizimi.
    
    5-pass consolidation:
    1. Session summary: Session ma'lumotlarini yakunlash
    2. Pattern detection: Takroriy patternlarni aniqlash
    3. Error extraction: Xatolarni ajratish
    4. Solution indexing: Yechimlarni indekslash
    5. Archive: Eski ma'lumotlarni arxivlash
    """

    def __init__(self, runtime=None, persistent=None):
        """
        Args:
            runtime: RuntimeMemory instance
            persistent: PersistentMemory instance
        """
        self.runtime = runtime
        self.persistent = persistent
        self.consolidation_log: list[dict] = []

    def consolidate(self) -> dict:
        """
        Run full 5-pass consolidation.
        
        Returns:
            Consolidation stats
        """
        stats = {
            "pass_1_session": 0,
            "pass_2_patterns": 0,
            "pass_3_errors": 0,
            "pass_4_solutions": 0,
            "pass_5_archive": 0,
            "total": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not self.runtime or not self.persistent:
            return stats

        # Pass 1: Session summary
        stats["pass_1_session"] = self._pass1_session_summary()

        # Pass 2: Pattern detection
        stats["pass_2_patterns"] = self._pass2_pattern_detection()

        # Pass 3: Error extraction
        stats["pass_3_errors"] = self._pass3_error_extraction()

        # Pass 4: Solution indexing
        stats["pass_4_solutions"] = self._pass4_solution_indexing()

        # Pass 5: Archive stale entries
        stats["pass_5_archive"] = self._pass5_archive()

        stats["total"] = sum(v for k, v in stats.items() if k.startswith("pass_"))

        # Log consolidation
        self.consolidation_log.append(stats)

        return stats

    def _pass1_session_summary(self) -> int:
        """Pass 1: Create session summary and consolidate to L2."""
        count = 0

        # Get session info
        session = self.runtime.read_latest("session")
        if not session:
            return 0

        # Consolidate session entries
        entries_to_consolidate = {}
        for type_name in ["short-turn", "task-memory", "decision-log", "observation-memory",
                          "execution-memory", "reflection-memory", "planning-memory"]:
            entries = self.runtime.read(type_name, limit=50)
            if entries:
                entries_to_consolidate[type_name] = entries

        if entries_to_consolidate:
            count = self.persistent.consolidate_from_runtime(entries_to_consolidate)

        # Create experience entry
        experience_entry = {
            "id": f"exp-{session.get('id', 'unknown')}",
            "type": "experience",
            "sessions": [{
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "task": session.get("summary", "Session completed"),
                "outcome": "successful" if not session.get("errors_encountered") else "with_errors",
                "key_learnings": self._extract_learnings(),
                "tags": self._extract_tags(),
            }],
            "summary": session.get("summary", "")[:500],
        }
        self.persistent.write("experience", experience_entry, check_duplicate=True)

        return count

    def _pass2_pattern_detection(self) -> int:
        """Pass 2: Detect repeated patterns and store in pattern memory."""
        count = 0

        # Analyze execution patterns
        executions = self.runtime.read("execution-memory", limit=20)
        pattern_counts: dict[str, int] = {}

        for execution in executions:
            pattern = execution.get("execution_pattern", "")
            if pattern:
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        # Store patterns that appear 2+ times
        for pattern, freq in pattern_counts.items():
            if freq >= 2:
                pattern_entry = {
                    "id": f"pattern-detected-{hash(pattern)}",
                    "type": "pattern-memory",
                    "patterns": {
                        "detected": {
                            "pattern": pattern,
                            "frequency": freq,
                            "source": "auto_detection",
                        }
                    },
                    "summary": f"Detected pattern: {pattern} (freq: {freq})",
                }
                if self.persistent.write("pattern-memory", pattern_entry, check_duplicate=True):
                    count += 1

        # Analyze decision patterns
        decisions = self.runtime.read("decision-log", limit=10)
        for dec_log in decisions:
            for decision in dec_log.get("decisions", []):
                decision_type = decision.get("type", "")
                if decision_type:
                    pattern_entry = {
                        "id": f"decision-pattern-{hash(decision.get('title', ''))}",
                        "type": "pattern-memory",
                        "patterns": {
                            "decision": {
                                "type": decision_type,
                                "title": decision.get("title", ""),
                                "decision": decision.get("decision", ""),
                            }
                        },
                        "summary": f"Decision pattern: {decision.get('title', '')[:200]}",
                    }
                    if self.persistent.write("pattern-memory", pattern_entry, check_duplicate=True):
                        count += 1

        return count

    def _pass3_error_extraction(self) -> int:
        """Pass 3: Extract and catalog errors."""
        count = 0

        # Get errors from session
        session = self.runtime.read_latest("session")
        errors = session.get("errors_encountered", []) if session else []

        # Also check observation memory for code smells
        observations = self.runtime.read("observation-memory", limit=10)
        for obs in observations:
            code_smells = obs.get("observations", [])
            for item in code_smells:
                smells = item.get("code_smells", [])
                for smell in smells:
                    error_entry = {
                        "id": f"smell-{hash(smell)}",
                        "type": "error-memory",
                        "errors": [{
                            "title": smell,
                            "source": item.get("file", "unknown"),
                            "frequency": 1,
                        }],
                        "summary": f"Code smell: {smell}",
                    }
                    if self.persistent.write("error-memory", error_entry, check_duplicate=True):
                        count += 1

        # Store actual errors
        for error in errors:
            error_entry = {
                "id": f"error-{hash(error.get('message', ''))}",
                "type": "error-memory",
                "errors": [{
                    "title": error.get("message", "Unknown error"),
                    "root_cause": error.get("root_cause", ""),
                    "fix": error.get("fix", ""),
                    "resolved": error.get("resolved", False),
                    "frequency": 1,
                }],
                "summary": error.get("message", "")[:200],
            }
            if self.persistent.write("error-memory", error_entry, check_duplicate=True):
                count += 1

        return count

    def _pass4_solution_indexing(self) -> int:
        """Pass 4: Index solutions from completed tasks."""
        count = 0

        # Get completed tasks
        tasks = self.runtime.read("task-memory", limit=10)
        for task in tasks:
            progress = task.get("progress", {})
            if progress.get("status") == "done" or progress.get("percentage", 0) >= 100:
                solution_entry = {
                    "id": f"soln-{task.get('id', 'unknown')}",
                    "type": "solution-memory",
                    "solutions": [{
                        "id": f"SOL-{task.get('id', 'unknown')}",
                        "title": task.get("title", ""),
                        "problem": task.get("description", ""),
                        "solution": task.get("summary", ""),
                        "tags": self._extract_tags_from_task(task),
                        "complexity": "medium",
                        "reusability": "high",
                    }],
                    "summary": f"Solution: {task.get('title', '')[:200]}",
                }
                if self.persistent.write("solution-memory", solution_entry, check_duplicate=True):
                    count += 1

        return count

    def _pass5_archive(self) -> int:
        """Pass 5: Archive stale persistent entries."""
        stats = self.persistent.cleanup_stale(archive_days=30, delete_days=90)
        return stats.get("archived", 0) + stats.get("deleted", 0)

    def _extract_learnings(self) -> list[str]:
        """Extract key learnings from runtime memory."""
        learnings = []

        # From reflections
        reflections = self.runtime.read("reflection-memory", limit=5)
        for ref in reflections:
            learnings.extend(ref.get("improvement_suggestions", [])[:3])

        # From decisions
        decisions = self.runtime.read("decision-log", limit=5)
        for dec_log in decisions:
            for dec in dec_log.get("decisions", []):
                if dec.get("rationale"):
                    learnings.append(dec["rationale"][:200])

        return learnings[:10]

    def _extract_tags(self) -> list[str]:
        """Extract tags from current session."""
        tags = set()

        # From active context
        active = self.runtime.read_latest("active-context")
        if active:
            task = active.get("current_task", "")
            if task:
                tags.update(task.lower().split()[:5])

        # From task
        task = self.runtime.read_latest("task-memory")
        if task:
            title = task.get("title", "")
            if title:
                tags.update(title.lower().split()[:5])

        return list(tags)[:10]

    def _extract_tags_from_task(self, task: dict) -> list[str]:
        """Extract tags from a task entry."""
        tags = []
        title = task.get("title", "").lower()
        desc = task.get("description", "").lower()

        keyword_map = {
            "auth": ["authentication", "jwt", "token", "login"],
            "test": ["testing", "unit", "integration"],
            "db": ["database", "sql", "query"],
            "api": ["endpoint", "rest", "graphql"],
            "ui": ["frontend", "component", "style"],
            "deploy": ["deployment", "ci", "cd"],
        }

        combined = f"{title} {desc}"
        for keyword, related in keyword_map.items():
            if keyword in combined:
                tags.extend(related[:2])

        return list(set(tags))[:10]

    def get_stats(self) -> dict:
        """Get consolidation statistics."""
        return {
            "total_consolidations": len(self.consolidation_log),
            "last_consolidation": self.consolidation_log[-1] if self.consolidation_log else None,
        }
