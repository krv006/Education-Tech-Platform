import '@livekit/components-styles'

import { LiveKitRoom, VideoConference } from '@livekit/components-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import api, { errMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function LessonRoom() {
  const { lessonId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [conn, setConn] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.post('/live/token/', { lesson_id: lessonId })
      .then((r) => setConn(r.data))
      .catch((err) => setError(errMessage(err)))
  }, [lessonId])

  async function onLeave() {
    if (user.role === 'student') {
      try { await api.post('/live/leave/', { lesson_id: lessonId }) } catch { /* davomat backend'da yopiladi */ }
    }
    navigate('/')
  }

  if (error) {
    return (
      <div className="stack">
        <div className="error-box">{error}</div>
        <button className="btn secondary sm" onClick={() => navigate('/')}>← Orqaga</button>
      </div>
    )
  }

  if (!conn) return <p className="muted">Xonaga ulanilmoqda…</p>

  return (
    <div className="room-wrap">
      <LiveKitRoom
        serverUrl={conn.url}
        token={conn.token}
        connect
        video={false}
        audio={false}
        onDisconnected={onLeave}
        data-lk-theme="default"
        style={{ height: '100%' }}
      >
        <VideoConference />
      </LiveKitRoom>
    </div>
  )
}
