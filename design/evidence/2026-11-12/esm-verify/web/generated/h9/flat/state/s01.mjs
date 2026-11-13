import { render01 } from '../views/v01.mjs';

window.__esmOrder.push('s01');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v01.mjs 又 import 回 state01
export const state01 = { id: 1, name: 'state-01' };

export function snapshot01() {
  return { id: 1, label: 'state-01', card: render01() };
}
