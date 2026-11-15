/* 登录三态的还原与剩余时间估算：纯推导，不碰 DOM、不发请求。 */

/* 登录三态还原与剩余估算（只展示，不参与放行）。 */
export function loginSnapshotState() {
  return {
    hours: S.login.hours, ok: S.login.ok, present: S.login.present,
    expireAt: S.login.expireAt, savedAt: S.login.savedAt, result: S.login.result,
    estimateReason: S.login.estimateReason,
  };
}

export function restoreLoginSnapshotState(snap) {
  if (!snap) return;
  S.login.hours = snap.hours;
  S.login.ok = snap.ok;
  S.login.present = snap.present;
  S.login.expireAt = snap.expireAt;
  S.login.savedAt = snap.savedAt;
  S.login.result = snap.result;
  S.login.estimateReason = snap.estimateReason === undefined ? null : snap.estimateReason;
}

/* 当前凭证剩余小时：只从绝对锚点按 Date.now 推；没有锚点返回事件带回的静态值，
 * 两者都没有返回 null（未知，不编 17 小时）。 */
export function loginHoursLeft() {
  if (S.login.expireAt !== null && S.login.expireAt !== undefined) {
    const bnMs = businessNowMs();
    if (bnMs == null) return null;   // 未校准：剩余显示未知，不拿 OS 时间冒充
    return (S.login.expireAt - bnMs) / 3600000;
  }
  return S.login.hours;
}

export function expiryText() {
  const at = S.login.expireAt;
  return at ? "约到 " + whenText(at) : "未知（以学校校验为准）";
}

/* E2（计划 20261109，决策 006 修订）：预计有效的短句与完整写法。
 * 只作提示——任何一种写法都不参与放行、拦截、过期判定或要求重登。 */
export function loginEstimateShort() {
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

export function loginEstimateText() {
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
