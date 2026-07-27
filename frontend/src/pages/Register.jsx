import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { errMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    role: 'parent',
    first_name: '',
    last_name: '',
    username: '',
    phone: '',
    password: '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await register({ ...form, phone: form.phone || undefined })
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
        <h1>Ro'yxatdan o'tish</h1>
        <p className="auth-sub">
          O'quvchi hisobini ota-ona o'z panelidan ochadi
        </p>
        {error && <div className="error-box">{error}</div>}
        <div className="field">
          <label>Kim sifatida?</label>
          <select className="input" value={form.role} onChange={set('role')}>
            <option value="parent">Ota-ona</option>
            <option value="teacher">O'qituvchi</option>
          </select>
        </div>
        <div className="grid-2">
          <div className="field">
            <label>Ism</label>
            <input className="input" value={form.first_name} onChange={set('first_name')} />
          </div>
          <div className="field">
            <label>Familiya</label>
            <input className="input" value={form.last_name} onChange={set('last_name')} />
          </div>
        </div>
        <div className="field">
          <label>Login</label>
          <input className="input" value={form.username} onChange={set('username')} required />
        </div>
        <div className="field">
          <label>Telefon (ixtiyoriy)</label>
          <input className="input" value={form.phone} onChange={set('phone')} placeholder="+9989..." />
        </div>
        <div className="field">
          <label>Parol</label>
          <input
            className="input"
            type="password"
            value={form.password}
            onChange={set('password')}
            autoComplete="new-password"
            required
          />
        </div>
        <button className="btn" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Yaratilmoqda…' : "Ro'yxatdan o'tish"}
        </button>
        <p className="auth-foot">
          Hisobingiz bormi? <Link to="/login">Kirish</Link>
        </p>
      </form>
    </div>
  )
}
