import { render09 } from '../views/v09.mjs';

window.__esmOrder.push('s09');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v09.mjs 又 import 回 state09
export const state09 = { id: 9, name: 'state-09' };

export function snapshot09() {
  return { id: 9, label: 'state-09', card: render09() };
}
