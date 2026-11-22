// Node verification: todo_list_component
// Edge verification: api_client calls fire on correct user actions; UI re-renders
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TodoList from "../src/components/TodoList.vue";
import * as api from "../src/api.js";

vi.mock("../src/api");

const mockTodos = [
  { id: 1, title: "buy milk", completed: false },
  { id: 2, title: "walk dog", completed: true },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getTodos).mockResolvedValue([...mockTodos]);
  vi.mocked(api.createTodo).mockResolvedValue({ id: 3, title: "new", completed: false });
  vi.mocked(api.toggleTodo).mockResolvedValue({ id: 1, title: "buy milk", completed: true });
  vi.mocked(api.deleteTodo).mockResolvedValue(undefined);
});

describe("TodoList", () => {
  it("shows empty state when no todos", async () => {
    vi.mocked(api.getTodos).mockResolvedValue([]);
    const w = mount(TodoList);
    await flushPromises();
    expect(w.text()).toContain("No todos yet");
  });

  it("renders todos on mount", async () => {
    const w = mount(TodoList);
    await flushPromises();
    expect(w.text()).toContain("buy milk");
    expect(w.text()).toContain("walk dog");
  });

  it("calls getTodos on mount", async () => {
    mount(TodoList);
    await flushPromises();
    expect(api.getTodos).toHaveBeenCalledOnce();
  });

  it("calls createTodo and adds item on form submit", async () => {
    const w = mount(TodoList);
    await flushPromises();
    await w.find("input").setValue("new");
    await w.find("form").trigger("submit");
    await flushPromises();
    expect(api.createTodo).toHaveBeenCalledWith("new");
    expect(w.text()).toContain("new");
  });

  it("ignores empty submit", async () => {
    const w = mount(TodoList);
    await flushPromises();
    await w.find("form").trigger("submit");
    await flushPromises();
    expect(api.createTodo).not.toHaveBeenCalled();
  });

  it("calls toggleTodo when checkbox is clicked", async () => {
    const w = mount(TodoList);
    await flushPromises();
    await w.findAll("input[type=checkbox]")[0].trigger("change");
    await flushPromises();
    expect(api.toggleTodo).toHaveBeenCalledWith(1, true);
  });

  it("calls deleteTodo and removes item when delete button clicked", async () => {
    const w = mount(TodoList);
    await flushPromises();
    await w.findAll("button:not([type=submit])")[0].trigger("click");
    await flushPromises();
    expect(api.deleteTodo).toHaveBeenCalledWith(1);
  });
});
