/* 验证码识别一节的视图层：本节显隐与文案的小工具加下载区的整段绘制；只读写 DOM 和面板字段，不发桥接请求。 */



import { OcrPanel, ocrFeature, ocrPhase } from "./state-ocr.js";
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



/* 标题行右侧二选一：没装放「下载并安装」（失败后「重新下载」）、已装没启用放「启用」、下载中放「取消下载 / 校验中…」、
 * 已启用放 chip；失败后才露出「导入已下载的组件包」那句链接（OC12）。 */
export function paintOcrDownload() {
  const feature = ocrFeature();
  const download = feature.download || {};
  const dlState = String(download.state || "");
  const phase = ocrPhase(feature);
  const downloading = phase === "downloading" || phase === "verifying";
  /* I1：点「安装这份」到快照刷新完成为止，快照还是导入前的旧状态：这段时间不画旧红条与导入行，进度区说正在安装 */
  const installing = !!(window.PhonePanel && window.PhonePanel.installing
    && window.PhonePanel.installing.relogin_ocr);
  const loading = downloading || phase === "checking" || installing;
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
    downloadBtn.disabled = busy || installing;
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
  /* OC11：红条拼「下载没有完成：原因，可以重试。」，拼法同手机访问（features/components/state.js downloadFailText）；
   * 更新失败后状态回到「需要更新」，原因同样要看得见，不能只剩一个「更新组件」按钮 */
  const failText = failed && !installing && (phase === "missing" || phase === "outdated")
    ? (typeof downloadFailText === "function" ? downloadFailText(download)
      : String(download.text || "下载没有完成，可以重试。")) : "";
  ocrText("#ocr-download-error", installing ? "" : (OcrPanel.error || failText));

  ocrShow("#ocr-missing", phase === "missing" && !installing);
  /* 更新失败后停在 outdated，手动下载导入是唯一的兜底，入口不能跟着「没装」一起收起来 */
  ocrShow("#ocr-import-line", (phase === "missing" || phase === "outdated") && failed && !installing);
  ocrShow("#ocr-off-note", phase === "off");
  ocrShow("#ocr-loading", loading);

  /* OC10：进度块左「正在下载验证码识别组件」、右「9.5 / 31.6 MB」，校验时「下载完成，正在校验组件…」；进度条墨色，复用 .ph-bar */
  const total = Number(download.total_bytes || 0);
  const done = Number(download.downloaded || 0);
  const pct = phase === "verifying" ? 100
    : (total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0);
  ocrText("#ocr-prog-text", installing ? "正在安装组件…"
    : (phase === "checking" ? "正在检查组件…"
    : (phase === "verifying" ? "下载完成，正在校验组件…" : "正在下载验证码识别组件")));
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
