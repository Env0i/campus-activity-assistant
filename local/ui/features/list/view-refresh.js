/* 列表加载与刷新视图辅助：时间轴骨架、已有列表顶部细进度条、原地刷新失败提示与顶栏 1.5s 已更新勾号。 */

export function skeletonHtml() {
  let html = '<div class="skel" aria-label="正在加载活动列表">';
  for (let i = 0; i < 3; i += 1) {
    html += '<div class="tl-node"><div class="tl-axis"><div class="tl-time"><span class="skel-bar" style="width:48px;height:14px"></span><span class="skel-bar" style="width:36px;height:11px;margin-top:4px"></span></div><span class="tl-dot" aria-hidden="true"></span></div>'
      + '<div class="tl-cards"><div class="skel-card"><span class="skel-bar" style="width:62%;height:14px"></span><span class="skel-bar" style="width:45%"></span><span class="skel-bar" style="width:82%"></span></div></div></div>';
  }
  return html + "</div>";
}

export function paintRefreshBarAndFail() {
  const isLoading = S.listState === "loading";
  const hasOld = S.items.length > 0;
  const bar = $("#list-refresh-bar");
  if (bar) bar.hidden = !(isLoading && hasOld);
  const fail = $("#list-refresh-fail");
  if (!fail) return;
  const showFail = !!S.listRefreshFail && hasOld && !isLoading;
  fail.hidden = !showFail;
  if (!showFail) return;
  const textEl = $("#list-refresh-fail-text");
  if (textEl) {
    const when = S.listAtLabel ? String(S.listAtLabel) : "上次";
    textEl.textContent = "没连上学校，下面还是 " + when + " 的列表，勾选都还在。";
  }
}

let refreshDoneTimer = null;

export function clearRefreshDoneState() {
  if (refreshDoneTimer) { clearTimeout(refreshDoneTimer); refreshDoneTimer = null; }
  S.refreshDoneUntil = 0;
  const btn = $("#btn-refresh");
  if (btn) {
    btn.classList.remove("is-done");
    const lbl = btn.querySelector(".lbl");
    if (lbl) lbl.textContent = "刷新";
  }
}

export function flashRefreshDone() {
  clearRefreshDoneState();
  const now = typeof _monoMs === "function" ? _monoMs() : Date.now();
  S.refreshDoneUntil = now + 1500;
  const btn = $("#btn-refresh");
  if (btn) {
    btn.classList.add("is-done");
    const lbl = btn.querySelector(".lbl");
    if (lbl) lbl.textContent = "已更新";
  }
  if (typeof setTimeout === "function") {
    refreshDoneTimer = setTimeout(() => {
      refreshDoneTimer = null;
      S.refreshDoneUntil = 0;
      const b = $("#btn-refresh");
      if (b) {
        b.classList.remove("is-done");
        const l = b.querySelector(".lbl");
        if (l) l.textContent = "刷新";
      }
      if (typeof paintFreshness === "function") paintFreshness();
    }, 1520);
  }
}
