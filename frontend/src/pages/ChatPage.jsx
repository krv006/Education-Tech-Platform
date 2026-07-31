// Telegram uslubidagi asosiy ekran (EduTech.docx: "interfeys telegram asosida").
// Chapda qidiruv + chatlar (har kurs = bitta guruh chat, 1 qatordan),
// o'ngda suhbat; kurs chatida tablar: Chat | Darslar | O'quvchilar.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import api, { errMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import HomeworkTab from '../components/HomeworkTab'
import { fmtTime, fmtWhen, LESSON_STATUS, sameDay } from '../lib/ui'

// Xabar ichidagi /boards/<id> havolasini bosiladigan qilamiz (doska PDF xabari)
function renderMsgText(text) {
  const parts = String(text).split(/(\/boards\/[0-9a-f-]{36})/g)
  return parts.map((p, i) =>
    p.startsWith('/boards/')
      ? <Link key={i} to={p} className="msg-board-link">📋 Doskani ochish</Link>
      : p,
  )
}

function fmtChatTime(iso) {
  const d = new Date(iso)
  if (sameDay(d, new Date())) return fmtTime(d)
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`
}

function Avatar({ name, kind, size }) {
  const initial = (name || '?').trim()[0]?.toUpperCase() || '?'
  return (
    <div className={`chat-avatar ${kind === 'course' ? 'group' : ''}`} style={size ? { width: size, height: size } : undefined}>
      {kind === 'course' ? '👥' : initial}
    </div>
  )
}

/** Tugagan dars davomati — Darslar tabida ochiladi (panel o'rnini bosadi). */
function AttendanceMini({ lessonId }) {
  const [rows, setRows] = useState(null)

  useEffect(() => {
    api.get('/attendance/', { params: { lesson: lessonId } })
      .then((r) => setRows(r.data.results || r.data))
      .catch(() => setRows([]))
  }, [lessonId])

  if (rows === null) return <p className="muted" style={{ padding: '4px 8px' }}>Yuklanmoqda…</p>
  if (rows.length === 0) return <p className="muted" style={{ padding: '4px 8px' }}>Davomat yozuvi yo'q.</p>
  return (
    <div className="att-mini">
      {rows.map((a) => (
        <div key={a.id} className="att-mini-row">
          <span className="who">{a.student.first_name || a.student.username}</span>
          <span title="Darsda bo'lgan vaqt">⏱ {a.minutes ?? '—'} daq</span>
          <span title="Diqqat tekshiruvi: javob/jami">👀 {a.attention_answered}/{a.attention_total}</span>
          <span title="Dars oynasidan chiqishlar" className={a.focus_exits > 2 ? 'warn' : ''}>
            🚪 {a.focus_exits}
          </span>
        </div>
      ))}
    </div>
  )
}

/** Kurs chatidagi "Darslar" tabi — dars ro'yxati + o'qituvchiga tez dars qo'shish. */
function LessonsTab({ courseId, isTeacher }) {
  const navigate = useNavigate()
  const [lessons, setLessons] = useState(null)
  const [form, setForm] = useState(null) // {title, starts_at, duration_min}
  const [openAtt, setOpenAtt] = useState(null) // davomat ochilgan dars id
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/lessons/', { params: { course: courseId, page_size: 100 } })
      const items = (data.results || data).sort((a, b) => new Date(b.starts_at) - new Date(a.starts_at))
      setLessons(items)
    } catch (e) { setErr(errMessage(e)) }
  }, [courseId])

  useEffect(() => { load() }, [load])

  async function createLesson(e) {
    e.preventDefault()
    try {
      await api.post('/lessons/', {
        course: courseId,
        title: form.title,
        starts_at: new Date(form.starts_at).toISOString(),
        duration_min: Number(form.duration_min) || 45,
      })
      setForm(null)
      load()
    } catch (e2) { setErr(errMessage(e2)) }
  }

  return (
    <div className="course-tab-body">
      {err && <div className="error-box">{err}</div>}
      {isTeacher && (
        form ? (
          <form className="tg-form" onSubmit={createLesson}>
            <input className="input" placeholder="Dars mavzusi" required value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <div className="row">
              <input className="input" type="datetime-local" required value={form.starts_at}
                onChange={(e) => setForm({ ...form, starts_at: e.target.value })} />
              <input className="input" type="number" min="10" max="180" value={form.duration_min}
                onChange={(e) => setForm({ ...form, duration_min: e.target.value })} style={{ width: 90 }} />
            </div>
            <div className="row">
              <button className="btn sm" type="submit">Saqlash</button>
              <button className="btn secondary sm" type="button" onClick={() => setForm(null)}>Bekor</button>
            </div>
          </form>
        ) : (
          <button className="btn sm" onClick={() => setForm({ title: '', starts_at: '', duration_min: 45 })}>
            + Dars qo'shish
          </button>
        )
      )}
      {lessons === null && <p className="muted">Yuklanmoqda…</p>}
      {lessons?.length === 0 && <p className="muted">Hali dars yo'q.</p>}
      {lessons?.map((l) => {
        const meta = LESSON_STATUS[l.status] || { label: l.status, badge: 'indigo', dot: 'indigo' }
        const today = sameDay(new Date(l.starts_at), new Date())
        return (
          <div key={l.id}>
            <div className={`lesson-line ${today ? 'today-row' : ''}`}>
              <div className="info">
                <div className="name">{l.title}</div>
                <div className="meta">{fmtWhen(l.starts_at).rel} {fmtWhen(l.starts_at).abs} · {l.duration_min} daq</div>
              </div>
              <span className={`badge ${meta.badge}`}><span className={`dot ${meta.dot}`} />{meta.label}</span>
              {l.status === 'finished' && (
                <button
                  className="btn secondary sm"
                  title="Davomat va diqqat hisoboti"
                  onClick={() => setOpenAtt((v) => (v === l.id ? null : l.id))}
                >
                  📊
                </button>
              )}
              {['scheduled', 'live'].includes(l.status) && (
                <button className="btn sm" onClick={() => navigate(`/lessons/${l.id}/room`)}>
                  {l.status === 'live' ? 'Kirish' : isTeacher ? 'Boshlash' : 'Kirish'}
                </button>
              )}
            </div>
            {openAtt === l.id && <AttendanceMini lessonId={l.id} />}
          </div>
        )
      })}
    </div>
  )
}

/** Kurs chatidagi "O'quvchilar" tabi (faqat o'qituvchi) — a'zolar + kutilayotgan
 * so'rovlar + jonli qidiruv (yozganda username bo'yicha takliflar chiqadi). */
function StudentsTab({ courseId }) {
  const [students, setStudents] = useState(null)
  const [pending, setPending] = useState([])
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState(null) // null = yopiq
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([
        api.get(`/courses/${courseId}/students/`),
        api.get('/courses/requests/'),
      ])
      const all = s.data.results || s.data
      setStudents(all.filter((e) => e.status === 'approved'))
      setPending((r.data.results || r.data).filter((e) => e.course === courseId))
    } catch (e) { setErr(errMessage(e)) }
  }, [courseId])

  useEffect(() => { load() }, [load])

  // Jonli qidiruv — 300ms debounce bilan (Telegram inline uslubi)
  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) { setSuggestions(null); return undefined }
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get(`/courses/${courseId}/search-students/`, { params: { q } })
        setSuggestions(data)
      } catch { setSuggestions([]) }
    }, 300)
    return () => clearTimeout(t)
  }, [query, courseId])

  async function respond(enrollmentId, action) {
    try {
      await api.post('/courses/requests/respond/', { enrollment_id: enrollmentId, action })
      load()
    } catch (e) { setErr(errMessage(e)) }
  }

  async function addStudent(s) {
    try {
      await api.post(`/courses/${courseId}/enroll/`, { student_id: s.id })
      setQuery('')
      setSuggestions(null)
      load()
    } catch (e2) { setErr(errMessage(e2)) }
  }

  return (
    <div className="course-tab-body">
      {err && <div className="error-box">{err}</div>}
      <div className="student-search">
        <input
          className="input"
          placeholder="🔍 O'quvchi qidirish — login, ism yoki taklif kodi…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {suggestions !== null && (
          <div className="student-suggest">
            {suggestions.length === 0 && <div className="none">Hech kim topilmadi</div>}
            {suggestions.map((s) => (
              <button
                key={s.id}
                className="student-suggest-row"
                disabled={s.enroll_status === 'approved'}
                onClick={() => addStudent(s)}
              >
                <Avatar name={s.first_name || s.username} size={32} />
                <span className="who">
                  <b>{s.first_name || s.username} {s.last_name}</b>
                  <span className="muted">@{s.username}</span>
                </span>
                {s.enroll_status === 'approved'
                  ? <span className="badge green">A'zo</span>
                  : s.enroll_status === 'pending'
                    ? <span className="badge amber">So'rov bor</span>
                    : <span className="add">+ Qo'shish</span>}
              </button>
            ))}
          </div>
        )}
      </div>
      {pending.map((p) => (
        <div key={p.id} className="lesson-line" style={{ background: '#fff7e0' }}>
          <div className="info">
            <div className="name">{p.student.first_name || p.student.username}</div>
            <div className="meta">Yozilish so'rovi kutilmoqda</div>
          </div>
          <button className="btn sm" onClick={() => respond(p.id, 'approve')}>Qabul</button>
          <button className="btn secondary sm" onClick={() => respond(p.id, 'decline')}>Rad</button>
        </div>
      ))}
      {students === null && <p className="muted">Yuklanmoqda…</p>}
      {students?.length === 0 && pending.length === 0 && <p className="muted">Hali o'quvchi yo'q.</p>}
      {students?.map((e) => (
        <div key={e.id} className="lesson-line">
          <Avatar name={e.student.first_name || e.student.username} size={36} />
          <div className="info">
            <div className="name">{e.student.first_name || e.student.username} {e.student.last_name}</div>
            <div className="meta">@{e.student.username}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function ChatPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [rooms, setRooms] = useState([])
  const [active, setActive] = useState(null)
  const [tab, setTab] = useState('chat') // kurs chatida: chat | lessons | students
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [showNew, setShowNew] = useState(false)   // student: direct so'rov + katalog
  const [teachers, setTeachers] = useState([])
  const [catalog, setCatalog] = useState([])
  const [liveLessons, setLiveLessons] = useState([]) // jonli efir banneri
  const [courseForm, setCourseForm] = useState(null) // teacher: yangi kurs
  const listRef = useRef(null)
  const activeRef = useRef(null)
  activeRef.current = active

  const isTeacher = user.role === 'teacher'

  const loadRooms = useCallback(async () => {
    try {
      const { data } = await api.get('/chat/rooms/')
      setRooms(data.results || data)
    } catch (err) { setError(errMessage(err)) }
  }, [])

  useEffect(() => {
    loadRooms()
    const t = setInterval(loadRooms, 8000)
    return () => clearInterval(t)
  }, [loadRooms])

  // Jonli efir banneri — Zoom qismi: hozir ketayotgan darslar doim ko'z oldida
  useEffect(() => {
    async function loadLive() {
      try {
        const { data } = await api.get('/lessons/', { params: { status: 'live' } })
        setLiveLessons(data.results || data)
      } catch { /* keyingi poll */ }
    }
    loadLive()
    const t = setInterval(loadLive, 15000)
    return () => clearInterval(t)
  }, [])

  // Ochiq suhbat xabarlari — polling
  useEffect(() => {
    if (!active) return undefined
    let last = null
    let cancelled = false
    async function poll() {
      try {
        const params = last ? { after: last } : {}
        const { data } = await api.get(`/chat/rooms/${active.id}/messages/`, { params })
        if (cancelled || activeRef.current?.id !== active.id) return
        if (data.length) {
          last = data[data.length - 1].created_at
          setMessages((prev) => {
            if (!params.after) return data
            const seen = new Set(prev.map((m) => m.id))
            const fresh = data.filter((m) => !seen.has(m.id))
            return fresh.length ? [...prev, ...fresh] : prev
          })
        } else if (!params.after) {
          setMessages([])
        }
      } catch { /* tarmoq — keyingi poll */ }
    }
    setMessages([])
    poll()
    const t = setInterval(poll, 3000)
    return () => { cancelled = true; clearInterval(t) }
  }, [active])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages])

  function open(room) {
    setActive(room)
    setTab('chat')
  }

  async function send(e) {
    e.preventDefault()
    const value = text.trim()
    if (!value || !active) return
    setText('')
    try {
      const { data } = await api.post(`/chat/rooms/${active.id}/send/`, { text: value })
      setMessages((prev) => (prev.some((m) => m.id === data.id) ? prev : [...prev, data]))
      loadRooms()
    } catch (err) { setError(errMessage(err)) }
  }

  async function openNew() {
    setShowNew(true)
    try {
      const [t, c] = await Promise.all([
        api.get('/chat/rooms/teachers/'),
        api.get('/courses/catalog/'),
      ])
      setTeachers(t.data)
      setCatalog(c.data.results || c.data)
    } catch (err) { setError(errMessage(err)) }
  }

  async function enrollCourse(course) {
    try {
      await api.post(`/courses/${course.id}/enroll/`, {})
      const { data } = await api.get('/courses/catalog/')
      setCatalog(data.results || data)
    } catch (err) { setError(errMessage(err)) }
  }

  async function requestDirect(teacher) {
    try {
      const { data } = await api.post('/chat/rooms/direct/request/', { teacher: teacher.username })
      setShowNew(false)
      await loadRooms()
      open(data)
    } catch (err) { setError(errMessage(err)) }
  }

  async function respond(room, action) {
    try {
      const { data } = await api.post('/chat/rooms/direct/respond/', { room_id: room.id, action })
      setActive(data)
      loadRooms()
    } catch (err) { setError(errMessage(err)) }
  }

  async function createCourse(e) {
    e.preventDefault()
    try {
      await api.post('/courses/', courseForm)
      setCourseForm(null)
      loadRooms()
    } catch (err) { setError(errMessage(err)) }
  }

  const canWrite = active && (active.kind === 'course' || active.direct_status === 'active')
  const filtered = rooms.filter((r) =>
    r.title.toLowerCase().includes(search.trim().toLowerCase()),
  )

  return (
    <div className={`chat-page tg ${active ? 'thread-open' : ''}`}>
      {/* ── Chap: Telegram sidebar ── */}
      <aside className="chat-list">
        <div className="chat-list-head">
          <button className="tg-menu-btn" onClick={() => setMenuOpen((v) => !v)}>☰</button>
          <input
            className="tg-search"
            placeholder="Qidirish"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {isTeacher
            ? <button className="btn sm" title="Yangi kurs (guruh)" onClick={() => setCourseForm({ title: '', subject: '', description: '' })}>+</button>
            : <button className="btn sm" title="O'qituvchiga yozish" onClick={openNew}>+</button>}
        </div>

        {menuOpen && (
          <div className="tg-menu">
            <div className="tg-menu-user">
              <Avatar name={user.first_name || user.username} size={40} />
              <div>
                <b>{user.first_name || user.username}</b>
                <div className="muted" style={{ fontSize: 12 }}>@{user.username}</div>
              </div>
            </div>
            {user.invite_code && (
              <button onClick={() => navigator.clipboard?.writeText(user.invite_code)}>
                🎟 Taklif kodim: {user.invite_code}
              </button>
            )}
            <button onClick={() => { logout(); navigate('/login') }}>🚪 Chiqish</button>
          </div>
        )}

        {/* Jonli efir — Zoom kirish nuqtasi */}
        {liveLessons.map((l) => (
          <button key={l.id} className="live-banner" onClick={() => navigate(`/lessons/${l.id}/room`)}>
            <span className="live-dot" />
            <span className="lb-body">
              <b>{l.title}</b>
              <span>{l.course_title} · jonli efirda</span>
            </span>
            <span className="lb-go">Kirish</span>
          </button>
        ))}

        {error && <div className="error-box" style={{ margin: 10 }}>{error}</div>}
        {filtered.length === 0 && <p className="muted" style={{ padding: 16 }}>Chat topilmadi.</p>}
        {filtered.map((r) => (
          <button
            key={r.id}
            className={`chat-row ${active?.id === r.id ? 'active' : ''}`}
            onClick={() => open(r)}
          >
            <Avatar name={r.title} kind={r.kind} />
            <div className="chat-row-body">
              <div className="top">
                <span className="name">{r.title}</span>
                {r.last_message && <span className="time">{fmtChatTime(r.last_message.created_at)}</span>}
              </div>
              <div className="bottom">
                <span className="preview">
                  {r.kind === 'direct' && r.direct_status === 'pending' && "⏳ So'rov kutilmoqda"}
                  {r.kind === 'direct' && r.direct_status === 'blocked' && '🚫 Bloklangan'}
                  {(r.kind === 'course' || r.direct_status === 'active') && (
                    r.last_message
                      ? <>{r.last_message.sender}: {r.last_message.text}</>
                      : r.kind === 'course' ? 'Kurs guruhi' : "Xabarlar yo'q"
                  )}
                </span>
                {r.unread > 0 && <span className="unread">{r.unread}</span>}
              </div>
            </div>
          </button>
        ))}
      </aside>

      {/* ── O'ng: suhbat / kurs ── */}
      <section className="chat-thread">
        {!active ? (
          <div className="chat-empty">
            <div className="tg-empty-pill">Suhbatni tanlang</div>
          </div>
        ) : (
          <>
            <div className="chat-thread-head">
              <button className="chat-back" onClick={() => setActive(null)}>←</button>
              <Avatar name={active.title} kind={active.kind} />
              <div className="info">
                <b>{active.title}</b>
                <span className="muted">
                  {active.kind === 'course' ? 'Kurs guruhi' : 'Shaxsiy suhbat'}
                </span>
              </div>
              {isTeacher && active.kind === 'direct' && active.direct_status === 'active' && (
                <button className="btn secondary sm" onClick={() => respond(active, 'block')}>🚫 Block</button>
              )}
            </div>

            {/* Kurs chatida tablar */}
            {active.kind === 'course' && (
              <div className="tg-tabs">
                <button className={tab === 'chat' ? 'on' : ''} onClick={() => setTab('chat')}>💬 Chat</button>
                <button className={tab === 'lessons' ? 'on' : ''} onClick={() => setTab('lessons')}>📅 Darslar</button>
                <button className={tab === 'homework' ? 'on' : ''} onClick={() => setTab('homework')}>📝 Vazifa</button>
                {isTeacher && (
                  <button className={tab === 'students' ? 'on' : ''} onClick={() => setTab('students')}>👥 O'quvchilar</button>
                )}
              </div>
            )}

            {isTeacher && active.kind === 'direct' && active.direct_status === 'pending' && (
              <div className="chat-request-bar">
                <span><b>{active.title}</b> yozishmoqchi. Qabul qilasizmi?</span>
                <button className="btn sm" onClick={() => respond(active, 'accept')}>Qabul qilish</button>
                <button className="btn secondary sm" onClick={() => respond(active, 'block')}>Rad etish</button>
              </div>
            )}

            {active.kind === 'course' && tab === 'lessons' && (
              <LessonsTab courseId={active.course} isTeacher={isTeacher} />
            )}
            {active.kind === 'course' && tab === 'students' && isTeacher && (
              <StudentsTab courseId={active.course} />
            )}
            {active.kind === 'course' && tab === 'homework' && (
              <HomeworkTab courseId={active.course} isTeacher={isTeacher} />
            )}

            {(active.kind !== 'course' || tab === 'chat') && (
              <>
                <div className="chat-messages" ref={listRef}>
                  {messages.map((m, i) => {
                    const mine = m.sender.id === user.id
                    const prev = messages[i - 1]
                    const showName = !mine && active.kind === 'course'
                      && (!prev || prev.sender.id !== m.sender.id)
                    return (
                      <div key={m.id} className={`bubble-row ${mine ? 'mine' : ''}`}>
                        <div className="bubble">
                          {showName && <div className="sender">{m.sender.first_name || m.sender.username}</div>}
                          <span className="text">{renderMsgText(m.text)}</span>
                          <span className="stamp">{fmtTime(new Date(m.created_at))}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>

                {canWrite ? (
                  <form className="chat-input" onSubmit={send}>
                    <input
                      className="input"
                      placeholder="Xabar yozing…"
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                    />
                    <button className="btn" type="submit" disabled={!text.trim()}>➤</button>
                  </form>
                ) : (
                  <div className="chat-locked">
                    {active.direct_status === 'pending' && !isTeacher && "⏳ So'rov yuborilgan — o'qituvchi javobini kuting."}
                    {active.direct_status === 'pending' && isTeacher && "So'rovga javob bering."}
                    {active.direct_status === 'blocked' && (isTeacher
                      ? <button className="btn sm" onClick={() => respond(active, 'accept')}>Blokdan chiqarish</button>
                      : <button className="btn sm" onClick={() => requestDirect({ username: active.other_user?.username })}>Qayta so'rov yuborish</button>
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </section>

      {/* ── Student: yangi direct so'rov + kurs katalogi ── */}
      {showNew && (
        <div className="chat-modal" onClick={() => setShowNew(false)}>
          <div className="chat-modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>O'qituvchiga yozish</h3>
            <p className="muted">So'rov yuborasiz — o'qituvchi qabul qilgach chat ochiladi.</p>
            {teachers.length === 0 && <p className="muted">O'qituvchilaringiz topilmadi.</p>}
            {teachers.map((t) => (
              <div key={t.id} className="chat-teacher-row">
                <Avatar name={t.first_name || t.username} />
                <span className="name">{t.first_name || t.username} {t.last_name}</span>
                {t.direct_status === 'active' && <span className="badge green">Ochiq</span>}
                {t.direct_status === 'pending' && <span className="badge amber">Kutilmoqda</span>}
                {(t.direct_status === null || t.direct_status === 'blocked') && (
                  <button className="btn sm" onClick={() => requestDirect(t)}>So'rov yuborish</button>
                )}
              </div>
            ))}

            <h3 style={{ marginTop: 8 }}>Kurslarga yozilish</h3>
            <p className="muted">So'rov o'qituvchi tasdig'idan keyin guruh chat ochiladi.</p>
            {catalog.length === 0 && <p className="muted">Ochiq kurslar yo'q.</p>}
            {catalog.map((c) => (
              <div key={c.id} className="chat-teacher-row">
                <Avatar name={c.title} kind="course" />
                <span className="name">
                  {c.title}
                  <span className="muted" style={{ display: 'block', fontSize: 12, fontWeight: 400 }}>
                    {c.teacher.first_name || c.teacher.username} · {c.student_count} o'quvchi
                  </span>
                </span>
                {c.my_status === 'approved' && <span className="badge green">A'zoman</span>}
                {c.my_status === 'pending' && <span className="badge amber">Kutilmoqda</span>}
                {(c.my_status === null || c.my_status === 'declined') && (
                  <button className="btn sm" onClick={() => enrollCourse(c)}>Yozilish</button>
                )}
              </div>
            ))}
            <button className="btn secondary sm" onClick={() => setShowNew(false)}>Yopish</button>
          </div>
        </div>
      )}

      {/* ── Teacher: yangi kurs (guruh) ── */}
      {courseForm && (
        <div className="chat-modal" onClick={() => setCourseForm(null)}>
          <form className="chat-modal-card" onClick={(e) => e.stopPropagation()} onSubmit={createCourse}>
            <h3>Yangi kurs — guruh chat</h3>
            <p className="muted">Kurs yaratilganda avtomatik guruh chati ochiladi.</p>
            <input className="input" placeholder="Kurs nomi" required value={courseForm.title}
              onChange={(e) => setCourseForm({ ...courseForm, title: e.target.value })} />
            <input className="input" placeholder="Fan (masalan: Matematika)" value={courseForm.subject}
              onChange={(e) => setCourseForm({ ...courseForm, subject: e.target.value })} />
            <textarea className="input" placeholder="Tavsif" rows={3} value={courseForm.description}
              onChange={(e) => setCourseForm({ ...courseForm, description: e.target.value })} />
            <div className="row">
              <button className="btn sm" type="submit">Yaratish</button>
              <button className="btn secondary sm" type="button" onClick={() => setCourseForm(null)}>Bekor</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
