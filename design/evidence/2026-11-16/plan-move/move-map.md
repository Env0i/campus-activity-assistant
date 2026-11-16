# 计划栏搬家地图：每个名字从哪儿到哪儿，按什么归层

- **开工 HEAD**：`abd2a6a`，分支 `refactor/step1`。
- **搬之前**：`local/ui/state/plan.js`（175 行）、`local/ui/state/task-display.js`（248 行）、`local/ui/views/plan-panel.js`（1358 行）。
- **搬之后**：`local/ui/features/plan/` 下五个模块——`state.js` 110 行、`actions.js` 72 行、`state-task.js` 246 行、`state-board.js` 232 行、`view.js` 383 行；`plan-panel.js` 从 1358 行降到 748 行。
- **只搬不改**：58 段顶层声明逐字照搬（28 个函数、2 个常量、两个状态文件的 28 个顶层声明），`scripts/move_check.py` 对开工 HEAD 逐段核对，**58 段全部找到且一字不差**；新文件里不属于原文的行**分不进任何一类的是 0 行**；`plan-panel.js` 与开工 HEAD 相比**只少了搬走的段**。
- **预计时长**：约三小时（冒烟 40 分钟、搬家与接线 70 分钟、逐字核对与搬后重跑安全网 40 分钟、全量回归与文档 40 分钟）。**实际**：约两小时；其中搬后安全网 365 行单独跑了十几分钟。

## 归层口径

按文件名决定层，函数体一个字不改：

- **状态层**（`state.js`、`state-task.js`、`state-board.js`）：不碰 DOM、不发桥接请求、不用定时器，只读 `S` 与入参算出结论。
- **视图层**（`view.js`）：只读写 DOM 与 `S`，只调状态层与视图层的名字。
- **编排层**（`actions.js`）：发桥接请求、调 controllers 里的名字、写完状态再统一重画。

## 一、`local/ui/state/task-display.js` → `state-task.js`（整个文件）

| 名字 | 原行 | 去处 | 理由 |
|---|---|---|---|
| `RUNNING_STATUSES` | 2 | `state-task.js` | 固定表，本文件与别的普通脚本共用 |
| `taskDisplayItem` | 6-21 | `state-task.js` | 纯推导 |
| `taskDisplayPhase` | 32-47 | `state-task.js` | 纯推导 |
| `taskDisplayLabel` | 50-68 | `state-task.js` | 纯查表拼字 |
| `taskModePrefix` | 71-75 | `state-task.js` | 纯拼字 |
| `taskPrepared` | 80-88 | `state-task.js` | 纯推导 |
| `taskDisplayDetail` | 91-106 | `state-task.js` | 纯拼字 |
| `executionView` | 114-170 | `state-task.js` | 纯推导 |
| `verifiedSigned` | 175-179 | `state-task.js` | 纯推导 |
| `telemetryDeadline` | 182-185 | `state-task.js` | 纯计算 |
| `submittingDetail` | 190-201 | `state-task.js` | 纯拼字 |
| `effectiveRetryDeadline` | 219-248 | `state-task.js` | 纯计算 |

整文件搬，原文件头注释随行。

## 二、`local/ui/state/plan.js` → `state.js` + `actions.js`

| 名字 | 原行 | 去处 | 理由 |
|---|---|---|---|
| `mergeTask` | 2-12 | `state.js` | 纯合并 |
| `PLAN_TERMINAL` | 15 | `state.js` | 固定表 |
| `TASK_TERMINAL` | 16 | `state.js` | 固定表 |
| `maxPlanGen` | 19-24 | `state.js` | 纯取大 |
| `planEventOwns` | 30-37 | `state.js` | 纯推导 |
| `admitPlanEvent` | 40-45 | `state.js` | 只写 `S.maxPlanGen`，不重画 |
| `openResultPage` | 112-115 | `state.js` | 只写 `S.resultOpen` / `S.resultSel` |
| `closeResultPage` | 117-120 | `state.js` | 同上 |
| `syncResultSelection` | 121-124 | `state.js` | 同上 |
| `resultPageOpen` | 126-134 | `state.js` | 纯推导（调同文件的 `closeResultPage`） |
| `planOutcome` | 139-155 | `state.js` | 纯统计 |
| `unknownLabel` | 159-166 | `state.js` | 纯拼字 |
| `selectionSignature` | 173-175 | `state.js` | 纯拼接 |
| `advancePlanStatus` | 48-52 | `actions.js` | 写完状态调 `setBusy` |
| `handlePlan` | 54-81 | `actions.js` | 改状态后 `closeResultPage` / `setBusy` / `noteStartedFromPhone` / `render` |
| `handleTask` | 83-107 | `actions.js` | 改状态后 `scheduleSignedRefresh` / `showTaskResult` / `render` |

## 三、`local/ui/views/plan-panel.js` → `state-board.js` + `view.js` + `actions.js`

| 名字 | 原行 | 去处 | 理由 |
|---|---|---|---|
| `paintSelected` | 4-127 | `view.js` | 写大屏三处 DOM |
| `selectionSummary` | 130-135 | `state-board.js` | 纯拼字 |
| `RUN_SOON_S` | 138 | `state-board.js` | 固定数，只被 `runTagText` 用 |
| `runTagText` | 139-144 | `state-board.js` | 纯推导 |
| `runHeadKey` | 147-150 | `state-board.js` | 纯拼接（不碰 DOM） |
| `runCaption` | 153-166 | `state-board.js` | 纯拼字 |
| `setBoardTag` | 168-175 | `view.js` | 写标签 DOM |
| `boardPlanState` | 179-187 | `state-board.js` | 纯推导 |
| `paintBoardState` | 189-193 | `view.js` | 写外框 dataset |
| `boardMetaHtml` | 195-207 | `view.js` | 拼 DOM 字符串 |
| `paintBoardActions` | 232-260 | `view.js` | 改按钮显隐 |
| `editNoteText` | 263-279 | `state-board.js` | 纯拼字 |
| `paintEditNote` | 281-286 | `view.js` | 写说明条 DOM |
| `resultMode` | 290-293 | `state-board.js` | 纯推导 |
| `boardTargetItem` | 296-301 | `state-board.js` | 纯推导 |
| `LATE_WINDOW_S` | 502 | `state-board.js` | 固定数，只被 `planLate` / `paintRunPanel` 用 |
| `planLate` | 503-516 | `state-board.js` | 纯推导 |
| `earliestWaitingOpen` | 519-527 | `state-board.js` | 纯推导 |
| `paintRunPanel` | 529-599 | `view.js` | 写提醒条与修改说明 |
| `verifyTask` | 602-606 | `actions.js` | 调 `refresh`（controllers 的名字） |
| `resultCounts` | 613-626 | `state-board.js` | 纯统计 |
| `resultView` | 629-664 | `state-board.js` | 纯推导 |
| `reselectableIds` | 668-678 | `state-board.js` | 纯推导 |
| `paintResultPanel` | 680-699 | `view.js` | 写统计与页脚 DOM |
| `earliestSelectedOpen` | 701-708 | `state-board.js` | 纯推导 |
| `paintPlan` | 710-733 | `view.js` | 写冲突框与任务卡 DOM |
| `stopReasonText` | 1027-1048 | `state-board.js` | 固定词表 |
| `taskViaHtml` | 1051-1060 | `view.js` | 拼 DOM 字符串 |
| `taskHtml` | 1062-1117 | `view.js` | 拼任务卡 |
| `retryDeadline` | 1120-1122 | `state-board.js` | 转调 `effectiveRetryDeadline` |

归层与指挥会话的预分一致，没有改动。`view.js` 383 行，没有超过 500，不需要按段再拆。

### 留在 `plan-panel.js` 的（这一批不动）

`togglePlace`、`bindPlaceToggle`、`planCheckList`、`paintChecks`、`autoLoginCredential`、`latestSelectedOpen`、`preStartWarnings`、`paintPrewarn`、`startBlocker`、`paintWhy`、`paintTickets`、`paintPolicyLine`、`paintRoute`、`routeDeadline`、`routeTime`、`routeTarget`、`paintCountdown`、`ledSet`、`fmtLed`、`paintLedLabel`、`paintLedBox`、`paintLed`、`updateControls`、`bandOf`、`applyBand`、`setPlanOpen`、`paintDock`、`paintBanners`。

## 四、被赋值的顶层变量（M3）

三个文件里没有被重新赋值的顶层 `let`：`plan-panel.js` 只有 `const RUN_SOON_S` / `const LATE_WINDOW_S`，`state/plan.js` 只有 `PLAN_TERMINAL` / `TASK_TERMINAL`，`task-display.js` 只有 `RUNNING_STATUSES`，都是字面量。`S.maxPlanGen`、`S.resultOpen`、`S.verifyAsked` 是状态对象上的字段，不受「导入的名字只读」影响。这一条没有要拆的地方。

## 五、加载期引用（M4）：0 行

对 55 个名字（28 个函数 + 2 个常量 + `state/plan.js` 16 个 + `task-display.js` 12 个）逐个查了 `app.js`、`main.js`、`legacy-globals.js`、`views/*.js`、`controllers/*.js`、`state/*.js`、`led.js`、`boot-guard.js` 里**列首非空白**的行（文件顶层语句），四类都查：顶层直接调用、顶层把函数名当回调传给 `addEventListener`、顶层 `const` 初始化表达式、加载期会执行的调用链。

**命中 0 行**。所以 `main.js` 与 `app.js` 这一批都没有新增/删除任何行，`applyBand()` 的位置照旧。计划里「删掉 main.js 某一行确认真加载变红」这一步因为没有那一行，标为不适用（见 `smoke.md`）。

## 六、入口与挂回

- `index.html`：删掉 `state/task-display.js` 与 `state/plan.js` 两行 `<script>`，`views/plan-panel.js` 那行保留，其余顺序不变。
- `legacy-globals.js`：新增 `attachPlanGlobals()`，挂回 36 个名字（挂回名单见下表）；原有挂回不动。拆出一个函数是因为 `installLegacyGlobals()` 加上这 36 行会超过代码形状的 60 行上限，拆出来两个都在限内。
- `features/login/actions.js`：按 M13 在现有 import 之后加一行
  `import { paintBoardActions, paintSelected } from "../plan/view.js";`，别的一字不动。编排层引视图层是层规则允许的。

挂回的名字与用它们的普通脚本：

| 挂回的名字 | 普通脚本谁在用 |
|---|---|
| `mergeTask` | `controllers/plan-events.js`、`controllers/plan.js`、`controllers/refresh.js` |
| `planEventOwns`、`admitPlanEvent` | `controllers/plan-events.js` |
| `handlePlan` | `app.js`、`controllers/refresh.js` |
| `handleTask` | `app.js` |
| `openResultPage` | `controllers/plan-events.js` |
| `closeResultPage` | `controllers/plan-events.js`、`controllers/plan.js` |
| `syncResultSelection` | `controllers/refresh.js` |
| `selectionSignature` | `controllers/plan-events.js`、`controllers/plan.js` |
| `planOutcome`、`unknownLabel` | `views/list.js` |
| `PLAN_TERMINAL` | `controllers/plan-events.js`、`controllers/plan.js`、`controllers/refresh.js` |
| `TASK_TERMINAL` | `controllers/plan.js` |
| `RUNNING_STATUSES` | `controllers/refresh.js`、`controllers/tick.js`、`views/plan-panel.js` |
| `executionView` | `views/list.js`、`views/plan-panel.js` |
| `taskDisplayItem` | `views/plan-panel.js` |
| `taskDisplayLabel` | `controllers/tick.js`、`views/list.js` |
| `taskDisplayDetail`、`taskModePrefix` | `controllers/tick.js` |
| `effectiveRetryDeadline` | `views/plan-panel.js` |
| `verifiedSigned` | `state/filters.js`、`state/labels.js`（两处都是 `typeof verifiedSigned === "function"` 的软引用，不挂回会静默失效） |
| `selectionSummary`、`resultMode`、`resultView` | `views/plan-panel.js` |
| `runHeadKey`、`paintEditNote`、`paintRunPanel` | `controllers/tick.js` |
| `planLate`、`reselectableIds`、`paintPlan` | `controllers/plan.js` |
| `stopReasonText` | `controllers/plan-events.js` |
| `paintPlan` | `views/list.js` |
| `verifyTask` | `app.js` |
| `paintSelected` | `controllers/plan.js`、`controllers/tick.js`、`views/list.js` |
| `paintBoardState` | `views/list.js` |
| `paintBoardActions` | `views/plan-panel.js` |

**没有挂回**：`runTagText`、`runCaption`、`editNoteText`、`boardPlanState`、`boardMetaHtml`、`boardTargetItem`、`earliestWaitingOpen`、`earliestSelectedOpen`、`paintResultPanel`、`taskViaHtml`、`taskHtml`、`retryDeadline`、`advancePlanStatus`、`resultPageOpen`、`maxPlanGen`、`resultCounts`、`taskDisplayPhase`、`taskPrepared`、`submittingDetail`、`telemetryDeadline`——它们要么只在搬走的代码内部用，要么只在模块之间 import（`maxPlanGen`、`resultCounts` 就是后者：守卫报「挂了没人用」，所以没挂）。

## 七、跟着改的路径文字（M8）

| 文件 | 改了什么 | 为什么 |
|---|---|---|
| `local/tests/test_ui_contract_list.py` | `read("ui/views/plan-panel.js")` → `read("ui/features/plan/view.js")`（读计划栏空态两句话） | 那两句在 `paintSelected` 里，搬到了 `view.js` |
| 同上，同一条用例 | 切片终点从 `function updateControls(` 改成读到文件末尾，起点文件跟着换成 `view.js` | `taskHtml` 与 `updateControls` 搬到了两个文件，拼接文本里 `updateControls` 出现在 `taskHtml` 前面，原来的「切到下一个锚点」取不到；断言一个字没改 |
| `local/tests/test_ui_contract_shell.py` | `read("ui/views/plan-panel.js")` → `read("ui/app.js")` | 它要比较前端常量与后端常量。读单个模块文件会带上 `export ` 前缀，正则 `^const LATE_WINDOW_S` 就匹配不上；读拼接文本（`read("ui/app.js")` 是整份脚本拼接、`export` 已剥掉）保持原正则与原断言不变 |
| `local/tests/test_prerefactor_fixes.py` | 两处文档字符串 + 副本变异目标 `copy/"state"/"plan.js"` → `copy/"features"/"plan"/"actions.js"` | `scheduleSignedRefresh` 的调用在 `handleTask`，搬到了 `actions.js`；变异点文字没动 |
| `local/tests/test_ui_main_window_plan.py` | 注释里的 `state/plan.js` → `features/plan/actions.js` | 同一处来源 |
| `docs/UI_SPEC.md` 5.19 开头那句 | 文案来源加上 `features/plan/view.js`、`state-board.js`、`state-task.js`，`plan-panel.js` 注明「留下的部分」 | 计划栏文案分散到新文件 |
| `local/tests/test_retry_phone_policy.py` | **没改** | 计划点名了这一处，实际文件里没有 `state/plan.js` 字样 |
| `tools/qa_runtime_reliability.py` | **没改** | 一处是计划编号，一处写的 `plan-panel.js loginReady`，而 `updateControls` 这一批留在 `plan-panel.js`，仍然准确 |

## 八、名单与期望值（M9）

- **大小名单**：`views/plan-panel.js` 从 `over800`（1358）换档到 `over500`（748，实测）；`paintSelected`（124）与 `paintRunPanel`（71）两条的键改到 `features/plan/view.js::…`，记录值与理由不变；没有新增项。
- **分层白名单**：删掉 `state/plan.js` 一整组（文件没了）与 `views/plan-panel.js` 里的 `refresh`（`verifyTask` 搬走后再没有普通脚本在这一层调它）；没有新增项。
- **模块图期望值**：`node tools/code_shape/ui_modules.mjs --expect` 重新生成，五类问题（顶层循环、缺 import、跨层引用、普通脚本引用了没挂回的模块名字、挂了没人用）都为空。

## 九、一处计划外的动作，说明一下

计划要求删掉 `state/plan.js` 与 `state/task-display.js`，又要求 `python -B tools/code_shape/check.py` 通过；而 `check.py` 是按 git 索引清点文件的（`git ls-files --cached`），文件删了但索引里还在，它会去读一个不存在的文件然后崩。为了让它能跑，把这两处删除记进了索引：

```text
git update-index --force-remove -- local/ui/state/plan.js local/ui/state/task-display.js
```

没有 `git add` 任何内容、没有提交。收工时 `git status` 里这两条是 `D `（已暂存的删除），其余改动都还在工作区。

## 十、逐字核对的结果

`scripts/move_check.py` 的输出：

- 顶层声明段 **58 段，一字不差找到 58 段**，找不到 0 段，找到但不同 0 段。
- 新文件里不属于原文的行：**0 行**（`export` 前缀按规则剥掉后逐行比对，文件头与 import 已归类）。
- `plan-panel.js` 留下 748 行，与开工 HEAD 相比**只少了搬走的段**，没有别的改动。
