import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CssBaseline, ThemeProvider } from '@mui/material'
import './index.css'
import App from './App.tsx'
import tacticalTheme from './theme.ts'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={tacticalTheme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </StrictMode>,
)
