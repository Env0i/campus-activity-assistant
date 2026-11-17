/* 过渡期清单（ESM 地基批）：把模块里的名字挂回 window，给还没迁的普通脚本用。
 * 模块里的名字不进全局作用域，普通脚本只能经 window 拿到；清单里的每个名字必须真的
 * 有普通脚本在用（tools/code_shape/ui_modules.mjs 守着，没人用就红），一旦没有就要从
 * 这里删掉；全部脚本迁成模块、清单清空后，整个文件连同 main.js 里的调用一起删除。 */
import { termsAccepted, termsLocked } from "./features/terms/state.js";
import { PhonePanel, phoneLinkedNow } from "./features/phone-access/state.js";
import { phoneLinkView } from "./features/phone-access/state-link.js";

import { OcrPanel } from "./features/components/state-ocr.js";
import { paintOcrDownload } from "./features/components/view-ocr.js";
import { loginEstimateText } from "./features/login/state.js";
import { paintLogin } from "./features/login/view.js";
import { receiveAutoState, setLogin, syncLoginDependentView } from "./features/login/actions.js";
import { loginEntry, receiveReloginState } from "./features/login/actions-relogin.js";
import { PLAN_TERMINAL, mergeTask, planOutcome, syncResultSelection, unknownLabel } from "./features/plan/state.js";
import { handlePlan, handleTask, verifyTask } from "./features/plan/actions.js";
import { RUNNING_STATUSES, executionView, taskDisplayDetail, taskDisplayLabel, taskModePrefix, verifiedSigned } from "./features/plan/state-task.js";
import { runHeadKey } from "./features/plan/state-board.js";
import { paintBoardState, paintEditNote, paintPlan, paintRunPanel, paintSelected } from "./features/plan/view.js";
import { startPlan } from "./features/plan/actions-start.js";
import { cancelTask, closeStopAsk, stopAskKey, stopAskOpen } from "./features/plan/actions-run.js";
import { handlePlanDone, presentPlanDone } from "./features/plan/actions-events.js";
import { handleDone } from "./features/login/actions-browser.js";
import { togglePlace, paintChecks } from "./features/plan/view-draft.js";
import { paintRoute, paintCountdown, paintLed } from "./features/plan/view-led.js";
import { updateControls } from "./features/plan/view-controls.js";
import { paintBanners } from "./features/shell/view-banners.js";
import { applyBand, setPlanOpen } from "./features/shell/view-band.js";
import { RUNTIME_ERRORS, runtimeErrorCopy } from "./features/shell/state-runtime.js";

/* 计划栏（features/plan）挂回：普通脚本里还有 app.js、controllers/refresh.js、
 * controllers/tick.js、views/list.js、state/filters.js、state/labels.js、
 * state/store.js 在用这些名字。 */
function attachPlanGlobals() {
  window.mergeTask = mergeTask;
  window.handlePlan = handlePlan;
  window.handleTask = handleTask;
  window.syncResultSelection = syncResultSelection;
  window.planOutcome = planOutcome;
  window.unknownLabel = unknownLabel;
  window.PLAN_TERMINAL = PLAN_TERMINAL;
  window.RUNNING_STATUSES = RUNNING_STATUSES;
  window.executionView = executionView;
    window.taskDisplayLabel = taskDisplayLabel;
  window.taskDisplayDetail = taskDisplayDetail;
  window.taskModePrefix = taskModePrefix;
    window.verifiedSigned = verifiedSigned;
    window.runHeadKey = runHeadKey;
      window.verifyTask = verifyTask;
  window.paintSelected = paintSelected;
  window.paintBoardState = paintBoardState;
    window.paintEditNote = paintEditNote;
  window.paintRunPanel = paintRunPanel;
  window.paintPlan = paintPlan;
  window.startPlan = startPlan;
  window.cancelTask = cancelTask;
  window.stopAskOpen = stopAskOpen;
  window.stopAskKey = stopAskKey;
  window.closeStopAsk = closeStopAsk;
  window.presentPlanDone = presentPlanDone;
  window.handlePlanDone = handlePlanDone;
  window.togglePlace = togglePlace;
  window.paintChecks = paintChecks;
  window.paintRoute = paintRoute;
  window.paintCountdown = paintCountdown;
  window.paintLed = paintLed;
  window.updateControls = updateControls;
}

/* 横幅、分档与组件错误文案的挂回：这几组由 shell 段搬成模块，普通脚本仍按全局名用。
 * 单独成函数，免得 installLegacyGlobals 超过 60 行。 */
function attachShellGlobals() {
  window.paintBanners = paintBanners;
  window.applyBand = applyBand;
  window.setPlanOpen = setPlanOpen;
  window.RUNTIME_ERRORS = RUNTIME_ERRORS;
  window.runtimeErrorCopy = runtimeErrorCopy;
}

export function installLegacyGlobals() {
  window.termsAccepted = termsAccepted;
  window.termsLocked = termsLocked;
  /* app.js 的 check 事件要顺手刷新这张卡片（重新登录成功会走 check）。跨文件只能靠
   * 一个显式挂载点：顶层 const 不会自动变成 window 属性。 */
  if (typeof window !== "undefined") window.PhonePanel = PhonePanel;
    /* 顶栏标识与手机详情卡（views/status-cards.js，还是普通脚本）：连接状态读后端 link，
   * 详情卡的「配对」那一行问配过对没有。 */
  window.phoneLinkView = phoneLinkView;
  window.phoneLinkedNow = phoneLinkedNow;
  window.OcrPanel = OcrPanel;
  window.paintOcrDownload = paintOcrDownload;
  /* 登录块（features/login）：普通脚本里还有 app.js、controllers/refresh.js、controllers/tick.js、
   * views/result.js、views/status-cards.js 在用这几个名字。 */
  window.setLogin = setLogin;
  window.receiveAutoState = receiveAutoState;
    window.syncLoginDependentView = syncLoginDependentView;
  window.loginEstimateText = loginEstimateText;
  window.paintLogin = paintLogin;
  window.loginEntry = loginEntry;
  window.receiveReloginState = receiveReloginState;
  window.handleDone = handleDone;
  attachPlanGlobals();
  attachShellGlobals();
}
