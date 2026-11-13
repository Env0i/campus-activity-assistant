import { render13 } from '../views/v13.mjs';

window.__esmOrder.push('s13');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v13.mjs 又 import 回 state13
export const state13 = { id: 13, name: 'state-13' };

export function snapshot13() {
  return { id: 13, label: 'state-13', card: render13() };
}
