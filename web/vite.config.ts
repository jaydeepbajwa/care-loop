import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// In dev, proxy API calls to the FastAPI server so the browser sees one origin.
// In the docker-compose demo, nginx does the same job.
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
    },
  },
})
