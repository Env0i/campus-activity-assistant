/* pywebview 桥接端口：api/hasBridge/waitForBridge。 */
function hasBridge() {
  return !!(window.pywebview && window.pywebview.api);
}

function api(name, ...args) {
  if (!hasBridge()) return Promise.reject(new Error("页面没有连接本机程序"));
  const fn = window.pywebview.api[name];
  if (typeof fn !== "function") return Promise.reject(new Error("本机程序不支持：" + name));
  try {
    return Promise.resolve(fn.apply(window.pywebview.api, args));
  } catch (err) {
    return Promise.reject(err);
  }
}

function waitForBridge(timeoutMs) {
  const limit = typeof timeoutMs === "number" ? timeoutMs : 15000;
  return new Promise((resolve) => {
    /* 15 秒承诺是经过时长：系统墙钟跳变不得提前或延后它 */
    const started = _monoMs();
    const probe = () => {
      /* WebView 先注入 api 容器，再注册方法。启动要等到 bootstrap 可调用。 */
      if (hasBridge() && typeof window.pywebview.api.bootstrap === "function") {
        resolve(true);
        return;
      }
      if (_monoMs() - started >= limit) {
        resolve(false);
        return;
      }
      setTimeout(probe, 50);
    };
    probe();
  });
}
