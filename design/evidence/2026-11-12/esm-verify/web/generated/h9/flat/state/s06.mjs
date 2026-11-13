import { render06 } from '../views/v06.mjs';

window.__esmOrder.push('s06');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v06.mjs 又 import 回 state06
export const state06 = { id: 6, name: 'state-06' };

export function snapshot06() {
  return { id: 6, label: 'state-06', card: render06() };
}
