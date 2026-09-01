"""
IGRIS BRAIN — Todo Integration
================================
Integrates todo management with the chat pipeline.

Features:
    - Auto-detect todo commands in chat
    - Track task progress automatically
    - Show todo status in responses
    - Manage todos via chat commands

Chat Commands:
    /todo add <title>     - Add new todo
    /todo list            - List all todos
    /todo done <id>       - Mark todo as completed
    /todo progress <id> <percent> - Update progress
    /todo delete <id>     - Delete todo
    /todo stats           - Show statistics
    /todo clear           - Clear completed todos
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, Callable

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from todo_manager import TodoManager, get_todo_manager, Priority, Status, Category


# ---------------------------------------------------------------- #
# Command Detection
# ---------------------------------------------------------------- #

TODO_COMMAND_PATTERN = re.compile(
    r"^/todo\s+"
    r"(add|list|done|complete|progress|delete|remove|stats|clear|help|template|templates)"
    r"(?:\s+(.+))?$",
    re.IGNORECASE,
)

# Natural language todo patterns
TODO_NL_PATTERNS = [
    # English
    (r"(?:add|create|new|make)\s+(?:a\s+)?(?:todo|task|item)[\s:]+(.+)", "add"),
    (r"(?:mark|set|complete|done)\s+(?:todo|task)?\s*(?:#?(\d+))?\s+(?:as\s+)?(?:done|complete|finished)", "done"),
    (r"(?:show|list|display|what(?:'s|s| are))\s+(?:my\s+)?(?:todos?|tasks?|items?)", "list"),
    (r"(?:show|what(?:'s|s))\s+todo\s+(?:stats?|statistics?)", "stats"),
    (r"(?:delete|remove|drop)\s+(?:todo|task)?\s*#?(\d+)", "delete"),
    
    # Uzbek
    (r"(?:qo'sh|yarat|yangi)\s+(?:vazifa|todo|task)[\s:]+(.+)", "add"),
    (r"(?:bajar|tugat|yakunla)\s+(?:vazifa)?\s*#?(\d+)", "done"),
    (r"(?:ko'rsat|ro'yxat)\s+(?:vazifalar?|todo)", "list"),
    (r"(?:o'chir|yo'q|olib\s+tashla)\s+(?:vazifa)?\s*#?(\d+)", "delete"),
]


class TodoCommand:
    """Todo buyruq aniqlash va bajarish."""
    
    def __init__(self, manager: TodoManager = None):
        self.manager = manager or get_todo_manager()
    
    def detect(self, message: str) -> Optional[dict]:
        """Xabarda todo buyrug'i borligini tekshirish.
        
        Returns:
            {"type": "todo_command", "action": str, "args": dict} or None
        """
        message = message.strip()
        
        # Check /todo command
        match = TODO_COMMAND_PATTERN.match(message)
        if match:
            action = match.group(1).lower()
            args_str = match.group(2) or ""
            return {
                "type": "todo_command",
                "action": action,
                "args": self._parse_args(action, args_str),
            }
        
        # Check natural language patterns
        for pattern, action in TODO_NL_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    "type": "todo_command",
                    "action": action,
                    "args": self._parse_nl_args(action, match),
                }
        
        return None
    
    def _parse_args(self, action: str, args_str: str) -> dict:
        """Buyruq argumentlarini parse qilish."""
        args = args_str.strip()
        
        if action == "add":
            # Parse priority and category from title
            priority = "medium"
            category = "general"
            
            # Check for priority markers
            if re.search(r"\b(urgent|shoshilinch)\b", args, re.IGNORECASE):
                priority = "urgent"
            elif re.search(r"\b(high|yuqori)\b", args, re.IGNORECASE):
                priority = "high"
            elif re.search(r"\b(low|past)\b", args, re.IGNORECASE):
                priority = "low"
            
            # Check for category markers
            if re.search(r"\b(bug|xato|fix|debug)\b", args, re.IGNORECASE):
                category = "debug"
            elif re.search(r"\b(test|sinov)\b", args, re.IGNORECASE):
                category = "testing"
            elif re.search(r"\b(doc|documentation|hujjat)\b", args, re.IGNORECASE):
                category = "docs"
            elif re.search(r"\b(code|kod|dastur)\b", args, re.IGNORECASE):
                category = "coding"
            elif re.search(r"\b(feature|yangilik)\b", args, re.IGNORECASE):
                category = "feature"
            
            return {"title": args, "priority": priority, "category": category}
        
        elif action in ("done", "complete"):
            # Extract todo ID or title
            id_match = re.match(r"#?(\d+)", args)
            if id_match:
                return {"todo_id": int(id_match.group(1))}
            return {"title": args}
        
        elif action == "progress":
            # Parse: progress <id> <percent>
            parts = args.split()
            if len(parts) >= 2:
                return {
                    "todo_id": int(parts[0].replace("#", "")),
                    "progress": int(parts[1].replace("%", "")),
                }
            return {}
        
        elif action in ("delete", "remove"):
            id_match = re.match(r"#?(\d+)", args)
            if id_match:
                return {"todo_id": int(id_match.group(1))}
            return {"title": args}
        
        return {"raw": args}
    
    def _parse_nl_args(self, action: str, match: re.Match) -> dict:
        """Natural language argumentlarni parse qilish."""
        if action == "add":
            title = match.group(1) if match.lastindex else ""
            return {"title": title.strip(), "priority": "medium", "category": "general"}
        elif action in ("done", "delete"):
            id_str = match.group(1) if match.lastindex else ""
            return {"todo_id": int(id_str) if id_str else None}
        return {}
    
    def execute(self, command: dict) -> str:
        """Buyruqni bajarish va javob qaytarish."""
        action = command.get("action", "")
        args = command.get("args", {})
        
        if action == "add":
            return self._handle_add(args)
        elif action == "list":
            return self._handle_list()
        elif action in ("done", "complete"):
            return self._handle_done(args)
        elif action == "progress":
            return self._handle_progress(args)
        elif action in ("delete", "remove"):
            return self._handle_delete(args)
        elif action == "stats":
            return self._handle_stats()
        elif action == "clear":
            return self._handle_clear()
        elif action == "help":
            return self._handle_help()
        elif action == "template":
            return self._handle_template(args)
        elif action == "templates":
            return self._handle_templates()
        
        return f"Unknown todo action: {action}"
    
    def _handle_add(self, args: dict) -> str:
        """Todo qo'shish."""
        title = args.get("title", "")
        if not title:
            return "Please provide a todo title. Example: /todo add Fix login bug"
        
        todo = self.manager.add(
            title=title,
            priority=args.get("priority", "medium"),
            category=args.get("category", "general"),
        )
        
        return (
            f"Todo added: #{todo.id.split('_')[-1]} {todo.title}\n"
            f"Priority: {todo.priority} | Category: {todo.category}"
        )
    
    def _handle_list(self) -> str:
        """Todo larni ko'rsatish."""
        todos = self.manager.list_all()
        
        if not todos:
            return "No todos yet. Add one with: /todo add <title>"
        
        lines = ["Todo List:"]
        for i, todo in enumerate(todos):
            status_icon = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]",
                "blocked": "[!]",
            }.get(todo.status, "[ ]")
            
            priority_icon = {
                "urgent": "!",
                "high": "^",
                "medium": "-",
                "low": ".",
            }.get(todo.priority, "-")
            
            lines.append(
                f"{i+1}. {status_icon} [{priority_icon}] {todo.title}"
                f" ({todo.status}, {todo.progress}%)"
            )
        
        return "\n".join(lines)
    
    def _handle_done(self, args: dict) -> str:
        """Todo ni bajarilgan deb belgilash."""
        todo_id = args.get("todo_id")
        title = args.get("title")
        
        if todo_id:
            # Find by index
            todos = self.manager.list_all()
            if 0 < todo_id <= len(todos):
                todo = todos[todo_id - 1]
                self.manager.update(todo.id, status="completed", progress=100)
                return f"Completed: {todo.title}"
        
        if title:
            # Find by title
            for todo in self.manager.list_all():
                if title.lower() in todo.title.lower():
                    self.manager.update(todo.id, status="completed", progress=100)
                    return f"Completed: {todo.title}"
        
        return "Todo not found. Use /todo list to see available todos."
    
    def _handle_progress(self, args: dict) -> str:
        """Todo progressini yangilash."""
        todo_id = args.get("todo_id")
        progress = args.get("progress", 0)
        
        if not todo_id:
            return "Please specify todo ID. Example: /todo progress 1 50"
        
        todos = self.manager.list_all()
        if 0 < todo_id <= len(todos):
            todo = todos[todo_id - 1]
            status = "completed" if progress >= 100 else "in_progress" if progress > 0 else "pending"
            self.manager.update(todo.id, progress=progress, status=status)
            return f"Updated {todo.title}: {progress}%"
        
        return "Todo not found."
    
    def _handle_delete(self, args: dict) -> str:
        """Todo ni o'chirish."""
        todo_id = args.get("todo_id")
        title = args.get("title")
        
        if todo_id:
            todos = self.manager.list_all()
            if 0 < todo_id <= len(todos):
                todo = todos[todo_id - 1]
                self.manager.delete(todo.id)
                return f"Deleted: {todo.title}"
        
        if title:
            for todo in self.manager.list_all():
                if title.lower() in todo.title.lower():
                    self.manager.delete(todo.id)
                    return f"Deleted: {todo.title}"
        
        return "Todo not found."
    
    def _handle_stats(self) -> str:
        """Statistika ko'rsatish."""
        stats = self.manager.get_stats()
        
        return (
            f"Todo Statistics:\n"
            f"  Total: {stats['total']}\n"
            f"  Pending: {stats['pending']}\n"
            f"  In Progress: {stats['in_progress']}\n"
            f"  Completed: {stats['completed']}\n"
            f"  Blocked: {stats['blocked']}\n"
            f"  Progress: {stats['progress_percent']}%"
        )
    
    def _handle_clear(self) -> str:
        """Bajarilgan todo larni tozalash."""
        completed = self.manager.list_all(status="completed")
        
        for todo in completed:
            self.manager.delete(todo.id)
        
        return f"Cleared {len(completed)} completed todos."
    
    def _handle_help(self) -> str:
        """Yordam."""
        return (
            "Todo Commands:\n"
            "  /todo add <title> - Add new todo\n"
            "  /todo list - List all todos\n"
            "  /todo done <number> - Mark as completed\n"
            "  /todo progress <number> <percent> - Update progress\n"
            "  /todo delete <number> - Delete todo\n"
            "  /todo stats - Show statistics\n"
            "  /todo clear - Clear completed todos\n"
            "  /todo template <name> <title> - Create from template\n"
            "  /todo templates - List all templates\n"
            "  /todo help - Show this help\n"
            "\n"
            "You can also say naturally:\n"
            "  'Add todo: Fix login bug'\n"
            "  'Mark todo 1 as done'\n"
            "  'Show my todos'\n"
            "  'Create bugfix: Fix auth'"
        )
    
    def _handle_template(self, args: dict) -> str:
        """Shablondan todo yaratish."""
        from todo_templates import get_template_todo_manager
        
        template_todo = get_template_todo_manager()
        
        # Parse: template <name> <title>
        raw = args.get("raw", "")
        parts = raw.split(maxsplit=1)
        
        if len(parts) < 1 or not parts[0]:
            return "Usage: /todo template <name> <title>\nExample: /todo template bugfix Fix login bug"
        
        template_name = parts[0]
        title = parts[1] if len(parts) > 1 else None
        
        result = template_todo.quick_create(template_name, title=title)
        return result
    
    def _handle_templates(self) -> str:
        """Shablonlar ro'yxati."""
        from todo_templates import get_template_todo_manager
        
        template_todo = get_template_todo_manager()
        return template_todo.get_template_help()


# ---------------------------------------------------------------- #
# Chat Pipeline Integration
# ---------------------------------------------------------------- #

class TodoChatIntegration:
    """Chat pipeline bilan todo integratsiyasi."""
    
    def __init__(self):
        self.command = TodoCommand()
        self.auto_track = True  # Avtomatik task tracking
    
    def process_message(self, message: str) -> Optional[dict]:
        """Xabarni qayta ishlash.
        
        Returns:
            {"is_todo": True, "response": str, "data": dict} or None
        """
        # Check for todo command
        command = self.command.detect(message)
        
        if command:
            response = self.command.execute(command)
            return {
                "is_todo": True,
                "response": response,
                "data": command,
            }
        
        return None
    
    def should_auto_track(self, message: str, pipeline: dict) -> bool:
        """Avtomatik tracking kerakligini aniqlash."""
        if not self.auto_track:
            return False
        
        # Track complex tasks
        need = pipeline.get("need", "")
        if need in ("code", "ui_build", "draw"):
            return True
        
        # Track requests with multiple steps
        if any(word in message.lower() for word in ["and", "then", "also", "va", "keyin"]):
            return True
        
        return False
    
    def create_tracking_todo(self, message: str, pipeline: dict) -> Optional[str]:
        """Tracking uchun todo yaratish."""
        if not self.should_auto_track(message, pipeline):
            return None
        
        need = pipeline.get("need", "general")
        category = {
            "code": "coding",
            "draw": "feature",
            "ui_build": "feature",
            "debug": "debug",
            "testing": "testing",
        }.get(need, "general")
        
        todo = self.command.manager.add(
            title=f"Complete task: {message[:50]}...",
            description=f"Pipeline: {need}",
            priority="medium",
            category=category,
        )
        
        return todo.id
    
    def update_tracking_todo(self, todo_id: str, status: str, progress: int = None):
        """Tracking todo ni yangilash."""
        updates = {"status": status}
        if progress is not None:
            updates["progress"] = progress
        
        self.command.manager.update(todo_id, **updates)
    
    def get_todo_context(self) -> str:
        """LLM uchun todo kontekstini olish."""
        todos = self.command.manager.list_all(status="in_progress")
        
        if not todos:
            return ""
        
        lines = ["Active tasks:"]
        for todo in todos[:5]:  # Faqat 5 ta
            lines.append(f"- {todo.title} ({todo.progress}%)")
        
        return "\n".join(lines)


# Singleton
_integration: Optional[TodoChatIntegration] = None


def get_todo_integration() -> TodoChatIntegration:
    """Todo integration singleton."""
    global _integration
    if _integration is None:
        _integration = TodoChatIntegration()
    return _integration


__all__ = [
    "TodoCommand",
    "TodoChatIntegration",
    "get_todo_integration",
]
