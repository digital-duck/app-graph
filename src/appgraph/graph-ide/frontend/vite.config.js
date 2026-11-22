import { defineConfig } from 'vite'

const API_PORT = process.env.API_PORT || '8880'
const DEV_PORT = parseInt(process.env.DEV_PORT || '8881', 10)

export default defineConfig({
  server: {
    port: DEV_PORT,
    proxy: {
      '/api': `http://localhost:${API_PORT}`,
    },
  },
})
