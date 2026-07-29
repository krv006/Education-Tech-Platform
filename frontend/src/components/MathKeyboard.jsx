// Photomath uslubidagi matematik klaviatura PANELI (EduTech.docx).
// Modal emas — doskaning pastida turadi, belgilar to'g'ridan-to'g'ri doskadagi
// aktiv matn blokiga kiritiladi. Javob hisoblanmaydi — o'quvchi o'zi yechadi.
import { useState } from 'react'

// Ko'p ishlatiladigan maktab formulalari — kursor turgan joyga qo'yiladi
export const MATH_TEMPLATES = [
  { name: 'Kvadrat tenglama', text: 'a·x² + b·x + c = 0\nD = b² − 4ac\nx₁,₂ = (−b ± √D) / 2a' },
  { name: 'Vieta teoremasi', text: 'x₁ + x₂ = −b/a\nx₁ · x₂ = c/a' },
  { name: "Qisqa ko'paytirish", text: '(a+b)² = a² + 2ab + b²\n(a−b)² = a² − 2ab + b²\na² − b² = (a−b)(a+b)' },
  { name: 'Pifagor teoremasi', text: 'a² + b² = c²' },
  { name: 'Trigonometriya', text: 'sin²x + cos²x = 1\ntg x = sin x / cos x\nsin 2x = 2 sin x cos x' },
  { name: 'Aylana va doira', text: 'C = 2πr\nS = πr²' },
  { name: 'Foiz', text: 'a ning p% i = a · p / 100' },
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

// api — doskadagi aktiv matn blokining imperativ interfeysi (InlineMathEditor ref):
// { insert(tok, back), backspace(), move(dir), undo() }
export default function MathKeyboard({ api }) {
  const [tab, setTab] = useState('basic')
  const [abc, setAbc] = useState(false)
  const call = (fn) => api.current && fn(api.current)

  return (
    <>
      <div className="mc-ctrl">
        <button className={abc ? 'on' : ''} onClick={() => setAbc((v) => !v)}>abc</button>
        <button onClick={() => call((a) => a.undo())} title="Bekor qilish">↺</button>
        <button onClick={() => call((a) => a.move(-1))}>←</button>
        <button onClick={() => call((a) => a.move(1))}>→</button>
        <button onClick={() => call((a) => a.insert('\n'))} title="Yangi qator">↵</button>
        <button onClick={() => call((a) => a.backspace())} title="O'chirish">⌫</button>
      </div>

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

      <div className="mc-grid">
        {abc
          ? ABC_KEYS.map((k) => (
            <button key={k} onClick={() => call((a) => a.insert(k))}>{k}</button>
          ))
          : SIDE_SETS[tab].map((pair, row) => [
            ...pair.map((k) => (
              <button key={k.label} className="fn" onClick={() => call((a) => a.insert(k.tok, k.back || 0))}>
                {k.label}
              </button>
            )),
            ...MAIN_KEYS[row].map((k) => (
              <button key={k} onClick={() => call((a) => a.insert(k))}>{k}</button>
            )),
          ])}
      </div>
    </>
  )
}
