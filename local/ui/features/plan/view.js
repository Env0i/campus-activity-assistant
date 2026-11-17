/* 计划栏的视图层：大屏标题、运行提示、结果页与任务卡的 DOM 呈现。 */

import { termsLocked } from "../terms/state.js";
import { RUNNING_STATUSES, executionView, taskDisplayDetail, taskDisplayLabel, taskModePrefix, verifiedSigned } from "./state-task.js";
import { boardPlanState, boardTargetItem, editNoteText, resultCounts, resultMode, resultView, reselectableIds, runCaption, runTagText, runWarnView, selectionSummary, stopReasonText } from "./state-board.js";
import { boardPhase } from "./state-machine.js";

/* 计划栏标题区的样子表：一个阶段一项，键与 BOARD_PHASES 一一对应。
 * 定值直接写；要看别的事实的写成小函数，接 (view, next, items)，函数体就是原分支里的表达式。 */
export const BOARD_STYLE = Object.freeze({
  first_use: {
    tag: "首次使用", tone: "off", dot: true,
    title: "登录后开始",
    text: "活动会在登录完成后自动加载。",
  },
  logging_in: {
    /* 登录尝试期间 S.busy 也为真，但这不是报名计划：
     * 不能把大屏说成「正在准备报名」，否则用户以为点登录触发了抢报名。 */
    tag: "登录中", tone: "amber", dot: true,
    title: "正在打开登录窗口",
    text: "在浏览器里登完再回来；中途关掉窗口会保留原来的登录状态。",
  },
  result: {
    /* 结果页是独立分支（原型 phase === 'result' 的 res 段，P1）：标签、结论标题、副行都来自 resultView；
     * 不写地点时间 meta，成功场次被移出选择集合也不会退回草稿的「下一场」 */
    tag: () => resultView().tag, tone: () => resultView().tone, dot: true,
    title: () => resultView().title,
    text: () => resultView().text,
  },
  terms_hold: {
    /* 条款没同意（且登录过）：原型渲染函数 draft 段的 !s.terms 覆盖——标签「已暂停」，
     * 没选活动时标题副行说停用了什么（帮助和设置照常可用）。 */
    tag: "已暂停", tone: "off", dot: true,
    title: () => S.terms.unknown ? "重新确认条款后才能报名" : "同意条款后才能报名",
    text: () => S.terms.unknown ? "登录、活动列表和报名计划暂时停用。帮助和设置照常可用。"
      : "登录、活动列表和报名计划都停用了。帮助和设置照常可用。",
  },
  broken: {
    /* 组件问题只留短状态（原型 draft 段 s.list === 'broken'）：完整原因与恢复动作在顶部横幅 */
    tag: "不可用", tone: "red", dot: true,
    title: "暂时不能报名",
    text: "程序组件缺失，处理办法在顶部提示里。",
  },
  list_error: {
    /* 列表失败只留短状态：完整原因与「重试」在列表空态 */
    tag: "需重试", tone: "red", dot: true,
    title: "活动暂时没加载",
    text: "具体原因看左边列表的提示。",
  },
  list_loading: {
    /* 加载态与「有没有选中」无关（原型 Main.dc.html:2006 只看 !sel.length）：
     * 手上有旧列表时点刷新同样要立刻显示在加载，否则界面像没反应。
     * 列表还在拉：不得把「近期没有要开放的活动」当事实说出口 */
    tag: "加载中", tone: "off", dot: true,
    title: "活动列表正在加载",
    text: "先等这一次加载结束。",
  },
  run_target: {
    /* 运行中（原型渲染函数 ex 段）：标题与批次数都来自同一个执行目标，单场结束不会把这里改成结论。
     * 标题下面只留一行说明，不再写地点时间（原型运行态没有）；三个阶段分开说：
     * 等开放 ≠ 已开放待提交（代码独有的「准备报名」）≠ 真正在提交。 */
    tag: (view) => runTagText(view),
    tone: (view) => view.phase === "submitting" ? "red" : "amber", dot: true,
    title: (view) => view.item ? view.item.name : "这一场活动",
    text: (view) => runCaption(view),
  },
  run_settling: {
    /* 没有可执行任务、plan_done 还没到：准备中 / 正在汇总，不提前报成功 */
    tag: "汇总中", tone: "amber", dot: true,
    title: "正在汇总结果",
    text: "每一场都结束了，正在汇总这一轮的结果。",
  },
  run_preparing: {
    tag: "准备中", tone: "amber", dot: true,
    title: "正在准备报名",
    text: "计划已经接管，正在核对每一场的开放时间。",
  },
  next_open: {
    tag: "开放中", tone: "amber", dot: false,
    title: (view, next) => next.name,
    meta: (view, next) => boardMetaHtml(next),
  },
  next_upcoming: {
    /* 副行只留地点与时间（原型 draft 段 nextIt），「选这一场」按钮就在票区下面 */
    tag: "下一场", tone: "amber", dot: true,
    title: (view, next) => next.name,
    meta: (view, next) => boardMetaHtml(next),
  },
  school_empty: {
    /* 学校成功返回 0 场（原型 draft 段）：大屏只留一句短状态，完整原因在列表空态，不在这里复读 */
    tag: "暂时没有", tone: "off", dot: true,
    title: "学校当前没有活动",
    text: "稍后刷新再看。",
  },
  clock_pending: {
    /* 没有可信现在：不能断言「没有可报名的场次」，也不能显示伪计数。
     * 只给短状态和单一恢复入口（打开时间详情重新校准）。 */
    tag: "时间待校准", tone: "amber", dot: true,
    title: "时间待校准",
    html: "校准北京时间后才能判断哪些场次可以报名。"
      + '<button type="button" class="btn btn-line btn-mini" data-open-clock>查看时间详情</button>',
  },
  none_eligible: {
    /* 列表里有活动，只是没有可执行目标（全已报名 / 全已截止 / 报名时间待公布）：
     * 这不是「学校没返回」，数据仍在列表里，别替学校下结论。 */
    tag: "暂时没有", tone: "off", dot: true,
    title: "没有可报名的场次",
    text: "列表里的活动已报名、已截止或还没公布报名时间。",
  },
  none_upcoming: {
    tag: "暂时没有", tone: "off", dot: true,
    title: "近期没有要开放的活动",
    text: "可能还没公布报名时间，也可能都报过了。过一会儿点「刷新」看看。",
  },
  selected_paused: {
    /* 选了活动（原型 draft 段）：标题一律「已选 N 场」，副行一句汇总；地点时间和场名都在票里，不再复读 */
    tag: "已暂停", tone: "off", dot: true,
    title: (view, next, items) => "已选 " + items.length + " 场",
    text: (view, next, items) => selectionSummary(items),
  },
  editing: {
    tag: "修改中", tone: "amber", dot: true,
    title: (view, next, items) => "已选 " + items.length + " 场",
    text: (view, next, items) => selectionSummary(items),
  },
  selected: {
    tag: "报名计划", tone: "amber", dot: true,
    title: (view, next, items) => "已选 " + items.length + " 场",
    text: (view, next, items) => selectionSummary(items),
  },
});

/* 表项里放定值还是小函数：小函数按 (view, next, items) 取，定值原样用 */
function styleValue(value, view, next, items) {
  return typeof value === "function" ? value(view, next, items) : value;
}

export function paintSelected() {
  const box = $("#selected");
  const meta = $("#selected-meta");
  const boardText = $("#board-text");
  const items = selectedItems();
  const next = boardTargetItem();
  /* 运行中以 executionView() 为唯一目标：标题、路线、LED、批次数同源，
   * 不再从原勾选集合里补位（取消的场次不能继续当目标）。 */
  const view = executionView();
  box.className = "b-title";
  meta.innerHTML = "";
  boardText.textContent = "";
  const style = BOARD_STYLE[boardPhase({
    busy: !!S.busy,
    present: S.login.present,
    runtimeError: !!S.runtime.error,
    loginPending: !!S.login.loginPending,
    resultMode: resultMode(),
    termsLocked: termsLocked(),
    listState: S.listState,
    itemsCount: S.items.length,
    selectedCount: items.length,
    hasNext: !!next,
    nextOpenNow: !!next && stateOf(next) === "open",
    clockKnown: bnowS() !== null,
    demo: !!S.demo,
    editing: !!S.editing,
    runPhase: view.phase,
  })];
  setBoardTag(styleValue(style.tag, view, next, items),
    styleValue(style.tone, view, next, items), style.dot);
  box.textContent = styleValue(style.title, view, next, items);
  if (style.html) boardText.innerHTML = styleValue(style.html, view, next, items);
  else boardText.textContent = styleValue(style.text || "", view, next, items);
  if (style.meta) meta.innerHTML = styleValue(style.meta, view, next, items);
}

export function setBoardTag(text, tone, dot) {
  const tag = $("#board-tag");
  const label = $("#board-tag-text");
  if (!tag || !label) return;
  tag.dataset.tone = tone || "amber";
  tag.dataset.dot = dot === false ? "false" : "true";
  label.textContent = text;
}

export function paintBoardState() {
  const board = $("#board");
  if (!board) return;
  board.dataset.planState = boardPlanState();
}

export function boardMetaHtml(item) {
  if (!item) return "";
  const placeText = String(item.place || "地点待定");
  const place = esc(placeText);
  const act = esc(activityTimeText(item));
  /* 大屏地点默认两行；按钮原生支持 Enter/Space，聚焦即可展开全文（R19）。
   * 表格的 .c-place 用同一套「两行 + 聚焦展开」口径，但互不依赖。 */
  return '<button type="button" class="b-place" data-place-toggle aria-expanded="false"'
    + ' title="' + esc("完整地点：" + placeText + "（Enter 展开/收起）") + '">'
    + '<svg class="i" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.3-6-10a6 6 0 1 1 12 0c0 4.7-6 10-6 10z"/><circle cx="12" cy="11" r="2.2"/></svg>'
    + '<span class="b-place-text">' + place + '</span></button>'
    + '<span><svg class="i" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>' + act + "</span>";
}

export function paintBoardActions() {
  const actions = $("#route-actions");
  const quickPick = $("#btn-board-pick");
  const checks = $("#plan-checks");
  const headed = $("#headed-label");
  const clear = $("#btn-clear-plan");
  const start = $("#btn-plan");
  const policyFor = $("#retry-for") ? $("#retry-for").closest(".policy-select") : null;
  const policyMax = $("#max-attempts") ? $("#max-attempts").closest(".policy-select") : null;
  if (!actions) return;
  const result = resultMode();
  /* 「选这一场」在正文票区下面（原型 hasPick）：没选活动、有下一场、列表已加载、条款已同意、不在结果页 */
  const showPick = !S.busy && !result && !selectedItems().length && !!boardTargetItem()
    && S.listState === "ready" && !termsLocked();
  if (quickPick) quickPick.hidden = !showPick;
  /* 结果页（计划结束）只留「重新选择 / 完成」，不再摆开始按钮 */
  /* 「清空」只在草稿且有选中时出现（原型 showClear）；运行中、结果页都不显示 */
  if (clear) clear.hidden = S.busy || result || !S.selected.size;
  if (S.busy || result) {
    actions.hidden = true;
    return;
  }
  actions.hidden = false;
  /* 主按钮一直在（禁用时下面写「还差一步」）；没登录由「还差一步：还没有登录」+「去登录」承担 */
  [checks, headed, policyFor, policyMax, start].forEach((el) => { if (el) el.hidden = false; });
  const restore = $("#btn-edit-restore");
  if (restore) restore.hidden = !S.editing;
  paintEditNote();
}

export function paintEditNote() {
  const note = $("#edit-note");
  if (!note) return;
  note.hidden = !S.editing || S.busy;
  note.textContent = S.editing && !S.busy ? editNoteText() : "";
}

export function paintRunPanel() {
  const warn = $("#run-warn");
  const hint = $("#plan-hint");
  const modify = $("#btn-modify");
  const why = $("#modify-why");
  if (!warn || !hint) return;
  if (!S.busy || !S.plan.id) {
    warn.hidden = true;
    hint.hidden = true;
    if (why) why.hidden = true;
    return;
  }
  const warnView = runWarnView(bnowS());
  const late = warnView.late;
  const waitList = warnView.waitList;
  const submitting = warnView.submitting;
  const text = warnView.text;
  const tone = warnView.tone;
  const act = warnView.act;
  warn.hidden = !text;
  warn.dataset.tone = tone;
  /* 每秒走字也调这里（tick.js，离开放 100 秒时「来得及」要改成「来不及」）：内容没变就不重写，
   * 免得「重新登录」按钮每秒重建、键盘焦点丢掉 */
  const html = text ? "<span>" + esc(text) + "</span>"
    + (act ? '<button type="button" data-act="' + act.act + '">' + esc(act.label) + "</button>" : "") : "";
  if (warn.dataset.html !== html) {
    warn.innerHTML = html;
    warn.dataset.html = html;
  }
  const fromPhone = String(S.plan.source || "") === "phone";
  hint.hidden = false;
  hint.textContent = "可以最小化窗口，但不要关闭工具或让电脑睡眠。"
    + (fromPhone ? "这个计划是从手机开始的，在电脑和手机上都能看进度、停止。" : "");
  /* 原型 modifyInfo.ok：没有还没提交的场次时也不能修改（没有能放回草稿的） */
  if (modify) modify.disabled = late || S.stopping || !waitList.length;
  if (why) {
    /* 修改说明逐字照原型 modifyInfo */
    why.hidden = false;
    why.textContent = submitting ? "有场次正在提交，现在不能修改。"
      : (late ? "有场次 100 秒内开放，工具已在准备，现在不能修改。"
        : "还没提交的场次可以放回草稿，改完要重新开始。");
  }
}

export function paintResultPanel() {
  const stats = $("#plan-stats");
  const actions = $("#result-actions");
  const done = resultMode();
  if (stats) {
    const c = resultCounts();
    /* 顺序和颜色照原型 .stats：已报名 ok、名额已满 wait、报名未成功 bad、错过了 bad、待核对 ask、已取消 wait */
    const cells = [[c.ok, "已报名", "ok"], [c.full, "名额已满", "wait"], [c.bad, "报名未成功", "bad"],
      [c.missed, "错过了", "bad"], [c.pending, "待核对", "ask"], [c.canceled, "已取消", "wait"]].filter((cell) => cell[0] > 0);
    stats.hidden = !done || !cells.length;
    stats.innerHTML = done ? cells.map((cell) => '<div data-tone="' + cell[2] + '"><strong>' + cell[0]
      + "</strong><span>" + cell[1] + "</span></div>").join("") : "";
  }
  if (actions) {
    /* 页脚只有两个按钮（原型 res 模板）：重新选择未成功的场次（有可重选时）、完成，回到活动列表 */
    actions.hidden = !done;
    const reselect = $("#btn-reselect");
    if (reselect) reselect.hidden = !done || !reselectableIds().length;
  }
}

export function paintPlan() {
  const conflictBox = $("#plan-conflicts");
  const validation = validateSelection();
  const messages = [];
  if (S.selectionNotice) messages.push("<div class=\"conflict-item\"><strong>选择提醒</strong><br>" + esc(S.selectionNotice) + "</div>");
  validation.errors.forEach((error) => messages.push("<div class=\"conflict-item\"><strong>" + esc(error.title) + "</strong><br>" + esc(error.text) + "</div>"));
  validation.conflicts.forEach((conflict) => messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong><br>「" + esc(conflict.left.name) + "」与「" + esc(conflict.right.name) + "」举办时段重叠（" + esc(shortTime(conflict.left.act_start)) + " – " + esc(shortTime(conflict.left.act_end)) + "），只能选其中一场。</div>"));
  conflictBox.innerHTML = messages.join("");
  /* 选择提醒和冲突是草稿内容：结果页不摆（原型 res 模板没有），留在选择里的失败场次回到草稿后照常提醒 */
  conflictBox.hidden = messages.length === 0 || resultMode();

  const tasksBox = $("#plan-tasks");
  const tasks = Array.from(S.plan.tasks.values());
  /* 同一帧用同一个业务时刻；未知传 null，由任务卡显示「等待开放/待校准」 */
  const now = bnowS();
  /* 任务卡只在运行中和结果页出现；草稿（含结果页关掉以后）不摆上一轮的卡片 */
  const showTasks = tasks.length && (S.busy || resultMode());
  tasksBox.innerHTML = showTasks ? tasks.map((task) => taskHtml(task, now)).join("") : "";
  paintCountdown();
  paintTickets();
  paintPolicyLine();
  paintRunPanel();
  paintResultPanel();
}

/* 每场准备好以后写明提交方式（架构方案 3.1）：直接提交，或改用页面点击并写原因 */
export function taskViaHtml(task) {
  const path = String(task && task.path || "");
  if (path === "direct") return '<small class="t-via">直接提交，不经过活动页</small>';
  if (path === "click") {
    const why = String(task.path_reason || "").trim();
    return '<small class="t-via" data-tone="warn">改用页面点击' + (why ? "：" + esc(why) : "")
      + "。活动页已提前打开</small>";
  }
  return "";
}

export function taskHtml(task, now) {
  const state = String(task.status || "queued");
  /* 标签与说明都按显示阶段改写：raw submitting 可能只是提前开页的预热 */
  const label = taskDisplayLabel(task);
  const cls = taskClass(state, task);
  /* 混合计划每场显示自己的模式：快照带 signup_mode，旧载荷按时间现算 */
  const mode = String(task.signup_mode || modeOf(task));
  const modePrefix = taskModePrefix(task);
  const stop = String(task.stop_reason || "");
  const tried = Math.max(0, Math.floor(Number(task.attempts) || 0));
  let detail = task.reason || task.detail || "";
  if (RUNNING_STATUSES.indexOf(state) >= 0) {
    /* 等待 / 准备 / 提交 / 等电脑自动登录共用一份解释（每秒走字也用它）；typing 的等待文案只在没有阶段说明时兜底 */
    detail = taskDisplayDetail(task, now)
      || (state === "waiting" ? (mode === "pre_register" ? "等待报名开放" : "报名已开放，马上开始") : detail);
  } else if (verifiedSigned(task)) {
    /* 刷新核对：学校列表显示这场已报名，就按成功说，不再让用户去核对（原型 card.verify） */
    detail = "刷新核对：学校显示已报名";
  } else if (state === "failed" && taskMissedBySleep(task)) {
    /* 原型 Slept 画板的 reason 原句（LS22 / PB15）；盖过 auth_unavailable 等「没提交」的泛说法 */
    detail = "电脑睡眠期间到了开放时间，没有提交。";
  } else if (state === "failed" && stop === "full") {
    detail = "学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。" + (tried ? "已提交 " + tried + " 次" : "");
  } else if (state === "canceled") {
    /* 整个计划停下时还没提交的场次 vs 用户逐场取消的（原型 finishState / card.cancel） */
    detail = String(S.plan.status || "") === "stopped" ? "计划已停止，这一场没有提交" : "你取消了这一场";
  } else if (state === "failed") {
    if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(String(task.task_id))
        && S.listState === "ready") {
      detail = "刷新核对：学校列表还没显示已报名，可能有延迟，去活动页看一眼；本工具不会再自动重发";
    } else if (stop === "unconfirmed") {
      /* 已发出的请求撤不回来：只陈述「发过几次、没拿到回应」，不下失败结论（原型 finishState） */
      detail = "已提交 " + tried + " 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动页看一眼，或稍后刷新核对。工具不会再自动重发。";
    } else if (stop === "auth_unavailable") {
      detail = "登录状态无法确认，本场没有提交 · 检查网络后刷新重试";
    } else {
      const bits = [];
      if (task.attempts) bits.push("提交了 " + task.attempts + " 次");
      const stopNote = String(task.outcome_label || "") || stopReasonText(task.stop_reason);
      if (stopNote && stop !== "success" && stop !== "already_signed") bits.push(stopNote);
      if (bits.length) detail = (detail ? detail + "（" : "") + bits.join("，") + (detail ? "）" : "");
    }
  } else if (state === "success") {
    /* 学校回包原话（last_reason）有就引用，去掉句末标点；没有就只说核对结论 */
    const said = String(task.last_reason || "").trim().replace(/[！!。.]+$/, "");
    detail = (said ? "学校回“" + said + "”，" : "") + "结束时向学校核对过：已报名";
  }
  const canCancel = ["queued", "waiting"].indexOf(state) >= 0 && S.busy;
  /* 待核对场次只给「刷新核对」：刷新活动列表看这一场是否已报名（ui-amendment-001 选项 A），不自动重发；
   * 不做「打开活动页」（后端没有按活动打开学校页面的接口，b-amendment-007） */
  const canVerify = !S.busy && stop === "unconfirmed" && !verifiedSigned(task);
  /* 名称与状态同排，说明在下，按钮另起一行（原型 .task / .t-acts） */
  const actionsHtml = (canCancel ? "<button class=\"task-cancel\" type=\"button\" data-task-id=\"" + esc(task.task_id) + "\">取消这一场</button>" : "")
    + (canVerify ? "<button class=\"task-cancel task-verify\" type=\"button\" data-task-id=\"" + esc(task.task_id) + "\">刷新核对</button>" : "");
  return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) + "\"><strong class=\"task-name\" title=\"" + esc(task.name) + "\">" + esc(task.name) + "</strong><span class=\"task-state " + cls + "\">" + esc(label) + "</span><span class=\"task-detail\">" + esc(modePrefix + detail) + "</span>" + taskViaHtml(task) + (actionsHtml ? "<div class=\"task-actions\">" + actionsHtml + "</div>" : "") + "</div>";
}
