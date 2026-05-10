import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, CheckCheck } from 'lucide-react';
import { api } from '@/api/client';
import { useHotkeys } from '@/hooks/useHotkeys';
import { useOperatorId } from '@/hooks/useOperatorId';
import type { Product, ReviewDetail as ReviewDetailType } from '@/types';
import ConfidenceBar from './ConfidenceBar';
import IssueBadge from './IssueBadge';
import MxikSelector from './MxikSelector';
import ProductEditForm from './ProductEditForm';

export default function ReviewDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { operatorId } = useOperatorId();
  const [edits, setEdits] = useState<Partial<Product>>({});
  const [saving, setSaving] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['review', id],
    queryFn: () => api.get<ReviewDetailType>(`/review/${id}`),
    enabled: !!id,
  });

  useHotkeys(
    {
      'ctrl+enter': () => confirm(),
      escape: () => navigate('/review'),
    },
    [id, edits, operatorId],
  );

  async function confirm() {
    if (!id || !operatorId || saving) return;
    setSaving(true);
    try {
      // Сначала сохраняем безопасные правки
      if (Object.keys(edits).length > 0) {
        await api.put(`/products/${id}`, edits);
      }
      // Подтверждаем карточку
      await api.post(`/review/${id}/decide`, { decision_type: 'confirm_product' }, operatorId);
      qc.invalidateQueries({ queryKey: ['review/queue'] });
      qc.invalidateQueries({ queryKey: ['stats/pipeline'] });
      navigate('/review');
    } finally {
      setSaving(false);
    }
  }

  async function handleMxikSelect(mxik: string, packageCode: number | null) {
    if (!id || !operatorId) return;
    await api.post(
      `/review/${id}/decide`,
      {
        decision_type: 'confirm_mxik',
        field_name: 'mxik_code',
        new_value: { mxik_code: mxik, mxik_package_code: packageCode },
      },
      operatorId,
    );
    qc.invalidateQueries({ queryKey: ['review', id] });
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
        <span className="text-sm font-medium truncate max-w-xs">
          {product.name_canonical ?? product.name_raw ?? product.product_id}
        </span>
        <div className="ml-auto flex items-center gap-3">
          <ConfidenceBar value={product.confidence_score} />
          {!operatorId && (
            <span className="text-xs text-red-500">Укажите ID оператора в сайдбаре</span>
          )}
          <button
            onClick={confirm}
            disabled={saving || !operatorId}
            className="flex items-center gap-1.5 bg-green-600 text-white px-3 py-1.5 rounded text-sm hover:bg-green-700 disabled:opacity-50"
          >
            <CheckCheck size={14} />
            Подтвердить
            <kbd className="ml-1 text-xs opacity-70">Ctrl+Enter</kbd>
          </button>
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
            <Row label="Штрихкод" value={data.product.barcode ?? (data.product as any).barcode ?? null} />
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
                  <a
                    key={s.product_id}
                    href={`/review/${s.product_id}`}
                    className="flex items-center justify-between text-xs p-2 bg-yellow-50 border border-yellow-200 rounded hover:bg-yellow-100"
                  >
                    <span className="truncate">{s.name_canonical}</span>
                    <span className="text-gray-500 ml-2 flex-shrink-0">
                      {Math.round(s.sim * 100)}%
                    </span>
                  </a>
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
