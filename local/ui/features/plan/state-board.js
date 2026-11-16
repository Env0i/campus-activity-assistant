/* 计划栏的状态层投影：标题、标签、结论与可重选场次（不碰 DOM）。 */

import { PLAN_TERMINAL, TASK_TERMINAL, resultPageOpen } from "./state.js";
import { effectiveRetryDeadline, executionView, verifiedSigned } from "./state-task.js";

/* 草稿副行（原型 renderVals 的 summary）：「X 场立即报名，Y 场预报名等开放」，为 0 的一半不写 */
export function selectionSummary(items) {
  const instant = items.filter((item) => modeOf(item) === "instant_signup").length;
  const pre = items.length - instant;
  return [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名等开放" : ""]
    .filter(Boolean).join("，");
}

/* 运行中标签（原型 ex 段 head）：离开放 5 秒以内叫「即将开放」 */
export const RUN_SOON_S = 5;

export function runTagText(view) {
  if (view.phase === "submitting") return "正在提交";
  if (view.phase === "arming") return "准备报名";
  const left = view.openAt === null ? null : bnLeftSec(view.openAt);
  return left !== null && left <= RUN_SOON_S ? "即将开放" : "等开放";
}

/* 每秒走字用：阶段或标签一变就重画标题区（tick.js） */
export function runHeadKey() {
  const view = executionView();
  return view.phase + "|" + (["submitting", "arming", "waiting"].indexOf(view.phase) >= 0 ? runTagText(view) : "");
}

/* 运行中标题下面那一行（原型 ex.cap）；「准备报名」是代码独有的阶段，标点照同一口径 */
export function runCaption(view) {
  const count = view.count;
  if (view.phase === "submitting") {
    if (count > 1) return "正在提交 " + count + " 场，每场结果单独显示。";
    const task = view.task || {};
    const tried = Math.max(0, Math.floor(Number(task.attempts) || 0));
    const last = String(task.last_reason || "").trim();
    return "已提交 " + tried + " 次" + (last ? "，最近：" + last : "");
  }
  if (view.phase === "arming") {
    return count > 1 ? "已开放，正在准备 " + count + " 场，每场结果单独显示。" : "已开放，正在准备提交。";
  }
  return count > 1 ? "这一批 " + count + " 场同时提交，到点自动开始。" : "这一场等开放，到点自动开始。";
}

/* 整屏外框（原型 .board.st-ok / st-warn / st-bad）：只在结果页按结论上色，运行中保持运行色。
 * 含「待核对」的计划不画成确定失败的红框，展示语义不能替用户宣布失败（FR06）。 */
export function boardPlanState() {
  if (S.busy) return "running";
  if (!resultMode()) return "idle";
  const frame = resultView().frame;
  if (frame === "ok") return "completed";
  if (frame === "bad") return "failed";
  if (frame === "warn") return String(S.plan.status) === "partial" ? "partial" : "attention";
  return "stopped";
}

/* 修改中的说明（原型 editNote）：三句拼成，离最近一场开放不到 300 秒时报剩余时间 */
export function editNoteText() {
  let text = "计划已暂停，重新开始前不会自动报名。";
  const done = Math.max(0, Math.floor(Number(S.editing && S.editing.doneN) || 0));
  if (done > 0) text += "已结束的 " + done + " 场不受影响。";
  const now = bnowS();
  let first = null;
  ((S.editing && S.editing.ids) || []).forEach((id) => {
    const item = findItem(id);
    const ts = item ? toTs(item.sign_start) : null;
    if (ts !== null && (first === null || ts < first)) first = ts;
  });
  if (now !== null && first !== null) {
    const gap = first - now;
    if (gap > 0 && gap <= 300) text += "离最近一场开放只剩 " + durText(gap) + "。";
  }
  return text;
}

/* 结果页（原型 phase === 'result'）：计划已结束，且结果页标记还开着（state/plan.js）。
 * 不再靠选择签名相等来判断：成功场次被自动移出选择集合不会让结果页退回草稿。 */
export function resultMode() {
  return !S.busy && !S.editing && S.plan.tasks.size > 0
    && PLAN_TERMINAL.indexOf(String(S.plan.status || "")) >= 0 && resultPageOpen();
}

/* 空选状态优先展示当前开放场次；没有开放场次时再展示最近的未来场次。 */
export function boardTargetItem() {
  const next = nextOpen();
  if (next.bestId) return findItem(next.bestId);
  if (next.openNow) return S.items.find((item) => !item.signed && stateOf(item) === "open") || null;
  return null;
}

/* 运行中「来不及」的判断（架构方案 4.3）：有场次在提交，或还没提交的场次离开放不到 100 秒。
 * 与后端 local/domain/login_rules.py 的 LATE_WINDOW_S 同一个数；修改计划的禁用条件也用它。 */
export const LATE_WINDOW_S = 100;

export function planLate() {
  const now = bnowS();
  if (now === null) return true;
  let late = false;
  S.plan.tasks.forEach((task) => {
    const st = String(task.status || "");
    if (st === "submitting") late = true;
    else if (st === "queued" || st === "waiting") {
      const open = toTs(task.sign_start);
      if (open !== null && open - now <= LATE_WINDOW_S) late = true;
    }
  });
  return late;
}

/* 最早一场还没提交的开放时刻：运行中登录失效时，「HH:MM:SS 前重新登录」按它减 100 秒算 */
export function earliestWaitingOpen() {
  let best = null;
  S.plan.tasks.forEach((task) => {
    if (["queued", "waiting"].indexOf(String(task.status || "")) < 0) return;
    const open = toTs(task.sign_start);
    if (open !== null && (best === null || open < best)) best = open;
  });
  return best;
}

/* 结果页大数字（原型 res.counts）：六类，名额已满单列、中性色。
 * 「报名未成功」含 failed 里除名额已满、待核对、错过了以外的，以及 auth_unavailable（没提交）；
 * 刷新核对确认过的算「已报名」。pending 即「待核对」。
 * 「错过了」（LS22 / PB15）由睡眠窗口推导（taskMissedBySleep，与时刻表行级同一判据），
 * 在 failed 之前拦下：一场任务只落进一类，不会既算错过了又算报名未成功。 */
export function resultCounts() {
  const counts = { ok: 0, full: 0, bad: 0, missed: 0, pending: 0, canceled: 0 };
  S.plan.tasks.forEach((task) => {
    const st = String(task.status || "");
    const stop = String(task.stop_reason || "");
    if (st === "success" || st === "already_signed" || verifiedSigned(task)) counts.ok += 1;
    else if (st === "canceled") counts.canceled += 1;
    else if (stop === "full") counts.full += 1;
    else if (stop === "unconfirmed") counts.pending += 1;
    else if (taskMissedBySleep(task)) counts.missed += 1;
    else if (st === "failed") counts.bad += 1;
  });
  return counts;
}

/* 结果页结论（原型渲染函数 res 段，按顺序判断）：标签、标题、副行、外框，以及只在全成功 / 全失败时的小 LED */
export function resultView() {
  const c = resultCounts();
  if (String(S.plan.status) === "stopped") {
    return { tag: c.pending ? "已停止，需确认" : "已停止", tone: c.pending ? "amber" : "off",
             title: "报名计划已停止", text: "已提交的场次保留原状态，还没提交的场次已取消。",
             frame: c.pending ? "warn" : "", led: null };
  }
  /* 计划结束时仍有没出结论的场次（排队 / 等待 / 提交中）不算全部报上 */
  const allSettled = Array.from(S.plan.tasks.values()).every((task) => TASK_TERMINAL.indexOf(String(task.status || "")) >= 0);
  if (c.ok && !c.bad && !c.missed && !c.pending && !c.canceled && !c.full && allSettled) {
    return { tag: "报名成功", tone: "green", title: "报名计划完成", text: "每场结束时都向学校核对过。",
             frame: "ok", led: ["✓", "green"] };
  }
  if (c.ok) {
    return { tag: "部分完成", tone: "amber", title: "报名计划部分完成",
             text: c.pending ? "有 " + c.pending + " 场需要到活动页核对，结果以学校为准。"
               : (c.full ? "有 " + c.full + " 场名额已满，不是工具出错。" : "结果以学校活动页为准。"),
             frame: "warn", led: null };
  }
  if (c.pending) {
    return { tag: "需确认", tone: "amber", title: "计划已结束，有 " + c.pending + " 场需确认",
             text: "工具不会自动重发，到学校活动页核对。", frame: "warn", led: null };
  }
  if (c.missed && !c.bad) {
    /* 原型 res 段：错过了排在待核对之后、名额已满之前；红框，不画 LED（hasLed 为假） */
    return { tag: "错过了", tone: "red", title: "电脑睡眠，错过了开放",
             text: "运行计划时别让电脑睡眠：在 Windows 电源设置里把睡眠改成“从不”，并保持插电。",
             frame: "bad", led: null };
  }
  if (c.full && !c.bad && !c.missed) {
    return { tag: "名额已满", tone: "amber", title: "这次没报上：名额满了",
             text: "学校的名额在开放后被报满了，不是工具出错。", frame: "warn", led: null };
  }
  return { tag: "未成功", tone: "red", title: "报名计划没有成功", text: "每场的原因都列在下面。",
           frame: "bad", led: ["✕", "red"] };
}

/* 可以重新选的场次（原型 res.canRetry）：报名未成功和已取消的；不含名额已满、待核对（工具不自动重发），
 * 还要能加入计划（没截止、没报上、不和已报名冲突） */
export function reselectableIds() {
  const ids = [];
  S.plan.tasks.forEach((task) => {
    const st = String(task.status || "");
    const stop = String(task.stop_reason || "");
    if (["failed", "canceled"].indexOf(st) < 0 || stop === "full" || stop === "unconfirmed") return;
    const item = findItem(task.activity_id);
    if (item && isEligibleForPlan(item) && !signedClash(item)) ids.push(String(item.id));
  });
  return ids;
}

export function earliestSelectedOpen() {
  let best = null;
  selectedItems().forEach((item) => {
    const ts = toTs(item.sign_start);
    if (ts !== null && (best === null || ts < best)) best = ts;
  });
  return best;
}

/* 终态的停止条件人话：让用户知道是「到点/到次数/到截止」里的哪一个。
 * unconfirmed/auth_unavailable 不是「失败原因」，是「结果没确认」：
 * 用词必须留出核对空间，不能写成没抢到。 */
export function stopReasonText(reason) {
  return {
    success: "报名成功",
    already_signed: "已经报过",
    login_invalid: "登录失效，先重新登录",
    auth_unavailable: "登录状态暂时无法确认",
    max_attempts: "达到最大提交次数",
    retry_duration: "重试时长到了",
    sign_end: "报名已截止",
    unconfirmed: "报名结果待核对",
    user_stopped: "已停止",
    process_error: "程序流程异常结束",
    /* 回包分类后的结束结论（架构方案 3.3）：后端另给 outcome_label，这里是兜底同义词 */
    full: "名额已满",
    closed: "报名已截止",
    conflict: "时间冲突",
    no_activity: "活动不存在",
    clock_skew: "本机时钟不准",
    unknown_reply: "学校回了无法识别的结果",
    page_unavailable: "学校页面打不开",
  }[reason] || "";
}

/* 提交中的重试截止（任务卡与 LED 的旧入口）：已并入统一推导 */
export function retryDeadline(task) {
  return effectiveRetryDeadline(task);
}
