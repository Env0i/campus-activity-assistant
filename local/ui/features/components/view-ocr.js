/* 验证码识别一节的视图层：本节显隐与文案的小工具加这一行特有的 chip、启用、
 * 重新导入、说明与刚装好那句；组件线的共有部分交给 features/components/view-row.js。
 * 只读写 DOM 和面板字段，不发桥接请求。 */

import { OcrPanel, ocrFeature, ocrPhase } from "./state-ocr.js";
import { componentState } from "./state-machine.js";
import { paintComponentRow } from "./view-row.js";
import { downloadFailText } from "./state.js";



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



/* 验证码识别这一行的元素 id 与固定文字：共有部分由 features/components/view-row.js
 * 的 paintComponentRow 画，行与行的差别（下载文案等）由这里的 spec 常量与调用方
 * 算好的 texts 保留。 */
const OCR_ROW_SPEC = {
  installId: "#btn-ocr-download",
  cancelId: "#btn-ocr-cancel",
  missingId: "#ocr-missing",
  importLineId: "#ocr-import-line",
  loadingId: "#ocr-loading",
  progTextId: "#ocr-prog-text",
  progNumId: "#ocr-prog-num",
  progressBarId: "#ocr-component-progress",
  progFillId: "#ocr-prog-fill",
  errorId: "#ocr-download-error",
  cancelledNoteId: "#ocr-note",
  locIds: ["#ocr-loc-before", "#ocr-loc-after"],
  openLocId: "#btn-ocr-open-loc",
  downloadText: "正在下载验证码识别组件",
};



/* 识别行特有的部分：chip 只有两处——已启用（ok 色）、已装没启用（中性，贴标题）；
 * 加载失败原型没有，保留现状。「启用」直接调启用接口，不再打开导入弹窗。
 * 共有的组件线（主按钮、取消、没装块、导入兜底、进度块、位置两行、红条、取消句）
 * 由 paintComponentRow 画；红条与取消句两行规则不同，由这里算好传入。 */
export function paintOcrDownload() {
  const feature = ocrFeature();
  const download = feature.download || {};
  const dlState = String(download.state || "");
  const phase = ocrPhase(feature);
  /* 点「安装这份」到快照刷新完成为止，快照还是导入前的旧状态：这段时间不画旧红条
   * 与导入行，进度区说正在安装 */
  const installing = !!(window.PhonePanel && window.PhonePanel.installing
    && window.PhonePanel.installing.relogin_ocr);
  const failed = dlState === "failed";
  const busy = !!OcrPanel.busy || !!(window.PhonePanel && window.PhonePanel.busy);
  const version = String(feature.package_version || "");

  /* 亲眼看着下载 → 校验 → 装好，才说一句「已安装并启用」；刷新到旧的 installed 不重复说 */
  const prev = OcrPanel.lastDownload;
  if ((prev === "downloading" || prev === "verifying") && dlState === "installed") {
    OcrPanel.note = "验证码识别组件已安装并启用。";
  }
  OcrPanel.lastDownload = dlState;

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

  /* lead 随状态变，版本号用 package_version（读不到就不写版本，不编） */
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

  const facts = componentState(feature,
    { busy: busy, installing: installing, location: OcrPanel.location });
  /* 红条拼「下载没有完成：原因，可以重试。」，拼法同手机访问（./state.js downloadFailText）；
   * 更新失败后状态回到「需要更新」，原因同样要看得见，不能只剩一个「更新组件」按钮。
   * 与手机行不同：这条红条在任何阶段都会先显示面板留下的 error。 */
  const failText = failed && !installing && (phase === "missing" || phase === "outdated")
    ? (typeof downloadFailText === "function" ? downloadFailText(download)
      : String(download.text || "下载没有完成，可以重试。")) : "";
  paintComponentRow(OCR_ROW_SPEC, facts, {
    componentError: installing ? "" : (OcrPanel.error || failText),
    /* 取消后回到没装态，一句「下载已取消，没有装任何东西。」由快照的 cancelled 派生；
     * 面板的「刚装好」备注优先于取消句 */
    cancelledNote: OcrPanel.note
      || (phase === "missing" && facts.cancelled && !OcrPanel.error && !failText
        ? "下载已取消，没有装任何东西。" : ""),
  });
  /* 识别行特有：装好未启用时的说明块 */
  ocrShow("#ocr-off-note", phase === "off");
}
