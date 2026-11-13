import { snapshot02 } from '../state/s02.mjs';
import { render02 } from '../views/v02.mjs';

window.__esmOrder.push('c02');
window.__esmCount = (window.__esmCount || 0) + 1;

export function build02() {
  var snap = snapshot02();
  return { id: snap.id, card: render02(), label: 'controller-02' };
}

export const controller02 = { id: 2, name: 'controller-02' };
