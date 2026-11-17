/* 计划栏标题区的状态机：只看调用方抄好的事实，按原分支的先后给出一个阶段。
 * 状态层不碰 DOM、不读 window、不读时钟，也不调别的函数——事实都由调用方算好传进来。 */

/* 十九个阶段，顺序即判断先后；视图层按这张表取样子。 */
export const BOARD_PHASES = Object.freeze([
  "first_use", "logging_in", "result", "terms_hold", "broken", "list_error",
  "list_loading", "run_target", "run_settling", "run_preparing", "next_open",
  "next_upcoming", "school_empty", "clock_pending", "none_eligible",
  "none_upcoming", "selected_paused", "editing", "selected",
]);

/* facts 的字段：busy、present（从没登录过是 false）、runtimeError、loginPending、
 * resultMode（调用方调 resultMode() 算好）、termsLocked、listState、itemsCount（列表场数）、
 * selectedCount（已选场数）、hasNext、nextOpenNow（下一个目标此刻是否开放）、
 * clockKnown（可信现在有没有）、demo、editing、runPhase（executionView().phase）。 */
export function boardPhase(f) {
  /* 条款没同意（且登录过）：没选活动与选了活动两处都要用，先算一次 */
  const termsHold = !f.busy && f.termsLocked && f.present !== false;
  if (!f.busy && f.present === false && !f.runtimeError) return "first_use";
  if (f.loginPending) return "logging_in";
  if (f.resultMode) return "result";
  if (termsHold && !f.selectedCount) return "terms_hold";
  if (!f.busy && f.runtimeError && f.listState !== "ready") return "broken";
  if (!f.busy && f.listState === "error" && !f.itemsCount) return "list_error";
  if (!f.busy && f.listState === "loading" && !f.selectedCount) return "list_loading";
  if (f.busy) return runPhaseOf(f.runPhase);
  if (!f.selectedCount) return emptyPhase(f);
  if (termsHold) return "selected_paused";
  return f.editing ? "editing" : "selected";
}

/* 在跑的三支：真正在提交 / 正在汇总 / 其余都算准备中（没有任务时也是） */
function runPhaseOf(phase) {
  if (phase === "submitting" || phase === "arming" || phase === "waiting") return "run_target";
  return phase === "settling" ? "run_settling" : "run_preparing";
}

/* 没选活动的六支：「有下一个目标」压过四种「暂时没有」；
 * 四种里先按列表就绪与否分成两半，再看学校是否返回 0 场、有没有可信现在。 */
function emptyPhase(f) {
  if (f.hasNext) return f.nextOpenNow ? "next_open" : "next_upcoming";
  if (f.listState !== "ready") return "none_upcoming";
  if (!f.itemsCount) return "school_empty";
  if (!f.clockKnown && !f.demo) return "clock_pending";
  return "none_eligible";
}
