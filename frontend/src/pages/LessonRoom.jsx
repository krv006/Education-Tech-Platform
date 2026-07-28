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

/** Ustki panel: dars nomi, jonli timer, qatnashchilar, ekran so'rovlari (2 xil):
 *  - "view":  o'quvchi O'QITUVCHINING ekranini ko'rsatishini so'raydi
 *  - "share": o'quvchi O'ZINING ekranini ulashishga RUXSAT so'raydi
 *    (o'quvchi token'ida share yopiq — o'qituvchi tasdiqlasa backend ochadi) */
function RoomTopBar({ title, isTeacher, userName, lessonId }) {
  const participants = useParticipants()
  const { localParticipant } = useLocalParticipant()
  const [elapsed, setElapsed] = useState(0)
  const [requests, setRequests] = useState([]) // o'qituvchiga kelgan so'rovlar
  const [sentView, setSentView] = useState(false)
  const [sentShare, setSentShare] = useState(false)

  function pushRequest(msg, type) {
    if (!isTeacher) return
    try {
      const data = JSON.parse(dec.decode(msg.payload))
      const identity = msg.from?.identity || String(Date.now())
      const id = `${type}:${identity}`
      setRequests((prev) =>
        prev.some((r) => r.id === id) ? prev
          : [...prev, { id, type, identity, name: data.name || "O'quvchi" }],
      )
    } catch { /* yaroqsiz xabar — e'tiborsiz */ }
  }

  const viewCh = useDataChannel('screen-request', (msg) => pushRequest(msg, 'view'))
  const shareCh = useDataChannel('share-permission', (msg) => pushRequest(msg, 'share'))
  const grantedCh = useDataChannel('share-granted', (msg) => {
    // o'quvchiga: ruxsat berildi — endi pastdagi share tugmasi ochiladi
    if (isTeacher) return
    try {
      const data = JSON.parse(dec.decode(msg.payload))
      if (data.identity === localParticipant?.identity) setSentShare('granted')
    } catch { /* e'tiborsiz */ }
  })

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  function askView() {
    viewCh.send(enc.encode(JSON.stringify({ name: userName })), { reliable: true })
    setSentView(true)
    setTimeout(() => setSentView(false), 30_000)
  }

  function askShare() {
    shareCh.send(enc.encode(JSON.stringify({ name: userName })), { reliable: true })
    setSentShare(true)
    setTimeout(() => setSentShare((v) => (v === 'granted' ? v : false)), 30_000)
  }

  async function approve(req) {
    setRequests((prev) => prev.filter((r) => r.id !== req.id))
    if (req.type === 'view') {
      try { await localParticipant.setScreenShareEnabled(true) } catch { /* bekor qilindi */ }
      return
    }
    // share ruxsati — backend LiveKit'da jonli ochadi
    try {
      await api.post('/live/allow-share/', { lesson_id: lessonId, identity: req.identity })
      grantedCh.send(enc.encode(JSON.stringify({ identity: req.identity })), { reliable: true })
    } catch { /* xatoda o'quvchi qayta so'raydi */ }
  }

  return (
    <>
      <div className="room-topbar">
        <span className="live-dot" />
        <span className="room-topbar-title">{title}</span>
        <span className="room-topbar-timer">{fmtElapsed(elapsed)}</span>
        <span className="room-topbar-count">👥 {participants.length}</span>
        {!isTeacher && (
          <>
            <button className="room-ask-btn" onClick={askView} disabled={!!sentView}>
              {sentView ? '✓ Yuborildi' : "👨‍🏫 Ekran so'rash"}
            </button>
            <button
              className="room-ask-btn"
              onClick={askShare}
              disabled={!!sentShare}
              title="O'z ekraningizni ko'rsatish uchun o'qituvchidan ruxsat so'rang"
            >
              {sentShare === 'granted' ? '✓ Ruxsat berildi' : sentShare ? '✓ Yuborildi' : '🖥 Mening ekranim'}
            </button>
          </>
        )}
      </div>
      {isTeacher && requests.length > 0 && (
        <div className="screen-request-stack">
          {requests.map((r) => (
            <div key={r.id} className="screen-request-toast">
              <span className="msg">
                {r.type === 'view'
                  ? <><b>{r.name}</b> ekraningizni ko'rishni so'rayapti</>
                  : <><b>{r.name}</b> o'z ekranini ulashishga ruxsat so'rayapti</>}
              </span>
              <div className="row">
                <button className="ok" onClick={() => approve(r)}>
                  {r.type === 'view' ? 'Ekranni ulashish' : 'Ruxsat berish'}
                </button>
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

/** O'quvchi uchun "Siz shu yerdamisiz?" — server jadvali bo'yicha, 15 soniya. */
function AttentionGuard({ lessonId }) {
  const [check, setCheck] = useState(null)

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const { data } = await api.get('/live/attention/', { params: { lesson_id: lessonId } })
        if (data.check) {
          setCheck((prev) => (prev?.id === data.check.id ? prev : data.check))
        }
      } catch { /* tarmoq — keyingi poll */ }
    }, 5000)
    return () => clearInterval(t)
  }, [lessonId])

  useEffect(() => {
    if (!check) return undefined
    const t = setTimeout(() => setCheck(null), 15_000) // 15s — o'zi yo'qoladi
    return () => clearTimeout(t)
  }, [check])

  async function answer() {
    try { await api.post('/live/attention/', { check_id: check.id }) } catch { /* kech qoldi */ }
    setCheck(null)
  }

  if (!check) return null
  return (
    <div className="attention-overlay">
      <div className="attention-card">
        <div className="emoji">👀</div>
        <b>Siz shu yerdamisiz?</b>
        <p>15 soniya ichida tasdiqlang — aks holda o'tkazib yuborilgan hisoblanadi.</p>
        <button onClick={answer}>✋ Shu yerdaman!</button>
      </div>
    </div>
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

  // Anti-cheat jurnali: o'quvchi dars oynasidan chiqib-kirishlari yoziladi
  useEffect(() => {
    if (user.role !== 'student' || !choices) return undefined
    const onVisibility = () => {
      api.post('/live/focus/', {
        lesson_id: lessonId,
        kind: document.hidden ? 'exit' : 'return',
      }).catch(() => { /* jurnal — jimgina */ })
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [user.role, choices, lessonId])

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
          lessonId={lessonId}
        />
        {user.role === 'student' && <AttentionGuard lessonId={lessonId} />}
        <VideoConference />
      </LiveKitRoom>
    </div>
  )
}
