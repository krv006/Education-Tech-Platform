// Telegram uslubidagi chat — chapda ro'yxat, o'ngda suhbat (EduTech.docx).
// Real-time: polling (ro'yxat 8s, ochiq suhbat 3s).
import { useCallback, useEffect, useRef, useState } from 'react'

import api, { errMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { fmtTime, sameDay } from '../lib/ui'

function fmtChatTime(iso) {
  const d = new Date(iso)
  if (sameDay(d, new Date())) return fmtTime(d)
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`
}

function Avatar({ name, kind }) {
  const initial = (name || '?').trim()[0]?.toUpperCase() || '?'
  return <div className={`chat-avatar ${kind === 'course' ? 'group' : ''}`}>{kind === 'course' ? '👥' : initial}</div>
}

export default function ChatPage() {
  const { user } = useAuth()
  const [rooms, setRooms] = useState([])
  const [active, setActive] = useState(null) // tanlangan room obyekti
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [teachers, setTeachers] = useState([])
  const listRef = useRef(null)
  const activeRef = useRef(null)
  activeRef.current = active

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

  // Ochiq suhbat xabarlari — birinchi to'liq, keyin faqat yangilari
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
      } catch { /* tarmoq uzilishi — keyingi poll'da qaytadi */ }
    }
    setMessages([])
    poll()
    const t = setInterval(poll, 3000)
    return () => { cancelled = true; clearInterval(t) }
  }, [active])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages])

  async function send(e) {
    e.preventDefault()
    const value = text.trim()
    if (!value || !active) return
    setText('')
    try {
      const { data } = await api.post(`/chat/rooms/${active.id}/send/`, { text: value })
      setMessages((prev) => [...prev, data])
      loadRooms()
    } catch (err) { setError(errMessage(err)) }
  }

  async function openNew() {
    setShowNew(true)
    try {
      const { data } = await api.get('/chat/rooms/teachers/')
      setTeachers(data)
    } catch (err) { setError(errMessage(err)) }
  }

  async function requestDirect(teacher) {
    try {
      const { data } = await api.post('/chat/rooms/direct/request/', { teacher: teacher.username })
      setShowNew(false)
      await loadRooms()
      setActive(data)
    } catch (err) { setError(errMessage(err)) }
  }

  async function respond(room, action) {
    try {
      const { data } = await api.post('/chat/rooms/direct/respond/', { room_id: room.id, action })
      setActive(data)
      loadRooms()
    } catch (err) { setError(errMessage(err)) }
  }

  const isTeacher = user.role === 'teacher'
  const canWrite = active && (active.kind === 'course' || active.direct_status === 'active')

  return (
    <div className={`chat-page ${active ? 'thread-open' : ''}`}>
      {/* ── Chap: chat ro'yxati ── */}
      <aside className="chat-list">
        <div className="chat-list-head">
          <b>💬 Chat</b>
          {!isTeacher && (
            <button className="btn sm" onClick={openNew}>+ Yangi</button>
          )}
        </div>
        {error && <div className="error-box" style={{ margin: 10 }}>{error}</div>}
        {rooms.length === 0 && <p className="muted" style={{ padding: 16 }}>Hozircha chat yo'q.</p>}
        {rooms.map((r) => (
          <button
            key={r.id}
            className={`chat-row ${active?.id === r.id ? 'active' : ''}`}
            onClick={() => setActive(r)}
          >
            <Avatar name={r.title} kind={r.kind} />
            <div className="chat-row-body">
              <div className="top">
                <span className="name">{r.title}</span>
                {r.last_message && <span className="time">{fmtChatTime(r.last_message.created_at)}</span>}
              </div>
              <div className="bottom">
                <span className="preview">
                  {r.kind === 'direct' && r.direct_status === 'pending' && '⏳ So\'rov kutilmoqda'}
                  {r.kind === 'direct' && r.direct_status === 'blocked' && '🚫 Bloklangan'}
                  {(r.kind === 'course' || r.direct_status === 'active') && (
                    r.last_message
                      ? <>{r.last_message.sender}: {r.last_message.text}</>
                      : 'Xabarlar yo\'q'
                  )}
                </span>
                {r.unread > 0 && <span className="unread">{r.unread}</span>}
              </div>
            </div>
          </button>
        ))}
      </aside>

      {/* ── O'ng: suhbat ── */}
      <section className="chat-thread">
        {!active ? (
          <div className="chat-empty">Suhbatni tanlang</div>
        ) : (
          <>
            <div className="chat-thread-head">
              <button className="chat-back" onClick={() => setActive(null)}>←</button>
              <Avatar name={active.title} kind={active.kind} />
              <div className="info">
                <b>{active.title}</b>
                <span className="muted">
                  {active.kind === 'course' ? 'Kurs guruhi' : "Shaxsiy suhbat"}
                </span>
              </div>
              {isTeacher && active.kind === 'direct' && active.direct_status === 'active' && (
                <button className="btn secondary sm" onClick={() => respond(active, 'block')}>🚫 Block</button>
              )}
            </div>

            {isTeacher && active.kind === 'direct' && active.direct_status === 'pending' && (
              <div className="chat-request-bar">
                <span><b>{active.title}</b> yozishmoqchi. Qabul qilasizmi?</span>
                <button className="btn sm" onClick={() => respond(active, 'accept')}>Qabul qilish</button>
                <button className="btn secondary sm" onClick={() => respond(active, 'block')}>Rad etish</button>
              </div>
            )}

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
                      <span className="text">{m.text}</span>
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
      </section>

      {/* ── Yangi direct so'rov (o'quvchi) ── */}
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
            <button className="btn secondary sm" onClick={() => setShowNew(false)}>Yopish</button>
          </div>
        </div>
      )}
    </div>
  )
}
