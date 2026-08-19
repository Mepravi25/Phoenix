import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // react-router-dom is currently resolved from the workspace-level
  // node_modules folder. Force every import to use this frontend's React copy,
  // otherwise BrowserRouter receives a different hook dispatcher.
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
})
