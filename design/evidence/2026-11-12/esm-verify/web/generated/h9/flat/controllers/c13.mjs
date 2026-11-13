import { snapshot13 } from '../state/s13.mjs';
import { render13 } from '../views/v13.mjs';

window.__esmOrder.push('c13');
window.__esmCount = (window.__esmCount || 0) + 1;

export function build13() {
  var snap = snapshot13();
  return { id: snap.id, card: render13(), label: 'controller-13' };
}

export const controller13 = { id: 13, name: 'controller-13' };
