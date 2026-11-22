// api.ts

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export interface Todo {
  id: number;
  title: string;
  completed: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const getTodos = (): Promise<Todo[]> => request("/todos");

export const createTodo = (title: string): Promise<Todo> =>
  request("/todos", { method: "POST", body: JSON.stringify({ title }) });

export const toggleTodo = (id: number, completed: boolean): Promise<Todo> =>
  request(`/todos/${id}`, { method: "PUT", body: JSON.stringify({ completed }) });

export const deleteTodo = (id: number): Promise<void> =>
  request(`/todos/${id}`, { method: "DELETE" });