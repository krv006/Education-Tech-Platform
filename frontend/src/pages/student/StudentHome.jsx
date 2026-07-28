import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import api, { errMessage } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import SectionNav, { useSectionTab } from '../../components/SectionNav'
import { fetchAll, fmtLongDate, fmtTime, fmtWhen, greeting, LESSON_STATUS, sameDay } from '../../lib/ui'

const FILTERS = [
  { key: 'today', label: 'Bugun' },
  { key: 'upcoming', label: 'Kelgusi' },
  { key: 'past', label: "O'tgan" },
  { key: 'all', label: 'Hammasi' },
]

export default function StudentHome() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useSectionTab('home')
  const [lessons, setLessons] = useState([])
  const [links, setLinks] = useState([])
  const [catalog, setCatalog] = useState([])
  const [enrolledCourses, setEnrolledCourses] = useState([])
  const [attendance, setAttendance] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [filter, setFilter] = useState('today')
  const [copied, setCopied] = useState(false)
  const [enrolling, setEnrolling] = useState('')

  async function load() {
    try {
      const [l, k, cat, mine, att] = await Promise.all([
        fetchAll('/lessons/'),
        fetchAll('/auth/links/'),
        fetchAll('/courses/catalog/'),
        fetchAll('/courses/'),
        fetchAll('/attendance/'),
      ])
      setLessons(l)
      setLinks(k)
      setCatalog(cat)
      setEnrolledCourses(mine)
      setAttendance(att)
    } catch (err) {
      setError(errMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function respond(linkId, action) {
    try {
      await api.post(`/auth/links/${linkId}/respond/`, { action })
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  async function enroll(courseId, title) {
    setError(''); setNotice('')
    setEnrolling(courseId)
    try {
      await api.post(`/courses/${courseId}/enroll/`)
      setNotice(`«${title}» kursiga so'rov yuborildi — o'qituvchi tasdiqlagach darslar ochiladi.`)
      load()
    } catch (err) {
      setError(errMessage(err))
    } finally {
      setEnrolling('')
    }
  }

  async function unenroll(courseId, title) {
    if (!window.confirm(`«${title}» kursidan chiqmoqchimisiz? Darslari jadvalingizdan yo'qoladi.`)) return
    setError(''); setNotice('')
    try {
      await api.post(`/courses/${courseId}/unenroll/`)
      setNotice(`«${title}» kursidan chiqdingiz.`)
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  function copyCode() {
    navigator.clipboard?.writeText(user.invite_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const now = new Date()
  const pending = links.filter((l) => l.status === 'pending')
  const approved = links.filter((l) => l.status === 'approved')
  const liveLessons = lessons.filter((l) => l.status === 'live')
  const todayLessons = lessons.filter((l) => sameDay(new Date(l.starts_at), now))
  const upcoming = lessons
    .filter((l) => l.status === 'scheduled' && new Date(l.starts_at) >= now)
    .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at))
  const totalMinutes = attendance.reduce((s, a) => s + (a.minutes || 0), 0)
  const enrolledIds = new Set(enrolledCourses.map((c) => c.id))
  const openCourses = catalog.filter((c) => !enrolledIds.has(c.id))

  const filtered = useMemo(() => {
    let list
    if (filter === 'today') list = todayLessons
    else if (filter === 'upcoming') list = lessons.filter((l) => ['scheduled', 'live'].includes(l.status) && new Date(l.starts_at) >= now)
    else if (filter === 'past') list = lessons.filter((l) => l.status === 'finished' || new Date(l.starts_at) < now)
    else list = lessons
    const dir = filter === 'past' ? -1 : 1
    return [...list].sort((a, b) => dir * (new Date(a.starts_at) - new Date(b.starts_at)))
  }, [lessons, filter]) // eslint-disable-line react-hooks/exhaustive-deps

  const filterCounts = {
    today: todayLessons.length,
    upcoming: lessons.filter((l) => ['scheduled', 'live'].includes(l.status) && new Date(l.starts_at) >= now).length,
    past: lessons.filter((l) => l.status === 'finished' || new Date(l.starts_at) < now).length,
    all: lessons.length,
  }

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="page-head">
        <div className="hello">
          <h2>{greeting()}, {user.first_name || user.username}! 👋</h2>
          <div className="sub">
            {fmtLongDate(now)}
            {upcoming[0] && <> · Keyingi dars: <b>{upcoming[0].title}</b> — {fmtWhen(upcoming[0].starts_at).rel}</>}
          </div>
        </div>
        <button className="btn secondary sm" onClick={copyCode} title="Nusxalash uchun bosing">
          {copied ? '✓ Nusxalandi' : `Taklif kodim: ${user.invite_code}`}
        </button>
      </div>

      <SectionNav
        tabs={[
          { key: 'home', label: 'Asosiy', icon: '🏠', count: pending.length },
          { key: 'lessons', label: 'Darslar', icon: '🗓️' },
          { key: 'courses', label: 'Kurslar', icon: '📚' },
        ]}
        current={tab}
        onChange={setTab}
      />

      {error && <div className="error-box">{error}</div>}
      {notice && <div className="success-box">{notice}</div>}

      {liveLessons.map((l) => (
        <div className="live-banner" key={l.id}>
          <span className="pulse" />
          <div>
            <div className="title">{l.title} — hozir jonli efirda</div>
            <div className="meta">{l.course_title} · {fmtWhen(l.starts_at).rel} {fmtWhen(l.starts_at).abs}</div>
          </div>
          <div className="spacer" />
          <button className="btn" onClick={() => navigate(`/lessons/${l.id}/room`)}>Darsga kirish →</button>
        </div>
      ))}

      {/* ═══ Asosiy ═══ */}
      {tab === 'home' && (
        <>
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

          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-icon indigo">📚</div>
              <div>
                <div className="num">{enrolledCourses.length}</div>
                <div className="lbl">Kurslarim</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon amber">🗓️</div>
              <div>
                <div className="num">{todayLessons.length}</div>
                <div className="lbl">Bugungi darslar</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon red">📡</div>
              <div>
                <div className="num">{liveLessons.length}</div>
                <div className="lbl">Jonli efirda</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon green">⏱️</div>
              <div>
                <div className="num">{totalMinutes}</div>
                <div className="lbl">Darsda o'tkazilgan daqiqa</div>
              </div>
            </div>
          </div>

          <section>
            <div className="section-head">
              <h3>Bugungi darslar <span className="count">({todayLessons.length})</span></h3>
              <button className="btn secondary sm" onClick={() => setTab('lessons')}>Barcha darslar →</button>
            </div>
            <div className="card">
              {todayLessons.length === 0 && (
                <div className="empty-state">
                  <div className="ico">🗓️</div>
                  <p>Bugunga dars yo'q — dam oling!</p>
                </div>
              )}
              {[...todayLessons]
                .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at))
                .map((l) => {
                  const meta = LESSON_STATUS[l.status] || { label: l.status, badge: 'indigo', dot: 'indigo' }
                  return (
                    <div className="lesson-line today-row" key={l.id}>
                      <div className="info">
                        <div className="name">{l.title}</div>
                        <div className="meta">{l.course_title} · {fmtWhen(l.starts_at).rel} · {l.duration_min} daq</div>
                      </div>
                      <span className={`badge ${meta.badge}`}><span className={`dot ${meta.dot}`} />{meta.label}</span>
                      {['scheduled', 'live'].includes(l.status) && (
                        <button className="btn sm" onClick={() => navigate(`/lessons/${l.id}/room`)}>
                          Darsga kirish
                        </button>
                      )}
                    </div>
                  )
                })}
            </div>
          </section>

          {approved.length > 0 && (
            <section>
              <div className="section-head">
                <h3>Meni kuzatayotganlar <span className="count">({approved.length})</span></h3>
              </div>
              <div className="card">
                {approved.map((link) => (
                  <div key={link.id} className="row" style={{ padding: '8px 0' }}>
                    <span style={{ fontSize: 18 }}>👤</span>
                    <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600 }}>
                      {link.parent.first_name || link.parent.username}
                    </span>
                    <button className="btn secondary sm" onClick={() => respond(link.id, 'decline')}>
                      Kuzatuvni uzish
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* ═══ Darslar ═══ */}
      {tab === 'lessons' && (
        <>
          <section>
            <div className="section-head">
              <h3>Darslar jadvali</h3>
              <div className="chip-row">
                {FILTERS.map((f) => (
                  <button key={f.key} className={`chip ${filter === f.key ? 'active' : ''}`}
                    onClick={() => setFilter(f.key)}>
                    {f.label}<span className="n">{filterCounts[f.key]}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="card" style={{ padding: '6px 16px' }}>
              {!loading && lessons.length === 0 && (
                <div className="empty-state">
                  <div className="ico">📚</div>
                  <p>Hali kursga yozilmagansiz.</p>
                  <p className="hint">Kursga yozilishni ota-onangiz yoki o'qituvchingiz amalga oshiradi.</p>
                </div>
              )}
              {lessons.length > 0 && filtered.length === 0 && (
                <div className="empty-state">
                  <div className="ico">🗓️</div>
                  <p>{filter === 'today' ? 'Bugunga dars yo\'q — dam oling!' : "Bu bo'limda dars yo'q."}</p>
                </div>
              )}
              {filtered.length > 0 && (
                <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>Mavzu</th><th>Kurs</th><th>Vaqt</th><th>Davomiyligi</th><th>Holat</th><th /></tr>
                  </thead>
                  <tbody>
                    {filtered.map((l) => {
                      const meta = LESSON_STATUS[l.status] || { label: l.status, badge: 'indigo', dot: 'indigo' }
                      const when = fmtWhen(l.starts_at)
                      return (
                        <tr key={l.id} className={sameDay(new Date(l.starts_at), new Date()) ? 'today-row' : ''}>
                          <td style={{ fontWeight: 600 }}>{l.title}</td>
                          <td className="muted">{l.course_title}</td>
                          <td className="when">
                            <div className="rel">{when.rel}</div>
                            {when.abs && <div className="abs">{when.abs}</div>}
                          </td>
                          <td className="muted">{l.duration_min} daq</td>
                          <td><span className={`badge ${meta.badge}`}><span className={`dot ${meta.dot}`} />{meta.label}</span></td>
                          <td>
                            {['scheduled', 'live'].includes(l.status) && (
                              <div className="row" style={{ justifyContent: 'flex-end' }}>
                                <button className="btn sm" onClick={() => navigate(`/lessons/${l.id}/room`)}>
                                  Darsga kirish
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                </div>
              )}
            </div>
          </section>

          {attendance.length > 0 && (
            <section>
              <div className="section-head">
                <h3>Mening davomatim</h3>
                <span className="count">{attendance.length} dars · {totalMinutes} daqiqa</span>
              </div>
              <div className="card" style={{ padding: '6px 16px' }}>
                <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>Dars</th><th>Kirdim</th><th>Chiqdim</th><th>Davomiyligi</th></tr>
                  </thead>
                  <tbody>
                    {[...attendance]
                      .sort((a, b) => new Date(b.joined_at || 0) - new Date(a.joined_at || 0))
                      .map((a) => {
                        const joined = a.joined_at ? fmtWhen(a.joined_at) : null
                        return (
                          <tr key={a.id}>
                            <td style={{ fontWeight: 600 }}>{a.lesson_title}</td>
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
              </div>
            </section>
          )}
        </>
      )}

      {/* ═══ Kurslar ═══ */}
      {tab === 'courses' && (
        <>
          {enrolledCourses.length > 0 && (
            <section>
              <div className="section-head">
                <h3>Kurslarim <span className="count">({enrolledCourses.length})</span></h3>
              </div>
              <div className="course-grid">
                {enrolledCourses.map((c) => {
                  const courseLessons = lessons.filter((l) => l.course === c.id)
                  return (
                    <div className="course-card" key={c.id}>
                      {c.subject && <span className="subject">{c.subject}</span>}
                      <h4>{c.title}</h4>
                      <div className="meta">
                        <span>👩‍🏫 {c.teacher?.first_name || c.teacher?.username}</span>
                        <span>🗓️ {courseLessons.length} dars</span>
                      </div>
                      <button className="btn secondary sm" onClick={() => unenroll(c.id, c.title)}>
                        Kursdan chiqish
                      </button>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          <section>
            <div className="section-head">
              <h3>Kurslar katalogi <span className="count">({openCourses.length} ta ochiq kurs)</span></h3>
            </div>
            {!loading && openCourses.length === 0 && (
              <div className="card empty-state">
                <div className="ico">🎓</div>
                <p>Barcha mavjud kurslarga yozilgansiz!</p>
              </div>
            )}
            <div className="course-grid">
              {openCourses.map((c) => (
                <div className="course-card" key={c.id}>
                  {c.subject && <span className="subject">{c.subject}</span>}
                  <h4>{c.title}</h4>
                  <div className="meta">
                    <span>👩‍🏫 {c.teacher?.first_name || c.teacher?.username}</span>
                    <span>👥 {c.student_count} o'quvchi</span>
                  </div>
                  {c.my_status === 'pending' ? (
                    <span className="badge amber" style={{ alignSelf: 'flex-start' }}>
                      ⏳ So'rov yuborilgan — tasdiq kutilmoqda
                    </span>
                  ) : (
                    <button className="btn sm" disabled={enrolling === c.id}
                      onClick={() => enroll(c.id, c.title)}>
                      {enrolling === c.id ? 'Yuborilmoqda…'
                        : c.my_status === 'declined' ? "Qayta so'rov yuborish" : 'Kursga yozilish'}
                    </button>
                  )}
                  {c.my_status === 'declined' && (
                    <span className="muted" style={{ fontSize: 12 }}>Avvalgi so'rov rad etilgan.</span>
                  )}
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
