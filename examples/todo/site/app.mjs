import { addTodo, loadTodos, saveTodos, toggleTodo } from "./todo-store.mjs";

const form = document.querySelector("#todo-form");
const input = document.querySelector("#todo-input");
const list = document.querySelector("#todo-list");
const emptyState = document.querySelector("#empty-state");
let todos = loadTodos(window.localStorage);

function render() {
  list.replaceChildren();
  emptyState.hidden = todos.length > 0;

  for (const todo of todos) {
    const item = document.createElement("li");
    item.className = `todo-item${todo.completed ? " completed" : ""}`;

    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = todo.completed;
    checkbox.setAttribute("aria-label", `将“${todo.text}”标记为${todo.completed ? "未完成" : "已完成"}`);
    checkbox.addEventListener("change", () => {
      todos = toggleTodo(todos, todo.id);
      saveTodos(window.localStorage, todos);
      render();
    });

    const text = document.createElement("span");
    text.className = "todo-text";
    text.textContent = todo.text;

    const state = document.createElement("span");
    state.className = "todo-state";
    state.textContent = todo.completed ? "已完成" : "待完成";

    label.append(checkbox, text, state);
    item.append(label);
    list.append(item);
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const updated = addTodo(todos, input.value, crypto.randomUUID());
  if (updated === todos) return;
  todos = updated;
  saveTodos(window.localStorage, todos);
  input.value = "";
  render();
  input.focus();
});

render();
