import { paintLogin } from "../login/view.js";
import { paintTour } from "./view-tour.js";
import { tourPauseNow, tourResumeNow } from "./actions-tour.js";
import { paintSelected, paintBoardState, paintPlan } from "../plan/view.js";
import { paintChecks } from "../plan/view-draft.js";
import { paintRoute, paintLed } from "../plan/view-led.js";
import { paintBanners } from "./view-banners.js";
import { updateControls } from "../plan/view-controls.js";

export function render() {
  paintList();
  /* 活动列表异步回填后同步更新状态胶囊计数，避免真实数据已到但仍显示初始化的 0。 */
  paintChips();
  paintMoreFilters();
  paintRail();
  paintSelected();
  paintBoardState();
  paintChecks();
  paintPlan();
  paintRoute();
  paintBanners();
  updateControls();
  paintTip();
  tick();
  paintLed();
  /* 引导还开着时，列表重画可能挪动高亮目标：重新定位现有高亮，不重开、不假点击 */
  if (S.tour.open && !S.tour.paused) paintTour();
}

export function setBusy(busy) {
  S.busy = !!busy;
  /* 计划开跑先暂停引导（运行状态优先），收尾后从原步骤继续 */
  if (S.busy && S.tour.open && !S.tour.paused) tourPauseNow();
  if (!S.busy && S.tour.paused) tourResumeNow();
  paintLogin();
  updateControls();
}
