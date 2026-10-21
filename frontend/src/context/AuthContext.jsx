import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, getErrorMessage, tokenStorage } from '../api/client'
import { AuthContext } from './authContext'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [authError, setAuthError] = useState('')

  const clearSession = useCallback(() => {
    tokenStorage.clear()
    setUser(null)
  }, [])

  useEffect(() => {
    let active = true
    const handleExpired = () => {
      if (active) clearSession()
    }
    window.addEventListener('supplier-auth-expired', handleExpired)

    async function restoreSession() {
      try {
        if (tokenStorage.getAccess() || tokenStorage.getRefresh()) {
          const response = await api.get('/auth/me/')
          if (active) setUser(response.data)
        }
      } catch (error) {
        clearSession()
        if (error.response?.status !== 401 && active) {
          setAuthError('La session ne peut pas être vérifiée. Vérifiez la connexion au serveur.')
        }
      } finally {
        if (active) setIsLoading(false)
      }
    }

    restoreSession()
    return () => {
      active = false
      window.removeEventListener('supplier-auth-expired', handleExpired)
    }
  }, [clearSession])

  const login = useCallback(async (username, password) => {
    setAuthError('')
    try {
      const tokenResponse = await api.post('/auth/token/', { username, password })
      tokenStorage.set(tokenResponse.data.access, tokenResponse.data.refresh)
      const userResponse = await api.get('/auth/me/')
      setUser(userResponse.data)
      return userResponse.data
    } catch (error) {
      clearSession()
      setAuthError(getErrorMessage(error))
      throw error
    }
  }, [clearSession])

  const logout = useCallback(async () => {
    const refresh = tokenStorage.getRefresh()
    try {
      if (refresh) await api.post('/auth/token/blacklist/', { refresh })
      setAuthError('')
    } catch (error) {
      setAuthError(`Session fermée localement. ${getErrorMessage(error)}`)
    } finally {
      clearSession()
    }
  }, [clearSession])

  const value = useMemo(
    () => ({ user, isLoading, authError, setAuthError, login, logout }),
    [user, isLoading, authError, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
