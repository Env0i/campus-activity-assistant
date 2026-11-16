/* 登录状态的统一写入与重画：改完状态后按顺序把受影响的视图刷一遍。 */

import { paintLogin } from "./view.js";
import { AUTO_STATES } from "./state-machine.js";
import { paintBoardActions, paintSelected } from "../plan/view.js";

/* 自动登录态只认后端给的 auto_state：电脑那边在不在登、转没转人工、多久后重试只有后端知道，
 * 前端从中继快照或结论去猜会和后端对不上。S.autoLogin 只是 state === "running" 的镜像，
 * 只在这里写。载荷没带 auto_state 时返回 false 并保持上一次：前端自己判出的暂时无法确认
 * 没有后端字段，后端状态一变会在一秒内推 login_auto，下一次校验也会带新值。 */
export function applyAutoState(fields) {
  if (!fields || typeof fields.auto_state !== "string") return false;
  const state = AUTO_STATES.indexOf(fields.auto_state) >= 0 ? fields.auto_state : "idle";
  const block = typeof fields.auto_block === "string" ? fields.auto_block : "";
  const retryInS = state === "backoff" && Number.isInteger(fields.auto_retry_in_s)
    ? fields.auto_retry_in_s : null;
  S.login.auto = { state: state, block: block, retryInS: retryInS, at: performance.now() };
  S.autoLogin = state === "running";
  return true;
}

/* 后端主动推来的 login_auto（中继结束、转人工、退避）：写进状态后和校验结论走同一个收口重画，
 * 横幅也当场跟着换；没带 auto_state 的载荷不动状态也不重画。 */
export function receiveAutoState(payload) {
  if (!applyAutoState(payload)) return false;
  syncLoginDependentView();
  paintBanners();
  return true;
}

export function setLogin(hours, ok, present, anchor) {
  S.login.hours = numOrNull(hours);
  S.login.ok = ok;
  /* present 是后端 session_present 的回声：false=从没登录过，true=登录过。
   * 不传（undefined）表示这次事件没说，保留上一次的判断。 */
  if (present !== undefined) S.login.present = !!present;
  if (S.login.result === "valid") S.login.handoff = false;
  if (anchor && typeof anchor === "object" && typeof anchor.auto_state === "string") {
    applyAutoState(anchor);
  } else if (S.login.result === "valid" || S.demo) {
    applyAutoState({ auto_state: "idle" });
  }
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
  paintLogin();
  paintClockStatus();
  refreshLoginEmptyState();
  render();
}
