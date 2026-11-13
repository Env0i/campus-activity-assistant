import { state02 } from '../state/s02.mjs';

window.__esmOrder.push('v02');
window.__esmCount = (window.__esmCount || 0) + 1;

// 与 state/s02.mjs 构成函数调用期的循环引用（只在调用时才互相读）
export function render02() {
  return 'card-' + state02.id;
}

export const view02 = { id: 2, name: 'view-02' };
