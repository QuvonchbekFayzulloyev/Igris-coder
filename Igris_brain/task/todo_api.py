"""
IGRIS BRAIN — Todo API
=======================
FastAPI endpoints for todo management.

Endpoints:
    GET  /api/todos          - List all todos
    POST /api/todos          - Create new todo
    GET  /api/todos/{id}     - Get todo by ID
    PUT  /api/todos/{id}     - Update todo
    DELETE /api/todos/{id}   - Delete todo
    GET  /api/todos/stats    - Get statistics
    GET  /api/todos/sidebar  - Get sidebar data
"""

from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

_brain = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _brain not in sys.path:
    sys.path.insert(0, _brain)

from task.todo_manager import TodoManager, get_todo_manager

# FastAPI app
app = FastAPI(title="IGRIS Todo API")

# Pydantic models
class TodoCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    category: str = "general"
    tags: list = []

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    progress: Optional[int] = None
    tags: Optional[list] = None

class TodoResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    priority: str
    category: str
    progress: int
    created_at: str
    updated_at: str
    completed_at: str
    tags: list
    subtasks: list

# Routes
@app.get("/api/todos")
async def list_todos(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None
):
    """List all todos with optional filters."""
    manager = get_todo_manager()
    todos = manager.list_all(status=status, priority=priority, category=category)
    return {
        "todos": [t.to_dict() for t in todos],
        "count": len(todos)
    }

@app.post("/api/todos")
async def create_todo(todo: TodoCreate):
    """Create a new todo."""
    manager = get_todo_manager()
    new_todo = manager.add(
        title=todo.title,
        description=todo.description,
        priority=todo.priority,
        category=todo.category,
        tags=todo.tags
    )
    return new_todo.to_dict()

@app.get("/api/todos/stats")
async def get_stats():
    """Get todo statistics."""
    manager = get_todo_manager()
    return manager.get_stats()

@app.get("/api/todos/sidebar")
async def get_sidebar():
    """Get sidebar data."""
    manager = get_todo_manager()
    return manager.get_sidebar_data()

@app.get("/api/todos/markdown")
async def get_markdown():
    """Get todo list as markdown."""
    manager = get_todo_manager()
    return {"markdown": manager.render_markdown()}

@app.get("/api/todos/{todo_id}")
async def get_todo(todo_id: str):
    """Get a specific todo."""
    manager = get_todo_manager()
    todo = manager.get(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo.to_dict()

@app.put("/api/todos/{todo_id}")
async def update_todo(todo_id: str, update: TodoUpdate):
    """Update a todo."""
    manager = get_todo_manager()
    
    # Filter None values
    updates = {k: v for k, v in update.dict().items() if v is not None}
    
    todo = manager.update(todo_id, **updates)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    return todo.to_dict()

@app.delete("/api/todos/{todo_id}")
async def delete_todo(todo_id: str):
    """Delete a todo."""
    manager = get_todo_manager()
    if not manager.delete(todo_id):
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"message": "Todo deleted"}

@app.post("/api/todos/{todo_id}/complete")
async def complete_todo(todo_id: str):
    """Mark a todo as completed."""
    manager = get_todo_manager()
    todo = manager.update(todo_id, status="completed", progress=100)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo.to_dict()

@app.post("/api/todos/{todo_id}/progress")
async def update_progress(todo_id: str, progress: int):
    """Update todo progress."""
    manager = get_todo_manager()
    
    status = "pending"
    if progress == 100:
        status = "completed"
    elif progress > 0:
        status = "in_progress"
    
    todo = manager.update(todo_id, progress=progress, status=status)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    return todo.to_dict()

# Run with: uvicorn todo_api:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
