import assert from "node:assert/strict";
import test from "node:test";

import { addTodo, loadTodos, saveTodos, toggleTodo } from "./site/todo-store.mjs";


function memoryStorage() {
  const values = new Map();
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setItem(key, value) {
      values.set(key, value);
    },
  };
}


test("addTodo trims input and appends an incomplete item", () => {
  const todos = addTodo([], "  Write acceptance test  ", "todo-1");

  assert.deepEqual(todos, [{ id: "todo-1", text: "Write acceptance test", completed: false }]);
  assert.deepEqual(addTodo(todos, "   ", "todo-2"), todos);
});


test("toggleTodo changes only the selected item", () => {
  const todos = [
    { id: "todo-1", text: "First", completed: false },
    { id: "todo-2", text: "Second", completed: false },
  ];

  assert.deepEqual(toggleTodo(todos, "todo-2"), [
    { id: "todo-1", text: "First", completed: false },
    { id: "todo-2", text: "Second", completed: true },
  ]);
});


test("saveTodos and loadTodos preserve todo state across reloads", () => {
  const storage = memoryStorage();
  const todos = [{ id: "todo-1", text: "Persist me", completed: true }];

  saveTodos(storage, todos);

  assert.deepEqual(loadTodos(storage), todos);
});
