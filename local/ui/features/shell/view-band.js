/* 窗口宽高分档与计划栏开合的视图。 */

import { paintDock } from "../plan/view-dock.js";

/* 与 styles.css 的断点是同一组阈值：宽 ≥1040 双栏；中 720–1039、窄 <720 单栏 + 底部计划条；
 * 高 <660 为矮窗。只看视口宽高，不读 UA。 */
export function bandOf(width, height) {
  const w = Number(width) || 1280;
  const h = Number(height) || 800;
  return { band: w >= 1040 ? "wide" : (w >= 720 ? "medium" : "narrow"), short: h < 660 };
}

export function applyBand() {
  const got = bandOf(window.innerWidth, window.innerHeight);
  S.band = got.band;
  S.short = got.short;
  const zd = $("#zd");
  if (zd && zd.dataset) {
    zd.dataset.band = got.band;
    zd.dataset.short = got.short ? "1" : "0";
  }
  if (got.band === "wide" && S.planOpen) setPlanOpen(false);
  else paintDock();
}

/* 中、窄档里计划栏和时刻表二选一：查看计划时收起时刻表，「返回列表」再换回来 */
export function setPlanOpen(open) {
  S.planOpen = !!open && S.band !== undefined && S.band !== "wide";
  const zd = $("#zd");
  if (zd && zd.dataset) zd.dataset.planOpen = S.planOpen ? "1" : "0";
  const back = $("#btn-plan-back");
  if (back) back.hidden = !S.planOpen;
  paintDock();
}
