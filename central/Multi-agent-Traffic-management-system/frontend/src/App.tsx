import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { ACCESS_TOKEN_KEY } from './api'
import Dashboard from './Dashboard'
import Login from './Login'
import Register from './Register'
import './App.css'

function ProtectedDashboard() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) ? <Dashboard /> : <Navigate replace to="/login" />
}

/** Application routes keep authentication boundaries out of presentation components. */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<ProtectedDashboard />} />
        <Route path="*" element={<Navigate replace to="/dashboard" />} />
      </Routes>
    </BrowserRouter>
  )
}
