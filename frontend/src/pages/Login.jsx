import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { errMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err) {
      setError(errMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="auth-logo">🎯</div>
        <h1>Fokus</h1>
        <p className="auth-sub">Onlayn ta'lim platformasiga kirish</p>
        {error && <div className="error-box">{error}</div>}
        <div className="field">
          <label>Login</label>
          <input
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="field">
          <label>Parol</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <button className="btn" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Kirilmoqda…' : 'Kirish'}
        </button>
        <p className="auth-foot">
          Hisobingiz yo'qmi? <Link to="/register">Ro'yxatdan o'tish</Link>
        </p>
      </form>
    </div>
  )
}
