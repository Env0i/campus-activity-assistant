/* 取消报名控制器（计划 20261107-conflict-cancel，X1–X4）：
 * 点「取消报名」只展开确认块；只有「确认取消报名」才调 cancel_signup。
 * 成败以后端复查为准：这里只把回包 kind 画成一句话，不自己判断成功。 */
function cancelFindRx(id) {
  return document.querySelector('.rx[data-rx="' + cssEscape(String(id)) + '"]');
}

function cancelReveal(id) {
  const rx = cancelFindRx(id);
  if (rx && rx.scrollIntoView) rx.scrollIntoView({ block: "nearest" });
}

/* 「取消报名」按钮：条件不满足一律不动（按钮本该是禁用的） */
function cancelAsk(id) {
  id = String(id);
  const item = findItem(id);
  if (!item || !canCancelNow(item) || cancelBlock(id).off) return;
  S.cancel.askId = id;
  S.cancel.res = null;
  render();
  cancelReveal(id);
  const no = document.querySelector('.rx[data-rx="' + cssEscape(id) + '"] [data-cancel-no]');
  if (no && no.focus) no.focus();
}

/* 「不取消」：只收起确认块，不调任何接口 */
function cancelAskDismiss() {
  if (!S.cancel.askId) return;
  S.cancel.askId = "";
  render();
}

/* 回包 → 结果句。refused 的 say 是学校原话，只显示在界面里，不写运行记录 */
function cancelSettle(id, res) {
  const item = findItem(id);
  const name = item ? item.name : "这场活动";
  S.cancel.busyId = "";
  const data = res && typeof res === "object" ? res : {};
  if (data.error === "terms_required") {
    noteTermsRequired(data);
    render();
    return;
  }
  const kind = String(data.kind || "");
  if (kind === "cancelled") {
    S.cancel.res = { id: id, kind: "cancelled" };
    /* 学校记录已核对为没报名：本地马上放回可报名，再刷新一次拿权威列表 */
    if (item) { item.signed = false; item.state = ""; }
    S.confirmed.delete(id);
    addLog("取消报名：「" + name + "」已取消，学校记录已核对");
    render();
    refresh(true);
    return;
  }
  if (kind === "refused") {
    S.cancel.res = { id: id, kind: "refused", say: String(data.message || "") };
    addLog("取消报名：「" + name + "」学校没有取消");
  } else if (kind === "precheck_failed" || kind === "busy") {
    S.cancel.res = { id: id, kind: "precheck", reason: kind === "busy" ? "busy" : String(data.reason || ""), say: String(data.message || "") };
    addLog("取消报名：「" + name + "」现在不能取消");
  } else {
    S.cancel.res = { id: id, kind: "unknown" };
    addLog("取消报名：「" + name + "」没能确认是否已取消，请到学校网站核对");
  }
  render();
  cancelReveal(id);
}

/* 「确认取消报名」：唯一调用 cancel_signup 的地方 */
function cancelConfirm(id) {
  id = String(id);
  if (S.cancel.askId !== id || S.cancel.busyId) return;
  const item = findItem(id);
  S.cancel.askId = "";
  if (!item || !item.signed || cancelBlock(id).off) { render(); return; }
  /* 确认块开着的这段时间里窗口可能过了、时钟可能丢了：前端先挡，不去问学校 */
  if (!canCancelNow(item)) {
    const closed = cancelWindowOpen(item) === false;
    S.cancel.res = { id: id, kind: "precheck", reason: closed ? "window_closed" : "clock_unavailable" };
    render();
    cancelReveal(id);
    return;
  }
  S.cancel.busyId = id;
  S.cancel.res = null;
  render();
  api("cancel_signup", id).then((res) => {
    if (S.cancel.busyId !== id) return;
    cancelSettle(id, res);
  }).catch(() => {
    if (S.cancel.busyId !== id) return;
    cancelSettle(id, { ok: false, kind: "unknown" });
  });
}
