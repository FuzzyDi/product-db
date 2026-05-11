import { useRef, useState } from 'react';
import * as XLSX from 'xlsx';
import { toast } from 'sonner';
import { Upload, FileSpreadsheet, Play, CheckCircle, XCircle } from 'lucide-react';
import { api } from '@/api/client';

// Маппинг заголовков XLSX → поля API
const COLUMN_MAP: Record<string, string> = {
  'наименование': 'name',
  'название': 'name',
  'name': 'name',
  'штрихкод': 'barcode',
  'barcode': 'barcode',
  'ean': 'barcode',
  'код': 'internal_code',
  'код товара': 'internal_code',
  'артикул': 'internal_code',
  'базовая единица измерения': 'uom',
  'единица измерения': 'uom',
  'ед. изм.': 'uom',
  'цена закупка': 'price_purchase',
  'цена розница': 'price_retail',
  'цена': 'price_retail',
};

interface ParsedRow {
  name: string;
  barcode?: string;
  internal_code?: string;
  uom?: string;
  price_purchase?: string;
  price_retail?: string;
}

function mapHeader(h: string): string {
  return COLUMN_MAP[h.trim().toLowerCase()] ?? h.trim().toLowerCase();
}

function parseSheet(file: File): Promise<ParsedRow[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target!.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: 'array' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const raw: Record<string, unknown>[] = XLSX.utils.sheet_to_json(ws, { defval: '' });
        const rows: ParsedRow[] = raw
          .map((row) => {
            const mapped: Record<string, string> = {};
            for (const [k, v] of Object.entries(row)) {
              const field = mapHeader(k);
              if (v !== '' && v != null) mapped[field] = String(v).trim();
            }
            return mapped as ParsedRow;
          })
          .filter((r) => r.name && r.name !== 'None');
        resolve(rows);
      } catch (err) {
        reject(err);
      }
    };
    reader.onerror = reject;
    reader.readAsArrayBuffer(file);
  });
}

function buildItem(row: ParsedRow, sourceId: string) {
  const extra: Record<string, string> = {};
  if (row.internal_code) extra.internal_code = row.internal_code;
  if (row.uom) extra.uom = row.uom;
  if (row.price_purchase) extra.price_purchase = row.price_purchase;
  if (row.price_retail) extra.price_retail = row.price_retail;

  let barcode = row.barcode;
  if (barcode && /^[\d.]+$/.test(barcode)) {
    barcode = String(Math.round(Number(barcode)));
  }

  return { name: row.name, barcode: barcode || null, source_id: sourceId, extra };
}

const BATCH_SIZE = 100;

interface DuplicateWarning {
  type: 'barcode' | 'name';
  value: string;
  rows: number[];
}

function findDuplicates(rows: ParsedRow[]): DuplicateWarning[] {
  const barcodeMap = new Map<string, number[]>();
  const nameMap = new Map<string, number[]>();

  rows.forEach((r, i) => {
    const rowNum = i + 2; // +2 т.к. строка 1 — заголовок
    if (r.barcode) {
      const key = r.barcode.trim();
      barcodeMap.set(key, [...(barcodeMap.get(key) ?? []), rowNum]);
    }
    if (r.name) {
      const key = r.name.trim().toLowerCase();
      nameMap.set(key, [...(nameMap.get(key) ?? []), rowNum]);
    }
  });

  const warnings: DuplicateWarning[] = [];
  for (const [value, rows] of barcodeMap)
    if (rows.length > 1) warnings.push({ type: 'barcode', value, rows });
  for (const [value, rows] of nameMap)
    if (rows.length > 1) warnings.push({ type: 'name', value, rows });

  return warnings;
}

export default function XlsxImport() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateWarning[]>([]);
  const [dupsExpanded, setDupsExpanded] = useState(false);
  const [sourceId, setSourceId] = useState('xlsx_import');
  const [status, setStatus] = useState<'idle' | 'parsing' | 'ready' | 'running' | 'done' | 'error'>('idle');
  const [progress, setProgress] = useState({ sent: 0, total: 0, tasks: 0, errors: 0, batch: 0, totalBatches: 0 });
  const [batchErrors, setBatchErrors] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState('');
  const [dragging, setDragging] = useState(false);

  async function handleFile(f: File) {
    setFile(f);
    setStatus('parsing');
    try {
      const parsed = await parseSheet(f);
      setRows(parsed);
      setDuplicates(findDuplicates(parsed));
      setDupsExpanded(false);
      setStatus('ready');
    } catch (e) {
      setErrorMsg(String(e));
      setStatus('error');
    }
  }

  async function startImport() {
    setStatus('running');
    setBatchErrors([]);
    const items = rows.map((r) => buildItem(r, sourceId));
    let sent = 0, tasks = 0, errors = 0;
    const errs: string[] = [];
    const totalBatches = Math.ceil(items.length / BATCH_SIZE);
    setProgress({ sent: 0, total: items.length, tasks: 0, errors: 0, batch: 0, totalBatches });

    for (let i = 0; i < items.length; i += BATCH_SIZE) {
      const batch = items.slice(i, i + BATCH_SIZE);
      const batchNum = Math.floor(i / BATCH_SIZE) + 1;
      setProgress(p => ({ ...p, batch: batchNum }));

      // Retry при 429 — ждём и повторяем
      let attempt = 0;
      while (attempt < 3) {
        try {
          const result = await api.post<{ task_ids: string[] }>('/intake/batch', { items: batch });
          tasks += result.task_ids?.length ?? 0;
          break;
        } catch (e) {
          const msg = String(e);
          if (msg.includes('429') || msg.toLowerCase().includes('rate') && attempt < 2) {
            attempt++;
            await new Promise(r => setTimeout(r, 3000 * attempt));
          } else {
            errors += batch.length;
            errs.push(`Пакет ${batchNum} (строки ${i + 1}–${i + batch.length}): ${msg}`);
            setBatchErrors([...errs]);
            break;
          }
        }
      }

      sent += batch.length;
      setProgress({ sent, total: items.length, tasks, errors, batch: batchNum, totalBatches });
      if (i + BATCH_SIZE < items.length) await new Promise(r => setTimeout(r, 600));
    }
    setStatus('done');
    if (errors === 0) {
      toast.success(`Импорт завершён: ${items.length} строк отправлено`);
    } else {
      toast.warning(`Импорт завершён с ошибками: ${errors} из ${items.length} не отправлено`);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-xl font-semibold mb-5">Импорт из XLSX</h1>

      {/* Dropzone */}
      {status === 'idle' || status === 'error' ? (
        <div
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
            dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'
          }`}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <Upload size={36} className="mx-auto mb-3 text-gray-400" />
          <p className="text-gray-600 font-medium">Перетащите XLSX файл или нажмите для выбора</p>
          <p className="text-sm text-gray-400 mt-1">Колонки: Наименование, Штрихкод, Код, Единица, Цена</p>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />
          {status === 'error' && (
            <p className="mt-3 text-red-500 text-sm">{errorMsg}</p>
          )}
        </div>
      ) : null}

      {/* Parsing */}
      {status === 'parsing' && (
        <div className="border rounded-lg p-8 text-center text-gray-500">
          Читаю файл...
        </div>
      )}

      {/* Ready */}
      {(status === 'ready' || status === 'running' || status === 'done') && (
        <div className="space-y-4">
          {/* File info */}
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border">
            <FileSpreadsheet size={20} className="text-green-600" />
            <div className="flex-1">
              <p className="text-sm font-medium">{file?.name}</p>
              <p className="text-xs text-gray-500">{rows.length} товаров</p>
            </div>
            {status === 'ready' && (
              <button
                className="text-xs text-gray-400 hover:text-gray-600"
                onClick={() => { setFile(null); setRows([]); setStatus('idle'); }}
              >
                Другой файл
              </button>
            )}
          </div>

          {/* Source ID */}
          {status === 'ready' && (
            <div className="flex items-center gap-3">
              <label className="text-sm text-gray-600 w-32 flex-shrink-0">Источник (source_id)</label>
              <input
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
                className="border rounded px-3 py-1.5 text-sm flex-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
          )}

          {/* Preview table */}
          {status === 'ready' && rows.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-3 py-2 text-xs font-medium text-gray-500 border-b">
                Предпросмотр (первые 5 строк)
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Название</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Штрихкод</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Код</th>
                      <th className="text-left px-3 py-2 font-medium text-gray-600">Ед. изм.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, 5).map((r, i) => (
                      <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="px-3 py-2 max-w-xs truncate">{r.name}</td>
                        <td className="px-3 py-2 text-gray-500">{r.barcode || '—'}</td>
                        <td className="px-3 py-2 text-gray-500">{r.internal_code || '—'}</td>
                        <td className="px-3 py-2 text-gray-500">{r.uom || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Progress */}
          {(status === 'running' || status === 'done') && (
            <div className="border rounded-lg p-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">
                  {status === 'done'
                    ? 'Завершено'
                    : `Батч ${progress.batch} / ${progress.totalBatches}`}
                </span>
                <span className="font-medium tabular-nums">
                  {progress.sent} / {progress.total} строк
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${status === 'done' ? 'bg-green-500' : 'bg-blue-500'}`}
                  style={{ width: `${progress.total ? (progress.sent / progress.total) * 100 : 0}%` }}
                />
              </div>
              <div className="flex gap-4 text-sm">
                <span className="flex items-center gap-1 text-green-600">
                  <CheckCircle size={14} />
                  Задач Celery: {progress.tasks}
                </span>
                {progress.errors > 0 && (
                  <span className="flex items-center gap-1 text-red-500">
                    <XCircle size={14} />
                    Ошибок: {progress.errors}
                  </span>
                )}
              </div>
              {status === 'done' && (
                <p className="text-sm text-gray-500">
                  Товары обрабатываются в фоне. Результаты появятся в разделе "Ревью" и "Товары".
                </p>
              )}
              {batchErrors.length > 0 && (
                <div className="mt-2 space-y-1">
                  {batchErrors.map((e, i) => (
                    <p key={i} className="text-xs text-red-500 font-mono break-all">{e}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Предупреждения о дублях */}
          {status === 'ready' && duplicates.length > 0 && (
            <div className="border border-yellow-300 bg-yellow-50 rounded-lg overflow-hidden">
              <button
                onClick={() => setDupsExpanded(e => !e)}
                className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-yellow-800 hover:bg-yellow-100"
              >
                <span className="font-medium">
                  ⚠ Найдено {duplicates.length} дублей в файле — проверьте перед импортом
                </span>
                <span className="text-xs text-yellow-600">{dupsExpanded ? 'Скрыть' : 'Показать'}</span>
              </button>
              {dupsExpanded && (
                <div className="border-t border-yellow-200 divide-y divide-yellow-100 max-h-48 overflow-y-auto">
                  {duplicates.map((d, i) => (
                    <div key={i} className="px-4 py-2 text-xs text-yellow-900 flex gap-3">
                      <span className={`flex-shrink-0 font-medium ${d.type === 'barcode' ? 'text-red-600' : 'text-yellow-700'}`}>
                        {d.type === 'barcode' ? 'ШК' : 'Название'}
                      </span>
                      <span className="truncate flex-1">{d.value}</span>
                      <span className="flex-shrink-0 text-yellow-600">строки {d.rows.join(', ')}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Кнопка */}
          {status === 'ready' && (
            <button
              onClick={startImport}
              disabled={rows.length === 0}
              className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              <Play size={16} />
              Начать импорт ({rows.length} товаров)
              {duplicates.length > 0 && (
                <span className="ml-1 text-xs bg-yellow-400 text-yellow-900 px-1.5 py-0.5 rounded">
                  {duplicates.length} дублей
                </span>
              )}
            </button>
          )}

          {status === 'done' && (
            <button
              onClick={() => { setFile(null); setRows([]); setStatus('idle'); setProgress({ sent: 0, total: 0, tasks: 0, errors: 0 }); setBatchErrors([]); }}
              className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium"
            >
              Загрузить ещё файл
            </button>
          )}
        </div>
      )}
    </div>
  );
}
