/* 两个组件行共有的绘制：标题行（圆点颜色、状态句、只亮一只的主按钮、展开箭头）、
 * 标题行下的进度条与小字、红条，以及收在展开区里的「没装」块、下载说明、导入兜底、
 * 「会装到 / 装在」两行位置和「打开所在文件夹」。
 *
 * 状态句与按钮该长什么样由 ./state-row.js 推导，这里只落 DOM；两行差别的口径见
 * docs/UI_SPEC.md 的「设置里的组件行」一节。只读写 DOM，不调编排层，不发桥接请求。 */

import { rowHead, rowOpen } from "./state-row.js";



function rowEl(selector) {
  return selector ? $(selector) : null;
}



function rowShow(selector, visible) {
  const el = rowEl(selector);
  if (el) el.hidden = !visible;
  return el;
}



function rowText(selector, value) {
  const el = rowEl(selector);
  if (el) {
    el.textContent = String(value || "");
    el.hidden = !value;
  }
  return el;
}



/* 主按钮能不能点：面板忙时一律不能点；装的时候还要挡住重复点，校验中挡取消 */
function buttonDisabled(action, want, facts) {
  if (want.disabled) return true;
  if (action === "install") return !!facts.busy || !!facts.installing;
  if (action === "cancel") return !!facts.busy || facts.state === "verifying";
  if (action === "retry" || action === "enable" || action === "package") return !!facts.busy;
  return false;
}



/* 按钮位只亮一只：先把这一行所有动作按钮收起来，再按推导结果点亮对应那一颗。
 * 文字也由推导给，免得按钮自己的字与状态句对不上。 */
function paintHeadButton(spec, want, facts) {
  const buttons = spec.buttons || {};
  Object.keys(buttons).forEach((action) => rowShow(buttons[action], false));
  const el = want ? rowEl(buttons[want.action]) : null;
  if (!el) return;
  el.hidden = false;
  el.disabled = buttonDisabled(want.action, want, facts);
  el.className = "btn " + (want.cls || "btn-line");
  el.textContent = String(want.label || "");
}



/* 标题行：图标旁那句状态、圆点颜色与慢闪、主按钮、进度条、小字（说明、坏档那句、读状态）。
 * 手机那颗状态还要记下 data-link，颜色与闪烁的值由样式表按 adv-s 的档位画。 */
function paintHead(spec, facts, texts) {
  const head = rowHead(spec.kind, facts, texts || {});
  const chip = rowEl(spec.statusId);
  if (chip) {
    chip.hidden = !head.text;
    chip.className = "adv-s " + head.tone + (head.blink ? " blink" : "");
    chip.dataset.state = String((texts && texts.phase) || facts.state || "");
    /* link 传的是 phoneLinkView 的结论对象，data-link 只要那个状态名 */
    if (spec.kind !== "ocr") {
      const view = texts && texts.link;
      chip.dataset.link = String(view && view.link ? view.link : (view || ""));
    }
  }
  rowText(spec.statusTextId, head.text);
  paintHeadButton(spec, head.button, facts);
  const bar = rowShow(spec.barId, typeof head.bar === "number");
  if (bar) bar.setAttribute("aria-valuenow", String(head.bar || 0));
  const fill = rowEl(spec.fillId);
  if (fill && fill.style) fill.style.width = (head.bar || 0) + "%";
  const note = rowEl(spec.noteId);
  if (note) {
    note.className = "adv-n" + (head.note && head.note.tone ? " " + head.note.tone : "");
    note.textContent = head.note ? head.note.text : "";
    note.hidden = !head.note;
    note.dataset.probe = String(facts.probe || "");
  }
}



/* 收在展开区里的那些块：位置两行只有「没装」与「装了」两种时机显示，
 * 导入兜底只在真的下载失败过时出现（坏了也算，那是唯一的手动出路） */
function paintDetail(spec, facts) {
  const open = rowOpen(spec.kind);
  rowShow(spec.detailId, open);
  const toggle = rowEl(spec.toggleId);
  if (toggle) {
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? String(spec.collapseLabel) : String(spec.expandLabel));
  }
  rowShow(spec.missingId, facts.state === "missing" && !facts.installing);
  rowShow(spec.importLineId, (facts.state === "missing" || facts.state === "outdated"
    || facts.state === "broken") && facts.failed && !facts.installing);
  rowShow(spec.loadingNoteId, !!facts.loading);
  (spec.locIds || []).forEach((sel, index) => {
    const visible = index === 0
      ? facts.state === "missing" && !!facts.location
      : facts.state !== "missing" && !facts.loading && !!facts.location;
    const box = rowShow(sel, visible);
    const code = rowEl(sel + "-path");
    if (box && facts.location) box.title = facts.location.path || facts.location.short;
    if (code) code.textContent = facts.location ? facts.location.short : "";
  });
  const openLoc = rowEl(spec.openLocId);
  if (openLoc) openLoc.disabled = !!facts.busy;
}



/* spec：这一行的元素 id 与展开箭头两句话；facts：componentState 的事实对象；
 * texts：状态机不管、画面要用的那几项（phase、link、version、componentError 等）。 */
export function paintComponentRow(spec, facts, texts) {
  const extra = texts || {};
  paintHead(spec, facts, extra);
  rowText(spec.errorId, extra.componentError || "");
  paintDetail(spec, facts);
}
