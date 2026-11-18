import { PhonePanel } from "../phone-access/state.js";

export function showHelp() {
  const dialog = $("#help");
  helpStatus("");
  paintUpdate();
  if (!dialog.open) dialog.showModal();
  if (typeof PhonePanel !== "undefined") void PhonePanel.refresh();
  savePrefs({ welcome_seen: true });
}

export function wireHelp() {
  $("#btn-help").addEventListener("click", showHelp);
}
