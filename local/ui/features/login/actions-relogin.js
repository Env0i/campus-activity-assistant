/* 重新登录对话框的编排：开与关、发请求、轮询浏览器登录、把每一处控件接到动作上。 */
/* 重新登录对话框（设计文档 9.3，电脑和手机同一套规则）：按「有没有保存账号 × 有没有验证码识别」分三种情况。
 * - 有账号（识别装没装都一样）：直接进验证码步，电脑填账号密码，用户只输验证码；
 *   登录过又失效时后台本来就在自动恢复，不让用户再确认一次「自动登录一次？」；
 * - 没账号：填账号密码（默认只用一次，勾「保存到这台电脑」才在登录成功后保存），没识别再输验证码；
 * - 保存的密码学校不认：自动登录已暂停，要输新密码。
 * 计划来不及（有场次在提交或离开放不到 100 秒）时后端回 plan_late，这里只说明原因。
 * 验证码图与进度来自后端 phone_relogin 事件（与手机同一场流程），界面不自己编状态。 */

import { reloginRefusal, reloginWay } from "./state-relogin.js";
import { reloginCase, reloginCodeReady, reloginDialog, reloginError, reloginNextReady, reloginPaintWay, reloginResetForm, reloginShowChallenge, reloginStep, reloginTogglePass } from "./view-relogin.js";
import { paintLogin } from "./view.js";
import { termsLocked } from "../terms/state.js";

/* 已经因「登录成功」触发过刷新的 flow_id：中继会重放快照，同一场不能刷新两次，
 * 否则列表会被反复打回加载态。空 flow_id 视为同一事件，也只放行一次（初始 null
 * 与哨兵空串区分「还没刷新过」）。 */
export let reloginRefreshedFlow = null;

/* 后端最近推来的这一场进度：对话框没开时也要记着，点「重新登录」才能接上同一场，
 * 不新开一场把电脑正在跑的那场顶掉。 */
export let reloginRelay = null;

/* 转人工只提醒一次：中继会重放快照，同一个 handoff 不能每来一条就刷一条运行记录 */
export let reloginHandoffSeen = false;

/* 中继里这一场是不是「电脑自己发起、还在进行、没转人工」。flowId 给定时还要是同一场。
 * 关对话框不取消它，顶栏「自动登录中…」也只认它。 */
export function reloginAutoLive(flowId) {
  const relay = reloginRelay;
  if (!relay || !relay.live || relay.handoff || String(relay.origin || "") !== "auto") return false;
  return flowId === undefined || String(relay.flow_id || "") === String(flowId || "");
}

/* 拖出一条轻轮询：浏览器登录那条路登完后，对话框自己收起（原型 lgwait 说「这里会自己更新」） */
export let reloginBrowserWatch = 0;

export function stopBrowserWatch() {
  if (reloginBrowserWatch) { clearInterval(reloginBrowserWatch); reloginBrowserWatch = 0; }
}

export function watchBrowserLogin() {
  stopBrowserWatch();
  reloginBrowserWatch = setInterval(() => {
    if (!S.relogin || !S.relogin.open) { stopBrowserWatch(); return; }
    const login = S.login || {};
    if (login.result === "valid" || login.ok === true) {
      stopBrowserWatch();
      addLog("登录成功");
      closeRelogin();
    }
  }, 1000);
}

/* 所有「登录 / 重新登录」入口走这里：登录过又失效（含已转人工）走重新登录，
 * 从没登录过的走登录表单。 */
export function loginEntry() {
  const login = S.login || {};
  if (login.result === "expired" || login.handoff) { openRelogin(); return; }
  openLogin();
}

/* 打开对话框：按当前情况落到对应的第一步。计划来不及时直接说明，不开表单 */
export function openRelogin() {
  const dlg = reloginDialog();
  /* 条款没同意：登录是学校动作，交给 doLogin 的条款门（弹条款或安静返回），不开对话框 */
  if (!dlg || (typeof termsLocked === "function" && termsLocked())) { doLogin(); return; }
  if (typeof closeStatusCards === "function") closeStatusCards(false);
  S.relogin = { open: true, step: "", flowId: "", challengeId: "" };
  reloginResetForm();
  const kind = reloginCase();
  if (typeof dlg.showModal === "function") { if (!dlg.open) dlg.showModal(); }
  else dlg.setAttribute("open", "");
  /* 中继里已经有一场在跑（电脑正在自动登录，或刚转人工等用户输码）：接上这一场，不另开 */
  if (reloginRelay && reloginRelay.live) {
    S.relogin.flowId = String(reloginRelay.flow_id || "");
    if (reloginRelay.state === "waiting_code" && reloginRelay.mode !== "auto" && reloginRelay.image) {
      reloginShowChallenge(reloginRelay);
      return;
    }
    reloginStep("wait", reloginRelay.mode === "auto" ? "电脑正在识别验证码…" : "正在登录…");
    return;
  }
  if (kind === "bad") reloginStep("bad");
  else if (kind === "captcha") { reloginStep("wait", "正在打开学校登录页…"); void beginRelogin(); }
  else reloginStep("login");
}

/* 顶栏「登录」/「去登录」/过期横幅走这条：不管有没有保存账号，都从登录表单开始 */
export function openLogin() {
  const dlg = reloginDialog();
  if (!dlg || (typeof termsLocked === "function" && termsLocked())) { doLogin(); return; }
  if (typeof closeStatusCards === "function") closeStatusCards(false);
  S.relogin = { open: true, step: "", flowId: "", challengeId: "" };
  reloginResetForm();
  if (typeof dlg.showModal === "function") { if (!dlg.open) dlg.showModal(); }
  else dlg.setAttribute("open", "");
  reloginStep("login");
}

/* 登录方式切到「用学校登录页」：说明换成 web 那三条，表单收起（原型 lgWay 的行为） */
export function reloginPickWay(way) {
  if (!S.relogin || !S.relogin.open) return;
  S.relogin.way = way === "browser" ? "browser" : "here";
  reloginStep("login");
}

/* 「打开学校登录页」：交给浏览器登录那条老路，对话框停在 lgwait 等它回来 */
export function reloginOpenSchoolPage() {
  reloginStep("lgwait");
  watchBrowserLogin();
  doLogin();
}

export function closeRelogin() {
  const dlg = reloginDialog();
  const flowId = S.relogin && S.relogin.flowId;
  const live = S.relogin && S.relogin.step && ["wait", "cap"].indexOf(S.relogin.step) >= 0;
  S.relogin = { open: false, step: "", flowId: "", challengeId: "" };
  stopBrowserWatch();
  const wideDlg = reloginDialog();
  if (wideDlg) wideDlg.classList.remove("wide");
  if (dlg && typeof dlg.close === "function" && dlg.open) dlg.close();
  else if (dlg) dlg.removeAttribute("open");
  /* 用户中途关掉：取消这一场，别让后台还挂着一个等验证码的登录进程。
   * 例外：对话框接上的是电脑自己正在做的自动登录（还没转人工），关掉只是不看了，
   * 取消它等于替用户打断一件本来不需要他动手的事。 */
  /* 返回这次取消的 Promise：「改用浏览器登录」要等它返回再发 login（U6）——relogin_cancel 还在终止
   * 中继 worker 时，worker 仍占着忙碌位，这时到达的 login 会被「已经有一个任务在跑」拒绝。
   * 没有取消可等时返回已完成的 Promise；取消调用失败也算完成，不卡住后面的动作。 */
  if (live && flowId && !reloginAutoLive(flowId)) return api("relogin_cancel", flowId).catch(() => {});
  return Promise.resolve();
}

async function beginRelogin(username, password, save) {
  let result = null;
  try {
    result = username ? await api("relogin_begin", username, password, !!save) : await api("relogin_begin");
  } catch (err) {
    result = { ok: false, text: "登录没有开始：" + msg(err) };
  }
  if (!S.relogin.open) return;
  if (!result || !result.ok) { reloginStep("msg", reloginRefusal(result)); return; }
  S.relogin.flowId = String(result.flow_id || "");
  reloginStep("wait", result.mode === "auto" ? "电脑正在登录并识别验证码…" : "正在打开学校登录页…");
}

async function autoReloginOnce() {
  reloginStep("wait", "电脑正在自动登录…");
  let result = null;
  try {
    result = await api("relogin_auto_once");
  } catch (err) {
    result = { ok: false, text: "自动登录没有开始：" + msg(err) };
  }
  if (!S.relogin.open) return;
  if (!result || !result.ok) { reloginStep("msg", reloginRefusal(result)); return; }
  S.relogin.flowId = String(result.flow_id || "");
}

export function submitReloginForm() {
  const user = String(($("#rl-user") || {}).value || "").trim();
  const pass = String(($("#rl-pass") || {}).value || "");
  if (!user || !pass) { reloginError("账号和密码都要填。"); return; }
  const save = !!($("#rl-save") || {}).checked;
  /* 记下「这一场是从登录表单进来的」：之后到验证码页要显示「上一步」 */
  if (S.relogin) S.relogin.fromLogin = true;
  reloginStep("wait", "正在登录…");
  const passBox = $("#rl-pass");
  if (passBox) passBox.value = "";
  void beginRelogin(user, pass, save);
}

async function submitReloginCode() {
  const code = String(($("#rl-code") || {}).value || "").trim();
  if (!/^[0-9A-Za-z]{4}$/.test(code)) { reloginError("验证码是 4 位字母或数字。"); return; }
  reloginStep("wait", "正在核对验证码…");
  let result = null;
  try {
    result = await api("relogin_submit", S.relogin.flowId, S.relogin.challengeId, code);
  } catch (err) {
    result = { ok: false, text: "验证码没有发出去：" + msg(err) };
  }
  if (S.relogin.open && result && result.ok === false && result.error !== "duplicate_submit") {
    reloginStep("msg", String(result.text || "验证码没有发出去，重新登录试试。"));
  }
}

export const RELOGIN_FAIL_TEXT = {
  bad_password: "学校说账号或密码不对。保存的密码已暂停使用；到「设置 → 登录」换成新密码，或在这里重新输入。",
  timeout: "这次登录超时了，可以再试一次。",
  canceled: "这次登录已取消。",
};

/* 登录成功的收尾：与浏览器登录成功走同一条路（controllers/plan.js handleDone 的
 * doCheck + refresh），让活动列表立刻加载，用户不必再手点一次「刷新」（N1）。
 * 计划运行中不刷新：后端照常继续计划，界面只说明这一句。 */
export function reloginSucceeded(flowId) {
  if (S.busy) return;
  const flow = String(flowId || "");
  /* 空 flow_id 视为同一事件：首次放行后记下哨兵空串，重放一律去重。 */
  if (flow === reloginRefreshedFlow) return;
  reloginRefreshedFlow = flow;
  if (typeof doCheck === "function") doCheck();
  /* 程序自己发起的刷新（U2/U3）：列表已有内容就走后台轮，失败不清列表和勾选；
   * 列表空着（常常正是因为登录失效才拉不到列表）走前台轮，才有骨架和错误空态可看。
   * 与 controllers/plan.js 浏览器登录成功后的判定同一口径。 */
  if (typeof refresh === "function") refresh(true, S.items.length ? { background: true } : undefined);
}

/* 后端推来的这一场进度（与手机同一份 public_state）：只在对话框开着时接管画面 */
export function receiveReloginState(payload) {
  const data = payload || {};
  reloginRelay = data;
  const handoff = !!data.handoff;
  /* 转人工：后台不另开一场，等用户在对话框里输这张验证码；只提醒一次 */
  if (handoff && !reloginHandoffSeen) {
    reloginHandoffSeen = true;
    /* 运行记录的次数要跟验证码页的提示一致：认错一次就转人工（识别结果不合规）和认满 3 次是两条路，说法不同 */
    const times = Number(data.attempts) || 0;
    addLog(times >= 3
      ? "[!] 自动识别 3 次没认对，请点「重新登录」输入验证码"
      : "[!] 电脑没认出验证码，请点「重新登录」输入验证码");
  }
  if (!handoff) reloginHandoffSeen = false;
  if (S.login) {
    /* 一场走完（成功/失败/取消）就不再是「等用户输码」，下一段失效还能重新静默恢复 */
    if (data.state === "success" || data.live === false) S.login.handoff = false;
    else if (handoff) S.login.handoff = true;
  }
  if (!S.relogin || !S.relogin.open) {
    if (data.state === "success") {
      if (S.busy) addLog("重新登录成功，报名计划照常继续");
      else reloginSucceeded(data.flow_id);
    }
    return;
  }
  if (S.relogin.flowId && data.flow_id && String(data.flow_id) !== S.relogin.flowId) return;
  if (data.flow_id) S.relogin.flowId = String(data.flow_id);
  const state = String(data.state || "");
  if (state === "waiting_code" && data.mode !== "auto" && data.image) {
    reloginShowChallenge(data);
    return;
  }
  if (state === "verifying" || state === "starting" || (state === "waiting_code" && data.mode === "auto")) {
    reloginStep("wait", data.mode === "auto" ? "电脑正在识别验证码…" : "正在登录…");
    return;
  }
  if (state === "success") {
    reloginSucceeded(data.flow_id);   /* 先按本场 flow 记账，再把 flowId 清空 */
    addLog(S.busy ? "重新登录成功，报名计划照常继续" : "重新登录成功");
    reloginStep("msg", S.busy ? "重新登录成功，报名计划照常继续。" : "重新登录成功。");
    S.relogin.flowId = "";
    return;
  }
  if (state === "failed" || state === "canceled") {
    const code = String(data.safe_error || state);
    /* 学校说密码不对：不重试（避免账号被锁），进「保存的密码不对」那一步让用户更新密码 */
    if (code === "bad_password") reloginStep("bad");
    else reloginStep("msg", RELOGIN_FAIL_TEXT[code] || "这次没登录上，可以再试一次，或者改用浏览器登录。");
    S.relogin.flowId = "";
  }
}

async function reloginSwitchToBrowser() {
  const flowId = S.relogin && S.relogin.flowId;
  const live = S.relogin && S.relogin.step && ["wait", "cap"].indexOf(S.relogin.step) >= 0;
  if (!live || !flowId || reloginAutoLive(flowId)) {
    await closeRelogin();
    doLogin();
    return;
  }
  reloginStep("wait", "正在切换…");
  try {
    await api("relogin_cancel", flowId);
  } catch (error) {
    /* 取消失败也要收口，浏览器登录仍由用户重新发起。 */
  }
  if (S.relogin) S.relogin.flowId = "";
  await closeRelogin();
  doLogin();
}

export function wireRelogin() {
  const on = (id, fn) => {
    const el = $("#" + id);
    if (el && el.addEventListener) el.addEventListener("click", fn);
  };
  on("btn-rl-auto", () => { void autoReloginOnce(); });
  on("btn-lg-next", submitReloginForm);
  on("btn-rl-code", () => { void submitReloginCode(); });
  on("btn-rl-browser", () => { void reloginSwitchToBrowser(); });
  on("btn-bad-browser", () => { void reloginSwitchToBrowser(); });
  on("btn-bad-update", () => { if (S.relogin) S.relogin.fromLogin = false; reloginPickWay("here"); });
  on("btn-lg-back", () => { if (S.relogin) S.relogin.fromLogin = false; reloginStep("login"); });
  on("btn-lg-webopen", reloginOpenSchoolPage);
  on("btn-rl-cancel", closeRelogin);
  on("btn-rl-done", closeRelogin);
  on("lg-here", () => reloginPickWay("here"));
  on("lg-web", () => reloginPickWay("browser"));
  on("lg-eye", reloginTogglePass);
  /* 账号或密码一动，「下一步」的可用状态跟着变；勾保存会换第 2 条说明的写法 */
  const userInput = $("#rl-user");
  if (userInput && userInput.addEventListener) userInput.addEventListener("input", reloginNextReady);
  const passInput = $("#rl-pass");
  if (passInput && passInput.addEventListener) {
    passInput.addEventListener("input", reloginNextReady);
    passInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && reloginWay() === "here") { event.preventDefault(); submitReloginForm(); }
    });
  }
  const saveBox = $("#rl-save");
  if (saveBox && saveBox.addEventListener) saveBox.addEventListener("change", reloginPaintWay);
  /* 验证码满 4 位才亮「登录」（原型 cap 的按钮是这么禁用的），回车等同点它 */
  const codeInput = $("#rl-code");
  if (codeInput && codeInput.addEventListener) {
    codeInput.addEventListener("input", reloginCodeReady);
    codeInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); void submitReloginCode(); }
    });
  }
  const dlg = reloginDialog();
  if (dlg && dlg.addEventListener) {
    dlg.addEventListener("cancel", (event) => { event.preventDefault(); closeRelogin(); });
  }
}

/* 三个异步动作只在本文件里被接线调用，导出用列表写法：沙箱只认 export 声明与 export { 列表 }。 */
export { autoReloginOnce, beginRelogin, reloginSwitchToBrowser, submitReloginCode };
