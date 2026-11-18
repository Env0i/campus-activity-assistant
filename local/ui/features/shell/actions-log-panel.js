/* 运行记录面板：开合状态与偏好保存共用同一入口。 */
export function setLogOpen(open, silent) {
  S.logOpen = !!open;
  const card = document.querySelector(".log-card");
  if (card) card.dataset.open = String(S.logOpen);
  $("#btn-log-toggle").textContent = S.logOpen ? "收起" : "展开";
  $("#btn-log-toggle").setAttribute("aria-expanded", String(S.logOpen));
  /* 载入已有偏好时只恢复显示，不能再次排队保存。 */
  if (!silent) savePrefs({ log_open: S.logOpen });
}

export function wireLogPanel() {
  $("#btn-log-toggle").addEventListener("click", () => setLogOpen(!S.logOpen));
}
