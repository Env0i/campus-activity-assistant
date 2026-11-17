/* 路线与 LED 的纯推导：站点、时刻、点阵格式。 */

import { RUNNING_STATUSES, effectiveRetryDeadline, executionView, taskDisplayItem } from "./state-task.js";

/* 当前执行窗口的截止：统一走 effectiveRetryDeadline（telemetry 优先，
 * 其次任务 retry_for_s/sign_end/run_started_at 推导），与任务卡、LED
 * 同一个来源，长策略不再显示成 120 秒。 */
export function routeDeadline(task, open, now) {
  return { name: "本次尝试截止", time: effectiveRetryDeadline(task, now) };
}

export function routeTime(ts) {
  const bnMs = businessNowMs();
  const sameDay = bnMs != null && startOfDay(ts * 1000) === startOfDay(bnMs);
  return sameDay ? fmtClock(ts) : whenText(ts * 1000);
}

export function routeTarget() {
  /* 运行中用执行模型的任务；模型没给任务时再按状态兜底（不读原勾选集合） */
  const view = executionView();
  const task = view.task
    || Array.from(S.plan.tasks.values()).find((item) => RUNNING_STATUSES.indexOf(String(item.status)) >= 0)
    || null;
  if (!task) return null;
  const item = taskDisplayItem(task);
  return item ? { item: item, task: task } : null;
}

/* ---------------------------------------------------------------- LED 点阵 */
export function ledSet(text, tone) {
  const el = $("#led");
  if (!el || !window.LED_UI) return; /* led.js 缺席时退回纯文本层，语义不丢 */
  window.LED_UI.renderLed(el, text, tone);
}

/* 点阵只承载倒计时与结论：等待/最后10秒/提交中/成功/失败/停止 */
export function fmtLed(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  const pad = (n) => String(n).padStart(2, "0");
  return pad(Math.floor(value / 3600)) + ":" + pad(Math.floor((value % 3600) / 60)) + ":" + pad(value % 60);
}
