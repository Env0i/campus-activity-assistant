import { render } from "../shell/actions-render.js";
/* 计划栏的编排层（开始这一段）：发 start_plan、只查不重发地对账、按快照恢复。 */

import { PLAN_TERMINAL, TASK_TERMINAL, mergeTask, selectionSignature } from "./state.js";
import { paintPlan } from "./view.js";
import { presentPlanDone } from "./actions-events.js";
import { termsLocked } from "../terms/state.js";
import { paintBanners } from "../shell/view-banners.js";
import { updateControls } from "./view-controls.js";
import { RUNTIME_ERRORS } from "../shell/state-runtime.js";

export function startPlan() {
  if (S.busy || S.starting || S.cancel.busyId) return;
  /* 条款未同意：报名计划是学校网络动作，拒绝后按钮已禁用，这里只兜底不强弹 */
  if (termsLocked()) {
    if (!S.terms.declined && !S.terms.unknown) openTerms();
    return;
  }
  const validation = validateSelection();
  if (!S.selected.size) {
    setResult({ ok: false, title: "还没选活动", text: "在时刻表勾选至少一场未报名活动。" });
    return;
  }
  if (validation.errors.length || validation.conflicts.length) {
    paintPlan();
    setResult({ ok: false, title: "计划还不能开始", text: "先处理上面的检查项，再开始报名计划。" });
    return;
  }
  /* 显式传 sign_end 与 signup_mode：重载/刷新时序下后端虽以自己快照为权威，
   * 前端把当前判定一起交上去，缺口数据时后端也能按报名截止拦截 */
  const items = selectedItems().map((item) => ({
    id: item.id,
    name: item.name,
    sign_start: item.sign_start || "",
    sign_end: item.sign_end || "",
    act_start: item.act_start || "",
    act_end: item.act_end || "",
    signed: !!item.signed,
    signup_mode: modeOf(item),
  }));
  setResult(null);
  /* FB1 轻量提交中标志：只做即时按钮反馈（连点不会创建第二套提交——后端
   * 最终接纳点的原子重检是最终权威），成功/拒绝/reject 均释放。
   * 本轮再加 request_id：15 秒无响应时按 ID 对账，绝不清标志放行第二次开始。 */
  const requestId = newRoundId("start");
  if (S.startRequest) {
    /* 替换请求必须撤销旧计时器：旧 15 秒/5 秒回调不得落到这次新开始上 */
    clearTimeout(S.startRequest.timer);
    clearTimeout(S.startRequest.queryTimer);
  }
  S.startRequest = { id: requestId, state: "submitting", timer: null,
                     queryTimer: null, reconcile: 0, gen: 0 };
  S.starting = true;
  updateControls();
  S.startRequest.timer = setTimeout(() => reconcileStart(requestId), 15000);
  api("start_plan", items, $("#headed").checked,
      { retry_for_s: S.retryPolicy.retry_for_s, max_attempts: S.retryPolicy.max_attempts },
      requestId).then((res) => {
    if (!S.startRequest || S.startRequest.id !== requestId) return;
    clearTimeout(S.startRequest.timer);
    clearTimeout(S.startRequest.queryTimer);
    if (res && res.pending) {
      /* 去重命中了仍在进行的那次开始：继续对账，不能当成失败也不能再发一次 */
      S.starting = true;
      reconcileStart(requestId);
      return;
    }
    S.starting = false;
    S.startRequest.state = "settled";
    if (!res || res.ok === false) {
      setBusy(false);
      /* 后端条款回绝：不按普通业务失败弹结果框，回到条款门禁 */
      if (res && res.error === "terms_required") {
        noteTermsRequired(res);
        return;
      }
      if (res && res.error && RUNTIME_ERRORS[res.error]) {
        /* FB4：开始计划的组件失败同样只挂横幅与唯一恢复入口，
         * 不生成同义失败结果框；并计入本轮刷新故障累计（迟到成功不得撤） */
        noteRoundError(res.error);
        paintBanners();
        updateControls();
        return;
      }
      showPlanError(res && res.text, res && res.conflicts, res && res.errors);
      return;
    }
    /* 后端可能在 Promise 回调之前就推来 plan/task 事件（协调器另一线程emit），
     * 这里只在计划 id 变了时才重置，避免把已收到的任务表清空。
     * ack 的接纳代次并入会话记录：归属判定与事件路由同一基准（P1）。 */
    const ackGen = notePlanGeneration(res.plan_generation);
    if (!S.plan.id || S.plan.id !== String(res.plan_id || "")) {
      S.plan = { id: String(res.plan_id || ""), gen: ackGen,
                 status: "ready", tasks: new Map(), armedAt: Date.now() / 1000 };
    } else if (ackGen > (Number(S.plan.gen) || 0)) {
      S.plan.gen = ackGen;
    }
    /* 修改后的「重新开始」不能等 plan 事件再清 editing：plan_id 没变时
       state/plan.js 的 handlePlan 会跳过 editing 清理，修改中的说明会一直留在屏上 */
    S.editing = null;
    S.stopping = false;
    /* ack 只证明「已接纳」，不证明「此刻仍在运行」：该计划已经通过 plan_done
     * 到达终态时（终态早于 ack），保持终态呈现与 busy=false——没有第二个
     * plan_done 会再来解锁，置忙会让停止入口悬在一个永远不结束的计划上（P1） */
    if (S.plan.id === String(res.plan_id || "")
        && PLAN_TERMINAL.indexOf(S.plan.status) >= 0) {
      updateControls();
      render();
      return;
    }
    setBusy(true);
    /* 已开放场次会立即执行，不能写成「等待各自开放时间」：
     * 按两种正式模式分别说明（预报名等开放 / 立即报名抢名额）。 */
    const futureCount = items.filter((item) => item.signup_mode === "pre_register").length;
    const instantCount = items.filter((item) => item.signup_mode === "instant_signup").length;
    const parts = [];
    if (futureCount) parts.push(futureCount + " 场预报名等开放");
    if (instantCount) parts.push(instantCount + " 场立即报名马上执行");
    addLog("已安排 " + items.length + " 场活动：" + (parts.join("，") || "按各场状态执行") + "。");
    render();
  }).catch((err) => {
    if (!S.startRequest || S.startRequest.id !== requestId) return;
    clearTimeout(S.startRequest.timer);
    /* 桥接异常不等于没启动：先对账再说话，不能直接放开第二次开始 */
    S.startRequest.state = "reconciling";
    reconcileStart(requestId, msg(err));
  });
}

/* 开始请求的对账：只问后端「这次到底启没启」，绝不重发 start_plan（R11）。
 * accepted → 恢复任务与停止按钮；rejected → 如实报错；pending → 继续等；
 * unknown/超时 → 明说「结果未确认，请勿重复启动」，保留重新确认入口。 */
export const START_QUERY_TIMEOUT_MS = 5000;

/* 开始请求的对账：只问后端「这次到底启没启」，绝不重发 start_plan（R11）。
 * accepted → 恢复任务与停止按钮；rejected → 如实报错；pending → 继续等；
 * unknown/超时 → 明说「结果未确认，请勿重复启动」，保留重新确认入口。
 * 每次查询有 5 秒本机响应期限与独立代次：Promise 永不 settle 也会退出查询态，
 * 迟到的旧回复不能落到后来的计划上。 */
export function reconcileStart(requestId, hint) {
  if (!S.startRequest || S.startRequest.id !== requestId) return;
  S.starting = true;
  S.startRequest.state = "reconciling";
  const gen = (S.startRequest.gen || 0) + 1;
  S.startRequest.gen = gen;
  clearTimeout(S.startRequest.queryTimer);
  updateControls();
  setResult({
    ok: "partial",
    title: "正在确认是否启动",
    text: hint ? "开始请求没有正常返回（" + hint + "），正在向本机确认；请勿重复启动。"
      : "开始请求没有立刻返回，正在向本机确认；请勿重复启动。",
  });

  const settled = () => {
    clearTimeout(S.startRequest.queryTimer);
    S.startRequest.queryTimer = null;
  };
  const unknown = (prefix) => {
    if (!S.startRequest || S.startRequest.id !== requestId || S.startRequest.gen !== gen) return;
    settled();
    /* 没有确定结论：保持开始按钮禁用，避免用户重复报名；只留只读确认入口 */
    S.starting = true;
    S.startRequest.state = "unknown";
    updateControls();
    setResult({
      ok: false,
      title: "结果未确认，请勿重复启动",
      text: prefix + "先看下面的任务区或点「刷新」确认当前计划，确认没有在跑再重新开始。",
      action: { label: "重新确认", run: () => reconcileStart(requestId) },
    });
  };

  S.startRequest.queryTimer = setTimeout(() => {
    if (!S.startRequest || S.startRequest.id !== requestId || S.startRequest.gen !== gen) return;
    unknown("本机 5 秒内没有回应这次对账。");
  }, START_QUERY_TIMEOUT_MS);

  api("start_request_state", requestId).then((res) => {
    if (!S.startRequest || S.startRequest.id !== requestId) return;
    if (S.startRequest.gen !== gen) return;      /* 旧代次迟到：不得替换后来的计划 */
    settled();
    const state = res && res.state;
    if (state === "accepted") {
      adoptPlan(S.startRequest.id, res && res.plan_id, res && res.snapshot,
                !!(res && (res.finished || !res.running)), res && res.plan_generation);
      return;
    }
    if (state === "rejected") {
      S.starting = false;
      S.startRequest.state = "rejected";
      updateControls();
      showPlanError((res && res.text) || "计划没能开始", [], []);
      return;
    }
    if (state === "canceled") {
      S.starting = false;
      S.startRequest.state = "canceled";
      updateControls();
      setResult({ ok: "partial", title: "这次开始已取消", text: "可以重新选择后再开始。" });
      return;
    }
    if (state === "pending" && S.startRequest.reconcile < 8) {
      S.startRequest.reconcile += 1;
      S.startRequest.timer = setTimeout(() => reconcileStart(requestId), 2000);
      return;
    }
    unknown("没有拿到确定的启动结论。");
  }).catch(() => {
    if (!S.startRequest || S.startRequest.id !== requestId) return;
    if (S.startRequest.gen !== gen) return;
    unknown("本机没有回应这次对账。");
  });
}

/* 已确认接纳：按快照真实状态恢复。
 * 15 秒内就结束的计划不能复活成「空任务运行中」——那会给出一个永远不结束的
 * 运行态和一个点不动的停止按钮（C05）。
 * generation 是后端接纳代次：ack 承认的归属与事件路由同一基准（P1）。 */
export function adoptPlan(requestId, planId, snapshot, finished, generation) {
  S.starting = false;
  if (S.startRequest && S.startRequest.id === requestId) {
    S.startRequest.state = "accepted";
    clearTimeout(S.startRequest.queryTimer);
    S.startRequest.queryTimer = null;
  }
  const id = String(planId || "");
  const status = String((snapshot && snapshot.status) || (finished ? "unknown" : "running"));
  const terminal = ["completed", "partial", "failed", "stopped"].indexOf(status) >= 0;
  const gen = notePlanGeneration(generation);
  if (id && (!S.plan.id || S.plan.id !== id)) {
    S.plan = { id: id, gen: gen, status: terminal ? status : "running", tasks: new Map(),
               armedAt: Date.now() / 1000 };
  } else if (gen > (Number(S.plan.gen) || 0)) {
    S.plan.gen = gen;
  }
  if ((snapshot && snapshot.tasks || []).length) {
    (snapshot.tasks || []).forEach((task) => {
      const key = String(task.task_id);
      const prev = S.plan.tasks.get(key) || null;
      const merged = mergeTask(prev, task);
      /* 旧进度不得把已终态场次拖回运行态（终态早于 ack，P1） */
      if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0
          && TASK_TERMINAL.indexOf(String(merged.status)) < 0) {
        merged.status = prev.status;
      }
      /* 后到 ack 不得清掉事件已收到的任务与 checkpoint：提交次数只增不减（P1） */
      const prevTries = Math.max(0, Math.floor(Number((prev || {}).attempts) || 0));
      const snapTries = Math.max(0, Math.floor(Number(merged.attempts) || 0));
      if (prevTries > snapTries) merged.attempts = prevTries;
      S.plan.tasks.set(key, merged);
    });
  }
  S.stopping = false;
  if (terminal) {
    S.plan.status = status;
    S.plan.doneSelection = selectionSignature();
    setBusy(false);
    /* ack 的权威终态直接走呈现入口：不过事件路由，避免被同计划
     * 重复终态分支拦截而不呈现（P1） */
    presentPlanDone({ plan_id: id, status: status,
                      summary: (snapshot && snapshot.summary) || {},
                      plan_generation: gen > 0 ? gen : undefined });
    return;
  }
  /* 同计划已可信终态：ack/对账带来的旧 running 快照不得复活忙态——
   * ack 只证明「已接纳」，不证明「此刻仍在运行」（终态早于 ack，P1） */
  if (S.plan.id === id && PLAN_TERMINAL.indexOf(S.plan.status) >= 0) {
    updateControls();
    render();
    return;
  }
  setBusy(true);
  addLog("[i] 已确认计划启动，继续显示进度。");
  render();
  api("bootstrap").then((info) => {
    if (info && info.plan) ingestBootstrapPlan({ plan: info.plan });
  }).catch(() => {});
}

/* 「放弃修改，按原计划继续」（U1）：原来直接绑 startPlan，用的是当前勾选，
 * 用户改过勾选再放弃，开始的就不是原计划。这里先把勾选恢复成修改前的场次
 * （只放回现在仍能报的），再走和「重新开始」同一条开始流程。 */
export function restoreEditedPlan() {
  if (S.editing && Array.isArray(S.editing.ids)) {
    S.selected.clear();
    S.editing.ids.forEach((id) => {
      const item = findItem(id);
      if (item && isEligibleForPlan(item)) S.selected.add(String(id));
    });
    render();
  }
  startPlan();
}

/* 后端验证失败：errors/conflicts 逐条翻译成「哪一场、什么问题」，
 * 不折成一句泛化文案；同 sign_start 不是冲突依据，只报举办时段。 */
const PLAN_ERROR_TEXT = {
  missing_id: "有活动缺少 id，刷新列表后再选。",
  duplicate_id: "同一活动被选了两遍，去掉重复的那一条。",
  already_signed: "此活动已报名，请从本次计划中移除。",
  invalid_sign_start: "报名开放时间缺失或格式不对。",
  activity_time_unknown: "缺少完整的活动举办起止时间。",
  activity_time_invalid: "活动结束时间不晚于开始时间。",
  activity_overlap: "活动举办时段重叠。",
  sign_end_passed: "报名已截止，不能加入计划。",
};

function showPlanError(text, conflicts, errors) {
  const messages = [];
  (errors || []).forEach((error) => {
    const kind = error && error.kind;
    if (kind === "activity_overlap") return; /* 冲突单列，避免重复 */
    const label = PLAN_ERROR_TEXT[kind] || "这一项不能加入计划。";
    const name = error && (error.name || error.activity_id);
    messages.push("<div class=\"conflict-item\"><strong>" + esc(label) + "</strong><br>" + (name ? "「" + esc(name) + "」" : "") + "</div>");
  });
  (conflicts || []).forEach((conflict) => {
    const left = conflict.left || {};
    const right = conflict.right || {};
    messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong><br>「" + esc(left.name) + "」与「" + esc(right.name) +
      "」举办时段重叠（" + esc(shortTime(left.act_start)) + " – " + esc(shortTime(left.act_end)) + "），只能选其中一场。</div>");
  });
  if (messages.length) {
    S.selectionNotice = "计划未能开始，先处理上面的提示再试。";
    const box = $("#plan-conflicts");
    box.innerHTML = messages.join("");
    box.hidden = false;
    render();
  }
  setResult({ ok: false, title: "计划没能开始", text: (messages.length ? "上面列出了每一场的问题。" : "") + (text || "先处理提示，再试一次。") });
}
