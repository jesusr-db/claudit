export const CHART_COLORS = [
  '#06b6d4', // cyan
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#22c55e', // green
  '#ec4899', // pink
  '#ef4444', // red
  '#6366f1', // indigo
  '#14b8a6', // teal
];

export function formatNum(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
  return n.toLocaleString();
}

export function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Pivot row-per-entity-per-day data into chart-friendly format */
export function pivotByDay<T extends Record<string, string>>(
  rows: T[],
  dateKey: string,
  nameKey: string,
  valueKey: string,
): { data: Record<string, string | number>[]; keys: string[] } {
  const keySet = new Set<string>();
  const map = new Map<string, Record<string, string | number>>();
  for (const row of rows) {
    const date = row[dateKey];
    const name = row[nameKey];
    const value = Number(row[valueKey]) || 0;
    keySet.add(name);
    if (!map.has(date)) map.set(date, { date });
    map.get(date)![name] = value;
  }
  const keys = [...keySet];
  const data = [...map.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  return { data, keys };
}

/** Dark theme tokens for AI Gateway dashboard cards */
export const DARK = {
  bg: '#0f1724',
  card: '#1a2332',
  border: '#2d3748',
  label: '#94a3b8',
  value: '#f8fafc',
  muted: '#64748b',
  rowBorder: '#1e293b',
} as const;
