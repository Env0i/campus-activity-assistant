// views.mjs — 模拟产品 views 模块，操作 DOM
import { formatActivityName } from './utils.mjs';

export function renderCards(container, items) {
  if (!container) return 0;
  container.innerHTML = '';
  let count = 0;
  for (const item of items) {
    const div = document.createElement('div');
    div.className = 'card';
    div.dataset.id = String(item.id);
    div.textContent = formatActivityName(item.name);
    container.appendChild(div);
    count++;
  }
  return count;
}

export function showTitle(text) {
  const el = document.getElementById('app-title');
  if (el) el.textContent = text;
}
