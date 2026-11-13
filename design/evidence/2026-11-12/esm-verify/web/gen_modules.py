# -*- coding: utf-8 -*-
"""生成 H2–H5、H9、H11 的全部样机页面与模块（可重复生成，结果一致）。

产物在 web/generated/ 下，由手机样机服务按 manifest.json 显式登记后提供。
本脚本不联网、不读产品模块，只在样机目录里写文件。

  python gen_modules.py            # 生成
  python gen_modules.py --clean    # 先删 generated/ 再生成
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "generated"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}

# 模块与普通脚本的总字节数（H3 要求「同样总大小」的对照）
SIZES: dict[str, int] = {}


def write(rel: str, text: str) -> int:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text if text.endswith("\n") else text + "\n"
    path.write_text(data, encoding="utf-8", newline="\n")
    SIZES[rel] = len(data.encode("utf-8"))
    return SIZES[rel]


# ---------------------------------------------------------------- 公共脚本
BASE_JS = r"""/* 样机探针公共脚本：普通脚本，先于所有模块执行。
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
"""

RUNNER_JS = r"""/* H9 计时 runner：普通脚本，轮询到本页全部模块执行完就记录并上报。
   auto=1（默认，http 下）：上报后自动跳到下一个形态/下一次，共 4 形态 x 3 次。
   auto=0：只测一次，交给桌面 pywebview 收快照。
   done_ms 是 performance.now()，基准就是本次导航开始。 */
(function () {
  var params = {};
  var query = location.search.replace(/^\?/, '').split('&');
  for (var i = 0; i < query.length; i++) {
    var pair = query[i].split('=');
    if (pair[0]) { params[pair[0]] = decodeURIComponent(pair[1] || ''); }
  }
  var pathSegs = location.pathname.split('/').filter(function (s) { return s; });
  if (pathSegs[pathSegs.length - 1] === 'index.html') { pathSegs.pop(); }
  var form = pathSegs[pathSegs.length - 1] || 'unknown';
  var run = parseInt(params.run || '1', 10) || 1;
  var isHttp = location.protocol === 'http:' || location.protocol === 'https:';
  var auto = isHttp && params.auto !== '0';
  var forms = ['legacy', 'flat', 'chain', 'preload-chain'];
  var RUNS_PER_FORM = 3;
  var EXPECTED_COUNT = 40;

  function snapshot() {
    return {
      page: 'h9',
      form: form,
      run: run,
      runs_per_form: RUNS_PER_FORM,
      module_count: window.__esmCount || 0,
      expected_count: EXPECTED_COUNT,
      order: window.__esmOrder || [],
      done_ms: window.__esmDoneAt || null,
      dom_ready_ms: window.__domReadyAt || null,
      load_ms: window.__loadAt || null,
      location: {
        protocol: location.protocol,
        host: location.host,
        origin: location.origin,
        pathname: location.pathname
      },
      ua: navigator.userAgent
    };
  }

  function baseDir() {
    var segs = location.pathname.split('/');
    segs = segs.filter(function (s) { return s; });
    var last = segs[segs.length - 1] || '';
    if (last === 'index.html' || last === 'page.html') { segs.pop(); }
    segs.pop();
    return '/' + segs.join('/');
  }

  function nextUrl() {
    var idx = 0;
    for (var i = 0; i < forms.length; i++) {
      if (forms[i] === form) { idx = i; }
    }
    var nextRun = run + 1;
    var nextForm = idx;
    if (nextRun > RUNS_PER_FORM) { nextForm = idx + 1; nextRun = 1; }
    if (nextForm >= forms.length) { return ''; }
    return baseDir() + '/' + forms[nextForm] + '/?run=' + nextRun;
  }

  function showDone() {
    var box = document.getElementById('result');
    if (box) { box.textContent = '计时完成：4 形态 x 3 次已上报，可回到首页看汇总。'; }
    if (!isHttp) { return; }
    fetch('/__summary', { cache: 'no-store' }).then(function (r) { return r.json(); })
      .then(function (data) {
        if (box) { box.textContent = '计时完成：' + JSON.stringify(data.counts || {}); }
      }, function () {});
  }

  function finish() {
    var payload = snapshot();
    if (!auto) {
      window.__finish(payload);
      return;
    }
    window.__postReport(payload).then(function () {
      var next = nextUrl();
      if (next) { location.replace(next); } else { showDone(); }
    });
  }

  var deadline = performance.now() + 10000;
  (function wait() {
    if (window.__esmDone || performance.now() > deadline) { finish(); return; }
    setTimeout(wait, 10);
  })();
})();
"""

PROBE_CSS = r"""html { font-family: system-ui, "Segoe UI", sans-serif; margin: 0; }
body { padding: 16px; line-height: 1.5; }
h1 { font-size: 18px; margin: 0 0 8px; }
pre { background: #f4f6fa; padding: 12px; overflow: auto; }
#fallback { display: none; background: #fff1f0; border: 1px solid #ffa39e;
  padding: 12px; margin: 12px 0; }
a { display: block; padding: 6px 0; }
"""


# ---------------------------------------------------------------- 桌面/手机主探针页
def page_shell(title: str, depth: int, body: str, doctor: str = "h2",
               extra_head: str = "") -> str:
    # 页面按产品写法放：pywebview 起本地服务时把「页面所在目录」当根，
    # ../common/... 会越过根变成 404，所以公共脚本在每个页面目录里各放一份。
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-page="{doctor}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="common/probe.css">
{extra_head}<script src="common/base.js"></script>
</head>
<body>
<h1>{title}</h1>
<div id="fallback">页面没有加载完整，请刷新或重新扫码</div>
<pre id="result">running…</pre>
{body}
</body>
</html>
"""


def gen_probe_page() -> None:
    """H2/H4/H5 主探针页：内联模块 + 404 模块 + 模块入口。"""
    extra = '<link rel="modulepreload" href="helper.mjs">\n'
    body = """<!-- H4：内联 type=module，在 CSP script-src 'self' 下应被拦 -->
<script type="module">
  window.__probe.inline_module_ran = true;
</script>
<script type="module" src="main.mjs"></script>
<!-- H4/H11：故意 404 的模块，用来观察 error 事件 -->
<script type="module" src="absent.mjs"></script>
"""
    write("h2/page.html", page_shell("ESM 探针（H2/H4/H5）", 1, body,
                                     doctor="h2", extra_head=extra))
    write("h2/helper.mjs", """/* H4：命名导出与默认导出 */
export const named = 'helper-named';
export const version = '1';

export default { version: '1', named: 'helper-named' };
""")
    write("h2/data.json", json.dumps(
        {"ok": True, "note": "H4 用 fetch 读 JSON，不用 import 断言"},
        ensure_ascii=False, indent=2))
    write("h2/main.mjs", r"""/* H2/H4/H5 主探针（模块）。
   注意：第一段必须是最早执行的接管逻辑，后面才允许 await。 */
import helper, { named, version } from './helper.mjs';

window.__probe.caps.static_import = {
  default_type: typeof helper,
  named_value: named,
  named_version: version,
  default_version: helper && helper.version ? helper.version : null
};

// H5：模块就绪后接管 onBackend，并重放普通脚本期间排队的推送
window.onBackend = {
  probe: function (n) {
    window.__probe.events.push({ n: n, at: performance.now(), phase: 'module' });
  }
};
var queued = window.__probe.queued.slice();
for (var i = 0; i < queued.length; i++) { window.onBackend.probe(queued[i].n); }
window.__probe.replayed = queued.length;

var allOk = true;
try {
  var dyn = await import('./helper.mjs');
  window.__probe.caps.dynamic_import = { ok: typeof dyn.named === 'string', named: dyn.named };
  window.__probe.caps.import_meta_url = import.meta.url;

  var awaited = await Promise.resolve('tla-ok');
  window.__probe.caps.top_level_await = awaited;

  var links = document.querySelectorAll('link[rel="modulepreload"]').length;
  var initiators = [];
  var entries = performance.getEntriesByType ? performance.getEntriesByType('resource') : [];
  for (var j = 0; j < entries.length; j++) {
    if (/helper\.mjs/.test(entries[j].name)) { initiators.push(entries[j].initiatorType); }
  }
  window.__probe.caps.modulepreload = {
    link_count: links,
    helper_initiator_types: initiators
  };

  var resp = await fetch('./data.json', { cache: 'no-store' });
  var data = await resp.json();
  window.__probe.caps.fetch_json = { ok: data.ok === true, status: resp.status };
} catch (err) {
  allOk = false;
  window.__probe.caps.probe_error = String(err && err.message ? err.message : err);
}

window.__probe.caps.all_caps_ok = allOk;
window.__probe.ready = true;
window.__esmDoneAt = performance.now();
window.__esmDone = true;
// H8：手机上要能直接看到通过与否，不用等到服务端汇总
var box = document.getElementById('result');
if (box) {
  box.textContent = (allOk ? '通过：' : '有失败：') + JSON.stringify(window.__probe.caps);
}
setTimeout(function () { window.__finish(window.__collect()); }, 600);
""")
    write("h2/index.html", page_shell("ESM 探针（H2/H4/H5）", 1, body,
                                      doctor="h2", extra_head=extra))


def gen_h11_page() -> None:
    """H11：入口模块 404，只有 5 秒兜底提示能出现。"""
    body = """<!-- H11：入口模块故意不存在，5 秒内不会有模块报到 -->
<script type="module" src="absent-main.mjs"></script>
"""
    write("h11/index.html", page_shell("ESM 兜底提示（H11）", 1, body, doctor="h11"))


def gen_cycle_page() -> None:
    """H3 的顶层互相引用循环：记录报错原文。"""
    body = """<script type="module" src="cycle-a.mjs"></script>
<script>
  // 再用动态 import 抓一次，拿到可读的异常名与消息
  window.__probe.caps.cycle_dynamic = { ok: false, error: null, name: null };
  import('./cycle-a.mjs').then(function () {
    window.__probe.caps.cycle_dynamic.ok = true;
  }).catch(function (err) {
    window.__probe.caps.cycle_dynamic.error = String(err && err.message ? err.message : err);
    window.__probe.caps.cycle_dynamic.name = String(err && err.name ? err.name : '');
  });
  setTimeout(function () {
    window.__probe.ready = true;
    var c = window.__probe.caps.cycle_dynamic;
    var box = document.getElementById('result');
    if (box) {
      box.textContent = c.ok ? '通过：顶层循环也能执行'
                             : '失败（预期）：' + c.name + ': ' + c.error;
    }
    window.__finish(window.__collect());
  }, 1200);
</script>
"""
    write("h3/cycle/index.html",
          page_shell("ESM 顶层循环依赖（H3）", 2, body, doctor="h3-cycle"))
    write("h3/cycle/cycle-a.mjs", """/* 顶层互相引用的循环：a 在顶层读 b 的常量，b 又 import a */
import { b } from './cycle-b.mjs';

export const a = 'a' + b;
""")
    write("h3/cycle/cycle-b.mjs", """import { a } from './cycle-a.mjs';

export const b = 'b' + a;
""")


# ---------------------------------------------------------------- H3 / H9 40 模块
STATE_TEMPLATE = """import {{ render{nn2} }} from '../views/v{nn2}.mjs';

window.__esmOrder.push('s{nn2}');
window.__esmCount = (window.__esmCount || 0) + 1;

// 函数调用期的循环引用：views/v{nn2}.mjs 又 import 回 state{nn2}
export const state{nn2} = {{ id: {nn}, name: 'state-{nn2}' }};

export function snapshot{nn2}() {{
  return {{ id: {nn}, label: 'state-{nn2}', card: render{nn2}() }};
}}
"""

VIEW_TEMPLATE = """import {{ state{nn2} }} from '../state/s{nn2}.mjs';

window.__esmOrder.push('v{nn2}');
window.__esmCount = (window.__esmCount || 0) + 1;

// 与 state/s{nn2}.mjs 构成函数调用期的循环引用（只在调用时才互相读）
export function render{nn2}() {{
  return 'card-' + state{nn2}.id;
}}

export const view{nn2} = {{ id: {nn}, name: 'view-{nn2}' }};
"""

CONTROLLER_TEMPLATE = """import {{ snapshot{nn2} }} from '../state/s{nn2}.mjs';
import {{ render{nn2} }} from '../views/v{nn2}.mjs';

window.__esmOrder.push('c{nn2}');
window.__esmCount = (window.__esmCount || 0) + 1;

export function build{nn2}() {{
  var snap = snapshot{nn2}();
  return {{ id: snap.id, card: render{nn2}(), label: 'controller-{nn2}' }};
}}

export const controller{nn2} = {{ id: {nn}, name: 'controller-{nn2}' }};
"""

LEGACY_TEMPLATE = """window.__esmOrder.push('l{nn2}');
window.__esmCount = (window.__esmCount || 0) + 1;

(function () {{
  window.__legacyLayers = window.__legacyLayers || {{ state: {{}}, view: {{}}, controller: {{}} }};
  window.__legacyLayers.state['{nn2}'] = {{ id: {nn}, name: 'state-{nn2}' }};
  window.__legacyLayers.view['{nn2}'] = {{
    render: function () {{ return 'card-' + window.__legacyLayers.state['{nn2}'].id; }}
  }};
  window.__legacyLayers.controller['{nn2}'] = {{
    build: function () {{
      return {{
        id: window.__legacyLayers.state['{nn2}'].id,
        card: window.__legacyLayers.view['{nn2}'].render(),
        label: 'controller-{nn2}'
      }};
    }}
  }};
}})();
"""


def gen_layered_modules(dest: str) -> list[str]:
    """13 个 state + 13 个 view + 13 个 controller + 入口，共 40 个模块。"""
    names = []
    for nn in range(1, 14):
        nn2 = "%02d" % nn
        write(f"{dest}/state/s{nn2}.mjs",
              STATE_TEMPLATE.format(nn=nn, nn2=nn2))
        names.append(f"./state/s{nn2}.mjs")
    for nn in range(1, 14):
        nn2 = "%02d" % nn
        write(f"{dest}/views/v{nn2}.mjs", VIEW_TEMPLATE.format(nn=nn, nn2=nn2))
        names.append(f"./views/v{nn2}.mjs")
    for nn in range(1, 14):
        nn2 = "%02d" % nn
        write(f"{dest}/controllers/c{nn2}.mjs", CONTROLLER_TEMPLATE.format(nn=nn, nn2=nn2))
        names.append(f"./controllers/c{nn2}.mjs")
    imports = "\n".join("import '%s';" % name for name in names)
    body = (imports + """

import { buildNN } from './controllers/c01.mjs';

// 调一次，证明函数调用期的循环引用不会在运行时炸
window.__cycleCallOk = buildNN().card === 'card-1';
window.__esmCount = (window.__esmCount || 0) + 1;
window.__esmDone = true;
window.__esmDoneAt = performance.now();
""").replace("buildNN", "build01")
    write(f"{dest}/main.mjs", body)
    return names


def gen_legacy_set() -> int:
    """40 个普通脚本，总字节数与模块版对齐（H3 的同尺寸对照）。"""
    texts = []
    for nn in range(1, 41):
        nn2 = "%02d" % nn
        text = LEGACY_TEMPLATE.format(nn=nn, nn2=nn2)
        if nn == 40:
            text += "\nwindow.__esmDone = true;\nwindow.__esmDoneAt = performance.now();\n"
        texts.append((nn2, text))
    return texts


def gen_h9_flat(preload: bool = False) -> None:
    names = gen_layered_modules("h9/preload" if preload else "h9/flat")
    extra = ""
    if preload:
        extra = "\n".join('<link rel="modulepreload" href="%s">' % name[2:]
                          for name in names) + "\n"
    body = """<script type="module" src="main.mjs"></script>
<script src="common/runner.js"></script>
"""
    write("h9/preload/index.html" if preload else "h9/flat/index.html",
          page_shell("H9 40 模块%s" % ("（modulepreload）" if preload else "（扁平引入）"),
                     2, body, doctor="h9", extra_head=extra))


def gen_h9_chain(preload: bool = False) -> None:
    """8 层链式：m01..m39 + 入口，共 40 个模块。"""
    dest = "h9/preload-chain" if preload else "h9/chain"
    for nn in range(1, 40):
        nn2 = "%02d" % nn
        nxt = nn + 5
        if nxt <= 39:
            nxt2 = "%02d" % nxt
            text = (f"import {{ layer{nxt2} }} from './m{nxt2}.mjs';\n\n"
                    f"window.__esmOrder.push('m{nn2}');\n"
                    "window.__esmCount = (window.__esmCount || 0) + 1;\n\n"
                    f"export function layer{nn2}() {{\n"
                    f"  return 'layer-{nn2}-' + layer{nxt2}();\n"
                    "}\n")
        else:
            text = (f"window.__esmOrder.push('m{nn2}');\n"
                    "window.__esmCount = (window.__esmCount || 0) + 1;\n\n"
                    f"export function layer{nn2}() {{\n"
                    f"  return 'layer-{nn2}';\n"
                    "}\n")
        write(f"{dest}/m{nn2}.mjs", text)
    imports = "\n".join("import { layer%02d } from './m%02d.mjs';" % (nn, nn)
                        for nn in range(1, 6))
    write(f"{dest}/main.mjs", imports + """

window.__chainCallOk = layer01().indexOf('layer-01-layer-06') === 0;
window.__esmCount = (window.__esmCount || 0) + 1;
window.__esmDone = true;
window.__esmDoneAt = performance.now();
""")
    extra = ""
    if preload:
        extra = "\n".join('<link rel="modulepreload" href="m%02d.mjs">' % nn
                          for nn in range(1, 40)) + "\n"
    body = """<script type="module" src="main.mjs"></script>
<script src="common/runner.js"></script>
"""
    write(f"{dest}/index.html",
          page_shell("H9 40 模块%s" % ("（链式 + modulepreload）" if preload else "（8 层链式）"),
                     2, body, doctor="h9", extra_head=extra))


def gen_h9_legacy(module_total: int) -> None:
    texts = gen_legacy_set()
    total = 0
    for nn2, text in texts:
        total += write(f"h9/legacy/l{nn2}.js", text)
    # 同尺寸：给最后一个脚本补注释，让总字节数与模块版对齐
    diff = module_total - total
    if diff > 0:
        pad = "\n/* 补齐到与模块版相同总字节数：%d 字节 */\n" % diff
        with open(OUT / "h9/legacy/l40.js", "a", encoding="utf-8", newline="\n") as fh:
            fh.write(pad)
        SIZES["h9/legacy/l40.js"] += len(pad.encode("utf-8"))
    tags = "\n".join('<script src="l%02d.js"></script>' % nn for nn in range(1, 41))
    body = tags + '\n<script src="common/runner.js"></script>\n'
    write("h9/legacy/index.html",
          page_shell("H9 40 普通脚本（对照）", 2, body, doctor="h9"))


def gen_landing() -> None:
    write("index.html", """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESM 补验样机</title>
<link rel="stylesheet" href="/common/probe.css">
</head>
<body>
<h1>ESM 补验样机</h1>
<div id="fallback" style="display:none">页面没有加载完整，请刷新或重新扫码</div>
<p>按顺序点下面几项，跑完回来看汇总。每一步都会自动上报，不需要手工记录。</p>
<a href="/h2/page.html">H2/H4/H5 探针（加载机制、能力矩阵、后端早推）</a>
<a href="/h11/">H11 缺模块兜底</a>
<a href="/h3/cycle/">H3 顶层循环依赖的报错样子</a>
<a href="/h9/legacy/">H9 四形态计时（自动 4 形态 x 3 次）</a>
<a href="/h9/chain/">（单项）8 层链式</a>
<a href="/h9/preload-chain/">（单项）链式 + modulepreload</a>
<pre id="summary">汇总读取中…</pre>
<script>
(function () {
  function refresh() {
    fetch('/__summary', { cache: 'no-store' }).then(function (r) { return r.json(); })
      .then(function (data) {
        document.getElementById('summary').textContent =
          '已收到 ' + data.total + ' 份上报\\n' + JSON.stringify(data.counts, null, 2);
      }, function () {
        document.getElementById('summary').textContent = '读不到汇总（服务已退出？）';
      });
  }
  refresh();
  setInterval(refresh, 3000);
})();
</script>
</body>
</html>
""")


def gen_manifest() -> None:
    entries = {}
    for path in sorted(OUT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(OUT).as_posix()
        if rel in ("manifest.json", "sizes.json"):
            continue
        mime = CONTENT_TYPES.get(path.suffix.lower())
        if not mime:
            continue
        entries["/" + rel] = {"file": rel, "type": mime}
    entries["/"] = {"file": "index.html", "type": CONTENT_TYPES[".html"]}
    (OUT / "manifest.json").write_text(
        json.dumps({"generated_by": "web/gen_modules.py", "files": entries},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    (OUT / "sizes.json").write_text(
        json.dumps(SIZES, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    write("common/base.js", BASE_JS)
    write("common/runner.js", RUNNER_JS)
    write("common/probe.css", PROBE_CSS)

    gen_probe_page()
    gen_h11_page()
    gen_cycle_page()
    gen_landing()

    gen_h9_flat(preload=False)
    module_total = sum(size for name, size in SIZES.items()
                       if name.startswith("h9/flat/") and name.endswith(".mjs"))
    gen_h9_chain(preload=False)
    gen_h9_chain(preload=True)
    gen_h9_legacy(module_total)

    # 公共脚本在每个页面目录各放一份（pywebview 的本地服务以页面目录为根）
    for dest in ("h2", "h11", "h3/cycle", "h9/legacy", "h9/flat",
                 "h9/chain", "h9/preload-chain"):
        write(dest + "/common/base.js", BASE_JS)
        write(dest + "/common/runner.js", RUNNER_JS)
        write(dest + "/common/probe.css", PROBE_CSS)

    gen_manifest()
    print("生成完成：%d 个文件，模块版总字节 %d" % (
        len(SIZES), module_total))


if __name__ == "__main__":
    main()
