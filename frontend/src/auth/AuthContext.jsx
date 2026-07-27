import { createContext, useContext, useEffect, useState } from 'react'

import api, { tokens } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!tokens.access) {
      setLoading(false)
      return
    }
    api.get('/auth/me/')
      .then((r) => setUser(r.data))
      .catch(() => tokens.clear())
      .finally(() => setLoading(false))
  }, [])

  async function login(username, password) {
    const { data } = await api.post('/auth/login/', { username, password })
    tokens.set(data)
    const me = await api.get('/auth/me/')
    setUser(me.data)
    return me.data
  }

  async function register(payload) {
    await api.post('/auth/register/', payload)
    return login(payload.username, payload.password)
  }

  function logout() {
    tokens.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
