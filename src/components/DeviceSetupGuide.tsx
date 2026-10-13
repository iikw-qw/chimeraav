import React from 'react'
import { Smartphone, Usb, Shield, Download, CheckCircle } from 'lucide-react'
import { cn } from '../lib/cn'

interface Step {
  number: number
  title: string
  description: string
  status: 'pending' | 'done' | 'error'
}

interface DeviceSetupGuideProps {
  deviceConnected: boolean
  agentInstalled: boolean
  platformsDetected: string[]
  onCheckConnection: () => void
  onInstallAgent: () => void
  onDetectPlatforms: () => void
  onDismiss: () => void
}

export default function DeviceSetupGuide(props: DeviceSetupGuideProps) {
  const steps: Step[] = [
    {
      number: 1,
      title: 'Install drivers',
      description: 'Open Chimera Tool → Settings → Drivers → Install All. Restart PC after.',
      status: 'pending',
    },
    {
      number: 2,
      title: 'Enable Developer Mode on phone',
      description: 'Settings → About Phone → Tap "Build Number" 7 times.',
      status: 'pending',
    },
    {
      number: 3,
      title: 'Enable USB Debugging',
      description: 'Settings → Developer Options → Enable "USB Debugging".',
      status: 'pending',
    },
    {
      number: 4,
      title: 'Connect phone via USB',
      description: 'Use ORIGINAL cable. Set USB mode to "File Transfer / MTP". Tap "Allow" on the debugging prompt. Check "Always allow".',
      status: props.deviceConnected ? 'done' : 'pending',
    },
    {
      number: 5,
      title: 'Install Chimera Agent',
      description: 'Click "Install Agent" button below. Agent enables screen control and automation.',
      status: props.agentInstalled ? 'done' : 'pending',
    },
    {
      number: 6,
      title: 'Install social apps',
      description: 'Open Google Play Store on phone. Install: Instagram, TikTok, Threads. Log in to each app at least once.',
      status: props.platformsDetected.length > 0 ? 'done' : 'pending',
    },
  ]

  const allDone = props.deviceConnected && props.agentInstalled && props.platformsDetected.length > 0

  return (
    <div className="rounded-xl border border-[--line-1] bg-[--bg-1] p-6 max-w-2xl mx-auto">
      <h2 className="text-xl font-bold text-[--txt-1] mb-1 flex items-center gap-2">
        <Smartphone className="w-5 h-5" />
        Device Setup Guide
      </h2>
      <p className="text-[--txt-3] text-sm mb-6">
        Follow these steps to connect your Android device
      </p>

      <div className="space-y-4">
        {steps.map((step) => (
          <div
            key={step.number}
            className={cn(
              'flex items-start gap-3 p-3 rounded-lg',
              step.status === 'done'
                ? 'bg-emerald-500/10 border border-emerald-500/30'
                : 'bg-[--bg-2] border border-[--line-1]',
            )}
          >
            <div className={cn(
              'flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold',
              step.status === 'done'
                ? 'bg-emerald-600 text-white'
                : 'bg-[--bg-3] text-[--txt-3]',
            )}>
              {step.status === 'done' ? <CheckCircle className="w-4 h-4" /> : step.number}
            </div>
            <div>
              <h3 className="text-[--txt-1] font-medium text-sm">{step.title}</h3>
              <p className="text-[--txt-3] text-xs mt-0.5">{step.description}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          onClick={props.onCheckConnection}
          className="px-4 py-2 bg-[--blue] hover:opacity-90 text-white text-sm rounded-lg flex items-center gap-2"
        >
          <Usb className="w-4 h-4" />
          Check Connection
        </button>
        <button
          onClick={props.onInstallAgent}
          disabled={!props.deviceConnected}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-[--bg-3] disabled:text-[--txt-3] text-white text-sm rounded-lg flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          Install Agent
        </button>
        <button
          onClick={props.onDetectPlatforms}
          disabled={!props.deviceConnected}
          className="px-4 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-[--bg-3] disabled:text-[--txt-3] text-white text-sm rounded-lg flex items-center gap-2"
        >
          <Shield className="w-4 h-4" />
          Detect Platforms
        </button>
      </div>

      {allDone && (
        <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
          <div className="flex items-center gap-2 text-emerald-400 font-medium">
            <CheckCircle className="w-5 h-5" />
            Device ready! All systems operational.
          </div>
          <p className="text-emerald-300/70 text-sm mt-1">
            You can now use Warmup, Scheduler, and all other features.
          </p>
          <div className="mt-3 flex gap-3">
            <button
              onClick={props.onDismiss}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm rounded-lg"
            >
              Start Working
            </button>
          </div>
        </div>
      )}

      <div className="mt-6 border-t border-[--line-1] pt-4">
        <p className="text-[--txt-3] text-xs">
          Troubleshooting: Try a different USB cable (original Samsung cable recommended).
          Use USB 2.0 port instead of 3.0. Restart phone and PC if issues persist.
        </p>
      </div>
    </div>
  )
}
