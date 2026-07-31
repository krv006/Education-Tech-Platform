// Yengil rich-text editor (CKEditor uslubi) — tashqi kutubxonasiz.
// O'qituvchi vazifa matnini formatlab yozadi: qalin, kursiv, ro'yxat, sarlavha.
// HTML server tomonda sanitize qilinadi (apps/homework/services.sanitize_html).
import { useEffect, useRef } from 'react'

const TOOLS = [
  { cmd: 'bold', label: <b>B</b>, title: 'Qalin' },
  { cmd: 'italic', label: <i>I</i>, title: 'Kursiv' },
  { cmd: 'underline', label: <u>U</u>, title: 'Tagchiziq' },
  { cmd: 'strikeThrough', label: <s>S</s>, title: "O'chirilgan" },
  { cmd: 'formatBlock', arg: 'h3', label: 'H', title: 'Sarlavha' },
  { cmd: 'insertUnorderedList', label: '• —', title: "Ro'yxat" },
  { cmd: 'insertOrderedList', label: '1. —', title: "Raqamli ro'yxat" },
  { cmd: 'removeFormat', label: '⌫F', title: 'Formatni tozalash' },
]

export default function RichEditor({ value, onChange, placeholder }) {
  const ref = useRef(null)

  // Tashqi value o'zgarsa (masalan forma tozalanganda) DOM'ni yangilaymiz —
  // lekin yozish paytida kursor sakramasligi uchun faqat farq bo'lsa
  useEffect(() => {
    const el = ref.current
    if (el && el.innerHTML !== (value || '')) el.innerHTML = value || ''
  }, [value])

  function exec(cmd, arg) {
    ref.current?.focus()
    document.execCommand(cmd, false, arg || undefined)
    onChange(ref.current?.innerHTML || '')
  }

  return (
    <div className="rte">
      {/* onMouseDown preventDefault — tugma bosilganda editor fokusi o'chmasin */}
      <div className="rte-toolbar" onMouseDown={(e) => e.preventDefault()}>
        {TOOLS.map((t) => (
          <button
            key={t.cmd + (t.arg || '')}
            type="button"
            title={t.title}
            onClick={() => exec(t.cmd, t.arg)}
          >{t.label}</button>
        ))}
      </div>
      <div
        ref={ref}
        className="rte-area"
        contentEditable
        suppressContentEditableWarning
        data-placeholder={placeholder || ''}
        onInput={() => onChange(ref.current?.innerHTML || '')}
      />
    </div>
  )
}
