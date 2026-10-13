import { useEffect, useRef, useState } from 'react'
import { CheckCircle, AlertTriangle, Loader2, Circle, Wrench, X, Flame, CalendarClock, BookOpen } from 'lucide-react'
import { Button } from './ui'
import { ManualSetupGuide } from './ManualSetupGuide'
import { api } from '../api/client'
import { useWebSocket } from '../utils/useWebSocket'
import { cn } from '../lib/cn'

interface StepData {
  step: number
  label: string
  percent: number
  status?: string
  instructions?: string[]
  platforms?: string[]
  tests?: Record<string, any>
  elapsed_ms?: number
}

interface Props {
  serial: string
  onComplete?: (result: any) => void
  onClose: () => void
}

const TEST_LABELS: Record<string, string> = {
  tap: 'Tap', swipe: 'Swipe', screenshot: 'Screenshot',
  uiautomator: 'UIAutomator', text_input: 'Text Input',
}

const STEP_TIMEOUT_MS = 30_000
const TOTAL_TIMEOUT_MS = 60_000

export function FixEverythingWizard({ serial, onComplete, onClose }: Props) {
  const [steps, setSteps] = useState<StepData[]>([])
  const [currentStep, setCurrentStep] = useState(0)
  const [percent, setPercent] = useState(0)
  const [complete, setComplete] = useState(false)
  const [cancelled, setCancelled] = useState(false)
  const [manualStep, setManualStep] = useState<StepData | null>(null)
  const [platforms, setPlatforms] = useState<string[]>([])
  const [testResults, setTestResults] = useState<Record<string, any> | null>(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [error, setError] = useState('')
  const [timedOut, setTimedOut] = useState(false)
  const [showManualGuide, setShowManualGuide] = useState(false)
  const [stepStalled, setStepStalled] = useState(false)
  const lastStepChangeRef = useRef(Date.now())
  const startTimeRef = useRef(Date.now())

  useWebSocket(`/api/ws/setup/${serial}`, (data: StepData) => {
    if (cancelled) return
    setCurrentStep(data.step)
    setPercent(data.percent)
    lastStepChangeRef.current = Date.now()
    setStepStalled(false)

    if (data.status === 'cancelled') {
      setCancelled(true)
      return
    }

    setSteps((prev) => {
      const existing = prev.findIndex((s) => s.step === data.step)
      if (existing >= 0) {
        const next = [...prev]
        next[existing] = data
        return next
      }
      return [...prev, data]
    })

    if (data.status === 'manual') {
      setManualStep(data)
    }
    if (data.status === 'error' && data.step === 1) {
      setError(data.label || 'Device not found')
    }
    if (data.tests) {
      setTestResults(data.tests)
    }
    if (data.elapsed_ms) {
      setElapsedMs(data.elapsed_ms)
    }
    if (data.percent === 100) {
      setPlatforms(data.platforms || [])
      setComplete(true)
    }
  })

  useEffect(() => {
    startTimeRef.current = Date.now()
    lastStepChangeRef.current = Date.now()
    api.post(`/api/v1/devices/${serial}/fix-everything`)
      .then((r) => onComplete?.(r.data))
      .catch((err) => setError(err?.message || 'Setup failed'))
  }, [serial])

  // Timeout watcher
  useEffect(() => {
    if (complete || cancelled || timedOut) return
    const interval = setInterval(() => {
      const now = Date.now()
      if (now - lastStepChangeRef.current > STEP_TIMEOUT_MS) {
        setStepStalled(true)
      }
      if (now - startTimeRef.current > TOTAL_TIMEOUT_MS) {
        setTimedOut(true)
        setError('Setup timed out. Please check USB connection and try again.')
        api.post(`/api/v1/devices/${serial}/cancel-setup`).catch(() => {})
        clearInterval(interval)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [complete, cancelled, timedOut, serial])

  const handleCancel = async () => {
    try {
      await api.post(`/api/v1/devices/${serial}/cancel-setup`)
    } catch {}
    setCancelled(true)
  }

  const handleRetry = () => {
    setCancelled(false)
    setTimedOut(false)
    setError('')
    setSteps([])
    setPercent(0)
    setComplete(false)
    setStepStalled(false)
    startTimeRef.current = Date.now()
    lastStepChangeRef.current = Date.now()
    api.post(`/api/v1/devices/${serial}/fix-everything`)
      .then((r) => onComplete?.(r.data))
      .catch((err) => setError(err?.message || 'Setup failed'))
  }

  const handleManualDone = () => {
    setManualStep(null)
    api.get(`/api/v1/devices/${serial}/platforms?force=true`).catch(() => {})
  }

  const stepIcon = (s: StepData) => {
    if (s.status === 'error') return <AlertTriangle className="h-4 w-4 text-red-400" />
    if (s.status === 'manual') return <AlertTriangle className="h-4 w-4 text-amber-400" />
    if (s.status === 'warning') return <AlertTriangle className="h-4 w-4 text-amber-400" />
    if (s.status === 'ok' || s.percent === 100) return <CheckCircle className="h-4 w-4 text-emerald-400" />
    if (s.step === currentStep) return <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
    return <Circle className="h-4 w-4 text-[--txt-3]" />
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-xl border border-[--line-1] bg-[--bg-1] shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-[--line-1] px-6 py-4">
          {complete ? (
            <CheckCircle className="h-6 w-6 text-emerald-400" />
          ) : (
            <Wrench className="h-6 w-6 text-blue-400" />
          )}
          <div>
            <h2 className="text-sm font-semibold text-[--txt-1]">
              {complete ? 'Device Ready!' : cancelled ? 'Setup Cancelled' : timedOut ? 'Setup Timed Out' : 'Setting Up Device'}
            </h2>
            <p className="text-xs text-[--txt-3]">{serial}</p>
          </div>
          {elapsedMs > 0 && (
            <span className="ml-auto rounded-full bg-[--bg-2] px-2 py-0.5 text-[10px] text-[--txt-3]">
              {(elapsedMs / 1000).toFixed(1)}s
            </span>
          )}
          <button type="button" onClick={onClose} className={cn('rounded-md p-1 text-[--txt-3] hover:bg-[--bg-2] hover:text-[--txt-1]', elapsedMs > 0 ? '' : 'ml-auto')}>
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[60vh] space-y-3 overflow-y-auto px-6 py-4">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-400">
              {error}
            </div>
          )}

          {/* Stalled warning */}
          {stepStalled && !complete && !cancelled && !timedOut && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-400">
              This is taking longer than expected...
            </div>
          )}

          {steps.map((s) => (
            <div key={s.step} className="flex items-start gap-3">
              <div className="mt-0.5">{stepIcon(s)}</div>
              <div className="flex-1">
                <div className="text-xs font-medium text-[--txt-1]">{s.label}</div>
                {s.instructions && s.step === manualStep?.step && (
                  <div className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                    <p className="mb-2 text-[10px] font-medium text-amber-400">On your phone:</p>
                    <ol className="list-inside list-decimal space-y-1 text-[10px] text-amber-300">
                      {s.instructions.map((inst, i) => (
                        <li key={i}>{inst}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Self-test results */}
          {testResults && (
            <div className="rounded-lg border border-[--line-1] bg-[--bg-2] p-3">
              <p className="mb-2 text-[10px] font-medium text-[--txt-3]">Self-Test Results</p>
              <div className="space-y-1">
                {Object.entries(testResults)
                  .filter(([k]) => !['summary', 'all_passed', 'screenshot_size'].includes(k))
                  .map(([key, val]) => (
                    <div key={key} className="flex items-center justify-between text-[10px]">
                      <span className="text-[--txt-2]">{TEST_LABELS[key] || key}</span>
                      <span className={val === 'ok' ? 'text-emerald-400' : 'text-red-400'}>
                        {val === 'ok' ? 'OK' : 'Fail'}
                        {key === 'screenshot' && val === 'ok' && testResults.screenshot_size
                          ? ` (${Math.round(testResults.screenshot_size / 1024)}KB)`
                          : ''}
                      </span>
                    </div>
                  ))}
                <div className="mt-1 border-t border-[--line-1] pt-1 text-[10px] font-medium text-[--txt-1]">
                  {testResults.summary}
                </div>
              </div>
            </div>
          )}

          {/* Progress bar */}
          {!cancelled && !timedOut && (
            <div className="pt-2">
              <div className="mb-1 flex justify-between text-[10px] text-[--txt-3]">
                <span>{percent}%</span>
                <span>{complete ? 'Complete' : 'Setting up...'}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/5">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-500',
                    complete ? 'bg-emerald-500' : 'bg-gradient-to-r from-blue-500 to-cyan-500',
                  )}
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          )}

          {/* Platforms found */}
          {complete && platforms.length > 0 && (
            <div className="rounded-lg bg-[--bg-2] p-3">
              <p className="mb-1 text-[10px] font-medium text-[--txt-3]">Installed Platforms</p>
              <div className="flex flex-wrap gap-1">
                {platforms.map((p) => (
                  <span key={p} className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-[--line-1] px-6 py-3">
          {(timedOut || cancelled) ? (
            <>
              <Button variant="secondary" size="sm" onClick={handleRetry}>
                Retry
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowManualGuide(true)}
                leftIcon={<BookOpen className="h-3.5 w-3.5" />}
              >
                Manual Setup
              </Button>
              <Button variant="primary" size="sm" onClick={onClose}>Close</Button>
            </>
          ) : manualStep && !complete ? (
            <>
              <Button variant="ghost" size="sm" onClick={handleCancel}>Cancel</Button>
              <Button variant="primary" size="sm" onClick={handleManualDone}>
                I've done step {manualStep.step}
              </Button>
            </>
          ) : complete ? (
            <>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { onClose(); window.location.hash = '#/warmup' }}
                leftIcon={<Flame className="h-3.5 w-3.5" />}
              >
                Start Warmup
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { onClose(); window.location.hash = '#/scheduler' }}
                leftIcon={<CalendarClock className="h-3.5 w-3.5" />}
              >
                Open Scheduler
              </Button>
              <Button variant="primary" size="sm" onClick={onClose}>Close</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={handleCancel}>Cancel</Button>
              {stepStalled && (
                <Button variant="secondary" size="sm" onClick={handleRetry}>Retry</Button>
              )}
            </>
          )}
        </div>
      </div>

      {showManualGuide && (
        <ManualSetupGuide serial={serial} onClose={() => setShowManualGuide(false)} />
      )}
    </div>
  )
}
