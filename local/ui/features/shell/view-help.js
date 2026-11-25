/* 帮助弹窗与重看引导入口。 */
export function fillHelp(help) {
  const data = help || DEFAULT_HELP;
  $("#help-title").textContent = data.title || DEFAULT_HELP.title;
  $("#help-sub").textContent = data.subtitle || "";
  $("#help-steps").innerHTML = (data.steps || []).map((step) => "<li><span class=\"no\">" + esc(step.no) + "</span><div><div class=\"t\">" + esc(step.title) + "</div><div class=\"d\">" + esc(step.text) + "</div></div></li>").join("");
}

/* 辅助动作的局部反馈：只在帮助里说下一步，不去复读到大屏或结果框。
 * 长地址/错误原话做成可选文本，不在 WebView 里导航。 */
export function helpStatus(text, tone) {
  const box = $("#help-status");
  if (!box) return;
  const dismissBtn = $("#btn-dismiss-help-status");
  if (!text) {
    box.hidden = true;
    box.textContent = "";
    if (dismissBtn) dismissBtn.hidden = true;
    return;
  }
  box.hidden = false;
  box.dataset.tone = tone || "warn";
  box.textContent = text;
  if (dismissBtn) dismissBtn.hidden = false;
  revealHelpStatus(box);
}

/* 矮窗里反馈可能刚好落在折叠处：帮助弹窗或设置抽屉可见时滚入可见区，头尾不动。 */
export function revealHelpStatus(box) {
  const settingsEl = $("#settings");
  const settingsShown = !!S.settingsOpen && !(settingsEl && settingsEl.hidden);
  if (box && ($("#help").open || settingsShown) && typeof box.scrollIntoView === "function") {
    box.scrollIntoView({ block: "nearest" });
  }
}

/* 忙时只禁重播；查版本、打开目录不打断报名计划。 */
export function paintReplayButtons() {
  [["#btn-help-tour", "重看引导"]].forEach((pair) => {
    const btn = $(pair[0]);
    if (!btn) return;
    btn.disabled = !!S.busy;
    btn.textContent = S.busy ? "计划结束后可重看引导" : pair[1];
    btn.title = S.busy ? "计划结束后可重看引导" : "重新看一遍五步引导";
  });
}
