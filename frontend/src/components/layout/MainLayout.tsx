import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

interface MainLayoutProps {
  title: string;
  /** Colored page icon shown next to the title (lucide icon element). */
  icon?: ReactNode;
  /** Tailwind classes for the icon tile, e.g. "bg-emerald-500/15 text-emerald-400". */
  iconClass?: string;
  subtitle?: string;
  children: ReactNode;
}

export function MainLayout({ title, icon, iconClass, subtitle, children }: MainLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title={title} icon={icon} iconClass={iconClass} subtitle={subtitle} />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
