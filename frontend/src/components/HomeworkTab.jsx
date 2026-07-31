// Uy vazifasi tabi — kurs guruh chatida (EduTech.docx + AI-home-checker).
// O'qituvchi: vazifa beradi, hamma topshiriqlar va AI natijalarini ko'radi.
// O'quvchi: fayl yuklaydi (PDF/rasm/DOCX, Speaking'da audio) — Gemini savolma-
// savol o'zbekcha tekshiradi. Natija: ball, baho, xatolar, tavsiyalar.
import { useCallback, useEffect, useRef, useState } from 'react'

import api, { errMessage } from '../api/client'

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp,.docx'
const ACCEPT_AUDIO = `${ACCEPT},.mp3,.wav,.m4a,.ogg`

const SKILLS = [
  ['', 'Oddiy fan (default)'],
  ['writing', 'Writing — yozma ish'],
  ['reading', 'Reading — o\'qib tushunish'],
  ['listening', 'Listening — tinglab tushunish'],
  ['speaking', 'Speaking — audio javob'],
]

function scoreColor(score) {
  if (score == null) return 'var(--muted)'
  if (score >= 90) return '#16a34a'
  if (score >= 70) return '#84cc16'
  if (score >= 50) return '#f59f00'
  return '#ef4444'
}

/** Bitta topshiriq natijasi — ball + savolma-savol tahlil + xulosa. */
function ResultCard({ sub }) {
  const [openQ, setOpenQ] = useState(null)
  const r = sub.result
  if (!r) return null
  return (
    <div className="hw-result">
      <div className="hw-score-row">
        <div className="hw-score" style={{ borderColor: scoreColor(r.overall_score) }}>
          <b>{Math.round(r.overall_score)}</b>
          <span>ball</span>
        </div>
        <div className="hw-score-info">
          <b style={{ color: scoreColor(r.overall_score) }}>{sub.grade || r.grade}</b>
          <span className="muted">{r.questions.length} ta savol tekshirildi</span>
        </div>
      </div>

      {r.questions.map((q, i) => (
        <div key={i} className="hw-q">
          <button className="hw-q-head" onClick={() => setOpenQ(openQ === i ? null : i)}>
            <span className="num">{q.question_number}</span>
            <span className="text">{q.question}</span>
            <b style={{ color: scoreColor(q.score) }}>{q.score}</b>
          </button>
          {openQ === i && (
            <div className="hw-q-body">
              <p><b>Sizning javobingiz:</b> {q.student_answer || '—'}</p>
              <p>{q.analysis}</p>
              {q.mistakes?.length > 0 && (
                <div className="hw-mistakes">
                  <b>Xatolar:</b>
                  <ul>{q.mistakes.map((m, j) => <li key={j}>{m}</li>)}</ul>
                </div>
              )}
              {q.correct_answer && <p><b>To'g'ri javob:</b> {q.correct_answer}</p>}
              {q.suggestions?.length > 0 && (
                <div className="hw-suggest">
                  <b>Tavsiyalar:</b>
                  <ul>{q.suggestions.map((s, j) => <li key={j}>{s}</li>)}</ul>
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      {r.summary && (
        <div className="hw-summary">
          {r.summary.strengths?.length > 0 && (
            <p>💪 <b>Kuchli tomonlar:</b> {r.summary.strengths.join('; ')}</p>
          )}
          {r.summary.weaknesses?.length > 0 && (
            <p>⚠️ <b>Zaif tomonlar:</b> {r.summary.weaknesses.join('; ')}</p>
          )}
          {r.summary.topics_to_review?.length > 0 && (
            <p>📖 <b>Takrorlash kerak:</b> {r.summary.topics_to_review.join('; ')}</p>
          )}
          {r.summary.recommendations?.length > 0 && (
            <p>🎯 <b>Tavsiyalar:</b> {r.summary.recommendations.join('; ')}</p>
          )}
        </div>
      )}
    </div>
  )
}

/** Status chip — checking holatida o'z-o'zidan yangilanadi (polling). */
function StatusChip({ status }) {
  if (status === 'checking') return <span className="hw-chip checking">⏳ Tekshirilmoqda…</span>
  if (status === 'done') return <span className="hw-chip done">✓ Tekshirildi</span>
  if (status === 'error') return <span className="hw-chip error">⚠ Xatolik</span>
  return null
}

/** O'quvchining bitta vazifa bo'yicha bo'limi: yuklash -> kutish -> natija. */
function StudentSubmitBox({ assignment, onChanged }) {
  const [sub, setSub] = useState(assignment.my_submission || null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  // AI tekshiruvi tugaguncha polling (4s)
  useEffect(() => {
    if (sub?.status !== 'checking') return undefined
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/homework/submissions/${sub.id}/`)
        setSub(data)
        if (data.status !== 'checking') onChanged?.()
      } catch { /* keyingi poll */ }
    }, 4000)
    return () => clearInterval(t)
  }, [sub?.id, sub?.status, onChanged])

  // Natija to'liq kerak (ro'yxatda result yo'q) — done bo'lsa olib kelamiz
  useEffect(() => {
    if (sub && sub.status === 'done' && !sub.result) {
      api.get(`/homework/submissions/${sub.id}/`).then((r) => setSub(r.data)).catch(() => {})
    }
  }, [sub])

  async function upload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await api.post(`/homework/assignments/${assignment.id}/submit/`, form)
      setSub(data)
      onChanged?.()
    } catch (err) { setError(errMessage(err)) }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const accept = assignment.skill_key === 'speaking' ? ACCEPT_AUDIO : ACCEPT
  return (
    <div className="hw-submit">
      {sub && (
        <div className="hw-sub-row">
          <span className="muted">📎 {sub.file_name}</span>
          <StatusChip status={sub.status} />
        </div>
      )}
      {sub?.status === 'error' && <div className="error-box">{sub.error}</div>}
      {error && <div className="error-box">{error}</div>}
      {sub?.status === 'done' && <ResultCard sub={sub} />}

      {sub?.status !== 'checking' && (
        <label className={`hw-upload ${uploading ? 'off' : ''}`}>
          {uploading ? '⏳ Yuklanmoqda…' : (sub ? '🔄 Qayta topshirish' : '📤 Vazifani topshirish')}
          <input
            ref={fileRef}
            type="file"
            accept={accept}
            onChange={upload}
            disabled={uploading}
            hidden
          />
        </label>
      )}
      <p className="hw-hint muted">
        {assignment.skill_key === 'speaking'
          ? 'Audio yozuv yuklang (mp3/wav/m4a/ogg) — AI tinglab baholaydi.'
          : 'Daftar sahifasi rasmi, PDF yoki Word fayl yuklang — AI savolma-savol tekshiradi.'}
      </p>
    </div>
  )
}

/** O'qituvchi: bitta topshiriqning natijasi (bosganda ochiladi). */
function TeacherSubmissionRow({ sub: initial }) {
  const [open, setOpen] = useState(false)
  const [sub, setSub] = useState(initial)

  useEffect(() => { setSub(initial) }, [initial])

  async function toggle() {
    if (!open && sub.status === 'done' && !sub.result) {
      try {
        const { data } = await api.get(`/homework/submissions/${sub.id}/`)
        setSub(data)
      } catch { /* ko'rsatilmasa ham ro'yxat qoladi */ }
    }
    setOpen((v) => !v)
  }

  async function recheck(e) {
    e.stopPropagation()
    try {
      const { data } = await api.post(`/homework/submissions/${sub.id}/recheck/`)
      setSub(data)
    } catch { /* keyin qayta */ }
  }

  return (
    <div className="hw-teacher-sub">
      <button className="hw-sub-row btn-plain" onClick={toggle}>
        <b>{sub.student_name}</b>
        <span className="muted">📎 {sub.file_name}</span>
        {sub.overall_score != null && (
          <b style={{ color: scoreColor(sub.overall_score) }}>{Math.round(sub.overall_score)}</b>
        )}
        <StatusChip status={sub.status} />
        <span className="hw-recheck" onClick={recheck} title="Qayta tekshirish">↺</span>
      </button>
      {open && sub.status === 'error' && <div className="error-box">{sub.error}</div>}
      {open && sub.status === 'done' && <ResultCard sub={sub} />}
    </div>
  )
}

export default function HomeworkTab({ courseId, isTeacher }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', skill_key: '', extra_instructions: '' })
  const [openId, setOpenId] = useState(null)

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/homework/assignments/', { params: { course: courseId } })
      setItems(data)
    } catch (e) { setError(errMessage(e)) }
  }, [courseId])

  useEffect(() => { load() }, [load])

  async function createAssignment(e) {
    e.preventDefault()
    try {
      await api.post('/homework/assignments/', { course_id: courseId, ...form })
      setForm({ title: '', description: '', skill_key: '', extra_instructions: '' })
      setShowForm(false)
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  if (items === null && !error) return <p className="muted" style={{ padding: 14 }}>Yuklanmoqda…</p>

  return (
    <div className="hw-tab">
      {error && <div className="error-box">{error}</div>}

      {isTeacher && (
        <>
          {!showForm && (
            <button className="btn sm hw-new" onClick={() => setShowForm(true)}>+ Vazifa berish</button>
          )}
          {showForm && (
            <form className="hw-form" onSubmit={createAssignment}>
              <input
                className="input"
                placeholder="Vazifa nomi (masalan: Kvadrat tenglamalar — 5 ta misol)"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                autoFocus
              />
              <textarea
                className="input"
                rows={2}
                placeholder="Tavsif (ixtiyoriy)"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
              <select
                className="input"
                value={form.skill_key}
                onChange={(e) => setForm({ ...form, skill_key: e.target.value })}
                title="Til fanlari uchun ko'nikma"
              >
                {SKILLS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
              </select>
              <input
                className="input"
                placeholder="AI'ga ko'rsatma (ixtiyoriy: '7-sinf darajasida bahola')"
                value={form.extra_instructions}
                onChange={(e) => setForm({ ...form, extra_instructions: e.target.value })}
              />
              <div className="row">
                <button className="btn sm" type="submit" disabled={!form.title.trim()}>Berish</button>
                <button className="btn secondary sm" type="button" onClick={() => setShowForm(false)}>Bekor</button>
              </div>
            </form>
          )}
        </>
      )}

      {items?.length === 0 && (
        <p className="muted" style={{ padding: 14 }}>
          {isTeacher ? "Hali vazifa berilmagan — birinchisini bering." : 'Hozircha vazifa yo\'q.'}
        </p>
      )}

      {items?.map((a) => (
        <div key={a.id} className="hw-card">
          <button
            className="hw-card-head btn-plain"
            onClick={() => setOpenId(openId === a.id ? null : a.id)}
          >
            <div className="hw-card-title">
              <b>📝 {a.title}</b>
              {a.description && <span className="muted">{a.description}</span>}
            </div>
            {isTeacher
              ? <span className="hw-chip">{a.submissions_count ?? 0} topshiriq</span>
              : (a.my_submission
                ? <StatusChip status={a.my_submission.status} />
                : <span className="hw-chip todo">Topshirilmagan</span>)}
          </button>

          {openId === a.id && (
            isTeacher
              ? <TeacherPanel assignmentId={a.id} />
              : <StudentSubmitBox assignment={a} onChanged={load} />
          )}
        </div>
      ))}
    </div>
  )
}

/** O'qituvchi: vazifa ochilganda topshiriqlar ro'yxati (2.5s yangilanadi emas — qo'lda). */
function TeacherPanel({ assignmentId }) {
  const [detail, setDetail] = useState(null)

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/homework/assignments/${assignmentId}/`)
      setDetail(data)
    } catch { setDetail({ submissions: [] }) }
  }, [assignmentId])

  useEffect(() => { load() }, [load])

  if (!detail) return <p className="muted" style={{ padding: '4px 12px' }}>Yuklanmoqda…</p>
  if (detail.submissions.length === 0) {
    return <p className="muted" style={{ padding: '4px 12px' }}>Hali hech kim topshirmagan.</p>
  }
  return (
    <div className="hw-teacher-list">
      {detail.submissions.map((s) => <TeacherSubmissionRow key={s.id} sub={s} />)}
      <button className="btn secondary sm" onClick={load}>↻ Yangilash</button>
    </div>
  )
}
