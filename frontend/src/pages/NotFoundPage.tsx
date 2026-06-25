import { Link } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';

export function NotFoundPage() {
  return (
    <MainLayout title="Not found">
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="text-6xl font-black text-primary">404</div>
        <p className="mt-2 text-text-secondary">This page does not exist.</p>
        <Link to="/" className="btn-primary mt-6">
          Back to dashboard
        </Link>
      </div>
    </MainLayout>
  );
}
