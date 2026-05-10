import type { Product } from '@/types';

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

export default function ProductEditForm({ product, onChange }: Props) {
  return (
    <div className="space-y-3">
      <Field
        label="Канонич. название"
        value={product.name_canonical}
        onChange={v => onChange({ name_canonical: v })}
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
        <Field
          label="Бренд"
          value={product.brand_name}
          onChange={v => onChange({ brand_name: v.toUpperCase() })}
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
