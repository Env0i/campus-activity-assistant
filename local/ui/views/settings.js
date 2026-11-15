/* 设置抽屉（决策 011 修订、014）：右侧抽屉，顶部分组跳转（高级功能 / 登录 / 程序）。
 * 需要动手的恢复动作都在这里：手机访问、验证码识别、保存的账号与自动登录、关闭窗口方式、
 * 版本与更新、本机数据、条款与隐私（含撤回同意）。帮助只做解释。
 * 这里只读后端快照（PhonePanel.state.advanced / bootstrap），不自己推断组件或条款状态。 */
function settingsOpen() {
  /* 以自己记的开合为准：Esc 逐层关闭时不能把「没打开」误判成打开、去抢别人的焦点 */
  return !!S.settingsOpen;
}

function openSettings(section) {
  const drawer = $("#settings");
  if (!drawer) return;
  if (typeof closeStatusCards === "function") closeStatusCards(false);
  const wasOpen = !!S.settingsOpen;
  drawer.hidden = false;
  S.settingsOpen = true;
  $("#btn-settings").setAttribute("aria-expanded", "true");
  if (!wasOpen && window.PhonePanel && typeof window.PhonePanel.refresh === "function") {
    /* 打开时重取一次手机访问与高级功能快照：组件、通道、账号状态都以后端为准 */
    try { window.PhonePanel.refresh(); } catch (error) { /* 面板刷新失败不影响抽屉本身 */ }
  }
  paintSettings();
  if (section) openSettingsSection(section);
  else if (!wasOpen) {
    const close = $("#btn-settings-close");
    if (close && close.focus) close.focus();
  }
}

/* 跳到某一组：标题带 scroll-margin，不被顶部分组按钮遮住 */
function openSettingsSection(section) {
  if (!settingsOpen()) { openSettings(section); return; }
  const head = $("#set-" + section);
  if (!head) return;
  if (head.scrollIntoView) head.scrollIntoView({ block: "start" });
  if (head.focus) head.focus();
}

function closeSettings(restoreFocus) {
  const drawer = $("#settings");
  if (!drawer || !S.settingsOpen) return;
  S.settingsOpen = false;
  drawer.hidden = true;
  $("#btn-settings").setAttribute("aria-expanded", "false");
  const box = $("#terms-withdraw-confirm");
  if (box) box.hidden = true;
  termsWithdrawAskOpen = false; /* 关抽屉强制收起确认条（TM10/TM11 既有行为），链接钮显隐由下次 paintTermsRow 接管 */
  if (restoreFocus && $("#btn-settings").focus) $("#btn-settings").focus();
}

function paintSettings() {
  paintClosePref();
  paintTermsRow();
  paintOcrDownload();
  if (!OcrPanel.location) void ocrLoadLocation().then(() => { if (OcrPanel.location) paintOcrDownload(); });
}

/* 关闭窗口时：每次询问 / 最小化 / 隐藏到后台 / 直接退出（写 ui.json 的 window.close_action） */
function paintClosePref() {
  const select = $("#close-pref");
  if (!select) return;
  const action = String(((S.prefs || {}).window || {}).close_action || "");
  select.value = ["minimize", "hide", "exit"].indexOf(action) >= 0 ? action : "ask";
}

function saveClosePref(value) {
  const windowPrefs = Object.assign({}, (S.prefs || {}).window || {});
  windowPrefs.close_action = value === "ask" ? "" : value;
  savePrefs({ window: windowPrefs });
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

async function withdrawTerms() {
  const box = $("#terms-withdraw-confirm");
  let result = null;
  try {
    result = await api("withdraw_terms");
  } catch (err) {
    result = { ok: false, text: "撤回没有完成：" + msg(err) };
  }
  termsWithdrawAskOpen = false;
  if (box) box.hidden = true;
  if (!result || !result.ok) {
    helpStatus(String((result && result.text) || "撤回没有完成。"), "warn");
    paintTermsRow(); /* 失败也收起确认条：句内「撤回同意」链接钮的显隐要跟上 */
    return;
  }
  /* 回执里的条款快照就是后端事实：门禁立刻按它关上，界面不另算 */
  if (typeof ingestTerms === "function") ingestTerms(result.terms);
  addLog("已撤回使用条款同意；保存的账号和登录信息没有删除");
  helpStatus("已撤回同意。重新同意后可以继续登录和报名。", "info");
  paintTermsRow();
  paintBanners();
  render();
}

/* OC06 / OC07：位置只问一次就记住（数据目录这次运行里不会变）；没拿到就下次打开抽屉再问 */
async function ocrLoadLocation() {
  if (OcrPanel.location) return;
  try {
    const loc = await api("advanced_component_location", "relogin_ocr");
    OcrPanel.location = (loc && loc.ok && loc.short)
      ? { path: String(loc.path || ""), short: String(loc.short) } : null;
  } catch (err) {
    OcrPanel.location = null;
  }
}

/* OC08：标题行「启用」——组件已在本机、只缺启用位，调 B2，不打开导入弹窗 */
async function enableOcr() {
  if (OcrPanel.busy) return;
  OcrPanel.busy = true;
  OcrPanel.error = "";
  OcrPanel.note = "";
  paintOcrDownload();
  let result = null;
  try {
    result = await api("enable_advanced_feature", "relogin_ocr");
  } catch (err) {
    result = { ok: false, text: "没有启用，请重试。" };
  } finally {
    OcrPanel.busy = false;
  }
  if (result && result.ok) OcrPanel.note = "验证码识别已启用。";
  else OcrPanel.error = String((result && result.text) || "没有启用，请重试。");
  if (window.PhonePanel && typeof window.PhonePanel.refresh === "function") await window.PhonePanel.refresh();
  else paintOcrDownload();
}

/* OC07：产品里直接用资源管理器打开，成功不说话，失败才在本节红条里说 */
async function openOcrDir() {
  let result = null;
  try {
    result = await api("open_advanced_component_dir", "relogin_ocr");
  } catch (err) {
    result = { ok: false };
  }
  if (result && result.ok) return;
  OcrPanel.error = String((result && result.text) || "打不开所在文件夹。");
  paintOcrDownload();
}

function wireSettings() {
  const close = $("#btn-settings-close");
  if (close) close.addEventListener("click", () => closeSettings(true));
  const nav = document.querySelector(".set-nav");
  if (nav && nav.addEventListener) {
    nav.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-sec]");
      if (btn) openSettingsSection(btn.dataset.sec);
    });
  }
  const pref = $("#close-pref");
  if (pref) pref.addEventListener("change", (event) => saveClosePref(event.target.value));
  const withdraw = $("#btn-terms-withdraw");
  if (withdraw) {
    withdraw.addEventListener("click", () => {
      if (S.busy) return;
      /* 只展开确认条，不发 withdraw_terms（TM10/TM11：点「确认撤回」才动手）；
         展开时藏句内链接钮（TM10，原型 canWithdraw 含 !termsWAsk，Main:2491/2492） */
      termsWithdrawAskOpen = true;
      $("#terms-withdraw-confirm").hidden = false;
      paintTermsRow();
    });
  }
  const cancel = $("#btn-terms-withdraw-cancel");
  if (cancel) cancel.addEventListener("click", () => {
    termsWithdrawAskOpen = false;
    $("#terms-withdraw-confirm").hidden = true;
    paintTermsRow();
  });
  const confirm = $("#btn-terms-withdraw-confirm");
  if (confirm) confirm.addEventListener("click", () => { void withdrawTerms(); });
  const ocrDownload = $("#btn-ocr-download");
  if (ocrDownload) {
    /* 手机面板已搬成模块：绑定发生在普通脚本阶段，模块那时还没执行，所以把
       「window.PhonePanel 在不在」的判断挪进点击处理里（写法同下面导入入口那处）。 */
    ocrDownload.addEventListener("click", () => {
      if (window.PhonePanel) void window.PhonePanel.downloadComponent("relogin_ocr");
    });
  }
  const ocrCancel = $("#btn-ocr-cancel");
  if (ocrCancel) {
    ocrCancel.addEventListener("click", () => {
      if (window.PhonePanel) void window.PhonePanel.cancelComponent("relogin_ocr");
    });
  }
  const ocrEnable = $("#btn-ocr-enable");
  if (ocrEnable) ocrEnable.addEventListener("click", () => void enableOcr());
  /* OC12：导入入口只剩下载失败后的句内链接，点了打开导入弹窗 */
  const ocrImport = $("#btn-ocr-import");
  if (ocrImport) ocrImport.addEventListener("click", () => {
    if (window.PhonePanel) window.PhonePanel.openComponents("relogin_ocr");
  });
  const ocrOpenLoc = $("#btn-ocr-open-loc");
  if (ocrOpenLoc) ocrOpenLoc.addEventListener("click", () => void openOcrDir());
}
