import { render10 } from '../views/v10.mjs';

window.__esmOrder.push('s10');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v10.mjs 又 import 回 state10
export const state10 = { id: 10, name: 'state-10' };

export function snapshot10() {
  return { id: 10, label: 'state-10', card: render10() };
}
