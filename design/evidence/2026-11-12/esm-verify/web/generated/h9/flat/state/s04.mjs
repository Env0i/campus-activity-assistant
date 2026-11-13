import { render04 } from '../views/v04.mjs';

window.__esmOrder.push('s04');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v04.mjs 又 import 回 state04
export const state04 = { id: 4, name: 'state-04' };

export function snapshot04() {
  return { id: 4, label: 'state-04', card: render04() };
}
