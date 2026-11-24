"use strict";

/* 手机页 DOM 层——计划启停与核对面板（依赖 model*.js、ui-session.js、ui-status.js、ui-list.js 先加载）：
 * 负责开始、对账、取消等待、停止、取消单场、结果重置、重试配置与核对抽屉渲染。 */

/* ---- 开始 / 停止 / 取消：未确认 start 用同一 request_id 只读对账 ---- */
async function startPlan() {
  if (!canWrite()) { setBanner("状态已过时，先刷新再开始", "stale_action"); return; }
  const items = model.selected.map((id) => ({ id }));
  if (!items.length) return;
  if (model.pending && PhoneModel.startPending(model.pending, Date.now())) {
    /* A-BUG-1：提示只在未决时给——accepted 的防双击窗口静默拦（开始已受理，
       不是「还没核对完」）；canceled/rejected 已在 startPending 放行，不会进来 */
    if (model.pending && !model.pending.done) {
      setBanner("上一次开始还没核对完，请先等结果", "info");
    }
    return;
  }
  /* A-BUG-1：走到这里说明没有未决的开始（终态 pending 已放行）——一律发新 request_id */
  const requestId = PhoneModel.newRequestId();
  model.pending = { request_id: requestId, at: Date.now(), done: false };
  model.notice = "";      // 原型 startState 会清掉勾选冲突提示（Phone.dc.html:540），计划已发出不再适用
  model.listOpen = false; // 原型 startState listOpen:false：计划一开始就收起活动列表（RW01）
  refreshControls();
  const { status, body } = await postAction({ action: "start_plan", args: {
    items, headed: false,
    retry_policy: { retry_for_s: Number(model.retry.retry_for_s),
                    max_attempts: Number(model.retry.max_attempts || 0) },
    request_id: requestId } });
  if (status === 401) return;
  if (body && body.ok && !body.pending) {
    model.pending.done = true;
    model.pending.outcome = "accepted";   // A-BUG-1：同步受理也记终态，保留防双击窗口
  }
  else if (body && body.error) setBanner(String(body.text || body.error), "error");
  refreshControls();
  void poll(true);
}
async function reconcile() {
  if (model.reconciling) return;
  const pending = model.pending;
  const requestId = pending && pending.request_id;
  if (!requestId) return;
  model.reconciling = true;
  try {
  const { body } = await postAction({
    action: "start_request_state", args: { request_id: requestId } });
  if (model.pending !== pending || pending.request_id !== requestId || pending.done || pending.canceling) return;
  if (body && (body.state === "accepted" || body.state === "rejected"
               || body.state === "canceled")) {
    pending.done = true;
    pending.outcome = body.state;   // A-BUG-1：终态原因随 pending 记下
    /* A-BUG-3：rejected/canceled 不能静默收口——回包文本（有则）或状态词亮到
       banner；accepted 照旧清掉「核对中」一类的提示 */
    if (body.state === "accepted") setBanner("");
    else setBanner(String(body.text || (body.state === "canceled"
      ? "开始已取消" : "开始请求被拒绝")),
      body.state === "canceled" ? "info" : "error");
  }
  if (body && body.state === "unknown") {
    setBanner("还没有查到开始结果。可点「取消等待」结束本次请求，再重新选择。", "info");
  }
  } finally {
    model.reconciling = false;
    refreshControls();
  }
}
async function cancelPendingStart() {
  // RW03：确认改走 sheet（askConfirm("cancelstart")，用户决策 1），这里只做取消动作。
  // UI-F5：失败经 showSheetError 就地说明并回 false，成功收 sheet
  if (!model.pending || model.pending.done || model.cancelingStart) return false;
  const pending = model.pending;
  pending.canceling = true;
  model.cancelingStart = true;
  try {
    const { body } = await postAction({action:"cancel_start_request",
      args:{request_id:pending.request_id}});
    if (body && body.ok && body.state === "canceled") {
      pending.done = true;
      pending.outcome = "canceled";   // A-BUG-1：终态原因随 pending 记下，立即放行新的开始
      setBanner("已取消这次开始，可以重新选择报名活动。", "info");
    } else {
      showSheetError(String((body && (body.text || body.error))
        || "取消结果尚未确认，请刷新核对"));
      return false;
    }
  } finally {
    pending.canceling = false;
    model.cancelingStart = false;
    refreshControls();
  }
  if (model.paired) void poll(true);
  return true;
}
async function stopPlan() {
  // SH03：确认改走 sheet（askConfirm("stop")，用户决策 1），这里只做停止动作。
  // UI-F5：失败经 showSheetError 就地说明并回 false，成功收 sheet
  const planId = model.plan && model.plan.plan_id;
  if (!planId) return false;
  const { body } = await postAction({ action: "stop_plan", args: { plan_id: planId } });
  if (body && body.error) {
    showSheetError("没能停止计划：" + String(body.text || body.error));
    return false;
  }
  void poll(true);
  return true;
}
/* 电脑窗口被隐藏到后台时，从这里把它叫回来：只发一个无参数动作，不动任何报名状态 */
async function showComputerWindow() {
  const { status, body } = await postAction({ action: "show_window", args: {} });
  if (status !== 200 || (body && body.ok === false)) {
    addLog("没能显示电脑窗口：" + String((body && (body.text || body.error)) || status));
    return;
  }
  addLog("已请电脑把窗口显示出来");
}
/* 取消一场（SH04）：确认改走 sheet（askConfirm("cancelTask")，用户决策 1），这里只做动作。
   B-P1-1：取消被点卡片的那一场——后端（Api.cancel_task→PlanCoordinator.cancel_task→
   phone_rules 白名单）本就收任意 task_id，桌面端也早就在发任意 taskId；
   旧实现固定发 tasks[0] 是前端自设的限制，多场计划会取消错对象。
   UI-F5：失败经 showSheetError 就地说明并回 false（确认 sheet 保持打开），成功收 sheet */
async function cancelTask(taskId) {
  const planId = model.plan && model.plan.plan_id;
  const task = ((model.plan && model.plan.tasks) || [])
    .find((t) => t && String(t.task_id) === String(taskId));
  if (!planId || !task) return false;
  const { body } = await postAction({
    action: "cancel_task", args: { plan_id: planId, task_id: task.task_id } });
  if (body && body.error) {
    showSheetError("没能取消这一场：" + String(body.text || body.error));
    return false;
  }
  void poll(true);
  return true;
}
/* RS01 结果态底栏两钮（原型 reselect/finishView，Phone.dc.html:933-934）：都清计划回草稿，
   并按 plan_id 记住已收起（服务端快照一直带终态计划，见 ingest 的 dismissedPlanId）。
   重新选择：把没成功（failed/canceled）的场放回选择集——放回的依据是 state.activities
   里对应活动仍可选（actionable：未报名、未截止、时间已知、不与已报名冲突，传入 businessNowS 校验）；
   放不回的场（已截止/时间未知）记进运行记录，不硬塞进勾选（原型是无条件放回，偏差已记） */
function reselectFailed() {
  const tasks = (model.plan && model.plan.tasks) || [];
  model.dismissedPlanId = String((model.plan && model.plan.plan_id) || "");
  model.plan = null;
  const picked = [];
  let skipped = 0;
  tasks.forEach((t) => {
    const st = String(t.status || "");
    if (st !== "failed" && st !== "canceled") return;
    const item = (model.items || []).find((i) => i && i.id === t.activity_id);
    if (item && PhoneModel.actionable(item, model.items, PhoneModel.businessNowS(model))) picked.push(item.id);
    else skipped += 1;
  });
  model.selected = picked;
  model.listOpen = false;
  model.notice = "";
  if (skipped > 0) addLog("有 " + skipped + " 场已截止或时间冲突，没能放回选择集，可另选其他场次");
  renderItems();
  renderPlan();   // A-BUG-2：任务卡随计划清空立即重画，不残留旧卡到下一次 poll
}
function finishPlanView() {
  model.dismissedPlanId = String((model.plan && model.plan.plan_id) || "");
  model.plan = null;
  model.selected = [];
  model.listOpen = false;
  model.notice = "";
  renderItems();
  renderPlan();   // A-BUG-2：完成后 #plan-tasks 立即清空，不等下一次轮询
}
async function saveRetry() {
  const { body } = await postAction({ action: "save_retry_policy", args: {
    retry_policy: {
      retry_for_s: Number(model.retry.retry_for_s),
      max_attempts: Number(model.retry.max_attempts || 0) } } });
  if (body && body.error) addLog("没能保存重试设置：" + String(body.text || body.error));
  else model.retryDirty = false;
}
function fillRetryOptions(options) {
  const sel = $("retry-for");
  sel.textContent = "";
  (options.choices || []).forEach((choice) => {
    const opt = document.createElement("option");
    opt.value = String(choice.value);
    opt.textContent = String(choice.label);
    sel.appendChild(opt);
  });
  sel.value = String(model.retry.retry_for_s);
}

/* SH01 核对 sheet 渲染（原型 isReview 段，Phone.dc.html:302-309）：批次头+条目+移除钮
   （reviewBatches）、提醒 ul.pw（preStartWarnings）；尝试设置字段为静态 markup
   （#retry-panel 随 SH01 从更多面板迁入），这里只写动态部分；主钮文案随提醒切换 */
function renderReview() {
  const picked = (model.items || []).filter((item) => model.selected.indexOf(item.id) >= 0);
  const box = $("review-items");
  box.textContent = "";
  PhoneModel.reviewBatches(picked, PhoneModel.businessNowS(model)).forEach((batch) => {
    const head = document.createElement("div");
    head.className = "bh";
    const time = document.createElement("b");
    time.textContent = batch.time;
    const note = document.createElement("span");
    note.textContent = batch.note;
    head.appendChild(time);
    head.appendChild(note);
    box.appendChild(head);
    batch.items.forEach((tk) => {
      const row = document.createElement("div");
      row.className = "tk";
      const main = document.createElement("div");
      const name = document.createElement("b");
      name.textContent = tk.name;
      main.appendChild(name);
      if (tk.act) {
        const act = document.createElement("small");
        act.textContent = tk.act;
        main.appendChild(act);
      }
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ic";
      btn.setAttribute("aria-label", tk.aria);
      btn.dataset.id = tk.id;
      /* 移除钮图标（原型 tk.remove 的 X，Phone:771）：静态常量串，不带任何用户数据 */
      btn.innerHTML = '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"></path></svg>';
      row.appendChild(main);
      row.appendChild(btn);
      box.appendChild(row);
    });
  });
  const warns = PhoneModel.preStartWarnings(model, picked);
  $("review-warns").innerHTML = warns.map((text) => "<li>" + PhoneModel.escape(text) + "</li>").join("");
  $("review-warns").hidden = !warns.length;   // 原型 hasPreWarn：没有提醒整块不出
  $("btn-review-start").textContent = warns.length ? "仍然开始报名计划" : "开始报名计划";
}
/* SH01 移除条目（原型 tk.remove，Phone:771）：走现有勾选反选（toggle off），不发任何动作；
   移除后计划空了就关 sheet（原型 setState({sheet:''})）。监听挂在 #review-items 上
   （事件委托），重画批次不会叠监听 */
function removeFromReview(id) {
  const res = PhoneModel.pickItem(model.selected, model.items, id, false);
  model.selected = res.selected;
  model.notice = "";
  renderItems();
  if (!model.selected.length) closeSheet(true);
  else renderReview();
}
function openReview() {
  if ($("btn-start").disabled) return;
  renderReview();
  openSheet("review");   // G03：核对面板迁进 sheet 外壳
}
