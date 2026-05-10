import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import type { Product } from '@/types';
import ConfidenceBar from './ConfidenceBar';
import IssueBadge from './IssueBadge';

interface QueueData {
  items: Product[];
  total: number;
  offset: number;
  limit: number;
}

export default function ReviewQueue() {
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ['review/queue'],
    queryFn: () => api.get<QueueData>('/review/queue?limit=100'),
    refetchInterval: 15_000,
  });

  if (isLoading) {
    return <div className="p-6 text-gray-500">Загрузка...</div>;
  }

  const items = data?.items ?? [];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">
          Очередь ревью
          {data && (
            <span className="ml-2 text-sm font-normal text-gray-500">
              {data.total} товаров
            </span>
          )}
        </h1>
      </div>

      {items.length === 0 ? (
        <div className="bg-white border rounded-lg p-12 text-center text-gray-400">
          Очередь пуста
        </div>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium">Название</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium w-36">Бренд</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium w-28">Confidence</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium">Проблемы</th>
                <th className="w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map(p => (
                <tr
                  key={p.product_id}
                  onClick={() => navigate(`/review/${p.product_id}`)}
                  className="hover:bg-blue-50 cursor-pointer transition-colors"
                >
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-900 truncate max-w-xs">
                      {p.name_canonical ?? p.name_raw ?? '—'}
                    </div>
                    {p.mxik_code && (
                      <div className="text-xs text-gray-400 mt-0.5 font-mono">{p.mxik_code}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-700">{p.brand_name ?? '—'}</td>
                  <td className="px-3 py-2">
                    <ConfidenceBar value={p.confidence_score} />
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(p.issues ?? []).slice(0, 3).map(i => (
                        <IssueBadge key={i} issue={i} />
                      ))}
                      {(p.issues?.length ?? 0) > 3 && (
                        <span className="text-xs text-gray-400">
                          +{(p.issues?.length ?? 0) - 3}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button className="text-blue-600 hover:underline text-xs">
                      Открыть
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
