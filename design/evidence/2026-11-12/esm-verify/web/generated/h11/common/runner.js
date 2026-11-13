/* H9 计时 runner：普通脚本，轮询到本页全部模块执行完就记录并上报。
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
