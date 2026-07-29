// Doska (EduTech.docx: Zoom whiteboard uslubi) — lenta formatida sheet'lar
// (tepadan pastga), sichqoncha bilan chizish, o'chirishga sabab majburiy.
// ƒ𝑥 rejimi: doskaning istalgan joyiga bosib TO'G'RIDAN-TO'G'RI matn/formula
// yoziladi (Photomath klaviaturasi pastda panel bo'lib turadi, javob berilmaydi).
// Sync: 2.5s polling. Faqat platforma ichida ko'rinadi (auth talab qilinadi).
import {
  forwardRef, useCallback, useEffect, useImperativeHandle,
  useLayoutEffect, useRef, useState,
} from 'react'

import api, { errMessage } from '../api/client'
import MathKeyboard, { MATH_TEMPLATES } from './MathKeyboard'

const COLORS = ['#1c1e3a', '#e03131', '#1a9f6c', '#2b6be4', '#f59f00']
const W = 1600
const H = 900
const TEXT_SIZE = 22 // doska birligida — canvas'dagi render bilan bir xil
const LINE = TEXT_SIZE * 1.3 // bir qator balandligi (canvas render bilan bir xil)
const MARGIN_X = 48  // yozuv doim qator boshidan — daftar chetidagi hoshiya
const MARGIN_Y = 30  // birinchi qatorning tepadan joyi

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

// Doskaning USTIDA turgan matn kiritish maydoni — yozilayotgan matn xuddi
// canvas'da chiziladigan joy va o'lchamda ko'rinadi. Klaviatura paneli bu
// blokni ref orqali boshqaradi (insert/backspace/move/undo).
const InlineMathEditor = forwardRef(function InlineMathEditor(
  { x, y, scale, color, onSave, onCancel }, ref,
) {
  const [text, setText] = useState('')
  const taRef = useRef(null)
  const textRef = useRef('')  // joriy matn — bir tick ichida bir necha tugma bosilsa ham dolzarb
  const caretRef = useRef(0)  // joriy kursor o'rni — DOM emas, shu manba ishlatiladi
  const histRef = useRef([])

  // Kursor faqat DOM yangilangach o'rnatilishi shart — aks holda controlled
  // textarea qiymati almashganda kursor boshiga sakraydi
  useLayoutEffect(() => {
    const el = taRef.current
    if (!el) return
    el.focus()
    el.setSelectionRange(caretRef.current, caretRef.current)
  }, [text])

  function mutate(next, caret) {
    histRef.current.push(textRef.current)
    if (histRef.current.length > 100) histRef.current.shift()
    textRef.current = next
    caretRef.current = caret
    setText(next)
  }

  useImperativeHandle(ref, () => ({
    insert(tok, back = 0) {
      const cur = textRef.current
      const start = Math.min(caretRef.current, cur.length)
      mutate(cur.slice(0, start) + tok + cur.slice(start), start + tok.length - back)
    },
    backspace() {
      const cur = textRef.current
      const start = Math.min(caretRef.current, cur.length)
      if (start === 0) return
      mutate(cur.slice(0, start - 1) + cur.slice(start), start - 1)
    },
    move(dir) {
      const p = Math.max(0, Math.min(textRef.current.length, caretRef.current + dir))
      caretRef.current = p
      const el = taRef.current
      if (el) { el.focus(); el.setSelectionRange(p, p) }
    },
    undo() {
      const prev = histRef.current.pop()
      if (prev === undefined) return
      textRef.current = prev
      caretRef.current = prev.length
      setText(prev)
    },
    save() {
      if (textRef.current.trim()) onSave(textRef.current)
      else onCancel()
    },
  }), [onSave, onCancel])

  // Telefonda canvas kichik — shrift 6-7px bo'lib o'qib bo'lmay qoladi.
  // Yozish payti kamida 14px ko'rsatamiz (doskaga baribir TEXT_SIZE da tushadi).
  const fontPx = Math.max(TEXT_SIZE * scale, 14)
  return (
    <textarea
      ref={taRef}
      className="board-inline-editor"
      style={{
        left: `${(x / W) * 100}%`,
        top: `${(y / H) * 100}%`,
        width: `${(1 - x / W) * 100}%`,
        fontSize: `${fontPx}px`,
        color,
      }}
      rows={text.split('\n').length}
      value={text}
      onChange={(e) => {
        histRef.current.push(textRef.current)
        textRef.current = e.target.value
        caretRef.current = e.target.selectionStart
        setText(e.target.value)
      }}
      onSelect={(e) => { caretRef.current = e.target.selectionStart }}
      onKeyDown={(e) => { if (e.key === 'Escape') onCancel() }}
      spellCheck={false}
      autoFocus
    />
  )
})

function SheetCanvas({
  sheet, canDraw, tool, color, width,
  onStroke, onErase, mathEdit, editorRef, onMathStart, onMathSave, onMathCancel,
}) {
  const ref = useRef(null)
  const liveRef = useRef(null) // chizilayotgan stroke

  useEffect(() => {
    if (ref.current) drawStrokes(ref.current, sheet.strokes, liveRef.current)
  }, [sheet.strokes])

  const toBoard = (e) => {
    const r = ref.current.getBoundingClientRect()
    return [((e.clientX - r.left) / r.width) * W, ((e.clientY - r.top) / r.height) * H]
  }

  // ƒ𝑥 joylashtirish "click"da — telefonda doskani barmoq bilan surish (pan)
  // tasodifan matn bloki ochib yubormasin (scroll'dan keyin click kelmaydi)
  function clickMath(e) {
    if (!canDraw || tool !== 'math') return
    const [x, y] = toBoard(e)
    const r = ref.current.getBoundingClientRect()
    onMathStart(sheet.index, x, y, r.width / W)
  }

  function down(e) {
    if (!canDraw) return
    if (tool === 'math') return // joylashtirish clickMath'da
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

  const cursorCls = tool === 'erase' ? 'erasing' : tool === 'math' ? 'texting' : 'drawing'
  return (
    <div className="board-sheet">
      <div className="board-sheet-label">Sheet {sheet.index + 1}</div>
      <div className="board-canvas-wrap">
        <canvas
          ref={ref}
          width={1120}
          height={630}
          className={canDraw ? cursorCls : ''}
          onClick={clickMath}
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onPointerLeave={up}
        />
        {mathEdit && (
          <InlineMathEditor
            ref={editorRef}
            x={mathEdit.x}
            y={mathEdit.y}
            scale={mathEdit.scale}
            color={color}
            onSave={onMathSave}
            onCancel={onMathCancel}
          />
        )}
      </div>
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
  // ƒ𝑥 rejimi: doskadagi aktiv matn bloki (bo'lmasa null)
  const [mathEdit, setMathEdit] = useState(null) // {sheetIndex, x, y, scale}
  const [showTemplates, setShowTemplates] = useState(false)
  const editorRef = useRef(null) // InlineMathEditor imperativ API

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
  const isMathSubject = /matem|algebra|geometr|fizik/i.test(board?.subject || '')

  // Rejim almashganda yozilayotgan matn yo'qolmasin — avval saqlaymiz
  function switchTool(next) {
    if (mathEdit) editorRef.current?.save()
    setTool(next)
  }

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

  function startMathEdit(sheetIndex, x, y, scale) {
    // boshqa joyga bosilsa — oldingi blok avval doskaga tushadi
    if (mathEdit) editorRef.current?.save()
    // Daftar uslubi: qayerga bosilmasin, yozuv o'sha QATORNING BOSHIDAN boshlanadi
    const row = Math.max(0, Math.round((y - MARGIN_Y) / LINE))
    setMathEdit({ sheetIndex, x: MARGIN_X, y: MARGIN_Y + row * LINE, scale })
    setShowTemplates(false)
  }

  function saveMathText(text) {
    const { sheetIndex, x, y } = mathEdit
    setMathEdit(null)
    if (!text.trim()) return
    sendStroke(sheetIndex, { type: 'text', text, x, y, size: TEXT_SIZE, color })
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
                  onClick={() => { setColor(c); switchTool('pen') }}
                />
              ))}
            </div>
            <button className={`board-tool ${tool === 'pen' ? 'on' : ''}`} onClick={() => switchTool('pen')}>✏️</button>
            <button
              className={`board-tool ${tool === 'erase' ? 'on' : ''}`}
              title="O'chirish (sabab so'raladi)"
              onClick={() => switchTool('erase')}
            >🧽</button>
            <select className="board-width" value={width} onChange={(e) => setWidth(Number(e.target.value))}>
              <option value={2}>Ingichka</option>
              <option value={4}>O'rta</option>
              <option value={8}>Yo'g'on</option>
            </select>
            {/* Fanga mos vosita: matematik rejim — doskaga bosib to'g'ridan-to'g'ri yozasiz */}
            {isMathSubject && (
              <button
                className={`board-tool formula ${tool === 'math' ? 'on' : ''}`}
                title="Matematik rejim — doskaga bosib yozasiz, o'zingiz yechasiz"
                onClick={() => switchTool(tool === 'math' ? 'pen' : 'math')}
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
            mathEdit={mathEdit?.sheetIndex === sheet.index ? mathEdit : null}
            editorRef={editorRef}
            onMathStart={startMathEdit}
            onMathSave={saveMathText}
            onMathCancel={() => setMathEdit(null)}
          />
        ))}
      </div>

      {/* ƒ𝑥 rejimida hali joy tanlanmagan — yo'l-yo'riq */}
      {tool === 'math' && !mathEdit && (
        <div className="board-math-hint">✍️ Doskaning istalgan joyiga bosing — o'sha yerga yozasiz</div>
      )}

      {/* Photomath klaviaturasi — matn bloki ochiq bo'lganda pastda turadi.
          onMouseDown preventDefault: tugma bosilganda doskadagi kursor o'chmasin */}
      {mathEdit && (
        <div className="board-mathbar" onMouseDown={(e) => e.preventDefault()}>
          <div className="mc-bar-actions">
            <button className="mc-templates-btn" onClick={() => setShowTemplates((v) => !v)}>📚</button>
            <span className="mc-hint">o'zingiz yechasiz — javob berilmaydi</span>
            <button className="mc-cancel" onClick={() => setMathEdit(null)}>✕ Bekor</button>
            <button className="mc-place" onClick={() => editorRef.current?.save()}>✓ Doskaga yozish</button>
          </div>
          {showTemplates && (
            <div className="mc-templates">
              {MATH_TEMPLATES.map((t) => (
                <button
                  key={t.name}
                  className="mc-template-row"
                  onClick={() => { editorRef.current?.insert(t.text); setShowTemplates(false) }}
                >
                  <b>{t.name}</b>
                  <span>{t.text.split('\n')[0]}</span>
                </button>
              ))}
            </div>
          )}
          <MathKeyboard api={editorRef} />
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
