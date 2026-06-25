import { useEffect } from 'react';
import { useLocalStorage } from './useLocalStorage';

export type Theme = 'dark' | 'light';

export function useTheme() {
  const [theme, setTheme] = useLocalStorage<Theme>('maestro-theme', 'light');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const toggle = () => setTheme(theme === 'dark' ? 'light' : 'dark');
  return { theme, setTheme, toggle };
}
