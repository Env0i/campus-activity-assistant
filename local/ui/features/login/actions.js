/* 登录状态的统一写入与重画：改完状态后按顺序把受影响的视图刷一遍。 */

import { receiveReloginState, reloginAutoLive } from "./actions-relogin.js";
import { paintLogin } from "./view.js";

/* 「自动登录中」只在两种情况下成立：学校判失效且后端说电脑正在恢复（setLogin 置位），
 * 或中继里确有一场电脑自己发起、还在进行、没转人工的登录（receiveReloginState 置位）。
 * 这里只负责收回，不置位：结论为 valid、已转人工、结论不是 expired 又没有这样一场中继时，
 * S.autoLogin 都不该还亮着，否则顶栏胶囊会一直停在「自动登录中…」。 */
export function reconcileAutoLogin() {
  if (!S.autoLogin) return;
  if (S.login.handoff || S.login.result === "valid") { S.autoLogin = false; return; }
  if (S.login.result === "expired") return;   /* 由 recovering 和中继事件决定 */
  if (typeof reloginAutoLive !== "function" || !reloginAutoLive()) S.autoLogin = false;
}

export function setLogin(hours, ok, present, anchor) {
  S.login.hours = numOrNull(hours);
  S.login.ok = ok;
  /* present 是后端 session_present 的回声：false=从没登录过，true=登录过。
   * 不传（undefined）表示这次事件没说，保留上一次的判断。 */
  if (present !== undefined) S.login.present = !!present;
  /* 静默自动登录（计划 20261111）：登录已失效、但电脑能自己补回来时，胶囊显示
   * 「自动登录中」，失效横幅也不出现（paintLogin 读 S.autoLogin）。
   * recovering 只由后端在本次 check 结论为 expired 时给出：第一次静默失败或已转人工
   * 输验证码时是 false，提醒照旧回来。转人工后（S.login.handoff）不再画回自动登录中。 */
  if (anchor && typeof anchor === "object" && "recovering" in anchor) {
    S.login.recovering = !!anchor.recovering;
    S.login.recoverBlock = anchor.recover_block ? String(anchor.recover_block) : "";
    if (S.login.result === "expired" && !S.login.handoff) S.autoLogin = !!anchor.recovering;
  }
  if (S.login.result === "valid") S.login.handoff = false;
  /* 不在「自动登录中」该在的状态里就收回（check 结论为 valid / 暂时无法确认 / 已转人工，
   * 或后端说不再恢复），不等中继的收尾事件：事件可能先到、晚到或没到。 */
  reconcileAutoLogin();
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

/* 登录态关联视口的统一收口（P1）：胶囊、剩余时间、时钟、大屏、路线、列表
 * 倒计时与空态、按钮必须在同一轮结论里一起刷新，不能只改胶囊留下旧倒计时。
 * 只重画、不改结论；调用点都已在请求代次校验之后，旧轮迟到事件不得用它
 * 覆盖新轮。 */
export function syncLoginDependentView() {
  /* 校验超时、请求失败等路径直接改 S.login.result 再走这里：先收回过期的自动登录态 */
  reconcileAutoLogin();
  paintLogin();
  paintClockStatus();
  refreshLoginEmptyState();
  render();
}
