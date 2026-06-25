import { ReactNode, useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { createProject, currentUser, setCurrentUser } from '../../services/api';
import { ThemeToggle } from './ThemeToggle';
import { FolderKanban, UserRound } from 'lucide-react';

interface HeaderProps {
  title: string;
  icon?: ReactNode;
  iconClass?: string;
  subtitle?: string;
}

export function Header({ title, icon, iconClass, subtitle }: HeaderProps) {
  const { projects, activeProjectId, setActiveProjectId, refreshProjects } = useProject();
  const [user, setUser] = useState(currentUser());

  const changeUser = () => {
    const name = window.prompt('Who is running tests? (recorded as "triggered by")', user);
    if (name === null) return;
    const next = name.trim() || 'admin';
    setCurrentUser(next);
    setUser(next);
  };

  const handleChange = async (value: string) => {
    if (value === '__new__') {
      const name = window.prompt('New project name:');
      if (!name?.trim()) return;
      try {
        const project = await createProject({ name: name.trim() });
        await refreshProjects();
        setActiveProjectId(project.id);
      } catch {
        window.alert('Could not create the project (name may already exist).');
      }
      return;
    }
    setActiveProjectId(Number(value));
  };

  return (
    <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3.5">
      <div className="flex items-center gap-3">
        {icon && (
          <span
            className={`flex h-9 w-9 items-center justify-center rounded-lg ${
              iconClass ?? 'bg-primary/15 text-primary'
            }`}
          >
            {icon}
          </span>
        )}
        <div>
          <h1 className="text-xl font-bold leading-tight">{title}</h1>
          {subtitle && <p className="text-xs text-text-muted">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5">
          <FolderKanban size={15} className="text-indigo-400" />
          <select
            className="max-w-[180px] bg-transparent pr-1 text-sm font-medium text-text-primary focus:outline-none"
            value={activeProjectId ?? ''}
            onChange={(event) => void handleChange(event.target.value)}
            aria-label="Active project"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
            <option value="__new__">＋ New project…</option>
          </select>
        </div>
        <button
          type="button"
          onClick={changeUser}
          title="Click to change who is recorded as triggering runs"
          className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-medium text-text-primary hover:border-primary/50"
        >
          <UserRound size={15} className="text-emerald-400" />
          <span className="max-w-[120px] truncate">{user}</span>
        </button>
        <ThemeToggle />
      </div>
    </header>
  );
}
