/* 设置抽屉（决策 011 修订、014）：右侧抽屉，顶部分组跳转（高级功能 / 登录 / 程序）。
 * 需要动手的恢复动作都在这里：手机访问、验证码识别、保存的账号与自动登录、关闭窗口方式、
 * 版本与更新、本机数据、条款与隐私（含撤回同意）。帮助只做解释。
 * 这里只读后端快照（PhonePanel.state.advanced / bootstrap），不自己推断组件或条款状态。 */
function settingsOpen() {
  /* 以自己记的开合为准：Esc 逐层关闭时不能把「没打开」误判成打开、去抢别人的焦点 */
  return !!S.settingsOpen;
}

/* 关闭窗口时：每次询问 / 最小化 / 隐藏到后台 / 直接退出（写 ui.json 的 window.close_action） */
function paintClosePref() {
  const select = $("#close-pref");
  if (!select) return;
  const action = String(((S.prefs || {}).window || {}).close_action || "");
  select.value = ["minimize", "hide", "exit"].indexOf(action) >= 0 ? action : "ask";
}

/* 条款与隐私：同意了哪一版、什么时候；没同意时写清停用了什么。计划运行中不能撤回。
 * 已同意句照原型（TM10，Main:2490）：「你在 MM-DD HH:mm 同意了 <版本> 版。用户协议、隐私政策
 * 和开源许可的全文都可以在这里查看。」，句尾跟句内链接钮「撤回同意」（TM10，Main:2492）。 */
/* 确认条开合的唯一位：点「撤回同意」置真、点「先不撤回」/「确认撤回」/关抽屉置假。
 * paintTermsRow 只读它——展开时藏句内链接钮（TM10，原型 canWithdraw 含 !termsWAsk，Main:2491），
 * 避免句子还挂着「撤回同意」、下面却已展开确认条的两处状态打架。 */
let termsWithdrawAskOpen = false;

/* 同意时间拼「MM-DD HH:mm」（TM10，格式同 views/update.js 的 formatCheckedAt，UP03 定的连字符）。
 * 后端存的是「YYYY-MM-DD HH:MM:SS」文本（ui.json terms_accepted_at），直接截取月日时分，
 * 不 new Date 解析；格式对不上时退回原文，为空再退「之前」。 */
function formatAcceptedAt(stamp) {
  const s = String(stamp || "");
  return /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(s) ? s.slice(5, 16) : "";
}

function paintTermsRow() {
  const line = $("#settings-terms-state");
  const withdraw = $("#btn-terms-withdraw");
  if (!line || !withdraw) return;
  const terms = S.terms || {};
  const accepted = typeof termsAccepted === "function" ? termsAccepted() : false;
  line.textContent = accepted
    ? "你在 " + (formatAcceptedAt(terms.acceptedAt) || terms.acceptedAt || "之前")
      + " 同意了 " + terms.version + " 版。用户协议、隐私政策和开源许可的全文都可以在这里查看。"
    : "还没有同意这一版：登录、登录检查、自动登录、刷新活动和开始计划都已停用。";
  withdraw.hidden = !accepted || termsWithdrawAskOpen;
  withdraw.disabled = !!S.busy;
  withdraw.title = S.busy ? "计划运行中不能撤回，先停止计划" : "撤回同意（保存的账号和登录信息不会删除）";
  /* 原因也写在句子下方（TM11，原型 Main:2490 withdrawBlocked 注）：悬停提示在触控板和键盘操作里看不到。 */
  const why = $("#terms-withdraw-why");
  if (why) why.hidden = !(accepted && S.busy);
}
