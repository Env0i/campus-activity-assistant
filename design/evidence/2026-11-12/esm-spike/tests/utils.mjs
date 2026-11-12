// utils.mjs — 叶子模块，state 和 views 都依赖它
export function formatActivityName(raw) {
  if (!raw) return '';
  return raw.trim().replace(/\s+/g, ' ');
}

export function padDate(d) {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

export const VERSION = '1.0.0';
