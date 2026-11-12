// =====================================================================
// main.mjs —— 入口模块
//
// 作用：
//   1. import chain → leaf，拉起完整 import 链
//   2. 在 runOrder 里留痕迹
//   3. 暴露 window.apiBridgeMain.callLegacyFoo() —— 模块反向调 legacy 全局
//   4. 轮询等 pywebview bridge 注入后，把结果回传给 Python 端 js_api.finalize()
//
// import 链执行顺序（深度优先）：
//   legacy.js 顶层 → leaf.mjs 顶层 → chain.mjs 顶层 → main.mjs 顶层
// =====================================================================

import './chain.mjs';

window.runOrder = window.runOrder || [];
window.runOrder.push('main-top');

window.apiBridgeMain = {
  callLegacyFoo: function () {
    if (window.legacyGlobal && typeof window.legacyGlobal.foo === 'function') {
      const r = window.legacyGlobal.foo();
      window.runOrder.push('main-called-legacy-foo:' + r);
      return r;
    }
    return 'legacyGlobal-not-ready';
  }
};

window._finalizeFired = false;

function finalizeFrontend() {
  if (window._finalizeFired) return;
  window._finalizeFired = true;

  const snapshot = {
    runOrder: window.runOrder || [],
    errors: window._spikeErrors || [],
    legacyExecuted: !!(window.runOrder && window.runOrder.indexOf('legacy-top') >= 0),
    mainExecuted: !!(window.runOrder && window.runOrder.indexOf('main-top') >= 0),
    chainExecuted: !!(window.runOrder && window.runOrder.indexOf('chain-top') >= 0),
    leafExecuted: !!(window.runOrder && window.runOrder.indexOf('leaf-top') >= 0),
    legacyGlobalExists: !!(window.legacyGlobal),
    apiBridgeMainExists: !!(window.apiBridgeMain),
    apiBridgeChainExists: !!(window.apiBridgeChain),
    apiBridgeLeafExists: !!(window.apiBridgeLeaf),
    pywebviewAvailable: 'pywebview' in window,
  };

  try {
    window.pywebview.api.finalize(snapshot);
  } catch (e) {
    window.runOrder.push('finalize-error:' + String(e));
    // Python 定时器会兜底 finalize
  }
}

function onDomReady() {
  window.runOrder.push('dom-load-fired');

  if ('pywebview' in window) {
    window.runOrder.push('pywebview-already-present-at-domload');
    setTimeout(finalizeFrontend, 500);
    return;
  }

  // 轮询等待 pywebview bridge 注入
  let waited = 0;
  const poll = setInterval(() => {
    waited += 100;
    if ('pywebview' in window) {
      window.runOrder.push('pywebview-appeared-after-' + waited + 'ms');
      clearInterval(poll);
      setTimeout(finalizeFrontend, 500);
    } else if (waited >= 3000) {
      window.runOrder.push('pywebview-never-appeared-after-3s');
      clearInterval(poll);
      // Python 定时器会兜底 finalize
    }
  }, 100);
}

window.addEventListener('load', onDomReady);

// 全局错误拦截
window._spikeErrors = [];
window.onerror = function (msg, url, line, col, err) {
  window._spikeErrors.push({
    msg: String(msg),
    url: url || '',
    line: line || 0,
    col: col || 0,
  });
};
