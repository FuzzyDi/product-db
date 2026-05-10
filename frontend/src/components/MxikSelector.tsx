import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { api } from '@/api/client';
import type { MxikItem, MxikPackage } from '@/types';
import { cn } from '@/lib/utils';

interface Props {
  selectedMxik: string | null;
  selectedPackageCode: number | null;
  onSelect: (mxik: string, packageCode: number | null) => void;
}

const PACKAGE_TYPE_LABEL: Record<number, string> = {
  1: 'штучный',
  2: 'весовой',
  3: 'прочий',
};

const CASH_SALE_LABEL: Record<number, string> = {
  0: 'запрещено',
  1: 'разрешено',
  2: 'частично',
};

export default function MxikSelector({ selectedMxik, selectedPackageCode, onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [chosenMxik, setChosenMxik] = useState<MxikItem | null>(null);

  const searchQuery = useQuery({
    queryKey: ['mxik/search', query],
    queryFn: () =>
      api.get<{ items: MxikItem[]; count: number }>(`/mxik/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
  });

  const packagesQuery = useQuery({
    queryKey: ['mxik/packages', chosenMxik?.mxik],
    queryFn: () =>
      api.get<{ mxik: string; packages: MxikPackage[] }>(
        `/mxik/${chosenMxik?.mxik}/packages`,
      ),
    enabled: !!chosenMxik,
  });

  function handleSelectMxik(item: MxikItem) {
    setChosenMxik(item);
    if (!packagesQuery.data?.packages?.length) {
      onSelect(item.mxik, null);
    }
  }

  function handleSelectPackage(code: number) {
    onSelect(chosenMxik!.mxik, code);
  }

  return (
    <div className="space-y-2">
      {/* Current value */}
      {selectedMxik && (
        <div className="flex items-center gap-2 text-xs bg-blue-50 border border-blue-200 rounded px-2 py-1.5">
          <span className="font-mono text-blue-700">{selectedMxik}</span>
          {selectedPackageCode && (
            <span className="text-blue-500">/ пакет {selectedPackageCode}</span>
          )}
          <button
            onClick={() => { setChosenMxik(null); onSelect('', null); }}
            className="ml-auto text-gray-400 hover:text-red-500"
          >
            ×
          </button>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Поиск ИКПУ по названию или штрихкоду..."
          className="w-full pl-7 pr-3 py-1.5 border rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
      </div>

      {/* Results */}
      {searchQuery.data && query.length >= 2 && (
        <div className="border rounded max-h-48 overflow-auto divide-y bg-white shadow-sm">
          {searchQuery.data.items.length === 0 ? (
            <div className="px-3 py-2 text-xs text-gray-400">Не найдено</div>
          ) : (
            searchQuery.data.items.map(item => (
              <button
                key={item.mxik}
                onClick={() => handleSelectMxik(item)}
                className={cn(
                  'w-full text-left px-3 py-2 text-xs hover:bg-blue-50 transition-colors',
                  chosenMxik?.mxik === item.mxik && 'bg-blue-50',
                )}
              >
                <div className="flex items-start gap-2">
                  <span className="font-mono text-gray-500 flex-shrink-0">{item.mxik}</span>
                  <div className="flex-1 min-w-0">
                    <div className="truncate">{item.name_ru}</div>
                    <div className="flex gap-2 mt-0.5 text-gray-400">
                      {item.label === 1 && <span className="text-purple-600">маркируемый</span>}
                      <span>наличные: {CASH_SALE_LABEL[item.cash_sale]}</span>
                      {item.is_group_code && <span className="text-orange-500">групповой</span>}
                    </div>
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {/* Package selection */}
      {chosenMxik && packagesQuery.data?.packages && packagesQuery.data.packages.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 mb-1">Выберите упаковку:</div>
          <div className="grid grid-cols-2 gap-1">
            {packagesQuery.data.packages.map(pkg => (
              <button
                key={pkg.code}
                onClick={() => handleSelectPackage(pkg.code)}
                className={cn(
                  'text-left border rounded px-2 py-1.5 text-xs hover:bg-blue-50 transition-colors',
                  selectedPackageCode === pkg.code && 'border-blue-400 bg-blue-50',
                )}
              >
                <div className="font-mono text-gray-500">{pkg.code}</div>
                <div>{pkg.name_ru ?? `Тип ${PACKAGE_TYPE_LABEL[pkg.package_type]}`}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
