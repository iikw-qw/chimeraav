import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Shield, Copy, Check, RefreshCw, Mail, Lock, AtSign, Key } from 'lucide-react'
import { api } from '../api/client'
import { Button } from '../components/ui'
import { toast } from '../hooks/useToast'

const APP_VERSION = '9.0'

interface AuthStatus {
  authorised: boolean
  install_id: string
  version: string
  bound_telegram: string | null
}

type AuthMode = 'code' | 'register' | 'login'

export function AuthGate({ onAuthorised }: { onAuthorised: () => void }) {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [code, setCode] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [issuing, setIssuing] = useState(false)
  const [mode, setMode] = useState<AuthMode>('code')
  const [checking, setChecking] = useState(true)
  const [hwId, setHwId] = useState('')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [telegram, setTelegram] = useState('')
  const [error, setError] = useState('')

  // On startup — check if device is already authorized
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const { data } = await api.post('/api/v1/auth/check')
        if (!alive) return
        if (data.authorized) {
          onAuthorised()
          return
        }
      } catch {}
      // Also check bot-based auth
      try {
        const { data } = await api.get<AuthStatus>('/api/auth/status', {
          params: { version: APP_VERSION },
        })
        if (!alive) return
        setStatus(data)
        if (data.authorised) {
          onAuthorised()
          return
        }
      } catch {}
      if (alive) setChecking(false)
    })()
    return () => { alive = false }
  }, [onAuthorised])

  // Get code — code-based flow
  const getCode = async () => {
    setIssuing(true)
    setError('')
    setCode(null)
    try {
      const { data } = await api.post('/api/v1/auth/get-code')
      if (data.already_authorized) {
        onAuthorised()
        return
      }
      if (data.code) {
        setCode(data.code)
        setHwId(data.hardware_id || '')
        // Poll every 3 seconds for bot confirmation
        const interval = setInterval(async () => {
          try {
            const { data: check } = await api.post('/api/v1/auth/check')
            if (check.authorized) {
              clearInterval(interval)
              onAuthorised()
            }
          } catch {}
        }, 3000)
        setTimeout(() => clearInterval(interval), 600000)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error')
    }
    setIssuing(false)
  }

  // Email/password auth
  const handleEmailAuth = async () => {
    if (!email || !password) return
    setIssuing(true)
    setError('')
    setCode(null)
    try {
      const endpoint = mode === 'register' ? '/api/v1/auth/register' : '/api/v1/auth/login'
      const body =
        mode === 'register'
          ? { email, password, telegram_username: telegram }
          : { email, password }
      const { data } = await api.post(endpoint, body)
      if (data.detail) {
        setError(data.detail)
        setIssuing(false)
        return
      }
      if (data.token) {
        localStorage.setItem('chtk', data.token)
      }
      if (data.verification_code) {
        setCode(data.verification_code)
      }
      if (data.token && !data.verification_code) {
        onAuthorised()
      }
    } catch {
      setError('Sidecar unavailable')
    } finally {
      setIssuing(false)
    }
  }

  const copyCode = async () => {
    if (!code) return
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center bg-[--bg-0]">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-[--txt-2] text-sm"
        >
          Checking device authorization...
        </motion.div>
      </div>
    )
  }

  return (
    <div className="flex h-screen items-center justify-center bg-[--bg-0]">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-[420px] rounded-2xl border border-[--line-1] bg-[--bg-1] p-7 shadow-[--shadow-card]"
      >
        <div className="flex items-center gap-3">
          <img
            src={new URL('../assets/chimera-logo.png', import.meta.url).href}
            alt="Chimera"
            className="h-10 w-10 rounded-xl object-cover"
          />
          <div>
            <div className="text-base font-semibold text-[--txt-1]">Chimera</div>
            <div className="text-xs text-[--txt-3]">
              {mode === 'code'
                ? 'Device authorization'
                : mode === 'register'
                  ? 'Create account + hardware binding'
                  : 'Sign in'}
            </div>
          </div>
        </div>

        {/* Mode tabs */}
        <div className="mt-5 flex gap-1 rounded-lg bg-[--bg-2] p-1">
          {(['code', 'register', 'login'] as AuthMode[]).map((m) => (
            <button
              key={m}
              onClick={() => {
                setMode(m)
                setCode(null)
                setError('')
              }}
              className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                mode === m
                  ? 'bg-[--bg-1] text-[--txt-1] shadow-sm'
                  : 'text-[--txt-3] hover:text-[--txt-2]'
              }`}
            >
              {m === 'code' ? 'Code' : m === 'register' ? 'Register' : 'Login'}
            </button>
          ))}
        </div>

        {/* Code-based auth */}
        {mode === 'code' && (
          <div className="mt-5">
            {!code ? (
              <>
                <p className="mb-4 text-sm leading-relaxed text-[--txt-2]">
                  Click the button to get a code.
                  <br />
                  Send it to the bot in Telegram.
                </p>
                <Button
                  className="w-full"
                  variant="primary"
                  loading={issuing}
                  leftIcon={<Key className="h-4 w-4" />}
                  onClick={getCode}
                >
                  Get code
                </Button>
              </>
            ) : (
              <>
                <div className="rounded-2xl border-2 border-emerald-500/40 bg-gradient-to-br from-emerald-900/40 to-emerald-800/20 p-5 text-center">
                  <div className="text-xs text-emerald-400">Your code:</div>
                  <div className="my-2 font-mono text-4xl font-extrabold tracking-[0.4em] text-[--txt-1]">
                    {code}
                  </div>
                  <div className="text-xs text-emerald-400">Send to bot:</div>
                  <code className="mt-1 inline-block rounded-lg bg-[--bg-0] px-4 py-2 text-sm text-[--txt-1]">
                    /verify {code}
                  </code>
                </div>
                <div className="mt-4 flex items-center justify-center gap-2">
                  <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
                  <span className="text-xs text-[--txt-3]">
                    Waiting for bot confirmation...
                  </span>
                </div>
                <div className="mt-3 flex justify-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={
                      copied ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )
                    }
                    onClick={copyCode}
                  >
                    {copied ? 'Copied' : 'Copy code'}
                  </Button>
                </div>
                {hwId && (
                  <div className="mt-2 text-center text-[10px] text-[--txt-3]">
                    HW: {hwId}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Email/password auth */}
        {(mode === 'register' || mode === 'login') && (
          <div className="mt-5 space-y-3">
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[--txt-3]" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                className="w-full rounded-lg border border-[--line-1] bg-[--bg-0] py-2.5 pl-10 pr-3 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[--txt-3]" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full rounded-lg border border-[--line-1] bg-[--bg-0] py-2.5 pl-10 pr-3 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
              />
            </div>
            {mode === 'register' && (
              <div className="relative">
                <AtSign className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[--txt-3]" />
                <input
                  type="text"
                  value={telegram}
                  onChange={(e) => setTelegram(e.target.value)}
                  placeholder="@telegram"
                  className="w-full rounded-lg border border-[--line-1] bg-[--bg-0] py-2.5 pl-10 pr-3 text-sm text-[--txt-1] outline-none focus:border-[--blue]"
                />
              </div>
            )}
            <Button
              className="w-full"
              variant="primary"
              loading={issuing}
              disabled={!email || !password}
              leftIcon={
                mode === 'register' ? (
                  <Shield className="h-4 w-4" />
                ) : (
                  <Lock className="h-4 w-4" />
                )
              }
              onClick={handleEmailAuth}
            >
              {mode === 'register' ? 'Get code' : 'Sign in'}
            </Button>

            {code && (
              <div className="flex items-center justify-between rounded-xl border-2 border-dashed border-emerald-500/40 bg-emerald-500/5 p-4">
                <div>
                  <div className="text-xs text-emerald-400">Code:</div>
                  <div className="font-mono text-3xl font-bold tracking-[0.4em] text-[--txt-1]">
                    {code}
                  </div>
                  <div className="mt-1 text-[10px] text-emerald-400">
                    Send to bot: /verify {code}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={
                    copied ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )
                  }
                  onClick={copyCode}
                >
                  {copied ? 'Copied' : 'Copy'}
                </Button>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-center text-xs text-red-400">
            {error}
          </div>
        )}

        {status && (
          <div className="mt-4 text-center text-[10px] text-[--txt-3]">
            install: <span className="font-mono">{status.install_id}</span> ·
            v{APP_VERSION}
          </div>
        )}
      </motion.div>
    </div>
  )
}
