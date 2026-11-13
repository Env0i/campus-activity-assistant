import { render08 } from '../views/v08.mjs';

window.__esmOrder.push('s08');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v08.mjs 又 import 回 state08
export const state08 = { id: 8, name: 'state-08' };

export function snapshot08() {
  return { id: 8, label: 'state-08', card: render08() };
}
