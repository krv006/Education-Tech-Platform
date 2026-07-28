// Umumiy UI yordamchilari — sana/vaqt formatlash va sahifalangan API'ni yig'ish.
// Brauzerlarning 'uz' lokalida oy/hafta nomlari to'liq emas — qo'lda beramiz.
import api from '../api/client'

export const MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']
export const WEEKDAYS = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba']

export function fmtTime(d) {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function fmtLongDate(d) {
  return `${WEEKDAYS[d.getDay()]}, ${d.getDate()}-${MONTHS[d.getMonth()]}`
}

export function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

export function fmtWhen(iso) {
  const d = new Date(iso)
  const now = new Date()
  const tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1)
  const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1)
  const time = fmtTime(d)
  if (sameDay(d, now)) return { rel: `Bugun, ${time}`, abs: '' }
  if (sameDay(d, tomorrow)) return { rel: `Ertaga, ${time}`, abs: '' }
  if (sameDay(d, yesterday)) return { rel: `Kecha, ${time}`, abs: '' }
  return {
    rel: `${d.getDate()}-${MONTHS[d.getMonth()]}, ${WEEKDAYS[d.getDay()].slice(0, 4)}`,
    abs: time,
  }
}

export function greeting() {
  const h = new Date().getHours()
  if (h < 6) return 'Xayrli tun'
  if (h < 12) return 'Xayrli tong'
  if (h < 18) return 'Xayrli kun'
  return 'Xayrli kech'
}

export const LESSON_STATUS = {
  scheduled: { label: 'Rejalashtirilgan', badge: 'indigo', dot: 'indigo' },
  live: { label: 'Jonli', badge: 'red', dot: 'red' },
  finished: { label: 'Tugagan', badge: 'green', dot: 'green' },
  cancelled: { label: 'Bekor qilingan', badge: 'amber', dot: 'amber' },
}

// sahifalangan ro'yxatni oxirigacha yig'ib keladi (xavfsizlik uchun 10 sahifa cheklovi)
export async function fetchAll(path) {
  const items = []
  for (let page = 1; page <= 10; page++) {
    const { data } = await api.get(path, { params: { page } })
    items.push(...data.results)
    if (!data.next) break
  }
  return items
}
