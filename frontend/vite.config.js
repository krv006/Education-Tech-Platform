import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // dev'da CORS'siz ishlash uchun: /api -> Django
      '/api': 'http://localhost:8000',
    },
  },
})
