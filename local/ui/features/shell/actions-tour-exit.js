export function tourClose(finished) {
  S.tour.open = false;
  S.tour.paused = false;
  $("#tour").hidden = true;
  const back = S.tour.restoreFocus || null;
  S.tour.restoreFocus = null;
  if (back && document.body && document.body.contains(back)) {
    try { back.focus(); } catch (err) { /* 元素已不可聚焦就算了 */ }
  }
  if (finished) savePrefsNow({ tour_version: TOUR_VERSION, tour_completed_at: new Date().toISOString() });
}

export function tourSkip() {
  /* 跳过=本版不再自动弹；帮助中的重看引导随时可回顾。 */
  savePrefsNow({ tour_version: TOUR_VERSION, tour_skipped_at: new Date().toISOString() });
  tourClose(false);
}

export function wireTourExit() {
  $("#tour-skip").addEventListener("click", tourSkip);
}
