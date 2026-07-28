import '@livekit/components-styles'

import {
  LiveKitRoom,
  PreJoin,
  useDataChannel,
  useLocalParticipant,
  useParticipants,
  VideoConference,
} from '@livekit/components-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import api, { errMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const enc = new TextEncoder()
const dec = new TextDecoder()

function fmtElapsed(sec) {
  const h = Math.floor(sec / 3600)
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0')
  const s = String(sec % 60).padStart(2, '0')
  return h ? `${h}:${m}:${s}` : `${m}:${s}`
}

/** Ustki panel: dars nomi, jonli timer, qatnashchilar soni, ekran so'rovi. */
function RoomTopBar({ title, isTeacher, userName }) {
  const participants = useParticipants()
  const { localParticipant } = useLocalParticipant()
  const [elapsed, setElapsed] = useState(0)
  const [requests, setRequests] = useState([]) // o'qituvchiga kelgan so'rovlar
  const [sent, setSent] = useState(false)

  const { send } = useDataChannel('screen-request', (msg) => {
    if (!isTeacher) return
    try {
      const data = JSON.parse(dec.decode(msg.payload))
      const id = msg.from?.identity || String(Date.now())
      setRequests((prev) =>
        prev.some((r) => r.id === id) ? prev : [...prev, { id, name: data.name || "O'quvchi" }],
      )
    } catch { /* yaroqsiz xabar — e'tiborsiz */ }
  })

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  function requestScreen() {
    send(enc.encode(JSON.stringify({ name: userName })), { reliable: true })
    setSent(true)
    setTimeout(() => setSent(false), 30_000)
  }

  async function shareScreen(req) {
    setRequests((prev) => prev.filter((r) => r.id !== req.id))
    try {
      await localParticipant.setScreenShareEnabled(true)
    } catch { /* foydalanuvchi share oynasini bekor qildi */ }
  }

  return (
    <>
      <div className="room-topbar">
        <span className="live-dot" />
        <span className="room-topbar-title">{title}</span>
        <span className="room-topbar-timer">{fmtElapsed(elapsed)}</span>
        <span className="room-topbar-count">👥 {participants.length}</span>
        {!isTeacher && (
          <button className="room-ask-btn" onClick={requestScreen} disabled={sent}>
            {sent ? "✓ So'rov yuborildi" : "🖥 Ekran so'rash"}
          </button>
        )}
      </div>
      {isTeacher && requests.length > 0 && (
        <div className="screen-request-stack">
          {requests.map((r) => (
            <div key={r.id} className="screen-request-toast">
              <span className="msg"><b>{r.name}</b> ekraningizni ko'rishni so'rayapti</span>
              <div className="row">
                <button className="ok" onClick={() => shareScreen(r)}>Ekranni ulashish</button>
                <button
                  className="no"
                  onClick={() => setRequests((p) => p.filter((x) => x.id !== r.id))}
                >
                  Keyinroq
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}

export default function LessonRoom() {
  const { lessonId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [conn, setConn] = useState(null)
  const [lesson, setLesson] = useState(null)
  const [choices, setChoices] = useState(null) // PreJoin natijasi — kamera/mikrofon tanlovi
  const [error, setError] = useState('')

  useEffect(() => {
    api.post('/live/token/', { lesson_id: lessonId })
      .then((r) => setConn(r.data))
      .catch((err) => setError(errMessage(err)))
    api.get(`/lessons/${lessonId}/`)
      .then((r) => setLesson(r.data))
      .catch(() => { /* sarlavha majburiy emas */ })
  }, [lessonId])

  async function onLeave() {
    if (user.role === 'student') {
      try { await api.post('/live/leave/', { lesson_id: lessonId }) } catch { /* davomat backend'da yopiladi */ }
    }
    navigate('/')
  }

  const roomOptions = useMemo(() => ({
    videoCaptureDefaults: choices?.videoDeviceId ? { deviceId: choices.videoDeviceId } : undefined,
    audioCaptureDefaults: choices?.audioDeviceId ? { deviceId: choices.audioDeviceId } : undefined,
  }), [choices])

  if (error) {
    return (
      <div className="room-loading">
        <div className="room-error-card">
          <div className="error-box">{error}</div>
          <button className="btn secondary sm" onClick={() => navigate('/')}>← Orqaga</button>
        </div>
      </div>
    )
  }

  if (!conn) {
    return (
      <div className="room-loading">
        <div className="room-spinner" />
        <p>Xonaga ulanilmoqda…</p>
      </div>
    )
  }

  // ── Lobby (Meet uslubi): kamera/mikrofonni ko'rib, sozlab kirish ──
  if (!choices) {
    return (
      <div className="room-lobby" data-lk-theme="default">
        <div className="room-lobby-card">
          <h1>Darsga tayyormisiz?</h1>
          <p className="room-lobby-sub">{lesson?.title || 'Jonli dars'}</p>
          <PreJoin
            defaults={{
              username: user.first_name || user.username,
              videoEnabled: true,
              audioEnabled: true,
            }}
            joinLabel="Darsga qo'shilish"
            micLabel="Mikrofon"
            camLabel="Kamera"
            persistUserChoices
            onSubmit={setChoices}
            onError={() => { /* kamera/mikrofon yo'q bo'lsa ham kirish mumkin */ }}
          />
          <button className="room-lobby-back" onClick={() => navigate('/')}>← Orqaga qaytish</button>
        </div>
      </div>
    )
  }

  return (
    <div className="room-wrap">
      <LiveKitRoom
        serverUrl={conn.url}
        token={conn.token}
        connect
        video={choices.videoEnabled}
        audio={choices.audioEnabled}
        options={roomOptions}
        onDisconnected={onLeave}
        data-lk-theme="default"
        style={{ height: '100%' }}
      >
        <RoomTopBar
          title={lesson?.title || 'Jonli dars'}
          isTeacher={!!conn.is_teacher}
          userName={user.first_name || user.username}
        />
        <VideoConference />
      </LiveKitRoom>
    </div>
  )
}
