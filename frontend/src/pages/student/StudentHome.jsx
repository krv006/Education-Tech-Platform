import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import api, { errMessage } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'

export default function StudentHome() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [lessons, setLessons] = useState([])
  const [links, setLinks] = useState([])
  const [error, setError] = useState('')

  async function load() {
    try {
      const [l, k] = await Promise.all([api.get('/lessons/'), api.get('/auth/links/')])
      setLessons(l.data.results)
      setLinks(k.data.results)
    } catch (err) { setError(errMessage(err)) }
  }

  useEffect(() => { load() }, [])

  async function respond(linkId, action) {
    try {
      await api.post(`/auth/links/${linkId}/respond/`, { action })
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  const pending = links.filter((l) => l.status === 'pending')
  const approved = links.filter((l) => l.status === 'approved')

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Darslarim</h2>
        <span className="badge indigo">Taklif kodim: {user.invite_code}</span>
      </div>
      {error && <div className="error-box">{error}</div>}

      {pending.map((link) => (
        <div key={link.id} className="card" style={{ borderColor: 'var(--amber)' }}>
          <div className="row">
            <span style={{ fontSize: 20 }}>📊</span>
            <div style={{ flex: 1 }}>
              <b style={{ fontSize: 14 }}>
                {link.parent.first_name || link.parent.username} tahlilingizni kuzatmoqchi
              </b>
              <p className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>
                Rozi bo'lsangiz, davomat va faolligingizni ko'radi. Istalgan payt uzasiz.
              </p>
            </div>
            <button className="btn secondary sm" onClick={() => respond(link.id, 'decline')}>Rad etish</button>
            <button className="btn sm" onClick={() => respond(link.id, 'approve')}>Tasdiqlash</button>
          </div>
        </div>
      ))}

      <div className="card">
        <h3 style={{ marginBottom: 12, fontSize: 15 }}>Darslar jadvali</h3>
        {lessons.length === 0 && (
          <p className="muted" style={{ fontSize: 13 }}>
            Hali darsga yozilmagansiz — kursga yozilishni ota-onangiz yoki o'qituvchi amalga oshiradi.
          </p>
        )}
        {lessons.map((l) => (
          <div key={l.id} className="row" style={{ padding: '10px 0', borderBottom: '1px solid var(--line)' }}>
            <div style={{ flex: 1 }}>
              <b style={{ fontSize: 14 }}>{l.title}</b>
              <p className="muted" style={{ fontSize: 12.5 }}>
                {l.course_title} · {new Date(l.starts_at).toLocaleString('uz')} · {l.duration_min} daq
              </p>
            </div>
            {l.status === 'live' && <span className="badge red">JONLI</span>}
            {['scheduled', 'live'].includes(l.status) && (
              <button className="btn sm" onClick={() => navigate(`/lessons/${l.id}/room`)}>
                Darsga kirish
              </button>
            )}
          </div>
        ))}
      </div>

      {approved.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: 10, fontSize: 15 }}>Meni kuzatayotganlar</h3>
          {approved.map((link) => (
            <div key={link.id} className="row" style={{ padding: '8px 0' }}>
              <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600 }}>
                {link.parent.first_name || link.parent.username}
              </span>
              <button className="btn secondary sm" onClick={() => respond(link.id, 'decline')}>
                Kuzatuvni uzish
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
