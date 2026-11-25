/* 活动类型标签与筛选纯规则（只读活动对象与筛选状态，不碰 DOM）。 */

export function activityTypeOf(item) {
  const raw = item && item.type;
  const text = raw === null || raw === undefined ? "" : String(raw).trim();
  return text || "其他";
}

/* 列表里出现过的全部活动类型（含当前已选但暂不在列表里的类型）：按中文排序，兜底「其他」放末尾 */
export function availableTypes(items, selectedTypes) {
  const seen = new Set();
  (items || []).forEach((item) => { seen.add(activityTypeOf(item)); });
  normalizeTypeFilter(selectedTypes).forEach((t) => { seen.add(t); });
  const list = Array.from(seen).sort((a, b) => a.localeCompare(b, "zh-CN"));
  const otherIdx = list.indexOf("其他");
  if (otherIdx >= 0) {
    list.splice(otherIdx, 1);
    list.push("其他");
  }
  return list;
}

/* 选中的类型列表：空数组表示不按类型筛选 */
export function normalizeTypeFilter(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  raw.forEach((v) => {
    const t = String(v || "").trim();
    if (t && out.indexOf(t) < 0) out.push(t);
  });
  return out;
}

export function matchesTypeFilter(item, selectedTypes) {
  const list = Array.isArray(selectedTypes) ? selectedTypes : [];
  if (!list.length) return true;
  return list.indexOf(activityTypeOf(item)) >= 0;
}

export function toggleTypeValue(selectedTypes, value) {
  const target = String(value || "").trim();
  const list = normalizeTypeFilter(selectedTypes);
  if (!target) return list;
  const idx = list.indexOf(target);
  if (idx >= 0) list.splice(idx, 1);
  else list.push(target);
  return list;
}
