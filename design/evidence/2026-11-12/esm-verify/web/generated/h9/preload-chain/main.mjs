import { layer01 } from './m01.mjs';
import { layer02 } from './m02.mjs';
import { layer03 } from './m03.mjs';
import { layer04 } from './m04.mjs';
import { layer05 } from './m05.mjs';

window.__chainCallOk = layer01().indexOf('layer-01-layer-06') === 0;
window.__esmCount = (window.__esmCount || 0) + 1;
window.__esmDone = true;
window.__esmDoneAt = performance.now();
