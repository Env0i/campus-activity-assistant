import { setResult } from "../shell/view-result.js";
import { render } from "../shell/actions-render.js";
import { clearSelection } from "../list/actions-selection.js";
/* 计划栏的编排层（运行中这一段）：停止确认、修改计划、重新选择与收尾。 */

import { closeResultPage, PLAN_TERMINAL } from "./state.js";
import { planLate, reselectableIds } from "./state-board.js";
import { paintLogin } from "../login/view.js";
import { setPlanOpen } from "../shell/view-band.js";
import { updateControls } from "./view-controls.js";

export function cancelTask(taskId) {
  if (!S.plan.id || !taskId) return;
  api("cancel_task", S.plan.id, taskId).then((res) => {
    if (res && res.ok === false) addLog(res.text || "这一场已经结束");
  }).catch((err) => addLog("[X] 取消这一场失败：" + msg(err)));
}

/* 停止确认是计划栏里的遮罩弹层（原型 P19 stopAsk），不是原生 dialog：
 * 打开时焦点落「继续计划」；Esc / 继续计划关闭并把焦点还给 #btn-stop；Tab 只在两个按钮间循环 */
export function stopAskOpen() {
  const ask = $("#plan-stop-ask");
  return !!ask && !ask.hidden;
}

export function openStopAsk() {
  const ask = $("#plan-stop-ask");
  if (!ask || !ask.hidden) return;
  ask.hidden = false;
  $("#btn-stop-keep").focus();
}

export function closeStopAsk(restoreFocus) {
  const ask = $("#plan-stop-ask");
  if (!ask || ask.hidden) return;
  ask.hidden = true;
  const opener = $("#btn-stop");
  if (restoreFocus !== false && opener && !opener.disabled) opener.focus();
}

/* 弹层打开时的键盘：Esc 只关弹层（不停止、不穿透到清空选择）；Tab 在两个按钮间循环；
 * Ctrl+F、/ 不抢焦点；Enter 交给当前按钮原生激活 */
export function stopAskKey(event) {
  const key = event.key;
  if (key === "Escape") { event.preventDefault(); closeStopAsk(true); return; }
  if (key === "Tab") {
    const keep = $("#btn-stop-keep");
    const yes = $("#btn-stop-yes");
    const order = [keep, yes];
    const at = order.indexOf(document.activeElement);
    const next = at < 0 ? (event.shiftKey ? yes : keep)
      : order[(at + (event.shiftKey ? order.length - 1 : 1)) % order.length];
    event.preventDefault();
    next.focus();
    return;
  }
  if ((event.ctrlKey && (key === "f" || key === "F")) || key === "/") event.preventDefault();
}

export function stopPlan() {
  if (!S.plan.id) return;
  /* 先确认再停：等待任务会取消、已提交任务可能已生效；Esc/继续计划都不触发停止 */
  openStopAsk();
}

/* 弹层里的「停止计划」：关弹层（不抢焦点，按钮随即变成「正在停止」）后走现有停止流程。
 * 弹层开着时计划恰好结束或已在停止，就只关弹层，不再向后端重复发停止请求 */
export function confirmStopPlan() {
  closeStopAsk(false);
  if (!S.busy || S.stopping) return;
  doStopPlan();
}

/* PB11 原型 RunPhone 的开始记录：「从手机开始了报名计划：2 场预报名等开放」。
 * 电脑自己开始的计划写「已安排 …」（startPlan 的 ack），这一句只给计划来源是手机的那一次。
 * 场次数按后端写进计划快照的 signup_mode 分，拿不到场次就只写前半句，不猜。 */
export function noteStartedFromPhone(tasks) {
  const list = Array.isArray(tasks) ? tasks : [];
  const instant = list.filter((task) => String(task && task.signup_mode || "") === "instant_signup").length;
  const pre = list.filter((task) => String(task && task.signup_mode || "") === "pre_register").length;
  const summary = [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名等开放" : ""].filter(Boolean).join("，");
  addLogFresh("从手机开始了报名计划" + (summary ? "：" + summary : ""));
}

/* 等开放时「修改计划」（决策 014 第 6 条）：复用停止和重选，不改报名调度。
 * 提交中或开放前 100 秒内不可用；停下以后把还没提交的场次放回选择，提示「改完要重新开始」。 */
export function modifyPlan() {
  if (!S.busy || !S.plan.id || S.stopping || planLate()) return;
  const keep = [];
  S.plan.tasks.forEach((task) => {
    if (["queued", "waiting"].indexOf(String(task.status || "")) >= 0) keep.push(String(task.activity_id));
  });
  /* doneN：进入修改时已经结束的场次数，修改说明写「已结束的 N 场不受影响」（原型 modifyS） */
  S.editing = { ids: keep, doneN: S.plan.tasks.size - keep.length };
  /* U9：「计划已暂停」那一句不在这里写——停止还没成功，现在写就是对运行记录说了假话。
   * 等计划真的以 stopped 结束、按 S.editing 放回勾选时，由 features/plan/actions-events.js 的计划结束处理调用本文件的 editPausedLine 写。 */
  doStopPlan();
}

/* PB03 原型 modifyS 的运行记录句。同样的句子可以再来一次（改了又停了又改），
 * 写的时候走 addLogFresh，不被 addLog 的整句去重吞掉。 */
export function editPausedLine(count) {
  return "计划已暂停：" + count + " 场放回草稿修改";
}

/* 结果页「重新选择未成功的场次」：只放回能重报的（不含名额已满、已截止、已报名冲突） */
export function reselectFailed() {
  if (S.busy) return;
  const ids = reselectableIds();
  S.selected.clear();
  ids.forEach((id) => S.selected.add(id));
  S.plan = { id: null, status: "idle", tasks: new Map() };
  closeResultPage();
  S.selectionNotice = "";
  setResult(null);
  render();
}

/* 结果页「完成，回到活动列表」：收起结果，回到空草稿；中、窄档顺便回到时刻表 */
export function finishResult() {
  closeResultPage();
  clearSelection();
  if (typeof setPlanOpen === "function") setPlanOpen(false);
}

/* 后端说「没有这个计划」时不能再说「照常进行」：计划其实已经不在了。
 * 按窗口恢复同一套快照对账，运行记录那句按快照写——快照说还在跑才是停止没成功，
 * 说计划已不在就写修改作废，拿不到快照时保守写停止没成功，不替后端下结论。
 * wasEditing 由停止分支在进入 stopFailed 前记下带过来；桥接异常那一支不写这两句。 */
let stopAttempt = 0;

/* 同一计划再次停止时，旧请求及其快照也不能归属于新的一次停止。 */
function ownsStopReply(planId, attempt) {
  return S.plan.id === planId && stopAttempt === attempt
    && PLAN_TERMINAL.indexOf(S.plan.status) < 0;
}

function resyncPlanFromBootstrap(wasEditing, planId, attempt) {
  api("bootstrap").then((info) => {
    if (!ownsStopReply(planId, attempt)) return;
    if (!info) { if (wasEditing) addLog("停止没成功，计划继续运行"); return; }
    /* 归属已由 ownsStopReply 核对：统一恢复入口同步允许的忙态与停止位 */
    ingestBootstrapPlan(info, true);
    if (wasEditing) addLog(info.busy ? "停止没成功，计划继续运行" : "计划已经结束，修改作废");
    render();
  }).catch(() => {
    if (!ownsStopReply(planId, attempt)) return;
    if (wasEditing) addLog("停止没成功，计划继续运行");
  });
}

export function doStopPlan() {
  S.stopNote = null;
  if (!S.plan.id) return;
  /* 立刻给「正在停止」的反馈：后端在按进程树终止 worker，
   * busy 要等 plan_done 才解锁，中间不能看起来像卡死 */
  S.stopping = true;
  paintLogin();
  updateControls();
  addLog("正在停止计划：结束还在重试的场次…");
  /* 停止没成功（后端拒绝，或桥接异常）：计划仍在运行。若这次停止是「修改计划」发起的，
   * 一并退出修改中（U1）——否则计划栏标签、说明和「放弃修改」会挂在一个还在跑的计划上。 */
  const planId = S.plan.id;
  const attempt = ++stopAttempt;
  const stopFailed = (line, noteText) => {
    const wasEditing = !!S.editing;
    S.stopping = false;
    S.editing = null;
    if (noteText) S.stopNote = { planId: planId, text: noteText };
    paintLogin();
    updateControls();
    addLog(line);
    /* 后端拒答那一支不属于能确认的失败：那句挪到快照对账后按 info.busy 写。
     * 这里只保留桥接异常那一支（带停止说明）照旧写，并把 wasEditing 交给对账分支。 */
    if (noteText && wasEditing) addLog("停止没成功，计划继续运行");
    render();
    return wasEditing;
  };
  api("stop_plan", planId).then((res) => {
    if (!ownsStopReply(planId, attempt)) return;
    if (res && res.ok === false) {
      const wasEditing = stopFailed(res.text || "当前没有这个计划");
      resyncPlanFromBootstrap(wasEditing, planId, attempt);
    }
  }).catch((err) => {
    if (!ownsStopReply(planId, attempt)) return;
    /* 桥接异常才写「照常进行」：这是我们能确认的失败；后端说没有计划要走快照对账 */
    stopFailed("[X] 停止计划失败：" + msg(err),
      S.editing ? "没能暂停，计划照常进行。" : "没能停止，计划照常进行。");
  });
}
