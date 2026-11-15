# 登录块搬家地图：每个名字从哪儿到哪儿，按什么归层

- **开工 HEAD**：`fb3e035`。搬之前是三个普通脚本：`local/ui/state/login.js`、`local/ui/views/login.js`、`local/ui/views/relogin.js`。
- **搬之后**：`local/ui/features/login/` 下六个模块（`state.js`、`view.js`、`actions.js`、`state-relogin.js`、`view-relogin.js`、`actions-relogin.js`），加两个普通脚本的落点（`views/result.js` 新建、`views/log.js` 追加）。
- **只搬不改**：57 段顶层声明逐字照搬，`scripts/move_check.py` 对开工 HEAD 逐段核对，57 段全部找到且完全相同，多出来的行全部可归类（见本文件末尾）。

## 归层口径

按计划定的三条规则，函数体一个字不改：

- **状态层**（`state.js`、`state-relogin.js`）：不碰 DOM、不发桥接请求、不用定时器，只读 `S` 与入参算出结论。
- **视图层**（`view.js`、`view-relogin.js`）：只读写 DOM 与 `S`，只调状态层和视图层的名字，不发桥接请求。
- **编排层**（`actions.js`、`actions-relogin.js`）：发桥接请求、用定时器、调 controllers 里的名字、绑事件、开关对话框、写完状态再统一重画。

被重新赋值的顶层变量（`reloginRelay`、`reloginHandoffSeen`、`reloginRefreshedFlow`、`reloginBrowserWatch`、`resultTimer`）各自与读写它的函数放在同一个文件——ES 模块导入的名字只读，跨文件赋值会报错。

## 一、`local/ui/state/login.js`（141 行）

| 名字 | 原行 | 去处 | 归层的理由 |
|---|---|---|---|
| `loginSnapshotState` | 1-8 | `features/login/state.js` | 只读 `S` 拼一个快照，纯推导 |
| `restoreLoginSnapshotState` | 10-19 | `features/login/state.js` | 只写 `S.login` 的字段，不碰页面 |
| `reconcileAutoLogin` | 21-30 | `features/login/actions.js` | 收回自动登录态后要统一重画，属「改完状态再重画」 |
| `setLogin` | 32-78 | `features/login/actions.js` | 统一写入登录结论并重画一串视图 |
| `loginHoursLeft` | 80-89 | `features/login/state.js` | 纯计算 |
| `expiryText` | 91-94 | `features/login/state.js` | 纯计算 |
| `loginEstimateShort` | 96-111 | `features/login/state.js` | 纯计算（时钟不可用时自己兜底） |
| `loginEstimateText` | 113-128 | `features/login/state.js` | 纯计算 |
| `syncLoginDependentView` | 130-141 | `features/login/actions.js` | 按登录结论重画顶栏与计划栏 |

## 二、`local/ui/views/login.js`（173 行）

| 名字 | 原行 | 去处 | 归层的理由 |
|---|---|---|---|
| `paintLogin` | 1-104 | `features/login/view.js` | 只写顶栏胶囊的 DOM |
| `setBusy` | 106-113 | `views/result.js`（新建） | 与登录无关的通用名字，块外 5 处普通脚本在用；留在视图层普通脚本，过渡名单不加项 |
| `resultTimer` | 115 | `views/result.js` | 跟着 `setResult` 走 |
| `setResult` | 117-139 | `views/result.js` | 同上（块外 7 处普通脚本在用） |
| `addLog` | 141-173 | `views/log.js` 末尾 | 同上（块外 14 处普通脚本在用），并到日志视图所在文件末尾 |

其中 `addLog` 的原文末尾还有三行注释（描述 check 时钟），没有代码，随这一段一并搬了过去。

## 三、`local/ui/views/relogin.js`（555 行）

| 名字 | 原行 | 去处 | 归层的理由 |
|---|---|---|---|
| `RELOGIN_PRIVACY_NOTE` | 1-8 | `state-relogin.js` | 是一句固定文案 |
| `reloginRefreshedFlow` | 10-13 | `actions-relogin.js` | 被赋值的顶层变量，只有编排层读写 |
| `reloginRelay` | 15-17 | `actions-relogin.js` | 同上 |
| `reloginHandoffSeen` | 18-19 | `actions-relogin.js` | 同上 |
| `reloginAutoLive` | 21-27 | `actions-relogin.js` | 读 `reloginRelay`，必须同文件 |
| `reloginDialog` | 29-31 | `view-relogin.js` | 取对话框元素 |
| `reloginCase` | 33-39 | `view-relogin.js` | **改了预分**：它读 `autoLoginCredential()`，那个名字定义在视图层的 `views/plan-panel.js`，状态层不能引用上层，见下文 |
| `reloginMask` | 41-45 | `view-relogin.js` | 同上 |
| `reloginCapSub` | 47-49 | `state-relogin.js` | 纯拼字 |
| `reloginUser` | 51-55 | `view-relogin.js` | 同上（读 `autoLoginCredential()`） |
| `reloginFromLogin` | 57-63 | `state-relogin.js` | 只读 `S.relogin` |
| `reloginHead` | 64-108 | `view-relogin.js` | 写标题与副句的 DOM |
| `RELOGIN_LOGIN_ACTS` | 109-112 | `state-relogin.js` | 固定表 |
| `RELOGIN_ACTS` | 113-120 | `state-relogin.js` | 固定表 |
| `RELOGIN_ALL_ACTS` | 121-122 | `state-relogin.js` | 固定表 |
| `reloginWay` | 124-126 | `state-relogin.js` | 只读 `S.relogin` |
| `reloginActs` | 128-133 | `state-relogin.js` | 纯查表 |
| `reloginPaintWay` | 135-158 | `view-relogin.js` | 写方式卡的 DOM |
| `reloginNextReady` | 160-166 | `view-relogin.js` | 只改按钮可点性 |
| `reloginTogglePass` | 168-181 | `view-relogin.js` | 切换密码框的显示 |
| `reloginCodeReady` | 183-187 | `view-relogin.js` | 只改按钮可点性 |
| `reloginError` | 189-195 | `view-relogin.js` | 写红字条 |
| `reloginStep` | 197-222 | `view-relogin.js` | 切步骤、显隐各块 |
| `reloginResetForm` | 224-242 | `view-relogin.js` | 清表单 |
| `reloginBrowserWatch` | 244-245 | `actions-relogin.js` | 被赋值的顶层变量，定时器句柄 |
| `stopBrowserWatch` | 247-249 | `actions-relogin.js` | 清定时器 |
| `watchBrowserLogin` | 251-262 | `actions-relogin.js` | 起定时器、轮询桥接接口 |
| `reloginShowChallenge` | 264-280 | `view-relogin.js` | 把验证码图画到弹窗里 |
| `loginEntry` | 282-288 | `actions-relogin.js` | 决定开哪个对话框（含发请求） |
| `openRelogin` | 290-314 | `actions-relogin.js` | 打开对话框并起轮询 |
| `openLogin` | 316-326 | `actions-relogin.js` | 打开账号密码窗口，发桥接请求 |
| `reloginPickWay` | 328-333 | `actions-relogin.js` | 切方式时可能发请求 |
| `reloginOpenSchoolPage` | 335-340 | `actions-relogin.js` | 发桥接请求打开学校页 |
| `closeRelogin` | 342-360 | `actions-relogin.js` | 关对话框、停轮询、发请求 |
| `reloginRefusal` | 362-370 | `state-relogin.js` | 纯推导（把后端拒绝原因翻成一句话） |
| `beginRelogin` | 372-383 | `actions-relogin.js` | 发桥接请求 |
| `autoReloginOnce` | 385-396 | `actions-relogin.js` | 发桥接请求 |
| `submitReloginForm` | 398-409 | `actions-relogin.js` | 发桥接请求 |
| `submitReloginCode` | 411-424 | `actions-relogin.js` | 发桥接请求 |
| `RELOGIN_FAIL_TEXT` | 426-430 | `actions-relogin.js` | 固定表，只有编排层用 |
| `reloginSucceeded` | 432-446 | `actions-relogin.js` | 关对话框并触发一次刷新 |
| `receiveReloginState` | 448-511 | `actions-relogin.js` | 处理后端中继、可能发请求 |
| `wireRelogin` | 513-555 | `actions-relogin.js` | 绑 20 处事件 |

### 改了预分的一处，理由

`reloginCase`、`reloginMask`、`reloginUser` 三个函数每一处都读 `autoLoginCredential()`。那个名字定义在 `local/ui/views/plan-panel.js`（视图层的普通脚本），而「状态层只能引用状态层与公共层」这条规则对模块同样生效，所以这三个函数不是纯推导，放进 `view-relogin.js`。挪完之后 `actions-relogin.js` 从视图层取 `reloginCase`——编排层可以引用视图层，规则允许。

## 四、入口与挂回

- `index.html` 删掉三行旧 `<script>`，在原来第一行的位置加上 `views/result.js`，其余顺序不变。
- `app.js` 只删掉加载期的两行（登录按钮绑定 `loginEntry`、调 `wireRelogin()`），别的行没动。
- `main.js` 在 `installLegacyGlobals()` 之后、`applyBand()` 之前放这两行，两个名字从 `actions-relogin.js` 直接 import，不经 `window`。

`legacy-globals.js` 现在挂回 15 个名字，每个都还有普通脚本在用：

| 挂回的名字 | 谁在用（普通脚本） |
|---|---|
| `setLogin` | `app.js`、`controllers/plan.js` |
| `syncLoginDependentView` | `app.js`、`controllers/plan.js`、`controllers/refresh.js` |
| `loginSnapshotState` | `controllers/plan.js` |
| `restoreLoginSnapshotState` | `controllers/plan.js` |
| `loginEstimateText` | `views/status-cards.js` |
| `paintLogin` | `controllers/plan.js`、`controllers/refresh.js`、`controllers/tick.js`、`views/result.js` |
| `loginEntry` | `app.js`（`main.js` 走 import，不经 window） |
| `receiveReloginState` | `app.js` |
| `phoneLinkView`、`phoneLinkedNow` | `views/status-cards.js`（手机标识与详情卡，上一批留下） |
| `maskAccount` | `views/plan-panel.js` |
| `OcrPanel`、`paintOcrDownload` | `views/settings.js`（高级功能一行，上一批留下） |
| `termsAccepted` | `controllers/terms.js`、`views/settings.js` |
| `termsLocked` | `app.js`、`main.js`、`controllers/plan.js`、`controllers/refresh.js`、`controllers/terms.js`、`state/conflict.js`、`state/filters.js`、`views/list.js`、`views/plan-panel.js`、`views/status-cards.js`、`views/tour.js` |

`node tools/code_shape/ui_modules.mjs` 的五类报告现在都是空的（没有循环、没有缺 import、没有跨层引用、没有未挂回的名字、没有挂了没人用的名字）。

## 五、逐字核对的结果

`scripts/move_check.py` 的输出：

- 顶层声明段 57 段，**一字不差找到 57 段**，找不到 0 段。
- 新文件里不属于原文的行：import 10 行、`export { ... }` 续行 1 行、`main.js` 接线 2 行、注释 16 行、空行 67 行、开工 HEAD 上本来就有的原有行 58 行。
- **分不进任何一类：0 行**。
