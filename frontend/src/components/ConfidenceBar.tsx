import { cn } from '@/lib/utils';

interface Props {
  value: string | number | null;
  showLabel?: boolean;
}

export default function ConfidenceBar({ value, showLabel = true }: Props) {
  const num = value == null ? null : Number(value);
  if (num == null) return <span className="text-gray-400 text-xs">—</span>;

  const pct = Math.round(num * 100);
  const color =
    num >= 0.8 ? 'bg-green-500' : num >= 0.6 ? 'bg-yellow-400' : 'bg-red-500';
  const textColor =
    num >= 0.8 ? 'text-green-700' : num >= 0.6 ? 'text-yellow-700' : 'text-red-600';

  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      {showLabel && (
        <span className={cn('text-xs font-medium tabular-nums', textColor)}>{pct}%</span>
      )}
    </div>
  );
}
