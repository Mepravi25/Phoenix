import { createTheme } from '@mui/material/styles'

/** Shared tactical command theme for the orchestrator and driver surfaces. */
const tacticalTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#00E5FF', contrastText: '#06131B' },
    secondary: { main: '#A78BFA' },
    success: { main: '#2ECC71' },
    warning: { main: '#F39C12' },
    error: { main: '#E74C3C' },
    background: { default: '#0F172A', paper: '#1E293B' },
    divider: '#334155',
    text: { primary: '#F8FAFC', secondary: '#94A3B8' },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: 'Inter, Roboto, Helvetica, Arial, sans-serif',
    button: { fontWeight: 800, letterSpacing: '0.04em' },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: '#0F172A', color: '#F8FAFC' },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: '1px solid #334155',
          boxShadow: 'none',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 8 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottom: '1px solid #334155' },
        head: { backgroundColor: '#172235', color: '#CBD5E1', fontWeight: 800 },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        notchedOutline: { borderColor: '#475569' },
      },
    },
  },
})

export default tacticalTheme
