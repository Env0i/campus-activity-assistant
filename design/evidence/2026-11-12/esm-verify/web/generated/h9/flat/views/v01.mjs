import { state01 } from '../state/s01.mjs';

window.__esmOrder.push('v01');
window.__esmCount = (window.__esmCount || 0) + 1;

// 与 state/s01.mjs 构成函数调用期的循环引用（只在调用时才互相读）
export function render01() {
  return 'card-' + state01.id;
}

export const view01 = { id: 1, name: 'view-01' };
