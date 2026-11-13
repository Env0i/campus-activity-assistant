/* 重新登录对话框（设计文档 9.3，电脑和手机同一套规则）：按「有没有保存账号 × 有没有验证码识别」分三种情况。
 * - 有账号（识别装没装都一样）：直接进验证码步，电脑填账号密码，用户只输验证码；
 *   登录过又失效时后台本来就在自动恢复，不让用户再确认一次「自动登录一次？」；
 * - 没账号：填账号密码（默认只用一次，勾「保存到这台电脑」才在登录成功后保存），没识别再输验证码；
 * - 保存的密码学校不认：自动登录已暂停，要输新密码。
 * 计划来不及（有场次在提交或离开放不到 100 秒）时后端回 plan_late，这里只说明原因。
 * 验证码图与进度来自后端 phone_relogin 事件（与手机同一场流程），界面不自己编状态。 */
const RELOGIN_PRIVACY_NOTE = "登录时，工具会替你勾选学校登录页上的《隐私协议》。";

/* 已经因「登录成功」触发过刷新的 flow_id：中继会重放快照，同一场不能刷新两次，
 * 否则列表会被反复打回加载态。空 flow_id 视为同一事件，也只放行一次（初始 null
 * 与哨兵空串区分「还没刷新过」）。 */
let reloginRefreshedFlow = null;

/* 后端最近推来的这一场进度：对话框没开时也要记着，点「重新登录」才能接上同一场，
 * 不新开一场把电脑正在跑的那场顶掉。 */
let reloginRelay = null;
/* 转人工只提醒一次：中继会重放快照，同一个 handoff 不能每来一条就刷一条运行记录 */
let reloginHandoffSeen = false;

/* 中继里这一场是不是「电脑自己发起、还在进行、没转人工」。flowId 给定时还要是同一场。
 * 关对话框不取消它，顶栏「自动登录中…」也只认它。 */
function reloginAutoLive(flowId) {
  const relay = reloginRelay;
  if (!relay || !relay.live || relay.handoff || String(relay.origin || "") !== "auto") return false;
  return flowId === undefined || String(relay.flow_id || "") === String(flowId || "");
}

function reloginDialog() {
  return $("#dlg-relogin");
}

function reloginCase() {
  const cred = typeof autoLoginCredential === "function" ? autoLoginCredential() : {};
  if (cred.saved && cred.paused) return "bad";
  /* 保存过账号就直接进验证码步：装了识别也一样，后台已经在自动认，不再先问一次 */
  if (cred.saved) return "captcha";
  return "login";
}

/* 打码账号：后端的 credential 里有 username 才给（手机页同一条规则），没有就只说登录方式。 */
function reloginMask() {
  const cred = typeof autoLoginCredential === "function" ? autoLoginCredential() : {};
  return String(cred.mask || "");
}

function reloginCapSub(mask) {
  return mask ? "账号 " + mask + " 和密码由电脑自动填写" : "账号和密码由电脑自动填写";
}

/* 打码背后的明文账号：只有「在这里输入」这条路要把它填回输入框。 */
function reloginUser() {
  const cred = typeof autoLoginCredential === "function" ? autoLoginCredential() : {};
  return String(cred.username || "");
}

/* 从登录表单点进验证码的：副句要说密码已填好，底栏第一个按钮变「上一步」（原型 1694-1697） */
function reloginFromLogin() {
  return !!(S.relogin && S.relogin.fromLogin);
}

/* 标题与副句照原型 rlView（Main.dc.html:1666-1698）：确认是「自动登录一次？」，
   验证码是「输入验证码」，登录表单是「登录学校账号」，自动登录中是「正在自动登录」。 */
function reloginHead(step, text) {
  const mask = reloginMask();
  const busy = String(text || "");
  let title = "重新登录";
  let sub = "";
  if (step === "confirm") {
    title = "自动登录一次？";
    sub = mask ? "用保存的账号 " + mask + "，验证码由电脑识别" : "验证码由电脑识别";
    const body = $("#rl-confirm-text");
    if (body) {
      body.textContent = "会向学校发送一次账号密码。登录时，工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。"
        + (S.busy ? "成功后报名计划照常继续。" : "成功后会刷新活动列表，计划不会自动开始。");
    }
  } else if (step === "login") {
    title = "登录学校账号";
    sub = "两种方式都可以，选你放心的那种";
  } else if (step === "bad") {
    title = "保存的密码不对";
    sub = "自动登录已暂停";
    const badText = $("#rl-bad-text");
    if (badText) badText.textContent = "学校说账号或密码不对。为了避免账号被锁，工具没有重试。请更新账号密码，之后自动登录会恢复。";
  } else if (step === "lgwait") {
    title = "在学校登录页登录";
    sub = "已经用浏览器打开学校登录页";
  } else if (step === "cap") {
    title = "输入验证码";
    sub = reloginFromLogin() && mask ? "账号 " + mask + "，密码已填好" : reloginCapSub(mask);
  } else if (step === "wait") {
    /* 从验证码页点下去还是「输入验证码」，只是正文换成忙碌行（原型 verifying 就是这么留标题的） */
    if (/核对验证码/.test(busy)) {
      title = "输入验证码";
      sub = reloginFromLogin() && mask ? "账号 " + mask + "，密码已填好" : reloginCapSub(mask);
    } else if (/自动/.test(busy)) { title = "正在自动登录"; sub = mask ? "用保存的账号 " + mask : ""; }
  }
  const titleBox = $("#dlg-relogin-title");
  if (titleBox) titleBox.textContent = title;
  const subBox = $("#rl-sub");
  if (subBox) { subBox.textContent = sub; subBox.hidden = !sub; }
}

/* 底部按钮跟着步骤走，位置固定在右下一行（原型 .dlg-f）：
   确认 = 取消 + 自动登录（原型这一步不摆浏览器入口）；
   登录 = 在这里输入时「取消 / 下一步」，用学校登录页时「取消 / 打开学校登录页」；
   验证码 = 浏览器 + 取消 + 登录；密码不对 = 在浏览器里登录 + 更新账号密码；
   在学校登录页等 = 取消；结果 = 知道了；忙碌时整条底栏收起 */
const RELOGIN_LOGIN_ACTS = {
  here: ["btn-rl-cancel", "btn-lg-next"],
  browser: ["btn-rl-cancel", "btn-lg-webopen"],
};
const RELOGIN_ACTS = {
  confirm: ["btn-rl-cancel", "btn-rl-auto"],
  cap: ["btn-rl-browser", "btn-rl-cancel", "btn-rl-code"],
  bad: ["btn-bad-browser", "btn-bad-update"],
  lgwait: ["btn-rl-cancel"],
  msg: ["btn-rl-done"],
  wait: [],
};
const RELOGIN_ALL_ACTS = ["btn-rl-browser", "btn-rl-cancel", "btn-rl-auto", "btn-bad-browser",
  "btn-bad-update", "btn-lg-back", "btn-lg-next", "btn-lg-webopen", "btn-rl-code", "btn-rl-done"];

function reloginWay() {
  return S.relogin && S.relogin.way === "browser" ? "browser" : "here";
}

function reloginActs(step) {
  if (step === "login") return RELOGIN_LOGIN_ACTS[reloginWay()] || RELOGIN_LOGIN_ACTS.here;
  /* 从登录表单点进来的验证码页：左边那个「改用浏览器登录」换成「上一步」（原型 1694-1697） */
  if (step === "cap" && reloginFromLogin()) return ["btn-lg-back", "btn-rl-cancel", "btn-rl-code"];
  return RELOGIN_ACTS[step] || [];
}

/* 登录那一屏：选中卡、表单、两组说明和警示语都跟着方式切（原型 lgWay） */
function reloginPaintWay() {
  const web = reloginWay() === "browser";
  const here = $("#lg-here");
  const browser = $("#lg-web");
  if (here) { here.classList.toggle("on", !web); here.setAttribute("aria-checked", String(!web)); }
  if (browser) { browser.classList.toggle("on", web); browser.setAttribute("aria-checked", String(web)); }
  const form = $("#lg-form");
  if (form) form.hidden = web;
  const trade = $("#lg-trade");
  if (trade) trade.hidden = !web;
  const hereFacts = $("#lg-facts-here");
  if (hereFacts) hereFacts.hidden = web;
  const webFacts = $("#lg-facts-web");
  if (webFacts) webFacts.hidden = !web;
  const saveFact = $("#lg-fact-save");
  const save = $("#rl-save");
  if (saveFact) {
    saveFact.textContent = save && save.checked
      ? "勾了保存：用 Windows 当前用户加密，只有这台电脑能解开，设置里随时能清除"
      : "没勾保存：密码只用这一次，不写进电脑";
  }
  reloginNextReady();
}

/* 「下一步」只有账号和密码都填了才亮（原型 acts 里的禁用条件） */
function reloginNextReady() {
  const user = String(($("#rl-user") || {}).value || "").trim();
  const pass = String(($("#rl-pass") || {}).value || "");
  const btn = $("#btn-lg-next");
  if (btn) btn.disabled = !user || !pass;
}

/* 密码框右侧的眼睛：点一下在明文和圆点之间切（原型 lgShow） */
function reloginTogglePass() {
  const pass = $("#rl-pass");
  const eye = $("#lg-eye");
  if (!pass) return;
  const show = pass.type === "password";
  pass.type = show ? "text" : "password";
  if (eye) {
    eye.classList.toggle("on", show);
    eye.setAttribute("aria-label", show ? "隐藏密码" : "显示密码");
    eye.setAttribute("title", show ? "隐藏密码" : "显示密码");
  }
  if (typeof pass.focus === "function") pass.focus();
}

function reloginCodeReady() {
  const code = String(($("#rl-code") || {}).value || "").trim();
  const btn = $("#btn-rl-code");
  if (btn) btn.disabled = !/^[0-9A-Za-z]{4}$/.test(code);
}

/* 错误条只有一条，固定在正文最上面（原型 10-外框）：传空串即收起 */
function reloginError(text) {
  const err = $("#rl-err");
  if (!err) return;
  err.textContent = String(text || "");
  err.hidden = !text;
}

function reloginStep(step, text) {
  S.relogin.step = step;
  ["confirm", "login", "bad", "cap", "wait", "lgwait", "msg"].forEach((name) => {
    const box = $("#rl-" + name);
    if (box) box.hidden = name !== step;
  });
  /* 登录那一屏比其它步骤宽一档（原型 .wide = 32rem），进出时跟着切 */
  const dlg = reloginDialog();
  if (dlg) dlg.classList.toggle("wide", step === "login");
  reloginHead(step, text);
  if (step === "login") reloginPaintWay();
  const acts = reloginActs(step);
  RELOGIN_ALL_ACTS.forEach((id) => {
    const el = $("#" + id);
    if (el) el.hidden = acts.indexOf(id) < 0;
  });
  /* 忙碌时原型整条底栏都不出现（hasActs=false），这里也不留一条空边 */
  const foot = $("#rl-foot");
  if (foot) foot.hidden = acts.length === 0;
  reloginError("");
  reloginCodeReady();
  const msgBox = $("#rl-msg-text");
  if (step === "msg" && msgBox) msgBox.textContent = String(text || "");
  const waitBox = $("#rl-wait-text");
  if (step === "wait" && waitBox) waitBox.textContent = String(text || "正在登录…");
}

/* 打开对话框并把表单清干净：两种入口（登录按钮 / 登录失效后再登录）都先过这里 */
function reloginResetForm() {
  const user = $("#rl-user");
  if (user) user.value = reloginUser();
  const pass = $("#rl-pass");
  if (pass) { pass.value = ""; pass.type = "password"; }
  const eye = $("#lg-eye");
  if (eye) {
    eye.classList.remove("on");
    eye.setAttribute("aria-label", "显示密码");
    eye.setAttribute("title", "显示密码");
  }
  const code = $("#rl-code");
  if (code) code.value = "";
  const save = $("#rl-save");
  if (save) save.checked = false;
  S.relogin.way = "here";
  S.relogin.fromLogin = false;
}

/* 拖出一条轻轮询：浏览器登录那条路登完后，对话框自己收起（原型 lgwait 说「这里会自己更新」） */
let reloginBrowserWatch = 0;

function stopBrowserWatch() {
  if (reloginBrowserWatch) { clearInterval(reloginBrowserWatch); reloginBrowserWatch = 0; }
}

function watchBrowserLogin() {
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

/* 验证码那一屏：图、已试次数、转人工提示都在这里画，打开对话框和收事件共用一份 */
function reloginShowChallenge(data) {
  const payload = data || {};
  S.relogin.challengeId = String(payload.challenge_id || "");
  const img = $("#rl-cap-img");
  if (img) img.src = String(payload.image || "");
  const tries = $("#rl-cap-tries");
  if (tries) tries.textContent = Number(payload.attempts) > 0 ? "已经试过 " + Number(payload.attempts) + " 次，换了一张新图。" : "";
  reloginStep("cap");
  /* 电脑自动发起的一场认不出来就交给用户：不另开一场，直接让用户输这一张的验证码 */
  if (payload.handoff) {
    const times = Number(payload.attempts) || 0;
    reloginError(times >= 3 ? "自动识别 3 次没认对，请输入验证码。" : "电脑没认出这张验证码，请输入验证码。");
  }
  const code = $("#rl-code");
  if (code) { code.value = ""; reloginCodeReady(); if (typeof code.focus === "function") code.focus(); }
}

/* 所有「登录 / 重新登录」入口走这里：登录过又失效（含已转人工）走重新登录，
 * 从没登录过的走登录表单。 */
function loginEntry() {
  const login = S.login || {};
  if (login.result === "expired" || login.handoff) { openRelogin(); return; }
  openLogin();
}

/* 打开对话框：按当前情况落到对应的第一步。计划来不及时直接说明，不开表单 */
function openRelogin() {
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
function openLogin() {
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
function reloginPickWay(way) {
  if (!S.relogin || !S.relogin.open) return;
  S.relogin.way = way === "browser" ? "browser" : "here";
  reloginStep("login");
}

/* 「打开学校登录页」：交给浏览器登录那条老路，对话框停在 lgwait 等它回来 */
function reloginOpenSchoolPage() {
  reloginStep("lgwait");
  watchBrowserLogin();
  doLogin();
}

function closeRelogin() {
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
  if (live && flowId && !reloginAutoLive(flowId)) api("relogin_cancel", flowId).catch(() => {});
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
  /* 程序自己发起的刷新（U2/U3）：列表已有内容就走后台轮，失败不清列表和勾选；
   * 列表空着（常常正是因为登录失效才拉不到列表）走前台轮，才有骨架和错误空态可看。
   * 与 controllers/plan.js 浏览器登录成功后的判定同一口径。 */
  if (typeof refresh === "function") refresh(true, S.items.length ? { background: true } : undefined);
}

/* 后端推来的这一场进度（与手机同一份 public_state）：只在对话框开着时接管画面 */
function receiveReloginState(payload) {
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
  /* 顶栏「自动登录中…」：这一场是电脑自动发起的、还在进行就亮，结束或转人工就收
   * （架构方案 4.3；转人工以后要让「登录已失效」和重新登录入口回来） */
  const auto = String(data.origin || "") === "auto" && !!data.live && !handoff
    && !(S.login && S.login.result === "valid");   /* 学校已确认有效，旧快照重放不再亮 */
  if (auto !== !!S.autoLogin) {
    S.autoLogin = auto;
    paintLogin();
    /* 横幅读 S.login.view（paintLogin 刚按 autoLogin 重算过）：转人工、静默失败时
     * 失效横幅要当场回来，不能等下一次 check。 */
    paintBanners();
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

function wireRelogin() {
  const on = (id, fn) => {
    const el = $("#" + id);
    if (el && el.addEventListener) el.addEventListener("click", fn);
  };
  on("btn-rl-auto", () => { void autoReloginOnce(); });
  on("btn-lg-next", submitReloginForm);
  on("btn-rl-code", () => { void submitReloginCode(); });
  on("btn-rl-browser", () => { closeRelogin(); doLogin(); });
  on("btn-bad-browser", () => { closeRelogin(); doLogin(); });
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
