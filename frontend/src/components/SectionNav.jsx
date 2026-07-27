import { useSearchParams } from 'react-router-dom'

// Tab holati URL (?tab=...) bilan sinxron — orqaga tugmasi va sahifa yangilashda saqlanadi
export function useSectionTab(defaultKey = 'home') {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || defaultKey
  const setTab = (t) => setParams(t === defaultKey ? {} : { tab: t }, { replace: true })
  return [tab, setTab]
}

export default function SectionNav({ tabs, current, onChange }) {
  return (
    <nav className="section-nav">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          className={current === t.key ? 'active' : ''}
          onClick={() => onChange(t.key)}
        >
          <span className="ico">{t.icon}</span>
          {t.label}
          {t.count > 0 && <span className="n">{t.count}</span>}
        </button>
      ))}
    </nav>
  )
}
