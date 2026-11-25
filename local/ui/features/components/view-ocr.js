/* 验证码识别一节的视图层：这一行特有的说明句、装好未启用的那句、启用按钮与展开区里的
 * 导入兜底；标题行、进度条、红条、位置这些共有的部分交给 features/components/view-row.js。
 * 只读写 DOM 和面板字段，不发桥接请求。 */

import { OcrPanel, ocrFeature, ocrPhase } from "./state-ocr.js";
import { componentState } from "./state-machine.js";
import { downloadFailText } from "./state.js";
import { retryWaitBase } from "../phone-access/state.js";
import { paintComponentRow } from "./view-row.js";



export function ocrShow(selector, visible) {
  const el = $(selector);
  if (el) el.hidden = !visible;
  return el;
}



export function ocrText(selector, text) {
  const el = $(selector);
  if (el) {
    el.textContent = String(text || "");
    el.hidden = !text;
  }
  return el;
}



/* 验证码识别这一行的元素 id：按钮位里放的是下载、启用、取消、重试四只，同一时刻最多看得见一只；
 * 状态句、进度条、小字、红条与展开区的落点也在这里登记一次，画法在 view-row.js。 */
const OCR_ROW_SPEC = {
  kind: "ocr",
  statusId: "#ocr-feature-status",
  statusTextId: "#ocr-feature-status-text",
  buttons: {
    install: "#btn-ocr-download",
    enable: "#btn-ocr-enable",
    cancel: "#btn-ocr-cancel",
    retry: "#btn-ocr-retry",
  },
  barId: "#ocr-loading",
  fillId: "#ocr-prog-fill",
  noteId: "#ocr-note",
  errorId: "#ocr-download-error",
  detailId: "#ocr-row-detail",
  toggleId: "#btn-ocr-row-toggle",
  collapseLabel: "收起验证码识别详情",
  expandLabel: "展开验证码识别详情",
  missingId: "#ocr-missing",
  importLineId: "#ocr-import-line",
  locIds: ["#ocr-loc-before", "#ocr-loc-after"],
  openLocId: "#btn-ocr-open-loc",
};



/* 点「安装这份」到快照刷新完成为止，快照还是导入前的旧状态：这段时间不画旧红条与导入行；
 * 亲眼看着下载 → 校验 → 装好，才说一句「已安装并启用」，刷新到旧的 installed 不重复说。 */
function trackInstall(dlState, installing) {
  const prev = OcrPanel.lastDownload;
  if ((prev === "downloading" || prev === "verifying") && dlState === "installed" && !installing) {
    OcrPanel.note = "验证码识别组件已安装并启用。";
  }
  OcrPanel.lastDownload = dlState;
}



/* 说明句随状态变，版本号用 package_version（读不到就不写版本，不编） */
function leadOf(phase, version) {
  if (phase === "on") {
    return (version ? "版本 " + version + "。" : "")
      + "电脑会自己认验证码，连续认错 3 次转给手机手动输。";
  }
  if (phase === "off") {
    return "已装好" + (version ? "（版本 " + version + "）" : "")
      + "，还没启用。启用后，登录失效时电脑会自己认验证码；配合“登录恢复”里的账号密码，就能无人值守自动登录。";
  }
  if (phase === "outdated") {
    return "主程序已升级，验证码识别组件需要随新版本更新。点「更新组件」重新装一份，登录恢复里的账号密码不用重填。";
  }
  return "登录失效时，电脑能自己认验证码，配合“登录恢复”里的账号密码就能全自动登录。没装或认不出来时，由你在手机上手动输入。";
}



/* 红条只讲下载失败：拼法同手机访问（./state.js downloadFailText）。文件本身不完整那句
 * 走标题行下的小字，不再挤进红条。 */
function failTextOf(phase, download, failed, installing) {
  if (installing || !failed) return "";
  if (phase !== "missing" && phase !== "outdated" && phase !== "broken") return "";
  return typeof downloadFailText === "function" ? downloadFailText(download)
    : String(download.text || "下载没有完成，可以重试。");
}



export function paintOcrDownload() {
  const feature = ocrFeature();
  const download = feature.download || {};
  const dlState = String(download.state || "");
  const phase = ocrPhase(feature);
  const installing = !!(window.PhonePanel && window.PhonePanel.installing
    && window.PhonePanel.installing.relogin_ocr);
  const failed = dlState === "failed";
  const busy = !!OcrPanel.busy || !!(window.PhonePanel && window.PhonePanel.busy);
  const version = String(feature.package_version || "");
  const facts = componentState(feature, {
    busy: busy, installing: installing, location: OcrPanel.location,
    retryWaitBase: retryWaitBase("relogin_ocr"),
  });
  trackInstall(dlState, installing);

  const failText = failTextOf(phase, download, failed, installing);
  /* 文件不完整那句由状态行推导放在标题行下的小字里（红字），红条只讲下载失败 */
  paintComponentRow(OCR_ROW_SPEC, facts, {
    /* 安装中状态机不改状态，只有收尾时才知道；标题行这一档要自己说出来 */
    phase: installing ? "installing" : phase,
    version: version,
    note: OcrPanel.note,
    componentError: installing ? "" : (OcrPanel.error || failText),
  });

  const line = $("#ocr-download-state");
  if (line) line.textContent = leadOf(phase, version);
  const dismissBtn = $("#btn-dismiss-ocr-note");
  if (dismissBtn) dismissBtn.hidden = !OcrPanel.note;
  /* 识别行特有：装好未启用时的说明块 */
  ocrShow("#ocr-off-note", phase === "off");
}
