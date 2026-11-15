/* 两个组件行共有的绘制：标题行的下载/取消两个按钮、「没装」块、导入兜底行、
 * 进度块（文字、MB 数、进度条、填充宽度）、「会装到 / 装在」两行位置与
 * 「打开所在文件夹」、红条与取消后那句话的落点。行与行的差别（下载文案、
 * 红条内容与条件、取消句的条件）由各自的 spec 常量与调用方算好的 texts 保留，
 * 差别清单见 design/evidence 里的 component-machine 差别表；界面口径见
 * docs/UI_SPEC.md 的「组件状态机」一节。只读写 DOM，不调编排层，不发桥接请求。 */



const INSTALL_TEXT_DEFAULT = "下载并安装";
const INSTALL_TEXT_OUTDATED = "更新组件";
const INSTALL_TEXT_FAILED = "重新下载";
const CANCEL_TEXT = "取消下载";
const CANCEL_TEXT_VERIFYING = "校验中…";
const PROG_TEXT_INSTALLING = "正在安装组件…";
const PROG_TEXT_CHECKING = "正在检查组件…";
const PROG_TEXT_VERIFYING = "下载完成，正在校验组件…";



function rowShow(selector, visible) {
  const el = $(selector);
  if (el) el.hidden = !visible;
  return el;
}



function rowText(selector, value) {
  const el = $(selector);
  if (el) {
    el.textContent = String(value || "");
    el.hidden = !value;
  }
  return el;
}



/* spec：这一行的元素 id 与固定文字；facts：componentState 的事实对象；
 * texts：调用方算好的、两行规则不同的那几句（红条、取消后那句）。 */
export function paintComponentRow(spec, facts, texts) {
  const state = facts.state;
  const install = $(spec.installId);
  if (install) {
    install.hidden = state !== "missing" && state !== "outdated";
    install.disabled = facts.busy || facts.installing;
    install.textContent = state === "outdated" ? INSTALL_TEXT_OUTDATED
      : (facts.failed ? INSTALL_TEXT_FAILED : INSTALL_TEXT_DEFAULT);
  }
  const cancel = $(spec.cancelId);
  if (cancel) {
    cancel.hidden = !facts.downloading;
    cancel.disabled = facts.busy || state === "verifying";
    cancel.textContent = state === "verifying" ? CANCEL_TEXT_VERIFYING : CANCEL_TEXT;
  }
  rowShow(spec.missingId, state === "missing" && !facts.installing);
  /* 更新失败后停在 outdated，手动下载导入是唯一的兜底，入口不能跟着「没装」一起收起来 */
  rowShow(spec.importLineId, (state === "missing" || state === "outdated")
    && facts.failed && !facts.installing);
  rowShow(spec.loadingId, facts.loading);
  rowText(spec.progTextId, facts.installing ? PROG_TEXT_INSTALLING
    : (state === "checking" ? PROG_TEXT_CHECKING
      : (state === "verifying" ? PROG_TEXT_VERIFYING : spec.downloadText)));
  const download = facts.download || {};
  const total = Number(download.total_bytes || 0);
  const done = Number(download.downloaded || 0);
  const pct = state === "verifying" ? 100
    : (total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0);
  const num = $(spec.progNumId);
  if (num) {
    num.textContent = state === "downloading" && total > 0
      ? (done / 1048576).toFixed(1) + " / " + (total / 1048576).toFixed(1) + " MB" : "";
  }
  const bar = $(spec.progressBarId);
  if (bar) bar.setAttribute("aria-valuenow", String(pct));
  const fill = $(spec.progFillId);
  if (fill && fill.style) fill.style.width = pct + "%";
  rowText(spec.errorId, texts.componentError || "");
  rowText(spec.cancelledNoteId, texts.cancelledNote || "");
  spec.locIds.forEach((sel, index) => {
    const visible = index === 0
      ? state === "missing" && !!facts.location
      : state !== "missing" && !facts.loading && !!facts.location;
    const box = rowShow(sel, visible);
    const code = $(sel + "-path");
    if (box && facts.location) box.title = facts.location.path || facts.location.short;
    if (code) code.textContent = facts.location ? facts.location.short : "";
  });
  const open = $(spec.openLocId);
  if (open) open.disabled = facts.busy;
}
