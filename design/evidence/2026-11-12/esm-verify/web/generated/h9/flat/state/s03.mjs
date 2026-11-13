import { render03 } from '../views/v03.mjs';

window.__esmOrder.push('s03');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v03.mjs 又 import 回 state03
export const state03 = { id: 3, name: 'state-03' };

export function snapshot03() {
  return { id: 3, label: 'state-03', card: render03() };
}
