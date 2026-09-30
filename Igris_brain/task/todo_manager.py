"""
IGRIS BRAIN — Todo Manager
============================
Manages todo items for the chat interface.

Features:
    - Add, edit, delete todos
    - Categories and priorities
    - Progress tracking
    - Persistence (JSON storage)
    - Real-time updates
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

# Project paths
PROJECT_ROOT = Path(__file__).parent
TODO_FILE = PROJECT_ROOT / "todos.json"


class Priority(Enum):
    """Todo ustuvorlik darajasi."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Status(Enum):
    """Todo holati."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class Category(Enum):
    """Todo kategoriyasi."""
    GENERAL = "general"
    CODING = "coding"
    DEBUG = "debug"
    TESTING = "testing"
    DOCUMENTATION = "docs"
    REFACTOR = "refactor"
    FEATURE = "feature"
    CHORE = "chore"


@dataclass
class Todo:
    """Todo elementi."""
    id: str
    title: str
    description: str = ""
    status: str = "pending"
    priority: str = "medium"
    category: str = "general"
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    tags: list = None
    subtasks: list = None
    progress: int = 0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
        if self.tags is None:
            self.tags = []
        if self.subtasks is None:
            self.subtasks = []
    
    def to_dict(self) -> dict:
        """Dictionary format."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Todo':
        """Dictionary dan yaratish."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class TodoManager:
    """Todo boshqaruvchisi."""
    
    def __init__(self, filepath: str = None):
        self.filepath = Path(filepath) if filepath else TODO_FILE
        self.todos: list[Todo] = []
        self._load()
    
    def _load(self):
        """Todo larni fayldan yuklash."""
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.todos = [Todo.from_dict(t) for t in data.get("todos", [])]
            except Exception:
                self.todos = []
        else:
            self.todos = []
    
    def _save(self):
        """Todo larni faylga saqlash."""
        data = {
            "todos": [t.to_dict() for t in self.todos],
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _generate_id(self) -> str:
        """Unikal ID yaratish."""
        return f"todo_{int(time.time() * 1000)}_{len(self.todos)}"
    
    def add(self, title: str, description: str = "", priority: str = "medium",
            category: str = "general", tags: list = None) -> Todo:
        """Yangi todo qo'shish."""
        todo = Todo(
            id=self._generate_id(),
            title=title,
            description=description,
            priority=priority,
            category=category,
            tags=tags or [],
        )
        self.todos.append(todo)
        self._save()
        return todo
    
    def get(self, todo_id: str) -> Optional[Todo]:
        """Todo ni olish."""
        for todo in self.todos:
            if todo.id == todo_id:
                return todo
        return None
    
    def update(self, todo_id: str, **kwargs) -> Optional[Todo]:
        """Todo ni yangilash."""
        todo = self.get(todo_id)
        if not todo:
            return None
        
        for key, value in kwargs.items():
            if hasattr(todo, key):
                setattr(todo, key, value)
        
        todo.updated_at = datetime.now().isoformat()
        
        if todo.status == "completed" and not todo.completed_at:
            todo.completed_at = datetime.now().isoformat()
            todo.progress = 100
        
        self._save()
        return todo
    
    def delete(self, todo_id: str) -> bool:
        """Todo ni o'chirish."""
        for i, todo in enumerate(self.todos):
            if todo.id == todo_id:
                self.todos.pop(i)
                self._save()
                return True
        return False
    
    def list_all(self, status: str = None, priority: str = None, 
                 category: str = None) -> list[Todo]:
        """Barcha todo larni olish."""
        result = self.todos
        
        if status:
            result = [t for t in result if t.status == status]
        if priority:
            result = [t for t in result if t.priority == priority]
        if category:
            result = [t for t in result if t.category == category]
        
        return result
    
    def get_stats(self) -> dict:
        """Statistika olish."""
        total = len(self.todos)
        completed = sum(1 for t in self.todos if t.status == "completed")
        in_progress = sum(1 for t in self.todos if t.status == "in_progress")
        pending = sum(1 for t in self.todos if t.status == "pending")
        blocked = sum(1 for t in self.todos if t.status == "blocked")
        
        by_priority = {}
        for p in Priority:
            by_priority[p.value] = sum(1 for t in self.todos if t.priority == p.value)
        
        by_category = {}
        for c in Category:
            by_category[c.value] = sum(1 for t in self.todos if t.category == c.value)
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "blocked": blocked,
            "progress_percent": round(completed / total * 100 if total > 0 else 0),
            "by_priority": by_priority,
            "by_category": by_category,
        }
    
    def get_sidebar_data(self) -> dict:
        """Sidebar uchun ma'lumot."""
        stats = self.get_stats()
        active_todos = self.list_all(status="in_progress") + self.list_all(status="pending")
        
        return {
            "stats": stats,
            "todos": [t.to_dict() for t in active_todos[:10]],  # Faqat 10 ta
            "recent_completed": [t.to_dict() for t in self.list_all(status="completed")[-5:]],
        }
    
    def render_markdown(self) -> str:
        """Todo larni markdown formatda chiqarish."""
        stats = self.get_stats()
        
        lines = []
        lines.append("## 📋 Todo List")
        lines.append("")
        
        # Progress bar
        progress = stats["progress_percent"]
        filled = progress // 5
        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"**Progress:** [{bar}] {progress}%")
        lines.append(f"*{stats['completed']}/{stats['total']} completed*")
        lines.append("")
        
        # Stats
        lines.append("### 📊 Statistics")
        lines.append(f"- ⏳ Pending: {stats['pending']}")
        lines.append(f"- 🔄 In Progress: {stats['in_progress']}")
        lines.append(f"- ✅ Completed: {stats['completed']}")
        lines.append(f"- 🚫 Blocked: {stats['blocked']}")
        lines.append("")
        
        # Active todos
        active = self.list_all(status="in_progress") + self.list_all(status="pending")
        if active:
            lines.append("### 🎯 Active Tasks")
            for todo in active[:10]:
                priority_emoji = {
                    "urgent": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢",
                }.get(todo.priority, "⚪")
                
                status_emoji = {
                    "pending": "⏳",
                    "in_progress": "🔄",
                    "blocked": "🚫",
                }.get(todo.status, "❓")
                
                category_emoji = {
                    "coding": "💻",
                    "debug": "🐛",
                    "testing": "🧪",
                    "docs": "📝",
                    "refactor": "♻️",
                    "feature": "✨",
                    "chore": "🔧",
                    "general": "📋",
                }.get(todo.category, "📋")
                
                lines.append(f"- {priority_emoji} {status_emoji} {category_emoji} **{todo.title}**")
                if todo.description:
                    lines.append(f"  *{todo.description[:50]}*")
                if todo.progress > 0 and todo.progress < 100:
                    lines.append(f"  Progress: {todo.progress}%")
        
        return "\n".join(lines)


# Singleton
_manager: Optional[TodoManager] = None


def get_todo_manager() -> TodoManager:
    """Todo manager singleton."""
    global _manager
    if _manager is None:
        _manager = TodoManager()
    return _manager


__all__ = [
    "Todo",
    "TodoManager",
    "Priority",
    "Status",
    "Category",
    "get_todo_manager",
]
