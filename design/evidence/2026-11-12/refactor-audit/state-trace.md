# 状态路径追踪

- **基线提交**：`7e2d31c`。所有行号以它为准。
- **执行日期**：2026-11-12（北京时间）。
- **口径**：见 `README.md` 的「C4」「C5」。
- **性质**：只写事实。判断（严重度、建议的状态机）在 `ui-states.md`。
- **来源与可信度**：五个功能的初稿由子模型追踪，执行方（Fable 5.2）抽查后重写。每一行末尾标了来源：
  - **核**：执行方读过这几行代码，确认属实。
  - **数**：来自清点脚本（`inventory.md`），行号是脚本给的。
  - **子**：子模型报告里的说法，执行方没有逐行复核。用它之前要自己再看一眼。
- **手机页**：子模型报告到得最晚，执行方只核了主要的「进行中」状态和三项对账，第六节比前五节粗。
- 子模型报告里被执行方查出与代码不符的说法没有收进本文件，清单见结果文件的 `spot_checks`。

路径省略了前缀 `local/ui/`（前端）和 `local/`（后端）时会写明；没写明的都是从仓库根起的完整路径。

---

## 一、登录与重新登录

### 状态

前端路径都在 `local/ui/` 下。

| 状态 | 含义 | 进（写成进行中）| 出（写回空闲）| 来源 |
|---|---|---|---|---|
| `S.login.checking` | 正在向学校校验登录 | `controllers/refresh.js:170`（只有前台轮） | `app.js:107`（check 事件）；`controllers/refresh.js:182`（100 秒超时）、`217`（桥接异常）、`260`（接续旧请求后的超时）、`315`（条款回绝）、`336`（没能开始） | 核 |
| `S.login.loginPending` | 浏览器登录窗口开着 | `controllers/plan.js:413` | `controllers/plan.js:423`（演示模式）、`430`（没能开始）、`448`（桥接异常）、`461`（done 事件） | 核（461 只核了行号） |
| `S.login.preLoginSnapshot` | 登录尝试前的结论快照 | `controllers/plan.js:412` | `controllers/plan.js:424`、`433`、`450`、`457`（失败分支）、`468`（成功分支）；共五处 | 核 |
| `S.autoLogin` | 胶囊显示「自动登录中…」 | `state/login.js:45`（check 结论为失效且后端说能自己恢复）；`views/relogin.js:466`（中继事件：电脑发起、还在进行、没转人工） | `state/login.js:27`（已转人工或已有效）、`29`（中继不再是自动进行中）；`views/relogin.js:466` | 核 |
| `S.login.handoff` | 自动登录已转人工，等用户输验证码 | `views/relogin.js:459` | `views/relogin.js:458`（这一场结束）；`state/login.js:47`（校验结论为有效） | 核 |
| `S.relogin` | 重新登录对话框的会话态（开没开、哪一步、哪一场） | `views/relogin.js:296`（`openRelogin`）、`321`（`openLogin`） | `views/relogin.js:346`（`closeRelogin`） | 核 |
| `reloginRelay` | 后端中继最近一份快照 | `views/relogin.js:444` | 不清，每次事件整份替换 | 核 |
| `reloginHandoffSeen` | 转人工的提醒是否已写过运行记录 | `views/relogin.js:448` | `views/relogin.js:455` | 核 |
| `S.round.check`、`S.round.checkTimer` | 这一轮校验的请求号和超时兜底 | `controllers/refresh.js:156`、`175` | 每轮开头 `158` 清旧定时器；事件到达 `app.js:104` | 核 |
| 后端 `Api._checking` | 校验线程在跑 | `local/app.py:2278` | `local/app.py:2322`、`2329` | 数 |
| 后端 `Api._proc`（中继占用） | 中继 worker 占着「单个任务」的位置 | `local/app.py:4272` | `_relay_finished`（`local/app.py:4289`、`4291`） | 核（4272）；数（其余） |
| 后端 `Api._pending_save` | 登录成功后待保存的账号 | `local/app.py:2034`、`4067`、`4149` | `local/app.py:4079`、`4307` | 数 |

`S.login.handoff`、`S.autoLogin`、`S.relogin`、`S.login.recovering`、`S.login.view` 等都没有在 `state/store.js` 的 `S` 字面量里声明（`inventory.md` 第五节）。

### 退出路径

**校验中（`S.login.checking`）**

| 路径 | 怎么出 | 来源 |
|---|---|---|
| 成功、失败 | check 事件到达，`app.js:107` 清掉，`124` 调 `setLogin` 重画 | 核 |
| 桥接异常 | `controllers/refresh.js:206-224`：清掉、结论写成「暂时无法确认」、写运行记录 | 核 |
| 超时 | `controllers/refresh.js:175-188`：100 秒定时器，同上 | 核 |
| 后端说已有一次校验在途（`skipped`） | `controllers/refresh.js:252-277`：接续旧请求号，重新挂 100 秒定时器；后端带回了结论就当场落地（`266-268`），先到的事件有暂存可重放（`270-275`） | 核 |
| 条款回绝、没能开始 | `controllers/refresh.js:313-319`、`330-342` | 核 |
| 旧一轮的迟到事件 | `app.js:98-102` 按请求号暂存或丢弃，不改当前一轮 | 核 |
| 后台自动刷新 | 不进「校验中」（`controllers/refresh.js:168` 的判断），超时和失败都静默收口（`177-181`、`213-216`） | 核 |
| 窗口关闭、用户取消 | 没有取消入口；校验是后台线程，不随窗口状态变。前端没有主动取消 check 的 API；后端 Api._checking 线程无对外取消路径 | 核 |

没有发现没清的路径。

**自动登录中（`S.autoLogin`）**

| 路径 | 怎么出 | 来源 |
|---|---|---|
| 中继成功、失败、取消 | 中继事件 `live` 为假，`views/relogin.js:463-466` 收回 | 核 |
| 转人工 | `views/relogin.js:459` 置 `handoff`，`463` 的条件不再成立 | 核 |
| 校验结论变成有效 | `state/login.js:47`、`27` | 核 |
| 校验超时、失败、没能开始（结论直接写成「暂时无法确认」） | 这些分支都调 `syncLoginDependentView`，它第一行（`state/login.js:136`）调 `reconcileAutoLogin`；中继不在自动进行中就收回（`29`） | 核 |
| 用户关掉重新登录对话框 | `views/relogin.js:355`：只有不是「电脑自己正在做的那一场」才发取消；自动登录继续，胶囊不变 | 核 |

已知限制（记在 `docs/UI_SPEC.md`，来源是修复这两项时的结果记录）：校验结论「失效且能恢复」比中继的终态事件晚到时，胶囊会短暂回到「自动登录中…」，下一次校验收回。

**登录提交中（`S.login.loginPending`）**

四个出口见上表。没有前端超时：`controllers/bridge.js:6-15` 的 `api()` 不带 timeout；`plan.js` 中 `S.login.loginPending` 只由后端事件清（`app.js:107`）。

**重新登录对话框**

| 路径 | 怎么出 | 来源 |
|---|---|---|
| 用户关（取消、×、Esc） | `views/relogin.js:342-356` | 核 |
| 成功、失败 | 对话框不自动关，切到结果说明那一步（`relogin.js` receiveReloginState 终态切 step），等用户点 | 核 |
| 验证码页点「改用浏览器登录」 | `views/relogin.js:514`：先 `closeRelogin()` 再 `doLogin()` | 核 |

「改用浏览器登录」：`closeRelogin` 发 `relogin_cancel`（`relogin.js:355`，不等结果），随后 `doLogin` 调 `login`（`relogin.js:514`）。`cancel` 锁内只清服务自己的 `_proc`，锁外 `terminate()` 不等待，末尾 `_on_finish` 即 `_relay_finished`，它在进程未退时保留 `Api._proc`，`login` 的 `_is_busy_locked` 就会看到它。**推测，不能判定**：只要中继进程在 `login` 检查时还没退出，`login` 就会被拒。未证明的前提有两处：①从 `terminate` 到进程退出的时长；②两次 js_api 调用的先后（pywebview 每次调用各起线程）。建议先补一条行为测试（见 ui-states.md U6）。补充轮原写「已核：没有竞态」，属对抗审计漏项，返修撤回。

### 等待中的操作

| 操作 | 进行中显示 | 失败显示 | 能否重试 | 来源 |
|---|---|---|---|---|
| 登录校验 | 胶囊「检查登录…」 | 胶囊「登录待确认」（`views/login.js:71-73`）；运行记录一句（`controllers/refresh.js:186`、`222`、`340`） | 点「刷新」 | 核 |
| 浏览器登录 | 胶囊「登录中…」；计划栏显示登录中 | 结果框「登录没能开始」（`controllers/plan.js:445`、`453`） | 再点登录 | 核 |
| 输验证码提交 | 对话框等待页（`reloginStep("wait")`） | 对话框结果说明（`reloginStep("result")`） | 关掉重开 | 核 |
| 静默自动登录 | 胶囊「自动登录中…」 | 第一次失败后胶囊回到失效（`views/login.js`），横幅回来；后台按 60/120/300/900 秒退避重试（后端 `auto_relogin_service.py`），期间界面没有「正在重试」的显示 | 用户可以随时点「重新登录」 | 核 |

### 前后端对应

- `S.login.result`（四态）直接取后端 check 事件的 `result`（`app.js:108`）。核。
- `S.autoLogin` 后端没有对应的单一字段，是前端用两个来源拼的：check 载荷的 `recovering`（`state/login.js:42-45`）和中继快照的 `origin`、`live`、`handoff`（`views/relogin.js:463`）。核。
- `S.login.checking` 只有前端有。后端的 `_checking` 是另一个量，不下发。核。

---

## 二、组件：手机访问与验证码识别

前端在 `local/ui/views/phone.js` 和 `local/ui/views/settings.js`。

### 状态

| 状态 | 含义 | 进 | 出 | 来源 |
|---|---|---|---|---|
| `PhonePanel.busy` | 面板里有一个请求在途 | `phone.js:847`、`866`、`890`、`1013`、`1099` | `phone.js:856`、`883`、`906`、`1022`、`1111` | 数；其中 `toggleStart`（`866`/`883`）和 `downloadComponent`（`1013`/`1022`）核过，出口在 `finally` 里 |
| `PhonePanel.pending` | 手机访问开启中、停止中 | `phone.js:867`、`891` | `phone.js:882`、`905` | 数；`867`/`882` 核过，在 `finally` 里 |
| `PhonePanel.installing[key]` | 导入的组件正在安装（两个键：手机控制、验证码识别） | `phone.js:793` | `phone.js:820`（`finally`） | 核 |
| `OcrPanel.busy` | 验证码识别面板有请求在途 | `settings.js:316` | `settings.js:326` | 数 |
| 下载中、校验中 | 组件包在下载或校验 | 后端组件服务的 `_state`，经快照的 `download.state` 下发（`advanced_features.py`）；前端不另存，由 `phonePhase`（`phone.js:17-18`）和 `ocrPhase`（`settings.js:154-155`）读出 | 后端服务线程结束时改写，经快照下发 | 核 |
| 检查中 | 组件状态暂时读不到 | `local/infrastructure/advanced_features.py:85-91`：事务锁等待超时、且没有上一次成功结果时，返回 `checking` | 下一次读状态成功 | 核 |
| 需要更新 | 旧格式单体包与主程序版本不配 | `local/infrastructure/advanced_features.py:124`（`component_outdated`） | 更新或重新导入后 | 核 |
| 后端 `Api._advanced_busy` | 有一个组件事务在跑 | `local/app.py:1440`、`1661`、`1740` | `local/app.py:1358`（`_component_finished`）、`1686`、`1768` | 核 |
| 后端组件服务 `_state` | 下载事务的阶段 | `start` 置 `_active`（`local/application/advanced_component_service.py:180`） | 线程的 `finally`（`329-339`）回调 `on_finished` 并清 `_active`；下载状态经 `advanced_features.py` 快照下发 | 核 |
| `PhonePanel.pollTimer` | 抽屉开着或有下载时的轮询 | `phone.js:244` | `phone.js:259` | 数 |
| `PhonePanel.notes.*` | 各小节的一句提示或错误 | 26 处写入，分在 11 个函数 | 各函数自己清 | 数 |

`PhonePanel` 共 26 个被写入的字段、96 处写入；`OcrPanel` 17 处写入，其中 6 处是 `phone.js` 写的（`inventory.md` 第五节）。

### 退出路径

**安装中（`PhonePanel.installing[key]`）**：`phone.js:793` 置位，`797-824` 是 `try … finally`，成功、后端回失败、桥接异常都走 `820`。核。没有没清的路径。

**下载的忙碌位（`Api._advanced_busy`）**：`local/app.py:1440` 置位；服务没能启动时当场清（`1443-1447`）；启动成功后由服务线程的 `finally` 回调清（`local/application/advanced_component_service.py:329-334` → `local/app.py:1358`）。核。没有发现没清的路径。

**检查中**：没有超时出口。后端返回里只有 `status=checking`、`busy=true`、`error=""`（`local/infrastructure/advanced_features.py:90-91`），不带等了多久、为什么等。前端显示蓝点「检查中」，没有「重试」按钮；重新打开设置抽屉或等下一次轮询会再读一次。有上一次成功结果时不显示检查中，沿用旧结果并带 `busy=true`（`88-89`），这是 `docs/ARCHITECTURE.md` 写明的做法。核。

**读状态失败**：`PhonePanel.refresh`（`phone.js:198-207`）在 `phone_access_state` 抛异常时不改状态、不提示，照旧快照重画。核。

### 等待中的操作

| 操作 | 进行中显示 | 失败显示 | 能否重试 | 来源 |
|---|---|---|---|---|
| 下载组件 | 这一行里的进度条 | 红条写原因（`phone.js:99-115` 的原因表）；后端同时写运行记录（`local/app.py:1369`） | 「重新下载」按钮（`paintPhoneAccess` 里 `failed ? "重新下载" : "下载并安装"`） | 核 |
| 导入并安装 | 「安装中…」（`phone.js:796`），抽屉按安装中画 | 对话框里一句（`phone.js:801`） | 再点「安装这份」 | 核 |
| 开启手机访问 | `pending = "starting"` | `notes.offErr`（`phone.js:874`、`880`） | 再点开启 | 核 |
| 读组件状态 | 无 | 无（见上「读状态失败」） | 重开抽屉 | 核 |
| 检查中 | 蓝点「检查中」 | 无；不会转成失败 | 无按钮，等下次轮询 | 核 |
| 启用后的自动更新（冻结态、窗口加载后各一次） | 走下载那一套显示 | 只写运行记录，界面停在「需要更新」 | 「更新组件」 | 核（与 `docs/ARCHITECTURE.md` 一致，指组件过期自动更新，不是版本号更新） |

### `phonePhase` 与 `ocrPhase`

见 `code-issues.md` 的 R4。两个面板的进度条、下载失败红条、取消后的说明、安装中遮蔽这四段，结构基本相同但有差异：settings.js 多了 `OcrPanel.error` 覆盖和 `PhonePanel.installing` 复合检查，不是纯粹换选择器（详细比对见 `desktop-recheck.md` 第三节）。`phone.js` 的 `paintPhoneAccess` 约第 437-695 行，`settings.js` 的 `paintOcrDownload` 约第 193-311 行。

---

## 三、版本更新

前端在 `local/ui/controllers/update.js` 和 `local/ui/views/update.js`。

### 状态

| 状态 | 含义 | 进 | 出 | 来源 |
|---|---|---|---|---|
| `S.update.state` | 更新流程走到哪一步，16 个取值（`controllers/update.js:22-24`） | 检查中 `controllers/update.js:55`；启动中 `133`；其余由后端事件写（`25`） | 后端事件；看门狗超时 | 核 |
| `S.update.requestId` | 这一次动作的请求号，迟到回执按它丢弃 | `controllers/update.js:54`、`132` | `18` 处比对 | 核 |
| `S.update.timer` | 看门狗：检查 15 秒、下载和校验每次进度续 60 秒 | `controllers/update.js:56`、`30`、`45` | `19` | 核 |
| 后端 `Api._updating` | 检查或下载在途（单飞） | `local/app.py:2076`；下载入口 `2131` | `local/app.py:2112`（事件带 `finished`）、`2088`、`2139`；另有 `local/application/update_service.py:54` | 核（2076、2112、2088）；数（其余） |
| 后端 `Api._update_result` | 最近一份更新状态，界面重载时用来恢复 | `local/app.py:2110`；`local/application/update_service.py:48` | 整份替换 | 核 |

### 退出路径

**检查中**：后端事件到达即出；没有事件由 `watchUpdate` 看门狗 15 秒收（`controllers/update.js:11-17`）。没有取消入口。

**启动安装程序（`launching`）**

| 路径 | 怎么出 | 来源 |
|---|---|---|
| 安装程序没能启动 | 后端推 `failed` 事件（`local/app.py:2246`）并返回 `ok=false`；前端 `controllers/update.js:137-139` 也按失败落地 | 核 |
| 桥接异常 | `controllers/update.js:141-145` | 核 |
| 版本目录切换路径，启动器没拉起 | 后端推 `failed`（`local/app.py:2218`） | 核 |
| 版本目录切换路径，启动器拉起 | 约 1 秒后程序自己走退出（`local/app.py:2231`） | 核 |
| **安装程序启动成功** | **不出**。后端第二次推的仍是 `launching`（`local/app.py:2242`，`finished` 为假），之后不再推事件；前端 `checkUpdate` 在这个状态直接返回（`controllers/update.js:51-52`），后端 `check_update` 也跳过（`local/app.py:2068-2073`）；`launchInstaller` 没有挂看门狗（`controllers/update.js:129-146`），事件处理里的续时名单也不含 `launching`（`28-31`） | 核 |

最后一行就是提案记为「已知限制」的那一项：安装程序启动后，「检查更新」一直不可点，直到重启工具。这时界面上有「关闭本工具…」按钮（`views/update.js:139`）。

### 等待中的操作

| 操作 | 进行中显示 | 失败显示 | 能否重试 | 来源 |
|---|---|---|---|---|
| 检查更新 | 「正在检查…」，按钮禁用（`views/update.js:41-45`） | 状态行写原因 | 再点「检查更新」 | 核 |
| 下载、校验 | 进度；有「取消」 | 状态行写原因，保留导入入口 | 重新下载 | 核（`receiveUpdate` 续看门狗 60s，`views/update.js` 按 state 画进度） |
| 启动安装程序 | 「正在启动安装程序…」，随后换成后端下发的第二句 | 状态行写原因 | 再点启动 | 核 |

### 前后端对应

更新状态以后端的 `_update_result` 为准，界面重载后经 `bootstrap` 恢复（`controllers/update.js:35-48`）。核。写这份状态的地方有两处：`Api._publish_update`（`local/app.py:2099-2115`）和更新服务直接赋值（`local/application/update_service.py:48-54`），见 `code-issues.md` 的 L4。

---

## 四、活动列表刷新与自动刷新

前端在 `local/ui/controllers/refresh.js`、`local/ui/views/list.js`、`local/ui/controllers/cancel.js`、`local/ui/app.js`。

### 状态

| 状态 | 含义 | 进 | 出 | 来源 |
|---|---|---|---|---|
| `S.listState` | `idle` / `loading` / `ready` / `error` | `loading`：`controllers/refresh.js:161`（只有前台轮） | `ready`：`503`；`error`：`197`（130 秒超时）、`238`（桥接异常）、`288`（接续后的超时）、`322`（条款回绝）、`350`（没能开始）、`483`（后端回失败）；`idle`：`app.js:77` | 核（行号由搜索得到，`161`-`350`、`483` 的上下文读过） |
| `S.round.list`、`S.round.listTimer` | 这一轮拉列表的请求号和 130 秒兜底 | `controllers/refresh.js:157`、`189` | 每轮开头 `159`；回包 `469` | 核 |
| `S.round.background` | 这一轮是不是后台自动刷新 | `controllers/refresh.js:149` | 下一轮覆盖 | 核 |
| `S.runtime.checkPending`、`listPending` | 这一轮两条分支各自收口没有 | `controllers/refresh.js:165-166` | `settleRefreshBranch`；`app.js:116-119` | 核 |
| `autoRefreshState` | 自动刷新的上次尝试时刻、连续失败次数、上次成功时刻文字 | `controllers/refresh.js:147`、`542`、`601`、`612` | `507`、`509` | 数 |
| `S.cancel.busyId` | 正在取消哪一场 | `controllers/cancel.js:84` | `controllers/cancel.js:37`（`cancelSettle` 第一句） | 核 |
| `S.cancel.askId` | 取消确认块开在哪一场 | 点「取消报名」 | `controllers/cancel.js:29`、`74`；手动刷新 `controllers/refresh.js:131` | 核 |
| 后端 `Api._listing` | 拉列表线程在跑 | `local/app.py:2302` | `local/app.py:2515` | 数 |
| 后端 `Api._cancelling` | 取消报名在跑 | `local/app.py:2575` | `local/app.py:2580` | 数 |

### 退出路径

**加载中（`S.listState = "loading"`）**：六个 `error` 出口和一个 `ready` 出口见上表，都有请求号和代次校验（`controllers/refresh.js:204`、`211`、`226`、`231`），旧一轮的回调不会改新一轮。核。没有发现没清的路径。

**后台自动刷新**：不进 `loading`，不清列表。失败时只累计次数（`controllers/refresh.js:472-477`）。核。

**前台轮失败会清空列表和勾选**：`controllers/refresh.js:479-481` 清 `S.items`、`S.byId`、`S.selected`。「前台轮」包括用户点的刷新，也包括程序自己发起的静默刷新，这些都没有带后台标志：

- 窗口重新可见时（`app.js:641`）
- 取消报名成功后（`controllers/cancel.js:52`）
- 计划结束后补一次权威列表（`controllers/refresh.js:456`）
- 重新登录成功后（`views/relogin.js:438`）

核。

**窗口从最小化或托盘恢复**：`app.js:633-641` 在页面重新可见时先调 `bootstrap`，不在跑计划就调 `refresh(true)`。它是前台轮，`controllers/refresh.js:160-163` 把 `S.listState` 写成 `loading`；`views/list.js:29-35` 在加载中一律把列表换成骨架行，注释写明「手上有旧列表也一样」。核。

**取消报名（`S.cancel.busyId`）**

| 路径 | 怎么出 | 来源 |
|---|---|---|
| 后端回了结果（成功、被拒、前置不满足、没确认） | `controllers/cancel.js:87-89` → `cancelSettle` 第 37 行 | 核 |
| 桥接异常 | `controllers/cancel.js:90-93`，按「没能确认」处理 | 核 |
| 超时 | 前端没有定时器。`api()`（`controllers/bridge.js:6-15`）也不带超时 | 核 |

取消进行中，刷新入口直接返回（`controllers/refresh.js:129`），刷新按钮禁用（`views/plan-panel.js:1230`）。如果桥接调用一直不返回，`busyId` 不会清，刷新就一直被挡。后端取消 worker 有 90 秒超时（`local/app.py:2572` `CANCEL_WORKER_TIMEOUT_S`），正常情况下会返回；桥接本身挂住的情形是**推测**——但前端 `bridge.js api()` 不带 timeout，确实没有兜底。

### 等待中的操作

| 操作 | 进行中显示 | 失败显示 | 能否重试 | 来源 |
|---|---|---|---|---|
| 手动刷新 | 骨架行；计数处「正在刷新…」（`views/list.js:381`）；刷新按钮禁用（`views/plan-panel.js:1230`） | 列表空态写原因 | 点「刷新」 | 核 |
| 后台自动刷新 | 无（有意不显示） | 无；连续 3 次失败才在运行记录里写一句（`refresh.js:472-477` `noteBackgroundListFailed` 累计） | 下一个 10 分钟；或手动刷新 | 核 |
| 等北京时间校准后再拉列表 | 后端发一句「北京时间校准中，稍后加载活动」 | 等不到照常拉列表 | — | 核（与 `docs/ARCHITECTURE.md` 一致） |
| 取消报名 | 这一行显示取消中 | 结果句写在这一行（`controllers/cancel.js:55-63`） | 再点取消 | 核 |

---

## 五、报名计划栏

前端在 `local/ui/controllers/plan.js`、`local/ui/controllers/plan-events.js`、`local/ui/state/plan.js`、`local/ui/views/plan-panel.js`。

### 状态

| 状态 | 含义 | 进 | 出 | 来源 |
|---|---|---|---|---|
| `S.selected` | 勾选的场次 | 12 处写入，分在 4 个文件（`inventory.md`） | — | 数 |
| `S.starting` | 开始请求已发、还没确认 | `controllers/plan.js:43`、`54`、`132`、`153` | `controllers/plan.js:58`、`180`、`187`、`211` | 核（`153`）；其余只有行号 |
| `S.startRequest.state` | 开始请求的对账状态：提交中、对账中、已接纳、被拒、未知 | 15 处写入，全在 `controllers/plan.js` | — | 数 |
| `S.busy` | 计划在跑或登录窗口开着 | 唯一写入点 `views/login.js:107`（`setBusy`） | 同左 | 数 |
| `S.plan.status` | 计划状态 | `state/plan.js:50`、`59`；`controllers/plan-events.js:8` | 终态不回退（`state/plan.js:49`） | 核 |
| `S.stopping` | 正在停止 | `controllers/plan.js:383` | `controllers/plan.js:389`（后端拒绝）、`395`（桥接异常）、`91`（新的开始被接纳）；`controllers/plan-events.js:10`、`47`（计划结束事件） | 核 |
| `S.editing` | 「修改中」：`{ids, doneN}` | `controllers/plan.js:353`（`modifyPlan`） | `controllers/plan.js:90`（新的开始被接纳）；`state/plan.js:60`（接到新计划）；`state/filters.js:390`（`clearSelection`） | 核 |
| 后端 `Api._plan` | 当前计划的协调器 | `local/app.py:3127`、`3205`、`3225` | 同左（置空） | 数 |
| 后端 `Api._plan_generation` | 计划接纳代次，事件靠它认主 | `local/app.py:3209` | 只增 | 数 |

`S.editing` 没有在 `state/store.js` 里声明。

### 退出路径

**修改中（`S.editing`）**

`modifyPlan`（`controllers/plan.js:346-357`）记下还没提交的场次，写一句运行记录「计划已暂停：N 场放回草稿修改」（`355`），然后调 `doStopPlan`（`356`）。

| 路径 | 结果 | 来源 |
|---|---|---|
| 停止成功，计划以 `stopped` 结束 | `controllers/plan-events.js:17-25`：把记下的场次放回勾选，清掉计划，`S.editing` 保留（界面显示「修改中」，这是设计的） | 核 |
| 用户改完点「重新开始计划」，后端接纳 | `controllers/plan.js:90` 清掉 | 核 |
| 用户清空选择 | `state/filters.js:390` 清掉 | 核 |
| **停止没成功**（后端拒绝或桥接异常） | `controllers/plan.js:388-399` 只清 `S.stopping`，`S.editing` 留着。计划还在跑，运行记录里已经写了「计划已暂停」 | 核 |
| **计划先自然结束**（状态不是 `stopped`） | `controllers/plan-events.js:17` 的条件不成立，走 `26-31` 进结果页，`S.editing` 没有清。结果页点「完成，回到活动列表」会经 `clearSelection` 清掉（`controllers/plan.js:373-377`）；点「重新选择未成功的场次」（`controllers/plan.js:360-370`）不清，回到草稿后计划栏标签是「修改中」（`views/plan-panel.js:124`），「放弃修改，按原计划继续」按钮也出现（`views/plan-panel.js:270`） | 核 |

**「放弃修改，按原计划继续」**：按钮 `#btn-edit-restore`（`local/ui/index.html:91`）绑的是 `startPlan`（`app.js:414`）。`startPlan`（`controllers/plan.js:2` 起）用的是当前的 `S.selected`。`S.editing.ids` 里存着原计划的场次，这个按钮没有用它。核。

**正在停止（`S.stopping`）**

| 路径 | 怎么出 | 来源 |
|---|---|---|
| 后端拒绝、桥接异常 | `controllers/plan.js:389`、`395` | 核 |
| 停止成功 | 后端回 `ok` 时前端什么都不做（`controllers/plan.js:387-393`），等计划结束事件在 `controllers/plan-events.js:10` 或 `47` 清。事件传递链：后端 `app.py` 协调器终态 `_emit("plan_done", ...)` → pywebview `evaluate_js` 投递 → 前端 `app.js` 接收 → `handlePlanDone` → `presentPlanDone` 第一句 `S.stopping = false`。窗口恢复时 `bootstrap` 只对账 `S.busy` 和 `S.plan.status`，不改 `S.stopping`，但 evaluate_js 失败概率极低 | 核 |

**开始请求（`S.starting`）**：请求没有正常返回时进入对账；对账也没有结论时，`controllers/plan.js:149-160` 把 `S.starting` 保持为真、开始按钮保持禁用，结果框给一个「重新确认」入口（`160`）。这是有意的：宁可挡住，也不让用户重复开始。核。

### 等待中的操作

| 操作 | 进行中显示 | 失败显示 | 能否重试 | 来源 |
|---|---|---|---|---|
| 开始计划 | 按钮禁用；超时后结果框「正在确认是否启动」（`controllers/plan.js:140-142`） | 结果框写原因；没结论时写「结果未确认，请勿重复启动」 | 「重新确认」；被拒后再点开始 | 核 |
| 停止计划 | 运行记录「正在停止计划…」（`controllers/plan.js:386`）；按钮按停止中画 | 运行记录一句（`392`、`398`）；没有结果框 | 再点停止 | 核 |
| 修改计划 | 同停止 | 同停止；另见上「停止没成功」 | — | 核 |
| 单场取消 | 只在运行记录里写一行（`plan-events.js` showTaskResult 各终态都 `addLog`；planLive 时不 `setResult`） | 同左 | — | 核 |

---

## 六、手机页

全部在 `local/ui/m/app.js`。文件分两块：`PhoneModel`（第 7-1361 行，纯函数，101 个成员）和页面逻辑（第 1367-3357 行，67 个函数）。页面状态都在第 1386 行的 `model` 对象上：55 个被写入的字段，146 处写入（`inventory.md` 第五节）。

### 状态

| 状态 | 含义 | 进 | 出 | 来源 |
|---|---|---|---|---|
| `model.flying` | 轮询在途 | `2434` | `2453`（`finally`） | 核 |
| `model.pairing` | 配对请求在途 | `2401` | `2426` | 数 |
| `model.pending` | 开始请求还没有结论（`done` 为假） | `2730` | `2741`（后端当场受理）、`2760`（对账查到终态） | 核 |
| `model.reconciling` | 正在向电脑对账开始请求 | `2753` | `2773`（`finally`） | 核 |
| `model.cancelingStart` | 正在取消等待中的开始 | `2783` | `2798` | 数 |
| `model.reloginStarting` | 重新登录的发起请求在途 | `3065` | `3079`、`3092`；`2989` | 数 |
| `model.reloginSubmitting` | 验证码提交在途 | `3123` | `3148`（被拒）；其余由 `ingestRelogin` 按电脑上这一场的状态清（`2988` 起 8 处） | 核（`3123`、`3148`）；数 |
| `model.busy` | 电脑上计划在跑 | 只由快照写（`2665`） | 同左 | 数 |
| `model.sheetId` | 开着哪个弹层 | `1565` | `1586` | 数 |
| `model.lastOkAt` | 上次轮询成功的时刻，用来判断状态是否过时 | `2441`，取手机本机时钟 | — | 核 |

`ingest`（第 2621-2713 行）一个函数写了 16 个字段。

### 退出路径

**轮询**：`2436-2459` 是 `try … catch … finally`。成功、失败、401、403 都经 `finally` 清在途标志并安排下一次。失败时累计次数、拉长间隔（`2461-2465`）。核。

**开始请求**：`postAction`（`2316-2325`）把网络异常接住，返回一个「没发出去」的结果，所以 `startPlan` 不会抛。后端当场受理就记终态（`2740-2743`）；否则每次轮询成功后在 `ingest` 末尾触发对账（`2712`）。对账查不到结果时横幅给「取消等待」（`2769-2771`）。`startPlan` 遇到 401 直接返回（`2739`），这时未决的请求留着，等重新配对、下一次轮询成功后再对账。核。

**提交验证码**：网络异常时故意不清在途标志（`3131-3137` 的注释写明：结果未知，保持禁用，先向电脑对账），提示「正在登录，请等结果」，立刻触发一次轮询。之后由快照里这一场的状态决定放行还是收口。断网期间这个标志一直是真，网络恢复、轮询成功后才收。核。

**对账**：`2754-2775` 是 `try … finally`，`reconciling` 一定清。核。

没有发现「走完以后永远不清」的路径。两处要靠下一次轮询成功才收：提交验证码遇到网络异常、开始请求遇到 401。

### 等待中的操作

| 操作 | 进行中显示 | 失败显示 | 能否重试 | 来源 |
|---|---|---|---|---|
| 轮询 | 「同步中」，刷新钮禁用（`2435`） | 按「连不上」呈现，自动重试 | 自动；也可手动刷新 | 核 |
| 开始计划 | 底栏按核对中画（`model.pending` 时底栏显示核对中） | 横幅写原因（`2744`、`2765-2767`） | 被拒后可再开始；未知时「取消等待」 | 核 |
| 提交验证码 | 「正在登录，请等结果」，弹层锁定（`3124`） | 弹层里一句（`3149-3151`） | 再输一次 | 核 |
| 配对 | 按钮禁用（`model.pairing = true`）；锁定倒计时（`PhoneModel.pairView` 有 `lockLeft`、`applyPairFailure` 置 `pairLockLeft`） | — | — | 核 |

### 前后端对应

- 手机页的计划、活动、登录都来自 `/api/state` 的快照，`model.busy` 完全以后端为准。核。
- 登录是否失效是手机页自己用三个字段拼的，没有用后端的四态结论（`code-issues.md` 的 R5）。核。
- 「立即报名还是预报名」手机页自己按开放时刻算（R8）。核。
- 「最近同步」用手机本机时钟（见第七节 #9）。核。

---

## 七、状态残留对账（C5）

`design/proposals/workbench-ui-polish.md`「前置：状态残留修复」的 11 项。全部由执行方核对。

| # | 提案里的说法 | 现状 | 证据 |
|---|---|---|---|
| 1 | 「放弃修改，按原计划继续」不恢复原来的勾选 | **未修** | `local/ui/app.js:414` 把按钮绑到 `startPlan`；`local/ui/controllers/plan.js:353` 存了原计划的场次，`startPlan` 不读它 |
| 2 | 停止没成功或计划先自然结束时，界面卡在「修改中」 | **未修** | 停止没成功：`local/ui/controllers/plan.js:388-399` 不清 `S.editing`。自然结束：`local/ui/controllers/plan-events.js:17-31` 不清；之后走 `local/ui/controllers/plan.js:360-370` 回草稿仍是「修改中」（`local/ui/views/plan-panel.js:124`、`270`） |
| 3 | 程序自己发起的刷新失败会清空列表和勾选 | **部分** | 每 10 分钟的自动刷新已修，提交 `14bec62`，起作用的是 `local/ui/controllers/refresh.js:472-477`。其余四处程序发起的静默刷新（`local/ui/app.js:641`、`local/ui/controllers/cancel.js:52`、`local/ui/controllers/refresh.js:456`、`local/ui/views/relogin.js:438`）失败时仍走 `refresh.js:479-481` 清空 |
| 4 | 每次把窗口从最小化恢复，列表都闪一次 | **未修** | `local/ui/app.js:633-641` → `local/ui/controllers/refresh.js:160-163` → `local/ui/views/list.js:29-35` |
| 5 | 胶囊可能停在「自动登录中…」 | **已修** | 提交 `52fd5b2`。`local/ui/state/login.js:25-30` 的 `reconcileAutoLogin`，在 `50` 和 `136` 两处调用。留有一条已知限制（见第一节） |
| 6 | 关掉「重新登录」对话框会取消电脑正在进行的自动登录 | **已修** | 提交 `52fd5b2`。`local/ui/views/relogin.js:23-27`、`355` |
| 7 | 学校判登录失效时，手机页可能仍写「电脑上的登录有效」 | **已修** | 提交 `ddd4edc`（随后 `d4b3872` 补了底栏）。`local/ui/m/app.js:136-138` 的 `loginRaw` 认 `last_check_state === "expired"` |
| 8 | 手机「核对计划」弹层不随轮询更新，点开始可能没反应 | **未修** | `renderReview` 只在两处被调用：`local/ui/m/app.js:2955`（从弹层里移除一场）和 `2959`（打开弹层）。轮询回来走的 `ingest`（`2621-2713`）不调它。「点开始可能没反应」没有复现，这半句是提案的原话 |
| 9 | 手机「最近同步」用的是手机本机时钟 | **未修** | `local/ui/m/app.js:2707-2710` 用 `new Date()` 取时分。同一文件里离线档的「最后同步」已经用北京时间（`2657-2661`） |
| 10 | 安装程序启动后「检查更新」一直不可点 | **已知限制，代码没改** | 见第三节「启动安装程序」最后一行 |
| 11 | 「错过了」把原因写进行里 | **未按提案改** | `local/ui/views/list.js:238-241` 现在在行里写一句短说明（「还开着，可以重新勾选」或「电脑睡眠期间到点」），没有提案要的开放时刻和「没有提交」。这几行自 `21b6591` 起没变 |

合计：已修 3 项（5、6、7），部分 1 项（3），未修 5 项（1、2、4、8、9），已知限制 1 项（10），未按提案改 1 项（11，属文案）。
