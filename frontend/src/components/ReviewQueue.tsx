import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { CheckCheck, ChevronUp, ChevronDown, X } from 'lucide-react';
import { api } from '@/api/client';
import { useOperatorId } from '@/hooks/useOperatorId';
import type { GroupMxikBucket, PipelineStats, Product, ProductType } from '@/types';

interface Category { id: number; name: string; parent_id: number | null; }
interface CategoryNode extends Category { children: CategoryNode[]; }
interface FlatCat { id: number; label: string; }

function flattenCats(cats: Category[]): FlatCat[] {
  const map = new Map<number, CategoryNode>();
  cats.forEach(c => map.set(c.id, { ...c, children: [] }));
  const roots: CategoryNode[] = [];
  map.forEach(n => { if (n.parent_id == null) roots.push(n); else map.get(n.parent_id)?.children.push(n); });
  const result: FlatCat[] = [];
  function walk(nodes: CategoryNode[], depth: number) {
    nodes.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    for (const n of nodes) {
      result.push({ id: n.id, label: '\u00a0\u00a0'.repeat(depth) + n.name });
      walk(n.children, depth + 1);
    }
  }
  walk(roots, 0);
  return result;
}
import ConfidenceBar from './ConfidenceBar';
import IssueBadge from './IssueBadge';

interface QueueData {
  items: Product[];
  total: number;
  offset: number;
  limit: number;
}

const ISSUE_FILTERS = [
  { label: 'Все', value: '' },
  { label: 'Негрупповые', value: '__NON_GROUP__' },
  { label: 'Workflow GROUP_MXIK', value: '__GROUP_MXIK__' },
  { label: 'Внутр. ШК', value: 'INTERNAL_BC_AS_GLOBAL' },
  { label: 'Нет бренда', value: 'MISSING_BRAND' },
  { label: 'Нет типа', value: 'MISSING_PRODUCT_TYPE' },
  { label: 'Нет ИКПУ', value: 'MISSING_MXIK' },
];

export default function ReviewQueue() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();
  const { operatorId } = useOperatorId();
  const scope = searchParams.get('scope');
  const initialGroupCodeFilter = searchParams.get('group_code') ?? '';
  const initialIssueFilter = scope === 'non_group'
    ? '__NON_GROUP__'
    : scope === 'group_mxik'
      ? '__GROUP_MXIK__'
      : (searchParams.get('reason') ?? '');
  const [issueFilter, setIssueFilter] = useState(initialIssueFilter);
  const [groupCodeFilter, setGroupCodeFilter] = useState(initialGroupCodeFilter);
  const [search, setSearch] = useState('');
  const [brandFilter, setBrandFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState<number | ''>('');
  const [categoryFilter, setCategoryFilter] = useState<number | ''>('');
  const [noType, setNoType] = useState(false);
  const [noCategory, setNoCategory] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batching, setBatching] = useState(false);
  const [focusedIdx, setFocusedIdx] = useState(0);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);
  const [preview, setPreview] = useState<{ product: Product; y: number } | null>(null);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState('confidence');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const PAGE_SIZE = 100;

  function handleSort(col: string) {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('asc');
    }
    setPage(0);
    setFocusedIdx(0);
  }

  const { data: productTypes } = useQuery({
    queryKey: ['refs/product-types'],
    queryFn: () => api.get<ProductType[]>('/refs/product-types'),
    staleTime: 60_000,
  });

  const { data: categoriesRaw } = useQuery({
    queryKey: ['refs/categories'],
    queryFn: () => api.get<Category[]>('/refs/categories'),
    staleTime: 60_000,
  });
  const { data: stats } = useQuery({
    queryKey: ['stats/pipeline'],
    queryFn: () => api.get<PipelineStats>('/stats/pipeline'),
    staleTime: 15_000,
  });
  const { data: groupMxikBuckets } = useQuery({
    queryKey: ['review/group-mxik-buckets'],
    queryFn: () => api.get<GroupMxikBucket[]>('/review/group-mxik-buckets?limit=200'),
    enabled: issueFilter === '__GROUP_MXIK__',
    staleTime: 30_000,
  });
  const categoryOptions = flattenCats(Array.isArray(categoriesRaw) ? categoriesRaw : []);

  const groupOnlyParam = issueFilter === '__GROUP_MXIK__' ? '&group_mxik_only=true' : '';
  const nonGroupOnlyParam = issueFilter === '__NON_GROUP__' ? '&non_group_only=true' : '';
  const groupCodeParam = issueFilter === '__GROUP_MXIK__' && groupCodeFilter
    ? `&mxik_code=${encodeURIComponent(groupCodeFilter)}`
    : '';
  const reviewReasonValue =
    issueFilter && issueFilter !== '__NON_GROUP__' && issueFilter !== '__GROUP_MXIK__'
      ? issueFilter
      : '';
  const typeParam = typeFilter ? `&product_type_id=${typeFilter}` : '';
  const catParam = categoryFilter ? `&category_id=${categoryFilter}` : '';
  const noTypeParam = noType ? '&no_type=true' : '';
  const noCatParam = noCategory ? '&no_category=true' : '';
  const reasonParam = reviewReasonValue ? `&review_reason=${encodeURIComponent(reviewReasonValue)}` : '';
  const { data, isLoading } = useQuery({
    queryKey: ['review/queue', page, sortBy, sortDir, issueFilter, groupCodeFilter, typeFilter, categoryFilter, noType, noCategory],
    queryFn: () => api.get<QueueData>(`/review/queue?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}&sort_by=${sortBy}&sort_dir=${sortDir}${reasonParam}${groupOnlyParam}${nonGroupOnlyParam}${groupCodeParam}${typeParam}${catParam}${noTypeParam}${noCatParam}`),
    refetchInterval: 15_000,
  });

  const allItems = data?.items ?? [];
  const items = allItems.filter(p => {
    if (brandFilter && p.brand_name !== brandFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        p.name_canonical?.toLowerCase().includes(q) ||
        p.name_raw?.toLowerCase().includes(q) ||
        p.brand_name?.toLowerCase().includes(q) ||
        p.barcodes?.some(b => b.includes(q))
      );
    }
    return true;
  });

  const brandOptions = [...new Set(allItems.map(p => p.brand_name).filter(Boolean) as string[])].sort();
  const reviewBreakdown = stats?.review_breakdown ?? {};
  const issueCounts: Record<string, number> = {
    '': stats?.review_queue_size ?? 0,
    '__NON_GROUP__': stats?.review_non_group_size ?? 0,
    '__GROUP_MXIK__': stats?.review_group_mxik_size ?? 0,
    INTERNAL_BC_AS_GLOBAL: reviewBreakdown.INTERNAL_BC_AS_GLOBAL ?? 0,
    MISSING_BRAND: reviewBreakdown.MISSING_BRAND ?? 0,
    MISSING_PRODUCT_TYPE: reviewBreakdown.MISSING_PRODUCT_TYPE ?? 0,
    MISSING_MXIK: reviewBreakdown.MISSING_MXIK ?? 0,
  };

  useEffect(() => {
    const nextScope = searchParams.get('scope');
    const next = nextScope === 'non_group'
      ? '__NON_GROUP__'
      : nextScope === 'group_mxik'
        ? '__GROUP_MXIK__'
        : (searchParams.get('reason') ?? '');
    setIssueFilter(prev => (prev === next ? prev : next));
    const nextGroupCode = searchParams.get('group_code') ?? '';
    setGroupCodeFilter(prev => (prev === nextGroupCode ? prev : nextGroupCode));
  }, [searchParams]);

  function applyIssueFilter(value: string) {
    const next = new URLSearchParams(searchParams);
    next.delete('reason');
    next.delete('scope');
    next.delete('group_code');
    if (value === '__NON_GROUP__') {
      next.set('scope', 'non_group');
    } else if (value === '__GROUP_MXIK__') {
      next.set('scope', 'group_mxik');
    } else if (value) {
      next.set('reason', value);
    }
    setSearchParams(next, { replace: true });
    setIssueFilter(value);
    setGroupCodeFilter('');
    setPage(0);
    setFocusedIdx(0);
  }

  function applyGroupCodeFilter(value: string) {
    const next = new URLSearchParams(searchParams);
    if (issueFilter === '__GROUP_MXIK__') {
      next.set('scope', 'group_mxik');
      if (value) next.set('group_code', value);
      else next.delete('group_code');
    }
    setSearchParams(next, { replace: true });
    setGroupCodeFilter(value);
    setPage(0);
    setFocusedIdx(0);
    setSelected(new Set());
  }

  function openReview(productId: string) {
    const query = searchParams.toString();
    navigate({
      pathname: `/review/${productId}`,
      search: query ? `?${query}` : '',
    });
  }

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        setFocusedIdx(i => {
          const next = Math.min(i + 1, items.length - 1);
          rowRefs.current[next]?.scrollIntoView({ block: 'nearest' });
          return next;
        });
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        setFocusedIdx(i => {
          const prev = Math.max(i - 1, 0);
          rowRefs.current[prev]?.scrollIntoView({ block: 'nearest' });
          return prev;
        });
      } else if (e.key === ' ') {
        e.preventDefault();
        const pid = items[focusedIdx]?.product_id;
        if (pid) setSelected(prev => { const s = new Set(prev); s.has(pid) ? s.delete(pid) : s.add(pid); return s; });
      } else if (e.key === 'Enter') {
        const pid = items[focusedIdx]?.product_id;
        if (pid) navigate(`/review/${pid}`);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [items, focusedIdx, navigate]);

  if (isLoading) {
    return <div className="p-6 text-gray-500">Загрузка...</div>;
  }

  const visibleIds = items.map(p => p.product_id);
  const allSelected = visibleIds.length > 0 && visibleIds.every(id => selected.has(id));

  function toggleAll() {
    if (allSelected) {
      setSelected(prev => { const s = new Set(prev); visibleIds.forEach(id => s.delete(id)); return s; });
    } else {
      setSelected(prev => new Set([...prev, ...visibleIds]));
    }
  }

  function toggleOne(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    setSelected(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  }

  async function batchAction(decision_type: string, value?: number) {
    if (!operatorId || batching || selected.size === 0) return;
    const count = selected.size;
    setBatching(true);
    try {
      await api.post('/review/batch', { product_ids: [...selected], decision_type, value: value ?? null }, operatorId);
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ['review/queue'] });
      qc.invalidateQueries({ queryKey: ['stats/pipeline'] });
      if (decision_type === 'confirm_product') toast.success(`Подтверждено: ${count} товаров`);
      else if (decision_type === 'dismiss') toast.info(`Убрано из очереди: ${count} товаров`);
      else if (decision_type === 'set_type') toast.success(`Тип назначен: ${count} товаров`);
      else if (decision_type === 'set_category') toast.success(`Категория назначена: ${count} товаров`);
    } catch {
      toast.error('Ошибка при выполнении операции');
    } finally {
      setBatching(false);
    }
  }

  function showPreview(p: Product, el: HTMLTableRowElement) {
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => {
      const rect = el.getBoundingClientRect();
      setPreview({ product: p, y: rect.top });
    }, 400);
  }

  function hidePreview() {
    if (previewTimer.current) clearTimeout(previewTimer.current);
    setPreview(null);
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-lg font-semibold">
          Очередь ревью
          <span className="ml-2 text-sm font-normal text-gray-500">
            {items.length}{items.length !== allItems.length ? ` / ${allItems.length}` : ''} товаров
          </span>
        </h1>
        <div className="flex gap-1">
          {ISSUE_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => applyIssueFilter(f.value)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                issueFilter === f.value
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              {f.label}
              <span className="ml-1 opacity-70">{issueCounts[f.value] ?? 0}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="flex gap-2 mb-3">
        <input
          value={search}
          onChange={e => { setSearch(e.target.value); setFocusedIdx(0); setPage(0); }}
          placeholder="Поиск по названию, бренду, штрихкоду..."
          className="flex-1 border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
        {brandOptions.length > 0 && (
          <select
            value={brandFilter}
            onChange={e => { setBrandFilter(e.target.value); setFocusedIdx(0); setPage(0); }}
            className="border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">Все бренды</option>
            {brandOptions.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        )}
        {(Array.isArray(productTypes) ? productTypes : []).length > 0 && (
          <select
            value={typeFilter}
            onChange={e => { setTypeFilter(e.target.value ? Number(e.target.value) : ''); setFocusedIdx(0); setPage(0); }}
            className="border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">Все типы</option>
            {(Array.isArray(productTypes) ? productTypes : []).map(t => (
              <option key={t.id} value={t.id}>{t.name_ru}</option>
            ))}
          </select>
        )}
        {categoryOptions.length > 0 && (
          <select
            value={categoryFilter}
            onChange={e => { setCategoryFilter(e.target.value ? Number(e.target.value) : ''); setFocusedIdx(0); setPage(0); }}
            className="border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
          >
            <option value="">Все категории</option>
            {categoryOptions.map(c => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
        )}
        <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={noType}
            onChange={e => { setNoType(e.target.checked); setPage(0); setFocusedIdx(0); }}
            className="rounded"
          />
          Без типа
        </label>
        <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={noCategory}
            onChange={e => { setNoCategory(e.target.checked); setPage(0); setFocusedIdx(0); }}
            className="rounded"
          />
          Без категории
        </label>
      </div>

      {issueFilter === '__GROUP_MXIK__' && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="font-medium">Режим GROUP_MXIK</div>
          <div className="mt-1 text-xs text-amber-800">
            Здесь показываются все товары, которые уже попали в отдельный поток группового ИКПУ. Навигация и кнопка
            “Следующий” дальше будут работать только внутри этого workflow.
          </div>
          <div className="mt-3 flex items-center gap-2">
            <label className="text-xs font-medium text-amber-900">Групповой ИКПУ</label>
            <select
              value={groupCodeFilter}
              onChange={e => applyGroupCodeFilter(e.target.value)}
              className="min-w-[24rem] max-w-full border border-amber-300 bg-white rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400"
            >
              <option value="">Все групповые ИКПУ</option>
              {(groupMxikBuckets ?? []).map(bucket => (
                <option key={bucket.mxik_code} value={bucket.mxik_code}>
                  {bucket.mxik_code} · {bucket.mxik_name_ru ?? 'Без названия'} · {bucket.total}
                </option>
              ))}
            </select>
            {groupCodeFilter && (
              <button
                onClick={() => applyGroupCodeFilter('')}
                className="text-xs text-amber-700 hover:text-amber-900 underline"
              >
                Сбросить
              </button>
            )}
          </div>
          {groupCodeFilter && (
            <div className="mt-2 text-xs text-amber-800">
              Показаны только карточки с групповым ИКПУ <span className="font-mono">{groupCodeFilter}</span>.
            </div>
          )}
        </div>
      )}

      {issueFilter === '__NON_GROUP__' && (
        <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          <div className="font-medium">Рабочий хвост без GROUP_MXIK</div>
          <div className="mt-1 text-xs text-blue-800">
            Здесь остались только обычные карточки качества данных: без бренда, типа, ИКПУ или с внутренним ШК.
          </div>
        </div>
      )}

      {selected.size > 0 && (
        <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm">
          <span className="text-blue-700 font-medium">Выбрано: {selected.size}</span>
          <button
            onClick={() => batchAction('confirm_product')}
            disabled={batching || !operatorId}
            className="flex items-center gap-1 px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 text-xs"
          >
            <CheckCheck size={12} /> {issueFilter === '__GROUP_MXIK__' ? 'Подтвердить GROUP_MXIK' : 'Подтвердить'}
          </button>
          <button
            onClick={() => batchAction('dismiss')}
            disabled={batching || !operatorId}
            className="flex items-center gap-1 px-2 py-1 bg-gray-500 text-white rounded hover:bg-gray-600 disabled:opacity-50 text-xs"
          >
            <X size={12} /> Убрать из очереди
          </button>
          <span className="w-px h-4 bg-blue-200 mx-1" />
          <select
            defaultValue=""
            onChange={e => { if (e.target.value) { batchAction('set_type', Number(e.target.value)); e.target.value = ''; } }}
            disabled={batching || !operatorId}
            className="border border-blue-300 rounded px-1.5 py-1 text-xs bg-white disabled:opacity-50 max-w-36"
          >
            <option value="">Назначить тип...</option>
            {(Array.isArray(productTypes) ? productTypes : []).map(t => (
              <option key={t.id} value={t.id}>{t.name_ru}</option>
            ))}
          </select>
          <select
            defaultValue=""
            onChange={e => { if (e.target.value) { batchAction('set_category', Number(e.target.value)); e.target.value = ''; } }}
            disabled={batching || !operatorId}
            className="border border-blue-300 rounded px-1.5 py-1 text-xs bg-white disabled:opacity-50 max-w-36"
          >
            <option value="">Назначить категорию...</option>
            {categoryOptions.map(c => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-xs text-gray-500 hover:text-gray-700"
          >
            Снять выделение
          </button>
        </div>
      )}

      {items.length === 0 ? (
        <div className="bg-white border rounded-lg p-12 text-center text-gray-400">
          Очередь пуста
        </div>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-3 py-2 w-8">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="cursor-pointer"
                  />
                </th>
                <SortTh col="name" label="Название" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
                <SortTh col="brand" label="Бренд" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="w-36" />
                <SortTh col="confidence" label="Confidence" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} className="w-28" />
                <th className="text-left px-3 py-2 text-xs text-gray-500 font-medium">Причина ревью</th>
                <th className="w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((p, idx) => (
                <tr
                  key={p.product_id}
                  ref={el => { rowRefs.current[idx] = el; }}
                  onClick={() => openReview(p.product_id)}
                  onMouseEnter={e => { setFocusedIdx(idx); showPreview(p, e.currentTarget); }}
                  onMouseLeave={hidePreview}
                  className={`cursor-pointer transition-colors ${
                    focusedIdx === idx ? 'bg-blue-100' : selected.has(p.product_id) ? 'bg-blue-50' : 'hover:bg-blue-50'
                  }`}
                >
                  <td className="px-3 py-2" onClick={e => toggleOne(p.product_id, e)}>
                    <input
                      type="checkbox"
                      checked={selected.has(p.product_id)}
                      onChange={() => {}}
                      className="cursor-pointer"
                    />
                  </td>
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
                      {(p.review_reasons ?? []).slice(0, 2).map(reason => (
                        <IssueBadge key={`reason-${reason}`} issue={reason} />
                      ))}
                      {(p.issues ?? [])
                        .filter(issue => !(p.review_reasons ?? []).includes(issue))
                        .slice(0, 2)
                        .map(issue => (
                          <IssueBadge key={`issue-${issue}`} issue={issue} compact />
                        ))}
                      {((p.review_reasons?.length ?? 0) + (p.issues?.length ?? 0)) > 4 && (
                        <span className="text-xs text-gray-400">
                          +{((p.review_reasons?.length ?? 0) + (p.issues?.length ?? 0)) - 4}
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

      {/* Пагинация */}
      {(data?.total ?? 0) > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-3 text-sm">
          <button
            onClick={() => { setPage(p => p - 1); setFocusedIdx(0); setSelected(new Set()); }}
            disabled={page === 0}
            className="px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ← Назад
          </button>
          <span className="text-gray-500 text-xs">
            Страница {page + 1} / {Math.ceil((data?.total ?? 0) / PAGE_SIZE)}
            &nbsp;·&nbsp; всего {data?.total ?? 0} товаров
          </span>
          <button
            onClick={() => { setPage(p => p + 1); setFocusedIdx(0); setSelected(new Set()); }}
            disabled={(page + 1) * PAGE_SIZE >= (data?.total ?? 0)}
            className="px-3 py-1.5 border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Вперёд →
          </button>
        </div>
      )}

      {items.length > 0 && (
        <div className="mt-2 text-xs text-gray-400 text-right">
          j/k — навигация &nbsp;·&nbsp; Space — выбор &nbsp;·&nbsp; Enter — открыть
        </div>
      )}

      {/* Hover preview */}
      {preview && (
        <div
          className="fixed z-50 w-72 bg-white border rounded-lg shadow-xl p-3 text-xs pointer-events-none"
          style={{ top: Math.min(preview.y, window.innerHeight - 220), right: 16 }}
        >
          <div className="font-semibold text-sm text-gray-900 mb-2 leading-tight">
            {preview.product.name_canonical ?? preview.product.name_raw ?? '—'}
          </div>
          <div className="space-y-1 text-gray-600">
            {preview.product.name_raw && preview.product.name_raw !== preview.product.name_canonical && (
              <div><span className="text-gray-400">Исходное: </span>{preview.product.name_raw}</div>
            )}
            {preview.product.name_uz_latn && (
              <div><span className="text-gray-400">Уз. лат.: </span>{preview.product.name_uz_latn}</div>
            )}
            {preview.product.brand_name && (
              <div><span className="text-gray-400">Бренд: </span><span className="font-medium">{preview.product.brand_name}</span></div>
            )}
            {preview.product.mxik_code && (
              <div><span className="text-gray-400">ИКПУ: </span><span className="font-mono">{preview.product.mxik_code}</span></div>
            )}
            {(preview.product.barcodes?.length ?? 0) > 0 && (
              <div><span className="text-gray-400">ШК: </span>{preview.product.barcodes.join(', ')}</div>
            )}
            {((preview.product.review_reasons?.length ?? 0) > 0 || (preview.product.issues?.length ?? 0) > 0) && (
              <div className="mt-1 space-y-1">
                {(preview.product.review_reasons?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {preview.product.review_reasons!.map(reason => <IssueBadge key={`preview-reason-${reason}`} issue={reason} />)}
                  </div>
                )}
                {(preview.product.issues?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {preview.product.issues!.map(i => <IssueBadge key={`preview-issue-${i}`} issue={i} compact />)}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SortTh({
  col, label, sortBy, sortDir, onSort, className = '',
}: {
  col: string; label: string; sortBy: string; sortDir: 'asc' | 'desc';
  onSort: (col: string) => void; className?: string;
}) {
  const active = sortBy === col;
  return (
    <th
      className={`text-left px-3 py-2 text-xs text-gray-500 font-medium cursor-pointer select-none hover:text-gray-800 ${className}`}
      onClick={() => onSort(col)}
    >
      <span className="flex items-center gap-0.5">
        {label}
        {active
          ? sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />
          : <ChevronUp size={12} className="opacity-20" />}
      </span>
    </th>
  );
}
