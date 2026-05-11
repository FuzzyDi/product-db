import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/api/client';
import type { MxikHealth, PipelineStats } from '@/types';
import { pct } from '@/lib/utils';

interface ReprocessStatus {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  result: string | null;
  error: string | null;
}

interface CeleryHealth {
  pending: number | null;
  active: number;
  reserved: number;
  workers: string[];
  worker_count: number;
}

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
  certified_history: Array<{ date: string; count: number }>;
}

function CertifiedChart({ data }: { data: Array<{ date: string; count: number }> }) {
  if (data.length === 0) {
    return <div className="text-xs text-gray-400 py-4 text-center">Нет данных за период</div>;
  }
  const max = Math.max(...data.map(d => d.count), 1);
  const W = 480, H = 60, pad = 2;
  const barW = Math.max(4, Math.floor((W - pad * (data.length + 1)) / data.length));
  const gap = Math.floor((W - barW * data.length) / (data.length + 1));

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${W} ${H + 16}`} className="overflow-visible">
        {data.map((d, i) => {
          const h = Math.max(2, Math.round((d.count / max) * H));
          const x = gap + i * (barW + gap);
          const y = H - h;
          return (
            <g key={d.date}>
              <rect x={x} y={y} width={barW} height={h} rx={2} className="fill-blue-500" opacity={0.8} />
              {d.count > 0 && (
                <text x={x + barW / 2} y={y - 2} textAnchor="middle" fontSize={9} className="fill-gray-500">
                  {d.count}
                </text>
              )}
              <text x={x + barW / 2} y={H + 13} textAnchor="middle" fontSize={8} className="fill-gray-400">
                {new Date(d.date).toLocaleDateString('ru', { day: 'numeric', month: 'numeric' })}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
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
  const qc = useQueryClient();

  const reprocess = useQuery({
    queryKey: ['admin/reprocess'],
    queryFn: () => api.get<ReprocessStatus>('/admin/reprocess'),
    refetchInterval: q => (q.state.data as ReprocessStatus | undefined)?.running ? 2000 : false,
  });

  async function startReprocess() {
    try {
      await api.post('/admin/reprocess', {});
      qc.invalidateQueries({ queryKey: ['admin/reprocess'] });
      toast.info('Перераспознавание запущено...');
    } catch (e: any) {
      toast.error(e?.message ?? 'Ошибка запуска');
    }
  }

  const rp = reprocess.data;
  const wasRunning = useRef(false);
  useEffect(() => {
    if (rp?.running) { wasRunning.current = true; }
    if (wasRunning.current && rp && !rp.running) {
      wasRunning.current = false;
      if (rp.result === 'ok') {
        toast.success('Перераспознавание завершено');
        qc.invalidateQueries({ queryKey: ['stats/pipeline'] });
      } else if (rp.error) {
        toast.error(`Ошибка: ${rp.error}`);
      }
    }
  }, [rp?.running, rp?.finished_at]);

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

  const celery = useQuery({
    queryKey: ['stats/celery'],
    queryFn: () => api.get<CeleryHealth>('/stats/celery'),
    refetchInterval: 10_000,
  });

  const s = stats.data;
  const h = health.data;
  const q = quality.data;
  const c = celery.data;

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-lg font-semibold mb-4">Дашборд</h1>

      {s && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
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
            <Metric
              label="Сертифицировано сегодня"
              value={s.certified_today}
              sub={s.certified_today > 0 ? 'за сегодня' : 'ещё ничего'}
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

      {/* Certified per day chart */}
      {q && (
        <div className="bg-white rounded-lg border p-4 mb-4">
          <div className="text-xs text-gray-500 mb-3">
            Сертифицировано по дням
            <span className="ml-1 text-gray-400">(последние 30 дней)</span>
          </div>
          <CertifiedChart data={q.certified_history} />
        </div>
      )}

      {/* Reprocess */}
      <div className="bg-white rounded-lg border p-4 mb-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-500 mb-0.5">Перераспознавание</div>
            <div className="text-xs text-gray-400">
              {rp?.running
                ? 'Выполняется...'
                : rp?.finished_at
                ? `Последний запуск: ${new Date(rp.finished_at).toLocaleString('ru')}`
                : 'Не запускалось'}
            </div>
          </div>
          <button
            onClick={startReprocess}
            disabled={rp?.running}
            className="flex items-center gap-1.5 px-3 py-1.5 border rounded text-sm hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw size={13} className={rp?.running ? 'animate-spin' : ''} />
            {rp?.running ? 'Выполняется...' : 'Перераспознать все'}
          </button>
        </div>
      </div>

      {/* Export */}
      <div className="bg-white rounded-lg border p-4 mb-4">
        <div className="text-xs text-gray-500 mb-2">Экспорт</div>
        <div className="flex flex-wrap gap-2">
          {['certified', 'verified', 'draft', 'candidate'].map(status => (
            <a
              key={status}
              href={`/api/v1/products/export/xlsx?status=${status}`}
              download
              className="flex items-center gap-1.5 border rounded px-3 py-1.5 text-xs hover:bg-gray-50 text-gray-700"
            >
              <Download size={12} />
              {STATUS_LABEL[status] ?? status} (.xlsx)
            </a>
          ))}
        </div>
      </div>

      {/* Celery queue */}
      <div className="bg-white rounded-lg border p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs text-gray-500">Очередь обработки (Celery)</div>
          <div className={`text-xs font-medium px-1.5 py-0.5 rounded ${
            !c ? 'bg-gray-100 text-gray-400' :
            c.worker_count === 0 ? 'bg-red-100 text-red-600' :
            'bg-green-100 text-green-700'
          }`}>
            {!c ? '...' : c.worker_count === 0 ? 'Воркер недоступен' : `${c.worker_count} воркер`}
          </div>
        </div>
        <div className="flex gap-6 text-sm">
          <div>
            <span className="text-gray-500">Ожидают: </span>
            <span className={`font-semibold ${c && (c.pending ?? 0) > 0 ? 'text-orange-500' : ''}`}>
              {c?.pending ?? '—'}
            </span>
          </div>
          <div>
            <span className="text-gray-500">В обработке: </span>
            <span className="font-semibold">{c?.active ?? '—'}</span>
          </div>
          <div>
            <span className="text-gray-500">Зарезервировано: </span>
            <span className="font-semibold">{c?.reserved ?? '—'}</span>
          </div>
        </div>
        {c && c.worker_count === 0 && (
          <div className="mt-2 text-xs text-red-500">
            Воркер не отвечает — импортированные товары не будут обработаны
          </div>
        )}
      </div>

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
