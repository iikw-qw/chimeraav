import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  FileText,
  Flame,
  FolderOpen,
  ImagePlus,
  LayoutDashboard,
  Layers,
  MessageCircle,
  Monitor,
  MousePointerClick,
  Pen,
  Share2,
  SlidersHorizontal,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '../../lib/cn'
import { useAppStore } from '../../stores/appStore'

interface NavEntry {
  path: string
  label: string
  Icon: LucideIcon
}

export const NAV_ITEMS: NavEntry[] = [
  { path: '/', label: 'Дашборд', Icon: LayoutDashboard },
  { path: '/phones', label: 'Телефоны', Icon: Monitor },
  { path: '/device-map', label: 'Карта устройств', Icon: Layers },
  { path: '/warmup', label: 'Прогрев', Icon: Flame },
  { path: '/messages', label: 'Сообщения', Icon: MessageCircle },
  { path: '/social', label: 'Соцсети', Icon: Share2 },
  { path: '/posts', label: 'Посты', Icon: ImagePlus },
  { path: '/accounts', label: 'Аккаунты', Icon: Users },
  { path: '/datasets', label: 'Датасеты', Icon: FolderOpen },
  { path: '/scheduler', label: 'Планировщик', Icon: CalendarClock },
  { path: '/captions', label: 'Подписи', Icon: Pen },
  { path: '/uniqueizer', label: 'Уникализатор', Icon: Sparkles },
  { path: '/autoclicker', label: 'Автокликер', Icon: MousePointerClick },
  { path: '/monitoring', label: 'Мониторинг', Icon: Activity },
  { path: '/logs', label: 'Логи', Icon: FileText },
  { path: '/settings', label: 'Настройки', Icon: SlidersHorizontal },
]

export function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed)
  const toggle = useAppStore((s) => s.toggleSidebar)
  const backendStatus = useAppStore((s) => s.backendStatus)
  const online = backendStatus === 'ready'

  return (
    <aside
      className={cn(
        'relative flex h-full shrink-0 flex-col border-r border-[--line-1] bg-[--bg-1] transition-[width] duration-200',
        collapsed ? 'w-14' : 'w-52',
      )}
    >
      <div className="flex h-12 items-center gap-3 px-3">
        <img
          src={new URL('../../assets/chimera-logo.png', import.meta.url).href}
          alt="Chimera"
          className="h-[22px] w-[22px] shrink-0 rounded-md object-cover"
        />
      </div>

      <button
        type="button"
        onClick={toggle}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="absolute right-2 top-4 flex h-5 w-5 items-center justify-center rounded-md border border-[--line-2] bg-[--bg-2] text-[--txt-2] hover:text-[--txt-1]"
      >
        {collapsed ? (
          <ChevronRight className="h-3 w-3" />
        ) : (
          <ChevronLeft className="h-3 w-3" />
        )}
      </button>

      <nav className="flex flex-1 flex-col gap-1 py-4">
        {NAV_ITEMS.map(({ path, label, Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className="no-drag"
            title={collapsed ? label : undefined}
          >
            {({ isActive }) => (
              <div
                className={cn(
                  'relative mx-2 flex h-10 items-center gap-3 rounded-lg px-3 transition-colors',
                  isActive
                    ? 'text-[--blue]'
                    : 'text-[--txt-2] hover:bg-[--bg-3] hover:text-[--txt-1]',
                )}
              >
                {isActive && (
                  <motion.span
                    layoutId="nav-indicator"
                    className="absolute inset-0 rounded-lg bg-[--blue-glow]"
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
                <Icon
                  className="relative z-10 h-[18px] w-[18px] shrink-0"
                  strokeWidth={1.5}
                />
                {!collapsed && (
                  <span className="relative z-10 truncate text-xs font-medium">
                    {label}
                  </span>
                )}
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      <div
        className={cn(
          'flex items-center gap-2 border-t border-[--line-1] px-3 py-3',
          collapsed && 'justify-center',
        )}
      >
        <span
          className={cn(
            'h-2 w-2 shrink-0 rounded-full',
            online ? 'bg-[--green]' : 'bg-[--red]',
          )}
        />
        {!collapsed && <span className="text-[10px] text-[--txt-3]">v9.0</span>}
      </div>
    </aside>
  )
}
