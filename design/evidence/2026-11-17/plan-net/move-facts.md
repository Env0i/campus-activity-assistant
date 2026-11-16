# 计划栏搬家事实（脚本生成）

生成口径：只读扫描 `local/ui/**/*.js`、`local/ui/index.html` 和 `tools/code_shape/baseline.json`。
## 表一：顶层名字、引用分布与加载期

| 定义文件 | 名字 | 其他文件引用次数 | 加载期使用 |
|---|---|---:|---|
| `local/ui/views/plan-panel.js` | `paintSelected` | 4 | 是：启动 render 或事件绑定调用链 |
| `local/ui/views/plan-panel.js` | `selectionSummary` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `runTagText` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `runHeadKey` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `runCaption` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `setBoardTag` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `boardPlanState` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintBoardState` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `boardMetaHtml` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `togglePlace` | 2 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `bindPlaceToggle` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintBoardActions` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `editNoteText` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintEditNote` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `resultMode` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `boardTargetItem` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `planCheckList` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintChecks` | 5 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `autoLoginCredential` | 6 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `latestSelectedOpen` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `preStartWarnings` | 3 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintPrewarn` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `startBlocker` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintWhy` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintTickets` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintPolicyLine` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `planLate` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `earliestWaitingOpen` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintRunPanel` | 2 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `verifyTask` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `resultCounts` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `resultView` | 6 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `reselectableIds` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintResultPanel` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `earliestSelectedOpen` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintPlan` | 2 | 是：启动 render 或事件绑定调用链 |
| `local/ui/views/plan-panel.js` | `paintRoute` | 2 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `routeDeadline` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `routeTime` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `routeTarget` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintCountdown` | 4 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `ledSet` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `fmtLed` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintLedLabel` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintLedBox` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintLed` | 3 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `stopReasonText` | 1 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `taskViaHtml` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `taskHtml` | 2 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `retryDeadline` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `updateControls` | 25 | 是：启动 render 或事件绑定调用链 |
| `local/ui/views/plan-panel.js` | `bandOf` | 0 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `applyBand` | 2 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `setPlanOpen` | 4 | 否：等用户动作或后端事件 |
| `local/ui/views/plan-panel.js` | `paintDock` | 1 | 是：启动 render 或事件绑定调用链 |
| `local/ui/views/plan-panel.js` | `paintBanners` | 22 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `mergeTask` | 3 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `maxPlanGen` | 3 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `planEventOwns` | 1 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `admitPlanEvent` | 1 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `advancePlanStatus` | 0 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `handlePlan` | 6 | 是：启动 render 或事件绑定调用链 |
| `local/ui/state/plan.js` | `handleTask` | 1 | 是：启动 render 或事件绑定调用链 |
| `local/ui/state/plan.js` | `openResultPage` | 1 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `closeResultPage` | 4 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `syncResultSelection` | 3 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `resultPageOpen` | 1 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `planOutcome` | 4 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `unknownLabel` | 2 | 否：等用户动作或后端事件 |
| `local/ui/state/plan.js` | `selectionSignature` | 2 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `taskDisplayItem` | 1 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `taskDisplayPhase` | 0 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `taskDisplayLabel` | 3 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `taskModePrefix` | 2 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `taskPrepared` | 0 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `taskDisplayDetail` | 2 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `executionView` | 7 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `verifiedSigned` | 7 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `telemetryDeadline` | 0 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `submittingDetail` | 0 | 否：等用户动作或后端事件 |
| `local/ui/state/task-display.js` | `effectiveRetryDeadline` | 3 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `startPlan` | 6 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `reconcileStart` | 0 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `adoptPlan` | 0 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `cancelTask` | 12 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `stopAskOpen` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `openStopAsk` | 0 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `closeStopAsk` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `stopAskKey` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `stopPlan` | 3 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `confirmStopPlan` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `noteStartedFromPhone` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `modifyPlan` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `editPausedLine` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `restoreEditedPlan` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `reselectFailed` | 3 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `finishResult` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `doStopPlan` | 1 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `doLogin` | 6 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `handleDone` | 2 | 否：等用户动作或后端事件 |
| `local/ui/controllers/plan.js` | `loginFailCopy` | 0 | 否：等用户动作或后端事件 |

## 表二：状态字段读写

| 字段 | 写入文件/函数 | 读取文件/函数 |
|---|---|---|
| `S.plan` | state/plan.js:handlePlan/handleTask；controllers/plan.js:startPlan/adoptPlan/reselectFailed | views/plan-panel.js、state/plan.js、state/task-display.js、controllers/plan.js |
| `S.busy` | state/setBusy 的统一入口，登录、计划 ack、停止和 bootstrap 调用 | views/plan-panel.js、state/task-display.js、controllers/plan.js、controllers/tick.js |
| `S.starting` | controllers/plan.js:startPlan/reconcileStart/adoptPlan | views/plan-panel.js:updateControls、controllers/plan.js |
| `S.stopping` | controllers/plan.js:doStopPlan/stopFailed/adoptPlan | views/plan-panel.js:paintRunPanel/updateControls、controllers/plan.js |
| `S.editing` | controllers/plan.js:modifyPlan/restoreEditedPlan/stopFailed；state/plan.js:handlePlan | views/plan-panel.js、state/plan.js、controllers/plan.js、controllers/tick.js |
| `S.startRequest` | controllers/plan.js:startPlan/reconcileStart | views/plan-panel.js:updateControls、controllers/plan.js:reconcileStart |
| `S.verifyAsked` | views/plan-panel.js:verifyTask | views/plan-panel.js:taskHtml、state/plan.js:handleTask |

## 表三：桥接调用与后端事件

| 方向 | 名称 | 文件/函数 |
|---|---|---|
| 调用 | `bootstrap` | `local/ui/controllers/plan.js` |
| 调用 | `cancel_task` | `local/ui/controllers/plan.js` |
| 调用 | `login` | `local/ui/controllers/plan.js` |
| 调用 | `start_plan` | `local/ui/controllers/plan.js` |
| 调用 | `start_request_state` | `local/ui/controllers/plan.js` |
| 调用 | `stop_plan` | `local/ui/controllers/plan.js` |
| 调用 | `check` | `local/ui/controllers/tick.js` |
| 事件 | `log` | `local/ui/app.js` |

## 表四：DOM 与动作入口

| 元素 | 出现于页面 | 主要绘制/动作函数 |
|---|---|---|
| `#banners` | 是 | 计划栏脚本按 `#banners` 读取或写入 |
| `#board` | 是 | 计划栏脚本按 `#board` 读取或写入 |
| `#board-tag` | 是 | 计划栏脚本按 `#board-tag` 读取或写入 |
| `#board-tag-text` | 是 | 计划栏脚本按 `#board-tag-text` 读取或写入 |
| `#board-text` | 是 | 计划栏脚本按 `#board-text` 读取或写入 |
| `#btn-board-pick` | 是 | 计划栏脚本按 `#btn-board-pick` 读取或写入 |
| `#btn-clear-plan` | 是 | 计划栏脚本按 `#btn-clear-plan` 读取或写入 |
| `#btn-dock-start` | 是 | 计划栏脚本按 `#btn-dock-start` 读取或写入 |
| `#btn-edit-restore` | 是 | 计划栏脚本按 `#btn-edit-restore` 读取或写入 |
| `#btn-finish` | 是 | 计划栏脚本按 `#btn-finish` 读取或写入 |
| `#btn-login` | 是 | 计划栏脚本按 `#btn-login` 读取或写入 |
| `#btn-modify` | 是 | 计划栏脚本按 `#btn-modify` 读取或写入 |
| `#btn-plan` | 是 | 计划栏脚本按 `#btn-plan` 读取或写入 |
| `#btn-plan-back` | 是 | 计划栏脚本按 `#btn-plan-back` 读取或写入 |
| `#btn-policy` | 是 | 计划栏脚本按 `#btn-policy` 读取或写入 |
| `#btn-refresh` | 是 | 计划栏脚本按 `#btn-refresh` 读取或写入 |
| `#btn-reselect` | 是 | 计划栏脚本按 `#btn-reselect` 读取或写入 |
| `#btn-stop` | 是 | 计划栏脚本按 `#btn-stop` 读取或写入 |
| `#countdown` | 是 | 计划栏脚本按 `#countdown` 读取或写入 |
| `#dock-sub` | 是 | 计划栏脚本按 `#dock-sub` 读取或写入 |
| `#dock-title` | 是 | 计划栏脚本按 `#dock-title` 读取或写入 |
| `#edit-note` | 是 | 计划栏脚本按 `#edit-note` 读取或写入 |
| `#headed-label` | 是 | 计划栏脚本按 `#headed-label` 读取或写入 |
| `#led` | 是 | 计划栏脚本按 `#led` 读取或写入 |
| `#led-box` | 是 | 计划栏脚本按 `#led-box` 读取或写入 |
| `#led-label` | 是 | 计划栏脚本按 `#led-label` 读取或写入 |
| `#max-attempts` | 是 | 计划栏脚本按 `#max-attempts` 读取或写入 |
| `#modify-why` | 是 | 计划栏脚本按 `#modify-why` 读取或写入 |
| `#plan-checks` | 是 | 计划栏脚本按 `#plan-checks` 读取或写入 |
| `#plan-conflicts` | 是 | 计划栏脚本按 `#plan-conflicts` 读取或写入 |
| `#plan-dock` | 是 | 计划栏脚本按 `#plan-dock` 读取或写入 |
| `#plan-hint` | 是 | 计划栏脚本按 `#plan-hint` 读取或写入 |
| `#plan-prewarn` | 是 | 计划栏脚本按 `#plan-prewarn` 读取或写入 |
| `#plan-stats` | 是 | 计划栏脚本按 `#plan-stats` 读取或写入 |
| `#plan-stop-ask` | 是 | 计划栏脚本按 `#plan-stop-ask` 读取或写入 |
| `#plan-tasks` | 是 | 计划栏脚本按 `#plan-tasks` 读取或写入 |
| `#plan-tickets` | 是 | 计划栏脚本按 `#plan-tickets` 读取或写入 |
| `#plan-why` | 是 | 计划栏脚本按 `#plan-why` 读取或写入 |
| `#policy-edit` | 是 | 计划栏脚本按 `#policy-edit` 读取或写入 |
| `#policy-line` | 是 | 计划栏脚本按 `#policy-line` 读取或写入 |
| `#policy-text` | 是 | 计划栏脚本按 `#policy-text` 读取或写入 |
| `#result-actions` | 是 | 计划栏脚本按 `#result-actions` 读取或写入 |
| `#retry-for` | 是 | 计划栏脚本按 `#retry-for` 读取或写入 |
| `#route` | 是 | 计划栏脚本按 `#route` 读取或写入 |
| `#route-actions` | 是 | 计划栏脚本按 `#route-actions` 读取或写入 |
| `#route-line` | 是 | 计划栏脚本按 `#route-line` 读取或写入 |
| `#run-actions` | 是 | 计划栏脚本按 `#run-actions` 读取或写入 |
| `#run-warn` | 是 | 计划栏脚本按 `#run-warn` 读取或写入 |
| `#selected` | 是 | 计划栏脚本按 `#selected` 读取或写入 |
| `#selected-meta` | 是 | 计划栏脚本按 `#selected-meta` 读取或写入 |
| `#zd` | 是 | 计划栏脚本按 `#zd` 读取或写入 |

## 表五：名单与非计划栏分段

| 段 | 行范围 | 行数 | 名单事实 |
|---|---:|---:|---|
| 计划标题与草稿操作 | 1-302 | 302 | 计划栏文件分段 |
| 检查清单与开始前提醒 | 303-409 | 107 | 计划栏文件分段 |
| 开始前门禁与策略 | 410-528 | 119 | 计划栏文件分段 |
| 运行提示与结果面板 | 529-733 | 205 | 计划栏文件分段 |
| 路线、倒计时点阵与 LED | 734-1023 | 290 | 计划栏文件分段 |
| 任务卡与停止原因 | 1024-1123 | 100 | 计划栏文件分段 |
| 进行中按钮与行门禁 | 1124-1270 | 147 | 计划栏文件分段 |
| 底栏、分档与横幅 | 1271-1358 | 88 | 计划栏文件分段 |
| 合计 | 1-1358 | 1358 | baseline over800 记录值 1358 |
| 非计划栏职责 | — | — | `paintCountdown`、`paintLed*`、`paintRoute`、`route*`、`paintBanners`、`paintDock`、`paintChecks`、`paintPrewarn` 与分档函数在下一步单独搬 |
| baseline 原文已扫描 | — | — | 包含 `local/ui/views/plan-panel.js` 的 over800 记录：是 |
