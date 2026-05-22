import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendUrl = process.env.VITE_BACKEND_URL || 'http://localhost:8000'
const wsBackendUrl = backendUrl.replace(/^http/i, 'ws')

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': backendUrl,
      '/ws': { target: wsBackendUrl, ws: true },
    },
  },
})
