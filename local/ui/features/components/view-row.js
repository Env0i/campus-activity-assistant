/* 两个组件行共有的绘制：标题行的下载/取消两个按钮、「没装」块、导入兜底行、
 * 进度块（文字、MB 数、进度条、填充宽度）、「会装到 / 装在」两行位置、
 * 「打开所在文件夹」、红条、读状态说明与「重试」。行与行的差别（下载文案、
 * 红条内容与条件）由各自的 spec 常量与调用方算好的 texts 保留，差别清单见
 * design/evidence 里的 component-machine 差别表；界面口径见
 * docs/UI_SPEC.md 的「组件状态机」一节。只读写 DOM，不调编排层，不发桥接请求。 */



const INSTALL_TEXT_DEFAULT = "下载并安装";
const INSTALL_TEXT_OUTDATED = "更新组件";
const INSTALL_TEXT_BROKEN = "重新安装";
const INSTALL_TEXT_FAILED = "重新下载";
const CANCEL_TEXT = "取消下载";
const CANCEL_TEXT_VERIFYING = "校验中…";
const PROG_TEXT_INSTALLING = "正在安装组件…";
const PROG_TEXT_VERIFYING = "下载完成，正在校验组件…";
const PROBE_TEXT_CHECKING = "正在确认组件状态…";
const PROBE_TEXT_TIMEOUT = "另一个窗口正在安装或更新组件，已等 30 秒";
const PROBE_TEXT_UNREADABLE = "暂时读不到组件状态";
const RETRY_TEXT = "重试";
/* 组件文件坏了时两行都写的说明：账号与设置不在组件包里，重装不会动它们 */
export const BROKEN_NOTE = "组件文件不完整。重新安装不会动你的账号和设置。";



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



/* 主按钮这一格的文字：有结论的三种状态各自说清这一下会做什么，
 * 其余（没装、或者只是下载失败过）都是重新下载一份。 */
function installText(state, failed) {
  if (state === "outdated") return INSTALL_TEXT_OUTDATED;
  if (state === "broken") return INSTALL_TEXT_BROKEN;
  return failed ? INSTALL_TEXT_FAILED : INSTALL_TEXT_DEFAULT;
}



/* 读状态那句：等锁等久了、读不到都给一句，并配「重试」；只是等锁（有结论或没有）
 * 时只有「没结论」那种要说「正在确认」，有结论的那种保留原来的字、什么都不加。 */
function probeText(probe, state) {
  if (probe === "timeout") return PROBE_TEXT_TIMEOUT;
  if (probe === "unreadable") return PROBE_TEXT_UNREADABLE;
  if (probe === "waiting" && state === "checking") return PROBE_TEXT_CHECKING;
  return "";
}



/* spec：这一行的元素 id 与固定文字；facts：componentState 的事实对象；
 * texts：调用方算好的、两行规则不同的那句红条文案。 */
export function paintComponentRow(spec, facts, texts) {
  const state = facts.state;
  const probe = facts.probe || "";
  const install = $(spec.installId);
  if (install) {
    /* 没结论（等锁、读不到）时不给动作按钮：那一下点下去也装不上，留着只会被当成「没装」 */
    install.hidden = (state !== "missing" && state !== "outdated" && state !== "broken")
      || !!probe;
    install.disabled = facts.busy || facts.installing;
    install.textContent = installText(state, facts.failed);
  }
  const cancel = $(spec.cancelId);
  if (cancel) {
    cancel.hidden = !facts.downloading;
    cancel.disabled = facts.busy || state === "verifying";
    cancel.textContent = state === "verifying" ? CANCEL_TEXT_VERIFYING : CANCEL_TEXT;
  }
  rowShow(spec.missingId, state === "missing" && !facts.installing);
  /* 更新失败后停在 outdated，手动下载导入是唯一的兜底，入口不能跟着「没装」一起收起来 */
  rowShow(spec.importLineId, (state === "missing" || state === "outdated" || state === "broken")
    && facts.failed && !facts.installing);
  rowShow(spec.loadingId, facts.loading);
  rowText(spec.progTextId, facts.installing ? PROG_TEXT_INSTALLING
    : (state === "verifying" ? PROG_TEXT_VERIFYING : spec.downloadText));
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
  const note = rowText(spec.probeId, probeText(probe, state));
  if (note) note.dataset.probe = probe;
  const retry = rowShow(spec.retryId, probe === "timeout" || probe === "unreadable");
  if (retry) {
    retry.disabled = facts.busy;
    retry.textContent = RETRY_TEXT;
  }
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
