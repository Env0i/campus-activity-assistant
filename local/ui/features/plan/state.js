/* 计划栏的状态层：事件归属、代次合并与计划结论统计（不碰 DOM、不发请求）。 */

export function mergeTask(prev, incoming) {
  const merged = Object.assign({}, prev || {}, incoming || {});
  TASK_RUNTIME_FIELDS.forEach((key) => {
    const value = incoming ? incoming[key] : undefined;
    if ((value === undefined || value === null || value === "") && prev && prev[key] != null) {
      merged[key] = prev[key];
    }
  });
  /* 同一计划与任务的终态先到先得：迟到的旧载荷不得把已结束的场次拖回运行态（P1） */
  if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0
      && TASK_TERMINAL.indexOf(String(merged.status)) < 0) {
    merged.status = prev.status;
  }
  /* 提交次数只增不减：后到的旧快照/旧事件不得抹掉已收到的次数（P1） */
  const prevTries = Math.max(0, Math.floor(Number((prev || {}).attempts) || 0));
  const snapTries = Math.max(0, Math.floor(Number(merged.attempts) || 0));
  if (prevTries > snapTries) merged.attempts = prevTries;
  if (String(merged.status) === "submitting" && !merged.submitSeen) merged.submitSeen = Date.now();
  return merged;
}

/* 计划级终态与单场终态集合：终态之后的同计划旧事件只补详情，不回退结论（P1） */
export const PLAN_TERMINAL = ["completed", "partial", "failed", "stopped"];

export const TASK_TERMINAL = ["success", "failed", "already_signed", "canceled"];

/* 已见过的最大计划接纳代次：屏上计划的代次与会话记录取大（P1） */
export function maxPlanGen() {
  const a = Number(S.maxPlanGen);
  const b = Number(S.plan && S.plan.gen);
  return Math.max(Number.isFinite(a) && a > 0 ? a : 0,
                  Number.isFinite(b) && b > 0 ? b : 0);
}

/* 计划事件归属路由（P1）：事件只有属于当前屏上计划，或携带比已见过的更大的
 * plan_generation（后端最终接纳时赋值，新计划的事件可能早于 start_plan 的
 * ack），才允许改当前状态。旧计划迟到的 plan/task/plan_done 只能进历史
 * 对账，不得清运行中计划的忙态、任务、停止入口，也不得改写已完成结论。 */
export function planEventOwns(data) {
  const id = String((data && data.plan_id) || "");
  if (!id) return false;
  if (S.plan.id === id) return true;          // 当前屏上计划：同计划按幂等合并
  const gen = Number(data.plan_generation);
  if (!Number.isFinite(gen)) return !S.plan.id;   // 旧格式载荷：只在空屏时接纳
  return gen > maxPlanGen();                  // 更新的接纳（含早于 ack 的新计划）
}

/* 接纳事件时更新会话代次记录，返回事件的代次（无代次返回 0） */
export function admitPlanEvent(data) {
  const gen = Number(data && data.plan_generation);
  if (!Number.isFinite(gen)) return 0;
  S.maxPlanGen = Math.max(S.maxPlanGen || 0, gen);
  return gen;
}

/* 结果页标记（原型 phase === 'result'，P1）：plan_done 时打开；开始新计划、点「完成」、
 * 点「重新选择未成功的场次」、用户自己在时刻表改了勾选时关闭。
 * 成功场次会被自动移出选择集合（controllers/refresh.js），那一步只同步记下的选择，不关结果页。 */
export function openResultPage() {
  S.resultOpen = true;
  S.resultSel = selectionSignature();
}

export function closeResultPage() {
  S.resultOpen = false;
  S.resultSel = null;
}

export function syncResultSelection() {
  if (S.resultOpen) S.resultSel = selectionSignature();
}

export function resultPageOpen() {
  if (!S.resultOpen) return false;
  if (S.resultSel !== selectionSignature()) {
    /* 选择变了又不是自动移出：只能是用户自己改了勾选，结果页到此关闭 */
    closeResultPage();
    return false;
  }
  return true;
}

/* 计划级结论分类：协调器的 counts.failed 把「结果未确认」也算进失败，
 * 但对用户这是两种不同的事实——这里按逐任务 stop_reason 单列，
 * 任务卡、总结、大屏和 LED 共用这一份口径。 */
export function planOutcome() {
  const counts = { success: 0, already_signed: 0, failed: 0, canceled: 0,
                   unconfirmed: 0, auth_unavailable: 0, unknown: 0 };
  S.plan.tasks.forEach((task) => {
    const state = String(task.status || "");
    if (state === "success") counts.success += 1;
    else if (state === "already_signed") counts.already_signed += 1;
    else if (state === "canceled") counts.canceled += 1;
    else if (state === "failed") {
      if (task.stop_reason === "unconfirmed") counts.unconfirmed += 1;
      else if (task.stop_reason === "auth_unavailable") counts.auth_unavailable += 1;
      else counts.failed += 1;
    }
  });
  counts.unknown = counts.unconfirmed + counts.auth_unavailable;
  return counts;
}

/* 未确认类别的统一标签：任务数、总结标题、大屏与 LED 必须同一个数字口径。
 * 两种未知同时存在时说「需确认」，不把没提交的场次混进「待核对」。 */
export function unknownLabel(outcome) {
  if (!outcome || !outcome.unknown) return "";
  if (outcome.unconfirmed && outcome.auth_unavailable) {
    return "有 " + outcome.unknown + " 场需确认";
  }
  if (outcome.unconfirmed) return "有 " + outcome.unconfirmed + " 场待核对";
  return "有 " + outcome.auth_unavailable + " 场未提交";
}

export function selectionSignature() {
  return Array.from(S.selected).slice().sort().join(",");
}
