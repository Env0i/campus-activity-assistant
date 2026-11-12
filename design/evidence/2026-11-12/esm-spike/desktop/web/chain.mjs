// =====================================================================
// chain.mjs —— 中间模块，import leaf，再被 main import
//
// 作用：
//   1. 验证 import 链（main → chain → leaf）层层传递
//   2. 在 runOrder 里留痕迹，用来和 legacy / main 比先后
// =====================================================================

import './leaf.mjs';

window.runOrder = window.runOrder || [];
window.runOrder.push('chain-top');

window.apiBridgeChain = {
  hello: () => 'chain-hello'
};
