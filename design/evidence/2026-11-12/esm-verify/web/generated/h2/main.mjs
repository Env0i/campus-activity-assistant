/* H2/H4/H5 主探针（模块）。
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
