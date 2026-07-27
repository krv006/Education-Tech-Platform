import axios from 'axios'

// Dev'da vite proxy /api -> localhost:8000 ga yo'naltiradi (vite.config.js).
// Prod'da VITE_API_URL env orqali beriladi.
const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || '') + '/api/v1',
})

const ACCESS_KEY = 'fokus_access'
const REFRESH_KEY = 'fokus_refresh'

export const tokens = {
  get access() { return localStorage.getItem(ACCESS_KEY) },
  get refresh() { return localStorage.getItem(REFRESH_KEY) },
  set({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

api.interceptors.request.use((config) => {
  if (tokens.access) config.headers.Authorization = `Bearer ${tokens.access}`
  return config
})

// 401 -> bir marta refresh qilib qayta urinish
let refreshing = null
api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && tokens.refresh && !original._retried) {
      original._retried = true
      try {
        refreshing = refreshing || axios.post(
          (import.meta.env.VITE_API_URL || '') + '/api/v1/auth/token/refresh/',
          { refresh: tokens.refresh },
        )
        const { data } = await refreshing
        refreshing = null
        tokens.set({ access: data.access, refresh: data.refresh })
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch {
        refreshing = null
        tokens.clear()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

// Backend'ning yagona xato formatidan odam o'qiydigan xabar
export function errMessage(error) {
  return (
    error.response?.data?.error?.message ||
    error.message ||
    'Xatolik yuz berdi. Qayta urinib ko\'ring.'
  )
}

export default api
