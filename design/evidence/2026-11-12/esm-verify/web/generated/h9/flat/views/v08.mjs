import { state08 } from '../state/s08.mjs';

window.__esmOrder.push('v08');
window.__esmCount = (window.__esmCount || 0) + 1;

// 与 state/s08.mjs 构成函数调用期的循环引用（只在调用时才互相读）
export function render08() {
  return 'card-' + state08.id;
}

export const view08 = { id: 8, name: 'view-08' };
