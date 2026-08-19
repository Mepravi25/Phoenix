import { useState, type FormEvent } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { Alert, Box, Button, Link, Paper, TextField, Typography } from '@mui/material'
import axios from 'axios'

import api, { ACCESS_TOKEN_KEY, type TokenResponse } from './api'

interface ValidationIssue {
  loc?: Array<string | number>
  msg?: string
}

function requestErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<{ detail?: string | ValidationIssue[] }>(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((issue) => `${issue.loc?.at(-1) ?? 'Input'}: ${issue.msg ?? 'is invalid'}`)
        .join(' ')
    }
  }
  return fallback
}

/** Shared sign-in panel for registered EV drivers and administrators. */
export default function Login() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submitLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    if (username.trim().length < 3) {
      setError('Username must contain at least 3 characters.')
      return
    }
    if (password.length < 8) {
      setError('Password must contain at least 8 characters.')
      return
    }
    setIsSubmitting(true)
    try {
      const response = await api.post<TokenResponse>('/login', { username, password })
      localStorage.setItem(ACCESS_TOKEN_KEY, response.data.access_token)
      navigate('/dashboard', { replace: true })
    } catch (requestError) {
      setError(requestErrorMessage(requestError, 'Unable to sign in. Please try again.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Box className="auth-page">
      <Paper className="auth-card" elevation={8}>
        <Typography component="h1" variant="h4" sx={{ fontWeight: 800 }} gutterBottom>
          Traffic Command
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Sign in with your driver or administrator credentials.
        </Typography>

        <Box component="form" onSubmit={submitLogin} noValidate>
          <TextField
            autoComplete="username"
            autoFocus
            fullWidth
            label="Username"
            margin="normal"
            onChange={(event) => setUsername(event.target.value)}
            required
            value={username}
          />
          <TextField
            autoComplete="current-password"
            fullWidth
            label="Password"
            margin="normal"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
          <Button
            disabled={isSubmitting}
            fullWidth
            size="large"
            sx={{ mt: 3 }}
            type="submit"
            variant="contained"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </Box>

        <Typography align="center" color="text.secondary" sx={{ mt: 3 }} variant="body2">
          Need an EV-driver account?{' '}
          <Link component={RouterLink} to="/register" underline="hover">
            Create an account
          </Link>
        </Typography>
      </Paper>
    </Box>
  )
}
