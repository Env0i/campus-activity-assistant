import { setBusy } from "../shell/actions-render.js";
import { render } from "../shell/actions-render.js";
/* 计划栏的编排层：写完状态统一重画、发起刷新。 */

import { PLAN_TERMINAL, admitPlanEvent, closeResultPage, mergeTask, planEventOwns } from "./state.js";
import { noteStartedFromPhone } from "./actions-run.js";
import { presentPlanDone, showTaskResult } from "./actions-events.js";

/* 同计划状态推进：已定终态不回退，运行态照常更新（P1） */
export function advancePlanStatus(incoming) {
  if (PLAN_TERMINAL.indexOf(S.plan.status) >= 0) return;
  S.plan.status = String(incoming || "ready");
  setBusy(["ready", "running"].indexOf(S.plan.status) >= 0);
}

/* 实时 plan 事件与页面恢复快照共用归属：同一计划已定终态时只补任务详情。
 * 恢复（restore）只回放显示，不重发开始，也不按快照写忙态——忙态由调用方
 * 按请求归属另判。返回快照是否被接纳（调用方可据此拒绝它的 busy）。 */
export function handlePlan(payload, options) {
  const restore = !!(options && options.restore);
  const data = payload || {};
  if (!planEventOwns(data)) return false;      /* 旧计划迟到事件不替换当前计划（P1） */
  const gen = admitPlanEvent(data);
  const id = String(data.plan_id || "");
  const status = String(data.status || (restore ? "running" : "ready"));
  const samePlan = !!S.plan.id && S.plan.id === id;
  /* 同计划已定终态：重复终态与迟到运行快照只补任务详情，不改结论、不复活忙态、不重开结果页（P1）。
   * 只有「恢复快照 + 同一终态」放行调用方按既有请求归属同步全局忙态（后端可另有受管操作在忙）。 */
  if (samePlan && PLAN_TERMINAL.indexOf(S.plan.status) >= 0) {
    mergePlanTasks(data.tasks);
    render();
    return restore && status === String(S.plan.status);
  }
  if (!samePlan) {
    S.plan = { id: id, gen: gen, status: status, tasks: new Map(), armedAt: Date.now() / 1000 };
    S.editing = null;   /* 新计划已接纳：修改流程和上一轮的结果页到此结束 */
    closeResultPage();
    setBusy(["ready", "running"].indexOf(S.plan.status) >= 0);
  } else {
    if (gen > (Number(S.plan.gen) || 0)) S.plan.gen = gen;
    advancePlanStatus(status);
  }
  /* 计划来源（desktop / phone）由后端写进计划事件：从手机开始的计划在计划栏底部注明 */
  if (data.source) S.plan.source = String(data.source);
  /* 晚到 plan 事件与恢复快照经 mergeTask 合并，不抹已收到的提交次数等 telemetry */
  mergePlanTasks(data.tasks);
  /* PB11：从手机开始的计划只记一句「开始了」。startNoted 记在计划对象上：同计划的后续 plan 事件不再写；
   * 恢复快照跳过这一步（重载前早写过了），页面重载后由 bootstrap 快照恢复的计划也不重写。 */
  if (restore) S.plan.startNoted = true;
  if (S.plan.source === "phone" && !S.plan.startNoted) {
    S.plan.startNoted = true;
    noteStartedFromPhone(data.tasks);
  }
  render();
  /* 首次恢复终态走与 plan_done 相同的呈现入口：不置忙、不重发开始、不重复写失败日志 */
  if (restore && PLAN_TERMINAL.indexOf(S.plan.status) >= 0) {
    presentPlanDone({ plan_id: id, status: S.plan.status, summary: data.summary || {} }, false);
  }
  return true;
}

function mergePlanTasks(tasks) {
  (tasks || []).forEach((task) => {
    S.plan.tasks.set(String(task.task_id),
                     mergeTask(S.plan.tasks.get(String(task.task_id)) || null, task));
  });
}

export function handleTask(payload) {
  const data = payload || {};
  if (!planEventOwns(data)) return;           // 旧计划的场次事件：不改当前计划（P1）
  const gen = admitPlanEvent(data);
  if (!S.plan.id || S.plan.id !== String(data.plan_id)) {
    S.plan = { id: String(data.plan_id || ""), gen: gen, status: "running", tasks: new Map(), armedAt: Date.now() / 1000 };
    closeResultPage();
  } else if (gen > (Number(S.plan.gen) || 0)) {
    S.plan.gen = gen;
  }
  const prev = S.plan.tasks.get(String(data.task_id)) || null;
  const task = mergeTask(prev, data);
  S.plan.tasks.set(String(data.task_id), task);
  if (["success", "failed", "already_signed", "canceled"].indexOf(task.status) >= 0) {
    /* 报名成功是已确认事实：任务卡、列表、计数、选择门禁和冲突基线同一时刻更新 */
    if (noteSignedTasks([task])) scheduleSignedRefresh();
    showTaskResult(task);
  }
  render();
}

/* 「刷新核对」：只刷新活动列表（不新增学校接口、不重发报名），结果由列表的 signed 决定 */
export function verifyTask(taskId) {
  if (!S.verifyAsked) S.verifyAsked = new Set();
  S.verifyAsked.add(String(taskId));
  refresh(false);
}
