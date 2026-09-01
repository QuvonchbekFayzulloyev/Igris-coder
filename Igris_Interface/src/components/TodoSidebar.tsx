import React, { useState, useEffect, useCallback } from 'react';

// Types
interface Todo {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  category: string;
  progress: number;
  created_at: string;
  updated_at: string;
}

interface TodoStats {
  total: number;
  completed: number;
  in_progress: number;
  pending: number;
  blocked: number;
  progress_percent: number;
  by_priority: Record<string, number>;
  by_category: Record<string, number>;
}

interface TodoSidebarProps {
  todos: Todo[];
  stats: TodoStats;
  onAddTodo: (title: string, priority: string, category: string) => void;
  onToggleStatus: (id: string, status: string) => void;
  onDeleteTodo: (id: string) => void;
  onUpdateProgress: (id: string, progress: number) => void;
}

// Priority Colors
const priorityColors: Record<string, string> = {
  urgent: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
};

// Priority Icons
const priorityIcons: Record<string, string> = {
  urgent: '🔴',
  high: '🟠',
  medium: '🟡',
  low: '🟢',
};

// Status Icons
const statusIcons: Record<string, string> = {
  pending: '⏳',
  in_progress: '🔄',
  completed: '✅',
  blocked: '🚫',
};

// Category Icons
const categoryIcons: Record<string, string> = {
  coding: '💻',
  debug: '🐛',
  testing: '🧪',
  docs: '📝',
  refactor: '♻️',
  feature: '✨',
  chore: '🔧',
  general: '📋',
};

// Todo Sidebar Component
export const TodoSidebar: React.FC<TodoSidebarProps> = ({
  todos,
  stats,
  onAddTodo,
  onToggleStatus,
  onDeleteTodo,
  onUpdateProgress,
}) => {
  const [newTodoTitle, setNewTodoTitle] = useState('');
  const [selectedPriority, setSelectedPriority] = useState('medium');
  const [selectedCategory, setSelectedCategory] = useState('general');
  const [showAddForm, setShowAddForm] = useState(false);
  const [expandedTodo, setExpandedTodo] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newTodoTitle.trim()) {
      onAddTodo(newTodoTitle.trim(), selectedPriority, selectedCategory);
      setNewTodoTitle('');
      setShowAddForm(false);
    }
  };

  const handleProgressChange = (id: string, value: number) => {
    onUpdateProgress(id, value);
    if (value === 100) {
      onToggleStatus(id, 'completed');
    } else if (value > 0) {
      onToggleStatus(id, 'in_progress');
    } else {
      onToggleStatus(id, 'pending');
    }
  };

  // Filter active todos
  const activeTodos = todos.filter(t => t.status !== 'completed');
  const completedTodos = todos.filter(t => t.status === 'completed');

  return (
    <div className="todo-sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <h3>📋 Todo List</h3>
        <button 
          className="add-todo-btn"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          {showAddForm ? '✕' : '+'}
        </button>
      </div>

      {/* Progress Bar */}
      <div className="progress-section">
        <div className="progress-info">
          <span>Progress</span>
          <span>{stats.progress_percent}%</span>
        </div>
        <div className="progress-bar">
          <div 
            className="progress-fill"
            style={{ width: `${stats.progress_percent}%` }}
          />
        </div>
        <div className="progress-stats">
          <span>{stats.completed}/{stats.total} completed</span>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="quick-stats">
        <div className="stat-item">
          <span className="stat-icon">⏳</span>
          <span className="stat-value">{stats.pending}</span>
          <span className="stat-label">Pending</span>
        </div>
        <div className="stat-item">
          <span className="stat-icon">🔄</span>
          <span className="stat-value">{stats.in_progress}</span>
          <span className="stat-label">In Progress</span>
        </div>
        <div className="stat-item">
          <span className="stat-icon">✅</span>
          <span className="stat-value">{stats.completed}</span>
          <span className="stat-label">Done</span>
        </div>
        <div className="stat-item">
          <span className="stat-icon">🚫</span>
          <span className="stat-value">{stats.blocked}</span>
          <span className="stat-label">Blocked</span>
        </div>
      </div>

      {/* Add Todo Form */}
      {showAddForm && (
        <form className="add-todo-form" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="What needs to be done?"
            value={newTodoTitle}
            onChange={(e) => setNewTodoTitle(e.target.value)}
            autoFocus
          />
          <div className="form-row">
            <select 
              value={selectedPriority}
              onChange={(e) => setSelectedPriority(e.target.value)}
            >
              <option value="low">🟢 Low</option>
              <option value="medium">🟡 Medium</option>
              <option value="high">🟠 High</option>
              <option value="urgent">🔴 Urgent</option>
            </select>
            <select 
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
            >
              <option value="general">📋 General</option>
              <option value="coding">💻 Coding</option>
              <option value="debug">🐛 Debug</option>
              <option value="testing">🧪 Testing</option>
              <option value="docs">📝 Docs</option>
              <option value="refactor">♻️ Refactor</option>
              <option value="feature">✨ Feature</option>
              <option value="chore">🔧 Chore</option>
            </select>
          </div>
          <button type="submit" className="submit-btn">
            Add Todo
          </button>
        </form>
      )}

      {/* Active Todos */}
      <div className="todos-section">
        <h4>🎯 Active Tasks ({activeTodos.length})</h4>
        <div className="todos-list">
          {activeTodos.length === 0 ? (
            <div className="empty-state">
              <p>No active tasks</p>
              <p className="hint">Click + to add a new todo</p>
            </div>
          ) : (
            activeTodos.map(todo => (
              <div 
                key={todo.id} 
                className={`todo-item ${expandedTodo === todo.id ? 'expanded' : ''}`}
              >
                <div className="todo-main">
                  <button 
                    className="status-btn"
                    onClick={() => {
                      const nextStatus = todo.status === 'pending' ? 'in_progress' : 
                                        todo.status === 'in_progress' ? 'completed' : 'pending';
                      onToggleStatus(todo.id, nextStatus);
                    }}
                  >
                    {statusIcons[todo.status]}
                  </button>
                  <div className="todo-content">
                    <div className="todo-title">
                      <span className="priority-badge" style={{ backgroundColor: priorityColors[todo.priority] }}>
                        {priorityIcons[todo.priority]}
                      </span>
                      <span className="category-icon">{categoryIcons[todo.category]}</span>
                      <span className="title-text">{todo.title}</span>
                    </div>
                    {todo.description && (
                      <p className="todo-desc">{todo.description}</p>
                    )}
                  </div>
                  <button 
                    className="expand-btn"
                    onClick={() => setExpandedTodo(expandedTodo === todo.id ? null : todo.id)}
                  >
                    {expandedTodo === todo.id ? '▼' : '▶'}
                  </button>
                </div>
                
                {expandedTodo === todo.id && (
                  <div className="todo-details">
                    <div className="progress-control">
                      <label>Progress: {todo.progress}%</label>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={todo.progress}
                        onChange={(e) => handleProgressChange(todo.id, parseInt(e.target.value))}
                      />
                    </div>
                    <div className="todo-actions">
                      <button 
                        className="delete-btn"
                        onClick={() => onDeleteTodo(todo.id)}
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Completed Todos */}
      {completedTodos.length > 0 && (
        <div className="todos-section completed-section">
          <h4>✅ Completed ({completedTodos.length})</h4>
          <div className="todos-list">
            {completedTodos.slice(-5).reverse().map(todo => (
              <div key={todo.id} className="todo-item completed">
                <button 
                  className="status-btn"
                  onClick={() => onToggleStatus(todo.id, 'pending')}
                >
                  {statusIcons.completed}
                </button>
                <div className="todo-content">
                  <span className="title-text">{todo.title}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Priority Distribution */}
      <div className="priority-distribution">
        <h4>📊 By Priority</h4>
        <div className="distribution-bar">
          {Object.entries(stats.by_priority).map(([priority, count]) => (
            count > 0 && (
              <div 
                key={priority}
                className="distribution-segment"
                style={{ 
                  backgroundColor: priorityColors[priority],
                  width: `${(count / stats.total) * 100}%`
                }}
                title={`${priority}: ${count}`}
              />
            )
          ))}
        </div>
      </div>
    </div>
  );
};

export default TodoSidebar;
