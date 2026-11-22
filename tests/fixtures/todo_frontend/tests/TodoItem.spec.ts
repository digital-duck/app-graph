// Node verification: todo_item_component
// Edge verification: emitted event payloads match what TodoList forwards to api_client
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import TodoItem from "../src/components/TodoItem.vue";

const todo = { id: 1, title: "buy milk", completed: false };
const completedTodo = { id: 2, title: "done", completed: true };

describe("TodoItem", () => {
  it("renders title", () => {
    const w = mount(TodoItem, { props: { todo } });
    expect(w.text()).toContain("buy milk");
  });

  it("checkbox reflects completed=false", () => {
    const w = mount(TodoItem, { props: { todo } });
    expect((w.find("input").element as HTMLInputElement).checked).toBe(false);
  });

  it("checkbox reflects completed=true", () => {
    const w = mount(TodoItem, { props: { todo: completedTodo } });
    expect((w.find("input").element as HTMLInputElement).checked).toBe(true);
  });

  it("emits toggle with correct id on checkbox change", async () => {
    const w = mount(TodoItem, { props: { todo } });
    await w.find("input").trigger("change");
    expect(w.emitted("toggle")).toEqual([[1]]);
  });

  it("emits delete with correct id on button click", async () => {
    const w = mount(TodoItem, { props: { todo } });
    await w.find("button").trigger("click");
    expect(w.emitted("delete")).toEqual([[1]]);
  });

  it("applies completed class when completed=true", () => {
    const w = mount(TodoItem, { props: { todo: completedTodo } });
    expect(w.find("span").classes()).toContain("completed");
  });

  it("does not apply completed class when completed=false", () => {
    const w = mount(TodoItem, { props: { todo } });
    expect(w.find("span").classes()).not.toContain("completed");
  });
});
