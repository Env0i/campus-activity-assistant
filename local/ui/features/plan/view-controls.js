/* 计划栏按钮门禁的视图。 */

import { termsLocked } from "../terms/state.js";
import { paintDock } from "./view-dock.js";
import { paintWhy } from "./view-draft.js";
import { paintBoardActions } from "./view.js";

export function updateControls() {
  const componentDown = !!S.runtime.error;
  /* 条款门禁（决策 013）：未同意时登录/刷新/开始全部禁用；离线演示不受限 */
  const termsGate = termsLocked();
  /* 缺组件：登录/开始都禁用（点了也是结构化失败）；刷新保持可用——复查组件并恢复的唯一通道 */
  $("#btn-login").disabled = S.busy || componentDown || termsGate;
  $("#btn-refresh").disabled = S.listState === "loading" || termsGate || !!S.cancel.busyId;
  /* 帮助任何状态都可打开；运行中只禁重看引导，原因写在按钮上。 */
  paintReplayButtons();
  const validation = validateSelection();
  /* 开始门禁：真实计划只在学校接口确认登录有效（valid）后可点；
   * checking/unknown/none/expired 一律禁用（demo 模式例外，供视觉演示）。
   * checking 必须显式排除：新一轮检查开始时不清旧 result，
   * 不排除的话上次 valid 会放行尚未确认的检查期。 */
  const loginReady = !!S.demo || (!S.login.checking && S.login.result === "valid");
  const canStart = !S.busy && !S.starting && !S.cancel.busyId && !componentDown && !termsGate && loginReady && S.selected.size > 0
    && validation.errors.length === 0 && validation.conflicts.length === 0
    && S.listState === "ready";
  /* 独立北京时间门禁（决策 012）：时钟不可读或不在 ready/holdover 时开始禁用 */
  const clockDown = businessNowMs() === null && !S.demo;
  $("#btn-plan").disabled = !canStart || clockDown;
  /* 有开始前提醒时主按钮改叫「仍然开始报名计划」：只提醒不拦 */
  const warned = (Number(S.preWarnCount) || 0) > 0;
  $("#btn-plan").textContent = S.busy ? "计划运行中"
    : (S.startRequest.state === "reconciling" ? "正在确认是否启动…"
      : (S.starting ? "正在提交…"
        : (clockDown ? "北京时间未校准" : (S.editing ? "重新开始计划"
          : (warned ? "仍然开始报名计划" : "开始报名计划")))));
  paintWhy();
  $("#btn-stop").disabled = !S.busy || !S.plan.id || S.stopping;
  $("#btn-stop").textContent = S.stopping ? "正在停止…" : "停止计划";
  /* 运行中底部换成「修改计划 / 停止计划」；草稿时是开始前提醒、检查和主按钮 */
  const runActions = $("#run-actions");
  if (runActions) runActions.hidden = !S.busy;
  $("#btn-clear-plan").disabled = S.busy || S.starting || (!S.selected.size && !S.plan.tasks.size);
  document.querySelectorAll(".row-check").forEach((check) => {
    const item = findItem(check.dataset.id);
    /* 与行渲染同一份判据：已报名/已截止/忙碌都禁用，已截止仍可查看。
     * 与 list.js rowHtml 的 checkDisabled 同一条判据，改一处要同步另一处（H2：此前这里缺 signStartPending） */
    check.disabled = S.busy || S.starting || termsLocked() || !isEligibleForPlan(item) || !!signedClash(item) || signStartPending(item);
  });
  /* 取消报名按钮与行渲染同一份互斥判据：计划、刷新、登录或另一场取消都会置灰并写原因 */
  document.querySelectorAll("[data-cancel]").forEach((btn) => {
    const id = btn.dataset && btn.dataset.cancel;
    if (!id) return;
    const block = cancelBlock(id);
    btn.disabled = block.off;
    btn.title = block.why;
    btn.textContent = S.cancel.busyId === id ? "正在取消…" : "取消报名";
  });
  paintBoardActions();
  paintDock();
  /* 计划结束（不再运行）时收起停止确认弹层；焦点在弹层里就移到「完成」按钮，没有就落到 #board */
  if (!S.busy) {
    const ask = $("#plan-stop-ask");
    if (ask && !ask.hidden) {
      const active = document.activeElement;
      const inside = !!active && (active.id === "btn-stop-keep" || active.id === "btn-stop-yes");
      ask.hidden = true;
      if (inside) {
        const finish = $("#btn-finish");
        const target = finish && !finish.hidden && !($("#result-actions") || {}).hidden ? finish : $("#board");
        if (target && target.focus) {
          if (target === $("#board")) target.tabIndex = -1;
          target.focus();
        }
      }
    }
  }
}
