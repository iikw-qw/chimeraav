/**
 * Форма входа с анимацией.
 */

import { useState } from 'react'
import { motion } from 'framer-motion'
import { useAuthStore } from '../../store/authStore'
import { useNavigate, Link } from 'react-router-dom'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const { login, isLoading } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(email, password)
      navigate('/')
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="w-full max-w-md"
    >
      <div className="text-center mb-8">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 200, delay: 0.2 }}
          className="w-16 h-16 bg-gradient-to-br from-chimera-500 to-chimera-700 rounded-2xl flex items-center justify-center mx-auto mb-4"
        >
          <span className="text-white font-bold text-2xl">C</span>
        </motion.div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Chimera v5.0</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Войдите в систему</p>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4">
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm"
          >
            {error}
          </motion.div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input-field"
            placeholder="your@email.com"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Пароль</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input-field"
            placeholder="••••••••"
            required
          />
        </div>

        <button type="submit" disabled={isLoading} className="btn-primary w-full">
          {isLoading ? 'Вход...' : 'Войти'}
        </button>

        <p className="text-center text-sm text-gray-500 dark:text-gray-400">
          Нет аккаунта?{' '}
          <Link to="/register" className="text-chimera-600 hover:text-chimera-700 font-medium">
            Зарегистрироваться
          </Link>
        </p>
      </form>
    </motion.div>
  )
}
