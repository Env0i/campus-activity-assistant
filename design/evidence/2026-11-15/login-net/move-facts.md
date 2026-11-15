# 搬家要用的事实（D8 五张表）

- **基线提交**：`896baf2`。执行日期：2026-11-15。
- **脚本**：`scripts/move_facts.py`，只读源码。命令（仓库根）：
  `python -B design/evidence/2026-11-15/login-net/scripts/move_facts.py`（加一个参数可同时落 JSON）。
- **清点范围**：块内三文件 `state/login.js`、`views/login.js`、`views/relogin.js`；引用方取 `local/ui/**/*.js`，去掉 `local/ui/m/`（手机页自己在闭包里定义了同名的 `addLog`、`openRelogin`、`beginRelogin`，不是桌面版的使用方），含 `main.js`。

## 表一：名字引用（含加载期）

口径：按顶层 `function 名字(` 找块内名字，在别的脚本里数它的每一处引用（调用或取值；不算声明与对象键，注释和字符串不计）。「加载期」指该处落在脚本顶层语句上（花括号深度为 0，同一行没有 `=>`），即脚本一加载就执行或取值。表中数字是 `scripts/move_facts.py` 的输出。

| 块内文件 | 名字 | 被谁引用（外部脚本×处） | 加载期 |
|---|---|---|---|
| state/login.js | `loginSnapshotState` | controllers/plan.js×1 | 无 |
| state/login.js | `restoreLoginSnapshotState` | controllers/plan.js×3 | 无 |
| state/login.js | `setLogin` | app.js×3、controllers/plan.js×1 | 无 |
| state/login.js | `loginEstimateShort` | views/login.js×1 | 无 |
| state/login.js | `loginEstimateText` | views/status-cards.js×1 | 无 |
| state/login.js | `syncLoginDependentView` | app.js×1、controllers/plan.js×5、controllers/refresh.js×5 | 无 |
| views/login.js | `paintLogin` | controllers/plan.js×2、controllers/refresh.js×1、controllers/tick.js×1、state/login.js×2、views/relogin.js×1 | 无 |
| views/login.js | `setBusy` | app.js×2、controllers/plan-events.js×1、controllers/plan.js×11、controllers/refresh.js×1、state/plan.js×2 | 无 |
| views/login.js | `setResult` | app.js×1、controllers/plan-events.js×8、controllers/plan.js×15、controllers/refresh.js×1、state/filters.js×2、views/selection.js×1 | 无 |
| views/login.js | `addLog` | 14 个脚本：app.js×7、controllers/cancel.js×4、controllers/plan-events.js×6、controllers/plan.js×8、controllers/prefs.js×1、controllers/refresh.js×5、controllers/terms.js×1、controllers/tick.js×1、controllers/window.js×2、main.js×1、views/help.js×1、views/log.js×3、views/relogin.js×4、views/settings.js×1 | 无 |
| views/relogin.js | `reloginAutoLive` | state/login.js×2（一处 `typeof` 判断、一处调用，都在函数体内） | 无 |
| views/relogin.js | `loginEntry` | app.js×3 | **有：app.js L251（取值）** |
| views/relogin.js | `receiveReloginState` | app.js×1（`window.onBackend` 里的箭头函数） | 无 |
| views/relogin.js | `wireRelogin` | app.js×1 | **有：app.js L252（调用）** |
| views/relogin.js | `openRelogin` / `beginRelogin` | 块外没有引用（手机页 `m/app.js` 有自己的同名函数，不在扫描范围） | — |

**结论**：加载期引用有两处，都在 `app.js` 顶层，别的脚本里没有：

- `app.js` L251：`$("#btn-login").addEventListener("click", loginEntry);`，加载期就把 `loginEntry` 当值取用。
- `app.js` L252：`wireRelogin();`，加载期直接调用。

`views/relogin.js` 搬成模块之前，这两行要先挪进 `main.js`（与上一块 `applyBand` 挪进 `main.js` 是同一类）；否则模块还没挂回 window，顶层一执行就报未定义。上一版这里写的「没有任何一处是加载期」是错的。

`receiveReloginState` 在 `app.js` 的 `window.onBackend` 里是 `(payload) => receiveReloginState(payload)` 箭头函数（L164），调用期才用，不算加载期。

`setBusy` / `setResult` / `addLog` 三个通用名字现在**定义在 `views/login.js` 里**，外部脚本在函数体里依赖它们（`addLog` 14 个脚本、`setBusy` 5 个、`setResult` 7 个，表一里都没有加载期引用）。搬动时要先把这三个定义搬走或留在原处，否则调用方全断。

## 表二：状态字段的写点与读点

口径：单字段赋值算写；`S.login = {…}` / `S.relogin = {…}` / `reloginRelay = {…}` 这类整体替换单列一行（它同时写掉该对象全部字段）。读点按「文件:函数」列。

| 字段 | 写点 | 读点 |
|---|---|---|
| `S.autoLogin` | state/login.js 的 `reconcileAutoLogin`、`setLogin`；views/relogin.js 的 `receiveReloginState` | tick.js×2、state/login.js×3、views/login.js `paintLogin`、views/plan-panel.js `startBlocker`、views/relogin.js `receiveReloginState` |
| `S.login.result` | app.js `boot`、refresh.js `refresh`/`settleSynchronous`、state/login.js `restoreLoginSnapshotState` | 13 处，含 refresh×1、tick×2、state/login.js×5、views/list.js、views/login.js、plan-panel×1、relogin×1、tour×1 |
| `S.login.ok` | refresh.js `refresh`/`settleSynchronous`、state/login.js×2 | state/login.js `loginSnapshotState`、views/login.js `paintLogin` |
| `S.login.present` | state/login.js×2 | tick×2、state/login.js、views/list.js×2、views/login.js、plan-panel×3 |
| `S.login.checking` | app.js `boot`、refresh.js `refresh`/`settleSynchronous` | refresh.js×3、conflict.js、views/list.js、views/login.js、plan-panel `updateControls`、status-cards |
| `S.login.loginPending` | controllers/plan.js `doLogin`/`handleDone` | refresh.js `autoRefreshDue`、conflict.js、views/login.js、views/plan-panel.js `paintSelected` |
| `S.login.view` | **只由** views/login.js `paintLogin` 写 | conflict.js、plan-panel×5、relogin×1、status-cards |
| `S.login.handoff` | state/login.js `setLogin`、views/relogin.js `receiveReloginState` | state/login.js×2 |
| `S.login.expireAt` / `hours` / `savedAt` / `estimateReason` | state/login.js×2（`restoreLoginSnapshotState`、`setLogin`） | 只在本文件内读（`expiryText`、`loginEstimateShort/Text`、`loginHoursLeft`、`loginSnapshotState`） |
| `S.login.lastCheckAt` / `lastCheckState` | state/login.js `setLogin` | views/status-cards.js×2 |
| `S.login.recoverBlock` / `recovering` | state/login.js `setLogin` | **无** |
| `S.login.preLoginSnapshot` | controllers/plan.js `doLogin`/`handleDone` | 同两函数 |
| `S.relogin.*` | 全部在 views/relogin.js 内写 | 全部在 views/relogin.js 内读（`S.relogin(整体)` 在 `closeRelogin`/`openLogin`/`openRelogin` 被整体替换） |
| `reloginRelay`（含 `live`/`handoff`/`origin`/`flow_id`/`mode`/`state`/`image`） | 顶层初始化、views/relogin.js `receiveReloginState` | views/relogin.js 的 `openRelogin`、`reloginAutoLive`；外部只经 `reloginAutoLive()` |

**哪些字段表达的是同一件事**

- `S.login.ok`、`S.login.result`、`S.login.view.state` 是**同一个登录结论的三种写法**：`ok` 是布尔（`paintLogin` 的 `ok === true/false` 分支用），`result` 是枚举（`none/unknown/valid/expired`），`view.state` 是 `paintLogin` 算出的投影（`ok/warn/bad/none/terms/pending`），计划栏、状态卡、横幅都只读 `view.state`。搬动时保住「只有 `paintLogin` 写 `view`，其他层只读」这条。
- `S.login.hours`、`expireAt`、`savedAt`、`estimateReason` 是同一份估算的四个碎片，只在 `state/login.js` 内读写，出了这个文件没人用——可以整组跟着搬。
- `S.login.handoff`（登录块里「已转人工」）与 `reloginRelay.handoff`（中继快照里「电脑这一场已转人工」）**是两件事**，名字相同、对象不同，搬动时最容易混。
- `S.relogin.open`、`step`、`flowId`、`challengeId`、`way`、`fromLogin` 与 `reloginRelay.*` 是「对话框自己这一场」与「后端中继那一场」两份状态，只有 `openRelogin` / `receiveReloginState` 在两者之间搬运。
- `S.login.recoverBlock`、`S.login.recovering` 只写不读，是死字段（搬动时可以不动，也别在测试里当依据）。

## 表三：反向调用

口径：状态层文件里调用视图层定义的名字；视图层文件里发桥接请求（`api(...)`、直接摸 `window.pywebview`、摸 `PhonePanel`）。

| 类 | 文件 | 行 | 目标 | 所在函数 |
|---|---|---|---|---|
| 状态层调视图层 | state/login.js | 70 | `paintLogin()` | `setLogin` |
| 状态层调视图层 | state/login.js | 137 | `paintLogin()` | `syncLoginDependentView` |
| 状态层调视图层 | state/login.js | 29 | `reloginAutoLive()` | `reconcileAutoLogin` |
| 视图层发桥接请求 | views/relogin.js | 358 | `api("relogin_cancel")` | `closeRelogin` |
| 视图层发桥接请求 | views/relogin.js | 375 | `api("relogin_begin")` ×2（有账号/无账号两条） | `beginRelogin` |
| 视图层发桥接请求 | views/relogin.js | 389 | `api("relogin_auto_once")` | `autoReloginOnce` |
| 视图层发桥接请求 | views/relogin.js | 417 | `api("relogin_submit")` | `submitReloginCode` |

**结论**：方向反过来的就这 3 处状态→视图（其中 2 处是同一个 `paintLogin`），搬成模块后必须改成回调或事件订阅；`views/login.js` 没有任何桥接请求；5 处桥接请求全在 `views/relogin.js`，搬动时这 5 个 `api` 调用要留在编排层（或经注入回调）。

## 表四：controllers/refresh.js 每个函数的归类

口径：函数体内出现登录检查记号（`S.login`、`loginPending`、`checking`、`paintLogin`、`autoLogin`、`relogin`）记登录；出现活动列表记号（`S.items`、`activities`、`applyActivities`、`S.listState`、`render(`、`S.filter`、`signed`、`list_activities`、`S.listPending`）记列表；两者都有单独标出交织行。

| 函数 | 行 | 归类 | 交织 |
|---|---|---|---|
| `applyPrefs` | 2 | 活动列表 | |
| `clearFilters` | 39 | 活动列表 | |
| `notePlanGeneration` | 53 | 计划/通用 | |
| `ingestBootstrapPlan` | 60 | 活动列表 | |
| `noteRoundError` | 96 | 计划/通用 | |
| `settleRefreshBranch` | 105 | 两者都有 | 120（按本轮故障决定撤/留横幅） |
| `refresh` | 122 | 两者都有 | 170-171、182-184、210、217-219（check 与 list 两条分支的收口） |
| `settleSynchronous` | 248 | 两者都有 | 260-262、315-317、336-338（登录结论落地 + 列表合并） |
| `noteListFailed` | 360 | 计划/通用 | |
| `addLogFresh` | 367 | 计划/通用 | |
| `runtimeErrorCopy` | 383 | 活动列表 | |
| `planConfirmedAt` | 393 | 计划/通用 | |
| `noteSignedTasks` | 398 | 活动列表 | |
| `applyConfirmedToItems` | 427 | 活动列表 | |
| `scheduleSignedRefresh` | 451 | 计划/通用 | |
| `applyActivities` | 460 | 活动列表 | |
| `checkRoundOpen` | 531 | **登录检查** | |
| `listRoundOpen` | 535 | 活动列表 | |
| `noteBackgroundListFailed` | 541 | 计划/通用 | |
| `planTaskBlocksAutoRefresh` | 550 | 计划/通用 | |
| `autoRefreshDue` | 567 | 两者都有 | 572-573、581（先看 `S.login.result/loginPending/checking` 再决定刷列表） |
| `autoRefreshTick` | 594 | 计划/通用 | |
| `startAutoRefresh` | 609 | 计划/通用 | |

**结论**：`refresh.js` 里真正只属于登录检查的只有 `checkRoundOpen` 一个函数；`refresh`、`settleSynchronous`、`autoRefreshDue`、`settleRefreshBranch` 四个是两条链路共用，登录结论就在这里写进 `S.login`。搬登录块**不搬 `refresh.js`**，但这四处作为「登录检查的写入方」必须留给编排层。

## 表五：通用名字的使用方与建议落点（只建议，不搬）

口径同表一；声明（`function addLog(` 等）不算。数字是 `scripts/move_facts.py` 的输出。

| 名字 | 使用方（文件×处） |
|---|---|
| `addLog` | 14 个脚本：app.js×7、controllers/cancel.js×4、controllers/plan-events.js×6、controllers/plan.js×8、controllers/prefs.js×1、controllers/refresh.js×5、controllers/terms.js×1、controllers/tick.js×1、controllers/window.js×2、main.js×1、views/help.js×1、views/log.js×3、views/relogin.js×4、views/settings.js×1 |
| `setBusy` | 5 个脚本：app.js×2、controllers/plan-events.js×1、controllers/plan.js×11、controllers/refresh.js×1、state/plan.js×2 |
| `setResult` | 7 个脚本：app.js×1、controllers/plan-events.js×8、controllers/plan.js×15、controllers/refresh.js×1、state/filters.js×2、views/login.js×1、views/selection.js×1 |

**建议**：三个都是「视图层的通用呈现件」，现在寄住在 `views/login.js`。搬登录块时先把它们挪到公共层（`local/ui/shared/` 或 `features/components/` 的视图件），再搬登录块；否则一搬就断开 14 个脚本里的 `addLog` 调用。`setBusy` / `setResult` 同理（分别 5 个、7 个脚本）。
