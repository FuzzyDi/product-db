import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
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

  const { data, isLoading } = useQuery({
    queryKey: ['refs/brands', search],
    queryFn: () =>
      api.get<Brand[]>(`/refs/brands${search ? `?q=${encodeURIComponent(search)}` : ''}`),
  });

  async function createBrand() {
    if (!newName.trim()) return;
    await api.post('/refs/brands', { name: newName.trim() });
    setNewName('');
    qc.invalidateQueries({ queryKey: ['refs/brands'] });
  }

  async function addAlias(brandId: number) {
    const alias = aliasInputs[brandId]?.trim();
    if (!alias) return;
    await api.post(`/refs/brands/${brandId}/aliases`, { alias });
    setAliasInputs(prev => ({ ...prev, [brandId]: '' }));
    qc.invalidateQueries({ queryKey: ['refs/brands'] });
  }

  const brands = Array.isArray(data) ? data : [];
  const preview = newName ? newName.toUpperCase() : null;

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-lg font-semibold mb-4">Бренды</h1>

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

      {/* Search */}
      <input
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Поиск..."
        className="w-full border rounded px-3 py-1.5 text-sm mb-3 focus:outline-none focus:ring-1 focus:ring-blue-400"
      />

      {/* List */}
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
                <span className="font-semibold text-sm">{b.name_canonical}</span>
                <span className="text-xs text-gray-400">ID {b.id}</span>
              </button>

              {expanded === b.id && (
                <div className="border-t px-3 py-2 bg-gray-50">
                  <div className="text-xs text-gray-500 mb-1.5">Добавить псевдоним</div>
                  <div className="flex gap-2">
                    <input
                      value={aliasInputs[b.id] ?? ''}
                      onChange={e =>
                        setAliasInputs(prev => ({ ...prev, [b.id]: e.target.value }))
                      }
                      onKeyDown={e => e.key === 'Enter' && addAlias(b.id)}
                      placeholder="Напр: nestle, Нестле..."
                      className="flex-1 border rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
                    />
                    <button
                      onClick={() => addAlias(b.id)}
                      className="bg-gray-700 text-white px-2 py-1 rounded text-xs hover:bg-gray-900"
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
  );
}
