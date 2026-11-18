import { render } from "./actions-render.js";
import { paintBanners } from "./view-banners.js";
import { OcrPanel } from "../components/state-ocr.js";
import { paintOcrDownload } from "../components/view-ocr.js";

export function openSettings(section) {
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
  refreshSettings();
  if (section) openSettingsSection(section);
  else if (!wasOpen) {
    const close = $("#btn-settings-close");
    if (close && close.focus) close.focus();
  }
}

/* 跳到某一组：标题带 scroll-margin，不被顶部分组按钮遮住 */
export function openSettingsSection(section) {
  if (!settingsOpen()) { openSettings(section); return; }
  const head = $("#set-" + section);
  if (!head) return;
  if (head.scrollIntoView) head.scrollIntoView({ block: "start" });
  if (head.focus) head.focus();
}

export function closeSettings(restoreFocus) {
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

function refreshSettings() {
  paintClosePref();
  paintTermsRow();
  paintOcrDownload();
  if (!OcrPanel.location) void ocrLoadLocation().then(() => { if (OcrPanel.location) paintOcrDownload(); });
}

function saveClosePref(value) {
  const windowPrefs = Object.assign({}, (S.prefs || {}).window || {});
  windowPrefs.close_action = value === "ask" ? "" : value;
  savePrefs({ window: windowPrefs });
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

export function wireSettings() {
  const manage = $("#btn-phone-manage");
  if (manage && manage.addEventListener) manage.addEventListener("click", () => {
    closeStatusCards(false);
    openSettings("adv");
  });
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
    /* 点击时检查手机面板是否可用；导入入口使用同样的判定。 */
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
