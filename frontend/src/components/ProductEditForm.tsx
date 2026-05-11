import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import type { Brand, Product, ProductType } from '@/types';

interface Category {
  id: number;
  name: string;
  parent_id: number | null;
}

interface FlatOption {
  id: number;
  label: string;
  depth: number;
}

function flattenCategories(categories: Category[]): FlatOption[] {
  const map = new Map<number, Category & { children: Category[] }>();
  categories.forEach(c => map.set(c.id, { ...c, children: [] }));
  const roots: (Category & { children: Category[] })[] = [];
  map.forEach(node => {
    if (node.parent_id == null) roots.push(node);
    else map.get(node.parent_id)?.children.push(node);
  });
  roots.sort((a, b) => a.name.localeCompare(b.name, 'ru'));

  const result: FlatOption[] = [];
  function walk(nodes: (Category & { children: Category[] })[], depth: number) {
    nodes.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    for (const node of nodes) {
      result.push({ id: node.id, label: '\u00a0\u00a0'.repeat(depth) + node.name, depth });
      walk(node.children, depth + 1);
    }
  }
  walk(roots, 0);
  return result;
}

interface Props {
  product: Product;
  onChange: (patch: Partial<Product>) => void;
}

const DANGER_FIELDS = new Set([
  'mxik_code', 'mxik_package_code', 'label_required', 'label_for_check', 'cash_sale',
]);

function Field({
  label,
  value,
  onChange,
  danger,
  maxLength,
  readOnly,
}: {
  label: string;
  value: string | null | undefined;
  onChange?: (v: string) => void;
  danger?: boolean;
  maxLength?: number;
  readOnly?: boolean;
}) {
  return (
    <div>
      <label className="flex items-center gap-1 text-xs text-gray-500 mb-0.5">
        {label}
        {danger && (
          <span className="text-red-500 text-xs" title="Опасное поле — только ручное подтверждение">
            ⚠
          </span>
        )}
        {maxLength && (
          <span className="text-gray-300 ml-auto tabular-nums">
            {(value ?? '').length}/{maxLength}
          </span>
        )}
      </label>
      <input
        value={value ?? ''}
        onChange={e => onChange?.(e.target.value)}
        maxLength={maxLength}
        readOnly={readOnly}
        className={`w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 ${
          danger
            ? 'border-red-200 bg-red-50 focus:ring-red-300'
            : readOnly
            ? 'bg-gray-50 text-gray-500'
            : 'focus:ring-blue-400'
        }`}
      />
    </div>
  );
}

function BrandCombobox({
  value,
  brandId,
  onChange,
}: {
  value: string | null | undefined;
  brandId: number | null | undefined;
  onChange: (patch: { brand_name: string; brand_id: number | null }) => void;
}) {
  const [input, setInput] = useState(value ?? '');
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  // Синхронизируем input если prop изменился снаружи
  useEffect(() => { setInput(value ?? ''); }, [value]);

  const { data } = useQuery({
    queryKey: ['refs/brands', q],
    queryFn: () => api.get<Brand[]>(`/refs/brands${q ? `?q=${encodeURIComponent(q)}` : ''}`),
    enabled: open,
    staleTime: 30_000,
  });
  const brands = Array.isArray(data) ? data : [];

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  function handleInput(v: string) {
    setInput(v);
    setQ(v);
    onChange({ brand_name: v.toUpperCase(), brand_id: null });
    setOpen(true);
  }

  function select(b: Brand) {
    setInput(b.name_canonical);
    onChange({ brand_name: b.name_canonical, brand_id: b.id });
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <label className="text-xs text-gray-500 mb-0.5 block">
        Бренд
        {brandId && <span className="ml-1 text-gray-300">#{brandId}</span>}
      </label>
      <input
        value={input}
        onChange={e => handleInput(e.target.value)}
        onFocus={() => setOpen(true)}
        placeholder="Введите или выберите..."
        className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
      />
      {open && brands.length > 0 && (
        <div className="absolute z-20 top-full left-0 right-0 mt-0.5 bg-white border rounded shadow-lg max-h-48 overflow-y-auto">
          {brands.slice(0, 10).map(b => (
            <button
              key={b.id}
              onMouseDown={() => select(b)}
              className="w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50 flex items-center justify-between"
            >
              <span className="font-medium">{b.name_canonical}</span>
              <span className="text-xs text-gray-400">{b.aliases.length} алиасов</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProductEditForm({ product, onChange }: Props) {
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
  const categoryOptions = flattenCategories(Array.isArray(categoriesRaw) ? categoriesRaw : []);

  return (
    <div className="space-y-3">
      <Field
        label="Наименование (рус.)"
        value={product.name_canonical}
        onChange={v => onChange({
          name_canonical: v,
          name_pos: v.slice(0, 20),
          name_receipt: v.slice(0, 40),
        })}
      />
      <Field
        label="Наименование (уз. лат.)"
        value={product.name_uz_latn}
        onChange={v => onChange({ name_uz_latn: v })}
      />
      <div className="grid grid-cols-2 gap-2">
        <Field
          label="POS (≤20 симв.)"
          value={product.name_pos}
          onChange={v => onChange({ name_pos: v })}
          maxLength={20}
        />
        <Field
          label="Чек (≤40 симв.)"
          value={product.name_receipt}
          onChange={v => onChange({ name_receipt: v })}
          maxLength={40}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <BrandCombobox
          value={product.brand_name}
          brandId={product.brand_id}
          onChange={patch => onChange(patch)}
        />
        <div>
          <label className="text-xs text-gray-500 mb-0.5 block">Тип товара</label>
          <select
            value={product.product_type_id ?? ''}
            onChange={e => onChange({ product_type_id: e.target.value ? Number(e.target.value) : null })}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 bg-white"
          >
            <option value="">— не задан —</option>
            {(Array.isArray(productTypes) ? productTypes : []).map(t => (
              <option key={t.id} value={t.id}>{t.name_ru}</option>
            ))}
          </select>
        </div>
      </div>
      {categoryOptions.length > 0 && (
        <div>
          <label className="text-xs text-gray-500 mb-0.5 block">Категория</label>
          <select
            value={product.category_id ?? ''}
            onChange={e => onChange({ category_id: e.target.value ? Number(e.target.value) : null })}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 bg-white"
          >
            <option value="">— не задана —</option>
            {categoryOptions.map(opt => (
              <option key={opt.id} value={opt.id}>{opt.label}</option>
            ))}
          </select>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Field
          label="Суббренд"
          value={product.subbrand ?? null}
          onChange={v => onChange({ subbrand: v } as Partial<Product>)}
        />
        <Field
          label="Вариант"
          value={product.variant ?? null}
          onChange={v => onChange({ variant: v } as Partial<Product>)}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field
          label="Объём / кол-во"
          value={product.quantity_value}
          onChange={v => onChange({ quantity_value: v })}
        />
        <Field
          label="Единица"
          value={product.quantity_unit}
          onChange={v => onChange({ quantity_unit: v })}
        />
      </div>
      <Field
        label="Тип упаковки"
        value={product.package_code}
        onChange={v => onChange({ package_code: v })}
      />

      {/* Dangerous fields */}
      <div className="border border-red-200 rounded p-3 space-y-2 bg-red-50/30">
        <div className="text-xs text-red-600 font-medium">Фискальные поля (только оператор)</div>
        <Field label="ИКПУ (MXIK)" value={product.mxik_code} readOnly danger />
        <div className="grid grid-cols-3 gap-2">
          <Field
            label="Маркируемый"
            value={product.label_required != null ? String(product.label_required) : null}
            readOnly
            danger
          />
          <Field
            label="Марка на чек"
            value={product.label_for_check != null ? String(product.label_for_check) : null}
            readOnly
            danger
          />
          <Field
            label="Наличные"
            value={product.cash_sale != null ? String(product.cash_sale) : null}
            readOnly
            danger
          />
        </div>
      </div>
    </div>
  );
}
