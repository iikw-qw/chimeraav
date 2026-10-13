/**
 * HTTP-клиент с JWT-авторизацией.
 * Использует axios, автоматически подставляет токен из localStorage.
 */

import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('chimera_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('chimera_token')
      localStorage.removeItem('chimera_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export { API_URL, WS_URL }
export default api
