// =====================================================================
// main.mjs —— 入口模块
//
// 作用：
//   1. import chain → leaf，拉起完整 import 链
//   2. 在 runOrder 里留痕迹（模块顶层代码比普通脚本延后）
//   3. 暴露 window.apiBridgeMain，包含：
//        - pongFromPython(val)  —— Python 通过 evaluate_js 调这个（场景 C）
//        - callLegacyFoo()     —— 模块反向调 legacy 全局（场景 D）
//
// 关键时序：
//   pywebview 的 bridge 注入（window.pywebview 可用）晚于 DOM load。
//   所以用 setTimeout 轮询等 pywebview 出现，再跑桥接测试。
//
// import 链执行顺序（深度优先）：
//   legacy.js 顶层 → leaf.mjs 顶层 → chain.mjs 顶层 → main.mjs 顶层
// =====================================================================

import './chain.mjs';

window.runOrder = window.runOrder || [];
window.runOrder.push('main-top');

window._bridgeResults = window._bridgeResults || {};
window._finalizeFired = false;

window.apiBridgeMain = {
  // Python → JS 通道（场景 C）
  pongFromPython: function (val) {
    window.runOrder.push('main-pong-from-python:' + val);
    window._bridgeResults.lastPongFromPython = val;
    return 'pong-ok:' + val;
  },

  // 模块 → legacy 互调（场景 D）
  callLegacyFoo: function () {
    if (window.legacyGlobal && typeof window.legacyGlobal.foo === 'function') {
      const r = window.legacyGlobal.foo();
      window.runOrder.push('main-called-legacy-foo:' + r);
      window._bridgeResults.moduleCallLegacy = r;
      return r;
    }
    return 'legacyGlobal-not-ready';
  }
};

// ---------------------------------------------------------------------
// 就绪后自动发起桥接测试
//
// pywebview 6.2.1 的 bridge 注入时机晚于 DOM load（至少差几百毫秒）。
// 所以用轮询等 window.pywebview 出现，最多等 3 秒。
// ---------------------------------------------------------------------
let _readyStarted = false;

function onDomReady() {
  if (_readyStarted) return;
  _readyStarted = true;
  window.runOrder.push('dom-load-fired');

  if ('pywebview' in window) {
    window.runOrder.push('pywebview-already-present-at-domload');
    setTimeout(runBridgeTests, 50);
    return;
  }

  // 轮询等待 pywebview bridge 注入
  let waited = 0;
  const poll = setInterval(() => {
    waited += 100;
    if ('pywebview' in window) {
      window.runOrder.push('pywebview-appeared-after-' + waited + 'ms');
      clearInterval(poll);
      setTimeout(runBridgeTests, 50);
    } else if (waited >= 3000) {
      window.runOrder.push('pywebview-never-appeared-after-3s');
      clearInterval(poll);
      // Python 定时器会兜底 finalize
    }
  }, 100);
}

function runBridgeTests() {
  if (!('pywebview' in window)) {
    window.runOrder.push('skip-bridge-tests-no-pywebview');
    return;
  }

  window.runOrder.push('running-bridge-tests');

  // JS → Python：调 ping(42)，预期 Python 返回 84
  try {
    const ret = window.pywebview.api.ping(42);
    window.runOrder.push('js-called-python-ping:42→' + ret);
    window._bridgeResults.pingResult = ret;
  } catch (e) {
    window.runOrder.push('js-ping-error:' + String(e));
    window._bridgeResults.pingError = String(e);
  }

  // 模块调 legacy（场景 D 前端主动发起）
  try {
    const ret2 = window.apiBridgeMain.callLegacyFoo();
    window.runOrder.push('main-called-legacy-frontend-initiated:' + ret2);
  } catch (e) {
    window.runOrder.push('main-call-legacy-frontend-error:' + String(e));
  }

  // legacy 反向调模块（场景 D 前端主动发起）
  try {
    const ret3 = window.legacyGlobal.callModuleBridgeMain();
    window.runOrder.push('legacy-called-module-frontend-initiated:' + ret3);
    window._bridgeResults.legacyCallModule = ret3;
  } catch (e) {
    window.runOrder.push('legacy-call-module-frontend-error:' + String(e));
  }

  // 前端主动 finalize —— 不等 Python 定时器了
  finalizeFrontend();
}

function finalizeFrontend() {
  if (window._finalizeFired) return;
  window._finalizeFired = true;

  const snapshot = {
    runOrder: window.runOrder || [],
    bridgeResults: window._bridgeResults || {},
    errors: window._spikeErrors || [],
    legacyGlobalExists: !!(window.legacyGlobal),
    apiBridgeMainExists: !!(window.apiBridgeMain),
    apiBridgeChainExists: !!(window.apiBridgeChain),
    apiBridgeLeafExists: !!(window.apiBridgeLeaf),
    pywebviewAvailable: 'pywebview' in window,
  };

  try {
    window.pywebview.api.finalizeScene(snapshot);
  } catch (e) {
    window.runOrder.push('finalizeScene-error:' + String(e));
  }
}

// 只用 DOM load —— pywebviewready 自定义事件在 pywebview 6.2.1 下不确定触发
window.addEventListener('load', onDomReady);

// 全局错误拦截
window._spikeErrors = [];
window.onerror = function (msg, url, line, col, err) {
  const info = { msg: String(msg), url: url || '', line: line || 0 };
  window._spikeErrors.push(info);
  if ('pywebview' in window && window.pywebview.api &&
      typeof window.pywebview.api.reportError === 'function') {
    try { window.pywebview.api.reportError(info); } catch (_) {}
  }
};
