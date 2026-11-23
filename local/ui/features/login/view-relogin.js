/* 重新登录对话框的 DOM 呈现：只读写页面与状态，不发桥接请求、不调编排层的函数。 */

import { RELOGIN_ALL_ACTS, reloginActs, reloginCapSub, reloginFromLogin, reloginWay } from "./state-relogin.js";
import { autoLoginCredential } from "../plan/state-draft.js";

export function reloginDialog() {
  return $("#dlg-relogin");
}

export function reloginHead(step, text) {
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

/* 登录那一屏：选中卡、表单、两组说明和警示语都跟着方式切（原型 lgWay） */
export function reloginPaintWay() {
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
export function reloginNextReady() {
  const user = String(($("#rl-user") || {}).value || "").trim();
  const pass = String(($("#rl-pass") || {}).value || "");
  const btn = $("#btn-lg-next");
  if (btn) btn.disabled = !user || !pass;
}

/* 密码框右侧的眼睛：点一下在明文和圆点之间切（原型 lgShow） */
export function reloginTogglePass() {
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

export function reloginCodeReady() {
  const code = String(($("#rl-code") || {}).value || "").trim();
  const btn = $("#btn-rl-code");
  if (btn) btn.disabled = !/^[0-9A-Za-z]{4}$/.test(code);
}

/* 错误条只有一条，固定在正文最上面（原型 10-外框）：传空串即收起 */
export function reloginError(text) {
  const err = $("#rl-err");
  if (!err) return;
  err.textContent = String(text || "");
  err.hidden = !text;
}

export function reloginStep(step, text) {
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
export function reloginResetForm() {
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

/* 验证码那一屏：图、已试次数、转人工提示都在这里画，打开对话框和收事件共用一份 */
export function reloginShowChallenge(data) {
  const payload = data || {};
  S.relogin.challengeId = String(payload.challenge_id || "");
  const img = $("#rl-cap-img");
  if (img) img.src = String(payload.image || "");
  const tries = $("#rl-cap-tries");
  if (tries) tries.textContent = Number(payload.attempts) > 0 ? "已经试过 " + Number(payload.attempts) + " 次，换了一张新图。" : "";
  reloginStep("cap");
  /* 电脑自动发起的一场认不出来就交给用户：只在转人工那一张显示原因，之后换图只留已试次数 */
  const hasHandoffAt = payload.handoff_attempts !== null && payload.handoff_attempts !== undefined;
  const handoffAt = hasHandoffAt ? Number(payload.handoff_attempts) : null;
  if (payload.handoff && handoffAt !== null && Number(payload.attempts || 0) === handoffAt) {
    reloginError(handoffAt >= 3 ? "自动识别 3 次没认对，请输入验证码。" : "电脑没认出这张验证码，请输入验证码。");
  }
  const code = $("#rl-code");
  if (code) { code.value = ""; reloginCodeReady(); if (typeof code.focus === "function") code.focus(); }
}

export function reloginCase() {
  const cred = typeof autoLoginCredential === "function" ? autoLoginCredential() : {};
  if (cred.saved && cred.paused) return "bad";
  /* 保存过账号就直接进验证码步：装了识别也一样，后台已经在自动认，不再先问一次 */
  if (cred.saved) return "captcha";
  return "login";
}

/* 打码账号：后端的 credential 里有 username 才给（手机页同一条规则），没有就只说登录方式。 */
export function reloginMask() {
  const cred = typeof autoLoginCredential === "function" ? autoLoginCredential() : {};
  return String(cred.mask || "");
}

/* 打码背后的明文账号：只有「在这里输入」这条路要把它填回输入框。 */
export function reloginUser() {
  const cred = typeof autoLoginCredential === "function" ? autoLoginCredential() : {};
  return String(cred.username || "");
}
