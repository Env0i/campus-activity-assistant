/* 中窄档底部计划条的视图。 */

import { resultMode, resultView, selectionSummary } from "./state-board.js";
import { startBlocker } from "./view-draft.js";

/* 计划条：已选几场 + 查看计划 + 开始；有开始前提醒时不给「开始」，先让用户看计划。
 * 四态照原型 dockTitle / dockSub（TF05 / PB16）：
 *  草稿  标题「已选 N 场」/「还没选活动」，副文 还差一步 > 开始前提醒 > 摘要句（优先级同原型）；
 *  修改中  「修改中：已选 N 场」+「计划已暂停，改完要重新开始」；
 *  运行中  沿用「报名计划运行中」+ 倒计时（原型取 LED 标签，表里没列这一行，不动）；
 *  结果  结论标题 / 正文，与结果页同一来源（resultView），窄档结果页藏在计划栏里时 dock 也要说结论。 */
export function paintDock() {
  const dock = $("#plan-dock");
  if (!dock) return;
  const narrow = !!S.band && S.band !== "wide";
  dock.hidden = !narrow || !!S.planOpen;
  if (dock.hidden) return;
  const items = selectedItems();
  const plan = $("#btn-plan");
  const warns = S.busy ? 0 : Number(S.preWarnCount) || 0;
  const result = !S.busy && resultMode();
  let title = items.length ? "已选 " + items.length + " 场" : "还没选活动";
  let sub = "";
  if (S.busy) {
    title = "报名计划运行中";
    sub = $("#countdown") ? String($("#countdown").textContent || "") : "";
  } else if (result) {
    const res = resultView();
    title = res.title;
    sub = res.text;
  } else if (S.editing) {
    title = "修改中：已选 " + items.length + " 场";
    sub = "计划已暂停，改完要重新开始";
  } else {
    /* 「还差一步」与计划栏里的 #plan-why 同一个判据：开始按钮禁用且不是正在开始 */
    const blocker = plan && plan.disabled && !S.starting ? startBlocker() : null;
    sub = blocker ? "还差一步：" + blocker.text
      : (warns > 0 ? "有 " + warns + " 条提醒，开始前先看一眼" : selectionSummary(items));
  }
  const start = $("#btn-dock-start");
  if (start) start.hidden = S.busy || result || warns > 0 || !plan || !!plan.disabled;
  $("#dock-title").textContent = title;
  $("#dock-sub").textContent = sub;
}
