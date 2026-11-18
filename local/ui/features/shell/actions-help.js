import { startTour } from "./actions-tour.js";
import { helpStatus } from "./view-help.js";
import { PhonePanel } from "../phone-access/state.js";

export function showHelp() {
  const dialog = $("#help");
  helpStatus("");
  paintUpdate();
  if (!dialog.open) dialog.showModal();
  if (typeof PhonePanel !== "undefined") void PhonePanel.refresh();
  savePrefs({ welcome_seen: true });
}

/* 帮助中的重播先确认非忙，再关模态、把焦点还给顶栏，最后进第1步。
 * 不复制教程长文，也不在弹窗还开着时叠一层遮罩。 */
function replayTourFrom(dialogSelector, openerSelector) {
  if (S.busy) {
    addLog("[i] 计划运行中：计划结束后再重看引导");
    return false;
  }
  const dialog = $(dialogSelector);
  if (dialog && dialog.open) dialog.close();
  const opener = $(openerSelector);
  if (opener) {
    try { opener.focus(); } catch (err) { /* 元素不可聚焦就算了，不挡住重播 */ }
  }
  startTour(0);
  return true;
}

export function wireHelp() {
  $("#btn-help").addEventListener("click", showHelp);
  $("#btn-help-tour").addEventListener("click", () => replayTourFrom("#help", "#btn-help"));
}
