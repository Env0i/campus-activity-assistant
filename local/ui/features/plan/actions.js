import { setBusy } from "../shell/actions-render.js";
import { render } from "../shell/actions-render.js";
/* 计划栏的编排层：写完状态统一重画、发起刷新。 */

import { PLAN_TERMINAL, TASK_TERMINAL, admitPlanEvent, closeResultPage, mergeTask, planEventOwns } from "./state.js";
import { noteStartedFromPhone } from "./actions-run.js";
import { showTaskResult } from "./actions-events.js";

/* 同计划状态推进：已定终态不回退，运行态照常更新（P1） */
export function advancePlanStatus(incoming) {
  if (PLAN_TERMINAL.indexOf(S.plan.status) >= 0) return;
  S.plan.status = String(incoming || "ready");
  setBusy(["ready", "running"].indexOf(S.plan.status) >= 0);
}

export function handlePlan(payload) {
  const data = payload || {};
  if (!planEventOwns(data)) return;      /* 旧计划迟到事件不替换当前计划（P1） */
  const gen = admitPlanEvent(data);
  if (!S.plan.id || S.plan.id !== String(data.plan_id)) {
    S.plan = { id: String(data.plan_id || ""), gen: gen, status: String(data.status || "ready"), tasks: new Map(), armedAt: Date.now() / 1000 };
    S.editing = null;   /* 新计划已接纳：修改流程和上一轮的结果页到此结束 */
    closeResultPage();
    setBusy(["ready", "running"].indexOf(S.plan.status) >= 0);
  } else {
    if (gen > (Number(S.plan.gen) || 0)) S.plan.gen = gen;
    advancePlanStatus(data.status);
  }
  /* 计划来源（desktop / phone）由后端写进计划事件：从手机开始的计划在计划栏底部注明 */
  if (data.source) S.plan.source = String(data.source);
  /* 晚到 plan 事件经 mergeTask 合并，不抹已收到的提交次数等 telemetry */
  (data.tasks || []).forEach((task) => {
    S.plan.tasks.set(String(task.task_id),
                     mergeTask(S.plan.tasks.get(String(task.task_id)) || null, task));
  });
  /* PB11：从手机开始的计划只记一句「开始了」。startNoted 记在计划对象上：同计划的后续 plan 事件不再写；
   * 页面重载后由 bootstrap 快照恢复的计划（ingestBootstrapPlan 预先置 true）也不重写。 */
  if (S.plan.source === "phone" && !S.plan.startNoted) {
    S.plan.startNoted = true;
    noteStartedFromPhone(data.tasks);
  }
  render();
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
  /* 已结束的场次不得被旧进度拖回运行态：状态保持先到的事实（P1） */
  if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0
      && TASK_TERMINAL.indexOf(String(task.status)) < 0) {
    task.status = prev.status;
  }
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
