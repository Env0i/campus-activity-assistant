// =====================================================================
// legacy.js —— 普通脚本（type="text/javascript"），顶层立即执行
//
// 作用：
//   1. 在 window.runOrder 里留下执行痕迹，用来和模块顶层代码比顺序
//   2. 把 legacyGlobal 挂到 window，供模块侧调用来验证「普通脚本
//      先于模块执行且模块能反向调普通脚本」
//
// 这是 type="text/javascript"，不是 module，所以不会被延后执行。
// =====================================================================

// runOrder 数组：记录每个脚本/模块顶层执行的先后顺序
// 每个顶层代码块在最开头 push 自己的标识
window.runOrder = window.runOrder || [];
window.runOrder.push('legacy-top');

// legacyGlobal：普通脚本暴露给外部的全局对象
// legacy 脚本自己不能 import 任何东西，所以只能挂到 window 上
window.legacyGlobal = {
  foo: function () {
    // 让调用方知道确实走到了这里，不是 undefined
    window.runOrder.push('legacyGlobal.foo-called');
    return 'legacy-foo-ok';
  },
  // 场景 D 里验证 legacy 能调模块暴露的函数
  callModuleBridgeMain: function () {
    if (window.apiBridgeMain && typeof window.apiBridgeMain.callLegacyFoo === 'function') {
      // 反过来调模块暴露的方法，再让模块调回 legacy，形成互调闭环
      return window.apiBridgeMain.callLegacyFoo();
    }
    return 'apiBridgeMain-not-ready-yet';
  }
};
