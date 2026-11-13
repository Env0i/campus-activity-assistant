import { render12 } from '../views/v12.mjs';

window.__esmOrder.push('s12');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v12.mjs 又 import 回 state12
export const state12 = { id: 12, name: 'state-12' };

export function snapshot12() {
  return { id: 12, label: 'state-12', card: render12() };
}
