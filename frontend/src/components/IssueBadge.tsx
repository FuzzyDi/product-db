import { cn } from '@/lib/utils';

const CRITICAL = new Set([
  'BARCODE_CONFLICT',
  'INTERNAL_BC_AS_GLOBAL',
  'BRAND_TYPE_MISMATCH',
]);

interface Props {
  issue: string;
}

export default function IssueBadge({ issue }: Props) {
  const isCritical = CRITICAL.has(issue);
  return (
    <span
      className={cn(
        'inline-block text-xs px-1.5 py-0.5 rounded font-mono',
        isCritical
          ? 'bg-red-100 text-red-700 border border-red-200'
          : 'bg-orange-50 text-orange-700 border border-orange-200',
      )}
    >
      {issue}
    </span>
  );
}
