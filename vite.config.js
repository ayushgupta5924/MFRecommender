import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // In production Vercel forwards /api to the backend (see vercel.json); do the same locally.
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
