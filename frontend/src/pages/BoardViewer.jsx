// Dars doskasini keyin ko'rish (chat'dagi havoladan) — faqat o'qish + PDF.
// Faqat platforma ichida, autentifikatsiya bilan (EduTech.docx: share yo'q).
import { useNavigate, useParams } from 'react-router-dom'

import BoardPanel from '../components/BoardPanel'

export default function BoardViewer() {
  const { lessonId } = useParams()
  const navigate = useNavigate()
  return (
    <div className="board-page">
      <BoardPanel lessonId={lessonId} readOnly onClose={() => navigate(-1)} />
    </div>
  )
}
