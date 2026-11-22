# Todo Frontend

A Vue 3 single-page application for managing todo items. It communicates with a REST backend to create, list, update, and delete todos, presenting them through a reactive component tree built entirely with the Composition API and local state.

## Prerequisites

- Node.js 18 or later
- Install dependencies:

```bash
npm install
```

## Running the dev server

```bash
npm run dev
```

The app runs at `http://localhost:5173` and expects the backend API at `http://localhost:8000`.

## Running tests

```bash
npm test
```

## Components

- **App** — mounts the root dashboard; no local state
- **TodoList** — receives an array of todo items as props and forwards item-level events up
- **TodoItem** — purely presentational card for a single todo; emits toggle and delete events