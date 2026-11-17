# 计划栏剩余段搬家：每个名字的去处与理由

@author Author

开工 HEAD `580c1c4`，分支 `refactor/step1`。**只搬不改**：函数体、常量、注释一字不差，只加 `export`、单行具名 `import` 与一行文件头注释。段 = 一个顶层函数或常量 + 紧挨着它上方的注释；文件末尾无归属的注释跟着最后一个函数走。

预计时长（开工前写）：约 90 分钟——prep 25、move 35、verify-move 30（安全网与全量可重叠）。

## 一、28 个名字的去处与理由

归层规则与前两次搬家相同：不碰 DOM、不发桥接、不用定时器、不调视图与编排名字的纯推导归状态层；只读写 DOM 与 S 字段、只调视图层与状态层名字的归视图层；发桥接、用定时器、绑事件、调编排层名字的归编排层。逐个核对后与前次预分一致：

| 新文件 | 层 | 放什么 |
|---|---|---|
| `features/plan/state-draft.js` | 状态 | `planCheckList`、`autoLoginCredential`、`latestSelectedOpen`、`preStartWarnings`、`startBlocker` |
| `features/plan/view-draft.js` | 视图 | `togglePlace`、`paintChecks`、`paintPrewarn`、`paintWhy`、`paintTickets`、`paintPolicyLine` |
| `features/plan/actions-draft.js` | 编排 | `bindPlaceToggle`（绑 click 事件） |
| `features/plan/state-led.js` | 状态 | `routeDeadline`、`routeTime`、`routeTarget`、`ledSet`、`fmtLed` |
| `features/plan/view-led.js` | 视图 | `paintRoute`、`paintCountdown`、`paintLedLabel`、`paintLedBox`、`paintLed` |
| `features/plan/view-controls.js` | 视图 | `updateControls` |
| `features/plan/view-dock.js` | 视图 | `paintDock` |
| `features/shell/view-band.js` | 视图 | `bandOf`、`applyBand`、`setPlanOpen` |
| `features/shell/view-banners.js` | 视图 | `paintBanners` |

全部 28 个，无遗漏。`views/plan-panel.js` 整段搬空后只从磁盘删，不碰暂存区。文件末尾的「/* 动作 */」注释（748 行）无归属，跟着最后一个函数 `paintBanners` 走。

## 二、被赋值的顶层变量

**0 个**。`plan-panel.js` 顶层只有 28 个 `function`，没有 `let`/`var`/顶层 `const`。函数体内的 `let`（如 `latestSelectedOpen` 的 `best`、`paintLed` 的 `first`）都在各自函数内。R3 天然满足，无「写它的函数必须同文件」约束。

两处经全局 `S` 的隐式耦合（不是 import，运行期靠调用先后）：`S.preWarnCount`（`paintChecks` 写、`updateControls`/`paintDock` 读）、`S.band`/`S.short`/`S.planOpen`（`applyBand`/`setPlanOpen` 写、`paintDock` 读）。搬后调用链不变，main.js 里 `applyBand()` 仍在 `installLegacyGlobals()` 之后，行为不变。

## 三、模块间 import 与循环检查

内部依赖（只列有依赖者）：

| 函数 | 调用的（28 个里的）其它名字 |
|---|---|
| `paintChecks` | `preStartWarnings`、`paintPrewarn`、`planCheckList` |
| `preStartWarnings` | `latestSelectedOpen`、`autoLoginCredential` |
| `paintWhy` | `startBlocker` |
| `paintRoute` | `routeTarget`、`routeDeadline`、`routeTime` |
| `paintLed` | `paintLedBox`、`ledSet`、`paintLedLabel`、`fmtLed` |
| `updateControls` | `paintWhy`、`paintDock` |
| `applyBand` | `bandOf`、`setPlanOpen`、`paintDock` |
| `setPlanOpen` | `paintDock` |
| `paintDock` | `startBlocker` |

其余 19 个内部依赖为 0（`bindPlaceToggle` 自己内联翻转 aria，不调 `togglePlace`）。

模块级依赖边（全单向，view/actions → state）：
- `view-draft → state-draft`
- `view-dock → state-draft`
- `view-led → state-led`
- `view-controls → view-draft`、`view-dock`
- `view-band → view-dock`

**无顶层循环**。两个 state 模块与 `actions-draft`、`view-banners` 出度为 0。新模块之间只加需要的具名 import。

## 四、加载期引用（R4）

只有两处，与计划甲一致：
1. `app.js:168` 顶层 `bindPlaceToggle();` —— 原样删掉，挪进 `main.js` 的 `installLegacyGlobals()` 之后、`applyBand()` 之前，加一句为什么挪，`bindPlaceToggle` 从 `actions-draft.js` import。
2. `main.js:35` 已有 `applyBand();` —— 调用那一行不动，`applyBand` 改为从 `view-band.js` import。

逐个核过普通脚本（含 led.js）：除这两处外，`togglePlace`/`paintBanners`/`updateControls`/`paintLed` 等 28 个名字在普通脚本里都包在回调或 `render()` 里，是运行期引用，经挂回 window 拿到。R4 的停下条件不触发。

`RUNTIME_ERRORS`/`runtimeErrorCopy` 的 6 处引用全在函数体内（app.js:113、refresh.js:97/384、tick.js:143、plan-panel.js:665、两个模块 L40/L73），**无加载期引用**，R2 的停下条件不触发。

## 五、RUNTIME_ERRORS 与 runtimeErrorCopy（R2）

`controllers/refresh.js` 的 `RUNTIME_ERRORS`（L377-381，连同上面那行注释）与 `runtimeErrorCopy`（L383-385）逐字搬进 `features/shell/state-runtime.js`；refresh.js 只删这两段，别的一字不动。

引用者处理：
- 普通脚本 `app.js`、`controllers/refresh.js`、`controllers/tick.js`、`views/plan-panel.js`（搬前）靠全局 → `legacy-globals.js` 挂回 `window.RUNTIME_ERRORS`、`window.runtimeErrorCopy`。
- 模块 `features/login/actions-browser.js`（L40）、`features/plan/actions-start.js`（L73）各补 `import { RUNTIME_ERRORS } from "../shell/state-runtime.js";`。
- `runtimeErrorCopy` 无模块引用者，只需挂回。

分层白名单 `views/plan-panel.js: runtimeErrorCopy` 那一组整组删掉（paintBanners 搬成视图层模块后，视图层引用状态层名字不算跨层）。

## 六、要补 import 的已有模块（R5）

| 文件 | 加的 import（来自新位置） | 为什么 |
|---|---|---|
| `features/login/actions.js` | `paintBanners` ← shell/view-banners.js | 登录态变了要重画横幅 |
| `features/login/view-relogin.js` | `autoLoginCredential` ← plan/state-draft.js | 重新登录对话框读三件事 |
| `features/phone-access/actions.js` | `paintCountdown` ← plan/view-led.js | 手机动作更新倒计时 |
| `features/phone-access/view.js` | `paintCountdown` ← plan/view-led.js | 手机视图更新倒计时 |
| `features/plan/actions-run.js` | `setPlanOpen`、`updateControls` ← shell/view-band.js、plan/view-controls.js | 收尾/停止后重算门禁与计划条 |
| `features/plan/actions-start.js` | `paintBanners`、`updateControls` ← shell/view-banners.js、plan/view-controls.js | 开始前后重画横幅与门禁 |
| `features/plan/view.js` | `paintCountdown`、`paintPolicyLine`、`paintTickets` ← plan/view-led.js、plan/view-draft.js | 计划栏重画时调这几段 |
| `features/login/actions-browser.js` | `RUNTIME_ERRORS` ← shell/state-runtime.js | 见第五节 |
| `features/plan/actions-start.js` | `RUNTIME_ERRORS` ← shell/state-runtime.js | 见第五节（同文件两行 import） |

每个文件只加这些 import 行，别的一字不动。

## 七、挂回 window（R6，以模块图守卫为准）

普通脚本里用到、要新挂回的名字（逐个谁在用）：

| 名字 | 谁在用 |
|---|---|
| `paintBanners` | app.js、controllers/tick.js、views/plan-panel.js→搬后无普通脚本用？以守卫为准 |
| `updateControls` | app.js 及大量普通脚本回调 |
| `paintCountdown` | controllers/tick.js、views/status-cards.js 等 |
| `setPlanOpen` | app.js（`#btn-dock-open`/`#btn-plan-back` 回调） |
| `applyBand` | main.js（已 import，不需挂回） |
| `paintRoute`、`paintLed`、`paintDock` 等 | render() 里按档调用 |

具体挂回清单在 move 阶段以 `node tools/code_shape/ui_modules.mjs` 的「未挂回/挂了没人用」报告逐项校准：普通脚本用到却没挂回的必挂，挂了没人用的不挂。计划栏名字进 `attachPlanGlobals`；横幅、分档、组件错误文案另起 `attachShellGlobals`（`installLegacyGlobals` 保持不超 60 行）。

## 八、跟着改的读法与路径（R7，断言一字不改）

按文字切源码的测试，搬家后模块重排使联合源码里函数顺序变化，切片的起止锚点可能失效（切空或切错）。这些切片要在 move 阶段改读各自所在的新文件，断言一字不动：

| 文件 | 命中 | 改法 |
|---|---|---|
| `test_ui_contract_feedback.py:597` | `updateControls(` 到「横幅」注释 | 起止锚点分落 view-controls.js 与 view-banners.js → 改为读 `view-controls.js` 单文件、切到文件尾 |
| `test_ui_contract_list.py:207/218` | `paintRoute()` 到 `routeDeadline` | 分落 view-led.js 与 state-led.js → 改为读 `view-led.js` 单文件、切到文件尾；`routeDeadline` 的断言改读 `state-led.js` |
| `test_ui_contract_login.py:172` | `updateControls(` 到 `paintBanners` | 同上拆分 |
| `test_ui_contract_login.py:220` | `preStartWarnings(` 到 `paintPrewarn` | 分落 state-draft.js 与 view-draft.js → 读 `state-draft.js` |
| `test_ui_contract_plan.py:349` | `paintRoute()` 到 `routeDeadline` | 同 list |
| `test_ui_contract_settings.py:192/221` | `updateControls(` 到 `paintBanners` | 同 feedback |

注：`test_ui_contract_login.py`、`test_ui_contract_settings.py` **不在本任务的 allowed_paths**。若搬后这两条变红，按 R11 停下条件处理（记 plan_defect），不擅自越界改；执行时会先试跑确认是否真的变红——联合源码若恰好仍保持顺序则可能不红。

按路径读的测试（上下文丁 + 本表）：
- `test_ui_main_window_plan.py:235/236` 读 `views/plan-panel.js` 找睡眠那句（在 `preStartWarnings`）→ 改读 `features/plan/state-draft.js`。
- `test_retry_phone_policy.py:528` 文档字符串、`tools/qa_runtime_reliability.py` 注释、`docs/UI_SPEC.md:711`、`docs/ARCHITECTURE.md` 的路径文字 → 改为新位置。

`read("ui/app.js")` 在夹具里就是「前端脚本联合源码」，绝大多数按文字切联合源码的用例搬家后仍能从拼接文本找到（函数都还在，只是模块顺序变）。只有**跨文件起止锚点**那几条会切坏，列在上表。

## 九、真加载冒烟（R8）

已在 `test_ui_plan_move_smoke.py` 末尾追加三条（已有 7 条不动），在开工代码上 10/10 通过：
1. `test_place_toggle_flips_expanded_after_native_load` —— 真加载后地点开关委托接上并翻转 aria-expanded（宽窄两档）；副本删掉 app.js 的 `bindPlaceToggle();` 后两档都红。
2. `test_medium_dock_opens_and_returns` —— 900×820 中点查看计划/返回列表开合。
3. `test_runtime_error_shows_component_banner` —— 组件错误横幅（宽窄两档）。

## 十、名单与文档（R10）

- 大小名单 `baseline.json`：删 `views/plan-panel.js` 文件项；三条函数键 `::paintLed`/`::paintBanners`/`::updateControls` 改新路径，记录值与理由不变；`controllers/refresh.js` 文件项按实测改小。无新增。
- 分层白名单 `ui_layer_allow.json`：只删 `views/plan-panel.js` 那一组，不加项。
- `ui_modules_expect.json`：用 `node tools/code_shape/ui_modules.mjs --expect` 重新生成。
- `docs/UI_SPEC.md` 5.19：那句过期的「下一批接」改成实情；路径文字更新。
- `docs/ARCHITECTURE.md`：前端目录处指向 plan-panel.js 的路径改新位置。

## 十一、执行时核对发现的落点调整与计划缺陷

**落点调整（R1 授权）**：预分把 `planCheckList`、`startBlocker` 归 `state-draft.js`，但两者都用 `views/terms.js` 的 `termsUpdateMode`（`typeof termsUpdateMode === "function"`）。搬进状态层后 `test_ui_layers.py` 报 state→views 跨层引用。按 R1「执行时逐个核对、改动在 move-map 写理由」，把这两段改归视图层 `view-draft.js`（视图层引用同层普通脚本名字不算跨层），函数体一字未动；`view-dock.js` 的 `startBlocker` import 相应改从 `view-draft.js`。落点调整后模块图五类问题全空、分层测试通过。

**计划缺陷（plan_defect，交规划方）**：`test_ui_contract_login.py` 有两条按文字切源码的用例（`test_start_button_requires_valid_or_demo`、`test_login_expiry_check_present`）在搬后变红——前者切 `updateControls → paintBanners`、后者切 `planCheckList → autoLoginCredential`，两对锚点搬到不同模块、顺序由依赖图强制，必须改读法。R7 要求改「所有按文字切源码的测试」读法，但 `scope.allowed_paths` 与 move 任务 `allowed_paths` 都漏列了 `test_ui_contract_login.py`。按 R11「allowed_paths 以外的文件变了就停下」，本执行未改该文件，两条用例如实报红，交规划方裁决是否把它加进 allowed_paths。

**假绿说明**：`test_ui_contract_settings.py` 两条 `updateControls → paintBanners` 切片用不带 start 的 `index`，搬家后切出空串，但断言是 `assertNotIn`，空串恰好仍过（测试未红）。这不是本批引入的行为回归，是既有测试写法对新模块顺序不敏感；该文件同样不在 allowed_paths，未改。

## 十二、搬后补改的切片读法（只改读法，断言一字未动）

按文字切源码的契约切片，搬家后起止锚点分落不同模块、或切到了别的函数，共 7 处。下表每行一处，断言与断言消息一字未动。

| 文件与用例 | 原来怎么截 | 改成怎么截 | 为什么 |
|---|---|---|---|
| `test_ui_contract_login.py` / `test_start_button_requires_valid_or_demo` | 联合源码，`function updateControls(` 到 `function paintBanners` | `features/plan/view-controls.js`，从 `export function updateControls(` 截到文件尾 | updateControls 与 paintBanners 分落两文件，联合源码里 paintBanners 在前，切片为空 |
| `test_ui_contract_login.py` / `test_login_expiry_check_present`（planCheckList 段） | 联合源码，`function planCheckList(` 到 `function autoLoginCredential` | `features/plan/view-draft.js`，从 `export function planCheckList(` 截到同文件的 `export function startBlocker` | planCheckList 在 view-draft.js，autoLoginCredential 在 state-draft.js，切片为空 |
| `test_ui_contract_login.py` / `test_login_expiry_check_present`（preStartWarnings 段） | 联合源码，`function preStartWarnings(` 到 `function paintPrewarn` | `features/plan/state-draft.js`，从 `export function preStartWarnings(` 截到文件尾 | paintPrewarn 在 view-draft.js，切片为空 |
| `test_ui_contract_settings.py` / `test_lifecycle_display_and_estimate_reminder`（门禁） | 联合源码，`function updateControls(` 到 `function paintBanners` | `features/plan/view-controls.js`，从 `export function updateControls(` 截到文件尾 | 切片为空串，`assertNotIn` 空跑即过，是假绿 |
| `test_ui_contract_settings.py` / `test_tour_does_not_gate_login_or_start`（门禁） | 同上 | 同上 | 同上；截对之后门禁里的 `S.tour` 才真正被检查 |
| `test_ui_contract_list.py` / `test_route_uses_independent_station_checkpoints` | `features/plan/view-led.js`，从 `export function paintRoute()` 截到文件尾 | 同文件，截到 `export function paintCountdown(` | 文件尾还有 paintCountdown、paintLed 等，范围过大；现在只截 paintRoute 本身 |
| `test_ui_contract_plan.py` / `test_paint_route_has_no_fake_time_fallbacks` | 同上 | 同上 | 同上 |
