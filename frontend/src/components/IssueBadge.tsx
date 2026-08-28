import { cn } from '@/lib/utils';

const CRITICAL = new Set([
  'BARCODE_CONFLICT',
  'INTERNAL_BC_AS_GLOBAL',
  'BRAND_TYPE_MISMATCH',
]);

const LABELS: Record<string, string> = {
  GROUP_MXIK: 'Групповой ИКПУ',
  INTERNAL_BC_AS_GLOBAL: 'Внутренний ШК как глобальный',
  MISSING_MXIK: 'Нет ИКПУ',
  MISSING_BRAND: 'Нет бренда',
  MISSING_PRODUCT_TYPE: 'Нет типа',
  MISSING_QUANTITY: 'Нет количества',
  FUZZY_MATCH: 'Нечёткое совпадение',
  LOW_CONFIDENCE: 'Низкая уверенность',
  BARCODE_CONFLICT: 'Конфликт штрихкода',
  BRAND_TYPE_MISMATCH: 'Конфликт бренда и типа',
};

interface Props {
  issue: string;
  compact?: boolean;
}

export default function IssueBadge({ issue, compact = false }: Props) {
  const isCritical = CRITICAL.has(issue);
  const label = compact ? issue : (LABELS[issue] ?? issue);
  return (
    <span
      className={cn(
        'inline-block text-xs px-1.5 py-0.5 rounded font-mono',
        isCritical
          ? 'bg-red-100 text-red-700 border border-red-200'
          : 'bg-orange-50 text-orange-700 border border-orange-200',
      )}
      title={issue}
    >
      {label}
    </span>
  );
}
