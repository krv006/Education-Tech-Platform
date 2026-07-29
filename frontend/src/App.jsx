import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import Layout from './components/Layout'
import BoardViewer from './pages/BoardViewer'
import ChatPage from './pages/ChatPage'
import LessonRoom from './pages/LessonRoom'
import Login from './pages/Login'
import Register from './pages/Register'
import ParentHome from './pages/parent/ParentHome'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="auth-wrap muted">Yuklanmoqda…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function HomeByRole() {
  const { user } = useAuth()
  // Telegram + Zoom + EduTech bitta oqimda: asosiy ekran — chatlar (EduTech.docx)
  if (user.role === 'teacher' || user.role === 'student') return <ChatPage />
  if (user.role === 'parent') return <ParentHome />
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
        <Route path="boards/:lessonId" element={<BoardViewer />} />
        <Route path="lessons/:lessonId/room" element={<LessonRoom />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
