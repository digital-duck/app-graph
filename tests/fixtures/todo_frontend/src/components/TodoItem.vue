<script setup lang="ts">
interface Todo {
  id: number
  title: string
  completed: boolean
}

const props = defineProps<{ todo: Todo }>()
const emit = defineEmits<{
  toggle: [id: number]
  delete: [id: number]
}>()
</script>

<template>
  <div class="todo-item">
    <input
      type="checkbox"
      :checked="props.todo.completed"
      @change="emit('toggle', props.todo.id)"
    />
    <span :class="{ completed: props.todo.completed }">{{ props.todo.title }}</span>
    <button @click="emit('delete', props.todo.id)">Delete</button>
  </div>
</template>

<style scoped>
.todo-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.completed {
  text-decoration: line-through;
  opacity: 0.6;
}
</style>