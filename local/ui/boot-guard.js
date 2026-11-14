/* 兜底与排队（ESM 地基批）：普通脚本，放在 app.js 之后、模块入口之前，不依赖模块与样式表。
 * 排队——把 window.onBackend 的每个处理函数包一层，__modulesReady 为真之前到的事件先按
 * 顺序存下，等 main.js 调 __replayBackendQueue 按原顺序、原参数放出，之后直接透传。
 * 兜底——页面加载完 10 秒后 __modulesReady 还不是真，就在页面顶部显示一条内联样式的
 * 提示（模块加载失败时页面没有任何报错，esm-verify H11）。全部脚本迁成模块、不再需要
 * 过渡时，本文件连同 index.html 里的引用一起删除。 */
(function () {
  "use strict";
  var queue = [];
  Object.keys(window.onBackend).forEach(function (name) {
    var original = window.onBackend[name];
    if (typeof original !== "function") return;
    window.onBackend[name] = function () {
      if (window.__modulesReady === true) return original.apply(this, arguments);
      queue.push({ fn: original, args: Array.prototype.slice.call(arguments) });
    };
  });
  window.__replayBackendQueue = function () {
    var pending = queue.splice(0, queue.length);
    pending.forEach(function (item) {
      /* 某条的处理函数抛错只影响这一条：报出后继续放后面的，顺序不变，一条不丢；
       * 已放出的不会再送（放出前队列已清空）。改事件之前每条各自到达、互不影响，
       * 这里把同样的性质还给排队重放。 */
      try {
        item.fn.apply(window, item.args);
      } catch (err) {
        if (typeof console === "object" && console && typeof console.error === "function") {
          console.error("[界面] 后端事件处理出错，跳过本条：", err);
        }
      }
    });
  };
  window.setTimeout(function () {
    if (window.__modulesReady === true) return;
    var tip = document.createElement("div");
    tip.setAttribute("style", "position:fixed;top:0;left:0;right:0;z-index:9999;"
      + "padding:10px 14px;background:#b3261e;color:#fff;font:14px/1.6 system-ui,sans-serif;");
    tip.textContent = "界面没有加载完整。请关闭工具后重新打开；还是这样就重新安装。";
    document.body.insertBefore(tip, document.body.firstChild);
  }, 10000);
})();
