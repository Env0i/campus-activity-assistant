# 对抗审计：第一轮材料

- **执行模型**：WorkBuddy，底层模型 DeepSeek-V4.1-Flash（与被审材料的执行方 Fable 5.2 不同厂商、不同模型）
- **基线**：`7e2d31c`。全部代码按 `git archive 7e2d31c` 导出的副本读，未读工作区里的 `local/**`
- **被审文件**：`README.md`、`inventory.md`、`state-trace.md`、`code-issues.md`、`ui-states.md`，以及 `design/proposals/engineering-refactor.md` 第 4 节末尾的「审计结果」段
- **口径**：本文件只找错与漏，不改被审文件，不复述原文，不写赞同意见
- **方法**：先按 C4 自己从代码里列出每个功能的状态变量与等待操作（附录 A），再拿 `state-trace.md` 比对找漏项；数字自己写脚本重算（`ast` 与 `git grep`），只在对比口径时看被审脚本；提案第 4 节的每个数字逐个重算
- **严重度**：阻断（照着写计划会改错或漏改）/ 重要（结论要改但不影响切法）/ 次要（措辞、行号偏一两行、小结数字）

## 结论

| 严重度 | 条数 | 编号 |
|---|---|---|
| 阻断 | 0 | — |
| 重要 | 3 | A1–A3 |
| 次要 | 3 | A4–A6 |

第一轮的硬数字**全部可复现**：文件行数、函数分位数、`Api` 的 153 个方法与 23 个标志位、`_lock` 被 67 个方法读、39 个脚本 33 个同环、state 层 62 处越界、views 层 24 处 `api()`、42 个被打补丁的模块级名字、66 个被改写的 `Api` 成员、11 项状态残留的 3/1/5/1/1 分布，均与清单一致。问题集中在**覆盖面的边界**（哪些刷新算程序发起、哪些字段算状态）和**一处并行切法**，不在数字本身。

---

## 一、重要

### A1　程序自己发起的静默刷新不是四处，是六处

**原文说什么**：`state-trace.md:218-224` 与 `ui-states.md:32`（U2）都说「程序自己发起的静默刷新」是四处，全部列在 `state-trace.md:220-223`：

- 窗口重新可见 `local/ui/app.js:641`
- 取消报名成功后 `local/ui/controllers/cancel.js:52`
- 计划结束后补一次权威列表 `local/ui/controllers/refresh.js:456`
- 重新登录成功后 `local/ui/views/relogin.js:438`

并据此在 `code-issues.md:402` 把「先修六条」的修复范围写成「这四处改成后台轮」。

**代码实际是什么**：`refresh` 的第一个参数是 `quiet`，后台标志在第二个参数的 `options.background` 里（`local/ui/controllers/refresh.js:122-124`：`function refresh(quiet, options) { const background = !!(options && options.background);`）。全仓只有 `local/ui/controllers/refresh.js:602` 的 `refresh(true, { background: true })` 真正走了后台轮。其余 `refresh(true)` 只是 quiet，`background` 仍为假，照样进 `S.listState = "loading"`（`refresh.js:160-163`）、失败照样清 `S.items`/`S.byId`/`S.selected`（`refresh.js:480-482`）。

按「程序发起、不是用户点的、列表可能非空」这一条筛，除上面四处外还有两处：

| 位置 | 谁发起 | 会清空什么 |
|---|---|---|
| `local/ui/controllers/plan-events.js:123` | 单场报名失败后 400ms 复查（`S.recheckPending` 守卫），程序发起 | 前台轮失败 → `S.items`、`S.byId`、`S.selected` 全清 |
| `local/ui/controllers/plan.js:471` | 浏览器登录成功后 `refresh(true)`，程序跟进 | 同上；登录前那份列表会被清掉 |

另有 `local/ui/controllers/terms.js:354`、`414` 与 `local/ui/app.js:84` 三处也是 `refresh(true)`，但前者发生在条款刚通过、列表本就没加载过，后者在启动时列表为空，实际影响很小，可只作说明。

**文件:行号**：被审材料 `state-trace.md:218-224`、`ui-states.md:32`；代码 `local/ui/controllers/refresh.js:122-124,160-163,480-482,602`、`local/ui/controllers/plan-events.js:123`、`local/ui/controllers/plan.js:471`

**类别**：R2 漏项 + R1 数字算错（「四处」）

**影响**：按现清单修 U2，修完仍是「计划里有场次失败后」和「浏览器登录成功后」两条路径会清空列表和勾选——正是用户抱怨的同一类症状。修复范围要改成六处（可注明后两处影响很小），或统一改成「程序发起一律传 `{background:true}`」。

### A2　组件一节的 C4 覆盖不全：26 个字段只列了 5 个，等待操作也漏了两项

**原文说什么**：`README.md:112-126` 的 C4 要求「每节列出：所有状态（前端变量与后端 `_state` 字段都算）……每个等待中的操作有没有『进行中』显示和失败显示，失败后能不能重试」。

`state-trace.md:107-119` 的组件状态表只列了 `PhonePanel.busy`、`PhonePanel.pending`、`PhonePanel.installing[key]`、`OcrPanel.busy`、`PhonePanel.pollTimer`、`PhonePanel.notes.*` 六项；`inventory.md:1132` 自己的清点是 `PhonePanel` **26 个被写入字段、96 处写入**，`OcrPanel` 5 个字段 17 处写入。

**代码实际是什么**：以下字段都直接决定界面显示或按钮可用性，但组件一节没有逐条给进出口：

| 字段 | 决定什么 | 位置 |
|---|---|---|
| `PhonePanel.state` / `location` | 组件状态与安装位置文案 | `local/ui/views/phone.js:201,220-223` |
| `PhonePanel.lastDownload` | 红条原因与「重新下载」按钮 | `local/ui/views/phone.js:1013` 一带 |
| `PhonePanel.codeLeft` / `tickTimer` / `pollTicks` | 配对码倒计时、轮询节奏 | `local/ui/views/phone.js:243-266` |
| `OcrPanel.error` / `note` / `lastDownload` | 验证码识别面板的覆盖错误与说明 | `local/ui/views/settings.js:210-212,317-329` |

等待操作也少了两项，两处都有进行中与失败显示，属于 C4 要求回答的三问：

- **启用组件**：`local/ui/views/phone.js:844-862`，`PhonePanel.busy` 进出在 `846`/`855`（finally），失败写 `notes.feature`；
- **清除保存的账号**：`local/ui/views/phone.js:1167-1177`，无 busy 位，但结果写 `credNote`/`credNoteTone`，失败句「清除没有完成」。

**文件:行号**：被审材料 `state-trace.md:107-119,133-142`；代码 `local/ui/views/phone.js:201,220-223,243-266,844-862,1167-1177`、`local/ui/views/settings.js:210-212,317-329`、`inventory.md:1132`

**类别**：R2 漏项

**影响**：步骤 1A 要做「一台组件状态机，两个组件各一个实例」。少列 20 来个字段，做计划时容易把 `lastDownload`/`OcrPanel.error` 这两条覆盖链漏在状态机外面——它们正是现在两个面板画得不一样的原因（`desktop-recheck.md` 第三节已指出 settings.js 多一层 `OcrPanel.error` 覆盖）。

### A3　「1A、1B、1C 不撞文件」与同一段的「三块都要改 app.js」矛盾

**原文说什么**：`code-issues.md:427`：「做完步骤 0、并且先把 `views/phone.js` 和 `views/settings.js` 按『手机访问 / 组件安装 / 登录恢复 / 设置抽屉』拆开之后，**1A、1B、1C 不撞文件**。三块都要改的只剩 `app.js`（`window.onBackend` 分发和事件绑定）和 `index.html`，各自只动自己那几行。」

**代码实际是什么**：把 `code-issues.md:421-425` 列的主要文件求交集：

| 块 | 文件 |
|---|---|
| 1A | `views/phone.js`、`views/settings.js`（组件部分） |
| 1B | `state/login.js`、`views/login.js`、`views/relogin.js`、`views/status-cards.js`、0c 拆出的 check 文件 |
| 1C | `views/plan-panel.js`、`controllers/plan.js`、`controllers/plan-events.js`、`state/plan.js`、`state/task-display.js`、0c 拆出的 list 文件 |
| **交集** | **`app.js`、`index.html`**（三块全有） |

而 `app.js` 的 `window.onBackend` 是**一个对象字面量**（`local/ui/app.js:89-150`）：1B 要改 `check` 分支（`95-129`），1C 要改 `plan`/`task`/`plan_done`（`138-140`），两处只隔 9 行，三块并行时在这个对象里必然互相踩，不是「各自只动自己那几行」那么松。

**文件:行号**：被审材料 `code-issues.md:419-427`；代码 `local/ui/app.js:89-150`

**类别**：R3 判断站不住（并行切法）

**影响**：照着排并行，三块会同时改 `app.js` 与 `index.html`。建议把结论改成「文件级交集两个：`app.js`、`index.html`；这两处不并行，三块按顺序合并，或先把 `window.onBackend` 按功能拆成三个注册函数再并行」。

---

## 二、次要

### A4　`refresh.js:479-481` 的清空行号偏一行

**原文说什么**：`state-trace.md:218`：「`controllers/refresh.js:479-481` 清 `S.items`、`S.byId`、`S.selected`」。

**代码实际是什么**：479 是 `return;` 所在分支的收尾 `}`，三个清空在 480–482：`S.items = [];`（480）、`S.byId = new Map();`（481）、`S.selected.clear();`（482）。

**文件:行号**：`state-trace.md:218`；`local/ui/controllers/refresh.js:480-482`

**类别**：R1（行号偏一）；结论本身成立。

### A5　H5 的「11 个可变全局」与 inventory 的「13 个」不一致

**原文说什么**：`code-issues.md:273`：「前端文件顶层的 11 个可变量」，列出 relogin 4 + refresh 3 + settings/login/terms/tick 各 1 = 11。

**代码实际是什么**：`inventory.md:1100` 的同一张表是 **13 个**：上面 11 个再加 `PhonePanel`（`views/phone.js:154`）与 `OcrPanel`（`views/settings.js:142`）两个被改写属性的 `const` 对象。两个对象在 H4 另算，但 H5 没有说明「不含 H4 那两个」，读者对不上账。

**文件:行号**：`code-issues.md:271-275`；`inventory.md:1100-1120`

**类别**：R4 自相矛盾（口径未注明）

### A6　inventory 的「74 个 `Api` 属性」无法用同一口径复现

**原文说什么**：`inventory.md:374`：「`Api` 实例属性（`local/app.py`，153 个方法，74 个属性）」，并给分布「0 个方法：6、1 个：24、2 个：21、3 个：13、4 个：3、≥5 个：7」。

**我算出来是什么**：按 README 的口径（`self._x` 被赋值的方法数、嵌套算外层），用 `ast` 扫 `Api` 的 153 个顶层方法，得到 **68 个**有赋值的属性，分布是 1 个方法 24、2 个 21、3 个 13、4 个 3、≥5 个 7（合计 68）——与 74 的差正好是「0 个方法」那 6 个。这 6 个应当是从 `Api` 方法之外写入、或只读不写的属性，但清单没给名单，复跑对不上。

同一个口径下，**23 个标志位与 `_lock` 的 67 个读方法完全复现**，所以这条不影响 H1 的结论，只是开头那个总数需要补一句「其中 6 个不在 `Api` 方法里赋值」或给出名单。

**文件:行号**：`inventory.md:374-376`；`local/app.py:813-4620`

**类别**：R1（数字不可复现）。建议 Codex 确认 74 的定义后补名单。

---

## 三、「全部复核」三类的完成记录

### 3.1 所有标「高」的条目（13 条，全部复核）

| 条目 | 结论 | 复核方式 |
|---|---|---|
| `ui-states.md` U1 | 成立 | `app.js:414` 绑 `startPlan`；`plan.js:353` 存 ids；`startPlan` 读 `S.selected`；停止失败 `plan.js:389`、`395` 只清 `S.stopping`；`plan-events.js:17` 条件只认 `stopped`；`plan-panel.js:124,270` 显示「修改中」 |
| `code-issues.md` L5 | 成立，数字全对 | 62 = 表内 32 行计数之和；25 个名字、7 个 state 文件、19 views + 6 controllers 逐个点算；抽查 `state/clock.js:78-81`、`plan.js:51,78,80,103,104,106`、`login.js:29,70-76,137-140`、`filters.js:343,362,381,391` 全部对得上 |
| `code-issues.md` L6 | 成立 | `api(` 在 views 里共 24 处：phone 15、relogin 5（355/371/385/413）、settings 4（110/183/322/338），与清单逐处一致 |
| `code-issues.md` L8 | 成立（内部自洽） | 33 个文件名单逐个点数为 33；39 − 6（不在环里）= 33 |
| `code-issues.md` Z1 | 成立 | `cmd_grab` 2502–3968 = 1467 行；内嵌函数 28 个、合计 856 行；`_settle_direct_event` 3234 行 114 行、`_finalize_once` 3530 行 80 行、`terminal` 2553 行 75 行 |
| `code-issues.md` Z2 | 成立 | `Api` 813–4620；153 个方法、60 个公开；`__init__` 814–980（167 行）；`_start_plan_inner` 2994–3232（239 行） |
| `code-issues.md` Z3 | 成立（抽查） | `PhoneModel` 7–1361；页面块 1367 起；`wire` 3184–3346；`ingest` 2621–2713；`model` 在 1386，47 个初始化字段 + 8 个动态写入 = 55 |
| `code-issues.md` H1 | 成立 | 23 个标志位逐个复现（`_phone_channel` 7、`_proc`/`_proc_tree`/`_pending_save` 6……与清单完全一致） |
| `code-issues.md` H2 | 成立 | `_lock` 67 个读方法；`with self._lock` 98 处；`_is_busy_locked` 4428–4438，锁顺序注释 4431–4432 |
| `code-issues.md` H4 | 成立 | `PhonePanel` 154 行；`installing` 793 置位、820（finally）清；`PhonePanel.busy` 5 个函数各一进一出共 10 处；`settings.js:200-201` 反向读 `PhonePanel.installing.relogin_ocr` |
| `code-issues.md` G1 | 成立（数未独立复现） | 39 个脚本、`app.js` 依赖 30 文件 128 名字与 inventory 表一致；560 个全局名未独立重算 |
| `code-issues.md` G2 | 成立 | 扇入 13/6/5/9/11/11/8/6/12 与 inventory 高扇入表逐项一致 |
| `code-issues.md` X1 / X2 | 成立 | 42 行、66 行逐行点算；`PREFS` 30 次 8 文件、`PlanCoordinator` 30、`DEMO` 24、`worker_command` 24、`spawn_owned` 16、`SESSION_FILE` 15 均一致；`_emit` 36 次 11 文件、`_last_check` 21、`_activities` 20、`_plan` 18、`_window` 16 |

### 3.2 所有「未修」「没清」的结论（11 项 + 各节「没有发现没清的路径」）

| # | 结论 | 复核 |
|---|---|---|
| 1 | 未修：放弃修改不恢复原勾选 | 成立，`app.js:414` / `plan.js:353` / `startPlan` 不读 `S.editing.ids` |
| 2 | 未修：停止失败或自然结束后卡「修改中」 | 成立，`plan.js:389,395` 不清 `S.editing`；`plan-events.js:17-31` 只清 stopped 分支；`plan.js:360-370` 回草稿仍是修改中 |
| 3 | 部分：自动刷新已修，其余四处未修 | **条数不成立**，见 A1（六处不是四处）；「部分」这个判断本身成立 |
| 4 | 未修：窗口恢复闪骨架 | 成立，`app.js:633-641` → `refresh.js:160-163` → `list.js:29-35`（注释写明「手上有旧列表也一样」） |
| 5 | 已修 `52fd5b2` | 成立，`state/login.js:25-30`，在 `50`、`136` 两处调用 |
| 6 | 已修 `52fd5b2` | 成立，`relogin.js:23-27`、`355` 只对非自动场发取消 |
| 7 | 已修 `ddd4edc`（`d4b3872` 补底栏） | 成立，`m/app.js:136-138` 认 `last_check_state === "expired"` |
| 8 | 未修：核对计划弹层不随轮询更新 | 成立，`renderReview` 只在 `m/app.js:2955`、`2959` 被调用；`ingest` 2621-2713 不调 |
| 9 | 未修：最近同步用手机墙钟 | 成立，`m/app.js:2707-2710` `new Date()`；同函数 2657-2661 已把北京时间存进 `lastOkText` |
| 10 | 已知限制：启动安装程序后无出口 | 成立，`app.py:2242` 第二次仍推 `state="launching"`（finished 假）；`update.js:51-52` 该状态直接 return；`launchInstaller` 129-146 无看门狗 |
| 11 | 未按提案改：错过了行里只有短说明 | 成立，`list.js:238-241` 两句短说明，无开放时刻 |

各节「没有发现没清的路径」：

- 登录校验中（`state-trace.md:56`）：成立，六个出口都在 `refresh.js` 带请求号与代次；
- 组件安装中/忙碌位（`:125,127`）：成立，`phone.js:797-824` 是 `try…finally`，`app.py:1443-1447` 启动失败当场清；
- 更新「启动安装程序」不出（`:176`）：成立，见 #10；
- 列表加载中（`:214`）：成立，出口齐全；
- 计划修改中（`:272-284`）：漏，见 #2，已列在 U1；
- 手机页（`:337`）：成立，两处要等下一次轮询成功才收，已写明。

### 3.3 提案第 4 节「审计结果」段的每个数字

| 提案里的数字 | 复核结果 |
|---|---|
| 前端 39 个脚本里有 33 个在同一个依赖环里 | 成立：`index.html` 共 39 个 `<script src>`，环内 33 个、环外 6 个（`led.js`、`store.js`、`update.js`、`cancel.js`、`window.js`、`app.js`） |
| `state/` 层有 62 处调用了视图或控制器 | 成立：表内 32 行计数之和 = 62；25 个名字（19 views + 6 controllers）、7 个 state 文件 |
| 三个视图文件直接发桥接请求 24 处 | 成立：phone 15 + relogin 5 + settings 4 |
| `Api` 有 153 个方法 | 成立：153 个顶层方法（含 60 个公开） |
| 23 个在三个以上方法里赋值的标志位 | 成立：独立重算 = 23，名单一致 |
| 一把被 67 个方法用的锁 | 成立：`self._lock` 读方法 67 个 |
| 测试给 `app` 模块打了 42 个名字的补丁 | 成立：清单 42 行 |
| 改写了 `Api` 实例的 66 个成员 | 成立：清单 66 行 |
| 11 项状态残留里已修 3、部分 1、未修 5、已知限制 1、文案 1 | 成立：3+1+5+1+1=11，逐项见 3.2 |

提案第 4 节另有两处表述与清单口径不同，不算错但建议改：

- 「`local/app.py` 约 4900 行」：实测 4873 行，清单也是 4873，「约」可留；
- 「`Api` 约 170 个方法」在提案第 1 节、清单与提案第 4 节的 153 不一致——第 1 节是讨论时的估数，第 4 节已用实数，读者容易以为两个都对。

---

## 四、抽查记录（每份被审文件）

| 文件 | 抽了哪些 | 条数 | 对 | 错 |
|---|---|---|---|---|
| `README.md` | 基线、C1 四类口径、C2 引用定义、C4 八条退出路径、C5 对账、抽查比例表；与 `inventory.md`/`state-trace.md` 的实际做法逐条对照 | 6 | 6 | 0（口径本身无矛盾；唯一落空的是 C4「所有状态」在组件一节没做到，记在 A2） |
| `inventory.md` | 文件行数（app.py 4873、grab.py 4076、m/app.js 3357、component_packages 1666、plan-panel 1467、phone 1252）；产品 Python 90 文件/1595 函数/P50 12/P90 40/P99 114/max 1467；15 个超 P99；类 61/29/385/3808；Api 153；23 标志位；`_lock` 67；`with self._lock` 98；42 补丁名；66 改写成员；23 模块全局；39/33/6 环；state 62/25/7；views 80/15/13 + api 24；高扇入 25 个（esc 11 文件 115 次、`S` 32 文件 1344 次、addLog 13）；手机 55 字段/146 写；13 个可变全局 | 24 | 23 | 1（74 个属性，见 A6） |
| `state-trace.md` | 第一节 12 个状态与 4 张退出路径表（含 `refresh.js` 170/184/197、`app.js` 107/124、`plan.js` 461）；第三节 `update.js` 51-52/129-146、`app.py` 2242；第四节 `refresh.js` 149/160-163/197/472-482、`cancel.js` 52、`app.js` 641、`relogin.js` 438、`list.js` 29-35；第五节 `plan.js` 346-357/383/389/395、`plan-events.js` 10/17-31/47、`plan-panel.js` 124/270；第七节 11 项 | 27 | 26 | 1（479-481，见 A4；另 A1 的四处属漏项不计入行号错） |
| `code-issues.md` | R1–R11 逐条行号（30/31/32、112/26、152-164/17/322、14-25/152-162/139-152/164-177、128/2411、80/214/239、18/514、131/133/497-499/502、475-476/1084-1085、123-125/115、23/127）；L1–L8（29、101、27-30、48-54/112/206/264、L5 全部行号、24 处 api、107、33/6/32）；Z1–Z9（2502-3968/3234/3530/2553、813-4620/153/60、7-1361/1367/3184/2621、437-698/193-311、61-419/2994-3232、129-389/133-387、9682/914/136/57/56）；H1–H7；G1–G4；X1–X4 | 46 | 45 | 1（H5 的 11，见 A5；A1/A3 是判断与覆盖问题，不计行号错） |
| `ui-states.md` | U1–U14 的严重度与来源；合计句；三条成因（`PhonePanel.busy` 5 进 5 出、`_advanced_busy` 3 进 3 出、`reloginSubmitting` 10 处）；5 张状态机表与代码的对应（`S.startRequest` 全在 `plan.js`、`S.editing` 四处写入、`S.busy` 唯一写入点 `views/login.js:107`）；末节七行要补测试 | 16 | 15 | 1（U2 的「四处」，见 A1） |
| `design/proposals/engineering-refactor.md` 第 4 节 | 9 个数字逐个重算（见 3.3）+ 六个大文件行数（4900/4100/3400/1700/1500/1250 与实测 4873/4076/3357/1666/1467/1252） | 15 | 15 | 0 |

**未达到每份 20 条的文件**：`README.md`（6 条）、`ui-states.md`（16 条）、提案第 4 节（15 条）。原因是这三份里可指认的代码行号本就少——README 是口径、提案是结论、ui-states 的事实全部引用 `state-trace.md`。对它们的审计以「口径与事实是否一致」为主，已逐节对照；如需按 20 条硬指标补，只能把 `state-trace.md` 的行号重复计一遍，没有增量信息。

---

## 五、附录 A：独立列出的状态变量与等待操作

先按 C4 自己从基线代码列一遍，再与 `state-trace.md` 比对。标「缺」的是被审材料没有逐条给进出口的。

### A.1 登录与重新登录

| 状态变量 | 我列的依据 | 材料有无 |
|---|---|---|
| `S.login.checking` | `refresh.js:170` 进；`app.js:107` 出 | 有 |
| `S.login.loginPending` | `plan.js:413` 进；`461` 出 | 有 |
| `S.login.preLoginSnapshot` | `plan.js:412` 进；`424/433/450/457/468` 出 | 有 |
| `S.login.result` / `ok` / `hours` / `present` | `app.js:108` 等写 | 部分（只当结论，不算状态） |
| `S.autoLogin` | `login.js:45` 进；`27/29` 出；`relogin.js:466` | 有 |
| `S.login.handoff` | `relogin.js:459` / `458` / `login.js:47` | 有 |
| `S.relogin` | `relogin.js:296/321/346` | 有 |
| `reloginRelay` | `relogin.js:444` | 有 |
| `reloginHandoffSeen` | `448/455` | 有 |
| `reloginRefreshedFlow` | `relogin.js:13`，`436` 写，`434` 读——决定重新登录成功后是否再刷一次 | **缺**（只在 H5 出现） |
| `reloginBrowserWatch` | `relogin.js:245`，`248/253` 写——决定浏览器登录是否还在轮询 | **缺**（只在 H5 出现） |
| `S.round.check` / `checkTimer` | `refresh.js:156/175/158` | 有 |
| 后端 `_checking` / `_proc` / `_pending_save` | `app.py:2278`、`4272`、`2034` | 有 |

等待操作：校验（胶囊「检查登录…」/「登录待确认」/刷新重试）✓、浏览器登录（「登录中…」/结果框/再点）✓、输验证码（等待页/结果说明/关掉重开）✓、静默自动登录（「自动登录中…」/第一次失败回失效/可随时点重新登录）✓。**「改用浏览器登录」的等待页**（`relogin.js:514` 先关后开，界面无「正在切换…」）材料没有列，`ui-states.md:87` 的状态机里画了「正在切换…」但代码没有——属建议，不算漏。

### A.2 组件

| 状态变量 | 依据 | 材料有无 |
|---|---|---|
| `PhonePanel.busy` | `phone.js:847/866/890/1013/1099` 进，`856/883/906/1022/1111` 出 | 有 |
| `PhonePanel.pending` | `867/891` 进，`882/905` 出 | 有 |
| `PhonePanel.installing[key]` | `793` / `820` | 有 |
| `PhonePanel.notes.*` | 26 处写、11 个函数 | 有（合成一行） |
| `PhonePanel.state/location/lastDownload` | `201/220-223`、`1013` 一带 | **缺** |
| `PhonePanel.codeLeft/tickTimer/pollTicks/pollTimer` | `243-266` | 部分（只列 pollTimer） |
| `OcrPanel.busy/error/note/lastDownload` | `settings.js:316-329`、`210-212` | 部分（只列 busy） |
| 后端 `_advanced_busy` | `1440/1661/1740` 进，`1358/1686/1768` 出 | 有 |
| 服务 `_state`、`checking`、`outdated` | `advanced_features.py:85-91,124` | 有 |

等待操作：下载 ✓、导入 ✓、开启手机访问 ✓、读状态 ✓、检查中 ✓、自动更新 ✓；**启用组件**（`phone.js:844-862`）与**清除账号**（`1167-1177`）**缺**。

### A.3 版本更新

| 状态变量 | 依据 | 材料有无 |
|---|---|---|
| `S.update.state` | `controllers/update.js:22-24` 16 值 | 有 |
| `S.update.requestId` | `54/132`，18 处比对 | 有 |
| `S.update.timer` | `56/30/45` 进，`19` 出 | 有 |
| 后端 `_updating` / `_update_result` | `app.py:2076/2112`、`2110` | 有 |

等待操作：检查 ✓、下载校验 ✓、启动安装程序 ✓（且写明「启动成功没有出口」）。

### A.4 活动列表刷新

| 状态变量 | 依据 | 材料有无 |
|---|---|---|
| `S.listState` | `refresh.js:161/197/238/288/322/350/483/503`、`app.js:77` | 有 |
| `S.round.list/listTimer/background` | `157/189/159/149/469` | 有 |
| `S.runtime.checkPending/listPending` | `165-166`，`settleRefreshBranch` | 有 |
| `autoRefreshState` | `147/507/509/542/601/612` | 有 |
| `confirmedRefreshTimer` | `refresh.js:391`，`453/454` 写——计划结束后那次刷新的去抖定时器 | **缺**（只在 H5 出现） |
| `S.cancel.busyId/askId` | `cancel.js:84/37`、`29/74` | 有 |
| 后端 `_listing` / `_cancelling` | `2302/2515`、`2575/2580` | 有 |

等待操作：手动刷新 ✓、后台刷新 ✓、等北京时间 ✓、取消报名 ✓（含无超时的结论）。

### A.5 报名计划栏

| 状态变量 | 依据 | 材料有无 |
|---|---|---|
| `S.selected` | 12 处、4 文件 | 有 |
| `S.starting` | `plan.js:43/54/132/153` 进，`58/180/187/211` 出 | 有 |
| `S.startRequest.state`（含 `queryTimer`/`reconcile`/`gen`） | 15 处全在 `plan.js` | 有 |
| `S.busy` | 唯一写入 `views/login.js:107` | 有 |
| `S.plan.status` / `gen` / `doneSelection` | `state/plan.js:50/59`、`plan-events.js:8`、`plan-events.js:12` | 部分（`doneSelection` 缺） |
| `S.stopping` | `plan.js:383` 进，`389/395/91`、`plan-events.js:10/47` 出 | 有 |
| `S.editing` | `plan.js:353` 进，`90/60/390` 出 | 有 |
| `S.recheckPending` | `plan-events.js:121` | **缺** |
| `S.resultSel` | H3 提到 3 处写 | **缺** |
| 后端 `_plan` / `_plan_generation` | `3127/3205/3225`、`3209` | 有 |

注意：`S.recheckPending` 与 A1 的 `plan-events.js:123` 是同一处——它既是一个没进清单的状态，也是漏掉的那次前台刷新。两条可以一起修。

### A.6 手机页

以 `supplement/phone.md` 的 55 字段表为准，我独立数的 `model` 初始化字段是 47 个（`m/app.js:1386-1422`）+ 动态 8 个 = 55，与表一致；`renderReview`、`ingest`、`reconcile`、`cancelPendingStart`、`beginRelogin`、`submitRelogin` 的进出口抽查 12 处全部对得上。

---

## 六、附录 B：重构切法逐步的文件交集

按 `code-issues.md:404-455` 的切法逐段求交集（只算材料里点名的「主要文件」，不含各自新增的小文件）：

| 步骤 | 文件集合 | 与谁相交 |
|---|---|---|
| 先修六条 | `controllers/plan.js`、`controllers/plan-events.js`、`app.js`、`controllers/cancel.js`、`controllers/refresh.js`、`views/relogin.js`、`m/app.js` | 与步骤 1 的 1B/1C 相交（`plan.js`/`plan-events.js`/`refresh.js`/`relogin.js`），所以必须先修完再动结构——材料已这么排 |
| 0a | `views/plan-panel.js`、`controllers/tick.js`、`controllers/terms.js`、`views/login.js`、`state/time.js` | 与 1B（`views/login.js`）、1C（`plan-panel.js`）相交；0a 在前，结论成立 |
| 0b | `state/store.js` | 不相交 |
| 0c | `controllers/refresh.js` + 新增 | 与 1B/1C 相交（拆出来的两个文件分给两块），顺序成立 |
| 0d | `local/tests/test_layer_boundaries.py` + 新增 | 不相交 |
| 1A | `views/phone.js`、`views/settings.js` | 与 1B 相交（材料已要求先把登录恢复表单拆出去） |
| 1B | `state/login.js`、`views/login.js`、`views/relogin.js`、`views/status-cards.js`、check 文件、**`app.js`**、**`index.html`** | 与 1A、1C 都相交于 `app.js`、`index.html` |
| 1C | `views/plan-panel.js`、`controllers/plan.js`、`controllers/plan-events.js`、`state/plan.js`、`state/task-display.js`、list 文件、**`app.js`**、**`index.html`** | 同上 |
| 步骤 2 五块 | 全在 `local/app.py` | 材料已写明「不能并行」，成立 |
| 步骤 3 | `local/grab.py` + 测试 | 与 1/2 不相交，成立 |

结论：只有 1A/1B/1C 这一层的「不撞文件」不成立，见 A3；其余各段的先后关系都成立。

---

## 七、仍无法判定

1. `inventory.md` 的 560 个前端全局名、1344 次 `S` 引用、441 处写入：需要复跑 `globals.mjs` 才能逐项对齐，我按「几何关系自洽 + 抽 25 个高扇入名字全部对上」判断为可信，未独立重算全图。
2. `test_ui_contract.py` 的 914 处字面断言：我按 `assertIn|assertNotIn|assertRegex|assertNotRegex` 计数得 914，与清单一致；但「914」是否含多行断言未逐处看。
3. `ui-states.md` 的 5 张建议状态机是判断，我只核了「每个状态在代码里有对应变量」和「每个去向在代码里有路径」，没有评价设计好坏。
4. `state-trace.md` 第七节第 11 项说「这几行自 `21b6591` 起没变」：`21b6591` 不在基线祖先路径的可见范围内（我只按 `git show 7e2d31c` 读），未核提交历史。
