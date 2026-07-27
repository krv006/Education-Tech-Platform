import { useEffect, useMemo, useState } from 'react'

import api, { errMessage } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import SectionNav, { useSectionTab } from '../../components/SectionNav'
import { fetchAll, fmtLongDate, fmtTime, fmtWhen, greeting } from '../../lib/ui'

const LINK_STATUS = {
  pending: { label: 'Kutilmoqda', badge: 'amber' },
  approved: { label: 'Tasdiqlangan', badge: 'green' },
  declined: { label: 'Rad etilgan', badge: 'red' },
}

export default function ParentHome() {
  const { user } = useAuth()
  const [tab, setTab] = useSectionTab('home')
  const [links, setLinks] = useState([])
  const [attendance, setAttendance] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [openForm, setOpenForm] = useState('') // '' | 'child' | 'link'
  const [childFilter, setChildFilter] = useState('all')
  const [inviteCode, setInviteCode] = useState('')
  const [childForm, setChildForm] = useState({ username: '', first_name: '', password: '' })

  async function load() {
    try {
      const [k, a] = await Promise.all([fetchAll('/auth/links/'), fetchAll('/attendance/')])
      setLinks(k)
      setAttendance(a)
    } catch (err) {
      setError(errMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function requestLink(e) {
    e.preventDefault()
    setError(''); setNotice('')
    try {
      await api.post('/auth/links/request/', { invite_code: inviteCode })
      setNotice("So'rov yuborildi — o'quvchi tasdig'i kutilmoqda.")
      setInviteCode('')
      setOpenForm('')
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
      setOpenForm('')
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  const approved = links.filter((l) => l.status === 'approved')
  const pending = links.filter((l) => l.status === 'pending')
  const totalMinutes = attendance.reduce((s, a) => s + (a.minutes || 0), 0)

  const perChild = useMemo(() => {
    const map = {}
    for (const a of attendance) {
      const id = a.student.id
      if (!map[id]) map[id] = { lessons: 0, minutes: 0 }
      map[id].lessons += 1
      map[id].minutes += a.minutes || 0
    }
    return map
  }, [attendance])

  const filteredAttendance = useMemo(() => {
    const list = childFilter === 'all' ? attendance : attendance.filter((a) => a.student.id === childFilter)
    return [...list].sort((a, b) => new Date(b.joined_at || 0) - new Date(a.joined_at || 0))
  }, [attendance, childFilter])

  const recentAttendance = useMemo(
    () => [...attendance].sort((a, b) => new Date(b.joined_at || 0) - new Date(a.joined_at || 0)).slice(0, 5),
    [attendance],
  )

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="page-head">
        <div className="hello">
          <h2>{greeting()}, {user.first_name || user.username}! 👋</h2>
          <div className="sub">
            {fmtLongDate(new Date())} · {approved.length} farzand kuzatuvda
          </div>
        </div>
      </div>

      <SectionNav
        tabs={[
          { key: 'home', label: 'Asosiy', icon: '🏠' },
          { key: 'children', label: 'Farzandlar', icon: '👨‍👩‍👧', count: pending.length },
          { key: 'attendance', label: 'Davomat', icon: '📊' },
        ]}
        current={tab}
        onChange={setTab}
      />

      {error && <div className="error-box">{error}</div>}
      {notice && <div className="success-box">{notice}</div>}

      {/* ═══ Asosiy ═══ */}
      {tab === 'home' && (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-icon indigo">👨‍👩‍👧</div>
              <div>
                <div className="num">{approved.length}</div>
                <div className="lbl">Farzandlar</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon amber">⏳</div>
              <div>
                <div className="num">{pending.length}</div>
                <div className="lbl">Kutilayotgan so'rov</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon green">✅</div>
              <div>
                <div className="num">{attendance.length}</div>
                <div className="lbl">Qatnashgan darslar</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon red">⏱️</div>
              <div>
                <div className="num">{totalMinutes}</div>
                <div className="lbl">Jami daqiqa</div>
              </div>
            </div>
          </div>

          <section>
            <div className="section-head">
              <h3>So'nggi davomat</h3>
              <button className="btn secondary sm" onClick={() => setTab('attendance')}>Barcha davomat →</button>
            </div>
            <div className="card">
              {recentAttendance.length === 0 && (
                <div className="empty-state">
                  <div className="ico">📊</div>
                  <p>Hali davomat yo'q.</p>
                  <p className="hint">Farzandingiz darsga kirganda bu yerda avtomatik ko'rinadi.</p>
                </div>
              )}
              {recentAttendance.map((a) => (
                <div className="lesson-line" key={a.id}>
                  <div className="info">
                    <div className="name">{a.lesson_title}</div>
                    <div className="meta">
                      👤 {a.student.first_name || a.student.username}
                      {a.joined_at && <> · {fmtWhen(a.joined_at).rel}</>}
                    </div>
                  </div>
                  <span className="badge indigo">{a.minutes != null ? `${a.minutes} daq` : 'darsda'}</span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {/* ═══ Farzandlar ═══ */}
      {tab === 'children' && (
        <section>
          <div className="section-head">
            <h3>Farzandlarim <span className="count">({links.length})</span></h3>
            <div className="row">
              <button className="btn secondary sm" onClick={() => setOpenForm(openForm === 'link' ? '' : 'link')}>
                🔗 O'quvchini ulash
              </button>
              <button className="btn sm" onClick={() => setOpenForm(openForm === 'child' ? '' : 'child')}>
                + Bola hisobi
              </button>
            </div>
          </div>

          {openForm === 'child' && (
            <form className="card form-pop" onSubmit={createChild} style={{ marginBottom: 14 }}>
              <h3>Bola hisobini ochish</h3>
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 12 }}>
                Siz ochgan hisob avtomatik sizga bog'lanadi — tasdiq talab qilinmaydi.
              </p>
              <div className="grid-2">
                <div className="field">
                  <label>Ismi</label>
                  <input className="input" placeholder="Farzandingiz ismi" value={childForm.first_name}
                    onChange={(e) => setChildForm({ ...childForm, first_name: e.target.value })} autoFocus />
                </div>
                <div className="field">
                  <label>Login</label>
                  <input className="input" placeholder="Kirish uchun login" value={childForm.username}
                    onChange={(e) => setChildForm({ ...childForm, username: e.target.value })} required />
                </div>
                <div className="field">
                  <label>Parol</label>
                  <input className="input" type="password" value={childForm.password}
                    onChange={(e) => setChildForm({ ...childForm, password: e.target.value })}
                    autoComplete="new-password" required />
                </div>
              </div>
              <div className="row">
                <button className="btn sm">Yaratish</button>
                <button type="button" className="btn secondary sm" onClick={() => setOpenForm('')}>Bekor qilish</button>
              </div>
            </form>
          )}

          {openForm === 'link' && (
            <form className="card form-pop" onSubmit={requestLink} style={{ marginBottom: 14 }}>
              <h3>Mavjud o'quvchini ulash</h3>
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 12 }}>
                O'quvchidan taklif kodini so'rang — kuzatuv faqat uning roziligi bilan ochiladi.
              </p>
              <div className="field" style={{ maxWidth: 260 }}>
                <label>Taklif kodi</label>
                <input className="input" value={inviteCode} placeholder="FK-XXXX"
                  onChange={(e) => setInviteCode(e.target.value.toUpperCase())} required autoFocus />
              </div>
              <div className="row">
                <button className="btn sm">So'rov yuborish</button>
                <button type="button" className="btn secondary sm" onClick={() => setOpenForm('')}>Bekor qilish</button>
              </div>
            </form>
          )}

          {!loading && links.length === 0 && (
            <div className="card empty-state">
              <div className="ico">👨‍👩‍👧</div>
              <p>Hali farzand ulanmagan.</p>
              <p className="hint">«+ Bola hisobi» orqali yangi hisob oching yoki taklif kodi bilan mavjud o'quvchini ulang.</p>
            </div>
          )}
          <div className="course-grid">
            {links.map((link) => {
              const st = LINK_STATUS[link.status] || { label: link.status, badge: 'indigo' }
              const stats = perChild[link.student.id]
              return (
                <div className="course-card" key={link.id}>
                  <span className={`badge ${st.badge}`} style={{ alignSelf: 'flex-start' }}>{st.label}</span>
                  <h4>{link.student.first_name || link.student.username}</h4>
                  <div className="meta">
                    <span>✅ {stats?.lessons || 0} dars</span>
                    <span>⏱️ {stats?.minutes || 0} daqiqa</span>
                  </div>
                  {link.status === 'approved' && (
                    <div className="next">
                      {stats
                        ? <>So'nggi faollik: <b>{filteredAttendance.find((a) => a.student.id === link.student.id)?.lesson_title || '—'}</b></>
                        : <span className="muted">Hali darsga kirmagan</span>}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* ═══ Davomat ═══ */}
      {tab === 'attendance' && (
        <section>
          <div className="section-head">
            <h3>Davomat tarixi</h3>
            {approved.length > 1 && (
              <div className="chip-row">
                <button className={`chip ${childFilter === 'all' ? 'active' : ''}`} onClick={() => setChildFilter('all')}>
                  Hammasi<span className="n">{attendance.length}</span>
                </button>
                {approved.map((link) => (
                  <button key={link.id} className={`chip ${childFilter === link.student.id ? 'active' : ''}`}
                    onClick={() => setChildFilter(link.student.id)}>
                    {link.student.first_name || link.student.username}
                    <span className="n">{perChild[link.student.id]?.lessons || 0}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="card" style={{ padding: '6px 16px' }}>
            {filteredAttendance.length === 0 && (
              <div className="empty-state">
                <div className="ico">📊</div>
                <p>Hali davomat yo'q.</p>
                <p className="hint">Farzandingiz darsga kirganda bu yerda avtomatik ko'rinadi.</p>
              </div>
            )}
            {filteredAttendance.length > 0 && (
              <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>O'quvchi</th><th>Dars</th><th>Kirdi</th><th>Chiqdi</th><th>Davomiyligi</th></tr>
                </thead>
                <tbody>
                  {filteredAttendance.map((a) => {
                    const joined = a.joined_at ? fmtWhen(a.joined_at) : null
                    return (
                      <tr key={a.id}>
                        <td style={{ fontWeight: 600 }}>{a.student.first_name || a.student.username}</td>
                        <td className="muted">{a.lesson_title}</td>
                        <td className="when">
                          {joined ? <><div className="rel">{joined.rel}</div>{joined.abs && <div className="abs">{joined.abs}</div>}</> : '—'}
                        </td>
                        <td className="muted">{a.left_at ? fmtTime(new Date(a.left_at)) : '—'}</td>
                        <td>{a.minutes != null ? `${a.minutes} daq` : '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  )
}
