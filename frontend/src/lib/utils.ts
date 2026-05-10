import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(val: string | number | null | undefined, unit?: string): string {
  if (val == null) return '—';
  return unit ? `${val} ${unit}` : String(val);
}

export function pct(val: string | number | null | undefined): string {
  if (val == null) return '—';
  return `${Math.round(Number(val) * 100)}%`;
}
