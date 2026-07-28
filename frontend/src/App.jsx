import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import Layout from './components/Layout'
import ChatPage from './pages/ChatPage'
import LessonRoom from './pages/LessonRoom'
import Login from './pages/Login'
import Register from './pages/Register'
import ParentHome from './pages/parent/ParentHome'
import StudentHome from './pages/student/StudentHome'
import TeacherHome from './pages/teacher/TeacherHome'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="auth-wrap muted">Yuklanmoqda…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function HomeByRole() {
  const { user } = useAuth()
  if (user.role === 'teacher') return <TeacherHome />
  if (user.role === 'parent') return <ParentHome />
  if (user.role === 'student') return <StudentHome />
  return <div className="card">Rol: {user.role} — bu panel hali tayyor emas.</div>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<HomeByRole />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="lessons/:lessonId/room" element={<LessonRoom />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
