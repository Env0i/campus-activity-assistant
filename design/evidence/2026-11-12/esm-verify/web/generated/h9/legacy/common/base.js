/* 样机探针公共脚本：普通脚本，先于所有模块执行。
   每个字段对应计划里的假设编号：
     H2  location 协议、host、端口、origin 与实际 User-Agent
     H4  能力矩阵与 404 模块的 error 事件、内联模块的 CSP 拦截
     H5  普通脚本先挂排队用的 onBackend，模块就绪后接管并重放
     H11 模块 5 秒内没报到就显示兜底提示
   全用 ES5 写法：手机内置浏览器可能是老内核。 */
(function () {
  var P = window.__probe = {
    page: document.documentElement.getAttribute('data-page') || 'unknown',
    t0: performance.now(),
    caps: {},
    errors: [],
    missing: { element_error: null, window_error: null },
    events: [],
    queued: [],
    replayed: 0,
    inline_module_ran: false,
    fallback_shown: false,
    fallback_at_ms: null,
    ready: false
  };
  window.__esmOrder = [];
  window.__esmCount = 0;
  window.__esmDone = false;
  window.__esmDoneAt = null;

  // H5：模块还没执行时，所有后端推送都先进这个队列
  window.onBackend = {
    probe: function (n) {
      P.queued.push({ n: n, at: performance.now(), phase: 'queued' });
    }
  };

  // H4：被依赖模块 404 时，script 元素会派发 error，document 捕获阶段能看到
  document.addEventListener('error', function (ev) {
    var t = ev.target;
    if (!t || t.tagName !== 'SCRIPT') { return; }
    var src = String(t.src || '');
    if (/absent[^/]*\.mjs$/i.test(src)) {
      P.missing.element_error = { src: src, phase: 'document-capture' };
    }
  }, true);
  window.addEventListener('error', function (ev) {
    P.errors.push({
      kind: 'window.error',
      message: String(ev.message || ''),
      filename: String(ev.filename || ''),
      lineno: ev.lineno || 0
    });
    if (!P.missing.window_error && ev.target === window) {
      P.missing.window_error = { message: String(ev.message || '') };
    }
  });
  window.addEventListener('unhandledrejection', function (ev) {
    var reason = ev.reason;
    P.errors.push({
      kind: 'unhandledrejection',
      message: String(reason && reason.message ? reason.message : reason)
    });
  });

  // H4：CSP script-src 'self' 会拦内联模块，拦下来时这里能收到（全部记下来）
  P.csp_violations = [];
  document.addEventListener('securitypolicyviolation', function (ev) {
    P.csp_violations.push({
      blocked_uri: ev.blockedURI,
      violated_directive: ev.violatedDirective,
      effective_directive: ev.effectiveDirective
    });
    P.caps.csp_violation = P.csp_violations[0];
  });

  // H11：5 秒兜底
  setTimeout(function () {
    if (P.ready) { return; }
    P.fallback_shown = true;
    P.fallback_at_ms = performance.now();
    var node = document.getElementById('fallback');
    if (node) { node.style.display = 'block'; }
    if ((location.protocol === 'http:' || location.protocol === 'https:') && !window.pywebview) {
      window.__postReport(window.__collect());
    }
  }, 5000);

  window.__collect = function () {
    return {
      page: P.page,
      location: {
        protocol: location.protocol,
        host: location.host,
        hostname: location.hostname,
        port: location.port,
        origin: location.origin,
        pathname: location.pathname,
        href: location.href
      },
      ua: navigator.userAgent,
      ua_platform: navigator.platform,
      caps: P.caps,
      csp_violations: P.csp_violations,
      inline_module: { ran: !!P.inline_module_ran },
      errors: P.errors,
      missing_module: P.missing,
      backend_events: P.events,
      backend_queued: P.queued,
      backend_replayed: P.replayed,
      fallback: { shown: !!P.fallback_shown, at_ms: P.fallback_at_ms },
      ready: !!P.ready,
      done_ms: window.__esmDoneAt || null,
      esm_order: window.__esmOrder || [],
      esm_count: window.__esmCount || 0,
      timings: {
        dom_content_loaded: window.__domReadyAt || null,
        load: window.__loadAt || null
      }
    };
  };

  window.__postReport = function (payload) {
    if (location.protocol !== 'http:' && location.protocol !== 'https:') {
      return Promise.resolve(false);
    }
    return fetch('/__report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.ok; }, function () { return false; });
  };

  // 桌面：等 pywebview.api 就绪后 finalize；手机：直接 POST 回样机服务
  window.__finish = function (payload, preferHttp) {
    if (preferHttp) {
      window.__postReport(payload);
      return;
    }
    var started = performance.now();
    (function poll() {
      P.finish_polls = (P.finish_polls || 0) + 1;
      if (window.pywebview && window.pywebview.api && window.pywebview.api.finalize) {
        try {
          window.pywebview.api.finalize(JSON.stringify(payload));
          return;
        } catch (e) {
          // 桥还没就绪时会抛，继续等，别把结果丢了
          P.finish_error = String(e && e.message ? e.message : e);
        }
      }
      if (performance.now() - started > 15000) {
        window.__postReport(payload);
        return;
      }
      setTimeout(poll, 50);
    })();
  };

  document.addEventListener('DOMContentLoaded', function () {
    window.__domReadyAt = performance.now();
  });
  window.addEventListener('load', function () {
    window.__loadAt = performance.now();
  });
})();
