// legacy.js —— 普通脚本对照（text/javascript，非模块）
// 目的：验证在 CSP script-src 'self' + nosniff 下普通脚本能正常执行
// 以及验证执行顺序 legacy < main

window.runOrder = window.runOrder || [];
window.runOrder.push('legacy-top');

window.legacyGlobal = {
  foo: function () {
    window.runOrder.push('legacyGlobal.foo-called');
    return 'legacy-foo-ok';
  },
  callModuleBridgeMain: function () {
    if (window.apiBridgeMain && typeof window.apiBridgeMain.callLegacyFoo === 'function') {
      // 反向调模块：模块里也挂了 callLegacyFoo —— 这里调用的就是模块的同名方法
      // 但我们要验证 legacy 能"看到"模块暴露在 window 上的对象
      window.runOrder.push('legacy-tried-call-apiBridgeMain');
      return 'legacy-saw-apiBridgeMain';
    }
    return 'apiBridgeMain-not-ready';
  }
};

window._spikeErrors = window._spikeErrors || [];
