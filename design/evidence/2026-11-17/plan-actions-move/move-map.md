# 计划栏控制器搬家：每个名字的去处与理由

## 口径

- **只搬不改**：函数体、常量、注释一字不差，只加 `export`、单行具名 `import` 与一行文件头注释。
- 两个控制器（`controllers/plan.js` 532 行、`controllers/plan-events.js` 134 行）整个搬空后**只从磁盘删除**，暂存区一步没碰（`tools/code_shape/check.py` 的 `list_sources` 已先修好，见下文）。
- 段 = 一个顶层函数或常量 + 紧挨着它上方的注释；文件末尾没有归属的注释跟着最后一个函数走（两处都是上一批搬走函数后留下的说明，内容原样保留）。

## 一、四个新文件

| 新文件 | 行数 | 段数 | 放什么 |
|---|---:|---:|---|
| `features/plan/actions-start.js` | 290 | 5 | 开始这一段：`startPlan`、`START_QUERY_TIMEOUT_MS`、`reconcileStart`、`adoptPlan`、`restoreEditedPlan` |
| `features/plan/actions-run.js` | 148 | 13 | 运行中这一段：停止确认、修改计划、重新选择、收尾 |
| `features/plan/actions-events.js` | 139 | 5 | 事件这一段：`presentPlanDone`、`handlePlanDone`、`restartStoppedPlan`、`loggedConclusion`、`showTaskResult` |
| `features/login/actions-browser.js` | 111 | 3 | 浏览器登录：`doLogin`、`handleDone`、`loginFailCopy` |

逐个名字：

| 名字 | 去处 |
|---|---|
| `startPlan` | `plan/actions-start.js` |
| `START_QUERY_TIMEOUT_MS` | `plan/actions-start.js`（只被 `reconcileStart` 用） |
| `reconcileStart` | `plan/actions-start.js` |
| `adoptPlan` | `plan/actions-start.js` |
| `restoreEditedPlan` | `plan/actions-start.js`（计划里写在 `actions-run.js`，见「三、一处偏离」） |
| `cancelTask`、`stopAskOpen`、`openStopAsk`、`closeStopAsk`、`stopAskKey`、`stopPlan`、`confirmStopPlan`、`doStopPlan` | `plan/actions-run.js` |
| `noteStartedFromPhone`、`modifyPlan`、`editPausedLine`、`reselectFailed`、`finishResult` | `plan/actions-run.js` |
| `presentPlanDone`、`handlePlanDone`、`restartStoppedPlan`、`loggedConclusion`、`showTaskResult` | `plan/actions-events.js` |
| `doLogin`、`handleDone`、`loginFailCopy` | `login/actions-browser.js` |

理由：`plan.js` 后半段的 `doLogin`/`handleDone`/`loginFailCopy` 管的是浏览器登录（`handleDone` 还顺带收单场报名 worker 的结果），归登录那一块；其余按「开始 / 运行中 / 事件收口」三段分，跟现有 `features/plan/` 的状态层与视图层同名规则一致。

## 二、被赋值的顶层变量

**0 个**。两个文件的顶层声明只有 `function` 与一个 `const START_QUERY_TIMEOUT_MS`，没有顶层 `let`/`var`，所以不存在「写它的函数必须同文件」的约束。

## 三、一处偏离：`restoreEditedPlan` 落在 `actions-start.js`

计划把 `restoreEditedPlan` 写在 `actions-run.js`。照此落点会形成顶层循环：

```
actions-run → actions-start（restoreEditedPlan 调 startPlan）
actions-start → actions-events（adoptPlan 调 presentPlanDone）
actions-events → actions-run（presentPlanDone 调 editPausedLine）
```

三者首尾相接，模块图守卫报 `cycles`、拼接夹具会直接报错。函数体一字不动的前提下，只能把三个文件里的一处挪位：`restoreEditedPlan` 本就是「把勾选恢复成修改前的场次，再走和重新开始同一条开始流程」，放在 `startPlan` 旁边更顺，于是挪进 `actions-start.js`。挪完依赖成一条直线：`actions-run → actions-start → actions-events`，守卫 `cycles` 为空。

## 四、加载期引用：app.js 顶层那 8 行

搬走之前 `app.js` 顶层直接把这些函数名当回调传给 `addEventListener`，模块里的名字在普通脚本阶段拿不到：

| 行（搬家前） | 元素 | 回调 |
|---:|---|---|
| 382 | `#btn-dock-start` | `startPlan` |
| 410 | `#btn-modify` | `modifyPlan` |
| 411 | `#btn-edit-restore` | `restoreEditedPlan` |
| 412 | `#btn-reselect` | `reselectFailed` |
| 413 | `#btn-finish` | `finishResult` |
| 418 | `#btn-plan` | `startPlan` |
| 419 | `#btn-stop` | `stopPlan` |
| 432 | `#btn-stop-yes` | `confirmStopPlan` |

按 A4 原样挪进 `main.js`，位置在 `installLegacyGlobals()` 之后、`applyBand()` 之前，名字从新模块直接 `import`（不经 `window`），前面加一句为什么挪。

**同一元素上监听器的先后**：逐个核过，这 8 个 id 在桌面端各只有 **1 个** `click` 监听器，全部来自 `app.js` 这两段；没有第二个 `addEventListener`、没有 `onclick` 属性、也没有会命中它们的委托处理器（`#board` 的委托只认 `#plan-prewarn [data-act]`、`#plan-why [data-act]`、`#run-warn [data-act]`，这 8 个按钮都没有 `data-act`；`#plan-tasks` 的委托只认 `.task-cancel`/`.task-verify`）。因此从 `app.js` 挪到 `main.js` 只改了注册时刻（都在用户能点之前），**没有改变任何一个元素上的有效先后**。

另外核过：`app.js` 顶层除这 8 行之外没有别的加载期引用；运行期还有 1 处 `startPlan()`（回车键那条路径，在函数里），走的是挂回的名字。

## 五、模块之间的 import

| 文件 | 加的行 | 为什么 |
|---|---|---|
| `features/login/actions-relogin.js` | `import { doLogin } from "./actions-browser.js";` | 该文件已有 5 处调 `doLogin`，原来靠全局拿 |
| `features/plan/actions.js` | `import { noteStartedFromPhone } from "./actions-run.js";` | 手机开始的计划要写运行记录 |
| `features/plan/actions.js` | `import { showTaskResult } from "./actions-events.js";` | 单场结论要落到结果框 |

这三个文件别的一字没动。

## 六、挂回 window 的名单（以模块图守卫为准）

新挂回的 8 个，逐个写谁在用：

| 名字 | 谁在用 |
|---|---|
| `startPlan` | `app.js`（回车键那条路径）、`main.js`（两个开始按钮） |
| `cancelTask` | `app.js`（`#plan-tasks` 委托里的取消） |
| `stopAskOpen` | `app.js`（键盘处理：弹层开着时 Esc/Tab 交给弹层） |
| `stopAskKey` | 同上 |
| `closeStopAsk` | `app.js`（「继续计划」按钮） |
| `presentPlanDone` | `controllers/refresh.js`（刷新拿到终态时走同一处呈现） |
| `handlePlanDone` | `app.js`（`plan_done` 事件回调） |
| `handleDone` | `app.js`（`done` 事件回调） |

撤掉的 11 个（原来只有这两个控制器在用，搬走后普通脚本已无人用）：`TASK_TERMINAL`、`admitPlanEvent`、`closeResultPage`、`openResultPage`、`planEventOwns`、`selectionSignature`、`planLate`、`reselectableIds`、`stopReasonText`、`loginSnapshotState`、`restoreLoginSnapshotState`。

顺带删掉 `attachPlanGlobals` 函数体第一段重复的注释（与函数上方那段一字不差）。

## 七、跟着改的路径文字与读法

| 文件 | 改了什么 |
|---|---|
| `local/tests/test_ui_contract_plan.py` | 读 `ui/controllers/plan-events.js` → 读 `ui/features/plan/actions-events.js` |
| `local/tests/test_ui_main_window_plan.py` | 读 `controllers/plan.js` → 读 `features/plan/actions-run.js` + `features/plan/actions-start.js`（三句话落在两个文件） |
| `local/tests/test_prerefactor_fixes.py` | 断言说明里的 `plan-events.js:123` → `actions-events.js:132`（照实写新行号） |
| `docs/ARCHITECTURE.md` | 控制器清单去掉 plan 与 plan-events，注明编排已迁成模块 |
| `docs/UI_SPEC.md` | 「文案取自」那句里的 `controllers/plan.js` 换成四个新模块 |

以上断言条件一字未改。另有一条**测试自身的摆设方式**要跟着改：`test_ui_plan_move_smoke.py` 第三条原来调 `openResultPage()` 打开结果页，而这个名字搬完后没有任何普通脚本在用、按 A6 不再挂回，改成直接摆 `S.resultOpen` 并用挂回的 `syncResultSelection()` 补齐选择签名；断言没动。

还有一处 **A8 没点名、但搬完就红**的文件，需要单列：

| 文件 | 症状 | 改了什么 |
|---|---|---|
| `local/tests/test_ui_contract_feedback.py` | 两条用例把「前端脚本联合源码」按位置切片取 `startPlan` 的函数体（`index("function startPlan()")` 到 `index("function cancelTask(")`）。模块按依赖顺序附在拼接源码后面，`actions-run.js`（`cancelTask`）先于 `actions-start.js`（`startPlan`），切出来是空串 | 改成直接读各自所在的文件：`ui/features/plan/actions-start.js` 从 `function startPlan()` 切到 `const START_QUERY_TIMEOUT_MS`，`ui/features/login/actions-browser.js` 从 `function doLogin()` 切到那段「事件」分隔注释 |

两条用例的**断言一句没改**，改的只是「从哪份源码里取那一段」。这是计划 A8 清单漏掉的一个文件：只改路径与读法，不改断言，和 A8 点名的五处同一性质。

## 八、check.py 的修复

`list_sources` 原来照着 `git ls-files --cached` 读，索引里还在、磁盘上已删的文件会去读一个不存在的路径然后崩。前两批搬家的执行方都只好先动 git 索引。这一批在过滤条件里加一条 `(ROOT / f).exists()`，别的一字未动；`test_code_shape.py` 末尾加一条用例：临时 git 仓库里放一个已跟踪文件、从磁盘删掉、不改索引，`list_sources` 不再列出它。

## 九、名单

- `baseline.json`：删掉 `local/ui/controllers/plan.js`（原记录 532 行）；三条函数键改成 `local/ui/features/plan/actions-start.js::startPlan`（117）、`::reconcileStart`（75）、`::startPlan.#anon1`（64），**记录值与理由不变**，没有新增项。
- `ui_layer_allow.json`：没有要删的项（唯一一条 `views/plan-panel.js: runtimeErrorCopy` 仍在用），也没有加项。
- `ui_modules_expect.json`：用 `node tools/code_shape/ui_modules.mjs --expect` 重新生成，五类问题为空。
