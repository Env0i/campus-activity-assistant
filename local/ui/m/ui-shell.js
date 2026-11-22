"use strict";

/* 手机页 DOM 层——抽屉外壳、确认槽、事件接线与启动入口（依赖前面全部 11 份脚本先加载，必须排在最后）：
 * 负责 sheet 开关与确认槽、全页 DOM 事件绑定、PhoneUI 导出及 DOMContentLoaded 启动。 */

/* G03 sheet 外壳（原型 Phone:299-300/924-926）：一个通用容器，openSheet/closeSheet
   管焦点归还与开关；验证中 busyLock 不收（Esc、点遮罩、关闭钮都不关）。
   RL03：电脑自动登录（mode=auto）时手机只是看进度，「收起，在后台继续」要能收——
   busyLock 只锁人工流程（starting/waiting_code/verifying/提交在途） */
function sheetBusy() {
  const flow = model.flow;
  if (flow && String(flow.mode || "") === "auto") return Boolean(model.reloginSubmitting);
  return Boolean(model.reloginSubmitting || PhoneModel.reloginBusy(flow));
}
/* confirm 的标题是占位：askConfirm 会按档覆写（RW03/SH03/SH04）；relogin 题固定（RL01，原型 Phone:884） */
const SHEET_TITLES = { more: "更多", review: "核对计划", confirm: "确认",
                       relogin: "在手机上重新登录" };
function openSheet(id) {
  const root = $("sheet-root");
  if (!root || !SHEET_TITLES[id] || model.sheetId) return;   // 一次只开一张
  model.sheetOpener = document.activeElement || null;
  model.sheetId = id;
  $("sheet-err").hidden = true;
  $("more-panel").hidden = id !== "more";
  $("review-panel").hidden = id !== "review";
  $("confirm-panel").hidden = id !== "confirm";
  $("relogin-panel").hidden = id !== "relogin";
  /* UI-F2：review/relogin 的页脚在 .sh-b 滚动区之外（sheet 级），随所属面板同开同收 */
  $("review-foot").hidden = id !== "review";
  $("relogin-foot").hidden = id !== "relogin";
  $("sheet-title").textContent = SHEET_TITLES[id];
  $("btn-sheet-close").hidden = sheetBusy();
  root.hidden = false;
  $("sheet-box").focus();
}
function closeSheet(force) {
  const root = $("sheet-root");
  if (!root || !model.sheetId) return;
  if (!force && sheetBusy()) {
    $("btn-sheet-close").hidden = true;   // 验证中：顺手把关闭钮也藏住
    return;
  }
  model.sheetId = "";
  root.hidden = true;
  $("more-panel").hidden = true;
  $("review-panel").hidden = true;
  $("confirm-panel").hidden = true;
  $("relogin-panel").hidden = true;
  $("review-foot").hidden = true;    // UI-F2：页脚随 sheet 收起
  $("relogin-foot").hidden = true;
  $("sheet-err").hidden = true;
  /* SEC-P3-3：重登 sheet 收起（含「取消」路径）即清账号/密码/验证码输入，
     重开时不得残留上一轮的密码；这些字段只属于重登 sheet，收其他 sheet 是空操作 */
  ["relogin-user", "relogin-pass", "code"].forEach((id) => {
    const el = $(id);
    if (el) el.value = "";
  });
  model.confirm = null;                   // RW03：确认档随 sheet 收起
  model.relConfirm = false;               // RL06：确认层是开 sheet 那一次的事
  const opener = model.sheetOpener;
  model.sheetOpener = null;
  if (opener && typeof opener.focus === "function") opener.focus();
}
/* SH06 操作失败红条（原型 netErr，Phone:870）：sheet 开着时写动作发不出去要就地说明 */
function showSheetError(text) {
  if (!model.sheetId) return;
  const el = $("sheet-err");
  el.textContent = String(text || "");
  el.hidden = !text;
}

/* RW03/SH03/SH04 确认槽（原型 isConfirm，Phone.dc.html:311-314/874-879）：文案在
   PhoneModel.confirmView，这里只填 DOM；取消等待本任务接线，停止与取消一场共用
   同一槽（sheets-ops 迁移停止/取消 sheet 时复用）。
   用户决策 1（2026-11-08）：三处原生 confirm 全部改走 sheet 外壳。
   B-P1-1：取消一场要记住被点卡片那一场的 task_id（confirmView 只管文案）；
   UI-F5：动作失败不静默收场——sheet 保持打开，失败句写进 #sheet-err（SH06），
   成功才收 sheet；在途时禁用双钮防重发。 */
function askConfirm(kind, taskName, taskId) {
  const view = PhoneModel.confirmView(kind, taskName);
  if (!view || model.sheetId) return;
  model.confirm = { kind: kind, taskId: taskId };
  openSheet("confirm");
  $("sheet-title").textContent = view.title;
  $("confirm-text").textContent = view.text;
  $("btn-confirm-no").textContent = view.no;
  $("btn-confirm-yes").textContent = view.yes;
  $("btn-confirm-no").disabled = false;    // 上一轮在途禁用过的钮要放开（UI-F5）
  $("btn-confirm-yes").disabled = false;
}
function onConfirmYes() {
  const slot = model.confirm;
  const kind = slot && slot.kind;
  const run = kind === "cancelstart" ? cancelPendingStart()
    : kind === "stop" ? stopPlan()
    : kind === "cancelTask" ? cancelTask(slot && slot.taskId) : null;
  if (!run) { closeSheet(true); return; }
  $("btn-confirm-yes").disabled = true;   // 在途防重发；失败分支重新放开
  $("btn-confirm-no").disabled = true;
  void Promise.resolve(run).then((ok) => {
    if (ok !== false) { closeSheet(true); return; }
    $("btn-confirm-yes").disabled = false;
    $("btn-confirm-no").disabled = false;
  });
}

function wire() {
  $("btn-pair").addEventListener("click", () => void pair());
  /* PA03：点阵屏只是可视化层，输入仍走 #pair-code；数字归一化照原型 onCode、
     Enter 提交照原型 onCodeKey（Phone:922），输入即清上一轮错误 */
  $("pair-code").addEventListener("input", () => {
    const el = $("pair-code");
    const digits = String(el.value || "").replace(/\D/g, "").slice(0, 6);
    if (el.value !== digits) el.value = digits;
    model.pairErr = "";
    renderPair();
  });
  $("pair-code").addEventListener("keydown", (event) => {
    if (event && event.key === "Enter") void pair();
  });
  $("btn-refresh").addEventListener("click", () => void poll(true));
  /* EX01（原型 alert.fn=refresh，Phone.dc.html:852）：离线告警上的「重试」＝同一次刷新 */
  $("btn-offline-retry").addEventListener("click", () => void poll(true));
  /* UI-F13（原型 Phone:857 的 fn=setState({bookmark:false})）：「知道了」收起
     配对成功告警，本会话不再出现 */
  $("btn-pair-ok").addEventListener("click", () => {
    model.pairOkPending = false;
    renderAlerts(PhoneModel.isStale(model.lastOkAt, model.nowMs));
  });
  /* G03：更多钮开 sheet（先迁更多面板；停止/取消/重登随各自任务迁） */
  $("btn-more").addEventListener("click", () => openSheet("more"));
  /* sheet 外壳：关闭钮、点遮罩、Esc 三条收起路径；验证中由 closeSheet 自己拦 */
  $("btn-sheet-close").addEventListener("click", () => closeSheet());
  $("sheet-root").addEventListener("click", (event) => {
    if (event && event.target === event.currentTarget) closeSheet();
  });
  document.addEventListener("keydown", (event) => {
    if (event && event.key === "Escape") closeSheet();
  });
  /* 开始前先核对计划：列出已选场次、尝试设置和开始前提醒，确认后才真的开始。
     EX02（原型 bar.fn=beginRelogin，Phone.dc.html:864）：登录失效时这颗主钮换成
     「重新登录」，直接开重登 sheet——canStart 不拦登录失效（只拦过时/忙），
     服务端会拦真正的开始，这里不给用户一条必然失败的路 */
  $("btn-start").addEventListener("click", () => {
    if (PhoneModel.loginExpired(model.login) && !model.busy
        && !(model.pending && !model.pending.done)) openRelogin();
    else openReview();
  });
  /* EX02（原型 alert.fn=beginRelogin，Phone.dc.html:854）：告警条上的「重新登录」 */
  $("btn-banner-relogin").addEventListener("click", () => openRelogin());
  $("btn-review-start").addEventListener("click", () => { closeSheet(true); void startPlan(); });
  $("btn-review-back").addEventListener("click", () => closeSheet());
  /* SH01 批次条目的移除钮（原型 tk.remove，Phone:771）：委托在容器上，
     按 dataset.id 走勾选反选；图标钮自身不带监听 */
  $("review-items").addEventListener("click", (event) => {
    const id = event && event.target && event.target.dataset
      ? String(event.target.dataset.id || "") : "";
    if (id) removeFromReview(id);
  });
  /* RW03/SH03：停止与取消等待先过确认槽（原型 isConfirm，用户决策 1）；
     卡上的「取消这一场」在 renderTasks 里接 askConfirm("cancelTask")（SH04） */
  $("btn-stop").addEventListener("click", () => askConfirm("stop"));
  $("btn-cancel-start").addEventListener("click", () => askConfirm("cancelstart"));
  $("btn-confirm-no").addEventListener("click", () => closeSheet());
  $("btn-confirm-yes").addEventListener("click", () => onConfirmYes());
  /* RS01 结果态两钮（原型 reselect/finishView，Phone.dc.html:933-934）：纯前端回草稿，
     不发任何写动作 */
  $("btn-reselect").addEventListener("click", () => reselectFailed());
  $("btn-finish").addEventListener("click", () => finishPlanView());
  /* RW01 列表开合（原型 toggleList，Phone.dc.html:930） */
  $("btn-toggle-list").addEventListener("click", () => {
    model.listOpen = !model.listOpen;
    renderItems();
  });
  if ($("btn-show-window")) {
    $("btn-show-window").addEventListener("click", () => void showComputerWindow());
  }
  /* RL 迁移：更多面板的入口钮开重登 sheet（RL01 题），表单动作都在 sheet 里 */
  $("btn-relogin-open").addEventListener("click", () => openRelogin());
  $("btn-relogin").addEventListener("click", () => void beginRelogin());
  /* RL06（原型 autoRelogin，Phone:661 口径）：确认后交给电脑自动登录，手机只看进度 */
  $("btn-relogin-auto").addEventListener("click", () => void beginRelogin());
  $("btn-relogin-submit").addEventListener("click", () => void submitRelogin());
  $("btn-relogin-cancel").addEventListener("click", async () => {
    model.relConfirm = false;
    /* 取消成立（或本来就没有在途流程）才收 sheet；撤不掉就留着重试 */
    const ok = await cancelRelogin();
    if (ok !== false) closeSheet(true);
  });
  $("btn-relogin-refresh").addEventListener("click", () => void refreshRelogin());
  /* RL03/RL08 doneLabel（收起，在后台继续/完成）：auto 态不锁 sheet，直接收 */
  $("btn-relogin-done").addEventListener("click", () => closeSheet());
  /* relCanSubmit（原型 Phone:675）：主钮可用性随输入走 */
  ["relogin-user", "relogin-pass", "code"].forEach((id) => {
    $(id).addEventListener("input", () => refreshControls());
  });
  /* 折叠内 #q 快捷入口（LD03 保留）：与整页搜索框写同一个关键词 */
  $("q").addEventListener("input", () => {
    model.filter.q = $("q").value;
    if ($("search-q")) $("search-q").value = $("q").value;
    renderItems();
  });
  /* LD03 整页搜索：搜索钮开合（aria-expanded 随动），搜索框输入即筛 */
  $("btn-search").addEventListener("click", () => toggleSearch());
  $("search-q").addEventListener("input", () => {
    model.filter.q = $("search-q").value;
    if ($("q")) $("q").value = $("search-q").value;
    renderItems();
  });
  /* LD02 未选场详情卡的「选这一场」（原型 pickNext，Phone.dc.html:928） */
  $("btn-pick-next").addEventListener("click", () => {
    if (!model.pickId) return;
    const res = PhoneModel.pickItem(model.selected, model.items, model.pickId, true);
    model.selected = res.selected;
    model.notice = res.notice;
    renderItems();
  });
  document.querySelectorAll("[data-status]").forEach((btn) => {
    btn.addEventListener("click", () => {
      model.filter.status = btn.dataset.status;
      document.querySelectorAll("[data-status]").forEach((other) =>
        other.setAttribute("aria-pressed", other === btn ? "true" : "false"));
      renderItems();
    });
  });
  document.querySelectorAll("[data-time]").forEach((btn) => {
    btn.addEventListener("click", () => {
      model.filter.time = btn.dataset.time;
      document.querySelectorAll("[data-time]").forEach((other) =>
        other.setAttribute("aria-pressed", other === btn ? "true" : "false"));
      renderItems();
    });
  });
  $("retry-for").addEventListener("change", () => {
    model.retry.retry_for_s = Number($("retry-for").value);
    model.retryDirty = true;
    void saveRetry();
    refreshControls();
  });
  $("max-attempts").addEventListener("change", () => {
    model.retry.max_attempts = Number($("max-attempts").value || 0);
    model.retryDirty = true;
    void saveRetry();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (model.pollTimer) clearTimeout(model.pollTimer);
      model.pollTimer = null;
      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表
      model.tickTimer = null;
    } else if (model.paired) {
      void poll(false);       // 回前台立刻补一次，仍按事件游标补齐
    }
  });
  if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    window.addEventListener("pagehide", () => {
      if (model.pollTimer) clearTimeout(model.pollTimer);
      model.pollTimer = null;
      if (model.tickTimer) clearTimeout(model.tickTimer);
      model.tickTimer = null;
    });
    window.addEventListener("pageshow", () => {
      if (!document.hidden && model.paired) void poll(false); // bfcache 恢复后按游标补齐
    });
  }
  probeExistingSession();
  refreshControls();
  renderPair();                      // PA01：配对视图首屏点亮点阵屏
}

globalThis.PhoneUI = { model, poll, wire, renderItems, refreshControls,
                       ingest, startPlan, cancelPendingStart, submitRelogin, beginRelogin,
                       cancelRelogin, refreshRelogin, showComputerWindow,
                       openSheet, closeSheet, renderPair, beginPairLock, pair, reconcile,
                       toggleSearch, renderBoard, renderRelogin, openRelogin,
                       renderReview, askConfirm, scheduleTick, tickClock };
                       // SH01/SH03/SH04：核对渲染与确认槽供 vm 用例直接驱动；P1：整秒计时也可直接驱动
if (document.readyState !== "loading") wire();
else document.addEventListener("DOMContentLoaded", wire);
