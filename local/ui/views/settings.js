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

function ocrFeature() {
  if (window.PhonePanel && typeof window.PhonePanel.feature === "function") {
    const row = window.PhonePanel.feature("relogin_ocr");
    if (row && Object.keys(row).length) return row;
  }
  const adv = (typeof S !== "undefined" && S.advanced) || {};
  return ((adv.features || {}).relogin_ocr) || {};
}

/* 验证码识别（settings-gap 二、OC01–OC15，原型 ocrView，Main.dc.html 1399–1411）。
 * 反馈就地写在这一节里（OC15），不走抽屉底部那一行；组件位置只走电脑端专用接口（B3），取不到就不显示。
 * note / error 由本文件的动作和 phone.js 里 relogin_ocr 的下载、取消、导入三处写入。 */
const OcrPanel = {
  busy: false,
  note: "",
  error: "",
  location: null,
  lastDownload: "",
};

/* 状态机：downloading / verifying 下载中 / broken 已装但加载失败（原型没画，保留，OC14）/
 * on 已启用 / off 已装好还没启用（R3，冲突 6）/ missing 没装 / checking 检查中（组件事务锁被占，还没结论，不是没装）。 */
function ocrPhase(feature) {
  const dl = String(((feature && feature.download) || {}).state || "");
  if (dl === "downloading") return "downloading";
  if (dl === "verifying") return "verifying";
  if (feature && String(feature.status || "") === "checking") return "checking";
  if (feature && String(feature.status || "") === "outdated") return "outdated";
  if (feature && String(feature.status || "") === "failed") return "broken";
  if (feature && feature.ready) return "on";
  if (feature && feature.available) return "off";
  return "missing";
}

function ocrShow(selector, visible) {
  const el = $(selector);
  if (el) el.hidden = !visible;
  return el;
}

function ocrText(selector, text) {
  const el = $(selector);
  if (el) {
    el.textContent = String(text || "");
    el.hidden = !text;
  }
  return el;
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

/* 标题行右侧二选一：没装放「下载并安装」（失败后「重新下载」）、已装没启用放「启用」、下载中放「取消下载 / 校验中…」、
 * 已启用放 chip；失败后才露出「导入已下载的组件包」那句链接（OC12）。 */
function paintOcrDownload() {
  const feature = ocrFeature();
  const download = feature.download || {};
  const dlState = String(download.state || "");
  const phase = ocrPhase(feature);
  const downloading = phase === "downloading" || phase === "verifying";
  const loading = downloading || phase === "checking";
  const failed = dlState === "failed";
  const busy = !!OcrPanel.busy || !!(window.PhonePanel && window.PhonePanel.busy);
  const version = String(feature.package_version || "");

  /* OC15：亲眼看着下载 → 校验 → 装好，才说一句「已安装并启用」；刷新到旧的 installed 不重复说 */
  const prev = OcrPanel.lastDownload;
  if ((prev === "downloading" || prev === "verifying") && dlState === "installed") {
    OcrPanel.note = "验证码识别组件已安装并启用。";
  }
  OcrPanel.lastDownload = dlState;

  /* OC02：chip 只有两处——已启用（ok 色）、已装没启用（中性，贴标题）；加载失败原型没有，保留（OC14） */
  const chip = $("#ocr-feature-status");
  if (chip) {
    const text = phase === "on" ? "已启用"
      : (phase === "outdated" ? "需要更新" : (phase === "broken" ? "加载失败" : ""));
    chip.hidden = !text;
    chip.textContent = text;
    chip.className = "ph-st" + (phase === "on" ? " ok" : (text ? " warn" : ""));
    chip.dataset.state = phase === "on" ? "ready" : String(feature.status || "missing");
  }
  ocrShow("#ocr-title-chip", phase === "off");
  const downloadBtn = $("#btn-ocr-download");
  if (downloadBtn) {
    downloadBtn.hidden = phase !== "missing" && phase !== "outdated";
    downloadBtn.disabled = busy;
    downloadBtn.textContent = phase === "outdated" ? "更新组件"
      : (failed ? "重新下载" : "下载并安装");
  }
  /* 「启用」直接调 enable_advanced_feature（B2），不再打开导入弹窗（OC08、冲突 6） */
  const enable = $("#btn-ocr-enable");
  if (enable) {
    enable.hidden = phase !== "off";
    enable.disabled = busy;
  }
  const reimport = $("#btn-ocr-feature-install");
  if (reimport) {
    reimport.hidden = phase !== "broken";
    reimport.disabled = busy;
    reimport.textContent = "重新导入组件包";
  }
  const cancel = $("#btn-ocr-cancel");
  if (cancel) {
    cancel.hidden = !downloading;
    cancel.disabled = busy || phase === "verifying";
    cancel.textContent = phase === "verifying" ? "校验中…" : "取消下载";
  }

  /* OC03：lead 随状态变，版本号用 package_version（读不到就不写版本，不编） */
  const line = $("#ocr-download-state");
  if (line) {
    line.textContent = phase === "on"
      ? (version ? "版本 " + version + "。" : "") + "电脑会自己认验证码，连续认错 3 次再转给手机手动输入。"
      : (phase === "off"
        ? "已装好" + (version ? "（版本 " + version + "）" : "")
          + "，还没启用。启用后，登录失效时电脑会自己认验证码；配合“登录恢复”里的账号密码，就能无人值守自动登录。"
        : (phase === "outdated"
          ? "主程序已升级，验证码识别组件需要随新版本更新。点「更新组件」重新装一份，登录恢复里的账号密码不用重填。"
          : "登录失效时，电脑能自己认验证码，配合“登录恢复”里的账号密码就能全自动登录。没装或认不出来时，由你在手机上手动输入。"));
  }
  /* OC11：红条拼「下载没有完成：原因，可以重试。」，拼法同手机访问（phone.js downloadFailText）；
   * 更新失败后状态回到「需要更新」，原因同样要看得见，不能只剩一个「更新组件」按钮 */
  const failText = failed && (phase === "missing" || phase === "outdated")
    ? (typeof downloadFailText === "function" ? downloadFailText(download)
      : String(download.text || "下载没有完成，可以重试。")) : "";
  ocrText("#ocr-download-error", OcrPanel.error || failText);

  ocrShow("#ocr-missing", phase === "missing");
  /* 更新失败后停在 outdated，手动下载导入是唯一的兜底，入口不能跟着「没装」一起收起来 */
  ocrShow("#ocr-import-line", (phase === "missing" || phase === "outdated") && failed);
  ocrShow("#ocr-off-note", phase === "off");
  ocrShow("#ocr-loading", loading);

  /* OC10：进度块左「正在下载验证码识别组件」、右「9.5 / 31.6 MB」，校验时「下载完成，正在校验组件…」；进度条墨色，复用 .ph-bar */
  const total = Number(download.total_bytes || 0);
  const done = Number(download.downloaded || 0);
  const pct = phase === "verifying" ? 100
    : (total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0);
  ocrText("#ocr-prog-text", phase === "checking" ? "正在检查组件…"
    : (phase === "verifying" ? "下载完成，正在校验组件…" : "正在下载验证码识别组件"));
  const num = $("#ocr-prog-num");
  if (num) {
    num.textContent = phase === "downloading" && total > 0
      ? (done / 1048576).toFixed(1) + " / " + (total / 1048576).toFixed(1) + " MB" : "";
  }
  const bar = $("#ocr-component-progress");
  if (bar) bar.setAttribute("aria-valuenow", String(pct));
  const fill = $("#ocr-prog-fill");
  if (fill && fill.style) fill.style.width = pct + "%";

  /* OC13：取消后回到没装态，一句「下载已取消，没有装任何东西。」由快照的 cancelled 派生 */
  ocrText("#ocr-note", OcrPanel.note
    || (phase === "missing" && dlState === "cancelled" && !OcrPanel.error && !failText
      ? "下载已取消，没有装任何东西。" : ""));

  /* OC06 / OC07：没装时「会装到」，装好后「装在」+「打开所在文件夹」 */
  const loc = OcrPanel.location;
  ocrShow("#ocr-loc-before", phase === "missing" && !!loc);
  ocrShow("#ocr-loc-after", phase !== "missing" && !loading && !!loc);
  ["#ocr-loc-before", "#ocr-loc-after"].forEach((sel) => {
    const box = $(sel);
    const code = $(sel + "-path");
    if (box && loc) box.title = loc.path || loc.short;
    if (code) code.textContent = loc ? loc.short : "";
  });
  const openLoc = $("#btn-ocr-open-loc");
  if (openLoc) openLoc.disabled = busy;
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
  if (ocrDownload && window.PhonePanel) {
    ocrDownload.addEventListener("click", () => void window.PhonePanel.downloadComponent("relogin_ocr"));
  }
  const ocrCancel = $("#btn-ocr-cancel");
  if (ocrCancel && window.PhonePanel) {
    ocrCancel.addEventListener("click", () => void window.PhonePanel.cancelComponent("relogin_ocr"));
  }
  const ocrEnable = $("#btn-ocr-enable");
  if (ocrEnable) ocrEnable.addEventListener("click", () => void enableOcr());
  /* OC12：导入入口只有失败后的句内链接（和加载失败时标题行的「重新导入组件包」），都打开导入弹窗 */
  ["#btn-ocr-import", "#btn-ocr-feature-install"].forEach((sel) => {
    const btn = $(sel);
    if (btn) btn.addEventListener("click", () => {
      if (window.PhonePanel) window.PhonePanel.openComponents("relogin_ocr");
    });
  });
  const ocrOpenLoc = $("#btn-ocr-open-loc");
  if (ocrOpenLoc) ocrOpenLoc.addEventListener("click", () => void openOcrDir());
}
