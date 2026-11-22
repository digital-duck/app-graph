<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getTodos, createTodo, toggleTodo, deleteTodo, type Todo } from '../api'
import TodoItem from './TodoItem.vue'

const todos = ref<Todo[]>([])
const newTitle = ref('')

onMounted(async () => {
  todos.value = await getTodos()
})

async function handleSubmit() {
  if (!newTitle.value.trim()) return
  const todo = await createTodo(newTitle.value.trim())
  todos.value.push(todo)
  newTitle.value = ''
}

async function handleToggle(id: number) {
  const todo = todos.value.find(t => t.id === id)
  if (!todo) return
  const updated = await toggleTodo(id, !todo.completed)
  const index = todos.value.findIndex(t => t.id === id)
  todos.value[index] = updated
}

async function handleDelete(id: number) {
  await deleteTodo(id)
  todos.value = todos.value.filter(t => t.id !== id)
}
</script>

<template>
  <div class="todo-dashboard">
    <form @submit.prevent="handleSubmit" class="todo-form">
      <input v-model="newTitle" placeholder="New todo..." />
      <button type="submit">Add</button>
    </form>

    <p v-if="todos.length === 0" class="empty-state">No todos yet.</p>

    <div v-else class="todo-list">
      <TodoItem
        v-for="todo in todos"
        :key="todo.id"
        :todo="todo"
        @toggle="handleToggle"
        @delete="handleDelete"
      />
    </div>
  </div>
</template>

<style scoped>
.todo-dashboard {
  max-width: 480px;
  margin: 0 auto;
}

.todo-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.todo-form input {
  flex: 1;
}

.empty-state {
  color: #888;
  text-align: center;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>