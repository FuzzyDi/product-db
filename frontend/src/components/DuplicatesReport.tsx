import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, GitMerge } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/api/client';
import { useOperatorId } from '@/hooks/useOperatorId';

interface DupePair {
  id_a: string;
  name_a: string;
  brand_a: string | null;
  status_a: string;
  id_b: string;
  name_b: string;
  brand_b: string | null;
  status_b: string;
  sim: number;
}

export default function DuplicatesReport() {
  const qc = useQueryClient();
  const { operatorId } = useOperatorId();
  const [threshold, setThreshold] = useState(0.85);
  const [merging, setMerging] = useState<string | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['duplicates', threshold],
    queryFn: () => api.get<{ pairs: DupePair[]; count: number }>(`/products/duplicates?threshold=${threshold}&limit=100`),
  });

  async function merge(sourceId: string, targetId: string, targetName: string) {
    if (!operatorId) { toast.error('Укажите ID оператора'); return; }
    if (!confirm(`Объединить в "${targetName}"?\nШтрихкоды источника будут перенесены.`)) return;
    setMerging(sourceId);
    try {
      await api.post(`/review/${sourceId}/decide`, {
        decision_type: 'merge_products',
        new_value: { target_product_id: targetId },
      }, operatorId);
      toast.success('Объединено');
      qc.invalidateQueries({ queryKey: ['duplicates'] });
      qc.invalidateQueries({ queryKey: ['stats/pipeline'] });
    } catch (e: any) {
      toast.error(e?.message ?? 'Ошибка');
    } finally {
      setMerging(null);
    }
  }

  const pairs = data?.pairs ?? [];

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Отчёт по дублям</h1>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-500">
            Порог схожести:
            <select
              value={threshold}
              onChange={e => setThreshold(Number(e.target.value))}
              className="ml-2 border rounded px-2 py-1 text-sm"
            >
              <option value={0.95}>95%</option>
              <option value={0.9}>90%</option>
              <option value={0.85}>85%</option>
              <option value={0.8}>80%</option>
              <option value={0.75}>75%</option>
            </select>
          </label>
          <span className="text-sm text-gray-400">
            {isLoading ? 'Загрузка...' : `${data?.count ?? 0} пар`}
          </span>
        </div>
      </div>

      {!operatorId && (
        <div className="mb-4 text-xs text-red-500 bg-red-50 border border-red-200 rounded p-2">
          Укажите ID оператора в сайдбаре для слияния дублей
        </div>
      )}

      {pairs.length === 0 && !isLoading && (
        <div className="text-gray-400 text-sm py-8 text-center">
          Дублей с порогом {Math.round(threshold * 100)}% не найдено
        </div>
      )}

      <div className="space-y-2">
        {pairs.map(pair => (
          <div key={`${pair.id_a}-${pair.id_b}`} className="bg-white border rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-orange-600 bg-orange-50 border border-orange-200 rounded px-1.5 py-0.5">
                {Math.round(pair.sim * 100)}% схожесть
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {/* Product A */}
              <div className="text-sm">
                <div className="flex items-center gap-1 font-medium text-gray-800">
                  <a href={`/review/${pair.id_a}`} className="hover:underline truncate">{pair.name_a}</a>
                  <a href={`/review/${pair.id_a}`} target="_blank" rel="noopener noreferrer"
                     className="flex-shrink-0 text-gray-400 hover:text-blue-600">
                    <ExternalLink size={11} />
                  </a>
                </div>
                {pair.brand_a && <div className="text-xs text-gray-500">{pair.brand_a}</div>}
                <div className="text-xs text-gray-400 mt-0.5">{pair.status_a}</div>
                <button
                  onClick={() => merge(pair.id_a, pair.id_b, pair.name_b)}
                  disabled={!!merging || !operatorId}
                  className="mt-1.5 flex items-center gap-1 text-xs px-2 py-1 bg-orange-50 text-orange-700 border border-orange-200 rounded hover:bg-orange-100 disabled:opacity-50"
                >
                  <GitMerge size={11} />
                  {merging === pair.id_a ? '...' : '→ Слить в правый'}
                </button>
              </div>

              {/* Product B */}
              <div className="text-sm">
                <div className="flex items-center gap-1 font-medium text-gray-800">
                  <a href={`/review/${pair.id_b}`} className="hover:underline truncate">{pair.name_b}</a>
                  <a href={`/review/${pair.id_b}`} target="_blank" rel="noopener noreferrer"
                     className="flex-shrink-0 text-gray-400 hover:text-blue-600">
                    <ExternalLink size={11} />
                  </a>
                </div>
                {pair.brand_b && <div className="text-xs text-gray-500">{pair.brand_b}</div>}
                <div className="text-xs text-gray-400 mt-0.5">{pair.status_b}</div>
                <button
                  onClick={() => merge(pair.id_b, pair.id_a, pair.name_a)}
                  disabled={!!merging || !operatorId}
                  className="mt-1.5 flex items-center gap-1 text-xs px-2 py-1 bg-orange-50 text-orange-700 border border-orange-200 rounded hover:bg-orange-100 disabled:opacity-50"
                >
                  <GitMerge size={11} />
                  {merging === pair.id_b ? '...' : '← Слить в левый'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
