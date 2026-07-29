import { Link, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

const ROLE_LABELS = {
  teacher: "O'qituvchi",
  student: "O'quvchi",
  parent: 'Ota-ona',
  admin: 'Admin',
  super_admin: 'Super Admin',
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <>
      <header className="app-header">
        <Link to="/" className="logo">
          <span>🎯</span>Fokus
        </Link>
        {(user.role === 'teacher' || user.role === 'student') && (
          <>
            <Link to="/" className="nav-link">💬 Chatlar</Link>
            <Link to="/panel" className="nav-link">📊 Panel</Link>
          </>
        )}
        <div className="spacer" />
        <span className="badge indigo">{ROLE_LABELS[user.role] || user.role}</span>
        <span className="user-name" style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink-soft)' }}>
          {user.first_name || user.username}
        </span>
        <button
          className="btn secondary sm"
          onClick={() => {
            logout()
            navigate('/login')
          }}
        >
          Chiqish
        </button>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </>
  )
}
