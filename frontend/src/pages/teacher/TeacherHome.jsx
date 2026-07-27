import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import api, { errMessage } from '../../api/client'

const STATUS_LABELS = {
  scheduled: ['Rejalashtirilgan', 'indigo'],
  live: ['Jonli', 'red'],
  finished: ['Tugagan', 'green'],
  cancelled: ['Bekor', 'amber'],
}

export default function TeacherHome() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState([])
  const [lessons, setLessons] = useState([])
  const [error, setError] = useState('')
  const [courseForm, setCourseForm] = useState({ title: '', subject: '' })
  const [lessonForm, setLessonForm] = useState({ course: '', title: '', starts_at: '', duration_min: 45 })

  async function load() {
    try {
      const [c, l] = await Promise.all([api.get('/courses/'), api.get('/lessons/')])
      setCourses(c.data.results)
      setLessons(l.data.results)
    } catch (err) {
      setError(errMessage(err))
    }
  }

  useEffect(() => { load() }, [])

  async function createCourse(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/courses/', courseForm)
      setCourseForm({ title: '', subject: '' })
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
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  async function finishLesson(id) {
    try {
      await api.post(`/lessons/${id}/finish/`)
      load()
    } catch (err) { setError(errMessage(err)) }
  }

  return (
    <div className="stack">
      <div className="page-head">
        <h2>O'qituvchi paneli</h2>
      </div>
      {error && <div className="error-box">{error}</div>}

      <div className="grid-2">
        <form className="card" onSubmit={createCourse}>
          <h3 style={{ marginBottom: 12, fontSize: 15 }}>Yangi kurs</h3>
          <div className="field">
            <label>Nomi</label>
            <input className="input" value={courseForm.title}
              onChange={(e) => setCourseForm({ ...courseForm, title: e.target.value })} required />
          </div>
          <div className="field">
            <label>Fan</label>
            <input className="input" value={courseForm.subject}
              onChange={(e) => setCourseForm({ ...courseForm, subject: e.target.value })} />
          </div>
          <button className="btn sm">Kurs yaratish</button>
        </form>

        <form className="card" onSubmit={createLesson}>
          <h3 style={{ marginBottom: 12, fontSize: 15 }}>Yangi dars</h3>
          <div className="field">
            <label>Kurs</label>
            <select className="input" value={lessonForm.course}
              onChange={(e) => setLessonForm({ ...lessonForm, course: e.target.value })} required>
              <option value="">Tanlang…</option>
              {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Mavzu</label>
            <input className="input" value={lessonForm.title}
              onChange={(e) => setLessonForm({ ...lessonForm, title: e.target.value })} required />
          </div>
          <div className="grid-2">
            <div className="field">
              <label>Boshlanish vaqti</label>
              <input className="input" type="datetime-local" value={lessonForm.starts_at}
                onChange={(e) => setLessonForm({ ...lessonForm, starts_at: e.target.value })} required />
            </div>
            <div className="field">
              <label>Davomiyligi (daq)</label>
              <input className="input" type="number" min="10" max="180" value={lessonForm.duration_min}
                onChange={(e) => setLessonForm({ ...lessonForm, duration_min: e.target.value })} />
            </div>
          </div>
          <button className="btn sm">Dars qo'shish</button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 12, fontSize: 15 }}>Darslar</h3>
        {lessons.length === 0 && <p className="muted" style={{ fontSize: 13 }}>Hali dars yo'q.</p>}
        {lessons.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>Mavzu</th><th>Kurs</th><th>Vaqt</th><th>Holat</th><th /></tr>
            </thead>
            <tbody>
              {lessons.map((l) => {
                const [label, color] = STATUS_LABELS[l.status] || [l.status, 'indigo']
                return (
                  <tr key={l.id}>
                    <td style={{ fontWeight: 600 }}>{l.title}</td>
                    <td className="muted">{l.course_title}</td>
                    <td className="muted">{new Date(l.starts_at).toLocaleString('uz')}</td>
                    <td><span className={`badge ${color}`}>{label}</span></td>
                    <td>
                      <div className="row" style={{ justifyContent: 'flex-end' }}>
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
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
