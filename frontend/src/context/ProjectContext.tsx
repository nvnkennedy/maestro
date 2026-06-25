import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from 'react';
import { listProjects } from '../services/api';
import type { Project } from '../types/domain';

interface ProjectContextValue {
  projects: Project[];
  activeProjectId: number | null;
  setActiveProjectId: (id: number) => void;
  refreshProjects: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextValue>({
  projects: [],
  activeProjectId: null,
  setActiveProjectId: () => {},
  refreshProjects: async () => {},
});

export const useProject = () => useContext(ProjectContext);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectIdState] = useState<number | null>(() => {
    const stored = window.localStorage.getItem('maestro-project');
    return stored ? Number(stored) : null;
  });

  const refreshProjects = async () => {
    const data = await listProjects();
    setProjects(data);
    if (data.length > 0 && !data.some((p) => p.id === activeProjectId)) {
      setActiveProjectIdState(data[0].id);
    }
  };

  useEffect(() => {
    void refreshProjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setActiveProjectId = (id: number) => {
    setActiveProjectIdState(id);
    window.localStorage.setItem('maestro-project', String(id));
  };

  return (
    <ProjectContext.Provider
      value={{ projects, activeProjectId, setActiveProjectId, refreshProjects }}
    >
      {children}
    </ProjectContext.Provider>
  );
}
