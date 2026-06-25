import { Route } from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { TestCaseDesigner } from '../components/test-cases/TestCaseDesigner';

export function TestCasesPage() {
  return (
    <MainLayout
      title="Test Designer"
      subtitle="Build and wire up automotive test flows"
      icon={<Route size={18} />}
      iconClass="bg-amber-500/15 text-amber-400"
    >
      <TestCaseDesigner />
    </MainLayout>
  );
}
