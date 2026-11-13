import { render02 } from '../views/v02.mjs';

window.__esmOrder.push('s02');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v02.mjs 又 import 回 state02
export const state02 = { id: 2, name: 'state-02' };

export function snapshot02() {
  return { id: 2, label: 'state-02', card: render02() };
}
