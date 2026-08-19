import { useState, type FormEvent } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { Alert, Box, Button, Link, Paper, TextField, Typography } from '@mui/material'
import axios from 'axios'

import api, { ACCESS_TOKEN_KEY, type TokenResponse } from './api'

interface ValidationIssue {
  loc?: Array<string | number>
  msg?: string
}

function requestErrorMessage(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string | ValidationIssue[] }>(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((issue) => `${issue.loc?.at(-1) ?? 'Input'}: ${issue.msg ?? 'is invalid'}`)
        .join(' ')
    }
  }
  return 'Unable to create the account. Please try again.'
}

/** Registration panel. The backend assigns the safe default ev_driver role. */
export default function Register() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const submitRegistration = async (event: FormEvent<HTMLFormElement>) => {
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
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      const response = await api.post<TokenResponse>('/register', { username, password })
      localStorage.setItem(ACCESS_TOKEN_KEY, response.data.access_token)
      navigate('/dashboard', { replace: true })
    } catch (requestError) {
      setError(requestErrorMessage(requestError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Box className="auth-page">
      <Paper className="auth-card" elevation={8}>
        <Typography component="h1" variant="h4" sx={{ fontWeight: 800 }} gutterBottom>
          Create driver account
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          Register to access authenticated priority routing.
        </Typography>

        <Box component="form" onSubmit={submitRegistration} noValidate>
          <TextField
            autoComplete="username"
            autoFocus
            fullWidth
            helperText="3–50 characters"
            label="Username"
            margin="normal"
            onChange={(event) => setUsername(event.target.value)}
            required
            value={username}
          />
          <TextField
            autoComplete="new-password"
            fullWidth
            helperText="At least 8 characters"
            label="Password"
            margin="normal"
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          <TextField
            autoComplete="new-password"
            fullWidth
            label="Confirm password"
            margin="normal"
            onChange={(event) => setConfirmPassword(event.target.value)}
            required
            type="password"
            value={confirmPassword}
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
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </Button>
        </Box>

        <Typography align="center" color="text.secondary" sx={{ mt: 3 }} variant="body2">
          Already registered?{' '}
          <Link component={RouterLink} to="/login" underline="hover">
            Sign in
          </Link>
        </Typography>
      </Paper>
    </Box>
  )
}
