import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, CheckCheck, ChevronRight, ExternalLink, GitMerge, X } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/api/client';
import { useHotkeys } from '@/hooks/useHotkeys';
import { useOperatorId } from '@/hooks/useOperatorId';
import type { Product, ReviewDetail as ReviewDetailType } from '@/types';
import ConfidenceBar from './ConfidenceBar';
import IssueBadge from './IssueBadge';
import MxikSelector from './MxikSelector';
import ProductEditForm from './ProductEditForm';

interface QueueData { items: Product[]; total: number; }

interface DecisionEntry {
  id: string;
  operator_id: string;
  decision_type: string;
  field_name: string | null;
  new_value: Record<string, unknown> | null;
  comment: string | null;
  created_at: string | null;
}

const DECISION_LABEL: Record<string, string> = {
  confirm_product: 'Подтверждён',
  confirm_mxik: 'ИКПУ установлен',
  correct_field: 'Поле исправлено',
  merge_products: 'Объединён',
  dismiss: 'Убран из очереди',
  reject_match: 'Привязка отклонена',
};

export default function ReviewDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { operatorId } = useOperatorId();
  const [edits, setEdits] = useState<Partial<Product>>({});
  const [saving, setSaving] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['review', id],
    queryFn: () => api.get<ReviewDetailType>(`/review/${id}`),
    enabled: !!id,
  });

  const { data: decisions } = useQuery({
    queryKey: ['review/decisions', id],
    queryFn: () => api.get<DecisionEntry[]>(`/review/${id}/decisions`),
    enabled: !!id,
  });

  const { data: queue } = useQuery({
    queryKey: ['review/queue'],
    queryFn: () => api.get<QueueData>('/review/queue?limit=100'),
    staleTime: 30_000,
  });

  function goNext() {
    const items = queue?.items ?? [];
    const idx = items.findIndex(p => p.product_id === id);
    const next = items[idx + 1];
    if (next) navigate(`/review/${next.product_id}`);
    else navigate('/review');
  }

  async function dismiss() {
    if (!id || !operatorId || dismissing) return;
    setDismissing(true);
    try {
      await api.post('/review/batch', { product_ids: [id], decision_type: 'dismiss' }, operatorId);
      qc.invalidateQueries({ queryKey: ['review/queue'] });
      toast.info(`Убрано из очереди`);
      goNext();
    } finally {
      setDismissing(false);
    }
  }

  useHotkeys(
    {
      'ctrl+enter': () => confirmProduct(),
      escape: () => navigate('/review'),
      a: () => confirmProduct(),
      d: () => dismiss(),
      arrowright: () => goNext(),
    },
    [id, edits, operatorId, queue],
  );

  async function confirmProduct() {
    if (!id || !operatorId || saving) return;
    setSaving(true);
    try {
      if (Object.keys(edits).length > 0) {
        await api.put(`/products/${id}`, edits);
      }
      await api.post(`/review/${id}/decide`, { decision_type: 'confirm_product' }, operatorId);
      setEdits({});
      qc.invalidateQueries({ queryKey: ['review/queue'] });
      qc.invalidateQueries({ queryKey: ['stats/pipeline'] });
      toast.success(`Подтверждено: ${product.name_canonical ?? product.name_raw ?? id}`);

      goNext();
    } finally {
      setSaving(false);
    }
  }

  async function merge(targetId: string) {
    if (!id || !operatorId || merging) return;
    setMerging(targetId);
    try {
      await api.post(
        `/review/${id}/decide`,
        { decision_type: 'merge_products', new_value: { target_product_id: targetId } },
        operatorId,
      );
      qc.invalidateQueries({ queryKey: ['review/queue'] });
      qc.invalidateQueries({ queryKey: ['stats/pipeline'] });
      toast.success('Товары объединены');
      goNext();
    } finally {
      setMerging(null);
    }
  }

  async function handleMxikSelect(mxik: string, packageCode: number | null) {
    if (!id || !operatorId || !mxik) return;
    await api.post(
      `/review/${id}/decide`,
      {
        decision_type: 'confirm_mxik',
        field_name: 'mxik_code',
        new_value: { mxik_code: mxik, mxik_package_code: packageCode },
      },
      operatorId,
    );
    await qc.refetchQueries({ queryKey: ['review', id] });
  }

  if (isLoading || !data) {
    return <div className="p-6 text-gray-500">Загрузка...</div>;
  }

  const product = { ...data.product, ...edits };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b bg-white flex-shrink-0">
        <button
          onClick={() => navigate('/review')}
          className="text-gray-500 hover:text-gray-800 flex items-center gap-1 text-sm"
        >
          <ArrowLeft size={14} /> Очередь
        </button>
        <span className="text-gray-300">|</span>
        {queue && (() => {
          const idx = queue.items.findIndex(p => p.product_id === id);
          return idx >= 0 ? (
            <span className="text-xs text-gray-400 flex-shrink-0">{idx + 1} / {queue.total}</span>
          ) : null;
        })()}
        <span className="text-sm font-medium truncate max-w-xs">
          {product.name_canonical ?? product.name_raw ?? product.product_id}
        </span>
        <div className="ml-auto flex items-center gap-3">
          <ConfidenceBar value={product.confidence_score} />
          {!operatorId && (
            <span className="text-xs text-red-500">Укажите ID оператора в сайдбаре</span>
          )}
          <button
            onClick={dismiss}
            disabled={dismissing || !operatorId}
            className="flex items-center gap-1.5 bg-gray-500 text-white px-3 py-1.5 rounded text-sm hover:bg-gray-600 disabled:opacity-50"
          >
            <X size={14} />
            {dismissing ? '...' : 'Убрать'}
            <kbd className="ml-1 text-xs opacity-70">D</kbd>
          </button>
          <button
            onClick={confirmProduct}
            disabled={saving || !operatorId}
            className="flex items-center gap-1.5 bg-green-600 text-white px-3 py-1.5 rounded text-sm hover:bg-green-700 disabled:opacity-50"
          >
            <CheckCheck size={14} />
            {saving ? 'Сохранение...' : 'Подтвердить'}
            <kbd className="ml-1 text-xs opacity-70">A</kbd>
          </button>
          {queue && (() => {
            const items = queue.items;
            const idx = items.findIndex(p => p.product_id === id);
            const next = items[idx + 1];
            return next ? (
              <button
                onClick={() => navigate(`/review/${next.product_id}`)}
                className="flex items-center gap-1 text-gray-500 hover:text-gray-800 text-sm border rounded px-2 py-1.5"
                title="Следующий без подтверждения (→)"
              >
                <ChevronRight size={14} />
              </button>
            ) : null;
          })()}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto grid grid-cols-2 gap-0 divide-x">
        {/* Left: raw data */}
        <div className="p-4 overflow-auto">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Исходные данные
          </div>

          <div className="space-y-2 text-sm">
            <Row label="Сырое название" value={data.product.name_raw} />
            <Row label="Нормализованное" value={data.product.name_normalized ?? null} />
            <Row label="Наим. (уз. лат.)" value={data.product.name_uz_latn ?? null} />
            <Row label="Штрихкод" value={data.product.barcodes?.join(', ') || null} />
            <Row label="ИКПУ" value={data.product.mxik_code} />
            <Row label="Пакейдж код" value={data.product.mxik_package_code?.toString() ?? null} />
            <Row label="Статус" value={data.product.status} />
          </div>

          {/* Issues */}
          {(data.product.issues?.length ?? 0) > 0 && (
            <div className="mt-4">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Проблемы
              </div>
              <div className="flex flex-wrap gap-1">
                {data.product.issues!.map(i => <IssueBadge key={i} issue={i} />)}
              </div>
            </div>
          )}

          {/* Similar products */}
          {data.similar_products.length > 0 && (
            <div className="mt-4">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Похожие товары (проверьте дубли)
              </div>
              <div className="space-y-1">
                {data.similar_products.map(s => (
                  <div
                    key={s.product_id}
                    className="flex items-center gap-1 text-xs p-2 bg-yellow-50 border border-yellow-200 rounded"
                  >
                    <a
                      href={`/review/${s.product_id}`}
                      className="flex-1 truncate hover:underline"
                    >
                      {s.name_canonical}
                    </a>
                    <a
                      href={`/review/${s.product_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}
                      className="flex-shrink-0 text-gray-400 hover:text-blue-600"
                      title="Открыть в новой вкладке"
                    >
                      <ExternalLink size={11} />
                    </a>
                    <span className="text-gray-500 flex-shrink-0">
                      {Math.round(s.sim * 100)}%
                    </span>
                    <button
                      onClick={() => {
                        if (window.confirm(`Объединить в "${s.name_canonical}"?\nШтрихкоды текущего товара будут перенесены.`)) {
                          merge(s.product_id);
                        }
                      }}
                      disabled={merging === s.product_id || !operatorId}
                      className="flex items-center gap-0.5 ml-1 px-1.5 py-0.5 bg-orange-100 text-orange-700 border border-orange-300 rounded hover:bg-orange-200 disabled:opacity-50 flex-shrink-0"
                      title="Объединить (текущий → этот)"
                    >
                      <GitMerge size={11} />
                      {merging === s.product_id ? '...' : 'Слить'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Decision history */}
          {decisions && decisions.length > 0 && (
            <div className="mt-4">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                История решений
              </div>
              <div className="space-y-1">
                {decisions.map(d => (
                  <div key={d.id} className="text-xs flex gap-2 py-1 border-b border-gray-100 last:border-0">
                    <div className="flex-1 text-gray-700">
                      <span className="font-medium">{DECISION_LABEL[d.decision_type] ?? d.decision_type}</span>
                      {d.field_name && <span className="text-gray-400"> · {d.field_name}</span>}
                    </div>
                    <div className="text-gray-400 flex-shrink-0 text-right">
                      <div>{d.operator_id}</div>
                      <div>{d.created_at ? new Date(d.created_at).toLocaleString('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: edit form */}
        <div className="p-4 overflow-auto">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Карточка товара
          </div>

          <ProductEditForm
            product={product}
            onChange={patch => setEdits(prev => ({ ...prev, ...patch }))}
          />

          {/* MXIK selector */}
          <div className="mt-4">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              ИКПУ (MXIK)
            </div>
            <MxikSelector
              selectedMxik={product.mxik_code}
              selectedPackageCode={product.mxik_package_code ?? null}
              onSelect={handleMxikSelect}
              barcode={data.product.barcodes?.[0] ?? null}
            />

            {/* MXIK candidates from pipeline */}
            {data.mxik_candidates.length > 0 && (
              <div className="mt-2">
                <div className="text-xs text-gray-400 mb-1">Кандидаты от пайплайна:</div>
                <div className="space-y-1">
                  {data.mxik_candidates.map(c => (
                    <button
                      key={c.mxik}
                      onClick={() => handleMxikSelect(c.mxik, null)}
                      className="w-full text-left text-xs p-2 border rounded hover:bg-blue-50 flex gap-2"
                    >
                      <span className="font-mono text-gray-500">{c.mxik}</span>
                      <span className="flex-1 truncate">{c.mxik_name_ru}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-400 w-36 flex-shrink-0">{label}</span>
      <span className="text-gray-900 break-all">{value ?? '—'}</span>
    </div>
  );
}
