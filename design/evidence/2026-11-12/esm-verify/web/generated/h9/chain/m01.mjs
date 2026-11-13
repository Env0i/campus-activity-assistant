import { layer06 } from './m06.mjs';

window.__esmOrder.push('m01');
window.__esmCount = (window.__esmCount || 0) + 1;

export function layer01() {
  return 'layer-01-' + layer06();
}
