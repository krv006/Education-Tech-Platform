import { Fragment, useEffect, useMemo, useState } from 'react'
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

export default function TeacherHome() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [tab, setTab] = useSectionTab('home')
  const [courses, setCourses] = useState([])
  const [lessons, setLessons] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('today')
  const [courseFilter, setCourseFilter] = useState('')
  const [journalFor, setJournalFor] = useState('') // ochiq jurnal — dars id
  const [journal, setJournal] = useState({}) // dars id -> davomat ro'yxati keshi
  const [manageFor, setManageFor] = useState('') // ochiq o'quvchilar paneli — kurs id
  const [courseStudents, setCourseStudents] = useState({}) // kurs id -> yozilganlar keshi
  const [newStudent, setNewStudent] = useState('')
  const [enrollBusy, setEnrollBusy] = useState(false)
  const [openForm, setOpenForm] = useState('') // '' | 'course' | 'lesson'
  const [courseForm, setCourseForm] = useState({ title: '', subject: '' })
  const [lessonForm, setLessonForm] = useState({ course: '', title: '', starts_at: '', duration_min: 45 })

  const [enrollRequests, setEnrollRequests] = useState([])

  async function load() {
    try {
      const [c, l, r] = await Promise.all([
        fetchAll('/courses/'), fetchAll('/lessons/'), fetchAll('/courses/requests/'),
      ])
      setCourses(c)
      setLessons(l)
      setEnrollRequests(r)
    } catch (err) {
      setError(errMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const now = new Date()
  const liveLessons = lessons.filter((l) => l.status === 'live')
  const todayLessons = lessons.filter((l) => sameDay(new Date(l.starts_at), now))
  const upcoming = lessons
    .filter((l) => l.status === 'scheduled' && new Date(l.starts_at) >= now)
    .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at))
  const totalStudents = courses.reduce((s, c) => s + (c.student_count || 0), 0)

  const nextByCourse = useMemo(() => {
    const map = {}
    for (const l of upcoming) if (!map[l.course]) map[l.course] = l
    return map
  }, [lessons]) // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    let list
    if (filter === 'today') list = todayLessons
    else if (filter === 'upcoming') list = lessons.filter((l) => ['scheduled', 'live'].includes(l.status) && new Date(l.starts_at) >= now)
    else if (filter === 'past') list = lessons.filter((l) => l.status === 'finished' || new Date(l.starts_at) < now)
    else list = lessons
    if (courseFilter) list = list.filter((l) => l.course === courseFilter)
    const dir = filter === 'past' ? -1 : 1
    return [...list].sort((a, b) => dir * (new Date(a.starts_at) - new Date(b.starts_at)))
  }, [lessons, filter, courseFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  async function respondRequest(enrollmentId, action) {
    setError('')
    try {
      await api.post('/courses/requests/respond/', { enrollment_id: enrollmentId, action })
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  async function loadStudents(courseId) {
    try {
      const rows = await fetchAll(`/courses/${courseId}/students/`)
      setCourseStudents((s) => ({ ...s, [courseId]: rows }))
    } catch (err) { setError(errMessage(err)) }
  }

  function toggleManage(courseId) {
    if (manageFor === courseId) { setManageFor(''); return }
    setManageFor(courseId)
    setNewStudent('')
    if (!courseStudents[courseId]) loadStudents(courseId)
  }

  async function addStudent(courseId) {
    if (!newStudent.trim()) return
    setError('')
    setEnrollBusy(true)
    try {
      await api.post(`/courses/${courseId}/enroll/`, { student: newStudent.trim() })
      setNewStudent('')
      await loadStudents(courseId)
      load()
    } catch (err) { setError(errMessage(err)) } finally { setEnrollBusy(false) }
  }

  async function removeStudent(courseId, studentId) {
    setError('')
    try {
      await api.post(`/courses/${courseId}/unenroll/`, { student_id: studentId })
      await loadStudents(courseId)
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  async function toggleJournal(lessonId) {
    if (journalFor === lessonId) { setJournalFor(''); return }
    setJournalFor(lessonId)
    if (!journal[lessonId]) {
      try {
        const rows = await fetchAll(`/attendance/?lesson=${lessonId}`)
        setJournal((j) => ({ ...j, [lessonId]: rows }))
      } catch (err) { setError(errMessage(err)) }
    }
  }

  const filterCounts = {
    today: todayLessons.length,
    upcoming: lessons.filter((l) => ['scheduled', 'live'].includes(l.status) && new Date(l.starts_at) >= now).length,
    past: lessons.filter((l) => l.status === 'finished' || new Date(l.starts_at) < now).length,
    all: lessons.length,
  }

  async function createCourse(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/courses/', courseForm)
      setCourseForm({ title: '', subject: '' })
      setOpenForm('')
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  async function createLesson(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/lessons/', {
        ...lessonForm,
        starts_at: new Date(lessonForm.starts_at).toISOString(),
      })
      setLessonForm({ course: '', title: '', starts_at: '', duration_min: 45 })
      setOpenForm('')
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  async function finishLesson(id) {
    try {
      await api.post(`/lessons/${id}/finish/`)
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  // kurs kartasi bosilganda — jadvalni shu kursga filtrlab, Darslar bo'limiga o'tish
  function filterByCourse(courseId) {
    setCourseFilter(courseId)
    setFilter('all')
    setTab('lessons')
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
      </div>

      <SectionNav
        tabs={[
          { key: 'home', label: 'Asosiy', icon: '🏠', count: enrollRequests.length },
          { key: 'courses', label: 'Kurslar', icon: '📚' },
          { key: 'lessons', label: 'Darslar', icon: '🗓️' },
        ]}
        current={tab}
        onChange={setTab}
      />

      {error && <div className="error-box">{error}</div>}

      {liveLessons.map((l) => (
        <div className="live-banner" key={l.id}>
          <span className="pulse" />
          <div>
            <div className="title">{l.title} — hozir jonli efirda</div>
            <div className="meta">{l.course_title} · {fmtWhen(l.starts_at).rel} {fmtWhen(l.starts_at).abs}</div>
          </div>
          <div className="spacer" />
          <button className="btn" onClick={() => navigate(`/lessons/${l.id}/room`)}>Xonaga kirish →</button>
        </div>
      ))}

      {/* ═══ Asosiy ═══ */}
      {tab === 'home' && (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-icon indigo">📚</div>
              <div>
                <div className="num">{courses.length}</div>
                <div className="lbl">Kurslarim</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon green">👥</div>
              <div>
                <div className="num">{totalStudents}</div>
                <div className="lbl">O'quvchilar</div>
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
          </div>

          {enrollRequests.map((r) => (
            <div key={r.id} className="card" style={{ borderColor: 'var(--amber)' }}>
              <div className="row">
                <span style={{ fontSize: 20 }}>🔔</span>
                <div style={{ flex: 1 }}>
                  <b style={{ fontSize: 14 }}>
                    {r.student.first_name || r.student.username} «{r.course_title}» kursiga yozilmoqchi
                  </b>
                  <p className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>
                    Tasdiqlasangiz, o'quvchi kurs darslarini ko'radi va jonli darsga kira oladi.
                  </p>
                </div>
                <button className="btn secondary sm" onClick={() => respondRequest(r.id, 'decline')}>Rad etish</button>
                <button className="btn sm" onClick={() => respondRequest(r.id, 'approve')}>Qabul qilish</button>
              </div>
            </div>
          ))}

          <section>
            <div className="section-head">
              <h3>Bugungi darslar <span className="count">({todayLessons.length})</span></h3>
              <button className="btn secondary sm" onClick={() => setTab('lessons')}>Barcha darslar →</button>
            </div>
            <div className="card">
              {todayLessons.length === 0 && (
                <div className="empty-state">
                  <div className="ico">🗓️</div>
                  <p>Bugunga dars rejalashtirilmagan.</p>
                  <p className="hint">«Darslar» bo'limida yangi dars rejalashtiring.</p>
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
                          {l.status === 'live' ? 'Xonaga kirish' : 'Boshlash'}
                        </button>
                      )}
                    </div>
                  )
                })}
            </div>
          </section>
        </>
      )}

      {/* ═══ Kurslar ═══ */}
      {tab === 'courses' && (
        <>
          <section>
            <div className="section-head">
              <h3>Kurslarim <span className="count">({courses.length})</span></h3>
              <button className="btn sm" onClick={() => setOpenForm(openForm === 'course' ? '' : 'course')}>
                + Yangi kurs
              </button>
            </div>

            {openForm === 'course' && (
              <form className="card form-pop" onSubmit={createCourse} style={{ marginBottom: 14 }}>
                <h3>Yangi kurs yaratish</h3>
                <div className="grid-2">
                  <div className="field">
                    <label>Kurs nomi</label>
                    <input className="input" placeholder="Masalan: Algebra · 7-sinf" value={courseForm.title}
                      onChange={(e) => setCourseForm({ ...courseForm, title: e.target.value })} required autoFocus />
                  </div>
                  <div className="field">
                    <label>Fan</label>
                    <input className="input" placeholder="Masalan: Matematika" value={courseForm.subject}
                      onChange={(e) => setCourseForm({ ...courseForm, subject: e.target.value })} />
                  </div>
                </div>
                <div className="row">
                  <button className="btn sm">Saqlash</button>
                  <button type="button" className="btn secondary sm" onClick={() => setOpenForm('')}>Bekor qilish</button>
                </div>
              </form>
            )}

            {!loading && courses.length === 0 && (
              <div className="card empty-state">
                <div className="ico">📚</div>
                <p>Hali kurs yaratmagansiz.</p>
                <p className="hint">Yuqoridagi «+ Yangi kurs» tugmasi orqali birinchi kursingizni oching.</p>
              </div>
            )}
            <div className="course-grid">
              {courses.map((c) => {
                const courseLessons = lessons.filter((l) => l.course === c.id)
                const next = nextByCourse[c.id]
                const roster = courseStudents[c.id]
                return (
                  <div className="course-card clickable" key={c.id}
                    onClick={() => filterByCourse(c.id)}
                    title="Jadvalni shu kurs bo'yicha ko'rish">
                    {c.subject && <span className="subject">{c.subject}</span>}
                    <h4>{c.title}</h4>
                    <div className="meta">
                      <span>👥 {c.student_count} o'quvchi</span>
                      <span>🗓️ {courseLessons.length} dars</span>
                    </div>
                    <div className="next">
                      {next
                        ? <>Keyingi: <b>{next.title}</b> · {fmtWhen(next.starts_at).rel} {fmtWhen(next.starts_at).abs}</>
                        : <span className="muted">Rejalashtirilgan dars yo'q</span>}
                    </div>
                    <button className="btn secondary sm" onClick={(e) => { e.stopPropagation(); toggleManage(c.id) }}>
                      {manageFor === c.id ? "▴ O'quvchilarni yopish" : "▾ O'quvchilarni boshqarish"}
                    </button>
                    {manageFor === c.id && (
                      <div className="roster" onClick={(e) => e.stopPropagation()}>
                        {!roster && <span className="muted" style={{ fontSize: 12.5 }}>Yuklanmoqda…</span>}
                        {roster && roster.length === 0 && (
                          <span className="muted" style={{ fontSize: 12.5 }}>Hali o'quvchi yozilmagan.</span>
                        )}
                        {roster && roster.map((en) => (
                          <div className="roster-line" key={en.id}>
                            <span className="name">👤 {en.student.first_name || en.student.username}</span>
                            {en.status === 'pending' && <span className="badge amber">Kutilmoqda</span>}
                            {en.status === 'declined' && <span className="badge red">Rad etilgan</span>}
                            <button className="roster-x" title="Kursdan chiqarish"
                              onClick={() => removeStudent(c.id, en.student.id)}>✕</button>
                          </div>
                        ))}
                        <div className="roster-add">
                          <input className="input" placeholder="Login yoki taklif kodi"
                            value={manageFor === c.id ? newStudent : ''}
                            onChange={(e) => setNewStudent(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addStudent(c.id) } }} />
                          <button className="btn sm" disabled={enrollBusy} onClick={() => addStudent(c.id)}>
                            {enrollBusy ? '…' : 'Biriktirish'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        </>
      )}

      {/* ═══ Darslar ═══ */}
      {tab === 'lessons' && (
        <section>
          <div className="section-head">
            <h3>
              Darslar jadvali
              {courseFilter && (
                <span className="count"> — {courses.find((c) => c.id === courseFilter)?.title}</span>
              )}
            </h3>
            <button className="btn sm" onClick={() => setOpenForm(openForm === 'lesson' ? '' : 'lesson')}>
              + Yangi dars
            </button>
          </div>

          {openForm === 'lesson' && (
            <form className="card form-pop" onSubmit={createLesson} style={{ marginBottom: 14 }}>
              <h3>Yangi dars rejalashtirish</h3>
              <div className="grid-2">
                <div className="field">
                  <label>Kurs</label>
                  <select className="input" value={lessonForm.course}
                    onChange={(e) => setLessonForm({ ...lessonForm, course: e.target.value })} required autoFocus>
                    <option value="">Tanlang…</option>
                    {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>Mavzu</label>
                  <input className="input" placeholder="Dars mavzusi" value={lessonForm.title}
                    onChange={(e) => setLessonForm({ ...lessonForm, title: e.target.value })} required />
                </div>
                <div className="field">
                  <label>Boshlanish vaqti</label>
                  <input className="input" type="datetime-local" value={lessonForm.starts_at}
                    onChange={(e) => setLessonForm({ ...lessonForm, starts_at: e.target.value })} required />
                </div>
                <div className="field">
                  <label>Davomiyligi (daqiqa)</label>
                  <input className="input" type="number" min="10" max="180" value={lessonForm.duration_min}
                    onChange={(e) => setLessonForm({ ...lessonForm, duration_min: e.target.value })} />
                </div>
              </div>
              <div className="row">
                <button className="btn sm">Rejalashtirish</button>
                <button type="button" className="btn secondary sm" onClick={() => setOpenForm('')}>Bekor qilish</button>
              </div>
            </form>
          )}

          <div className="chip-row" style={{ marginBottom: 12 }}>
            {FILTERS.map((f) => (
              <button key={f.key} className={`chip ${filter === f.key ? 'active' : ''}`}
                onClick={() => setFilter(f.key)}>
                {f.label}<span className="n">{filterCounts[f.key]}</span>
              </button>
            ))}
            {courseFilter && (
              <button className="chip" onClick={() => setCourseFilter('')}>✕ Kurs filtri</button>
            )}
          </div>

          <div className="card" style={{ padding: '6px 16px' }}>
            {filtered.length === 0 && (
              <div className="empty-state">
                <div className="ico">🗓️</div>
                <p>{filter === 'today' ? 'Bugunga dars rejalashtirilmagan.' : "Bu bo'limda dars yo'q."}</p>
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
                    const rows = journal[l.id]
                    return (
                      <Fragment key={l.id}>
                        <tr>
                          <td style={{ fontWeight: 600 }}>{l.title}</td>
                          <td className="muted">{l.course_title}</td>
                          <td className="when">
                            <div className="rel">{when.rel}</div>
                            {when.abs && <div className="abs">{when.abs}</div>}
                          </td>
                          <td className="muted">{l.duration_min} daq</td>
                          <td><span className={`badge ${meta.badge}`}><span className={`dot ${meta.dot}`} />{meta.label}</span></td>
                          <td>
                            <div className="row" style={{ justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
                              {['live', 'finished'].includes(l.status) && (
                                <button className={`btn secondary sm ${journalFor === l.id ? 'active' : ''}`}
                                  onClick={() => toggleJournal(l.id)}>
                                  {journalFor === l.id ? '▴ Jurnal' : '▾ Jurnal'}
                                </button>
                              )}
                              {['scheduled', 'live'].includes(l.status) && (
                                <>
                                  <button className="btn sm" onClick={() => navigate(`/lessons/${l.id}/room`)}>
                                    {l.status === 'live' ? 'Xonaga kirish' : 'Boshlash'}
                                  </button>
                                  <button className="btn secondary sm" onClick={() => finishLesson(l.id)}>
                                    Tugatish
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                        {journalFor === l.id && (
                          <tr className="journal-row">
                            <td colSpan={6}>
                              {!rows && <span className="muted" style={{ fontSize: 13 }}>Yuklanmoqda…</span>}
                              {rows && rows.length === 0 && (
                                <span className="muted" style={{ fontSize: 13 }}>Bu darsga hech kim kirmagan.</span>
                              )}
                              {rows && rows.length > 0 && (
                                <div className="journal">
                                  <div className="journal-title">Davomat — {rows.length} o'quvchi</div>
                                  {rows.map((a) => (
                                    <div className="journal-line" key={a.id}>
                                      <span className="name">👤 {a.student.first_name || a.student.username}</span>
                                      <span className="muted">
                                        {a.joined_at ? fmtTime(new Date(a.joined_at)) : '—'}
                                        {' → '}
                                        {a.left_at ? fmtTime(new Date(a.left_at)) : 'hali darsda'}
                                      </span>
                                      <span className="mins">{a.minutes != null ? `${a.minutes} daq` : ''}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </Fragment>
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
