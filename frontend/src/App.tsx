import { Route, Routes } from 'react-router-dom';
import { DashboardPage } from './pages/DashboardPage';
import { TestCasesPage } from './pages/TestCasesPage';
import { ExecutionPage } from './pages/ExecutionPage';
import { SchedulesPage } from './pages/SchedulesPage';
import { ConfigurationPage } from './pages/ConfigurationPage';
import { TemplateManagerPage } from './pages/TemplateManagerPage';
import { ReportsPage } from './pages/ReportsPage';
import { PluginsPage } from './pages/PluginsPage';
import { HelpPage } from './pages/HelpPage';
import { NotFoundPage } from './pages/NotFoundPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/test-cases" element={<TestCasesPage />} />
      <Route path="/execution" element={<ExecutionPage />} />
      <Route path="/execution/:executionId" element={<ExecutionPage />} />
      <Route path="/schedules" element={<SchedulesPage />} />
      <Route path="/configuration" element={<ConfigurationPage />} />
      <Route path="/templates" element={<TemplateManagerPage />} />
      <Route path="/reports" element={<ReportsPage />} />
      <Route path="/plugins" element={<PluginsPage />} />
      <Route path="/help" element={<HelpPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
