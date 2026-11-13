import { snapshot08 } from '../state/s08.mjs';
import { render08 } from '../views/v08.mjs';

window.__esmOrder.push('c08');
window.__esmCount = (window.__esmCount || 0) + 1;

export function build08() {
  var snap = snapshot08();
  return { id: snap.id, card: render08(), label: 'controller-08' };
}

export const controller08 = { id: 8, name: 'controller-08' };
