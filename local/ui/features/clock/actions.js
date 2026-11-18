import { render } from "../shell/actions-render.js";
import { updateControls } from "../plan/view-controls.js";

export function markClockUnavailable(reason) {
  const cur = S.businessClock;
  cur.state = "unavailable";
  cur.reason = String(reason || "暂时无法获取北京时间");
  paintClockStatus();
  if (clockPopOpenNow()) renderClockPop();   /* 浮层与顶栏同源（UI_SPEC §5.16.13） */
  updateControls();
  render();
}

export function ingestBusinessClock(snap, opts) {
  const options = opts || {};
  const cur = S.businessClock;
  const fields = clockSnapshotFields(snap, options.rttMs);
  if (!fields) {
    markClockUnavailable("暂时无法读取时间状态");
    return;
  }
  /* 归属：只接受同一实例；新 owner 只由权威 bootstrap 重建 */
  if (cur.owner && fields.owner && fields.owner !== cur.owner && !options.authoritative) return;
  if (fields.gen < cur.gen) return;                 /* 旧代次不覆盖新结论 */
  const attemptSettled = settleClockAttempt(cur, fields);
  if (fields.gen === cur.gen && cur.anchorEpochMs
      && fields.epochAtSampleMs < cur.epochAtSampleMs) return;   /* 同代旧采样不倒退 */
  if (fields.state === "unavailable") {
    /* 同代「不可用」不得抹掉已建立的可读锚点：真正的过期由年龄/误差门禁判 */
    if (fields.gen === cur.gen && cur.anchorEpochMs
        && (cur.state === "ready" || cur.state === "holdover")) return;
    cur.state = "unavailable";
    cur.reason = fields.reason || "暂时无法获取北京时间";
    cur.gen = fields.gen;
    cur.owner = fields.owner || cur.owner;
    /* 失败也带着退避信息：界面要能说清「什么时候会自动再试」 */
    cur.retryAttempt = fields.retryAttempt;
    cur.retryInS = fields.retryInS;
    cur.lastFailureSource = fields.lastFailureSource;
    cur.lastFailureReason = fields.lastFailureReason;
    cur.syncState = "idle";
    paintClockStatus();
    if (clockPopOpenNow()) renderClockPop();   /* 浮层状态行与顶栏同源（UI_SPEC §5.16.13） */
    updateControls();
    render();
    return;
  }
  applyClockAnchor(cur, fields, attemptSettled);
  paintClockStatus();
  if (clockPopOpenNow()) renderClockPop();   /* 锚点/ready↔holdover 变化同步进已打开的浮层 */
  updateControls();   /* 时钟门禁即时生效：不可用→开始禁用，恢复→解禁 */
  render();
}

function settleClockAttempt(cur, fields) {
  /* 是否完成首轮由后端报告：收到 bootstrap 并不意味着校准已经结束。 */
  const freshAttempt = fields.syncRound === null || cur.syncRound == null
    || fields.syncRound >= cur.syncRound;
  let attemptSettled = false;
  if (freshAttempt) {
    cur.syncStatus = fields.syncStatus;
    if (fields.syncRound !== null) cur.syncRound = fields.syncRound;
    /* 失败不增加授时 generation，必须按尝试编号核对，不能一直等成功代次。 */
    const ownsAttempt = fields.syncRound !== null && cur.syncRequestRound != null
      && (fields.syncRound > cur.syncRequestRound || cur.syncFollowRound === fields.syncRound);
    if (cur.syncState === "syncing" && ownsAttempt
        && (fields.syncStatus === "succeeded" || fields.syncStatus === "failed")) {
      clearTimeout(cur.syncTimer);
      cur.syncState = "idle";
      cur.syncError = fields.syncStatus === "failed" ? CLOCK_SYNC_FAILURE : "";
      attemptSettled = true;
    }
  }
  if (attemptSettled) {
    paintClockStatus();
    if (clockPopOpenNow()) renderClockPop();   /* 收口必须解浮层按钮锁死与「正在校准…」残留 */
    paintClockPopFeedback();
  }
  return attemptSettled;
}

function applyClockAnchor(cur, fields, attemptSettled) {
  const advanced = fields.gen > cur.gen;
  cur.owner = fields.owner || cur.owner;
  cur.gen = fields.gen;
  cur.state = fields.state === "holdover" ? "holdover" : "ready";
  cur.anchorEpochMs = fields.epochAtSampleMs + fields.bridgeMs / 2;
  cur.perfAt = _monoMs();
  cur.sampleAgeMs = fields.sampleAgeMs;
  cur.uncertaintyMs = fields.uncertaintyMs;
  cur.bridgeMs = fields.bridgeMs;
  cur.source = fields.source;
  cur.reason = fields.reason;
  cur.retryAttempt = fields.retryAttempt;
  cur.retryInS = fields.retryInS;
  cur.lastFailureSource = fields.lastFailureSource;
  cur.lastFailureReason = fields.lastFailureReason;
  if (advanced && !attemptSettled) {
    cur.syncState = "idle";
    cur.syncError = "";
  }
}

export function wireClockActions() {
  const pop = $("#clock-pop");
  if (pop) pop.addEventListener("click", (event) => {
    const button = event.target.closest("#clock-pop-sync");
    if (button && !button.disabled && pop.contains(button)) resyncClock();
  });
}

/* 校时用例：重新校时、后台轮询与快照摄入后的呈现刷新。 */
/* 重新校准：只调用本机时钟；反馈留在时间详情，不抢占业务结论。 */
export function resyncClock() {
  const c = S.businessClock;
  if (c.syncState === "syncing") return;
  c.syncState = "syncing";
  c.syncError = "";
  const request = (c.syncRequest || 0) + 1;
  c.syncRequest = request;
  c.syncRequestRound = c.syncRound;
  c.syncFollowRound = c.syncStatus === "syncing" ? c.syncRound : null;
  const startedGen = c.gen;
  paintClockStatus();
  if (clockPopOpenNow()) renderClockPop();
  paintClockPopFeedback();
  api("sync_clock").then(() => {
    if (c.syncRequest !== request || c.syncState !== "syncing") return;
    /* 结果经 business_clock 事件/轮询回收；超时无回执才在详情里报失败 */
    c.syncTimer = setTimeout(() => {
      if (S.businessClock.syncRequest === request && S.businessClock.syncState === "syncing"
          && S.businessClock.gen === startedGen) {
        S.businessClock.syncState = "idle";
        S.businessClock.syncError = "暂时无法确认本次校准结果，请稍后重试。";
        paintClockStatus();
        if (clockPopOpenNow()) renderClockPop();
        paintClockPopFeedback();
      }
    }, 12000);
    pollClockNow();
  }).catch((err) => {
    if (c.syncRequest !== request || c.syncState !== "syncing") return;
    c.syncState = "idle";
    c.syncError = "重新校准没能开始：" + msg(err);
    paintClockStatus();
    if (clockPopOpenNow()) renderClockPop();
    paintClockPopFeedback();
  });
}

/* 本机快照轮询：不访问外部网络；首校时完成、F5/可见性恢复、失效后都能更新。 */
export function pollClockNow() {
  if (!hasBridge() || S.demo) return Promise.resolve(null);
  const started = _monoMs();
  return api("clock_snapshot").then((snap) => {
    ingestBusinessClock(snap, { rttMs: _monoMs() - started });
    S.businessClock.attempted = true;
    return snap;
  }).catch(() => {
    S.businessClock.attempted = true;
    markClockUnavailable("暂时无法读取时间状态");
    return null;
  });
}

export function startClockPolling() {
  if (S.clockTimer) return;
  S.clockTimer = setInterval(pollClockNow, CLOCK_POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) pollClockNow();
  });
}
