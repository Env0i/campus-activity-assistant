import { state03 } from '../state/s03.mjs';

window.__esmOrder.push('v03');
window.__esmCount = (window.__esmCount || 0) + 1;

// 与 state/s03.mjs 构成函数调用期的循环引用（只在调用时才互相读）
export function render03() {
  return 'card-' + state03.id;
}

export const view03 = { id: 3, name: 'view-03' };
