// Doska (EduTech.docx: Zoom whiteboard uslubi) — lenta formatida sheet'lar
// (tepadan pastga), sichqoncha bilan chizish, o'chirishga sabab majburiy.
// Sync: 2.5s polling. Faqat platforma ichida ko'rinadi (auth talab qilinadi).
import { useCallback, useEffect, useRef, useState } from 'react'

import api, { errMessage } from '../api/client'

const COLORS = ['#1c1e3a', '#e03131', '#1a9f6c', '#2b6be4', '#f59f00']
const W = 1600
const H = 900

function drawStrokes(canvas, strokes, live) {
  const ctx = canvas.getContext('2d')
  const s = canvas.width / W
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  const paint = (st) => {
    if (st.type === 'text') {
      // formula bloki — monospace, ko'p qatorli
      const size = (st.size || 24) * s
      ctx.fillStyle = st.color || '#1c1e3a'
      ctx.font = `${size}px Consolas, 'Courier New', monospace`
      ctx.textBaseline = 'top'
      String(st.text).split('\n').forEach((line, i) => {
        ctx.fillText(line, st.x * s, (st.y + i * (st.size || 24) * 1.3) * s)
      })
      return
    }
    const pts = st.points || []
    if (pts.length < 2) return
    ctx.strokeStyle = st.color || '#1c1e3a'
    ctx.lineWidth = Math.max(1, (st.width || 3) * s)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.beginPath()
    ctx.moveTo(pts[0][0] * s, pts[0][1] * s)
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0] * s, pts[i][1] * s)
    ctx.stroke()
  }
  strokes.forEach(paint)
  if (live) paint(live)
}

// nuqta-segment masofasi — eraser uchun stroke tanlash
function hitStroke(strokes, x, y) {
  const th = 14
  for (let i = strokes.length - 1; i >= 0; i--) {
    const st = strokes[i]
    if (st.type === 'text') {
      // matn bloki — taxminiy bounding box
      const lines = String(st.text).split('\n')
      const wBox = Math.max(...lines.map((l) => l.length)) * (st.size || 24) * 0.62
      const hBox = lines.length * (st.size || 24) * 1.3
      if (x >= st.x && x <= st.x + wBox && y >= st.y && y <= st.y + hBox) return st
      continue
    }
    const pts = strokes[i].points || []
    for (let j = 0; j < pts.length - 1; j++) {
      const [x1, y1] = pts[j]
      const [x2, y2] = pts[j + 1]
      const dx = x2 - x1
      const dy = y2 - y1
      const len2 = dx * dx + dy * dy || 1
      let t = ((x - x1) * dx + (y - y1) * dy) / len2
      t = Math.max(0, Math.min(1, t))
      const px = x1 + t * dx
      const py = y1 + t * dy
      if ((x - px) ** 2 + (y - py) ** 2 < th * th) return strokes[i]
    }
  }
  return null
}

function SheetCanvas({ sheet, canDraw, tool, color, width, onStroke, onErase }) {
  const ref = useRef(null)
  const liveRef = useRef(null) // chizilayotgan stroke

  useEffect(() => {
    if (ref.current) drawStrokes(ref.current, sheet.strokes, liveRef.current)
  }, [sheet.strokes])

  const toBoard = (e) => {
    const r = ref.current.getBoundingClientRect()
    return [((e.clientX - r.left) / r.width) * W, ((e.clientY - r.top) / r.height) * H]
  }

  function down(e) {
    if (!canDraw) return
    e.preventDefault()
    const [x, y] = toBoard(e)
    if (tool === 'erase') {
      const hit = hitStroke(sheet.strokes, x, y)
      if (hit) onErase(sheet.index, hit)
      return
    }
    liveRef.current = { points: [[x, y]], color, width }
    try { ref.current.setPointerCapture(e.pointerId) } catch { /* sun'iy event — muhim emas */ }
  }

  function move(e) {
    if (!liveRef.current) return
    const [x, y] = toBoard(e)
    const pts = liveRef.current.points
    const [lx, ly] = pts[pts.length - 1]
    if ((x - lx) ** 2 + (y - ly) ** 2 < 4) return
    pts.push([x, y])
    drawStrokes(ref.current, sheet.strokes, liveRef.current)
  }

  function up() {
    const live = liveRef.current
    liveRef.current = null
    if (live && live.points.length >= 2) onStroke(sheet.index, live)
  }

  return (
    <div className="board-sheet">
      <div className="board-sheet-label">Sheet {sheet.index + 1}</div>
      <canvas
        ref={ref}
        width={1120}
        height={630}
        className={canDraw ? (tool === 'erase' ? 'erasing' : 'drawing') : ''}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerLeave={up}
      />
    </div>
  )
}

export default function BoardPanel({ lessonId, onClose, readOnly = false, onRequestAccess, accessRequested }) {
  const [board, setBoard] = useState(null)
  const [tool, setTool] = useState('pen')
  const [color, setColor] = useState(COLORS[0])
  const [width, setWidth] = useState(4)
  const [error, setError] = useState('')
  const [eraseTarget, setEraseTarget] = useState(null) // {sheetIndex, stroke}
  const [eraseReason, setEraseReason] = useState('')
  // ƒ Formula (Photomath uslubi): yozasiz -> tizim yechadi -> doskaga qo'yiladi
  const [formulaOpen, setFormulaOpen] = useState(false)
  const [formulaExpr, setFormulaExpr] = useState('')
  const [solving, setSolving] = useState(false)
  const [solution, setSolution] = useState(null) // {pretty, result, steps}

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/board/${lessonId}/`)
      setBoard(data)
    } catch (e) { setError(errMessage(e)) }
  }, [lessonId])

  useEffect(() => {
    load()
    const t = setInterval(load, 2500)
    return () => clearInterval(t)
  }, [load])

  const canDraw = !readOnly && !!board?.can_draw

  async function sendStroke(sheetIndex, stroke) {
    // optimistik: darhol ko'rsatamiz
    setBoard((prev) => ({
      ...prev,
      sheets: prev.sheets.map((s) =>
        s.index === sheetIndex ? { ...s, strokes: [...s.strokes, stroke] } : s,
      ),
    }))
    try {
      await api.post(`/board/${lessonId}/stroke/`, { sheet: sheetIndex, stroke })
    } catch (e) { setError(errMessage(e)) }
  }

  async function confirmErase() {
    const { sheetIndex, stroke } = eraseTarget
    try {
      await api.post(`/board/${lessonId}/erase/`, {
        sheet: sheetIndex, stroke_ids: [stroke.id], reason: eraseReason,
      })
      setEraseTarget(null)
      setEraseReason('')
      load()
    } catch (e) { setError(errMessage(e)) }
  }

  async function addSheet() {
    try {
      await api.post(`/board/${lessonId}/sheet/`)
      load()
    } catch (e) { setError(errMessage(e)) }
  }

  async function solveFormula() {
    setSolving(true)
    setSolution(null)
    try {
      const { data } = await api.post(`/board/${lessonId}/solve/`, { expr: formulaExpr })
      setSolution(data)
    } catch (e) { setError(errMessage(e)) }
    setSolving(false)
  }

  async function placeFormula() {
    // formula + javob + qadamlar bitta blok bo'lib oxirgi sheet'ga tushadi
    const lines = [
      solution.pretty,
      '',
      `Javob: ${solution.result}`,
      ...solution.steps.map((s) => `• ${s}`),
    ]
    const sheet = board.sheets[board.sheets.length - 1]
    const existingTexts = sheet.strokes.filter((s) => s.type === 'text').length
    const el = {
      type: 'text',
      text: lines.join('\n'),
      x: 60,
      y: 50 + (existingTexts % 4) * 200,
      size: 22,
      color,
    }
    setFormulaOpen(false)
    setFormulaExpr('')
    setSolution(null)
    try {
      await api.post(`/board/${lessonId}/stroke/`, { sheet: sheet.index, stroke: el })
      load()
    } catch (e) { setError(errMessage(e)) }
  }

  async function downloadPdf() {
    try {
      const { data } = await api.get(`/board/${lessonId}/pdf/`, { responseType: 'blob' })
      const url = URL.createObjectURL(data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'doska.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch { setError("PDF hali yo'q — doska bo'sh bo'lishi mumkin.") }
  }

  if (!board) return <div className="board-loading">Doska yuklanmoqda…</div>

  return (
    <div className="board-panel">
      <div className="board-toolbar">
        <b>🖊 Doska</b>
        {canDraw && (
          <>
            <div className="board-colors">
              {COLORS.map((c) => (
                <button
                  key={c}
                  className={`board-color ${color === c && tool === 'pen' ? 'on' : ''}`}
                  style={{ background: c }}
                  onClick={() => { setColor(c); setTool('pen') }}
                />
              ))}
            </div>
            <button className={`board-tool ${tool === 'pen' ? 'on' : ''}`} onClick={() => setTool('pen')}>✏️</button>
            <button
              className={`board-tool ${tool === 'erase' ? 'on' : ''}`}
              title="O'chirish (sabab so'raladi)"
              onClick={() => setTool('erase')}
            >🧽</button>
            <select className="board-width" value={width} onChange={(e) => setWidth(Number(e.target.value))}>
              <option value={2}>Ingichka</option>
              <option value={4}>O'rta</option>
              <option value={8}>Yo'g'on</option>
            </select>
            {/* Fanga mos vosita: matematikada formula yechuvchi (EduTech.docx) */}
            {/matem|algebra|geometr|fizik/i.test(board.subject || '') && (
              <button
                className="board-tool formula"
                title="Formula yozing — tizim o'zi yechib doskaga qo'yadi"
                onClick={() => setFormulaOpen(true)}
              >ƒ𝑥</button>
            )}
          </>
        )}
        {!readOnly && board.is_teacher && (
          <button className="btn secondary sm" onClick={addSheet}>+ Sheet</button>
        )}
        {!readOnly && !board.is_teacher && !board.can_draw && onRequestAccess && (
          <button className="room-ask-btn dark" onClick={onRequestAccess} disabled={accessRequested}>
            {accessRequested ? "✓ So'rov yuborildi" : "✋ Chizish ruxsati"}
          </button>
        )}
        {readOnly && <button className="btn secondary sm" onClick={downloadPdf}>⬇ PDF</button>}
        <div className="spacer" />
        {onClose && <button className="board-close" onClick={onClose}>✕</button>}
      </div>
      {error && <div className="error-box" style={{ margin: '8px 12px' }}>{error}</div>}

      {/* Lenta: sheet'lar tepadan pastga (EduTech.docx) */}
      <div className="board-ribbon">
        {board.sheets.map((sheet) => (
          <SheetCanvas
            key={sheet.index}
            sheet={sheet}
            canDraw={canDraw}
            tool={tool}
            color={color}
            width={width}
            onStroke={sendStroke}
            onErase={(sheetIndex, stroke) => setEraseTarget({ sheetIndex, stroke })}
          />
        ))}
      </div>

      {/* ƒ Formula — yozasiz, tizim yechadi (Photomath uslubi) */}
      {formulaOpen && (
        <div className="chat-modal" onClick={() => setFormulaOpen(false)}>
          <div className="chat-modal-card formula-card" onClick={(e) => e.stopPropagation()}>
            <h3>ƒ𝑥 Formula yechish</h3>
            <p className="muted">
              Yozing: <code>x^2 - 5x + 6 = 0</code> yoki <code>(x^2-9)/(x-3)</code> — tizim
              o'zi yechadi va doskaga qo'yadi.
            </p>
            <div className="row">
              <input
                className="input"
                placeholder="Masalan: 2x^2 + 3x - 5 = 0"
                value={formulaExpr}
                onChange={(e) => { setFormulaExpr(e.target.value); setSolution(null) }}
                onKeyDown={(e) => { if (e.key === 'Enter' && formulaExpr.trim()) solveFormula() }}
                autoFocus
              />
              <button className="btn sm" disabled={!formulaExpr.trim() || solving} onClick={solveFormula}>
                {solving ? '…' : 'Yechish'}
              </button>
            </div>
            {solution && (
              <div className="formula-preview">
                <pre>{solution.pretty}</pre>
                <div className="answer">Javob: <b>{solution.result}</b></div>
                {solution.steps.length > 0 && (
                  <ul>
                    {solution.steps.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                )}
                <button className="btn sm" onClick={placeFormula}>📌 Doskaga qo'yish</button>
              </div>
            )}
            <button className="btn secondary sm" onClick={() => setFormulaOpen(false)}>Yopish</button>
          </div>
        </div>
      )}

      {/* O'chirish sababi — majburiy */}
      {eraseTarget && (
        <div className="chat-modal" onClick={() => setEraseTarget(null)}>
          <div className="chat-modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Chiziqni o'chirish</h3>
            <p className="muted">Sabab yozish majburiy — o'chirishlar jurnalda saqlanadi.</p>
            <input
              className="input"
              placeholder="Masalan: xato chizildi"
              value={eraseReason}
              onChange={(e) => setEraseReason(e.target.value)}
              autoFocus
            />
            <div className="row">
              <button className="btn sm" disabled={!eraseReason.trim()} onClick={confirmErase}>
                O'chirish
              </button>
              <button className="btn secondary sm" onClick={() => setEraseTarget(null)}>Bekor</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
