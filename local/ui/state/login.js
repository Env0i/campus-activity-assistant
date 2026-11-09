/* 登录三态还原与剩余估算（只展示，不参与放行）。 */
function loginSnapshotState() {
  return {
    hours: S.login.hours, ok: S.login.ok, present: S.login.present,
    expireAt: S.login.expireAt, savedAt: S.login.savedAt, result: S.login.result,
    estimateReason: S.login.estimateReason,
  };
}

function restoreLoginSnapshotState(snap) {
  if (!snap) return;
  S.login.hours = snap.hours;
  S.login.ok = snap.ok;
  S.login.present = snap.present;
  S.login.expireAt = snap.expireAt;
  S.login.savedAt = snap.savedAt;
  S.login.result = snap.result;
  S.login.estimateReason = snap.estimateReason === undefined ? null : snap.estimateReason;
}

function setLogin(hours, ok, present, anchor) {
  S.login.hours = numOrNull(hours);
  S.login.ok = ok;
  /* present 是后端 session_present 的回声：false=从没登录过，true=登录过。
   * 不传（undefined）表示这次事件没说，保留上一次的判断。 */
  if (present !== undefined) S.login.present = !!present;
  /* 估算锚点（绝对时刻）：bootstrap.login / check 事件 / 登录完成后都带同一来源的
   * estimated_expires_at（epoch 秒）。收到就整份替换（重新登录=新锚点），
   * 显式 null 且本机无会话时清掉旧锚点；事件没带（undefined）保持现状。
   * 绝不按「本次收到事件的时刻 + hours」重算——那会把每次刷新都变成续期。 */
  /* 上次校验时刻与结论（架构方案 4.5）：bootstrap.login 与 check 事件都带；没带就保留上一次 */
  if (anchor && typeof anchor === "object" && "last_check_at" in anchor) {
    S.login.lastCheckAt = anchor.last_check_at ? String(anchor.last_check_at) : "";
    S.login.lastCheckState = String(anchor.last_check_state || "unknown");
  }
  if (anchor && typeof anchor === "object" && "estimated_expires_at" in anchor) {
    const at = numOrNull(anchor.estimated_expires_at);
    S.login.expireAt = at === null ? null : at * 1000;   /* 统一存 epoch 毫秒 */
    if (at === null) S.login.savedAt = null;
    else if (anchor.saved_at) S.login.savedAt = anchor.saved_at;
  }
  /* 估算来源（E2）：事件没带就保留上一次，别把已有的「约到」误降成「不估算」 */
  if (anchor && typeof anchor === "object" && "estimate_reason" in anchor) {
    S.login.estimateReason = anchor.estimate_reason ? String(anchor.estimate_reason) : null;
  }
  paintLogin();
  if (document.body) {
    paintRail();
    paintSelected();
    paintBoardActions();
    /* 后到的校验结论要能把空态从「正在检查」改成真实状态 */
    refreshLoginEmptyState();
  }
}

/* 当前凭证剩余小时：只从绝对锚点按 Date.now 推；没有锚点返回事件带回的静态值，
 * 两者都没有返回 null（未知，不编 17 小时）。 */
function loginHoursLeft() {
  if (S.login.expireAt !== null && S.login.expireAt !== undefined) {
    const bnMs = businessNowMs();
    if (bnMs == null) return null;   // 未校准：剩余显示未知，不拿 OS 时间冒充
    return (S.login.expireAt - bnMs) / 3600000;
  }
  return S.login.hours;
}

function expiryText() {
  const at = S.login.expireAt;
  return at ? "约到 " + whenText(at) : "未知（以学校校验为准）";
}

/* E2（计划 20261109，决策 006 修订）：预计有效的短句与完整写法。
 * 只作提示——任何一种写法都不参与放行、拦截、过期判定或要求重登。 */
function loginEstimateShort() {
  const at = S.login.expireAt;
  if (!at) return "";
  const now = businessNowMs();
  const p = schoolParts(at);
  const pad = (n) => String(n).padStart(2, "0");
  const time = pad(p.h) + ":" + pad(p.mi);
  if (now === null) return "约到 " + p.mo + "月" + p.d + "日 " + time;
  /* 跨天写「明天」；更远的日子写具体日期，避免把后天的时刻说成明天 */
  const diff = Math.round((startOfDay(at) - startOfDay(now)) / 86400000);
  if (diff === 0) return "约到 " + time;
  if (diff === 1) return "约到明天 " + time;
  return "约到 " + p.mo + "月" + p.d + "日 " + time;
}

function loginEstimateText() {
  const at = S.login.expireAt;
  /* 老载荷没带 estimate_reason：有锚点按 ok 显示，没锚点按未知处理 */
  const reason = S.login.estimateReason || (at ? "ok" : "no_anchor");
  if (reason === "clock_unavailable" || (reason === "ok" && !at)) {
    return "北京时间校准后再估";
  }
  if (reason !== "ok") return "不知道（这次登录不是在本工具里完成的）";
  const now = businessNowMs();
  if (now !== null && at <= now) {
    return S.login.result === "valid"
      ? "已过预计时间，学校仍确认有效"
      : "已过预计时间，以学校校验为准";
  }
  return loginEstimateShort() + "（按登录后 10 小时估，以学校为准）";
}

/* 登录态关联视口的统一收口（P1）：胶囊、剩余时间、时钟、大屏、路线、列表
 * 倒计时与空态、按钮必须在同一轮结论里一起刷新，不能只改胶囊留下旧倒计时。
 * 只重画、不改结论；调用点都已在请求代次校验之后，旧轮迟到事件不得用它
 * 覆盖新轮。 */
function syncLoginDependentView() {
  paintLogin();
  paintClockStatus();
  refreshLoginEmptyState();
  render();
}
