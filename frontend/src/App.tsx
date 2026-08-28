import { Suspense, lazy, useState } from 'react';
import { BrowserRouter, NavLink, Outlet, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import { useQuery } from '@tanstack/react-query';
import { LayoutDashboard, ListChecks, Search, Tag, Upload, Layers, GitMerge } from 'lucide-react';
import { api } from '@/api/client';
import { useApiKey } from '@/hooks/useApiKey';
import { useOperatorId } from '@/hooks/useOperatorId';
import { cn } from '@/lib/utils';

const Dashboard = lazy(() => import('@/components/Dashboard'));
const ReviewQueue = lazy(() => import('@/components/ReviewQueue'));
const ReviewDetail = lazy(() => import('@/components/ReviewDetail'));
const ProductSearch = lazy(() => import('@/components/ProductSearch'));
const BrandManager = lazy(() => import('@/components/BrandManager'));
const CategoryManager = lazy(() => import('@/components/CategoryManager'));
const XlsxImport = lazy(() => import('@/components/XlsxImport'));
const DuplicatesReport = lazy(() => import('@/components/DuplicatesReport'));

function PageFallback() {
  return <div className="p-6 text-sm text-gray-500">Загрузка...</div>;
}

function Layout() {
  const { apiKey, setApiKey } = useApiKey();
  const { operatorId, setOperatorId } = useOperatorId();
  const [apiKeyDraft, setApiKeyDraft] = useState(apiKey);
  const [idDraft, setIdDraft] = useState(operatorId);

  const { data: stats } = useQuery({
    queryKey: ['stats/pipeline'],
    queryFn: () => api.get<{ review_queue_size: number }>('/stats/pipeline'),
    refetchInterval: 60_000,
  });

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Дашборд', exact: true },
    { to: '/review', icon: ListChecks, label: 'Ревью', badge: stats?.review_queue_size },
    { to: '/products', icon: Search, label: 'Товары' },
    { to: '/refs/brands', icon: Tag, label: 'Бренды' },
    { to: '/refs/categories', icon: Layers, label: 'Категории' },
    { to: '/import', icon: Upload, label: 'Импорт XLSX' },
    { to: '/duplicates', icon: GitMerge, label: 'Дубли' },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-52 bg-sidebar text-gray-100 flex flex-col flex-shrink-0">
        <div className="px-4 py-4 font-semibold text-white border-b border-slate-700">
          Product DB
        </div>
        <nav className="flex-1 py-2">
          {navItems.map(({ to, icon: Icon, label, badge, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors',
                  isActive
                    ? 'bg-slate-700 text-white'
                    : 'text-gray-300 hover:bg-slate-700 hover:text-white',
                )
              }
            >
              <Icon size={16} />
              <span className="flex-1">{label}</span>
              {badge != null && badge > 0 && (
                <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                  {badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-slate-700 space-y-3">
          <div>
            <div className="text-xs text-gray-400 mb-1">API Key</div>
            <input
              value={apiKeyDraft}
              onChange={e => setApiKeyDraft(e.target.value)}
              onBlur={() => setApiKey(apiKeyDraft.trim())}
              placeholder="X-API-Key..."
              className="w-full bg-slate-700 text-white text-xs px-2 py-1.5 rounded outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>

          {/* Operator ID */}
          <div className="text-xs text-gray-400 mb-1">Оператор</div>
          <input
            value={idDraft}
            onChange={e => setIdDraft(e.target.value)}
            onBlur={() => setOperatorId(idDraft)}
            placeholder="Введите ID..."
            className="w-full bg-slate-700 text-white text-xs px-2 py-1.5 rounded outline-none focus:ring-1 focus:ring-blue-400"
          />
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="bottom-right" richColors closeButton />
      <Routes>
        <Route element={<Layout />}>
          <Route
            index
            element={
              <Suspense fallback={<PageFallback />}>
                <Dashboard />
              </Suspense>
            }
          />
          <Route
            path="review"
            element={
              <Suspense fallback={<PageFallback />}>
                <ReviewQueue />
              </Suspense>
            }
          />
          <Route
            path="review/:id"
            element={
              <Suspense fallback={<PageFallback />}>
                <ReviewDetail />
              </Suspense>
            }
          />
          <Route
            path="products"
            element={
              <Suspense fallback={<PageFallback />}>
                <ProductSearch />
              </Suspense>
            }
          />
          <Route
            path="refs/brands"
            element={
              <Suspense fallback={<PageFallback />}>
                <BrandManager />
              </Suspense>
            }
          />
          <Route
            path="refs/categories"
            element={
              <Suspense fallback={<PageFallback />}>
                <CategoryManager />
              </Suspense>
            }
          />
          <Route
            path="import"
            element={
              <Suspense fallback={<PageFallback />}>
                <XlsxImport />
              </Suspense>
            }
          />
          <Route
            path="duplicates"
            element={
              <Suspense fallback={<PageFallback />}>
                <DuplicatesReport />
              </Suspense>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
