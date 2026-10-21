import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
const ACCESS_TOKEN_KEY = 'supplier_access_token'
const REFRESH_TOKEN_KEY = 'supplier_refresh_token'
const AUTH_EXPIRED_EVENT = 'supplier-auth-expired'

export const tokenStorage = {
  getAccess: () => sessionStorage.getItem(ACCESS_TOKEN_KEY),
  getRefresh: () => sessionStorage.getItem(REFRESH_TOKEN_KEY),
  set(access, refresh) {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, access)
    if (refresh) sessionStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear() {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY)
    sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

export const api = axios.create({ baseURL: API_BASE_URL })

api.interceptors.request.use((config) => {
  const access = tokenStorage.getAccess()
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

let refreshRequest

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const isAuthRequest = originalRequest?.url?.includes('/auth/token/')

    if (error.response?.status !== 401 || !originalRequest || originalRequest._retried || isAuthRequest) {
      return Promise.reject(error)
    }

    const refresh = tokenStorage.getRefresh()
    if (!refresh) {
      tokenStorage.clear()
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
      return Promise.reject(error)
    }

    originalRequest._retried = true
    try {
      refreshRequest ||= axios
        .post(`${API_BASE_URL}/auth/token/refresh/`, { refresh })
        .then(({ data }) => data)
        .finally(() => {
          refreshRequest = undefined
        })
      const tokens = await refreshRequest
      tokenStorage.set(tokens.access, tokens.refresh || refresh)
      originalRequest.headers.Authorization = `Bearer ${tokens.access}`
      return api(originalRequest)
    } catch (refreshError) {
      tokenStorage.clear()
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
      return Promise.reject(refreshError)
    }
  },
)

export function getErrorMessage(error) {
  const data = error.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data === 'object' && data !== null) {
    const firstError = Object.values(data).flat()[0]
    if (typeof firstError === 'string') return firstError
  }
  return 'Une erreur est survenue. Veuillez réessayer.'
}

export async function downloadFile(url, fallbackFilename) {
  let response
  try {
    response = await api.get(url, { responseType: 'blob' })
  } catch (error) {
    if (error.response?.data instanceof Blob) {
      const body = await error.response.data.text()
      try {
        error.response.data = JSON.parse(body)
      } catch {
        error.response.data = { detail: body || 'Le fichier n’a pas pu être généré.' }
      }
    }
    throw error
  }
  const disposition = response.headers['content-disposition'] || ''
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || fallbackFilename
  const objectUrl = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
  return filename
}
