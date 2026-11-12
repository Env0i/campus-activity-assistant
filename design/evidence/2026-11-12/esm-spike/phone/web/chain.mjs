// chain.mjs —— import 链中间模块
// import leaf.mjs，在顶层代码里留痕迹

import './leaf.mjs';

window.runOrder = window.runOrder || [];
window.runOrder.push('chain-top');

window.apiBridgeChain = {
  name: 'chain-mjs'
};
