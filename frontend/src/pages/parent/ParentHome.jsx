import { useEffect, useState } from 'react'

import api, { errMessage } from '../../api/client'

export default function ParentHome() {
  const [links, setLinks] = useState([])
  const [attendance, setAttendance] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [childForm, setChildForm] = useState({ username: '', first_name: '', password: '' })

  async function load() {
    try {
      const [k, a] = await Promise.all([api.get('/auth/links/'), api.get('/attendance/')])
      setLinks(k.data.results)
      setAttendance(a.data.results)
    } catch (err) { setError(errMessage(err)) }
  }

  useEffect(() => { load() }, [])

  async function requestLink(e) {
    e.preventDefault()
    setError(''); setNotice('')
    try {
      await api.post('/auth/links/request/', { invite_code: inviteCode })
      setNotice("So'rov yuborildi — o'quvchi tasdig'i kutilmoqda.")
      setInviteCode('')
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  async function createChild(e) {
    e.preventDefault()
    setError(''); setNotice('')
    try {
      const { data } = await api.post('/auth/children/', childForm)
      setNotice(`Bola hisobi yaratildi. Taklif kodi: ${data.invite_code}`)
      setChildForm({ username: '', first_name: '', password: '' })
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  const STATUS = {
    pending: ['Kutilmoqda', 'amber'],
    approved: ['Tasdiqlangan', 'green'],
    declined: ['Rad etilgan', 'red'],
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>Ota-ona paneli</h2>
      </div>
      {error && <div className="error-box">{error}</div>}
      {notice && (
        <div className="error-box" style={{ background: 'var(--green-bg)', color: 'var(--green-d)' }}>
          {notice}
        </div>
      )}

      <div className="grid-2">
        <form className="card" onSubmit={createChild}>
          <h3 style={{ marginBottom: 6, fontSize: 15 }}>Bola hisobini ochish</h3>
          <p className="muted" style={{ fontSize: 12.5, marginBottom: 12 }}>
            Siz ochgan hisob avtomatik sizga bog'lanadi.
          </p>
          <div className="field">
            <label>Ismi</label>
            <input className="input" value={childForm.first_name}
              onChange={(e) => setChildForm({ ...childForm, first_name: e.target.value })} />
          </div>
          <div className="field">
            <label>Login</label>
            <input className="input" value={childForm.username}
              onChange={(e) => setChildForm({ ...childForm, username: e.target.value })} required />
          </div>
          <div className="field">
            <label>Parol</label>
            <input className="input" type="password" value={childForm.password}
              onChange={(e) => setChildForm({ ...childForm, password: e.target.value })}
              autoComplete="new-password" required />
          </div>
          <button className="btn sm">Yaratish</button>
        </form>

        <form className="card" onSubmit={requestLink}>
          <h3 style={{ marginBottom: 6, fontSize: 15 }}>O'quvchini ulash</h3>
          <p className="muted" style={{ fontSize: 12.5, marginBottom: 12 }}>
            O'quvchidan taklif kodini oling — kuzatuv faqat uning tasdig'i bilan ochiladi.
          </p>
          <div className="field">
            <label>Taklif kodi</label>
            <input className="input" value={inviteCode} placeholder="FK-XXXX"
              onChange={(e) => setInviteCode(e.target.value.toUpperCase())} required />
          </div>
          <button className="btn sm">So'rov yuborish</button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 12, fontSize: 15 }}>Farzandlarim</h3>
        {links.length === 0 && <p className="muted" style={{ fontSize: 13 }}>Hali bog'lanish yo'q.</p>}
        {links.map((link) => {
          const [label, color] = STATUS[link.status] || [link.status, 'indigo']
          return (
            <div key={link.id} className="row" style={{ padding: '8px 0' }}>
              <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600 }}>
                {link.student.first_name || link.student.username}
              </span>
              <span className={`badge ${color}`}>{label}</span>
            </div>
          )
        })}
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 12, fontSize: 15 }}>Davomat</h3>
        {attendance.length === 0 && (
          <p className="muted" style={{ fontSize: 13 }}>
            Hali davomat yo'q — bola darsga kirganda avtomatik yoziladi.
          </p>
        )}
        {attendance.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>O'quvchi</th><th>Dars</th><th>Kirdi</th><th>Chiqdi</th><th>Daqiqa</th></tr>
            </thead>
            <tbody>
              {attendance.map((a) => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600 }}>{a.student.first_name || a.student.username}</td>
                  <td className="muted">{a.lesson_title}</td>
                  <td className="muted">{a.joined_at ? new Date(a.joined_at).toLocaleString('uz') : '—'}</td>
                  <td className="muted">{a.left_at ? new Date(a.left_at).toLocaleTimeString('uz') : '—'}</td>
                  <td>{a.minutes ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
