"""
IGRIS BRAIN — Todo Templates
==============================
Predefined templates for common development tasks.

Features:
    - 20+ built-in templates
    - Custom template creation
    - Template categories
    - Quick task creation from templates
    - Template variables

Usage:
    from todo_templates import TemplateManager
    
    manager = TemplateManager()
    
    # List templates
    templates = manager.list_templates()
    
    # Create todo from template
    todo = manager.create_from_template("bugfix", title="Fix login bug")
    
    # Create custom template
    manager.create_template(
        name="custom_deploy",
        title="Deploy {service} to {environment}",
        subtasks=["Build", "Test", "Deploy", "Verify"],
        category="chore"
    )
"""

from __future__ import annotations

import json
import os
import sys
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

_brain = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _brain not in sys.path:
    sys.path.insert(0, _brain)

from task.todo_manager import TodoManager, get_todo_manager


# ---------------------------------------------------------------- #
# Template Data
# ---------------------------------------------------------------- #

@dataclass
class TodoTemplate:
    """Todo shabloni."""
    name: str
    title: str
    description: str = ""
    priority: str = "medium"
    category: str = "general"
    subtasks: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    checklist: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)


# Built-in templates
BUILTIN_TEMPLATES = {
    # Bug Fixes
    "bugfix": TodoTemplate(
        name="bugfix",
        title="Fix: {title}",
        description="Bug fix for: {description}",
        priority="high",
        category="debug",
        subtasks=[
            "Reproduce the bug",
            "Identify root cause",
            "Implement fix",
            "Write test case",
            "Verify fix",
        ],
        checklist=[
            "Bug reproduced",
            "Root cause identified",
            "Fix implemented",
            "Tests passing",
            "Code reviewed",
        ],
    ),
    
    "hotfix": TodoTemplate(
        name="hotfix",
        title="Hotfix: {title}",
        description="Critical hotfix: {description}",
        priority="urgent",
        category="debug",
        subtasks=[
            "Identify issue",
            "Create hotfix branch",
            "Implement fix",
            "Test fix",
            "Deploy to production",
            "Monitor",
        ],
    ),
    
    # Features
    "feature": TodoTemplate(
        name="feature",
        title="Feature: {title}",
        description="New feature: {description}",
        priority="medium",
        category="feature",
        subtasks=[
            "Define requirements",
            "Design solution",
            "Implement feature",
            "Write tests",
            "Update documentation",
            "Code review",
        ],
        checklist=[
            "Requirements documented",
            "Design approved",
            "Implementation complete",
            "Tests added",
            "Documentation updated",
            "PR created",
        ],
    ),
    
    "feature_api": TodoTemplate(
        name="feature_api",
        title="API Feature: {title}",
        description="New API endpoint: {description}",
        priority="medium",
        category="feature",
        subtasks=[
            "Design API schema",
            "Implement endpoint",
            "Add validation",
            "Write tests",
            "Update API docs",
            "Add to SDK",
        ],
    ),
    
    # Refactoring
    "refactor": TodoTemplate(
        name="refactor",
        title="Refactor: {title}",
        description="Code refactoring: {description}",
        priority="low",
        category="refactor",
        subtasks=[
            "Analyze current code",
            "Identify improvements",
            "Implement changes",
            "Run tests",
            "Update documentation",
        ],
    ),
    
    "refactor_module": TodoTemplate(
        name="refactor_module",
        title="Module Refactor: {title}",
        description="Module restructuring: {description}",
        priority="medium",
        category="refactor",
        subtasks=[
            "Document current structure",
            "Plan new structure",
            "Move files/classes",
            "Update imports",
            "Run all tests",
            "Update documentation",
        ],
    ),
    
    # Testing
    "test": TodoTemplate(
        name="test",
        title="Add tests: {title}",
        description="Write tests for: {description}",
        priority="medium",
        category="testing",
        subtasks=[
            "Identify test cases",
            "Write unit tests",
            "Write integration tests",
            "Run test suite",
            "Check coverage",
        ],
        checklist=[
            "Test cases identified",
            "Unit tests written",
            "Integration tests written",
            "All tests passing",
            "Coverage > 80%",
        ],
    ),
    
    "test_e2e": TodoTemplate(
        name="test_e2e",
        title="E2E Tests: {title}",
        description="End-to-end testing: {description}",
        priority="medium",
        category="testing",
        subtasks=[
            "Define test scenarios",
            "Set up test environment",
            "Write test scripts",
            "Run tests",
            "Fix failures",
            "Document results",
        ],
    ),
    
    # Documentation
    "docs": TodoTemplate(
        name="docs",
        title="Documentation: {title}",
        description="Update documentation: {description}",
        priority="low",
        category="docs",
        subtasks=[
            "Review existing docs",
            "Identify gaps",
            "Write/update content",
            "Add examples",
            "Review and publish",
        ],
    ),
    
    "docs_api": TodoTemplate(
        name="docs_api",
        title="API Documentation: {title}",
        description="Document API: {description}",
        priority="medium",
        category="docs",
        subtasks=[
            "Document endpoints",
            "Add request/response examples",
            "Document error codes",
            "Add authentication docs",
            "Create usage guide",
        ],
    ),
    
    # Deployment
    "deploy": TodoTemplate(
        name="deploy",
        title="Deploy: {title}",
        description="Deployment task: {description}",
        priority="high",
        category="chore",
        subtasks=[
            "Check prerequisites",
            "Run tests",
            "Build artifacts",
            "Deploy to staging",
            "Verify staging",
            "Deploy to production",
            "Verify production",
            "Monitor",
        ],
        checklist=[
            "Tests passing",
            "Build successful",
            "Staging verified",
            "Production verified",
            "Monitoring active",
        ],
    ),
    
    "deploy_rollback": TodoTemplate(
        name="deploy_rollback",
        title="Rollback: {title}",
        description="Rollback deployment: {description}",
        priority="urgent",
        category="chore",
        subtasks=[
            "Identify issue",
            "Stop deployment",
            "Revert changes",
            "Verify rollback",
            "Notify team",
            "Post-mortem",
        ],
    ),
    
    # Code Review
    "review": TodoTemplate(
        name="review",
        title="Code Review: {title}",
        description="Review code: {description}",
        priority="medium",
        category="general",
        subtasks=[
            "Review code quality",
            "Check tests",
            "Verify documentation",
            "Test locally",
            "Approve/Request changes",
        ],
    ),
    
    # Performance
    "performance": TodoTemplate(
        name="performance",
        title="Performance: {title}",
        description="Performance optimization: {description}",
        priority="high",
        category="feature",
        subtasks=[
            "Profile current performance",
            "Identify bottlenecks",
            "Implement optimizations",
            "Benchmark before/after",
            "Document improvements",
        ],
    ),
    
    "performance_db": TodoTemplate(
        name="performance_db",
        title="DB Performance: {title}",
        description="Database optimization: {description}",
        priority="high",
        category="feature",
        subtasks=[
            "Analyze slow queries",
            "Add indexes",
            "Optimize queries",
            "Test performance",
            "Document changes",
        ],
    ),
    
    # Security
    "security": TodoTemplate(
        name="security",
        title="Security: {title}",
        description="Security task: {description}",
        priority="high",
        category="chore",
        subtasks=[
            "Identify vulnerability",
            "Assess risk",
            "Implement fix",
            "Test fix",
            "Update security docs",
        ],
    ),
    
    "security_audit": TodoTemplate(
        name="security_audit",
        title="Security Audit: {title}",
        description="Security audit: {description}",
        priority="high",
        category="chore",
        subtasks=[
            "Run security scan",
            "Review dependencies",
            "Check permissions",
            "Review auth flows",
            "Document findings",
            "Create fix plan",
        ],
    ),
    
    # Setup
    "setup": TodoTemplate(
        name="setup",
        title="Setup: {title}",
        description="Setup task: {description}",
        priority="medium",
        category="chore",
        subtasks=[
            "Check prerequisites",
            "Install dependencies",
            "Configure settings",
            "Test setup",
            "Document steps",
        ],
    ),
    
    "setup_dev": TodoTemplate(
        name="setup_dev",
        title="Dev Setup: {title}",
        description="Development environment setup: {description}",
        priority="medium",
        category="chore",
        subtasks=[
            "Clone repository",
            "Install dependencies",
            "Set up database",
            "Configure environment",
            "Run migrations",
            "Verify setup",
        ],
    ),
    
    # Migration
    "migration": TodoTemplate(
        name="migration",
        title="Migration: {title}",
        description="Data/code migration: {description}",
        priority="high",
        category="chore",
        subtasks=[
            "Plan migration",
            "Backup data",
            "Create migration scripts",
            "Test migration",
            "Run migration",
            "Verify results",
            "Clean up",
        ],
    ),
    
    # Research
    "research": TodoTemplate(
        name="research",
        title="Research: {title}",
        description="Research task: {description}",
        priority="low",
        category="general",
        subtasks=[
            "Define research question",
            "Gather information",
            "Analyze findings",
            "Document conclusions",
            "Share with team",
        ],
    ),
}


# ---------------------------------------------------------------- #
# Template Manager
# ---------------------------------------------------------------- #

class TemplateManager:
    """Shablon boshqaruvchisi."""
    
    def __init__(self, custom_templates_file: str = None):
        self.builtin = BUILTIN_TEMPLATES.copy()
        self.custom: dict[str, TodoTemplate] = {}
        self.custom_file = Path(custom_templates_file) if custom_templates_file else None
        self._load_custom()
    
    def _load_custom(self):
        """Maxsus shablonlarni yuklash."""
        if self.custom_file and self.custom_file.exists():
            try:
                with open(self.custom_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, tpl_data in data.items():
                        self.custom[name] = TodoTemplate(**tpl_data)
            except Exception:
                pass
    
    def _save_custom(self):
        """Maxsus shablonlarni saqlash."""
        if self.custom_file:
            self.custom_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.custom_file, "w", encoding="utf-8") as f:
                json.dump(
                    {name: tpl.to_dict() for name, tpl in self.custom.items()},
                    f, indent=2, ensure_ascii=False
                )
    
    def list_templates(self, category: str = None) -> list[TodoTemplate]:
        """Shablonlar ro'yxati."""
        all_templates = list(self.builtin.values()) + list(self.custom.values())
        
        if category:
            all_templates = [t for t in all_templates if t.category == category]
        
        return sorted(all_templates, key=lambda t: t.name)
    
    def get_template(self, name: str) -> Optional[TodoTemplate]:
        """Shablonni olish."""
        return self.builtin.get(name) or self.custom.get(name)
    
    def create_template(
        self,
        name: str,
        title: str,
        description: str = "",
        priority: str = "medium",
        category: str = "general",
        subtasks: list = None,
        checklist: list = None,
        tags: list = None,
    ) -> TodoTemplate:
        """Yangi shablon yaratish."""
        if name in self.builtin:
            raise ValueError(f"Template '{name}' already exists as builtin")
        
        template = TodoTemplate(
            name=name,
            title=title,
            description=description,
            priority=priority,
            category=category,
            subtasks=subtasks or [],
            checklist=checklist or [],
            tags=tags or [],
        )
        
        self.custom[name] = template
        self._save_custom()
        
        return template
    
    def delete_template(self, name: str) -> bool:
        """Shablonni o'chirish."""
        if name in self.builtin:
            return False  # Can't delete builtin
        
        if name in self.custom:
            del self.custom[name]
            self._save_custom()
            return True
        
        return False
    
    def create_from_template(
        self,
        template_name: str,
        title: str = None,
        description: str = None,
        **kwargs
    ) -> Optional[dict]:
        """Shablondan todo yaratish.
        
        Returns:
            Todo ma'lumotlari dict formatda
        """
        template = self.get_template(template_name)
        if not template:
            return None
        
        # Apply variables
        variables = kwargs.copy()
        if title:
            variables["title"] = title
        if description:
            variables["description"] = description
        
        # Substitute variables in title
        todo_title = template.title
        for key, value in variables.items():
            todo_title = todo_title.replace(f"{{{key}}}", str(value))
        
        # Substitute variables in description
        todo_desc = template.description
        for key, value in variables.items():
            todo_desc = todo_desc.replace(f"{{{key}}}", str(value))
        
        return {
            "title": todo_title,
            "description": todo_desc,
            "priority": template.priority,
            "category": template.category,
            "subtasks": template.subtasks.copy(),
            "checklist": template.checklist.copy(),
            "tags": template.tags.copy(),
        }
    
    def render_template(self, template_name: str) -> str:
        """Shablonni markdown formatda chiqarish."""
        template = self.get_template(template_name)
        if not template:
            return f"Template '{template_name}' not found"
        
        lines = []
        lines.append(f"## Template: {template.name}")
        lines.append(f"**Category:** {template.category}")
        lines.append(f"**Priority:** {template.priority}")
        lines.append("")
        lines.append(f"**Title:** {template.title}")
        if template.description:
            lines.append(f"**Description:** {template.description}")
        lines.append("")
        
        if template.subtasks:
            lines.append("### Subtasks")
            for i, subtask in enumerate(template.subtasks, 1):
                lines.append(f"{i}. [ ] {subtask}")
            lines.append("")
        
        if template.checklist:
            lines.append("### Checklist")
            for item in template.checklist:
                lines.append(f"- [ ] {item}")
            lines.append("")
        
        return "\n".join(lines)
    
    def list_categories(self) -> list[str]:
        """Barcha kategoriyalar."""
        all_templates = list(self.builtin.values()) + list(self.custom.values())
        categories = list(set(t.category for t in all_templates))
        return sorted(categories)


# ---------------------------------------------------------------- #
# Integration with TodoManager
# ---------------------------------------------------------------- #

class TemplateTodoManager:
    """Shablon + Todo integratsiyasi."""
    
    def __init__(self):
        self.template_manager = TemplateManager()
        self.todo_manager = get_todo_manager()
    
    def create_todo_from_template(
        self,
        template_name: str,
        title: str = None,
        description: str = None,
        **kwargs
    ) -> Optional[str]:
        """Shablondan todo yaratish.
        
        Returns:
            Todo ID
        """
        todo_data = self.template_manager.create_from_template(
            template_name, title=title, description=description, **kwargs
        )
        
        if not todo_data:
            return None
        
        # Create main todo
        todo = self.todo_manager.add(
            title=todo_data["title"],
            description=todo_data["description"],
            priority=todo_data["priority"],
            category=todo_data["category"],
            tags=todo_data["tags"],
        )
        
        # Create subtasks
        for subtask_title in todo_data["subtasks"]:
            self.todo_manager.add(
                title=f"  └─ {subtask_title}",
                description=f"Subtask of: {todo.title}",
                priority=todo_data["priority"],
                category=todo_data["category"],
            )
        
        return todo.id
    
    def quick_create(self, template_name: str, **kwargs) -> str:
        """Tez yaratish."""
        todo_id = self.create_todo_from_template(template_name, **kwargs)
        if todo_id:
            return f"Created todo from template '{template_name}'"
        return f"Template '{template_name}' not found"
    
    def get_template_help(self) -> str:
        """Yordam matni."""
        templates = self.template_manager.list_templates()
        
        lines = ["Available Templates:"]
        lines.append("")
        
        categories = self.template_manager.list_categories()
        for category in categories:
            cat_templates = [t for t in templates if t.category == category]
            lines.append(f"**{category.upper()}**")
            for tpl in cat_templates:
                lines.append(f"  - {tpl.name}: {tpl.title}")
            lines.append("")
        
        lines.append("Usage:")
        lines.append("  /todo template <name> <title>")
        lines.append("  /todo templates")
        
        return "\n".join(lines)


# ---------------------------------------------------------------- #
# Singleton
# ---------------------------------------------------------------- #

_template_manager: Optional[TemplateManager] = None
_template_todo_manager: Optional[TemplateTodoManager] = None


def get_template_manager() -> TemplateManager:
    """Template manager singleton."""
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager


def get_template_todo_manager() -> TemplateTodoManager:
    """Template todo manager singleton."""
    global _template_todo_manager
    if _template_todo_manager is None:
        _template_todo_manager = TemplateTodoManager()
    return _template_todo_manager


__all__ = [
    "TodoTemplate",
    "BUILTIN_TEMPLATES",
    "TemplateManager",
    "TemplateTodoManager",
    "get_template_manager",
    "get_template_todo_manager",
]
