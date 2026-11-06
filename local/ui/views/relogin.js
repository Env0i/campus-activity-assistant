/* 重新登录对话框（设计文档 9.3，电脑和手机同一套规则）：按「有没有保存账号 × 有没有验证码识别」分四种情况。
 * - 有账号 + 有识别：先确认，再让电脑自动登录一次（relogin_auto_once）；
 * - 有账号 + 没识别：电脑填账号密码，用户只输验证码（relogin_begin → relogin_submit）；
 * - 没账号：填账号密码（默认只用一次，勾「保存到这台电脑」才在登录成功后保存），没识别再输验证码；
 * - 保存的密码学校不认：自动登录已暂停，要输新密码。
 * 计划来不及（有场次在提交或离开放不到 100 秒）时后端回 plan_late，这里只说明原因。
 * 验证码图与进度来自后端 phone_relogin 事件（与手机同一场流程），界面不自己编状态。 */
const RELOGIN_PRIVACY_NOTE = "登录时，工具会替你勾选学校登录页上的《隐私协议》。";

/* 已经因「登录成功」触发过刷新的 flow_id：中继会重放快照，同一场不能刷新两次，
 * 否则列表会被反复打回加载态。空 flow_id 视为同一事件，也只放行一次（初始 null
 * 与哨兵空串区分「还没刷新过」）。 */
let reloginRefreshedFlow = null;

function reloginDialog() {
  return $("#dlg-relogin");
}

function reloginCase() {
  const cred = typeof autoLoginCredential === "function" ? autoLoginCredential() : {};
  if (cred.saved && cred.paused) return "bad";
  if (cred.saved && cred.ocr) return "confirm";
  if (cred.saved) return "captcha";
  return "form";
}

function reloginStep(step, text) {
  S.relogin.step = step;
  ["confirm", "form", "cap", "wait", "msg"].forEach((name) => {
    const box = $("#rl-" + name);
    if (box) box.hidden = name !== step;
  });
  const msgBox = $("#rl-msg-text");
  if (step === "msg" && msgBox) msgBox.textContent = String(text || "");
  const waitBox = $("#rl-wait-text");
  if (step === "wait" && waitBox) waitBox.textContent = String(text || "正在登录…");
}

/* 打开对话框：按当前四种情况落到对应的第一步。计划来不及时直接说明，不开表单 */
function openRelogin() {
  const dlg = reloginDialog();
  /* 条款没同意：登录是学校动作，交给 doLogin 的条款门（弹条款或安静返回），不开对话框 */
  if (!dlg || (typeof termsLocked === "function" && termsLocked())) { doLogin(); return; }
  if (typeof closeStatusCards === "function") closeStatusCards(false);
  S.relogin = { open: true, step: "", flowId: "", challengeId: "" };
  const kind = reloginCase();
  const note = $("#rl-form-note");
  if (note) {
    note.textContent = kind === "bad"
      ? "电脑上保存的密码学校不认，自动登录已暂停。输入新的账号密码；勾选保存会替换旧的。"
      : "账号密码默认只用这一次，不写进电脑；勾选下面这一项才会在登录成功后保存。";
  }
  const pass = $("#rl-pass");
  if (pass) pass.value = "";
  const code = $("#rl-code");
  if (code) code.value = "";
  const save = $("#rl-save");
  if (save) save.checked = false;
  if (kind === "confirm") reloginStep("confirm");
  else if (kind === "captcha") { reloginStep("wait", "正在打开学校登录页…"); void beginRelogin(); }
  else reloginStep("form");
  if (typeof dlg.showModal === "function") { if (!dlg.open) dlg.showModal(); }
  else dlg.setAttribute("open", "");
}

function closeRelogin() {
  const dlg = reloginDialog();
  const flowId = S.relogin && S.relogin.flowId;
  const live = S.relogin && S.relogin.step && ["wait", "cap"].indexOf(S.relogin.step) >= 0;
  S.relogin = { open: false, step: "", flowId: "", challengeId: "" };
  if (dlg && typeof dlg.close === "function" && dlg.open) dlg.close();
  else if (dlg) dlg.removeAttribute("open");
  /* 用户中途关掉：取消这一场，别让后台还挂着一个等验证码的登录进程 */
  if (live && flowId) api("relogin_cancel", flowId).catch(() => {});
}

/* 后端的拒绝统一说人话；plan_late 单独一句「现在来不及」 */
function reloginRefusal(result) {
  const data = result || {};
  if (data.error === "plan_late") {
    return "现在来不及重新登录：" + String(data.text || "有场次正在提交，或者离开放不到 100 秒。")
      + " 电脑能自动登录就会自动登录。";
  }
  return String(data.text || "这次没能开始登录，稍后再试。");
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

function submitReloginForm() {
  const user = String(($("#rl-user") || {}).value || "").trim();
  const pass = String(($("#rl-pass") || {}).value || "");
  if (!user || !pass) {
    const err = $("#rl-form-err");
    if (err) { err.hidden = false; err.textContent = "账号和密码都要填。"; }
    return;
  }
  const save = !!($("#rl-save") || {}).checked;
  reloginStep("wait", "正在登录…");
  const passBox = $("#rl-pass");
  if (passBox) passBox.value = "";
  void beginRelogin(user, pass, save);
}

async function submitReloginCode() {
  const code = String(($("#rl-code") || {}).value || "").trim();
  if (!/^[0-9A-Za-z]{4}$/.test(code)) {
    const err = $("#rl-cap-err");
    if (err) { err.hidden = false; err.textContent = "验证码是 4 位字母或数字。"; }
    return;
  }
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

const RELOGIN_FAIL_TEXT = {
  bad_password: "学校说账号或密码不对。保存的密码已暂停使用；到「设置 → 登录」换成新密码，或在这里重新输入。",
  timeout: "这次登录超时了，可以再试一次。",
  canceled: "这次登录已取消。",
};

/* 登录成功的收尾：与浏览器登录成功走同一条路（controllers/plan.js handleDone 的
 * doCheck + refresh），让活动列表立刻加载，用户不必再手点一次「刷新」（N1）。
 * 计划运行中不刷新：后端照常继续计划，界面只说明这一句。 */
function reloginSucceeded(flowId) {
  if (S.busy) return;
  const flow = String(flowId || "");
  /* 空 flow_id 视为同一事件：首次放行后记下哨兵空串，重放一律去重。 */
  if (flow === reloginRefreshedFlow) return;
  reloginRefreshedFlow = flow;
  if (typeof doCheck === "function") doCheck();
  if (typeof refresh === "function") refresh(true);
}

/* 后端推来的这一场进度（与手机同一份 public_state）：只在对话框开着时接管画面 */
function receiveReloginState(payload) {
  const data = payload || {};
  /* 顶栏「自动登录中…」：这一场是电脑自动发起的、还在进行就亮，结束就收（架构方案 4.3） */
  const auto = String(data.origin || "") === "auto" && !!data.live;
  if (auto !== !!S.autoLogin) {
    S.autoLogin = auto;
    paintLogin();
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
    S.relogin.challengeId = String(data.challenge_id || "");
    const img = $("#rl-cap-img");
    if (img) img.src = String(data.image);
    const tries = $("#rl-cap-tries");
    if (tries) tries.textContent = Number(data.attempts) > 0 ? "已经试过 " + Number(data.attempts) + " 次，换了一张新图。" : "";
    const err = $("#rl-cap-err");
    if (err) err.hidden = true;
    reloginStep("cap");
    const code = $("#rl-code");
    if (code) { code.value = ""; if (typeof code.focus === "function") code.focus(); }
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
    reloginStep("msg", RELOGIN_FAIL_TEXT[code] || "这次没登录上，可以再试一次，或者改用浏览器登录。");
    S.relogin.flowId = "";
  }
}

function wireRelogin() {
  const on = (id, fn) => {
    const el = $("#" + id);
    if (el && el.addEventListener) el.addEventListener("click", fn);
  };
  on("btn-rl-auto", () => { void autoReloginOnce(); });
  on("btn-rl-form", submitReloginForm);
  on("btn-rl-code", () => { void submitReloginCode(); });
  on("btn-rl-browser", () => { closeRelogin(); doLogin(); });
  on("btn-rl-close", closeRelogin);
  on("btn-rl-done", closeRelogin);
  const dlg = reloginDialog();
  if (dlg && dlg.addEventListener) {
    dlg.addEventListener("cancel", (event) => { event.preventDefault(); closeRelogin(); });
  }
}
