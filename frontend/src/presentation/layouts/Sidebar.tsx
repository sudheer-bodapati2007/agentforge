import clsx from 'clsx'
import {
  Activity,
  BookOpen,
  FlaskConical,
  FolderKanban,
  History,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
  Workflow,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useSystemStatus } from '@/application/use-cases/system'

interface NavItem {
  to: string
  label: string
  icon: ReactNode
  /** Sections that are not built yet are shown, labelled with their phase, but not navigable. */
  availableIn?: string
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: <LayoutDashboard />, end: true },
  { to: '/projects/new', label: 'New Project', icon: <Plus /> },
  { to: '/projects', label: 'Projects', icon: <FolderKanban />, end: true },
  { to: '/workflows', label: 'All Workflows', icon: <Workflow /> },
  { to: '/activity', label: 'Agent Activity', icon: <Activity /> },
  { to: '/knowledge', label: 'Knowledge Base', icon: <BookOpen /> },
  { to: '/evaluations', label: 'Evaluations', icon: <FlaskConical /> },
  { to: '/history', label: 'Execution History', icon: <History /> },
]

const ITEM = 'flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium [&_svg]:size-4 [&_svg]:shrink-0'

function Item({ item, collapsed, onNavigate }: { item: NavItem; collapsed: boolean; onNavigate?: () => void }) {
  if (item.availableIn) {
    return (
      <li>
        <span
          aria-disabled="true"
          title={`${item.label} — planned for phase ${item.availableIn.slice(1)}`}
          className={clsx(ITEM, 'cursor-not-allowed text-fg-subtle/70')}
        >
          {item.icon}
          {!collapsed && (
            <>
              <span className="flex-1 truncate">{item.label}</span>
              <span className="rounded border border-line px-1 font-mono text-[10px] text-fg-subtle">{item.availableIn}</span>
            </>
          )}
        </span>
      </li>
    )
  }
  return (
    <li>
      <NavLink
        to={item.to}
        end={item.end}
        title={collapsed ? item.label : undefined}
        onClick={onNavigate}
        className={({ isActive }) =>
          clsx(
            ITEM,
            'transition-colors',
            isActive
              ? 'bg-accent-soft text-fg shadow-[inset_2px_0_0_0_var(--color-accent)] [&_svg]:text-accent'
              : 'text-fg-muted hover:bg-hover hover:text-fg',
          )
        }
      >
        {item.icon}
        {!collapsed && <span className="truncate">{item.label}</span>}
      </NavLink>
    </li>
  )
}

interface SidebarProps {
  collapsed: boolean
  onToggleCollapsed: () => void
  onNavigate?: () => void
}

export function Sidebar({ collapsed, onToggleCollapsed, onNavigate }: SidebarProps) {
  const { data: status, isError } = useSystemStatus()

  return (
    <nav aria-label="Main" className="flex h-full flex-col border-r border-line bg-sidebar">
      <div className={clsx('flex h-14 items-center gap-2.5 border-b border-line', collapsed ? 'justify-center px-2' : 'px-4')}>
        <img src="/favicon.svg" alt="" className="size-7" />
        {!collapsed && <span className="text-[15px] font-semibold tracking-tight">AgentForge</span>}
      </div>

      <ul className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {NAV.map((item) => (
          <Item key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />
        ))}
      </ul>

      <div className="space-y-1 border-t border-line p-2">
        <ul>
          <Item item={{ to: '/settings', label: 'Settings', icon: <Settings /> }} collapsed={collapsed} onNavigate={onNavigate} />
        </ul>
        {!collapsed && (
          <div className="rounded-md border border-line bg-panel px-2.5 py-2 text-xs">
            <p className="text-fg-subtle">Model</p>
            <p className="truncate font-mono text-fg-muted">
              {isError ? 'API unreachable' : status ? (status.llm.model ?? 'Not configured') : '…'}
            </p>
          </div>
        )}
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="hidden h-8 w-full items-center justify-center gap-2 rounded-md text-xs text-fg-subtle hover:bg-hover hover:text-fg md:flex"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
        </button>
      </div>
    </nav>
  )
}
