/* 重新登录对话框里的纯推导：这个文件只按状态算出「该显示哪种情况、哪种方式、哪句话」，不碰 DOM、不发请求。 */

export const RELOGIN_PRIVACY_NOTE = "登录时，工具会替你勾选学校登录页上的《隐私协议》。";

export function reloginCapSub(mask) {
  return mask ? "账号 " + mask + " 和密码由电脑自动填写" : "账号和密码由电脑自动填写";
}

/* 从登录表单点进验证码的：副句要说密码已填好，底栏第一个按钮变「上一步」（原型 1694-1697） */
export function reloginFromLogin() {
  return !!(S.relogin && S.relogin.fromLogin);
}

/* 标题与副句照原型 rlView（Main.dc.html:1666-1698）：确认是「自动登录一次？」，
   验证码是「输入验证码」，登录表单是「登录学校账号」，自动登录中是「正在自动登录」。 */

export const RELOGIN_LOGIN_ACTS = {
  here: ["btn-rl-cancel", "btn-lg-next"],
  browser: ["btn-rl-cancel", "btn-lg-webopen"],
};

export const RELOGIN_ACTS = {
  confirm: ["btn-rl-cancel", "btn-rl-auto"],
  cap: ["btn-rl-browser", "btn-rl-cancel", "btn-rl-code"],
  bad: ["btn-bad-browser", "btn-bad-update"],
  lgwait: ["btn-rl-cancel"],
  msg: ["btn-rl-done"],
  wait: [],
};

export const RELOGIN_ALL_ACTS = ["btn-rl-browser", "btn-rl-cancel", "btn-rl-auto", "btn-bad-browser",
  "btn-bad-update", "btn-lg-back", "btn-lg-next", "btn-lg-webopen", "btn-rl-code", "btn-rl-done"];

export function reloginWay() {
  return S.relogin && S.relogin.way === "browser" ? "browser" : "here";
}

export function reloginActs(step) {
  if (step === "login") return RELOGIN_LOGIN_ACTS[reloginWay()] || RELOGIN_LOGIN_ACTS.here;
  /* 从登录表单点进来的验证码页：左边那个「改用浏览器登录」换成「上一步」（原型 1694-1697） */
  if (step === "cap" && reloginFromLogin()) return ["btn-lg-back", "btn-rl-cancel", "btn-rl-code"];
  return RELOGIN_ACTS[step] || [];
}

/* 后端的拒绝统一说人话；plan_late 单独一句「现在来不及」 */
export function reloginRefusal(result) {
  const data = result || {};
  if (data.error === "plan_late") {
    return "现在来不及重新登录：" + String(data.text || "有场次正在提交，或者离开放不到 100 秒。")
      + " 电脑能自动登录就会自动登录。";
  }
  return String(data.text || "这次没能开始登录，稍后再试。");
}
