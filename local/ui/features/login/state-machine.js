/* 登录胶囊的纯状态机：输入调用方抄好的事实，输出阶段与旧 view.state。
 * 不碰 DOM、不读 window、不读时钟；阶段先后与 features/login/view.js 原分支一致。 */

export const LOGIN_PHASES = Object.freeze([
  "plan_running", "demo", "auto", "logging_in", "checking", "never",
  "unknown", "expired", "valid", "unset", "terms",
]);

export const LOGIN_VIEW_STATES = Object.freeze([
  "ok", "none", "demo", "pending", "checking", "unknown", "bad", "terms",
]);

export function loginPhase(facts) {
  const data = facts || {};
  const busyExpired = data.result === "expired" && data.present !== false;
  let phase;
  if (data.busy && !data.loginPending && !busyExpired && !data.autoLogin) phase = "plan_running";
  else if (data.demo) phase = "demo";
  else if (data.autoLogin) phase = "auto";
  else if (data.loginPending) phase = "logging_in";
  else if (data.checking || (data.ok === null && data.present === true)) phase = "checking";
  else if (data.present === false) phase = "never";
  else if (data.result === "unknown" && data.ok === false) phase = "unknown";
  else if (data.ok === false && data.present !== false) phase = "expired";
  else if (data.ok === true) phase = "valid";
  else phase = "unset";
  if (data.termsLocked && phase !== "demo" && phase !== "auto" && phase !== "logging_in") {
    return "terms";
  }
  return phase;
}

export function loginViewState(phase, present) {
  if (phase === "plan_running") return present === false ? "none" : "ok";
  const states = {
    demo: "demo", auto: "pending", logging_in: "pending", checking: "checking",
    never: "none", unknown: "unknown", expired: "bad", valid: "ok", unset: "none",
    terms: "terms",
  };
  return states[phase] || "none";
}
