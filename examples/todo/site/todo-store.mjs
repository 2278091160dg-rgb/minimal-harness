const STORAGE_KEY = "minimal-harness-todos";


export function addTodo(todos, text, id) {
  const normalized = text.trim();
  if (!normalized) return todos;
  return [...todos, { id, text: normalized, completed: false }];
}


export function toggleTodo(todos, id) {
  return todos.map((todo) =>
    todo.id === id ? { ...todo, completed: !todo.completed } : todo,
  );
}


export function saveTodos(storage, todos) {
  storage.setItem(STORAGE_KEY, JSON.stringify(todos));
}


export function loadTodos(storage) {
  const serialized = storage.getItem(STORAGE_KEY);
  if (!serialized) return [];
  try {
    const value = JSON.parse(serialized);
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}
