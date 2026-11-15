/* 结果条与「忙」这个开关：全程序共用的两件小事，跟登录无关，所以放在视图层普通脚本里。 */
function setBusy(busy) {
  S.busy = !!busy;
  /* 计划开跑先暂停引导（运行状态优先），收尾后从原步骤继续 */
  if (S.busy && S.tour.open && !S.tour.paused) tourPauseNow();
  if (!S.busy && S.tour.paused) tourResumeNow();
  paintLogin();
  updateControls();
}

let resultTimer = null;

function setResult(result) {
  const el = $("#result");
  clearTimeout(resultTimer);
  resultTimer = null;
  if (!result) {
    el.hidden = true;
    el.textContent = "";
    el.className = "result";
    return;
  }
  el.hidden = false;
  const cls = result.ok === true ? "is-ok" : (result.ok === "partial" ? "is-partial"
    : (result.ok === "neutral" ? "is-neutral" : "is-bad"));
  el.className = "result " + cls;
  el.innerHTML = "<strong>" + esc(result.title || "") + "</strong><span>" + esc(result.text || "") + "</span>" +
    (result.action ? "<button class=\"result-action\" type=\"button\" id=\"result-action\">" + esc(result.action.label) + "</button>" : "");
  if (result.action) {
    const btn = el.querySelector("#result-action");
    btn.addEventListener("click", result.action.run);
  }
  /* 登录成功的结论 6 秒后自动收起；其他结论留到用户确认 */
  if (result.autoClose) resultTimer = setTimeout(() => { if (!S.busy) setResult(null); }, Math.max(0, result.autoClose - Date.now()));
}
