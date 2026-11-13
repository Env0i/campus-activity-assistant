# 代码问题清单

- **基线提交**：`7e2d31c`。所有行号以它为准。
- **执行日期**：2026-11-12（北京时间）。
- **口径**：见 `README.md`。数字都来自 `inventory.md`，可用 `scripts/` 复跑。
- **怎么读**：每条分「事实」和「判断」。事实是代码里数得出、指得到行号的；判断是执行方（Fable 5.2）的意见，包括严重度、影响和建议归属。「建议归属」里的步骤编号对应文末「重构切法」。
- **来源**：第一节「重复的规则」的初筛由子模型做（卡 7），执行方逐条对过行号和原文后才收；子模型报告里有 3 条与代码不符，没有收（见结果文件的 `spot_checks`）。其余各节来自清点脚本。

## 汇总

| 类 | 条数 | 高 | 中 | 低 |
|---|---|---|---|---|
| ① 重复的规则 | 11 | 0 | 7 | 4 |
| ② 跨层调用 | 8 | 3 | 4 | 1 |
| ③ 超大文件与函数 | 9 | 3 | 4 | 2 |
| ④ 隐式状态 | 7 | 3 | 3 | 1 |
| C2 前端全局依赖 | 4 | 2 | 2 | 0 |
| C3 `app.py` 再导出与测试接缝 | 4 | 2 | 2 | 0 |

这份清单没有发现「现在就会让用户看到错误」的缺陷，那一类在 `ui-states.md`。这里的「高」都是「改这一处必然牵动三处以上」。

---

## ① 重复的规则

### R1　组件下载失败原因表，Python 一份、JS 一份　【中】

**事实**

- Python：`local/app.py:119-125` 的 `_DOWNLOAD_FAIL_REASONS`，5 个键，写运行记录时用（`local/app.py:1369`）。
- JS：`local/ui/views/phone.js:99` 的 `PHONE_DOWNLOAD_REASON`，界面红条用（`local/ui/views/phone.js:110`）。
- `local/tests/test_reason_maps.py` 用正则从两份源码里抽键，只比对**键的集合**，不比对文案。

**判断**：两边文案可以各改各的而测试不红；测试靠正则抽源码，表换个写法就要跟着改。建议后端在失败载荷里直接带上原因文案，前端只显示。归属：步骤 1A（组件状态机）。

### R2　发布页地址写了两份　【低】

**事实**：`local/app.py:112` 和 `local/ui/state/store.js:26` 各有一个 `RELEASES_LATEST_URL`，字符串相同。

**判断**：仓库地址变了要改两处。建议前端从 `bootstrap` 取。归属：步骤 2（拆 `Api` 的更新服务时顺手）。

### R3　重试时长选项前端留了一份默认值　【中】

**事实**：`local/ui/state/store.js:152-164` 的 `S.retryOptions` 写死了 6 个选项和默认值，注释说由 `bootstrap.retry_options` 同源覆盖；后端的出处是 `local/app.py:322` 的 `_retry_options_payload`。`local/ui/state/store.js:17` 的 `RETRY_WINDOW_S = 120` 注释写「与 grab.py / app.py 对齐」。

**判断**：有运行时覆盖，平时不会不一致；但 `bootstrap` 失败或晚到时界面用的是前端这一份。建议前端默认值改成空、等 `bootstrap`。归属：步骤 1C（计划栏状态机）。

### R4　`phonePhase` 与 `ocrPhase` 两份组件阶段判定　【中】

**事实**

- `local/ui/views/phone.js:14-25` 的 `phonePhase` 和 `local/ui/views/settings.js:152-162` 的 `ocrPhase`。下载中、校验中、检查中、需要更新、坏了这五个分支逐行同构（`phone.js:17-21`，`settings.js:154-158`）。
- 不同的地方：`phonePhase` 多一个输入 `st.running`，输出多一档 `disabled`；`ready` 在手机访问里映射成 `off`（装好没开），在验证码识别里映射成 `on`；`available` 分别映射成 `disabled` 和 `off`。
- 两个文件里还各有一对逐字相同的小函数：`phoneShow` / `phoneText`（`phone.js:139-152`）和 `ocrShow` / `ocrText`（`settings.js:164-177`）。

**判断**：同一个阶段名（`on`、`off`）在两个组件里含义不同，读代码的人会搞混；新增一个阶段要改两处。建议合成一个「组件阶段」函数，手机访问的「开着」作为它之上的一层。归属：步骤 1A。

### R5　「登录是不是失效了」有三种算法　【中】

**事实**

- 后端：`local/domain/login_rules.py` 的 `check_result` 按 check 的输出分成 `valid` / `none` / `expired` / `unknown` 四态。
- 桌面端：不自己算，读后端给的 `S.login.result`（`local/ui/state/login.js:28`、`45`，`local/ui/views/login.js:16`，`local/ui/views/list.js:269`，`local/ui/views/relogin.js:286`，`local/ui/controllers/tick.js:130`、`149`）。
- 手机页：`local/ui/m/app.js:136-138` 的 `loginRaw` 用三个字段拼：`session_expired`、`session_present === false`、`last_check_state === "expired"`。其中 `session_expired` 在产品代码里只有两处赋值，都是 `False`（`local/domain/login_rules.py:128`、`local/app.py:2411`），所以这个条件永远不成立。

**判断**：手机页没有用后端已经算好的四态，自己又拼了一遍，里面还带着一个死条件。建议手机快照直接带后端的结论，手机页只读它。归属：步骤 1B 和手机页那一步。

### R6　举办时间重叠的判断写了四处　【中】

**事实**：`local/signup_plan.py:80`（`intervals_overlap`）、`local/ui/state/filters.js:214`、`local/ui/state/filters.js:239`、`local/ui/m/app.js:593`，都是半开区间 `a.start < b.end && b.start < a.end`。没有测试比对四处。

**判断**：后端做最终校验、前端做即时提示，各有一份说得通；但桌面端自己就有两份，手机页又一份。规则一旦要改（比如首尾相接算不算冲突），要改四处。建议桌面端合成一个函数；手机页能不能复用取决于 ES Modules 之后两端是否共享模块。归属：步骤 1C。

### R7　「来不及重新登录」的 100 秒写了两份　【中】

**事实**：`local/domain/login_rules.py:18` 和 `local/ui/views/plan-panel.js:514` 各有一个 `LATE_WINDOW_S = 100`。JS 那边的注释写明和后端是同一个数。没有测试比对。

**判断**：改一边忘另一边，界面说「来得及」而后端判「来不及」。建议由 `bootstrap` 下发。归属：步骤 1C。

### R8　「立即报名还是预报名」桌面和手机算法不同，文案也已经不一致　【中】

**事实**

- 桌面端 `local/ui/views/plan-panel.js:131` 用后端给的报名方式（`modeOf(item) === "instant_signup"`）数「立即报名」的场数。
- 手机页 `local/ui/m/app.js:497-499` 自己拿开放时刻和当前业务时间比（`open <= nowS`）。
- 摘要文案：桌面端是「N 场预报名等开放」（`plan-panel.js:133`），手机页是「N 场预报名」（`m/app.js:502`）。

**判断**：两端对同一场活动可能给出不同的归类（例如开放时刻缺失、或已截止的场次）。这是推测，没有构造用例验证。文案不一致是事实。归属：手机页那一步。

### R9　批次说明的文案两端各写一份　【低】

**事实**：`local/ui/views/plan-panel.js:475-476` 和 `local/ui/m/app.js:1084-1085`，「立即报名 N 场」「预报名，同时提交 N 场」「预报名 1 场」三句逐字相同。

**判断**：现在一致，靠人对齐。归属：手机页那一步。

### R10　HTML 转义函数两端各一份，范围不同　【低】

**事实**：桌面端 `local/ui/state/time.js:123-125` 的 `esc` 转义 `&`、`<`、`>`、`"` 四个字符；手机页 `local/ui/m/app.js:430-432` 的 `escape` 多转义一个单引号。

**判断**：桌面端的 `esc` 被 11 个文件用了 115 次。如果有地方把它的结果放进单引号包着的属性里，就有注入风险；这一点没有逐处检查，是推测。建议桌面端补上单引号，两端共用一份。归属：步骤 0。

### R11　「登录后 10 小时」数字写了两份　【低】

**事实**：`local/domain/login_rules.py:23` 的 `LOGIN_ESTIMATE_H = 10.0`；`local/ui/state/login.js:127` 的文案里写死了「按登录后 10 小时估」。

**判断**：后端改了估算时长，界面文案还说 10 小时。归属：步骤 1B。

### 没查完的

- **报名结束原因到文案的映射**：后端 `local/domain/signup_reply.py` 有 `STOP_REASON_LABELS`（经 `stop_reason_label`，第 94-96 行），桌面端 `local/ui/state/task-display.js:62-65`、手机页 `local/ui/m/app.js:886-887` 各自按 `stop_reason` 分支。三处有没有不一致没有逐条比对。
- **列表分组与排序**：桌面端和手机页各有一套，没有逐行比对。

---

## ② 跨层调用

### 后端

#### L1　`application/` 直接 import 了 `infrastructure/`　【中】

**事实**：`local/application/advanced_component_service.py:29` 写的是 `from infrastructure import component_packages as _packages`。同一文件的文档字符串（第 14 行附近）说本模块不 import 网络和进程模块。`test_layer_boundaries` 不拦这一条。

**判断**：其他六个应用层服务都靠端口注入，只有这一个破例。组件包的读写规则因此绑死在应用层里，测试要造真实目录。归属：步骤 2 抽组件服务时改成注入。

#### L2　`infrastructure/` 延迟 import 了顶层的 `runtime_paths`　【低】

**事实**：`local/infrastructure/component_packages.py:101`，在 `_root()` 函数体里 `from runtime_paths import DATA_DIR`，只在调用方没传 `root` 时走到。

**判断**：是个默认值兜底，影响小。归属：步骤 2，改成调用方必须传 `root`。

#### L3　分层测试只守了一半方向　【中】

**事实**：`local/tests/test_layer_boundaries.py:27-30` 的黑名单是 12 个具体模块名，只检查 `domain/` 和 `application/`。下面五个方向出现了也不会红：`domain → application`、`domain → infrastructure`、`application → infrastructure`、`infrastructure → application`、`infrastructure → 顶层`。现状是前两个和第四个各 0 条，第三个 1 条（L1），第五个 1 条（L2）。

**判断**：现在干净是因为人守着，不是测试守着。重构时最容易在这里滑。归属：步骤 0（先补守卫，把 L1、L2 记进白名单）。

#### L4　更新服务从外面改写 `Api` 的 9 处私有字段　【中】

**事实**：`local/application/update_service.py` 把 `Api` 实例当 `state` 参数接进来（第 15 行起的 `UpdateState` 协议），在第 48-54、112、206、264 行直接给 `_update_result`、`_update_installer`、`_update_installer_path`、`_update_staging_path`、`_update_cancelled`、`_updating` 赋值。同一批字段在 `Api` 自己的 `check_update`、`_publish_update`、`update_download`、`update_cancel` 里也赋值（`inventory.md` 第三节）。

**判断**：更新状态的写入点分在两个文件，谁是主人说不清；`import` 方向是对的，但数据方向是应用层改接口层。好处是更新这一块的边界已经用协议画出来了，是拆 `Api` 最容易的第一刀。归属：步骤 2 第一块。

### 前端

#### L5　`state/` 调用了 `views/` 和 `controllers/`　【高】

**事实**：7 个 state 文件引用了 25 个定义在 `views/`（19 个）或 `controllers/`（6 个）的名字，共 62 处（`inventory.md` 第五节「越界引用：state/」）。分三种：

- **state 层在赋值之后直接重画**。`local/ui/state/clock.js:78-81`、`114-116`、`134-137`、`159-162` 四处连着调 `paintClockStatus`、`renderClockPop`、`updateControls`、`render`。`local/ui/state/login.js:70-76`、`137-140` 调 `paintLogin`、`paintRail`、`paintSelected`、`paintBoardActions`、`refreshLoginEmptyState`、`paintClockStatus`、`render`。`local/ui/state/plan.js:51`、`62`、`80`、`106` 调 `setBusy`、`render`。`local/ui/state/filters.js:362`、`372`、`382`、`392` 调 `render`，`381`、`391` 调 `setResult`。
- **state 层调了控制器的动作**。`local/ui/state/plan.js:78` 调 `noteStartedFromPhone`，`103` 调 `noteSignedTasks` 和 `scheduleSignedRefresh`，`104` 调 `showTaskResult`。
- **纯判断放错了层**。`verifiedSigned` 定义在 `local/ui/views/plan-panel.js:614`，被 `state/task-display.js:58`、`state/filters.js:307`、`state/labels.js:61` 使用；`hmsDay`（`plan-panel.js:139`）、`submittingDetail`（`plan-panel.js:1102`）、`effectiveRetryDeadline`（`plan-panel.js:1188`）、`selectionSignature`（`plan-panel.js:901`）同理。`numOrNull` 定义在 `local/ui/controllers/tick.js:162`，`termsLocked` 定义在 `local/ui/controllers/terms.js:13`，都被 state 层使用。`reloginAutoLive`（`views/relogin.js:23`）被 `state/login.js:29` 使用。

**判断**：`docs/ARCHITECTURE.md:180` 写 `ui/state/**` 是「状态仓库 S 与纯投影」，实际不是。迁 ES Modules 时 state 要 import views，views 又 import state，环解不开。第三种最好修（把函数搬到 state 层，不改行为）；第一、二种要等状态机那一步改成「状态变了由订阅方重画」。归属：第三种在步骤 0，前两种在步骤 1。

#### L6　`views/` 调用了 `controllers/`，其中 24 处是直接发桥接请求　【高】

**事实**：13 个 views 文件引用了 15 个定义在 `controllers/` 的名字，共 80 处。其中 `api(…)` 24 处：`local/ui/views/phone.js` 15 处、`local/ui/views/relogin.js` 5 处（第 355、371、385、413 行等）、`local/ui/views/settings.js` 4 处（第 110、183、322、338 行）。`termsLocked` 21 处，`savePrefs` 6 处，`doLogin` 5 处，`refresh` 4 处。

**判断**：`docs/ARCHITECTURE.md:182` 写 views「不发桥接请求」，这三个文件不符合。它们实际是「视图加控制器加状态」三合一（见 H4），也正是状态残留最多的三处：组件、重新登录、设置。归属：步骤 1A、1B。

#### L7　`views/` 直接写状态仓库 73 处　【中】

**事实**：`inventory.md` 第五节「views/ 里直接写 S 的位置」。集中在 `views/relogin.js`（20 处，`S.relogin.*`、`S.login.handoff`、`S.autoLogin`）、`views/tour.js`（12 处）、`views/conflict-tip.js`（9 处）、`views/list.js`（7 处，缓存行元素）。`S.busy` 唯一的写入点在 `local/ui/views/login.js:107` 的 `setBusy`。

**判断**：其中一部分是视图自己的显示状态（哪个浮层开着、哪一行高亮），放在视图里写说得通；但 `S.login.handoff`、`S.autoLogin`、`S.busy` 是业务状态，由视图写就出现了「多处可写」。归属：步骤 1B（登录）、步骤 1C（`S.busy`）。

#### L8　39 个脚本里有 33 个在同一个依赖环里　【高】

**事实**：把函数体里的调用也算作依赖边，文件级强连通分量只有一个，含 33 个文件；不在环里的只有 `led.js`、`state/store.js`、`controllers/update.js`、`controllers/cancel.js`、`controllers/window.js`、`app.js`。直接互相引用的文件有 32 对。只算加载时就执行的顶层代码，没有环：除了 `app.js`，只有 `controllers/tick.js` 在顶层用了 `state/clock.js` 的 `_monoMs`。

**判断**：好消息是加载期没有环，ES Modules 迁移在技术上走得通（环上的引用都发生在函数被调用时）。坏消息是任何一个文件都能间接碰到其他 32 个，「两个功能并行改不撞文件」现在做不到。归属：步骤 0 先把 L5 第三种和 G2 搬掉，环会小很多；剩下的在步骤 1 逐块解。

---

## ③ 超大文件与函数

分布见 `inventory.md` 第一节。本机版 Python 函数 1111 个，P50 12 行、P90 39 行、P99 101 行；本机版前端函数 1008 个，P50 7 行、P90 31 行、P99 107 行。

### Z1　`cmd_grab` 一个函数 1467 行　【高】

**事实**：`local/grab.py:2502-3968`。里面嵌了 28 个函数，合计 856 行，最长的是 `_settle_direct_event`（第 3234 行起，114 行）、`_finalize_once`（第 3530 行起，80 行）、`terminal`（第 2553 行起，75 行）。

**判断**：这些内嵌函数靠闭包共享外层的局部变量，等于一个没有声明字段的对象。报名链路全在里面，不能单独测其中一段。提案把 `grab.py` 排在最后是对的；动之前除了录对照测试，还要先把闭包共享的变量收成一个显式的状态对象，否则一拆就散。归属：步骤 3。

### Z2　`Api` 类 3808 行、153 个方法　【高】

**事实**：`local/app.py:813-4620`。153 个方法里不以下划线开头的有 60 个（pywebview 会把它们都暴露给前端）。`docs/ARCHITECTURE.md:179` 写的是「Api 49 个公开方法」。`__init__` 167 行（第 814-980 行），`_start_plan_inner` 239 行（第 2994-3232 行）。

**判断**：文档里的 49 已经过时。153 个方法按 H1 的字段分组能对上提案列的五个服务，再加窗口托盘和 worker 进程两块。归属：步骤 2。

### Z3　`local/ui/m/app.js` 3357 行，单文件　【高】

**事实**：`PhoneModel`（纯函数）在第 7-1361 行，101 个成员；页面逻辑在第 1367-3357 行，67 个函数、55 个被写入的 `model` 字段、146 处写入。`wire` 163 行（第 3184-3346 行），`ingest` 93 行（第 2621-2713 行），一个函数里写了十几个字段。

**判断**：`PhoneModel` 和页面逻辑已经天然分开，拆成两个模块几乎不用改代码；页面逻辑再按配对、轮询、重新登录、计划四块拆。手机页只有一个文件，任何两件手机页的事都撞。归属：步骤 1 的手机页部分，随 ES Modules 一起。

### Z4　`paintPhoneAccess` 262 行　【中】

**事实**：`local/ui/views/phone.js:437-698`。全仓库最长的 JS 函数。`local/ui/views/settings.js:193-311` 的 `paintOcrDownload` 119 行，结构与它平行（见 `ui-states.md` 组件一节）。

**判断**：一个函数画了手机访问的全部状态，改一个状态要读完整个函数。归属：步骤 1A。

### Z5　`run_plan_task` 359 行、`_start_plan_inner` 239 行　【中】

**事实**：`local/application/plan_service.py:61-419`，`local/app.py:2994-3232`。

**判断**：报名计划的接纳和单场监督各是一个大函数。它们有测试守着（`test_signup_plan`、`test_runtime_bundle`），可以晚点动。归属：步骤 2 最后一块（计划）。

### Z6　`_make_handler` 261 行，类定义在函数里　【中】

**事实**：`local/infrastructure/phone_http.py:129-389`，函数体里定义了 255 行的 `Handler` 类（第 133-387 行，24 个方法）。

**判断**：为了把服务对象闭包进处理器才这么写。不挡并行，可读性差。归属：步骤 2 的手机访问一块，可选。

### Z7　`plan-panel.js` 1467 行、63 个顶层函数　【中】

**事实**：`local/ui/views/plan-panel.js`。被 17 个文件依赖，自己依赖 13 个文件。里面混着 L5 列的 5 个纯判断函数。

**判断**：计划栏、点阵倒计时、横幅、控制按钮都在这一个文件里，`paintBanners`（被 8 个文件调用）和 `updateControls`（被 6 个文件调用）其实是全局的，不是计划栏的。归属：步骤 0 先把纯判断搬走，步骤 1C 再按职责拆。

### Z8　界面契约测试 9682 行，914 处字面断言　【低】

**事实**：`local/tests/test_ui_contract.py` 9682 行，`assertIn` / `assertNotIn` / `assertRegex` / `assertNotRegex` 共 914 处；`test_phone_ui.py` 5466 行、136 处；`test_ui_reliability.py` 2415 行、57 处。`read("ui/app.js")` 出现 56 次。

**判断**：这是提案「目标」第 4 条的规模。所有前端改动都要碰 `test_ui_contract.py` 这一个文件，并行时必撞。归属：步骤 0 先按功能把它拆成几个文件（只搬不改），之后重构到哪块改哪块。

### Z9　停用的旧界面还在仓库里　【低】

**事实**：`local/gui.py` 1116 行，是旧的 tkinter 界面。随包 README 写它「已停用，保留作对照」。`local/launchers/_py.bat:32-33` 的图形界面入口启动的是 pywebview 界面。

**判断**：不参与运行，但占着大文件名单的第四位。定大小参考值时要么删掉，要么进白名单。由用户定。

---

## ④ 隐式状态

### H1　`Api` 上有 23 个标志位在三个以上方法里赋值　【高】

**事实**：`inventory.md` 第三节 B。`Api` 实例共 74 个属性，23 个在 3 个及以上方法里赋值，另有 21 个在 2 个方法里赋值。按功能归类：

| 功能 | 属性（赋值的方法数）|
|---|---|
| 组件与手机访问 | `_phone_channel`（7）、`_advanced_busy`（5）、`_cloudflare_exit_notice`（4）；`_cloudflare` 在 5 个方法里原地修改 |
| 登录与重新登录 | `_pending_save`（6）、`_once_creds_rejected`（5）、`_checking`（3）、`_check_again`（3）、`_last_check`（3）、`_login_wait_pending`（3）、`_relay_creds_source`（3） |
| worker 进程 | `_proc`（6）、`_proc_tree`（6）、`_relay_proc_tree`（4） |
| 更新 | `_updating`（4）、`_update_request_id`（3）、`_update_cancelled`（3），外加 L4 的 9 处外部写入 |
| 活动列表 | `_listing`（3）、`_list_last`（3）、`_pc_list_error`（3） |
| 窗口与托盘 | `_window_minimized`（5）、`_window_hidden`（3）、`_tray`（3） |
| 计划 | `_next_plan_source`（3） |

**判断**：每一组都是一个没有名字的小状态机。`_advanced_busy` 这种「进去置真、每条出口各自置假」的写法（`local/app.py:1440`、`1661`、`1740` 置真；`1358`、`1686`、`1768` 置假）就是漏清退出路径的温床。归属：步骤 2，每抽一个服务就把对应一组字段带走，并改成一个进口一个出口。

### H2　一把锁管所有功能　【高】

**事实**：`Api._lock`（`local/app.py:842`）被 67 个方法读取，`with self._lock` 在文件里出现 98 次。另有 `_credential_lock`（第 843 行，12 个方法）和 `_phone_access_lock`（第 845 行，9 个方法）。`_closing` 在 2 个方法里赋值、30 个方法里读取。忙碌判定 `_is_busy_locked`（第 4428-4438 行）把取消报名、单个 worker、计划、计划进程表四样合在一起看。

**判断**：这是拆 `Api` 的头号难点。服务抽出去以后，锁归谁、两把锁的先后顺序怎么定，要在拆之前写下来；`local/app.py:4431-4432` 的注释说明这里已经为锁顺序返修过。`_closing` 和忙碌判定是跨功能的，应该留在一个很薄的协调对象里，不归任何一个服务。归属：步骤 2 开头先定锁和协调对象的归属，再拆。

### H3　`S` 有 22 个字段没有声明　【中】

**事实**：`local/ui/state/store.js:63-190` 的 `S` 字面量声明了 45 个一级字段；另有 22 个字段只在别的文件里第一次赋值时才出现（`inventory.md` 第五节「S 的字段」）。写入最多的是 `S.relogin`（17 处，第一处在 `local/ui/views/relogin.js:198`）、`S.editing`（4 处，`local/ui/controllers/plan.js:90`）、`S.autoLogin`（4 处，`local/ui/state/login.js:27`）、`S.saveFailures`（4 处）、`S.statusCard`（3 处）、`S.resultSel`（3 处）。

**判断**：「修改中」（`S.editing`）和「自动登录中」（`S.autoLogin`）正是提案点名卡住过的两个状态，它们都不在状态仓库的声明里，读 `store.js` 的人不知道有它们。归属：步骤 0（补声明和注释，不改行为）。

### H4　`PhonePanel` 和 `OcrPanel` 是 `S` 之外的两个小状态仓库　【高】

**事实**：`PhonePanel`（`local/ui/views/phone.js:154`）有 26 个被写入的字段、96 处写入，全在本文件；`views/help.js` 也读它。`PhonePanel.notes` 26 处、`busy` 10 处（5 个函数各自一进一出）、`pending` 4 处、`installing` 2 处（第 793、820 行）。`OcrPanel`（`local/ui/views/settings.js:142`）17 处写入，其中 11 处在 `views/settings.js`、6 处在 `views/phone.js`；`settings.js:200-201` 反过来读 `PhonePanel.installing.relogin_ocr`。

**判断**：两个面板互相读写对方的状态，验证码识别的「安装中」存在手机访问面板的对象里。这是组件一块状态残留的结构原因。归属：步骤 1A，合成一个组件状态模块，两个面板都只读它。

### H5　前端文件顶层的 11 个可变量　【中】

**事实**：`inventory.md` 第五节「S 以外的可变全局」。`local/ui/views/relogin.js` 4 个（第 13、17、19、245 行：`reloginRefreshedFlow`、`reloginRelay`、`reloginHandoffSeen`、`reloginBrowserWatch`），`local/ui/controllers/refresh.js` 3 个（第 391、526、527 行），`local/ui/views/settings.js:78`、`local/ui/views/login.js:115`、`local/ui/controllers/terms.js:39`、`local/ui/controllers/tick.js:2` 各 1 个。

**判断**：`reloginRelay` 存的是后端中继的最近一份快照，`reloginAutoLive` 靠它判断，`state/login.js` 又靠 `reloginAutoLive` 收回「自动登录中」。登录状态因此分在 `S.login`、`S.autoLogin`、`S.relogin` 和这 4 个变量四处。归属：步骤 1B。

### H6　手机页 `model` 有 55 个可变字段　【中】

**事实**：`local/ui/m/app.js:1386` 的 `model`，55 个字段、146 处写入。`model.reloginSubmitting` 10 处写入分在 2 个函数里，`model.notice` 7 处分在 7 个函数里，`model.selected` 6 处分在 6 个函数里。

**判断**：提交中标志有 10 个写入点，每条退出路径都要记得清，和桌面端的问题同构。归属：步骤 1 的手机页部分。

### H7　Python 模块级可变全局 23 个　【低】

**事实**：`inventory.md` 第三节 A。`local/` 下 19 个，`server/` 下 4 个。影响面最大的是 `local/app.py:388` 的 `DEMO`（`main` 里 `global` 赋值，22 个函数读它，测试打补丁 24 次）和 `local/infrastructure/component_packages.py:62` 的 `_STATUS_CACHE`（11 处写入）。其余多是进程内缓存和一次性初始化。

**判断**：缓存类的问题不大。`DEMO` 是一个跨整个 `app.py` 的开关，拆 `Api` 时每个服务都要能拿到它，建议改成构造参数。归属：步骤 2。

---

## C2　前端全局依赖表的结论

完整的表在 `inventory.md` 第五节。

### G1　560 个全局名字，没有命名空间　【高】

**事实**：桌面端 39 个脚本在顶层定义了 560 个全局名字，没有同名冲突。`app.js` 依赖 30 个文件、128 个名字。

**判断**：这是迁 ES Modules 的工作量基数。因为没有同名冲突，过渡期「模块把对外名字挂回 `window`」的做法不会撞名。

### G2　被最多文件依赖的工具函数放在了不相干的文件里　【高】

**事实**：

| 名字 | 定义位置 | 被几个文件引用 |
|---|---|---|
| `addLog` | `local/ui/views/login.js:141` | 13 |
| `setResult` | `local/ui/views/login.js:117` | 6 |
| `setBusy` | `local/ui/views/login.js:106` | 5 |
| `msg` | `local/ui/controllers/tick.js:163` | 9 |
| `numOrNull` | `local/ui/controllers/tick.js:162` | 见 L5、L6 |
| `termsLocked` | `local/ui/controllers/terms.js:13` | 11 |
| `esc` | `local/ui/state/time.js:123` | 11 |
| `paintBanners` | `local/ui/views/plan-panel.js:1371` | 8 |
| `updateControls` | `local/ui/views/plan-panel.js:1224` | 6 |
| `render` | `local/ui/views/list.js:2` | 12 |

**判断**：运行记录写在登录视图里，错误转文字写在每秒心跳的控制器里。13 个文件因此依赖登录视图，这是 L8 那个大环的主要成因之一。把这几个搬到各自该在的小文件，不改行为，环就小一圈。归属：步骤 0。

### G3　`S` 被 32 个文件引用 1344 次，写入 441 处分在 27 个文件　【中】

**事实**：`inventory.md` 第五节「状态仓库 S 的写入」。写入最分散的字段：`S.login` 51 处、6 个文件；`S.plan` 29 处、5 个文件；`S.selected` 12 处、4 个文件；`S.selectionNotice` 8 处、4 个文件。写入集中的：`S.terms` 90 处，81 处在 `controllers/terms.js`；`S.startRequest` 15 处全在 `controllers/plan.js`。

**判断**：`S.terms` 和 `S.startRequest` 说明「一个功能一个写入口」在这个代码库里做得到，条款那一块也确实没有出现在状态残留名单里。`S.login`、`S.plan`、`S.selected` 是要治的三个。归属：步骤 1B、1C。

### G4　`controllers/refresh.js` 是所有功能的交汇点　【中】

**事实**：`local/ui/controllers/refresh.js` 614 行，依赖 19 个文件、40 个名字；写了 `S.login`、`S.plan`、`S.round`、`S.cancel`、`S.runtime`、`S.selected`、`S.listState`、`S.listError`、`S.filter`、`S.prefs`、`S.confirmed`、`S.items`、`S.byId` 等 18 个一级字段。`refresh` 123 行（第 122-244 行），`settleSynchronous` 108 行（第 248-355 行）。

**判断**：登录校验和拉列表两条分支缠在一个函数里。登录状态机和计划栏状态机都要改它，不先拆开就没法并行。归属：步骤 0 把 check 分支和 list 分支拆成两个文件。

---

## C3　`app.py` 再导出与测试接缝的结论

完整的表在 `inventory.md` 第三节 C 和第四节。

### X1　42 个模块级名字被测试打补丁　【高】

**事实**：`local/app.py` 模块级 177 个名字，其中 42 个被 `local/tests/` 打补丁。次数最多的：`PREFS`（30 次、8 个文件）、`PlanCoordinator`（30 次）、`DEMO`（24 次）、`worker_command`（24 次）、`spawn_owned`（16 次）、`SESSION_FILE`（15 次）。42 个里有 6 个是别名（如 `PREFS`、`spawn_owned`、`_kill_tree`），11 个是 import 进来的名字（如 `PlanCoordinator`、`SESSION_FILE`、`DATA_DIR`、`check_latest_release`）。

**判断**：补丁打在 `app` 模块的全局名字上，只有 `app.py` 里的代码按全局名字去取时才生效。把 `Api` 的方法搬进别的模块后，那边取到的是自己模块的名字，补丁就落空了，而且测试不会报错，只会悄悄走到真实实现。拆的时候两条路选一条：服务从构造参数拿这些依赖，`app.py` 在组装时把自己的全局名字传进去（每次调用时现取，不能在构造时取一次）；或者同一提交里把测试改成补到新位置。归属：步骤 2 每一块都要过这张表。

### X2　测试改写了 `Api` 实例的 66 个成员　【高】

**事实**：`inventory.md` 第三节 C。其中方法 23 个（`_emit` 36 次、11 个文件；`_clock_ready` 10 次；`_terms_gate` 10 次；`_ensure_tray` 10 次；`_run` 8 次），属性 40 个（`_last_check` 21 次、`_activities` 20 次、`_plan` 18 次、`_window` 16 次、`_relay` 11 次、`_update_result` 11 次）。还有 3 个名字 `Api` 里找不到（`_endpoint`、`fail`、`ack_lost`，是测试替身自己的成员）。另外有 3 个方法是直接补在 `app.Api` 类上的：`_run`、`_run_plan_task`、`_spawn`。

**判断**：这些下划线名字事实上是测试接口。属性搬进服务后，`api._last_check = …` 这样的测试准备代码会变成给 `Api` 挂一个没人读的属性，同样不报错。归属：步骤 2，每抽一块先搜这张表里属于它的名字，同一提交里改测试。

### X3　手机服务按名字反射调用 `Api` 的公开方法　【中】

**事实**：`local/application/phone_service.py:438` 是 `getattr(self._api, name, None)`，`name` 来自 `local/domain/phone_rules.py:155` 的 `ACTION_PARAMS` 白名单。`Api` 构造时把自己传给它（`local/app.py:902-903`）。

**判断**：`Api` 拆薄以后，白名单里的方法名必须仍然在传进去的那个对象上。归属：步骤 2 的手机访问一块，改成显式的动作表。

### X4　19 种补丁是「经 app 去补别的模块」　【中】

**事实**：例如 `app.updater.download_installer`（5 次）、`app.threading.Thread`（6 次）、`app._advanced_features.feature_ready`（3 次）、`app.subprocess.Popen`（2 次）。

**判断**：这些补的是模块对象本身，代码搬家后仍然生效，不会坏。但 `app.threading.Thread` 这种是全进程生效的，搬家后读测试的人会找不到被测代码在哪。归属：步骤 2，顺手改成补到实际使用的模块。

---

## 文件与函数大小参考值候选（判断，由用户定）

依据是 `inventory.md` 第一节本机版两行的实际分布。超过各档的数量：

| 门槛 | 本机版 Python（1111 个函数 / 55 个文件）| 本机版前端（1008 个函数 / 40 个文件）|
|---|---|---|
| 函数 > 40 行 | 102 个（9.2%）| 70 个（6.9%）|
| 函数 > 60 行 | 53 个（4.8%）| 37 个（3.7%）|
| 函数 > 80 行 | 22 个（2.0%）| 22 个（2.2%）|
| 函数 > 100 行 | 12 个（1.1%）| 13 个（1.3%）|
| 文件 > 400 行 | 15 个 | 10 个 |
| 文件 > 500 行 | 11 个 | 8 个 |
| 文件 > 800 行 | 5 个 | 3 个 |

三档候选：

| 档 | 函数上限 | 文件上限 | 要进白名单的函数 | 要进白名单的文件 | 说明 |
|---|---|---|---|---|---|
| 甲（宽）| 100 行 | 800 行 | 25 个 | 8 个 | 贴着 P99。只拦最离谱的，白名单短，容易守住，但对新代码几乎没有约束 |
| 乙（中）| 60 行 | 500 行 | 90 个 | 19 个 | 约在 P95。白名单较长，要按重构进度逐步清 |
| 丙（严）| 40 行 | 400 行 | 172 个 | 25 个 | 贴着 P90。白名单太长，写理由会流于形式 |

甲档会进白名单的文件：`local/app.py`、`local/grab.py`、`local/infrastructure/component_packages.py`、`local/gui.py`、`local/business_clock.py`、`local/ui/m/app.js`、`local/ui/views/plan-panel.js`、`local/ui/views/phone.js`。

**建议**：

1. **新文件和新函数按乙档**（函数 60 行、文件 500 行）。
2. **存量按甲档列白名单，只许变短不许变长**：检查脚本记下白名单里每一项现在的行数，变长就红，变短就自动更新记录。这样不用一次清完，也不会越改越大。
3. **测试文件不设上限**，只设「单个测试函数 60 行」；`test_ui_contract.py` 这类按功能拆开是为了并行，不是为了行数。
4. **类不单设行数**，改看「一个类在 3 个以上方法里赋值的属性不超过 5 个」。`Api` 现在是 23 个，拆完应该归零。这个指标直接对着状态残留的成因。
5. `local/gui.py` 建议删除而不是进白名单（见 Z9），由用户定。

---

## 重构切法（判断，由用户和指挥会话定）

按提案第 2 节的顺序：先界面状态，再拆 `Api`，`grab.py` 最后。下面每一步写碰哪些文件、能不能并行、之前要补什么。

在步骤 0 之前，建议先修 `ui-states.md` 里标了「先修」的六条缺陷（U1、U2、U3、U4、U7、U9）。它们各是几行的改动，碰的是 `controllers/plan.js`、`controllers/plan-events.js`、`app.js`、`controllers/cancel.js`、`controllers/refresh.js`、`views/relogin.js`、`m/app.js`，不依赖后面任何一步；修完再搬代码，搬的就是对的行为。

### 步骤 0　铺路，只搬不改行为

这一步的目的是让步骤 1 的三块能并行。四件事互不撞文件，可以同时做。

| 编号 | 做什么 | 碰的文件 | 之前要补的测试 |
|---|---|---|---|
| 0a | 把放错层的纯函数搬到 state 层（L5 第三种、G2）：`verifiedSigned`、`hmsDay`、`submittingDetail`、`effectiveRetryDeadline`、`selectionSignature`、`numOrNull`、`msg`、`termsLocked`、`addLog`、`setResult`、`setBusy`、`esc` | `views/plan-panel.js`、`controllers/tick.js`、`controllers/terms.js`、`views/login.js`、`state/time.js`，新增两三个小文件，`index.html` 的脚本顺序 | 不用新测试；契约测试按联合源码断言，搬家不红。搬完跑全量确认 |
| 0b | 补全 `S` 的 22 个未声明字段和注释（H3） | `state/store.js` | 无 |
| 0c | 把 `controllers/refresh.js` 的 check 分支和 list 分支拆成两个文件（G4） | `controllers/refresh.js`，新增一个文件，`index.html` | 先确认 `test_ui_reliability` 里刷新轮次的行为测试覆盖两条分支各自的超时和失败 |
| 0d | 后端分层测试补齐五个方向，前端加一份分层测试，现有越界进白名单（L3） | `local/tests/test_layer_boundaries.py`，新增一个前端分层测试文件 | 本身就是测试 |

0a 和 0c 都要改 `index.html` 的脚本列表，各自只加一两行，合并时注意顺序即可。

另有一件要排在最前面、单独做：**把 `test_ui_contract.py` 按功能拆成几个文件**（Z8），只搬不改。不拆的话，步骤 1 的三块都要改这一个 9682 行的文件。

### 步骤 1　界面状态机，三块

| 编号 | 功能 | 主要文件 | 会撞的地方 |
|---|---|---|---|
| 1A | 组件（手机访问、验证码识别）| `views/phone.js`、`views/settings.js` 里验证码识别的部分；后端要给「检查中超时的原因」时碰 `local/app.py` 的组件方法 | `views/phone.js` 里还有登录恢复的账号密码表单（`paintRelogin` 第 321 行、`paintCredForm` 第 412 行、`goSaveCredentials` 第 937 行、`saveCredentials` 到 `clearCredentials` 第 1089 行起），属于 1B。先把它拆出去 |
| 1B | 登录与重新登录 | `state/login.js`、`views/login.js`、`views/relogin.js`、`views/status-cards.js`、0c 拆出来的 check 文件 | 同上；另外 `views/settings.js` 里有登录一组的显示 |
| 1C | 计划栏 | `views/plan-panel.js`、`controllers/plan.js`、`controllers/plan-events.js`、`state/plan.js`、`state/task-display.js`、0c 拆出来的 list 文件 | `views/plan-panel.js` 里的 `paintBanners`、`updateControls` 是全局的，三块都会调，先在 0a 里搬出去 |

**能不能并行**：做完步骤 0、并且先把 `views/phone.js` 和 `views/settings.js` 按「手机访问 / 组件安装 / 登录恢复 / 设置抽屉」拆开之后，1A、1B、1C 不撞文件。三块都要改的只剩 `app.js`（`window.onBackend` 分发和事件绑定）和 `index.html`，各自只动自己那几行。

**每块之前要补的测试**：给这块现有的每个「进行中」状态补一条行为测试，覆盖 `README.md` 列的八条退出路径里适用的那几条。现有测试里字面断言多、退出路径断言少，先补再改才知道有没有改坏。具体缺哪几条，列在 `ui-states.md` 末尾的「每一块动手前要先补的测试」。

手机页（Z3、H6）建议跟在 1B、1C 后面做：它和桌面端共用后端快照，等桌面端的状态定义稳了再照着改，并在这一步把 `PhoneModel` 拆成独立模块。

ES Modules 迁移按提案是「随前端按功能分目录一步做」。建议放在步骤 1 的每一块里各自迁各自的文件（过渡期挂回 `window`），不要单独开一步全量迁，否则又是一次所有文件都动。

### 步骤 2　拆 `Api`

都改 `local/app.py`，**不能并行**，一次一块，每块一个提交。开工前先定两件事：锁和 `_closing`、忙碌判定归谁（H2）；`DEMO` 怎么传（H7）。

建议顺序和理由：

1. **更新**。边界已经用 `UpdateState` 协议画好（L4），字段 9 个，和别的功能没有共享状态。拿它试出「服务持有状态、`Api` 一行转发、测试同步改」的做法。
2. **组件**（`_advanced_busy`、两个组件服务的回调）。顺手解决 L1。
3. **手机访问**（`_phone_channel`、`_cloudflare*`、`_phone`）。和组件共用 `_phone_access_lock`，所以紧跟在组件后面。解决 X3。
4. **登录恢复**（`_pending_save`、`_once_creds_rejected`、`_relay*`、`_checking` 一组）。字段最多，和 worker 进程的 `_proc` 纠缠，放在后面。
5. **计划**（`_plan`、`_plan_procs`、`_start_requests`）。测试最密（`PlanCoordinator` 被补 30 次），最后做。

**每块之前**：对照 X1、X2 两张表，列出这一块涉及的被补丁名字和被改写成员，决定是保留再导出还是改测试，写进那一块的计划。

### 步骤 3　`grab.py`

1. 录对照测试：同样的输入（假学校回包序列）得到同样的 stdout 行和退出码。`cmd_list`、`cmd_check`、`cmd_cancel`、`cmd_grab` 各一套。
2. 把 `cmd_grab` 里 28 个闭包共享的局部变量收成一个显式的状态对象，函数先原地不动，只改取变量的方式。这一步对照测试必须逐字不变。
3. 再把闭包提成模块级函数或方法，按「取密钥 / 直发 / 点击兜底 / 终态核对 / 登录交接」分文件。

步骤 3 只碰 `local/grab.py` 和它的测试，和步骤 1、2 不撞文件，理论上可以并行。不建议并行：它是报名链路，值得单独一个版本周期来验。
