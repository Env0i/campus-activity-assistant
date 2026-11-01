# 校园活动预报名工具（本机版）· 视觉验收交互说明

> 交付对象：开发/验收团队。用途：照单可验——看见哪个元素、期望什么、禁止什么。
> 证据口径：全部结论来自静态源码与文档（仓库 `<repo>`，只读）。
> 行号以本次读取为准。文档与实现不一致处集中在 §5，不自行消解。

---

## 0. 产品镜头与验收口径

**用户 + 任务**：目标学校（校园）专升本学生，用本人账号，在自己的 Windows 电脑上
把「到点自动报名」跑通：先确认登录态，再从几百条活动里挑出能报的，加进一个计划，到点提交，
结果看得懂（成功/没抢到/待核对/未提交）。
**首读对象**：顶栏登录胶囊 + 黑底大屏（`#board`）上的「现在什么状态 / 下一场几点开放」。
**主动作**：`#btn-plan`「开始报名计划」。
**密度决定**：紧凑。时刻表正文 13px（`docs/UI_SPEC.md:606`），五列栅格
`--cols: 26px 76px minmax(0,1fr) 156px 132px`（`local/ui/styles.css:15`），一屏要同时看到
状态胶囊、大屏、列表与主按钮（`docs/UI_SPEC.md:80`）。
**层级**：胶囊/大屏标题（状态）> 主按钮与门禁原因 > 列表行 > 任务卡与路线 > 运行记录。
**交互模型**：仪表盘式的「大屏 + 时刻表 + 底部日志」，全部单页，无路由。
**响应优先级**：窗口最小 980×700、默认 1120×800（`docs/UI_SPEC.md:616`）；压力视口
746×512、680×480 允许换行但**不允许横向滚动**，关键操作（帮助/刷新/停止/开始）必须仍可点
（`docs/UI_SPEC.md:617-618`）。
**禁止的通用默认**：渐变主视觉、玻璃拟态、四张等权 KPI 卡、通用「加载中…/出错了」骨架、
按组件库默认色染整屏结论。本产品的「设计」在这里是：黑底琥珀 LED 点阵、时刻表分组、
真实 checkpoint 路线图（`local/ui/styles.css:1-17`）。
**不可验证项**（静态阅读无法定论，需真实截图/实机）：pywebview 窗口标题是否与
`document.title` 一致；100%/150% 缩放下的像素对齐；LED 点阵字形（`local/ui/led.js`）；
移动端 `local/ui/m/` 三文件（不在本次桌面验收范围）。

---

## 1. 页面层级树

单一窗口 `#zd`（`local/ui/index.html:10`），三层结构 + 6 个覆盖层，全部同页共存，
靠 `hidden` / `dialog.open` / `z-index` 控制可见性。

```
窗口（pywebview / WebView2，最小 980×700）
└─ div.zd#zd                                    index.html:10
   ├─ header.top                                index.html:11-25
   │  ├─ .brand  .name-full「校园活动预报名工具」/.name-short「校园预报名工具」
   │  │           .brand-desc「活动查询与报名计划」          index.html:12-15
   │  └─ .top-right[data-tour-target=login]     index.html:16
   │     ├─ button.clock#clock                  时间入口（打开浮层 L4）
   │     ├─ button.pill#pill                    登录胶囊（无点击处理器，见 D13）
   │     ├─ span#status-detail.sr-only          胶囊说明的屏幕阅读器副本
   │     ├─ button#btn-help                     打开模态 M2
   │     ├─ button#btn-refresh                  refresh()
   │     └─ button#btn-login#btn-login-text      doLogin()
   ├─ div.banners#banners                        index.html:27  ← 横幅容器（0–n 条）
   ├─ section.board#board                        index.html:29-62 黑底大屏
   │  ├─ .b-main[data-tour-target=select]
   │  │  ├─ .b-tag#board-tag(data-tone) + #board-tag-text
   │  │  ├─ #rail-message                     一句话摘要
   │  │  ├─ h2#selected / #selected-meta / #board-text
   │  │  ├─ .b-metrics  #countdown / #metric-total / #metric-free
   │  │  ├─ #plan-conflicts[role=alert][hidden]  冲突/校验块（非弹窗）
   │  │  ├─ #plan-tasks[aria-live=polite]        任务卡容器
   │  │  └─ p#result[role=status][hidden]        结果条
   │  ├─ aside.b-led[data-tour-target=run] #led(data-tone) + #led-label>#metric-next
   │  └─ .b-foot
   │     ├─ #route-line[hidden] > #route + #btn-stop
   │     └─ #route-actions[data-tour-target=start]
   │        #plan-checks / #btn-board-login / #btn-board-pick /
   │        #retry-for / #max-attempts / #headed / #btn-clear-plan / #btn-plan
   ├─ section.table                             index.html:64-79
   │  ├─ .filters[data-tour-target=filters]  #q #chips #time #sort #checkin #checkout #count
   │  └─ .list#list[data-tour-target=list]
   │     ├─ .colhead（选/开放时间/活动/地点/距开放）
   │     ├─ #rows                            行/分组/骨架注入点
   │     └─ .empty#empty[hidden]             列表空态覆盖层 L6（绝对定位覆盖 .list）
   └─ footer.logbar#logbar[data-open]           index.html:81-84
      └─ #log-last + 工具按钮 + #log[role=log]

覆盖层（父子关系 = 谁打开谁负责关闭）
├─ M1 dialog#dlg-terms      条款模态   index.html:89-199   父：boot / refresh / 横幅 / 帮助
├─ M2 dialog#help           帮助模态   index.html:201-261  父：顶栏 #btn-help / 首启 welcome
├─ M3 dialog#dlg-stop       停止确认   index.html:281-284  父：#btn-stop
├─ L4 div.pop#clock-pop     时间浮层   index.html:279      父：#clock（+ 大屏「查看时间详情」）
├─ L5 div.tour#tour         六步引导   index.html:263-277  父：首启 / 帮助「重看引导」
└─ L6 div.empty#empty       列表空态   index.html:77       父：paintEmpty（列表内覆盖）
```

### 1.1 每个覆盖层的出现条件与关闭路径

| 层 | 出现条件 | 证据 | 关闭路径 |
|---|---|---|---|
| M1 条款 | `!termsAccepted() && !demo && !prompted && !declined` 时自动弹 | `local/ui/controllers/terms.js:71-74` | 「我已阅读并同意」（真保存）/「暂不使用」/ X / Esc（保存中被拦） |
| M1 条款 | `refresh()` 遇 `termsLocked()` 且未拒绝、状态未知 | `local/ui/controllers/refresh.js:123-126` | 同上 |
| M1 条款 | 横幅「查看条款」 | `local/ui/views/board.js:785,791` + `local/ui/app.js:246-251` | 关闭后焦点回被点按钮 |
| M1 条款 | 帮助内「查看条款」 | `local/ui/app.js:177` | 关闭后回帮助并聚焦「查看条款」（`views/terms.js:152-158`） |
| M1 条款（只读态） | 已同意同版时打开，`S.terms.viewOnly = termsAccepted() && !unknown` | `local/ui/controllers/terms.js:100` | 只有「关闭」（`views/terms.js:27,36,40`） |
| M2 帮助 | 点击 `#btn-help` | `local/ui/views/help.js:10-17` | X / 「关闭」/ Esc；内部动作不关 |
| M2 帮助 | 首启且不会自动进引导时自动开（`firstRun && !tourWillAuto`） | `local/ui/app.js:45-53` | 同上 |
| M3 停止确认 | `#btn-stop` → `stopPlan()` | `local/ui/controllers/plan.js:275-280` | 只有 `returnValue==="yes"` 才真停；Esc/「继续计划」= 不停（`app.js:226-231`） |
| L4 时间浮层 | 点击 `#clock` | `local/ui/views/clock-pop.js:41-52` | 再次点击/点外部（`app.js:207-209`）/Esc（`app.js:370`）/浮层 × 按钮 |
| L4 时间浮层 | 大屏「查看时间详情」按钮（`[data-open-clock]`） | `local/ui/views/board.js:96` + `app.js:222-225` | 同上 |
| L5 引导 | 首启且 `tour_version < TOUR_VERSION(2)` | `local/ui/views/tour.js:7-14` | 跳过/完成（Esc = 跳过，`app.js:343`） |
| L5 引导 | 帮助「重看引导」（运行中禁用） | `local/ui/views/help.js:44-57` | 同上 |

**互斥与不穿透（可机械验证）**
- 条款弹窗打开时 `document` 级 keydown 直接 return，Enter/Esc/Ctrl+F/`/`/F5 不落到背景
  （`local/ui/app.js:335-336`）；保存中 Esc 被 `cancel` 拦住（`app.js:187-189`）。
- 帮助与条款不叠开：打开条款前先 `closeHelpIfOpen()`（`local/ui/views/terms.js:111-115`）。
- 帮助/停止确认打开时，Enter/Esc 只属于弹窗（`local/ui/app.js:356-359`）。
- 引导可见且未暂停时，Esc=跳过、Tab 在 `#tour-skip/#tour-prev/#tour-next` 间循环、
  背景 Ctrl+F 与 `/` 被吞、背景 Enter 不开始计划（`app.js:342-352` + `views/tour.js:32-45`）。
- 计划运行中引导自动暂停（`local/ui/views/login.js:110`），结束后从原步骤继续（`:111`）。

---

## 2. 核心操作流程（每一步的可见反馈与门禁）

**F0 启动** `boot()`（`local/ui/app.js:11-70`）
`waitForBridge` → `bootstrap()` → 填帮助/版本（`:16-18`）→ 恢复更新状态（`:19`）→
`applyPrefs`（`:29`）→ `ingestTerms`（`:32`）→ 北京时间快照（`:35`）→ `setLogin`（`:37`）→
`setBusy` + `ingestBootstrapPlan`（`:39-40`）→ 首启引导或帮助（`:44-55`）→
`front_ready` + 时钟轮询 + `refresh(true)`（`:64-69`）。
bootstrap 失败：`markTermsUnknown()` + `setLogin(null,null)` + `listState="idle"` + `render()`
（`app.js:56-63`），并写日志「[X] 界面初始化失败：…」（`app.js:399-404`）。

**F1 登录** `doLogin()`（`local/ui/controllers/plan.js:305-358`）
先存 `preLoginSnapshot`（`:315`）→ 胶囊「登录中…」（`views/login.js:29-34`）、大屏
「正在打开登录窗口」（`views/board.js:20-27`）→ 成功 `handleDone login`：清快照、清锚点、
结果条「登录成功 / 正在加载活动列表。登录剩余时间以学校校验为准。」6 秒自动收（`plan.js:366-374`）；
失败：整份回滚快照，结果条按 `loginFailCopy()` 五分支 + 「再试一次」（`plan.js:375-385,395-403`）。
门禁：`termsLocked()` 时直接拒绝（`plan.js:308-311`）；`#btn-login` 在 busy/缺组件/条款未同意时 disabled
（`views/board.js:746`）。

**F2 选择** 复选框或整行点击（`app.js:146-159`）→ `toggleSelection()`（`state/filters.js:225-266`）
与已报名活动冲突 → 「与已报名活动「X」的举办时间重叠（…），不能再加入计划。」（`:243-246`）；
与本次选择冲突 → 「与「X」的活动时间重叠，同一计划只能选择其中一场。已保留原选择。」（`:254`）；
消息进 `#plan-conflicts`（`views/board.js:322`）。已报名/已截止/忙碌时复选框 disabled
（`views/list.js:137`、`views/board.js:769-773`）。

**F3 开始计划** `startPlan()`（`local/ui/controllers/plan.js:2-115`）
前置：无选择 → 结果条「还没选活动 / 在时刻表勾选至少一场未报名活动。」（`:10-13`）；
有校验错/冲突 → 「计划还不能开始 / 先处理上面的检查项，再开始报名计划。」（`:14-18`）。
提交中：`S.starting=true`，按钮变「正在提交…」（`views/board.js:762-765`），15 秒无回执转
「正在确认是否启动…」+ 结果条「正在确认是否启动 / …请勿重复启动。」（`plan.js:127-140`）；
对账 unknown → 结果条「结果未确认，请勿重复启动」+「重新确认」按钮（`plan.js:146-159`）。
后端拒绝 → `showPlanError()` 把 `errors/conflicts` 逐条翻成「哪一场、什么问题」（`views/selection.js:43-66`）。

**F4 运行** `plan/task` 事件（`state/plan.js:54-96`）
大屏阶段按 `executionView()` 五阶段改写（`state/task-display.js:89-145`）：
`preopen→「等待开放」`、`preparing→「准备报名」`、`retrying→「提交中」`（`:50-62`）；
倒计时 `#countdown`、LED、任务卡说明同源（`views/board.js:406-463,496-590`）。
单场终态只更新任务卡与日志，计划跑着时不写结果条（`controllers/plan-events.js:107-152`）。

**F5 停止** `stopPlan()` → `#dlg-stop` → `doStopPlan()`
立即 `S.stopping=true`，胶囊 busy、`#btn-stop` 文案「正在停止…」且 disabled（`views/board.js:766-767`），
日志「正在停止计划：结束还在重试的场次…」（`plan.js:289`）；解锁只在 `plan_done`
（`controllers/plan-events.js:13`）。

**F6 刷新** `refresh()`（`controllers/refresh.js:115-195`）
`check` 与 `list` 两条分支并行；超时兜底 100s/130s（`:148-163`）；两条都收口才撤/留组件横幅
（`:102-113`）；旧轮 `request_id` 迟到先暂存、接续后重放一次（`:203-245`）。

**F7 结果判读** `presentPlanDone()`（`controllers/plan-events.js:2-67`）
`completed` → 「报名计划完成」；`stopped` → 「报名计划已停止」+ 未知并列；
`partial` → 「报名计划部分完成，有 N 场待核对」；`failed` 且含未知 → 「报名计划已结束，有 N 场…」；
否则 → 「报名计划没有成功」。整屏边框走 `data-plan-state`（`views/board.js:153-166`）。

---

## 3. 关键组件三态表

> 记法：**元素** → 期望（文案/类名/属性）· 证据 `文件:行号`。凡未写「禁用」者即可点。

### 3.1 顶栏登录胶囊 `#pill`

| 态 | 期望 | 证据 |
|---|---|---|
| 加载（校验中） | class 含 `is-busy`，`data-state="checking"`，`#pill-text`=「检查登录…」，`#status-detail`=「正在检查登录状态，马上就好」 | `views/login.js:35-40` |
| 空白（从没登录） | `is-none`，`data-state="none"`，「未登录」；`#status-detail`=「点右上角「登录」，在打开的浏览器中完成登录」 | `views/login.js:41-45` |
| 错误（无法确认） | `is-none`，`data-state="unknown"`，「登录待确认」；说明「暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录」 | `views/login.js:46-51` |
| 失效 | `is-bad`，`data-state="bad"`，「登录已失效」；说明「重新登录后可继续使用」 | `views/login.js:59-66` |
| 有效（约剩 ≥2h） | `is-ok`，「已登录」+ `#pill-sub`「约剩 N 小时」 | `views/login.js:74-80` |
| 有效（<2h） | `is-warn`，「已登录」+「约剩 …」，说明「不到 2 小时，建议现在先重新登录一次」 | `views/login.js:67-73`（阈值 `EXPIRING_H=2`，`state/store.js:16`） |
| 演示 | `is-warn`，「演示模式」+「内存样例」 | `views/login.js:22-28` |
| 按钮文字联动 | `bad/warn/ok` →「重新登录」，其余「登录」；`none/bad` 用实心 | `views/login.js:99,102-104` |

禁止：加载中写「已登录」；未知态写「登录已失效」。

### 3.2 顶栏时钟 `#clock`（唯一时间入口）

`data-state` 五值 + 可见文本（`views/clock.js:5-18`；词表 `state/clock.js:29-35`）：

| data-state | `#clock-label` | `#clock-time` | title/aria-label | 视觉 |
|---|---|---|---|---|
| `ready` | 北京时间 | `HH:MM:SS` | 北京时间，已校准，查看时间详情 | 图标绿（`styles.css:48`） |
| `holdover` | 北京时间 | `HH:MM:SS` | 北京时间，使用上次校准结果，… | 图标 `--warn`（`styles.css:50-52`） |
| `syncing` | 北京时间 | 「校准中…」 | …正在校准… | 图标 warn，时间字号变小（`styles.css:46-47`） |
| `unavailable` | 北京时间 | 「待校准」 | …时间校准失败… | 图标 warn |
| `demo` | 演示时间 | `HH:MM:SS`（`Date.now()`） | 演示时间，… | 图标 `--ink-3` |

浮层 `#clock-pop`（`views/clock-pop.js:64-140`）：`pop[data-state]` 同步同值（`:73`），
内含 标题/`#clock-pop-time`/日期/`#clock-pop-status`（图标+`CLOCK_COPY.label`）/`pop-explain`/
四个 `dt-dd` 事实（最近校准、估计误差、上次退出、登录预计剩余）/两个 `details.records`
（使用记录、时间来源）//`#clock-pop-sync`（校准中或 demo 时 disabled，`:126-127`）/
`#clock-pop-feedback`（`role=status`，`:142-155`）。

### 3.3 活动时刻表（`#rows` + `#empty` + `#count`）

| 态 | 期望 | 证据 |
|---|---|---|
| 加载（首次，无缓存） | `#rows` 注入 `div.skel[aria-label=正在加载活动列表]`，6 条 `.skel-row`；`#empty.hidden = true` | `views/list.js:26-31,63-67`；样式 `styles.css:308-314` |
| 加载（有缓存） | `.list.is-loading` 顶部 2px 扫光条；`#count`=「正在刷新…」 | `views/list.js:25,291`；`styles.css:247` |
| 空白（被筛掉） | `#empty-title`「没有符合筛选的活动」/`#empty-text`「一共 N 场，换个关键词，或清除筛选看完整列表。」/`#empty-action`「清除筛选」，`dataset.action="clear-filters"` | `views/list.js:242-249` |
| 空白（尚未加载） | 「还没有加载活动列表」/「点「刷新」加载一次；需要登录时，顶部会提示下一步。」/「刷新」 | `views/list.js:250-257` |
| 空白（校验中） | 「正在检查登录状态」/「正在核对已保存的登录，稍等一下；这段时间先不用重新登录。」/「刷新」 | `views/list.js:260-266` |
| 空白（未登录） | 「登录后查看活动」/「点右上角「登录」，在打开的浏览器中完成登录，然后点「刷新」。」/「刷新」 | `views/list.js:267-272` |
| 空白（失效） | 「登录状态失效，先重新登录」/「点右上角「重新登录」，完成后点「刷新」。」/「刷新」 | `views/list.js:273-278` |
| 空白（无法确认） | 「暂时无法确认登录状态」/「请检查网络后点「刷新」。」/「刷新」 | `views/list.js:279-284` |
| 空白（学校 0 场） | 「学校当前没有返回活动」/「登录是有效的，学校这次没有返回可报名活动；稍后点「刷新」再看。」/「刷新」 | `views/list.js:285-287` |
| 错误（缺组件） | 「活动列表未加载」/「组件有问题，处理办法看页面顶部的提示。」；**`#empty-action` 隐藏** | `views/list.js:225-233` |
| 错误（普通失败） | `listErrorCopy()` 四分支标题（还没登录/登录已过期/暂时无法加载/活动暂时没加载）+ 人话下一步；`#empty-action`「重试」 | `views/list.js:234-241`、`controllers/tick.js:112-123` |

禁止：加载中显示「学校当前没有返回活动」；缺组件时给「登录/重新登录」指引或第二个「重新检查」。

### 3.4 大屏 `#board`（`#board-tag` / `#selected` / `#board-text` / `#rail-message` / 指标）

| 态 | `#board-tag-text` + tone | 标题 `#selected` | 说明 | 证据 |
|---|---|---|---|---|
| 缺组件 | 「组件缺失」red | `runtimeErrorCopy().title`（程序组件缺失/无法读取/启动失败） | 「处理办法看页面顶部的提示。」 | `views/board.js:28-34` |
| 列表失败 | 「需重试」red | 「活动暂时没加载」 | 「具体原因看下面列表的提示。」 | `:35-41` |
| 加载中 | 「加载中」off | 「活动列表正在加载」 | 「正在加载活动，先等这一次加载结束。」 | `:42-48` |
| 首次使用 | 「首次使用」off | 「登录后开始」 | 「活动会在登录完成后自动加载。」 | `:14-19` |
| 登录中 | 「登录中」amber | 「正在打开登录窗口」 | 「在浏览器里登完再回来；中途关掉窗口会保留原来的登录状态。」 | `:20-27` |
| 运行·等开放 | 「等开放」amber | 目标活动名或「这一场活动」 | 「这一场等开放 · 到点自动开始。」/「同时开放 N 场 · 每场结果单独显示。」 | `:52-67` |
| 运行·准备 | 「准备报名」amber | 同上 | 「已开放，正在准备提交。」/「已开放，正在准备 N 场 · 每场任务独立显示结果。」 | 同上 |
| 运行·提交 | 「正在提交」red | 同上 | 「正在提交这一场。」/「正在提交 N 场 · 每场任务独立显示结果。」 | 同上 |
| 运行·准备中/汇总 | 「准备中」/「汇总中」amber | 「正在准备报名」/「正在汇总结果」 | 「计划已经接管，正在核对每一场的开放时间。」/「每一场都结束了，正在汇总这一轮的结果。」 | `:70-76` |
| 未选·有下一场 | 「下一场」amber /「开放中」amber | 活动名 | 「选择活动后可在此查看报名计划。」/「这场已经开放，现在可以选中后开始报名计划。」 | `:79-84` |
| 未选·学校 0 场 | 「暂时没有」off | 「学校这次没有返回活动」 | 「稍后点「刷新」再看。」 | `:85-89` |
| 未选·时钟未知 | 「时间待校准」amber | 「时间待校准」 | 「校准北京时间后才能判断哪些场次可以报名。」+「查看时间详情」按钮 | `:90-96` |
| 未选·无可执行目标 | 「暂时没有」off | 「没有可报名的场次」 | 「列表里的活动已报名、已截止或还没公布报名时间。」 | `:97-102` |
| 未选·未加载 | 「暂时没有」off | 「近期没有要开放的活动」 | 「可能还没公布报名时间，也可能都报过了。过一会儿点「刷新」看看。」 | `:103-107` |
| 已选 | 「报名计划」amber（终态改写为报名成功/部分完成/已停止…） | 单场=活动名，多场=「已选 N 场」 | 单场「在下面的时刻表里确认活动，再开始报名计划。」 | `:110-136` |

指标：`#metric-total` 已知零写 `0`、未加载/失败写 `—`；`#metric-free` 时钟未知写「待确认」；
`#countdown` 未选「待选」、无时间「时间待校准/时间待公布」（`views/list.js:295-321`、`views/board.js:406-463`）。

### 3.5 主按钮与门禁（`updateControls()`，`views/board.js:741-775`）

| 元素 | disabled 条件 | 文案/状态 | 证据 |
|---|---|---|---|
| `#btn-login` | `S.busy ‖ 缺组件 ‖ termsGate` | 「登录/重新登录」 | `:746` + `views/login.js:99` |
| `#btn-refresh` | `listState==="loading" ‖ termsGate` | 「刷新」 | `:747` |
| `#btn-plan` | `!canStart ‖ 时钟不可用`；`canStart` 要求 未繁忙、未 starting、无组件故障、未条款锁定、`login.result==="valid"`（或 demo）、有选择、无校验错/冲突、`listState==="ready"` | 「开始报名计划」/「正在提交…」/「正在确认是否启动…」/「计划运行中」/「北京时间未校准」 | `:755-765` |
| `#btn-stop` | `!busy ‖ !plan.id ‖ stopping` | 「停止」/「正在停止…」 | `:766-767` |
| `#btn-clear-plan` | `busy ‖ (无选择且无任务)` | 「清空选择」 | `:768` |
| `.row-check`（每行） | `busy ‖ 已报名/已截止`（`!isEligibleForPlan`） | — | `:769-773`、`state/filters.js:99-101` |
| `#btn-board-login` | 仅 `present===false && 无组件错 && 未条款锁定` 时显示 | 「登录」 | `:227-235` |
| `#btn-board-pick` | 仅无快捷登录、无选择、无任务、有下一场时显示 | 「选这一场」 | `:231-233` |
| `#empty-action` | 缺组件时隐藏 | 刷新/重试/清除筛选（按 `dataset.action` 分派） | `views/list.js:225-231`、`app.js:324-329` |

### 3.6 计划任务卡 `#plan-tasks`（`taskHtml`，`views/board.js:657-687`）

标签：`等待开放`（preopen）/`准备报名`（preparing）/`提交中`（retrying）/`报名成功`/`已报名`/
`报名未成功`/`已取消`/`排队`/`处理中`（`state/labels.js:47-49`），未知两类改写成
`待核对`（`stop_reason=unconfirmed`）与`未提交`（`stop_reason=auth_unavailable`）（`state/task-display.js:50-62`）。
细节行：preopen「提前准备，等到 HH:MM 开放」或「提前准备，开放时间待公布」；preparing
「已开放，正在准备提交」；retrying = `submittingDetail()`（「已提交 N/M 次」或「已提交 N 次（不限次数）」+
最近原因 +「重试到 HH:MM」/「重试窗口约 mm:ss」/「等待提交结果」）（`views/board.js:628-655`）；
unconfirmed「已提交 N 次，没有拿到确定回应 · 去活动页核对，本工具不会再自动重发」；
auth_unavailable「登录状态无法确认，本场没有提交 · 检查网络后刷新重试」（`:670-684`）。
`取消`按钮仅在 `queued/waiting` 且 `busy` 时出现（`:685-686`）。
禁止：`待核对/未提交` 画成 `is-bad` 红叉（`state/labels.js:51-58` 只给 `is-warn`）。

### 3.7 结果条 `#result`

`hidden` 默认；`ok===true`→`is-ok`，`ok==="partial"`→`is-partial`，其余→`is-bad`
（`views/login.js:118-139`）；结构 `strong 标题 + span 正文 [+ .result-action 按钮]`；
`autoClose` 到期且非 busy 自动收起（`:138`）。计划级结论与单场结论分层：跑着时不写结果条
（`controllers/plan-events.js:107-114`）。

### 3.8 检查条 `#plan-checks`（选中时出现的四条提示）

`网络断开了`（bad）、登录到期「登录估算约 X 过期，可能赶不上这次报名窗口，建议先重新登录」（warn）
或「预计可覆盖本次窗口；临近开放建议再确认」（ok）、时间「北京时间待校准，校准后才能开始计划」/
「正在使用上次校准结果，工具会自动重新校准」/「报名时间按北京时间执行」、
「有场次没提供报名截止：本次最多 2 分钟」、「开放在 24 小时以后」（`views/board.js:247-283`）。
元素为 `span.chk[data-tone]`，前置符号由 CSS 生成（✓/⚠/✕，`styles.css:136-140`）。

### 3.9 横幅 `#banners`（可 0–n 条，`div.banner[data-tone][role=alert]`）

| 触发 | tone | 文案 | 按钮 |
|---|---|---|---|
| 条款状态未知 | warn | 「条款状态没能确认。」+「登录、活动列表和报名计划暂时停用；点「查看条款」打开全文并重新确认，确认成功才会恢复。」 | `data-act="terms-open"`「查看条款」 |
| 条款未同意 | warn | 「还没有同意使用条款。」+（已拒绝 ?「登录、活动列表和报名计划保持停用。」: 「同意后才能登录、查看活动列表与开始报名计划。」） | `data-act="terms-open"` |
| 组件故障 | bad | `runtimeErrorCopy().title` + 「。」+ hint（三条，`controllers/refresh.js:285-289`） | `data-act="runtime-refresh"`「重新检查」 |
| 断网 | bad | 「网络断开了。」+（busy ?「到点时还没恢复，这次报名会失败。恢复以后看一眼计划结果。」: 「恢复以后点「刷新」。」） | 无 |
| 睡眠 | warn | 「刚才有 X 界面没动静，电脑可能睡眠了。」+「要是睡过了开放时间，就赶不上了。看看计划和运行记录。」 | `data-act="sleep-ok"`「知道了」 |

证据：`views/board.js:778-810`。

### 3.10 条款弹窗（M1）

四态（底部操作区由 `applyTermsFooter()` 收敛，`views/terms.js:15-49`）：
- 默认未同意：「暂不使用」+「我已阅读并同意」（都可用）。
- 保存中：`#btn-terms-accept` 文案「正在保存…」且 disabled、`#btn-terms-decline` disabled、
  X disabled、Esc 不生效（`views/terms.js:37-47`、`app.js:187-189`），局部反馈「正在保存…」info（`controllers/terms.js:182`）。
- 超时未确认：`#btn-terms-recheck`「重新确认状态」出现（`views/terms.js:28-34`）；
  同意/暂不使用仍禁用；反馈「保存结果未确认：…门禁保持关闭。点「重新确认状态」核对本机记录。」warn（`controllers/terms.js:257-265`）。
- 只读（已同意同版）：「我已阅读并同意」「暂不使用」隐藏，只留「关闭」；
  反馈「已同意本版（…）；条款更新后会再次展示并要求重新同意。」info（`views/terms.js:27,36,40`、`controllers/terms.js:104-106`）。

错误分支文案（`termsStatus` 写进 `#dlg-terms-status`，`role=status`）：
副本无版本号（`controllers/terms.js:168`）、副本版本与程序版本不一致（`:171-174`、`:200-202`、`:222-224`）、
保存失败（`:204`、`:250`）。全文/要点切换：按钮「查看完整条款」⇄「返回条款要点」，
`aria-expanded` 同步，标题 `#dlg-terms-view-title` 同步，滚动回顶（`views/terms.js:51-64`）。

### 3.11 帮助弹窗（M2）

- 结构：三步说明（`#help-steps`，来自 `bootstrap.help` 或 `DEFAULT_HELP`，`views/help.js:2-8`）+
  唯一「重看引导」；版本行 `#help-version`（来自 `bootstrap.version`，`app.js:18`）；
  更新七态（见 3.12）；本机数据 `#btn-help-data`；条款行 `#help-terms-version`；跨设备与高级功能。
- 运行中只禁重播：按钮文案「计划结束后可重看引导」且 disabled
  （`views/help.js:60-68`；`updateControls` 调 `paintReplayButtons()`，`views/board.js:749`）。
- 局部反馈唯一归属 `#help-status[data-tone]`（`views/help.js:21-33`）：发布页打不开 →
  「发布页没能打开（系统浏览器可能被拦）。地址：<固定 URL>」warn（`app.js:299-305`）；
  数据目录打不开 → 「打不开数据目录：…」bad（`app.js:317-319`）；安装/账号结果 → info/warn（`views/phone.js:118,167-169`）。
  成功打开数据目录**不写** `#help-status`，只把路径写回 `#help-data-path`（`app.js:307-316`）。
- 手机控制面板 `#phone-access-detail`：仅在组件 ready 时展开（`views/phone.js:84`）；
  未开启时 `#phone-address`「未开启」、`#phone-code`「—」、`#phone-qr` 隐藏 +「开启后显示二维码」；
  开启后显示地址/配对码/二维码，`#btn-phone-start` 隐藏、`#btn-phone-stop` 出现（`views/phone.js:85-93`）。
- 高级功能状态词表：`加载失败/已启用/已停用/未安装`（`views/phone.js:9-14`）。

### 3.12 更新七态（`#update-status[data-state]` + `#update-progress` + `#update-flow`）

文案（`views/update.js:20-32`）：
`idle`「尚未检查」／`checking`「正在检查…」／`current`「当前为最新正式版」／
`available`「发现新版本 X」／`no_installer`（后端 text 或「发现新版本，请前往下载页手动下载。」）／
`preview`「当前为预览版本，最新正式版 X」／`unavailable`「暂无正式发布」／
`confirm`「确认下载并安装 X？」／`downloading`「正在下载安装包…」／`verifying`「正在校验安装包…」／
`ready_to_install`「安装包已校验通过，可以启动安装程序。」／`launching`「正在启动安装程序…」／
`error`「暂时无法检查更新。」+ 原因／`failed`（后端 text 或「更新没能完成，请重试。」）。

按钮显隐（`views/update.js:52-65`）：`下载并安装` 仅 `available|failed` 且有 installer；
`确认下载` 仅 `confirm`；`启动安装程序` 仅 `ready_to_install`；`取消` 仅 `confirm|downloading`；
`检查更新` 在 `checking/downloading/verifying/launching` 时 disabled（`:17-19`），
`error|failed` 时改文案「重试检查」。进度行：downloading「已下载 X / Y（N%）」、
verifying「正在比对大小与 SHA-256…」、ready_to_install「已通过大小与 SHA-256 校验」（`:41-51`）；
「检查时间 MM-DD HH:MM」只在有 `checked_at` 且非 checking 时显示（`:34-37`）。

### 3.13 六步引导（L5）

`#tour-step`「第 N/6 步」、`#tour-title`、`#tour-text`、`#tour-dots`；
`#tour-prev` 在第 1 步 disabled；`#tour-next` 最后一步文案「完成」（`views/tour.js:82-88`）。
高亮可用条件：目标存在、`innerWidth > 980`、目标有尺寸（`:91-94`）；不满足则 `#tour.is-bottom`
退回底部说明条，且不写 `#tour-spot` 几何（`:99-102`、`styles.css:509-510`）。
运行中暂停：`#tour.hidden=true`（`:65-68`），结束 `tourResumeNow()`（`:70-75`）。

### 3.14 运行记录 `#logbar[data-open]` / `#log`

收起（`data-open="false"`）：`.when-open` 与 `.logbody` 隐藏，只显示 `#log-last`
（「还没有记录」初始，之后为「HH:MM:SS  最新一句」）；展开（`true`）：`#log-last` 隐藏、
`#log` 高度 196px 内部滚动（`views/log.js:2-9`、`styles.css:317`）。
行前缀着色：`[X]`→`data-k=bad` 红、`[!]`→warn、`[OK]`/`▶`→ok（`views/login.js:157-160`、`styles.css:320-322`）；
最多 500 行（`views/login.js:163`）；无业务时间戳时前缀「待校准」（`:149-150`）。

---

## 4. 视觉验收判据（逐条机械可判）

> 每条：**看哪个元素** → 期望值 / **禁止**。全部可在 DevTools 控制台一条 `document.querySelector(...)` 判定。

**V-01 名称契约**：`document.title === "校园活动预报名工具"`，`.name-full` 文本相同；
视口 ≤860px 时 `.name-short` 可见且 `.name-full` 隐藏。禁止出现「准点」。
证据 `local/ui/index.html:6,14`、`styles.css:39,553`、`docs/UI_SPEC.md:13-19`。

**V-02 顶栏四件套**：`#clock`、`#pill`、`#btn-help`、`#btn-refresh`、`#btn-login` 同时可见在
`.top-right` 内；`#btn-help` 的 `aria-label` 恰为「帮助：使用说明、版本更新与本机数据」。
证据 `index.html:17-23`。

**V-03 胶囊状态机**：`#pill.dataset.state ∈ {none, unknown, bad, ok, warn, checking, pending, demo}`，
且 `className` 含对应 `is-none/is-bad/is-ok/is-warn/is-busy`；`#pill-text` 与 §3.1 表一致。
禁止：`data-state="checking"` 时 `#pill-text` 为「已登录」。证据 `views/login.js:2-105`。

**V-04 时钟五态**：`#clock.dataset.state ∈ {ready, holdover, syncing, unavailable, demo}`；
`syncing` → `#clock-time==="校准中…"`，`unavailable` → `"待校准"`，
`demo` → `#clock-label==="演示时间"`；`#clock.title` 必须包含 `CLOCK_COPY[state].label`。
禁止：`unavailable` 时 `#clock-time` 显示 `HH:MM:SS` 形态的数字。证据 `views/clock.js:5-21`。

**V-05 骨架先于空态**：`S.listState==="loading" && items.length===0` 时
`#rows .skel` 存在且 `#empty.hidden===true`；`#rows .skel-row` 数量为 6。
禁止：同一时刻 `#empty` 可见或 `#empty-title` 为「学校当前没有返回活动」。
证据 `views/list.js:26-31,63-67`。

**V-06 空态唯一动作**：`#empty` 可见时 `#empty-action` 必须可见（**唯一例外**：`S.runtime.error` 为真时隐藏）；
`#empty-action.dataset.action ∈ {refresh, clear-filters}`，且「清除筛选」只配 `items.length>0` 分支。
禁止：按按钮文字/`items.length` 反推动作。证据 `views/list.js:211-288`、`app.js:324-329`。

**V-07 空态四分支不与登录态错配**：`loginEmptyState()` = checking/none/expired/unknown/valid 五值，
对应标题逐字匹配 §3.3 表；`valid` 分支标题必须是「学校当前没有返回活动」且正文不得出现
「登录」「重新登录」字样。证据 `views/list.js:195-201,259-287`。

**V-08 错误说明唯一归属**：`S.runtime.error` 非空时，页面中含「重新检查」的按钮**只有一个**
（`#banners [data-act="runtime-refresh"]`）；`#empty` 内不得出现「重新检查」，`#result` 不得出现
组件错误文案。证据 `views/board.js:793-799`、`views/list.js:225-233`、`docs/UI_SPEC.md:301`。

**V-09 整屏边框只认计划级状态**：`#board.dataset.planState ∈ {idle, running, completed, failed, partial, stopped, attention}`；
边框颜色映射：completed→`--green`、failed→`--red`、partial→`--amber-dim`、attention→`--amber-dim`、
idle/running/stopped→无 2px 内描边。**含未知（`planOutcome().unknown>0`）且非 completed 时必须为 `attention`。**
禁止：`failed` 与 `unknown>0` 同时成立时出现红边框。证据 `views/board.js:153-166`、`styles.css:93-97`。

**V-10 结果条三色**：`#result.className` ∈ {`result is-ok`, `result is-partial`, `result is-bad`}；
`ok===true` 仅 is-ok、`ok==="partial"` 仅 is-partial。禁止：含未知的计划结论用 `is-bad`。
证据 `views/login.js:129-130`、`controllers/plan-events.js:56-64`。

**V-11 任务卡未知不画红**：`stop_reason==="unconfirmed"` 的任务 `.task-state` 必须含 `is-warn`
且文案「待核对」；`auth_unavailable` → `is-warn` +「未提交」。禁止出现 `is-bad`。
证据 `state/labels.js:51-58`、`state/task-display.js:55-61`。

**V-12 计划总结五项分列**：终态结果条正文必须同时出现「报名未成功」「待核对」「未提交」「已取消」
四个计数段（`splitText`，`controllers/plan-events.js:30-32`）。禁止用「都没抢到」「N 场都没抢到」。
禁止 `auth_unavailable` 场次出现「登录失效」「请重新登录」。证据 `docs/UI_SPEC.md:478-489`。

**V-13 主按钮门禁**：`#btn-plan.disabled===false` 时下列全部成立：`!S.busy`、`!S.starting`、
`!S.runtime.error`、`!termsLocked()`、`(S.demo || (!S.login.checking && S.login.result==="valid"))`、
`S.selected.size>0`、`validateSelection().errors.length===0`、`validateSelection().conflicts.length===0`、
`S.listState==="ready"`、`businessNowMs()!==null`。任一条不成立则 disabled 必须为 true。
证据 `views/board.js:755-761`。

**V-14 时钟门禁可见原因**：时钟不可用（`businessNowMs()===null && !demo`）时
`#btn-plan.textContent==="北京时间未校准"` 且 disabled。证据 `views/board.js:759-765`。

**V-15 停止链**：`S.stopping` 为真时 `#btn-stop.textContent==="正在停止…"` 且 disabled，
`#pill` 的 `#status-detail` 为「正在停止计划；已报名的场次不受影响」。证据 `views/board.js:766-767`、`views/login.js:19`。

**V-16 冲突可见**：存在 `conflictIds()` 命中行时 `#plan-conflicts.hidden===false`，
每条含 `strong` 标题 + 正文，且至少一条文案匹配「举办时段重叠」或「同一计划只能选择其中一场」。
禁止：冲突存在时 `#btn-plan` 可点。证据 `views/board.js:318-334`、`state/filters.js:186-203`。

**V-17 行三态可读**：`.row` 的 class 组合可判：`is-selected`（选中，左侧 3px `--blue`）、`is-armed`
（提交中，左侧 3px 深色竖条）、`is-signed`/`is-closed`（名字变细、时间灰）、`is-unknown`、
`is-conflict`（背景 `--warn-tint`）。已报名/已截止行 `.row-check.disabled===true`。
证据 `views/list.js:128-137`、`styles.css:263-268`。

**V-18 签到/签退 unknown 不写「无需」**：`checkin_required===null` 时行内 flag 文案只能是
「签到信息同步中」（`attendance_state==="pending"`）或「签到时间待确认」，且带 `is-unknown` 类。
禁止「无需签到」。签退同构。证据 `state/filters.js:39-61`、`docs/UI_SPEC.md:203-215`。

**V-19 筛选取值语义**：`#chips button.chip` 的选中态用 `aria-pressed==="true"`（恰好一个），
禁止 `aria-selected`；`#checkin`/`#checkout` 取 `all|yes|no`；`yes` 只显 `true`、`no` 只显 `false`、
`all` 保留 `null`。证据 `views/selection.js:2-22`、`state/filters.js:32-37`、`docs/UI_SPEC.md:211,514-515`。

**V-20 清筛选只清六键**：调用「清除筛选」后 `#q` 为空、`#chips` 回到 `all`、`#time/#sort/#checkin/#checkout`
回 `all/open/all/all`，且 `#retry-for`、`#max-attempts`、`#headed`、日志展开态**保持不变**；
`savePrefs` 写入载荷只含 `filter`。证据 `controllers/refresh.js:35-49`、`docs/UI_SPEC.md:324`。

**V-21 已知零 vs 未知**：`#metric-total`/`#count` 在 `listState==="ready"` 时必须为数字（0 也写 `0`）；
`idle`/`error` 且无缓存时 `#metric-total==="—"`。`#metric-free` 在时钟未知且已知行数时写「待确认」。
禁止把未加载写成 `0`。证据 `views/list.js:290-305`、`docs/UI_SPEC.md:325`。

**V-22 地点两行 + 键盘展开**：`.c-place[role="button"][tabindex="0"][aria-expanded]` 存在；
聚焦后按 Enter/Space → `aria-expanded` 翻转且**不改变** `.row-check.checked`、不触发开始计划；
大屏 `#selected-meta [data-place-toggle]` 同为 `button[aria-expanded]`。
证据 `views/list.js:167`、`app.js:150-167`、`views/board.js:168-203`、`docs/UI_SPEC.md:492-496`。

**V-23 引导高亮诚实性**：`#tour` 可见且 `innerWidth<=980` 或目标缺失时 `#tour.is-bottom` 存在且
`#tour-spot` 无内联几何；`#tour-card` 必须完全在视口内。引导打开时背景 `Enter` 不开始计划、
`Ctrl+F`/`/` 不聚焦 `#q`。证据 `views/tour.js:89-121`、`app.js:331-352`。

**V-24 引导不代操作**：`TOUR_STEPS` 六步 `target` 依次为 `login/list/filters/select/start/run`；
引导活动期间 `window.pywebview.api` 的 `login/start_plan/check/list_activities` 调用次数为 0。
证据 `state/store.js:31-44`、`views/tour.js`（全文件无 api 调用）。

**V-25 弹窗互斥**：任一时刻 `document.querySelectorAll("dialog[open]").length <= 1`；
`#help` 与 `#dlg-terms` 不得同时 open。证据 `views/terms.js:111-115`、`views/help.js:14`。

**V-26 键盘不穿透**：`#dlg-terms[open]` 时按 Esc/Enter/Ctrl+F/F5 → `#btn-plan` 无 click、
`S.selected` 不变、`#q` 未聚焦、无新 check/list 请求（仅保存中 Esc 被 `cancel` 拦）。
证据 `app.js:331-336,187-189`。

**V-27 停止确认语义**：`#dlg-stop` 打开时 Esc 或「继续计划」→ `S.plan.id` 不变、无 `stop_plan` 调用；
只有 `returnValue==="yes"` 触发。证据 `app.js:226-231`、`index.html:283`。

**V-28 日志折叠**：`#logbar[data-open="false"]` 时 `.when-open` 与 `#log` 均不可见、`#log-last` 可见；
`true` 时相反，且 `#log` 高度固定 196px 内滚（页面不出现纵向溢出）。证据 `styles.css:317`、`views/log.js:2-9`。

**V-29 更新七态动作唯一**：`paintUpdate` 后 `#update-flow` 内最多一个 `.btn` 非 hidden
（`confirm` 态为「确认下载」+「取消」两个，属文档明列的例外）。`checking/downloading/verifying/launching`
时 `#btn-update-check.disabled===true`。证据 `views/update.js:52-65`、`docs/UI_SPEC.md:553-558`。

**V-30 更新文案零估计**：downloading 的百分比与字节必须来自 `result.downloaded/total_bytes`，
禁止出现客户端计算的估算值。证据 `views/update.js:41-44`。

**V-31 版本唯一显示位**：含 `info.version` 的元素只有 `#help-version`（另有条款版本 `#help-terms-version`、
`#dlg-terms-version` 属不同语义）。禁止顶栏/大屏/日志出现版本号。证据 `app.js:18`、`docs/UI_SPEC.md:286`。

**V-32 运行中重播禁用**：`S.busy` 为真时 `#btn-help-tour.disabled===true` 且文案恰为
「计划结束后可重看引导」。证据 `views/help.js:60-68`。

**V-33 顶部时钟不进本机墙钟**：注入 ±8h/±30d 的 OS 时差后，`#clock-time`、`#countdown`、
`#led`、`#route` 的数值不变（仍按 `businessNowMs()`）。证据 `controllers/tick.js:4-63`、`state/clock.js:195-211`。

**V-34 LED 口径**：`#led[data-tone] ∈ {off, dim, amber, red, green}`；运行中 waiting 用 `amber`、
最后 10 秒 `red`、arming/submitting 无盲区（`--:--:--` + 「准备中」/「待定」），
终态 ✓/✕ 只在 `S.plan.doneSelection === selectionSignature()` 时留在屏上。
禁止：提交中且截止未知时显示 `00:00:00`。证据 `views/board.js:472-590`。

**V-35 路线图不编时间**：五个 `.stn` 的 `data-s ∈ {done, now, hot, todo}`；
未发生节点的时间文本必须是「待启动/待打开/待开始/待定」之一，**禁止**出现形如 `HH:MM:SS` 的估算时刻。
证据 `views/board.js:364-379`、`docs/UI_SPEC.md:266`。

**V-36 五视口无横向滚动**：980×760、1120×800、1280×900、746×512、680×480 下
`document.documentElement.scrollWidth <= clientWidth`，且 `#btn-help/#btn-refresh/#btn-plan/#btn-stop`
落在视口内或整页可滚达并被真实指针点中（`elementFromPoint` 命中自身）。
证据 `docs/UI_SPEC.md:617,687`。

**V-37 50px/56px 顶栏不裁剪**：`header.top` 高度 56px（`styles.css:33`），
`max-height:720px` 媒体查询不得把控件切掉一半；≤560px 时 `.top-right` 换行且控件 `max-width:100%`。
证据 `styles.css:532-560`、`docs/UI_SPEC.md:15-17`。

**V-38 对比度**：正文 `--ink #1a1f24` on `--paper #fff`、已报名灰 `--ink-2 #4e5964`、
大屏 `--on-board-2 #a7afa9` on `--board #121513` 均 ≥4.5:1。证据 `styles.css:4-11`、`docs/UI_SPEC.md:609`。

**V-39 键盘焦点**：`:focus-visible` 有 2px 蓝色描边（`styles.css:27`），大屏内为琥珀色（`:98`）；
Tab 顺序 = DOM 顺序；`#rows` 可聚焦（`tabindex="0"`）。证据 `index.html:74`。

**V-40 文案违禁词**：界面可见文本中不得出现 `token/接口/子进程/退出码/报错码`；
错误文案必须同时含「发生了什么」与「现在能做什么」。证据 `docs/UI_SPEC.md:588-593`、
`controllers/refresh.js:285-289`、`controllers/plan.js:395-403`。

**V-41 事件态一致性（F5 恢复）**：`plan_done` 落地后 `bootstrap()` 恢复（`ingestBootstrapPlan`）
必须复现同一组：`#result` 类与文案、任务卡次数与原因、`#led` 字形、`#board.dataset.planState`、
`#btn-plan` 文案；且**不重发** `start_plan`。证据 `controllers/refresh.js:59-90`、`docs/UI_SPEC.md:517-524`。

**V-42 单飞**：连续两次点「开始报名计划」只产生一个计划（`S.starting` 立即置真 + 后端原子接纳）；
`#btn-plan` 文案在点击后 1 帧内变「正在提交…」。证据 `controllers/plan.js:36-45`、`views/board.js:762-765`。

---

## 5. 文档 ↔ 实现不一致清单（不消解，待裁定）

**D01 · §9 条目数**：`docs/UI_SPEC.md:626-693` 实数 63 条 `- [ ]`；任务口径称 69 条。
差异 6 条，需确认是多轮增删后的口径漂移，还是另有清单文件。

**D02 · 路线图站点名与未发生文案**：规范 §5.10.9 写「本次启动 / 活动页已打开 / **盯按钮** /
原定开放 / **本次重试到**」，未发生显示「待启动 / 待打开 / **待发生**」（`docs/UI_SPEC.md:266`）；
实现为「本次启动 / 活动页已打开 / **开始监测** / 原定开放 / **本次尝试截止**」，
未发生显示「待启动 / 待打开 / **待开始** / **待定**」（`local/ui/views/board.js:365-371`）。
**影响**：按文档字面检索的验收脚本会全部落空。

**D03 · 顶栏时钟「五态」的可见文案**：规范 §5.16.13 要求顶栏唯一时间入口五态
（已校准／校准中…／使用上次校准结果／待校准／演示时间）（`docs/UI_SPEC.md:425-427`）；
实现只把 `syncing`→「校准中…」、`unavailable`→「待校准」写进 `#clock-time`，
`ready`/`holdover` 只显示时刻、标签恒为「北京时间」，`演示时间` 只换 `#clock-label`。
「已校准」「使用上次校准结果」只出现在 `title`/`aria-label` 与浮层 `CLOCK_COPY.label`
（`local/ui/views/clock.js:11-21`、`local/ui/state/clock.js:29-35`）。
**影响**：肉眼验收看不到 holdover 与 ready 的区分，只有图标颜色不同（`styles.css:48-53`）。

**D04 · 注释与规范互相矛盾**：`local/ui/controllers/tick.js:131-133` 注释写
「顶栏那颗时钟仍显示本机时间，因为它是给人看『这台电脑现在几点』的」，与
`docs/UI_SPEC.md:363-365`（顶栏显示工具独立北京时间，未校准显示「待校准」，不回退本机时间）
及同文件实际实现（`tick()` 调 `paintClockStatus()` → `businessNowMs()`）矛盾。属遗留注释。

**D05 ·「一条坏色横幅」措辞**：规范 §5.13.5 写「一条坏色横幅（标题 + 恢复动作）不满屏重复」
（`docs/UI_SPEC.md:296`）；`paintBanners()` 允许「组件故障」(`data-tone="bad"`) 与「网络断开了」
(`data-tone="bad"`) 同时各挂一条（`local/ui/views/board.js:793-803`）。
按 §5.13.10「一个错误只有一个主要说明」仍有歧义，需明确「不同成因可并存、同一成因唯一」。

**D06 · 开始按钮的「单一可见原因」只覆盖时钟**：`#btn-plan` 只在时钟不可用时改写文案
（`local/ui/views/board.js:759-765`）；`login.result!=="valid"`、无选择、有冲突、列表未就绪时
按钮仍写「开始报名计划」，界面上没有可见禁用原因（只有「计划还不能开始」的结果条，
且那条只在点过按钮后出现，而按钮此时已 disabled，点不到——`local/ui/controllers/plan.js:14-18` 这条分支走不到）。
需裁定：是补可见原因，还是接受「门禁不可见」。

**D07 · 计划总结词表**：规范 §5.17.4 要求按「成功 / 确认未成功 / 待核对 / 未提交 / 取消」逐项分列
（`docs/UI_SPEC.md:480-482`）；实现分列为「**已报名** N 场 · **报名未成功** N 场 · 待核对 N 场 ·
未提交 N 场 · **已取消** N 场」，且 `success` 与 `already_signed` 合并进「已报名」
（`local/ui/controllers/plan-events.js:30-32`）。
**影响**：验收脚本按「成功」检索会失败；用户也无法区分「本次抢到」与「本来就报过」。

**D08 · §4 状态矩阵词表 vs 实现词表**：矩阵写任务条「等待开放/**提交中/成功**/已报名/**失败**/已取消」
（`docs/UI_SPEC.md:93`）；实现为「等待开放/准备报名/提交中/**报名成功**/已报名/**报名未成功**/已取消/排队/处理中」
（`local/ui/state/labels.js:47-49` + `local/ui/state/task-display.js:50-62`）。
§5.17 的新增词（待核对/未提交）已实现，矩阵未同步。

**D09 · 筛选胶囊文案与顺序**：§4 ASCII 图为「[全部|未报名|已报名]」（`docs/UI_SPEC.md:68`），
实现为「可报名｜已报名｜全部」，默认选中 `全部`（`local/ui/index.html:67`、`docs/UI_SPEC.md:51` 要求默认全部）。
以实现为准时，§4 图需改。

**D10 · 更新七态「一个可做动作」的自洽性**：§5.18.1「每个状态只留一个可做的动作…按钮多于一个可点即不合格」
（`docs/UI_SPEC.md:553-558`）与实现冲突的只有一处：`available`/`failed` 时
`#btn-update-check` 仍可点、「下载并安装」也可点（`local/ui/views/update.js:17-19,57-58`）。
需明确「检查更新」是否计入「可做动作」。

**D11 · 帮助三步说明第二步措辞**：§6 要求第二步写出「再点「开始报名计划」」（`docs/UI_SPEC.md:601`），
前端兜底 `DEFAULT_HELP` 写的是「再选择「开始报名计划」」（`local/ui/state/store.js:9`）。
后端 `Api.help()` 载荷未核对（`local/app.py` 未读），需在真实 bootstrap 下核对实际文案。

**D12 · 帮助面板缺少 JS 依赖的两个节点**：`local/ui/views/phone.js:48,52` 查找
`#btn-phone-feature-remove` 与 `#ocr-feature-status`，`local/ui/index.html:230,243` 均无此 id
（高级功能区只有一个无 id 的 `<span class="help-feature-status">按需安装</span>`）。
**影响**：「高级功能」行状态恒为静态「按需安装」，ddddocr 安装结果只能从 `#help-status` 反馈里看。

**D13 · `#pill` 是空按钮**：`index.html:18` 是 `<button class="pill" id="pill" type="button">`，
`local/ui/app.js` 全文件无 `#pill` 的点击监听，也无 disabled 管理。
**影响**：可访问性上是「可聚焦但无动作」的按钮；若设计稿本意是可点击查看登录详情，属实现缺口。

**D14 · 空态初始 HTML 与首帧渲染不一致**：`index.html:77` 初始文案为
「这里还没有活动 / 点「刷新」加载活动；需要登录时，顶部会提示下一步。/ 刷新」；
`paintEmpty()` 首帧会覆盖为「还没有加载活动列表 / 点「刷新」加载一次；…」（`local/ui/views/list.js:250-257`）。
**影响**：`render()` 之前的截图不能作为验收基线；验收必须以首帧 `render()` 后为准。

**D15 · §5.13 与 §5.15 的双入口描述并存**：§5.13.1 仍写「顶栏并列两个入口——「说明」与「更多」」
（`docs/UI_SPEC.md:292`），同节已声明被 §5.15 取代（`:290`）；实现只有 `#btn-help` 单入口。
属文档内部矛盾，验收一律按 §5.15。

**D16 · 时钟浮层宽度**：§5.16.13 写「340px 详情浮层」（`docs/UI_SPEC.md:425`），
实现 `.pop{width:360px}`（`local/ui/styles.css:455`）。以哪个为准需裁定（340 或 360 都要改一处）。

**D17 · 引导降级阈值与 CSS 断点不一致**：引导降级用 `innerWidth > 980`（`local/ui/views/tour.js:92`），
而 CSS 断点为 1060/900/860/560（`local/ui/styles.css:517,526,553,545`）。
**影响**：981–1059px 区间引导仍做高亮，但该区间大屏/顶栏已按窄窗重排，高亮框可能与重排后的目标错位；
需实机确认 980–1060 区间的 `#tour-spot` 是否准确。

---

## 6. 未能静态核实的项（需实机/截图裁定，不含结论）

1. LED 点阵字形与 `aria-label="计划点阵屏"` 的实际朗读内容（`local/ui/led.js` 未读）。
2. 100% / 150% 缩放下的像素对齐与 `--cols` 五列是否溢出（需真机）。
3. `local/ui/m/`（手机页三文件，537 行 app.js）与桌面版的状态口径一致性——不在本次桌面验收内。
4. 后端 `Api.help()` / `bootstrap.help` 实际载荷是否与 `DEFAULT_HELP` 逐字段一致（`local/app.py` 未读）。
5. `#banners` 高度挤占时 680×480 下 `#rows` 的可达高度（需实测几何）。
6. `docs/UI_SPEC.md:517-545`（§5.17.12）中 `plan_generation` 归属判定的界面表现——只做了静态代码核对
   （`local/ui/state/plan.js:30-45`），未做并发时序验证。
