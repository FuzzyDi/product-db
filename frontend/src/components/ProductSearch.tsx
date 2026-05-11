import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { api } from '@/api/client';
import type { Product } from '@/types';
import ConfidenceBar from './ConfidenceBar';
import IssueBadge from './IssueBadge';

interface SearchResult {
  items: Product[];
  count: number;
}

interface ListResult {
  items: Product[];
  total: number;
}

const STATUS_BADGE: Record<string, string> = {
  candidate: 'bg-gray-100 text-gray-600',
  draft:     'bg-yellow-100 text-yellow-700',
  verified:  'bg-blue-100 text-blue-700',
  certified: 'bg-green-100 text-green-700',
};

export default function ProductSearch() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const searchResult = useQuery({
    queryKey: ['products/search', query],
    queryFn: () =>
      api.get<SearchResult>(`/products/search?q=${encodeURIComponent(query)}&limit=50`),
    enabled: query.length >= 2,
  });

  const listResult = useQuery({
    queryKey: ['products/list'],
    queryFn: () => api.get<ListResult>('/products?limit=50'),
    enabled: query.length < 2,
  });

  const items = query.length >= 2
    ? (searchResult.data?.items ?? [])
    : (listResult.data?.items ?? []);
  const isLoading = query.length >= 2 ? searchResult.isLoading : listResult.isLoading;

  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold mb-4">Товары</h1>

      <div className="relative mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Поиск по названию, штрихкоду или ИКПУ..."
          className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
      </div>

      {isLoading ? (
        <div className="text-gray-400 text-sm">Загрузка...</div>
      ) : items.length === 0 ? (
        <div className="text-gray-400 text-sm">Ничего не найдено</div>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium">Название</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium w-32">Бренд</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium w-20">Статус</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium w-28">Confidence</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium">Проблемы</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map(p => (
                <tr
                  key={p.product_id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/review/${p.product_id}`)}
                >
                  <td className="px-3 py-2">
                    <div className="font-medium truncate max-w-sm">
                      {p.name_canonical ?? p.name_raw ?? '—'}
                    </div>
                    {p.mxik_code && (
                      <div className="text-xs text-gray-400 font-mono">{p.mxik_code}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-gray-600">{p.brand_name ?? '—'}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_BADGE[p.status] ?? 'bg-gray-100'}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <ConfidenceBar value={p.confidence_score} />
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(p.issues ?? []).slice(0, 2).map(i => (
                        <IssueBadge key={i} issue={i} />
                      ))}
                      {(p.issues?.length ?? 0) > 2 && (
                        <span className="text-xs text-gray-400">+{(p.issues?.length ?? 0) - 2}</span>
                      )}
                    </div>
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
