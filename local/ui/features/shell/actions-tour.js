import { termsLocked } from "../terms/state.js";
import { paintTour } from "./view-tour.js";
import { tourClose } from "./actions-tour-exit.js";

export function tourShouldAutoStart() {
  /* 只按内容版本判定：看过本版（tour_version >= TOUR_VERSION）就不再自动弹。
   * 完成/跳过时间戳只描述「当时那一版」，不得挡住更新的内容版本；
   * 软件版本（VERSION/1.1.0 等）变化与 TOUR_VERSION 无关。 */
  const seen = Number(S.prefs.tour_version);
  if (Number.isFinite(seen) && seen >= TOUR_VERSION) return false;
  return !S.busy;
}

/* 首次自动引导的时机（决策 009 修订）：登录成功、活动列表加载后、条款已同意才开始。
 * boot / 同意条款只登记「想自动开始」，真正开始等这三件事都到位（check 与列表到达时各问一次）。 */
export function requestAutoTour() {
  S.tour.autoPending = true;
  maybeStartTour();
}

export function maybeStartTour() {
  if (!S.tour.autoPending || S.tour.open || S.busy) return;
  if (typeof termsLocked === "function" && termsLocked()) return;
  if (!S.demo && S.login.result !== "valid") return;
  if (S.listState !== "ready") return;
  S.tour.autoPending = false;
  startTour(0);
}

/* 可操作那一步只放行高亮的那一行和引导卡片：其余背景点了不算数 */
function tourGuardClick(event) {
  if (!S.tour.open || S.tour.paused) return;
  const step = TOUR_STEPS[S.tour.step] || {};
  if (!step.interactive) return;
  const target = event.target;
  if (!target || !target.closest) return;
  if (target.closest("#tour-card")) return;
  const row = S.tour.rowEl;
  if (row && row.contains && row.contains(target)) return;
  event.preventDefault();
  event.stopPropagation();
}

export function startTour(at) {
  if (S.busy) return;                 /* 计划运行中优先，引导不启动 */
  /* 记住引导开始前焦点在哪，关闭/跳过/完成后还回去（元素还在页面上才还） */
  const prev = document.activeElement;
  S.tour.restoreFocus = (prev && prev !== document.body) ? prev : null;
  S.tour.open = true;
  S.tour.paused = false;
  S.tour.step = Math.max(0, Math.min(Number(at) || 0, TOUR_STEPS.length - 1));
  $("#tour").hidden = false;
  paintTour();
  const nextBtn = $("#tour-next");
  if (nextBtn) nextBtn.focus();       /* 键盘焦点留在引导卡片里 */
}

/* 引导可见时的键盘约束：Tab/Shift+Tab 在卡片按钮间循环。
 * 返回 true = 已处理（调用方直接 return），按钮清单与 aria-modal 声明一致。 */
export function tourTrapTab(event) {
  event.preventDefault();
  const buttons = ["#tour-skip", "#tour-prev", "#tour-next"]
    .map((sel) => $(sel)).filter((el) => el && !el.disabled);
  if (!buttons.length) return true;
  const idx = buttons.indexOf(document.activeElement);
  if (idx < 0) {
    buttons[event.shiftKey ? buttons.length - 1 : 0].focus();
    return true;
  }
  const dir = event.shiftKey ? -1 : 1;
  buttons[(idx + dir + buttons.length) % buttons.length].focus();
  return true;
}

export function tourPauseNow() {
  S.tour.paused = true;
  $("#tour").hidden = true;
}

export function tourResumeNow() {
  if (!S.tour.open) return;
  S.tour.paused = false;
  $("#tour").hidden = false;
  paintTour();
}

export function wireTour() {
  $("#tour-prev").addEventListener("click", () => {
    if (S.tour.step > 0) { S.tour.step -= 1; paintTour(); }
  });
  $("#tour-next").addEventListener("click", () => {
    if (S.tour.step >= TOUR_STEPS.length - 1) { tourClose(true); return; }
    S.tour.step += 1;
    paintTour();
  });
  /* 窗口尺寸或内部滚动变化时重新定位高亮与卡片 */
  window.addEventListener("resize", () => { if (S.tour.open && !S.tour.paused) paintTour(); });
  document.addEventListener("click", tourGuardClick, true);
  document.addEventListener("scroll", () => { if (S.tour.open && !S.tour.paused) paintTour(); }, true);
}
