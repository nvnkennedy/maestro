import { NavLink } from 'react-router-dom';
import {
  Gauge,
  Route,
  CarFront,
  CalendarClock,
  Wrench,
  FileBarChart2,
  FileCode2,
  Cpu,
  BookOpen,
} from 'lucide-react';
import { canLeave } from '../../utils/navGuard';
import { useApi } from '../../hooks/useApi';
import { getHealth } from '../../services/api';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: Gauge, color: 'text-sky-400' },
  { to: '/test-cases', label: 'Test Designer', icon: Route, color: 'text-amber-400' },
  { to: '/execution', label: 'Execution', icon: CarFront, color: 'text-emerald-400' },
  { to: '/schedules', label: 'Scheduler', icon: CalendarClock, color: 'text-violet-400' },
  { to: '/configuration', label: 'Configuration', icon: Wrench, color: 'text-orange-400' },
  { to: '/templates', label: 'Templates', icon: FileCode2, color: 'text-pink-400' },
  { to: '/reports', label: 'Reports', icon: FileBarChart2, color: 'text-rose-400' },
  { to: '/plugins', label: 'Plugins', icon: Cpu, color: 'text-cyan-400' },
  { to: '/help', label: 'Help & Readme', icon: BookOpen, color: 'text-teal-400' },
];

export function Sidebar() {
  const { data: health } = useApi(getHealth, []);
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-3 px-5 py-5">
        <img src="/maestro-logo.svg" alt="Maestro" className="h-10 w-10 drop-shadow" />
        <div>
          <div className="bg-gradient-to-r from-blue-500 to-sky-400 bg-clip-text text-lg font-extrabold leading-tight text-transparent">
            Maestro
          </div>
          <div className="text-[10px] uppercase tracking-widest text-text-muted">
            Automotive Testing
          </div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, color }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={(e) => {
              if (!canLeave()) e.preventDefault();
            }}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-primary/15 text-text-primary shadow-sm ring-1 ring-primary/30'
                  : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary'
              }`
            }
          >
            <Icon size={17} className={color} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 text-[11px] text-text-muted">
        Maestro v{health?.version ?? '…'}
      </div>
    </aside>
  );
}
