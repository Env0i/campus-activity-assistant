import { helpStatus } from "./view-help.js";
import { render } from "./actions-render.js";
import { paintBanners } from "./view-banners.js";
import { OcrPanel } from "../components/state-ocr.js";
import { setRowOpen } from "../components/state-row.js";
import { paintOcrDownload } from "../components/view-ocr.js";
import { paintFeishuRow } from "./view-feishu.js";

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
  paintFeishuRow(true);   /* 打开时对齐已保存的地址；之后的输入不被重画覆盖 */
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
  paintFeishuRow(false);
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
  /* 照原型 Main.dc.html:1968 撤回成功后直接关掉设置抽屉（交由顶部横幅与运行记录说明），并把焦点还给设置按钮 */
  closeSettings(true);
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


/* 飞书提醒：保存只写 config.json 的 feishu_webhook（后端合并写，读不出就拒绝）；
 * 发测试消息测的是输入框里这条地址，成功和失败原因都由后端给，这里只负责就地显示。 */
async function saveFeishu() {
  const input = $("#feishu-url");
  const url = input ? String(input.value || "").trim() : "";
  let result = null;
  try {
    result = await api("save_feishu_webhook", url);
  } catch (err) {
    result = { ok: false, text: "地址没有保存：" + msg(err) };
  }
  if (result && result.ok) S.feishuWebhook = String(result.url || "");
  S.feishuNote = { text: String((result && result.text) || "地址没有保存。"),
                   tone: result && result.ok ? "ok" : "warn" };
  paintFeishuRow(false);
  if (result && result.ok) addLog("飞书提醒地址已保存");
}

function wireFeishu() {
  const save = $("#btn-feishu-save");
  if (save) save.addEventListener("click", () => { void saveFeishu(); });
  const test = $("#btn-feishu-test");
  if (test) test.addEventListener("click", () => { void testFeishu(); });
}

async function testFeishu() {
  const input = $("#feishu-url");
  const url = input ? String(input.value || "").trim() : "";
  S.feishuNote = { text: "正在发测试消息…", tone: "ok" };
  paintFeishuRow(false);
  let result = null;
  try {
    result = await api("test_feishu_webhook", url);
  } catch (err) {
    result = { ok: false, text: "测试消息没发出去：" + msg(err) };
  }
  S.feishuNote = { text: String((result && result.text) || "测试消息没发出去。"),
                   tone: result && result.ok ? "ok" : "warn" };
  paintFeishuRow(false);
  if (result && result.ok) addLog("飞书提醒测试消息已发出");
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
       * 展开时藏句内链接钮（TM10，原型 canWithdraw 含 !termsWAsk，Main:2491/2492） */
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
  wireOcrControls();
  wireChecklistAndProgram();
  wireFeishu();
}

function wireOcrControls() {
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

function wireChecklistAndProgram() {
  const reloginOcrStep = $("#btn-relogin-ocr-step");
  if (reloginOcrStep) {
    reloginOcrStep.addEventListener("click", () => {
      if (reloginOcrStep.dataset.action === "enable") {
        void enableOcr();
        return;
      }
      setRowOpen("ocr", true);
      if (window.PhonePanel && typeof window.PhonePanel.paint === "function") window.PhonePanel.paint();
      else paintOcrDownload();
      const ocrSec = $("#set-ocr");
      if (ocrSec && ocrSec.scrollIntoView) ocrSec.scrollIntoView({ block: "start" });
      const dlBtn = $("#btn-ocr-download");
      const target = (dlBtn && !dlBtn.hidden) ? dlBtn : $("#btn-ocr-row-toggle");
      if (target && target.focus) target.focus();
    });
  }
  const updateToggle = $("#btn-update-row-toggle");
  if (updateToggle) {
    updateToggle.addEventListener("click", () => {
      S.updateOpen = !S.updateOpen;
      if (typeof paintUpdate === "function") paintUpdate();
    });
  }
  const feishuToggle = $("#btn-feishu-toggle");
  if (feishuToggle) {
    feishuToggle.addEventListener("click", () => {
      S.feishuOpen = !S.feishuOpen;
      paintFeishuRow(false);
    });
  }
  [
    ["#btn-dismiss-ocr-note", () => { OcrPanel.note = ""; paintOcrDownload(); }],
    ["#btn-dismiss-credential-note", () => { if (window.PhonePanel) { window.PhonePanel.credNote = ""; window.PhonePanel.paint(); } }],
    ["#btn-dismiss-feishu-note", () => { S.feishuNote = null; paintFeishuRow(false); }],
    ["#btn-dismiss-help-status", () => helpStatus("")],
  ].forEach((pair) => {
    const btn = $(pair[0]);
    if (btn) btn.addEventListener("click", pair[1]);
  });
  const retryBtn = $("#btn-list-refresh-retry");
  if (retryBtn) retryBtn.addEventListener("click", () => refresh(false));
  const banners = $("#banners");
  if (banners) banners.addEventListener("click", (e) => {
    if (e.target && e.target.closest && e.target.closest('[data-act="banner-collapse"]')) {
      S.collapsedBanner = S.bannerTopKey || "";
      paintBanners();
      if (typeof paintClockStatus === "function") paintClockStatus();
      if (typeof window.paintLogin === "function") window.paintLogin();
    }
  });
}
