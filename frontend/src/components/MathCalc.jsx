// Matematik doska — Photomath klaviaturasining kloni (EduTech.docx).
// MUHIM: tizim javobni CHIQARMAYDI — o'quvchi hamma qadamni o'zi yozib yechadi.
// Barcha matematik belgilar (kasr, √, daraja, trig, log, lim, ∫, Σ) default ichida.
// Yozilgan ish "Doskaga qo'yish" bilan blok bo'lib doskaga tushadi.
import { useLayoutEffect, useRef, useState } from 'react'

// Ko'p ishlatiladigan maktab formulalari — eslatma sifatida doskaga qo'yiladi
const TEMPLATES = [
  {
    name: 'Kvadrat tenglama',
    insert: 'ax² + bx + c = 0',
    pin: 'a·x² + b·x + c = 0\nD = b² − 4ac\nx₁,₂ = (−b ± √D) / 2a',
  },
  {
    name: 'Vieta teoremasi',
    pin: 'x₁ + x₂ = −b/a\nx₁ · x₂ = c/a',
  },
  {
    name: "Qisqa ko'paytirish",
    pin: '(a+b)² = a² + 2ab + b²\n(a−b)² = a² − 2ab + b²\na² − b² = (a−b)(a+b)',
  },
  {
    name: 'Pifagor teoremasi',
    insert: 'a² + b² = c²',
    pin: 'a² + b² = c²',
  },
  {
    name: 'Trigonometriya',
    pin: 'sin²x + cos²x = 1\ntg x = sin x / cos x\nsin 2x = 2 sin x cos x',
  },
  {
    name: 'Aylana va doira',
    pin: 'C = 2πr\nS = πr²',
  },
  {
    name: 'Foiz',
    insert: 'a · p / 100',
    pin: 'a ning p% i = a · p / 100',
  },
]

// Asosiy 4 ustun — Photomath'dagi kabi doim o'ng tomonda turadi
const MAIN_KEYS = [
  ['7', '8', '9', '÷'],
  ['4', '5', '6', '×'],
  ['1', '2', '3', '−'],
  ['0', '.', '=', '+'],
]

// Chap 2 ustun — tepadagi pill'lar bilan almashadi (har biri 4 qator × 2)
const SIDE_SETS = {
  basic: [
    [{ label: '(□)', tok: '()', back: 1 }, { label: '□ⁿ', tok: '^' }],
    [{ label: '□/□', tok: '()/()', back: 4 }, { label: '√□', tok: '√()', back: 1 }],
    [{ label: '□²', tok: '²' }, { label: 'x', tok: 'x' }],
    [{ label: 'π', tok: 'π' }, { label: '%', tok: '%' }],
  ],
  fx: [
    [{ label: 'f(x)', tok: 'f(x)' }, { label: 'log', tok: 'log()', back: 1 }],
    [{ label: 'ln', tok: 'ln()', back: 1 }, { label: 'lg', tok: 'lg()', back: 1 }],
    [{ label: 'eˣ', tok: 'e^' }, { label: '10ˣ', tok: '10^' }],
    [{ label: '|□|', tok: '||', back: 1 }, { label: 'x!', tok: '!' }],
  ],
  trig: [
    [{ label: 'sin', tok: 'sin()', back: 1 }, { label: 'cos', tok: 'cos()', back: 1 }],
    [{ label: 'tan', tok: 'tg()', back: 1 }, { label: 'cot', tok: 'ctg()', back: 1 }],
    [{ label: 'sin⁻¹', tok: 'arcsin()', back: 1 }, { label: 'cos⁻¹', tok: 'arccos()', back: 1 }],
    [{ label: '°', tok: '°' }, { label: 'θ', tok: 'θ' }],
  ],
  lim: [
    [{ label: 'lim', tok: 'lim(x→)', back: 1 }, { label: '→', tok: '→' }],
    [{ label: '∞', tok: '∞' }, { label: 'd/dx', tok: 'd/dx()', back: 1 }],
    [{ label: '∫', tok: '∫ dx', back: 3 }, { label: 'Σ', tok: 'Σ' }],
    [{ label: 'Π', tok: 'Π' }, { label: 'dx', tok: 'dx' }],
  ],
}

const TABS = [
  { id: 'basic', label: '± ×' },
  { id: 'fx', label: 'f(x) log ln' },
  { id: 'trig', label: 'sin cos tan' },
  { id: 'lim', label: 'lim dx ∫ Σ' },
]

// abc rejimi — harflar to'liq gridni egallaydi (6 ustun × 4 qator)
const ABC_KEYS = [
  'a', 'b', 'c', 'd', 'e', 'f',
  'g', 'h', 'k', 'm', 'n', 'p',
  'q', 'r', 's', 't', 'u', 'v',
  'x', 'y', 'z', ',', '(', ')',
]

export default function MathCalc({ onPlace, onClose }) {
  const [expr, setExpr] = useState('')
  const [tab, setTab] = useState('basic')
  const [abc, setAbc] = useState(false)
  const [showTemplates, setShowTemplates] = useState(false)
  const inputRef = useRef(null)
  const historyRef = useRef([]) // undo uchun oldingi holatlar
  const caretRef = useRef(0)   // React render'idan keyin tiklanadigan kursor o'rni

  // Kursor faqat DOM yangilangach o'rnatilishi shart — aks holda controlled
  // textarea qiymati almashganda kursor boshiga sakraydi
  useLayoutEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.focus()
    el.setSelectionRange(caretRef.current, caretRef.current)
  }, [expr])

  // Har bir o'zgarishdan oldin tarixga yozamiz (↺ uchun)
  function mutate(next, caret) {
    historyRef.current.push(expr)
    if (historyRef.current.length > 100) historyRef.current.shift()
    caretRef.current = caret
    setExpr(next)
  }

  function insert(tok, back = 0) {
    const el = inputRef.current
    const start = el?.selectionStart ?? expr.length
    const end = el?.selectionEnd ?? expr.length
    mutate(expr.slice(0, start) + tok + expr.slice(end), start + tok.length - back)
  }

  function backspace() {
    const el = inputRef.current
    const start = el?.selectionStart ?? expr.length
    const end = el?.selectionEnd ?? expr.length
    if (start === end && start === 0) return
    const from = start === end ? start - 1 : start
    mutate(expr.slice(0, from) + expr.slice(end), from)
  }

  function undo() {
    const prev = historyRef.current.pop()
    if (prev === undefined) return
    caretRef.current = prev.length
    setExpr(prev)
  }

  function moveCaret(dir) {
    const el = inputRef.current
    if (!el) return
    const p = Math.max(0, Math.min(expr.length, (el.selectionStart ?? 0) + dir))
    el.focus()
    el.setSelectionRange(p, p)
  }

  return (
    <div className="chat-modal" onClick={onClose}>
      <div className="mathcalc" onClick={(e) => e.stopPropagation()}>
        <div className="mc-head">
          <b>𝑓𝑥 Matematik doska</b>
          <span className="mc-hint">o'zingiz yechasiz — javob berilmaydi</span>
          <button className="mc-templates-btn" onClick={() => setShowTemplates((v) => !v)}>
            📚 Formulalar
          </button>
          <button className="board-close dark" onClick={onClose}>✕</button>
        </div>

        {/* Tayyor formulalar — eslatma; yechim emas */}
        {showTemplates && (
          <div className="mc-templates">
            {TEMPLATES.map((t) => (
              <div key={t.name} className="mc-template-row">
                <button
                  className="name"
                  title={t.insert ? "Kirish qatoriga qo'yish" : ''}
                  onClick={() => t.insert && (insert(t.insert), setShowTemplates(false))}
                >
                  <b>{t.name}</b>
                  <span>{t.pin.split('\n')[0]}</span>
                </button>
                <button className="pin" onClick={() => onPlace(`${t.name}:\n${t.pin}`)}>📌 Doskaga</button>
              </div>
            ))}
          </div>
        )}

        {/* Ish maydoni — o'quvchi qadamlarini shu yerga yozadi (har qator = bir qadam) */}
        <textarea
          ref={inputRef}
          className="mc-work"
          placeholder={'Masalan:\n9 − 3 ÷ (1/3) + 1\n= 9 − 9 + 1\n= 1'}
          value={expr}
          onChange={(e) => {
            historyRef.current.push(expr)
            caretRef.current = e.target.selectionStart
            setExpr(e.target.value)
          }}
          rows={4}
          autoFocus
        />

        {/* Boshqaruv qatori: abc, undo, strelkalar, yangi qator, o'chirish */}
        <div className="mc-ctrl">
          <button className={abc ? 'on' : ''} onClick={() => setAbc((v) => !v)}>abc</button>
          <button onClick={undo} title="Bekor qilish">↺</button>
          <button onClick={() => moveCaret(-1)}>←</button>
          <button onClick={() => moveCaret(1)}>→</button>
          <button onClick={() => insert('\n')} title="Yangi qadam">↵</button>
          <button onClick={backspace} title="O'chirish">⌫</button>
        </div>

        {/* Bo'lim pill'lari — Photomath'dagi kabi */}
        {!abc && (
          <div className="mc-tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={tab === t.id ? 'on' : ''}
                onClick={() => setTab(t.id)}
              >{t.label}</button>
            ))}
          </div>
        )}

        {/* Klaviatura: chapda funksiya tugmalari, o'ngda raqamlar */}
        <div className="mc-grid">
          {abc
            ? ABC_KEYS.map((k) => (
              <button key={k} onClick={() => insert(k)}>{k}</button>
            ))
            : SIDE_SETS[tab].map((pair, row) => [
              ...pair.map((k) => (
                <button key={k.label} className="fn" onClick={() => insert(k.tok, k.back || 0)}>
                  {k.label}
                </button>
              )),
              ...MAIN_KEYS[row].map((k) => (
                <button key={k} onClick={() => insert(k)}>{k}</button>
              )),
            ])}
        </div>

        <div className="mc-actions">
          <button className="btn secondary sm" onClick={() => mutate('', 0)}>
            C — tozalash
          </button>
          <button className="mc-place" disabled={!expr.trim()} onClick={() => onPlace(expr)}>
            📌 Doskaga qo'yish
          </button>
        </div>
      </div>
    </div>
  )
}
