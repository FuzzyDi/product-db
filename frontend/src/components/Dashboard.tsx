import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { MxikHealth, PipelineStats } from '@/types';
import { pct } from '@/lib/utils';

interface QualityStats {
  decisions_by_type: Record<string, number>;
  learned_aliases: number;
  history: Array<{
    period_date: string;
    total_products: number;
    with_brand: number;
    with_mxik: number;
    auto_confirmed: number;
    avg_confidence: number | null;
  }>;
}

function Metric({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = {
  candidate: 'Кандидат',
  draft: 'Черновик',
  verified: 'Проверен',
  certified: 'Сертифицирован',
};

const STATUS_COLOR: Record<string, string> = {
  candidate: 'bg-gray-200',
  draft: 'bg-yellow-300',
  verified: 'bg-blue-400',
  certified: 'bg-green-500',
};

export default function Dashboard() {
  const stats = useQuery({
    queryKey: ['stats/pipeline'],
    queryFn: () => api.get<PipelineStats>('/stats/pipeline'),
    refetchInterval: 30_000,
  });

  const health = useQuery({
    queryKey: ['stats/mxik-health'],
    queryFn: () => api.get<MxikHealth>('/stats/mxik-health'),
    refetchInterval: 60_000,
  });

  const quality = useQuery({
    queryKey: ['stats/quality'],
    queryFn: () => api.get<QualityStats>('/stats/quality?days=7'),
    refetchInterval: 120_000,
  });

  const s = stats.data;
  const h = health.data;
  const q = quality.data;

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-lg font-semibold mb-4">Дашборд</h1>

      {s && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <Metric label="Всего товаров" value={s.total_products.toLocaleString()} />
            <Metric
              label="На ревью"
              value={s.review_queue_size}
              sub={s.total_products ? pct(s.review_queue_size / s.total_products) : undefined}
            />
            <Metric
              label="С брендом"
              value={pct(s.total_products ? s.with_brand / s.total_products : 0)}
              sub={`${s.with_brand.toLocaleString()} товаров`}
            />
            <Metric
              label="С ИКПУ"
              value={pct(s.total_products ? s.with_mxik / s.total_products : 0)}
              sub={`${s.with_mxik.toLocaleString()} товаров`}
            />
          </div>

          {/* By status */}
          <div className="bg-white rounded-lg border p-4 mb-4">
            <div className="text-xs text-gray-500 mb-3">По статусу</div>
            <div className="space-y-2">
              {Object.entries(s.by_status).map(([status, count]) => {
                const share = s.total_products ? count / s.total_products : 0;
                return (
                  <div key={status} className="flex items-center gap-2">
                    <div className="w-24 text-xs text-gray-600">
                      {STATUS_LABEL[status] ?? status}
                    </div>
                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${STATUS_COLOR[status] ?? 'bg-gray-400'}`}
                        style={{ width: `${Math.round(share * 100)}%` }}
                      />
                    </div>
                    <div className="w-16 text-xs text-right text-gray-500 tabular-nums">
                      {count.toLocaleString()}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Learning stats */}
      {q && (
        <div className="bg-white rounded-lg border p-4 mb-4">
          <div className="text-xs text-gray-500 mb-2">Обучение системы</div>
          <div className="flex flex-wrap gap-6 text-sm">
            <div>
              <span className="text-gray-500">Выучено псевдонимов: </span>
              <span className="font-semibold text-blue-600">{q.learned_aliases}</span>
            </div>
            {Object.entries(q.decisions_by_type).map(([type, count]) => (
              <div key={type}>
                <span className="text-gray-500">{type}: </span>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
          {q.history.length > 0 && (
            <div className="mt-3 text-xs text-gray-400">
              Последнее: {new Date(q.history[0].period_date).toLocaleDateString('ru')} —{' '}
              {q.history[0].total_products.toLocaleString()} товаров,{' '}
              ср. confidence {q.history[0].avg_confidence != null ? pct(q.history[0].avg_confidence) : '—'}
            </div>
          )}
        </div>
      )}

      {/* MXIK health */}
      {h && (
        <div className="bg-white rounded-lg border p-4">
          <div className="text-xs text-gray-500 mb-2">Реестр ИКПУ</div>
          <div className="flex flex-wrap gap-4 text-sm">
            <div>
              <span className="text-gray-500">Статус: </span>
              <span
                className={
                  h.last_sync_status === 'success'
                    ? 'text-green-600 font-medium'
                    : 'text-red-500 font-medium'
                }
              >
                {h.last_sync_status ?? '—'}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Активных записей: </span>
              <span className="font-medium">{h.active_records.toLocaleString()}</span>
              <span className="text-gray-400"> / {h.total_records.toLocaleString()}</span>
            </div>
            {h.last_sync_at && (
              <div>
                <span className="text-gray-500">Последняя синхронизация: </span>
                <span>{new Date(h.last_sync_at).toLocaleString('ru')}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
