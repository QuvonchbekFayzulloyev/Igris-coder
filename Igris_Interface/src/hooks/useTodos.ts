import { useState, useEffect, useCallback } from 'react';

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
  tags: string[];
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

interface UseTodosReturn {
  todos: Todo[];
  stats: TodoStats;
  loading: boolean;
  error: string | null;
  addTodo: (title: string, priority?: string, category?: string, description?: string) => Promise<void>;
  updateTodo: (id: string, updates: Partial<Todo>) => Promise<void>;
  deleteTodo: (id: string) => Promise<void>;
  toggleStatus: (id: string, status: string) => Promise<void>;
  updateProgress: (id: string, progress: number) => Promise<void>;
  refreshTodos: () => Promise<void>;
}

const STORAGE_KEY = 'igris_todos';

// Default stats
const defaultStats: TodoStats = {
  total: 0,
  completed: 0,
  in_progress: 0,
  pending: 0,
  blocked: 0,
  progress_percent: 0,
  by_priority: { low: 0, medium: 0, high: 0, urgent: 0 },
  by_category: {},
};

export function useTodos(): UseTodosReturn {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [stats, setStats] = useState<TodoStats>(defaultStats);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Calculate stats from todos
  const calculateStats = useCallback((todoList: Todo[]): TodoStats => {
    const total = todoList.length;
    const completed = todoList.filter(t => t.status === 'completed').length;
    const in_progress = todoList.filter(t => t.status === 'in_progress').length;
    const pending = todoList.filter(t => t.status === 'pending').length;
    const blocked = todoList.filter(t => t.status === 'blocked').length;

    const by_priority: Record<string, number> = { low: 0, medium: 0, high: 0, urgent: 0 };
    const by_category: Record<string, number> = {};

    todoList.forEach(todo => {
      if (by_priority[todo.priority] !== undefined) {
        by_priority[todo.priority]++;
      }
      by_category[todo.category] = (by_category[todo.category] || 0) + 1;
    });

    return {
      total,
      completed,
      in_progress,
      pending,
      blocked,
      progress_percent: total > 0 ? Math.round((completed / total) * 100) : 0,
      by_priority,
      by_category,
    };
  }, []);

  // Load todos from localStorage
  const loadTodos = useCallback(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setTodos(parsed);
        setStats(calculateStats(parsed));
      }
    } catch (e) {
      console.error('Failed to load todos:', e);
      setError('Failed to load todos');
    } finally {
      setLoading(false);
    }
  }, [calculateStats]);

  // Save todos to localStorage
  const saveTodos = useCallback((newTodos: Todo[]) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newTodos));
      setTodos(newTodos);
      setStats(calculateStats(newTodos));
    } catch (e) {
      console.error('Failed to save todos:', e);
      setError('Failed to save todos');
    }
  }, [calculateStats]);

  // Generate unique ID
  const generateId = useCallback(() => {
    return `todo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  // Add todo
  const addTodo = useCallback(async (
    title: string,
    priority: string = 'medium',
    category: string = 'general',
    description: string = ''
  ) => {
    const newTodo: Todo = {
      id: generateId(),
      title,
      description,
      status: 'pending',
      priority: priority as Todo['priority'],
      category,
      progress: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      tags: [],
    };

    const newTodos = [...todos, newTodo];
    saveTodos(newTodos);
  }, [todos, saveTodos, generateId]);

  // Update todo
  const updateTodo = useCallback(async (id: string, updates: Partial<Todo>) => {
    const newTodos = todos.map(todo => {
      if (todo.id === id) {
        const updated = {
          ...todo,
          ...updates,
          updated_at: new Date().toISOString(),
        };
        
        // Auto-complete if progress is 100
        if (updated.progress === 100 && updated.status !== 'completed') {
          updated.status = 'completed';
        }
        
        return updated;
      }
      return todo;
    });

    saveTodos(newTodos);
  }, [todos, saveTodos]);

  // Delete todo
  const deleteTodo = useCallback(async (id: string) => {
    const newTodos = todos.filter(todo => todo.id !== id);
    saveTodos(newTodos);
  }, [todos, saveTodos]);

  // Toggle status
  const toggleStatus = useCallback(async (id: string, status: string) => {
    await updateTodo(id, { status: status as Todo['status'] });
  }, [updateTodo]);

  // Update progress
  const updateProgress = useCallback(async (id: string, progress: number) => {
    const updates: Partial<Todo> = { progress };
    
    if (progress === 100) {
      updates.status = 'completed';
    } else if (progress > 0) {
      updates.status = 'in_progress';
    } else {
      updates.status = 'pending';
    }
    
    await updateTodo(id, updates);
  }, [updateTodo]);

  // Refresh todos
  const refreshTodos = useCallback(async () => {
    setLoading(true);
    loadTodos();
  }, [loadTodos]);

  // Load on mount
  useEffect(() => {
    loadTodos();
  }, [loadTodos]);

  return {
    todos,
    stats,
    loading,
    error,
    addTodo,
    updateTodo,
    deleteTodo,
    toggleStatus,
    updateProgress,
    refreshTodos,
  };
}

export default useTodos;
