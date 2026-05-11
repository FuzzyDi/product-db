import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '@/api/client';
import type { Brand } from '@/types';

interface BrandsData {
  items?: Brand[];
}

export default function BrandManager() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [newName, setNewName] = useState('');
  const [aliasInputs, setAliasInputs] = useState<Record<number, string>>({});
  const [expanded, setExpanded] = useState<number | null>(null);
  const [unrecognizedOpen, setUnrecognizedOpen] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessResult, setReprocessResult] = useState<{ updated: number; checked: number } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['refs/brands', search],
    queryFn: () =>
      api.get<Brand[]>(`/refs/brands${search ? `?q=${encodeURIComponent(search)}` : ''}`),
  });

  const { data: unrecognized } = useQuery({
    queryKey: ['refs/brands/unrecognized'],
    queryFn: () => api.get<{ token: string; count: number }[]>('/refs/brands/unrecognized'),
    enabled: unrecognizedOpen,
    staleTime: 60_000,
  });

  async function createBrand() {
    if (!newName.trim()) return;
    await api.post('/refs/brands', { name: newName.trim() });
    setNewName('');
    qc.invalidateQueries({ queryKey: ['refs/brands'] });
  }

  async function reprocess() {
    setReprocessing(true);
    setReprocessResult(null);
    try {
      const res = await api.post<{ updated: number; checked: number }>('/refs/brands/reprocess', {});
      setReprocessResult(res);
      qc.invalidateQueries({ queryKey: ['stats/pipeline'] });
    } finally {
      setReprocessing(false);
    }
  }

  async function addAliases(brandId: number) {
    const raw = aliasInputs[brandId] ?? '';
    const aliases = raw
      .split(/[\n,]+/)
      .map(s => s.trim())
      .filter(Boolean);
    if (aliases.length === 0) return;
    await api.post(`/refs/brands/${brandId}/aliases/batch`, { aliases });
    setAliasInputs(prev => ({ ...prev, [brandId]: '' }));
    qc.invalidateQueries({ queryKey: ['refs/brands'] });
    qc.invalidateQueries({ queryKey: ['refs/brands/unrecognized'] });
  }

  function appendToAliasInput(brandId: number, value: string, autoExpand = true) {
    setAliasInputs(prev => {
      const current = prev[brandId] ?? '';
      const sep = current && !current.endsWith('\n') ? '\n' : '';
      return { ...prev, [brandId]: current + sep + value };
    });
    setExpanded(brandId);
  }

  const brands = Array.isArray(data) ? data : [];
  const preview = newName ? newName.toUpperCase() : null;

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Бренды</h1>
        <div className="flex items-center gap-3">
          {reprocessResult && (
            <span className="text-sm text-green-600">
              Обновлено: {reprocessResult.updated} из {reprocessResult.checked} товаров
            </span>
          )}
          <button
            onClick={reprocess}
            disabled={reprocessing}
            className="flex items-center gap-1.5 border px-3 py-1.5 rounded text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={14} className={reprocessing ? 'animate-spin' : ''} />
            {reprocessing ? 'Обработка...' : 'Перераспознать товары'}
          </button>
        </div>
      </div>

      {/* Create */}
      <div className="bg-white border rounded-lg p-4 mb-4">
        <div className="text-sm font-medium mb-2">Добавить бренд</div>
        <div className="flex gap-2">
          <div className="flex-1">
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && createBrand()}
              placeholder="Название бренда..."
              className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            {preview && (
              <div className="mt-1 text-xs text-gray-500">
                Будет сохранено как: <span className="font-bold text-gray-800">{preview}</span>
              </div>
            )}
          </div>
          <button
            onClick={createBrand}
            className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700"
          >
            <Plus size={14} /> Добавить
          </button>
        </div>
      </div>

      <div className="flex gap-4">
        {/* Left: brands list */}
        <div className="flex-1 min-w-0">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Поиск..."
            className="w-full border rounded px-3 py-1.5 text-sm mb-3 focus:outline-none focus:ring-1 focus:ring-blue-400"
          />

          {isLoading ? (
            <div className="text-gray-400 text-sm">Загрузка...</div>
          ) : (
            <div className="space-y-1">
              {brands.map(b => (
                <div key={b.id} className="bg-white border rounded-lg overflow-hidden">
                  <button
                    onClick={() => setExpanded(expanded === b.id ? null : b.id)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-left hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-2">
                      {expanded === b.id ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                      <span className="font-semibold text-sm">{b.name_canonical}</span>
                      {b.aliases.length > 0 && (
                        <span className="text-xs text-gray-400">{b.aliases.length} алиасов</span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">ID {b.id}</span>
                  </button>

                  {expanded === b.id && (
                    <div className="border-t px-3 py-2 bg-gray-50 space-y-2">
                      {/* Existing aliases */}
                      {b.aliases.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {b.aliases.map(a => (
                            <span key={a} className="text-xs bg-white border rounded px-1.5 py-0.5 text-gray-600">
                              {a}
                            </span>
                          ))}
                        </div>
                      )}
                      {/* Add aliases */}
                      <div>
                        <div className="text-xs text-gray-500 mb-1">
                          Добавить псевдонимы (через запятую или новую строку)
                        </div>
                        <textarea
                          value={aliasInputs[b.id] ?? ''}
                          onChange={e => setAliasInputs(prev => ({ ...prev, [b.id]: e.target.value }))}
                          rows={3}
                          placeholder={"nestle\nНестле\nNESTLE"}
                          className="w-full border rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400 resize-none font-mono"
                        />
                        <button
                          onClick={() => addAliases(b.id)}
                          className="mt-1 bg-gray-700 text-white px-3 py-1 rounded text-xs hover:bg-gray-900"
                        >
                          Добавить
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: unrecognized panel */}
        <div className="w-72 flex-shrink-0">
          <button
            onClick={() => setUnrecognizedOpen(o => !o)}
            className="w-full flex items-center justify-between px-3 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50 mb-2"
          >
            <span>Нераспознанные</span>
            {unrecognizedOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          {unrecognizedOpen && (
            <div className="border rounded-lg bg-white overflow-hidden">
              <div className="px-3 py-2 text-xs text-gray-400 border-b">
                {expanded !== null
                  ? 'Клик → добавить в алиасы раскрытого бренда'
                  : 'Раскройте бренд, затем кликайте'}
              </div>
              <div className="max-h-96 overflow-y-auto">
                {(unrecognized ?? []).map(({ token, count }) => (
                  <button
                    key={token}
                    onClick={() => expanded !== null && appendToAliasInput(expanded, token)}
                    disabled={expanded === null}
                    className="w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-between gap-2 border-b last:border-0"
                    title={expanded === null ? 'Сначала раскройте бренд' : `Добавить "${token}" как алиас`}
                  >
                    <span className="font-medium truncate">{token}</span>
                    <span className="flex-shrink-0 text-gray-400 tabular-nums">{count}</span>
                  </button>
                ))}
                {(unrecognized ?? []).length === 0 && (
                  <div className="px-3 py-4 text-xs text-gray-400 text-center">Все распознаны</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
