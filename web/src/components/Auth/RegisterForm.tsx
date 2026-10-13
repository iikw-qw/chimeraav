/**
 * Форма регистрации с показом кода верификации Telegram.
 */

import { useState } from 'react'
import { motion } from 'framer-motion'
import { useAuthStore } from '../../store/authStore'
import { useNavigate, Link } from 'react-router-dom'
import { Copy, Check } from 'lucide-react'

export default function RegisterForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [telegram, setTelegram] = useState('')
  const [error, setError] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [copied, setCopied] = useState(false)
  const { register, isLoading } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const code = await register(email, password, telegram || undefined)
      setVerificationCode(code)
    } catch (err: any) {
      setError(err.message)
    }
  }

  const copyCode = () => {
    navigator.clipboard.writeText(`/verify ${verificationCode}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (verificationCode) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md card text-center"
      >
        <div className="w-16 h-16 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto mb-4">
          <Check className="text-green-600" size={32} />
        </div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Регистрация успешна!</h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">Для верификации Telegram отправьте боту команду:</p>

        <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-4 flex items-center justify-between mb-4">
          <code className="text-lg font-mono text-chimera-600 dark:text-chimera-400">
            /verify {verificationCode}
          </code>
          <button onClick={copyCode} className="p-2 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors">
            {copied ? <Check size={18} className="text-green-500" /> : <Copy size={18} />}
          </button>
        </div>

        <button onClick={() => navigate('/')} className="btn-primary w-full">
          Начать работу
        </button>
      </motion.div>
    )
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
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Регистрация</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">Создайте аккаунт Chimera</p>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-4">
        {error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="input-field" placeholder="your@email.com" required />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Пароль</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input-field" placeholder="Минимум 6 символов" required minLength={6} />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Telegram username <span className="text-gray-400">(опционально)</span></label>
          <input type="text" value={telegram} onChange={(e) => setTelegram(e.target.value)} className="input-field" placeholder="@username" />
        </div>

        <button type="submit" disabled={isLoading} className="btn-primary w-full">
          {isLoading ? 'Регистрация...' : 'Зарегистрироваться'}
        </button>

        <p className="text-center text-sm text-gray-500 dark:text-gray-400">
          Уже есть аккаунт?{' '}
          <Link to="/login" className="text-chimera-600 hover:text-chimera-700 font-medium">Войти</Link>
        </p>
      </form>
    </motion.div>
  )
}
