# L4 主窗口：原型 24 画板与现行代码对账表（2026-11-08）

只读审计，没有改任何代码和原型。用途：后面的修单照这张表给执行者下具体指令。
素材：夜班两份只读素材（`<过程留证>/l4-proto.md` 原型侧、`l4-code.md` 代码侧，不入库），合并时对关键 file:line 做了抽查复核（见文末「抽查复核记录」，40 余处，修正 4 处；对抗审阅再勘误：其中 3 处反向，见文末「修订记录」）。

## 范围与读法

- **基准**：`design/prototype/workbench-2026-11/Main.dc.html` 工作区版 **2498 行**（1–528 CSS；530–915 DOM；917 scene 枚举；919–2495 DCLogic）；a85209e 时为 **2283 行**。行号一律以工作区在途版为准，下称 `Main:NNNN`。Main.dc.html 本身有未提交改动。
- **画板清单（24 张薄壳，全部 `dc-import name="Main"`）**，按本表分组编号：
  1. Medium（draft/medium）2. Narrow（draft/narrow）
  3. Normal 4. LongName 5. Filters 6. NoResult 7. ZeroAct 8. ListErr 9. Attention（unknown）10. Broken 11. Expired 12. NetOff 13. Slept（以上 wide）
  14. Waiting（wide）15. MediumRun（running/medium）16. RunClick 17. RunAuto 18. RunPhone 19. NarrowWarn（prewarn/narrow）20. NarrowResult（result/narrow）
  21. SecondRun 22. ToastMin 23. LogOpen 24. Policy（以上 wide）
  另有可操作基准画板 **Main**（Main.dc.html 本体，不计薄壳），归第一组。
- **清单勘误**（已逐张核 dc-import）：磁盘另有 `Running.dc.html`（running/wide）与 `PreWarn.dc.html`（prewarn/wide），与 15/19 号画板同 scene 不同 tier；素材乙的 24 表把 Main.dc.html 本体计为画板、漏了 Attention.dc.html、以 Running/PreWarn 替代 MediumRun/NarrowWarn，且称「画板清单无独立 Unknown 画板」——实有 `Attention.dc.html`（scene="unknown"，1280×800）。本表以素材甲的 24 张为准，Running/PreWarn 在第三组末尾各附一行勘误。
- **三档宽度实值**（薄壳 hint-size 写明，已复核 Medium 900×700、Narrow 430×820、ToastMin 1280×800）：wide = 1280×800，medium = 900×700，narrow = 430×820。`two=(tier==='wide')`、`narrow=(tier==='narrow')`、`short = props.short || 窗高<660`（Main:2172-2173）。
- **在途改动影响**：`local/ui` 下 13 个已跟踪文件有未提交修改（app.js、index.html、styles.css、views/list.js、views/plan-panel.js、state/filters.js、state/labels.js、state/store.js、controllers/plan.js、controllers/refresh.js、controllers/tick.js，另 m/app.js、m/styles.css 属手机页 L3 范围），3 个未跟踪新增（views/conflict-tip.js、controllers/cancel.js、state/conflict.js）。**所有 local/ 行号按磁盘现状，合入后会漂移；文案逐字以反引号原文为准。**
- **列的含义**（照 2026-11-07/settings-gap.md）：差距类型 = 文案 / 结构 / 缺失 / 多出 / 状态 / 样式 / 已一致。后端信号「有」写 UI 实际消费的字段，「需补」写最小新增字段。一行可含多型，统计按型计次。
- **合并口径**：素材甲标【已复现】的行号未逐条复验的，按原文引用；本次亲自复核过的事实（画板薄壳声明、Main 关键行、local/ui 文案与函数、后端通知）在行内直接给 file:line。

---

## 一、顶栏与窗口三档（基准 Main + 画板 1–2）

| 编号 | 画板·区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| TF01 | Main·外框 | 顶栏 `header.top`（Main:532）→ 冲突气泡 `tipb`（562，frozen 收起）→ 提示横幅（576）→ 主区 `.main`（580：列表+计划栏 flex `0 0 25rem`，Main:2455）→ 底部运行记录条（689）；中窄档加 dock（685）；仅 ToastMin 自绘标题栏 `wbar`（531） | `.zd#zd`（index.html:11）→ 顶栏（14-29）→ `#banners`（31）→ `main.work#work` 双栏（33，styles.css:99）→ `section.table#timetable`（34）/`aside.board.plan-panel#board`（51）→ `footer.logbar#logbar`（101）；整屏边框按 `data-plan-state` 着色（styles.css:101-107） | 已一致（主干结构）；`tipb` 对应物为在途新增 `views/conflict-tip.js`（未入库，未深对） | — | 合入在途改动后复核冲突气泡层（conflict 专项切片） |
| TF02 | Main·顶栏构成 | mark+`校园活动预报名工具`（Main:2428，w≤860 换 `校园预报名工具`）；时钟 `北京时间`+`14:20:05`（535/2429）；登录 pill `已登录`+`14:20 校验`（542/2443）；手机 pill `手机已连接`（2453）；分隔线（556）；`刷新`（title `刷新（F5）`，aria `刷新登录状态和活动列表`）、`设置`、`帮助`（557-559） | 品牌名全/短同字（index.html:17），另有副句 `活动查询与报名计划`（原型无）；按钮 title：`刷新登录状态和活动列表（F5）`/`设置：高级功能、登录、程序`/`帮助：使用说明、快捷键、重看引导`（index.html:26-28）——刷新 title 语序与原型 `刷新（F5）` 不同 | 文案 + 多出 | — | title 照原型改；`活动查询与报名计划` 一句需用户定（见 NEEDS-HUMAN 6） |
| TF03 | Main·登录 pill 状态机 | `已登录/未登录/登录待确认/登录已失效/登录中…/自动登录中…`（Main:2400），tone ok/''/warn/bad/busy/busy（2401） | `未登录/已登录`（views/login.js:9,20）、`登录待确认`（:58）、`登录已失效`（:65）、`自动登录中…`（:35，is-busy）——逐字同 | 已一致 | 有：`bootstrap.login`（result/present/hours_left）、`S.autoLogin`（中继进度事件 origin=auto） | 不动 |
| TF04 | 画板1 Medium·外框（draft/medium 900×700） | 900px；品牌与文字 pill 保留、按钮只剩图标（Main:2428 btnLabels=two=false）；planOpen=false → 只显示列表、dock 常驻（Main:2455）；计划栏是点 `查看计划` 后的全屏视图（showBack → `返回列表`） | `styles.css:762-767`：≤1039 藏 `.work .board`，`#zd[data-plan-open="1"]` 反转藏表显栏；按钮图标化（:763）；`#btn-dock-open`→`setPlanOpen(true)`（app.js:303）、`#btn-plan-back`→false（app.js:304） | 已一致（等价实现：原型按 tier 档，代码按窗口宽度断点；900 档落在代码 720–1039 区间，行为一致） | — | 不动 |
| TF05 | 画板1 Medium·dock 文案与缺态 | dock 标题 `已选 N 场`/`还没选活动`，副文取 `还差一步：…`/`有 N 条提醒，开始前先看一眼`/摘要句如 `1 场立即报名，2 场预报名等开放`（Main:2422、Main:2283）；修改中换 `修改中：已选 N 场`/`计划已暂停，改完要重新开始`（Main:2423）；结果态 dock=结论标题/正文（Main:2425） | `paintDock`（views/plan-panel.js:1310-1333）：`还没选活动`+`在时刻表里勾选想报的活动`/`已选 N 场`/`报名计划运行中`；副文取 `#countdown` 倒计时文本（:1321、:1324）而非摘要句；提醒 `有 N 条提醒，开始前先看一眼`（:1326-1327）；**无 `S.editing` 分支、无结果态分支** | 缺失（修改中态、结果态）+ 文案（副文信息源：摘要句 vs 倒计时） | 有：`S.busy`、`S.preWarnCount`、`plan_done` 事件 | 照原型改（纯前端补两个 dock 分支与摘要副文）；与 NEEDS-HUMAN 7 相关 |
| TF06 | 画板2 Narrow·外框（draft/narrow 430×820） | 430px；无品牌、无 `北京时间` 小字、无分隔线；列表无列头、无地点列、时间内联、奖励行内 `2 分 · 工资 20`、活动时段短式、搜索占位 `搜活动或地点`；网格四列式 `1.25rem 3rem minmax(0,1fr) 3.75rem`（仅骨架行 Main:2459；Main:2181 窄档 cols 为三列 `1.25rem minmax(0,1fr) auto`，与四列引文不符） | `styles.css:726-750`：≤860 地点列收起、品牌换短名、筛选下拉标签隐藏；`styles.css:769-771` ≤719 藏 `.clock-label`；`styles.css:718-724` ≤560 顶栏换行；矮窗 <660 压缩 LED（styles.css:772-779） | 已一致（地点列收起等价：原型逻辑隐藏，代码 CSS 隐藏同一列） | — | 不动 |
| TF07 | 画板1/2·分档依据 | tier 由画板显式传入（frozen 画板全显式）；wide 恒双栏 `panelFlex 0 0 25rem`，中窄按 planOpen 切换（Main:2455） | 分档按窗口实测宽度：宽 ≥1040 / 中 720–1039 / 窄 <720 / 矮 <660（views/plan-panel.js:1283 bandOf，注释声明与 styles.css 同组阈值；styles.css:762/769/772、:980 宽档强制藏 dock） | 结构（设计档位 vs 响应式断点） | — | 保留并说明：产品窗口连续缩放，断点制合理，三档语义均已覆盖 |

## 二、主列表组（画板 3–13：正常/长名/筛选/空态×3/异常×5）

| 编号 | 画板·区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| LS01 | 画板3 Normal·外框 | wide 双栏；11 行全出，m2 `不可加入` chip、t1 `下一场`+`9 分 55 秒`（soon 橙）、o1 `已开放 5 时 20 分`、s1/c1/u1 dim（Main:2234-2237）；分组序按 Main:2202 原文 `var order = ['正在开放', '今天', '明天', '后天', '待公布', '已报名', '已截止']`——`待公布`→`已报名`→`已截止`（已报名在已截止前）；分段 `可报名 8` `已报名 1` `全部 11`（Main:2202-2216/2457） | 列表骨架 `.list#list`（index.html:44）、行渲染 rowHtml（views/list.js:128-191）；分组 groupTimetable（list.js:76-115）原文序：`报名时间待公布`（:110）→`已截止`（:112，旁注 `只能查看`）→`已报名`（:113）——已截止在已报名前，**与原型互换**；chips `可报名/已报名/全部`（index.html:37）+paintChips 计数（views/selection.js:2-22） | 结构（分组序：原型 已报名→已截止，代码 已截止→已报名）；行态与计数一致 | 有：`activities` 事件 items[]（state/filters.js:4-24 normalize）、`seconds_to_open` | 照原型改（对调 list.js 两组顺序） |
| LS02 | 画板3 Normal·计划栏未选态 | tag `报名计划`；LED `00:09:55`/`最近开放`/`14:30:00`；标题=下一场活动名；副文 `图书馆报告厅，11月5日 19:00–20:30`；`选这一场`；政策 `尝试 2 分钟，不限次数`+`修改`；chips `✓ 登录和北京时间都没问题`；`开始报名计划` 禁用+why `还差一步：先在时刻表勾选活动`（Main:2310/2321/2328/634/636/2465/2478/2133） | `index.html:52/56/59/68/85`；未选四分支（plan-panel.js:90-121：`下一场`/`开放中`、`暂时没有`、`时间待校准`+`查看时间详情`、`没有可报名的场次`、`近期没有要开放的活动`）；why 逐字同（plan-panel.js:422 一带） | 已一致（核心句）；`时间待校准` 分支为多出（有意扩展，原型未画） | 有：`bootstrap.business_clock`、login、plan 快照 | 不动；`时间待校准` 分支列给用户补画板 |
| LS03 | 画板4 LongName·外框 | 同 Normal 框架；差异=勾选超长名 m1 后计划栏呈现长名（Main:1077） | 同 Normal 框架；勾选走 toggleSelection（app.js:159-162 → filters.js:267-311） | 已一致 | 有：items[].name/place | 不动 |
| LS04 | 画板4 LongName·截断与开始前提醒 | 名称/地点 2 行截断（CSS 176/100/110）；LED `18:39:55`/`下一批开放`/`明天 09:00:00`；提醒 `要等到明天 09:00，自动登录没开。中途登录失效要你重⁠新登录；开放前 100 秒内失效，那场就结束。`+`去保存`；开始钮变 `仍然开始报名计划`，检查 chips 整行不渲染（Main:1536-1537/2317/2478/2465） | 活动名 line-clamp:2+title 全文（list.js:187）；地点 `aria-label="地点：…，按回车展开全部"`+Enter/Space 展开（list.js:188、plan-panel.js:223-228）；大屏 `.b-place` 两行+展开（plan-panel.js:207-219）；`仍然开始报名计划`（plan-panel.js:1229-1234）、有提醒则检查条不显示（:332） | 已一致 | 有：`advanced.credential.saved/ocr_ready/paused` | 不动 |
| LS05 | 画板5 Filters·外框 | 同 Normal 框架；搜索行右侧 `更多筛选` 折叠按钮（fN=0 无计数后缀） | 同 Normal 框架；筛选区常驻一行（index.html:35-43） | 已一致（框架本身）；折叠差异见下行 | 有：prefs.filter（savePrefs 落盘） | 见下行 |
| LS06 | 画板5 Filters·折叠抽屉与计数徽标 | `fbtn` 折叠按钮（aria-expanded=fOpen、非默认项计数徽标 fN）展开 `.more` 面板放 4 下拉：`开放 [不限｜今天]`、`排序`、`签到`、`签退`（Main:586-596/2419） | **无折叠抽屉**：搜索+3 chips+4 下拉+计数全部常驻（index.html:35-43）；`clearFilters`（controllers/refresh.js:38-49）、`setFilter`（views/selection.js:24-28） | 缺失（折叠交互与计数徽标） | 有：prefs.filter | 需用户定（NEEDS-HUMAN 4） |
| LS07 | 画板6 NoResult·外框 | 同 Normal 框架；搜索值 `篮球`、计数 `0 / 11 场`（Main:1161/2458） | 同 Normal 框架；计数 `N / M 场`（list.js:371-377 paintCount） | 已一致 | — | 不动 |
| LS08 | 画板6 NoResult·空态 | 标题 `没有符合筛选的活动`；正文 `一共 11 场。换个关键词，或清除筛选看完整列表。`；按钮 `清除筛选`（Main:2418） | 标题、按钮同字（list.js:310-313）；正文 `一共 N 场，换个关键词，或清除筛选看完整列表。`——句号变逗号 | 文案（一个标点） | — | 照原型改（1 字） |
| LS09 | 画板7 ZeroAct·外框 | 同 Normal 框架；分段全 0：`可报名 0` `已报名 0` `全部 0`、`0 / 0 场`（Main:1078/2457） | 同 Normal 框架；分段与计数随空列表归零（list.js:371-377） | 已一致 | 有：`activities` items=[]、check.result | 不动 |
| LS10 | 画板7 ZeroAct·空态 | `学校当前没有返回活动`/`这不是登录问题。稍后点“刷新”再看，学校发布新活动后会出现在这里。`/`刷新`（Main:2417） | 登录有效零场分支逐字同（list.js:365-368，注释引 Main:2096）；代码另扩展登录四态（checking/none/expired/unknown，list.js:339-364）与首屏未加载/条款锁占位（:315-337） | 已一致（该分支）；四态细分为多出（有意扩展） | 有：`check.result`（valid/none/expired/unknown）、terms | 不动；四态与条款锁占位列给用户补画板 |
| LS11 | 画板8 ListErr·外框 | 同 Normal 框架；日志末行替换为 `14:20:04  活动列表没加载：连不上学校站点`（Main:1064） | 同 Normal 框架；失败来源 `listState="error"`+`listError`（refresh.js:389-405）、Promise catch（:195-204）、130 秒超时 `活动列表超过 130 秒没有回应`（:167-173）；加载态扫光+6 行骨架（styles.css:303、list.js:30-35）；**三路失败均不写运行记录（不 addLog，日志停在上一条）——原型会替换日志末行** | 已一致（框架与失败机制）+ 缺失（列表失败不写运行记录） | 有：`listState`/`listError` | 照原型改（三路失败各写一条运行记录） |
| LS12 | 画板8 ListErr·空态文案与按钮 | 标题 `活动暂时没加载`；正文 `连不上学校站点，已保存的登录不受影响。检查网络后点“刷新”。`；按钮 `刷新`（Main:2416） | 标题同字；正文 `连不上学校站点。检查网络后再试一次，已保存的登录不受影响。`（controllers/tick.js:139，语序不同）；按钮 `重试`（list.js:304） | 文案（语序+按钮名） | 有：`listErrorCopy` 归因链（tick.js:127-140） | 照原型改（按钮 `刷新`、正文语序）；与 settings-gap.md「列表加载失败的按钮叫刷新」返修项同一条 |
| LS13 | 画板9 Attention·外框 | warn 横幅（tone '' → 橙）：`暂时无法确认登录状态。`+`检查网络后点“刷新”，先不用重新登录。`+按钮 `刷新`（Main:2141，role=status） | 横幅 warn、role=alert、标题逐字同，正文 `检查网络后点「刷新」，先不用重新登录。`（plan-panel.js:1377-1381）——引号 `“刷新”` vs `「刷新」`；按钮 `刷新` 同 | 已一致（结构）+ 文案（引号样式） | 有：`check.result === "unknown"` | 照原型改引号或按 DT04 口径统一，需用户定 |
| LS14 | 画板9 Attention·勾选与冲突行 | **原型禁勾 unknown**：Main:2221 `var off = busy || !s.terms || st === 'signed' || st === 'closed' || st === 'unknown' || !!hitSigned`——off 明确含 `st === 'unknown'`，待公布行复选框禁用（Main:606 disabled 绑定 off）；t3 行警告 `与已选的「人工智能与未来职业」时间重叠`（Main:2222）；pill `登录待确认`（2400） | **代码可勾 unknown、仅拦开始**：check.disabled 判据（plan-panel.js:1245）为 busy/termsLocked/isEligibleForPlan/signedClash，isEligibleForPlan（filters.js:102-104）不排除 unknown——待公布 pre_register 可勾，仅由 validateSelection 以 `报名开放时间待确认`（filters.js:161）拦开始。胶囊 `登录待确认`（login.js:58）；空态 `暂时无法确认登录状态`（list.js:359-364）；`还差一步：登录状态还没确认`（plan-panel.js:434-436）；检查条 `登录状态待确认`（:327）；冲突行提示由在途新增 `state/conflict.js`/`views/conflict-tip.js` 承接（未入库，未深对） | 结构（勾选门禁：原型禁勾+拦开始，代码可勾+仅拦开始）；胶囊与冲突行文案同 | 有：`check.result`、plan 快照 conflicts（`start_plan` 回包 conflicts/errors） | 勾选门禁差异列给用户定（照原型禁勾，或保留可勾+拦开始并说明）；冲突行合入在途后按 conflict 专项切片复核 |
| LS15 | 画板10 Broken·外框 | bad 横幅+空态+计划栏 `不可用` 三件套（Main:2137/2414/2326） | 横幅 bad、role=alert+按钮 `重新检查`（plan-panel.js:1340-1346）；空态（list.js:290-298，按钮隐藏避免与横幅重复）；计划栏 tag `不可用`（red）+`暂时不能报名`（plan-panel.js:49-55） | 已一致（三件套结构） | 有：`check.runtime_error` | 见下行 |
| LS16 | 画板10 Broken·横幅文案与错误码 | 横幅单句 `程序组件缺失。`+`重新下载完整版本，下载页在设置的“版本与更新”里。`+`重新检查`；空态 `活动列表没加载`/`程序组件缺失，修好之前看不了活动。处理办法在顶部提示里。`（Main:2137/2414） | 横幅按错误码三套 hint：`程序组件缺失`/`程序组件无法读取`/`程序组件启动失败`（refresh.js:295-299 RUNTIME_ERRORS）；空态标题 `活动列表未加载`+`组件有问题，处理办法看页面顶部的提示。`（list.js:294-295）；计划栏短状态逐字同 `程序组件缺失，处理办法在顶部提示里。`（plan-panel.js:53） | 文案（空态标题）+ 多出（三码拆分，有意扩展） | 有：runtime_error 三码 | 空态标题照原型改 `活动列表没加载`；三码拆分列给用户（原型只画了 missing） |
| LS17 | 画板11 Expired·外框 | bad 横幅+pill bad+`重新登录`（Main:2142/2400） | 横幅 bad、role=alert+按钮 `重新登录`（plan-panel.js:1373-1376）；胶囊 `登录已失效`（login.js:65） | 已一致（结构） | 有：`check.result === "expired"`、`S.busy` | 见下行 |
| LS18 | 画板11 Expired·横幅正文 | 草稿态正文 `重新登录后可以继续。`；运行态 `报名计划还在等，开放前 100 秒以前重新登录就照常继续。`（Main:2142 两态） | 草稿态 `重新登录后可以继续刷新和报名。`（多 4 字）；运行态逐字同（plan-panel.js:1375）；`还差一步：登录已失效`（plan-panel.js:433） | 文案（草稿态正文） | 有：`check.result`、`S.busy` | 照原型改（删「刷新和报名」）或保留并说明 |
| LS19 | 画板12 NetOff·外框 | bad 横幅两态：`网络断开了。`+运行态 `到点时还没恢复，这次报名会失败。恢复以后看一眼计划结果。`/草稿态 `恢复以后点“刷新”。`+`重新检测`（Main:2139） | 横幅逐字同两态+`重新检测`（plan-panel.js:1361-1364）；`重新检测` 只重读 navigator.onLine 并写日志（app.js:373-382） | 已一致 | 有：`S.online = navigator.onLine !== false`（state/store.js:68）+ online/offline 事件（app.js:536-537） | 不动 |
| LS20 | 画板12 NetOff·提醒与刷新拦截 | 开始前提醒 `现在连不上网。到开放时间还没恢复，就提交不出去。`（Main:1640） | 提醒逐字同（plan-panel.js:373，tone=bad）；断网不发学校请求（refresh.js:133-136） | 已一致 | 有：`S.online` | 不动 |
| LS21 | 画板13 Slept·外框（warn 横幅） | 橙横幅：`电脑刚才睡眠了约 23 分钟。`+`期间「人工智能与未来职业」「志愿服务培训」到了开放时间，没有提交。`+`知道了`——写分钟数、点名场次（Main:2140） | `刚才有 N 界面没动静，电脑可能睡眠了。要是睡过了开放时间，就赶不上了。看看计划和运行记录。`+`知道了`（plan-panel.js:1368-1369）——不写约数分钟、不点名场次 | 文案（措辞与信息量） | 有：`S.sleepGap`/`S.sleepWindow`（controllers/tick.js:9-14 心跳 >120 秒，store.js:18） | 照原型改：写 `约 N 分钟` 并点名场次（sleepWindow 内的计划场次前端可得名） |
| LS22 | 画板13 Slept·行级错过与结果页 | 结果页计数 `2 错过了`（红，Main:2387）、tag `错过了`、结论标题 `电脑睡眠，错过了开放`+副文 `运行计划时别让电脑睡眠：在 Windows 电源设置里把睡眠改成“从不”，并保持插电。`（Main:2394）；任务卡 `错过了`（Main:2295 动词表含 missed） | 行级 `错过了` 标记有：missedBySleep（filters.js:227-239）+ 状态格 `错过了`+小字（list.js:232-235）；**结果页与任务卡无 missed**：resultCounts 五类 `{ok,full,bad,pending,canceled}`（plan-panel.js:625-637）、taskLabel 无 missed 键（state/labels.js:48）、taskClass 无 missed 分支（:50-64） | 缺失（结果页计数/结论/任务卡） | 有：`S.sleepWindow`+`plan_done` tasks[]；missed 可由前端推导（missedBySleep 已这么做），补结果页**不需后端新字段** | 照原型改（NEEDS-HUMAN 5） |
| LS23 | 附行（素材乙对照） | 素材乙 §13 记录同一结论：`resultCounts` 无 missed、`taskLabel` 无 missed、横幅不点名场次——本表 LS21/LS22 与之一致 | 同左 | — | — | — |

## 三、计划栏组（画板 14–20：待开放/运行×4/警告/结果）

| 编号 | 画板·区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| PB01 | 画板14 Waiting·外框 | wide 双栏运行面板：tag `等开放`、标题=活动名、cap `这一批 2 场同时提交，到点自动开始。`、LED `00:09:53`/`开放时间`/`14:30:00`（琥珀，≤10 秒红）、路线五站、场次卡 `等待开放`+`取消这一场`、foot `修改计划`+`停止计划`+hint `可以最小化窗口，但不要关闭工具或让电脑睡眠。`（Main:2365-2368/2295/660-661） | tag `等开放`/`即将开放`（≤5 秒，plan-panel.js:150-156）；cap 两句（:165-178 runCaption）；LED 琥珀/≤10 秒红+`开放时间`（:941-956）；路线五站（:742-788）；hint 逐字同（:595）；`停止计划` 确认遮罩（plan.js:277-314） | 已一致 | 有：plan/task 事件 tasks[]（controllers/plan-events.js） | 不动 |
| PB02 | 画板14 Waiting·任务卡等待文案 | `等待开放`+`提前准备，等到 14:30:00 开放`（Main:2295/2298） | `提前准备，等到 HH:MM:SS 开放`/`开放时间待公布`/`已准备好，HH:MM:SS 开放时提交`（state/task-display.js:89-104）；模式前缀 `预报名 · `/`立即报名 · `（:69-73） | 已一致 | 有：task.sign_start/status | 不动 |
| PB03 | 画板14 Waiting·修改计划 | 修改后日志 `计划已暂停：N 场放回草稿修改`（Main:1771）；说明 `还没提交的场次可以放回草稿，改完要重新开始。` | 说明三句逐字同（plan-panel.js:599-605，含 `有场次正在提交，现在不能修改。`）；日志 `修改计划：先停下，改完要重新开始`（controllers/plan.js:340）；修改中 `#edit-note`+`放弃修改，按原计划继续`（plan-panel.js:293-298、index.html:87）——原型本有同一按钮（Main:650 `sc-if hasEdit` 同钮、文字逐字同；editNote 见 Main:630/2340-2348） | 文案（日志句） | 有：plan 快照 queued/waiting、planLate | 照原型改日志句；`放弃修改` 两侧本就有，无需另定去留 |
| PB04 | 画板15 MediumRun·外框（running/medium 900×700） | 900px；planOpen=true → 只显示计划栏全屏（showList=false、showDock=false，板加 solo：LED 最大宽 22rem）（Main:1115/2455、CSS 188） | `styles.css:762-767` data-plan-open=1 反转全屏；`#zd[data-plan-open="1"] .led-wrap` 最大宽 22rem（styles.css:767） | 已一致 | — | 不动 |
| PB05 | 画板15 MediumRun·提交中面板 | tag `正在提交`（红）；cap `已提交 1 次，最近：学校暂时没有回应`；LED `00:01:58`/`本次尝试到`/`14:22:05`（红）；路线 `准备好提交 14:21:06（done）`；foot `修改计划` 禁用+`有场次正在提交，现在不能修改。`（Main:2361-2363/2375/1764） | tag `正在提交`（红，plan-panel.js:151-156）；cap `已提交 N 次，最近：X`（:165-173；原型任务卡的 `（上限 M 次）` 精简掉，上限只在任务卡——有意精简）；LED 红 `本次尝试到`（:920-934）；`修改计划` 禁用说明逐字同（:599-605） | 已一致 | 有：task.attempts/last_reason/retry_deadline | 不动 |
| PB06 | 画板16 RunClick·外框 | 同 Waiting 双栏；差异=o1 徽章 `提交中`、路线第二站 click 场 `活动页已打开 14:21:06（done）`（Main:2375）、via 行 warn 色（Main:2301） | 同 Waiting；`taskViaHtml`（plan-panel.js:1068-1077）；路线 click 站名 `活动页已打开`（:770-774） | 已一致 | 有：task.path/path_reason/page_opened_at | 不动 |
| PB07 | 画板16 RunClick·via 行 | `直接提交，不经过活动页`（直发）；`改用页面点击：没取到学校的报名密钥。活动页已提前打开`（click，warn 色）（Main:2301） | 逐字同（plan-panel.js:1068-1077）；`taskPrepared` 以 page_opened_at 为准（task-display.js:78-86） | 已一致 | 有：task.path/path_reason | 不动 |
| PB08 | 画板17 RunAuto·外框 | 同 Waiting；pill `自动登录中…`（busy，Main:2400）；run-warn info 两态：等待中 `登录失效了，电脑正在自动登录。计划照常等开放，不用你管。`/提交中 `登录失效了，电脑正在自动登录（最多约 20 秒），成功后接着提交。`（Main:2152-2168） | 胶囊 `自动登录中…`（login.js:35，is-busy）；run-warn 两句逐字同（plan-panel.js:558-565）；100 秒界线 `LATE_WINDOW_S = 100` 与后端 login_rules.py 同数（:509） | 已一致 | 有：task.login_wait、`advanced.credential.saved/ocr_ready/paused`（plan-panel.js:349-356） | 不动 |
| PB09 | 画板17 RunAuto·任务卡与日志 | 原型无任务卡自动登录说明；日志 `学校返回登录失效，复查一次仍失效；正在用保存的账号自动登录`（Main:1082） | 任务卡多一句 `电脑正在自动登录，换上新登录态后接着提交`（task-display.js:91-94，代码独有）；`复查一次仍失效` 日志句在 UI 代码无对应（归后端日志域） | 多出（任务卡说明，有意扩展）；`复查`句列无法验证 | 有：task.login_wait | 不动；后端日志句在 grab 侧核对（超本切片） |
| PB10 | 画板18 RunPhone·外框 | 同 Waiting；hint `这个计划是从手机开始的，在电脑和手机上都能看进度、停止。`（Main:662/2438）；手机 pill `手机已连接`（2453） | hint 逐字同（plan-panel.js:593-596）；来源 `S.plan.source`（state/plan.js:67-68） | 已一致 | 有：plan 事件 `data.source`（desktop/phone） | 不动 |
| PB11 | 画板18 RunPhone·开始日志 | 日志 `14:20:05  从手机开始了报名计划：2 场预报名等开放`（Main:1089） | 开始日志 `已安排 N 场活动：…`（controllers/plan.js:106），无「从手机开始」句 | 缺失（日志句） | 有：`S.plan.source` | 照原型改（纯前端：source=phone 时 addLog 换句） |
| PB12 | 画板19 NarrowWarn·外框（prewarn/narrow 430×820，7 行压缩薄壳） | init `s.selected=['t2','w1']; s.retry=0; s.net='off'`，**未置 planOpen=true**（Main:1068）→ 冻结态只见列表+dock，dock 副文 `有 4 条提醒，开始前先看一眼`、按钮只有 `查看计划`（Main:2422），4 条提醒正文不可见（画板标题却叫「窄窗口：开始前提醒」）；对照 PreWarn（prewarn/wide）恒双栏可见面板 | 窄档同构：dock 副行 `有 N 条提醒，开始前先看一眼`、不给 `开始`（plan-panel.js:1326-1330）；提醒列表 `#plan-prewarn`（index.html:83）在计划栏内，窄档未开计划栏时同样不可见——与原型窄档行为一致 | 状态（提醒可见性，原型自身待定） | 有：`S.preWarnCount`、`S.online`、`advanced.credential.*` | 需用户定（NEEDS-HUMAN 2） |
| PB13 | 画板19 NarrowWarn·提醒文案 | 4 条：断网（Main:1640）、无自动登录+`去保存`（1536-1537，`重⁠新登录` 含 U+2060）、无截止时间（1646）、超 24h（1650）；另有沿用上次校准条（Main:1641 `北京时间在用上次的校准结果，误差约 ±0.3 秒…`） | 五条提醒（比原型多的只有 cred.paused 变体与误差动态化）：断网逐字同（plan-panel.js:373）；无自动登录句同源、误差动态取 `clockUncertaintyText`（原型写死 `约 ±0.3 秒`）、多 `保存的密码学校不认` 分支（:374-389）；无截止时间（:398-404）、超 24h（:405-407）逐字同；沿用上次校准条两侧本就有（Main:1641） | 已一致（文案同源）；多出（cred.paused 变体与误差动态化，有意扩展） | 有：`advanced.credential.saved/ocr_ready/paused`、items[].noEnd | 不动；多出两点改列为 cred.paused 变体与误差动态化，列给用户 |
| PB14 | 画板20 NarrowResult·外框（result/narrow 430×820） | 430px 全屏计划栏（solo）、无列表无 dock；tag `部分完成`（琥珀）、板描边 st-warn、无 LED 框（Main:1149-1152/2392） | resultMode 判定（plan-panel.js:302-305）、resultView 六分支（:640-669）；整屏边框着色（styles.css:101-107，注释 FR06：含待核对不画成确定失败红框） | 已一致 | 有：`plan_done` 事件、`resultPageOpen()`（state/plan.js:106-128） | 不动 |
| PB15 | 画板20 NarrowResult·计数与副文 | 计数块 `1 已报名`/`1 名额已满`/`1 待核对`（Main:2387 六类含 `错过了`）；标题 `报名计划部分完成`+副文 `有 1 场需要到活动页核对，结果以学校为准。`（2392）；任务卡动词表 `报名成功/名额已满/报名未成功/错过了/待核对/已取消`（2295） | 大数字五类（plan-panel.js:685-697：`已报名/名额已满/报名未成功/待核对/已取消`，**无 `错过了`**，同 LS22）；副文 ask 分支逐字同（:652-669）；任务卡 `待核对` detail 逐字同+`刷新核对`（:1124-1151） | 已一致（副文/任务卡）+ 缺失（missed 计数与动词） | 有：tasks[].status/stop_reason（success/already_signed/full/unconfirmed/canceled/failed） | missed 见 LS22（NEEDS-HUMAN 5） |
| PB16 | 画板20 NarrowResult·dock 结果态 | 窄档结果页 dock 显示结论标题/正文（Main:2425） | `paintDock` 无结果分支（plan-panel.js:1310-1333）——窄档结果页藏在计划栏里、dock 仍显示草稿文案 | 缺失 | 有：`plan_done`、resultMode | 照原型改（纯前端，与 TF05 同一处补） |
| PB17 | 勘误附行：Running/PreWarn 薄壳 | 磁盘实有 `Running.dc.html`（running/wide 1280×800）与 `PreWarn.dc.html`（prewarn/wide 1280×800），与画板 15/19 同 scene；wide 档恒双栏，running/wide=Waiting 同款面板、prewarn/wide 提醒列表直接可见 | 两张画板的画面细节未逐行核对（仅核 dc-import 与存在性） | —（清单勘误，不判差距） | — | 列入无法验证清单；建议原型维护者确认这两张与 MediumRun/NarrowWarn 的去留 |

## 四、全局件（画板 21–24 + 跨画板）

| 编号 | 画板·区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| GL01 | 画板21 SecondRun·外框 | note 横幅（白底描边）：`工具已经开着。`+`刚才又打开了一次，已切回这个窗口。同一台电脑只运行一份，免得同一场被提交两遍。`+`知道了`；日志 `14:20:06  又打开了一次，已切回这个窗口`；面板同 Waiting（Main:2145/1181） | **无对应实现**：功能字符串在 local/ui 全无命中（grep 复核；唯一宽匹配是 views/phone.js:901 设置表单注释 `表单已经开着…`，与本功能无关）；`window.onBackend`（app.js:75-146）无 second/info 类事件；local/app.py 未见单实例 UI 事件（仅 phone_relogin 的 singleflight） | 缺失（整体） | **需补**：后端单实例合并机制 + `window.onBackend` 新事件（如 `second_open`）；前端横幅可挂 paintBanners（plan-panel.js:1338-1388） | 需后端先补（NEEDS-HUMAN 3） |
| GL02 | 画板22 ToastMin·外框 | 模拟桌面盖全屏：桌面卡 `窗口已最小化`+`点任务栏上的按钮就能回来。`+`回到窗口`；toast 头部 `校园活动预报名工具`、标题三态 `报名计划完成/报名计划部分完成/报名计划结束`、正文 `1 场成功，1 场待核对，1 场名额已满。点这里看每场结果。`、按钮 `查看结果`（Main:1730-1741/869-875）；背后主窗仍渲染 result 面板+wbar | **UI 无窗口内 toast**（grep toast 全目录 0 命中）；后端托盘通知兜底：窗口最小化/藏后台且计划结束时 `_tray.notify`（local/app.py:2885-2896，抽查吻合）；标题与正文由 `plan_done_notice` 给：`N 场成功，N 场待核对，N 场名额已满，N 场没成功`，为 0 不写（local/application/plan_service.py:28-49，missed 归入「没成功」——与原型 toast 正文四类计数语义等价；但原型结果页另有独立 `错过了` 格，见 LS22）；**托盘标题为二态（plan_service.py:51 `报名计划部分完成`/`报名计划已结束`），原型 toastTitle 三态（Main:1735 `报名计划完成`/`报名计划部分完成`/`报名计划结束`）——全成功时 完成 vs 已结束、无成功场次时 结束 vs 已结束** | 缺失（窗口内 toast）+ 文案（托盘标题：原型三态 vs 后端二态）+ 已一致（托盘正文四类计数语义） | 有：`plan_done` 事件 tasks[]；`_notify_plan_done` 触发点 app.py:2647（:741 是标志初始化、:4029 是 minimized 事件接线） | 窗口内 toast 是否要做需用户定（NEEDS-HUMAN 7）；托盘标题对齐原型三态属后端 plan_service.py 改动，列给用户定；托盘通知机制不动 |
| GL03 | 画板22 ToastMin·薄壳 frozen | 薄壳 `ToastMin.dc.html:11` **缺 `frozen="{{yes}}"`**（其余 23 张都有）→ 挂键盘监听与 1 秒定时器（Main:1780/1788 仅 !frozen 时安装），任务栏时钟每秒走字（Main:1732） | 不涉代码（原型演示属性）；本报告已亲自复核该行确无 frozen | 状态（原型内部） | — | 需用户定（NEEDS-HUMAN 1） |
| GL04 | 画板23 LogOpen·外框 | 收起 `运行记录`+最近一行+`展开`；展开 3 行+`收起`；默认两行 `14:20:03  [OK] 已复用本机登录，学校校验通过`、`14:20:04  活动列表已更新，共 11 场`（Main:690/2483/1058） | `index.html:101-104` 同构：`运行记录`+`#log-last`（默认 `还没有记录`）+`展开`/`收起`（views/log.js:2-9，aria-expanded+savePrefs 记忆）；展开追加 复制/清空/打开数据目录 三钮（代码独有）；日志体 196px（styles.css:379，注释引原型 38/196 密度）；最近 40 条（store.js:139） | 已一致；三工具钮为多出（有意扩展） | 有：`onBackend.log`、prefs.log_open | 不动 |
| GL05 | 画板24 Policy·外框 | 计划栏政策行+编辑器展开：`尝试时长` 六选项、`最多提交次数（0 = 不限）`、`改用页面点击时显示浏览器` 复选（Main:636-642） | `index.html:68-74` 同构；开合 `修改`/`收起`（app.js:306-312，注释引原型 policyBtn）；落盘 `savePrefs({retry_policy})`（app.js:394-417） | 已一致（结构） | 有：`S.retryOptions.choices`（bootstrap 覆盖，store.js:118-130 同源副本） | 见下行 |
| GL06 | 画板24 Policy·选项标签 | `自动延长（最多 25 分钟）`（带空格，Main:639）；概括行 `-1→自动延长` 映射（Main:2464） | `自动延长（最多25分钟）`（无空格，index.html:71、store.js:127）；`最多提交次数（0=不限）`（无空格）；概括行直接用选项 label（plan-panel.js:501-503） | 文案（两处空格+映射方式） | 有：prefs.retry_policy（-1=自动延长、0=直到报名截止语义注释 index.html:70） | 照原型改（补空格）或统一空格规范，需用户顺手定 |
| GL07 | 跨画板·横幅体系 | tone：bad 红/warn 橙/note 白底描边（CSS 52-53）；顺序 netoff→slept→unknown→expired→clock→second→migrated（Main:2138-2146） | `data-tone=bad|warn`（styles.css:92-93）；顺序 runtime→netoff→slept→expired→unknown（plan-panel.js:1340-1381）——unknown/expired 与原型互换，但两态同源 `S.login.result` 互斥，无实际影响；note 档无使用（SecondRun/Migrated 均未实现，见 GL01） | 已一致（bad/warn）+ 状态（顺序互换，无实际影响） | 有：`S.online`/`S.sleepGap`/`S.login.result`/`S.runtime.error` | 不动 |

---

## 差异统计（按类型计次，一行可含多型；勘误附行 LS23/PB17 不计）

| 类型 | 行 |
|---|---|
| 已一致 | 32 |
| 文案 | 11 |
| 缺失 | 9 |
| 多出 | 7 |
| 状态 | 3 |
| 结构 | 3 |
| 样式 | 0 |

共 52 行（TF 7 + LS 22 + PB 16 + GL 7）。样式 0：本批未发现样式类差距；LED 点阵渲染、断行、层叠等视觉项归「无法验证」。缺失集中在：SecondRun 整体（GL01）、Slept 结果页（LS22/PB15）、dock 修改中与结果态（TF05/PB16）、Filters 折叠抽屉（LS06）、RunPhone 日志句（PB11）、窗口内 toast（GL02）、列表失败不写运行记录（LS11）。
统计为对抗审阅修订后的值（LS01/LS14 改列结构、LS11 增缺失、PB03 减多出、GL02 增文案）；修订前值见文末「修订记录」。

## 抽查复核记录

素材 file:line 逐处复核（命令 `sed -n` / `grep -n`），**全部吻合的节选 30 处**：`index.html:36` `搜活动名或地点`、`:45` 表头五列、`:52/:56/:59` 计划栏头、`:68` 政策行、`:71` `自动延长（最多25分钟）`、`:99` dock、`:101-104` 运行记录条；`views/plan-panel.js:49-62` 不可用/需重试、`:564-580` 登录失效运行提醒、`:625-637` resultCounts、`:1310-1333` paintDock（确认无 editing/result 分支）、`:1367-1381` slept/expired/unknown 横幅；`views/list.js:294` `活动列表未加载`、`:304` `重试`、`:310-313` NoResult 逗号版；`controllers/tick.js:139` 失败文案；`controllers/refresh.js:295-299` RUNTIME_ERRORS；`state/labels.js:48` taskLabel 无 missed；`controllers/plan.js:106` `已安排 N 场活动：…`、`:340` 修改日志；`styles.css:762/769/772/980` 断点；`views/login.js:35` `自动登录中…`（素材只引了注释，实际分支在本行，已补证）；`local/app.py:2885-2896` 托盘通知、`local/application/plan_service.py:28-49` 四类正文；`Main.dc.html:2139-2146` 横幅族、`:2414/:2416/:2417/:2418` 空态族、`:2387` 含 `错过了` 计数、`:639` `自动延长（最多 25 分钟）`、`:586-596` 筛选折叠、`:917` scene 枚举、`:1068` prewarn init、`:1089` runphone 日志、`:1771` 修改日志、`:2455` 双栏切换、`:2422-2425` dock 四态。

**修正 4 处（对抗审阅再勘误：原第 1-3 条把本来正确的引用改反了，现按磁盘实测改正；仅第 4 条属实）**：
1. dock 标题/副文在 `Main.dc.html:2422`（素材甲原引 2422 本来正确；前期修订改成的 2421 有误——2420 是空行，pwN 行在 2421）。
2. 修改中 dock 在 `Main.dc.html:2423`（素材乙原引 2420 有误，前期修订改成的 2422 同样有误）。
3. 结果 dock 在 `Main.dc.html:2425`（素材乙原引 2425 本来正确；前期修订改成的 2424 是 running dock）。
4. 素材乙称 secondrun 功能字符串「grep 全无命中」→ 复核维持：功能字符串确无命中；唯一宽匹配 `views/phone.js:901` 是设置表单注释 `表单已经开着就不清用户输到一半的内容`，与本功能无关。

另：画板薄壳声明逐张复核——24 张 `dc-import` 全部 scene/tier/hint-size 与本表清单一致；`ToastMin.dc.html:11` 确缺 `frozen="{{yes}}"`；`NarrowWarn.dc.html:4` 为 7 行压缩薄壳。

## 需用户定（NEEDS-HUMAN）

1. **ToastMin 薄壳缺 `frozen="{{yes}}"` 是否有意**。原型侧：`ToastMin.dc.html:11` 无该属性（其余 23 张都有），后果是任务栏时钟每秒走字（Main:1780/1788 仅 !frozen 安装）。代码侧：不涉产品代码，仅影响画板渲染本身。
2. **NarrowWarn（prewarn/narrow）冻结态看不到 4 条提醒正文**。原型侧：Main:1068 init 未置 `planOpen=true`，Main:2455 `showPanel: two || s.planOpen`（narrow 下 false）→ 只见 dock 副文计数 `有 4 条提醒，开始前先看一眼`（Main:2422），与画板标题「窄窗口：开始前提醒」的意图可能不符；同 scene 的 PreWarn（wide）恒双栏可见。代码侧：提醒在计划栏内、窄档不开计划栏同样不可见（plan-panel.js:1326-1330 行为与原型一致）。要改原型 init 还是接受现状，需原型维护者定。
3. **SecondRun 整体无实现**。原型侧：横幅 `工具已经开着。刚才又打开了一次，已切回这个窗口。同一台电脑只运行一份，免得同一场被提交两遍。`+`知道了`（Main:2145）、日志 `又打开了一次，已切回这个窗口`（Main:1181）。代码侧：UI 与 app.py 均无单实例合并/事件（grep 复核）。是否进本批、后端何时补事件，需用户定。
4. **Filters 无折叠抽屉**。原型侧：`fbtn` 折叠按钮+非默认项计数徽标+`.more` 面板（Main:586-596）。代码侧：4 下拉常驻一行（index.html:38-41）。1:1 口径应折叠；常驻可用性更好，取舍需用户定。
5. **Slept 缺「错过了」统计**。原型侧：计数 `错过了`（Main:2387）、结论 `电脑睡眠，错过了开放`+`运行计划时别让电脑睡眠：…`（Main:2394）、任务动词 `missed→错过了`（Main:2295）、横幅点名场次（Main:2140）。代码侧：resultCounts/taskLabel 无 missed（plan-panel.js:625-637、labels.js:48），横幅 `刚才有 N 界面没动静…`（plan-panel.js:1368-1369），仅行级 `错过了`（filters.js:227-239）。前端可由 sleepWindow 推导、不需后端字段；要不要按原型补齐，需用户定。
6. **品牌副句 `活动查询与报名计划`（index.html:17）原型没有**。删或留需用户定。
7. **窗口内 toast 要不要做**。原型侧：后台结束弹 toast（Main:1730-1741，标题三态+四类计数正文）。代码侧：只有托盘系统通知（app.py:2885-2896），窗口内无 toast 元素。做窗口内 toast 属新功能，需用户定；托盘正文已覆盖同一信息。

## 无法验证清单

- LED 点阵渲染、ToastMin 桌面层叠、断行（WebView2/Edge 实际折行）、浮卡与 toast 动画——纯源码推演，未在浏览器打开原型。
- 未运行 `python local/app.py --demo`、未起 pywebview 桥、未连学校站点；所有「运行后实际长什么样」为静态推断。
- `window.pywebview.api` 回包真实结构按 UI 消费侧记录（app.js:14-57、plan-events.js 等），未连真机核对 app.py 侧（本次仅抽查 `_notify_plan_done` 与 singleflight）。
- RunAuto 的 `复查一次仍失效` 日志句、睡眠唤醒、断网恢复、托盘通知实际弹出、单实例合并——运行时行为或后端日志域。
- 勘误附行 PB17：`Running.dc.html`、`PreWarn.dc.html` 两张薄壳的画面细节未逐行核对（仅核 dc-import 与存在性）。
- 在途未跟踪 `views/conflict-tip.js`、`controllers/cancel.js`、`state/conflict.js` 与原型 `tipb`/取消确认流的对账——归 conflict/取消专项切片，本表未深对。
- 素材甲标注【静态推断】的产品侧进入路径（scene 名与架构方案注释推断，原型不含路由），本表沿用其标注，未另行验证。

## 修订记录（对抗审阅 2026-11-08）

对抗审阅两路（机械核验 + 实质反证，互盲；判定与处置全文见同目录 `ADVERSARIAL-L4.md`）之后修订本表。所有行号修正落笔前均以 `sed -n` 实测磁盘原文。三档结论：52 行中站得住 44、部分站不住 6（LS11/PB03/PB13/TF05/PB16/GL02）、推翻 2（LS14/LS01）。

1. **推翻重写 2 行**：LS14——原型 Main:2221 `off` 明确含 `st === 'unknown'`（原型禁勾 unknown，Main:606 绑定），代码 check.disabled（plan-panel.js:1245，isEligibleForPlan 不排除 unknown）可勾、仅由 validateSelection（filters.js:161）拦开始，原判「已一致」方向反转，改列结构差异；LS01——原型分组序 Main:2202 为 待公布→已报名→已截止，原句把原型序引反，代码 list.js:110-113 顺序相反，原判「已一致」掩盖真实结构差异，两侧原文已并列。
2. **部分改判 6 行**：LS11 补「代码三路失败均不写运行记录」差异；PB03 撤销「放弃修改钮代码独有」（Main:650 原型本有）；PB13 撤销「比原型多沿用上次校准条」（Main:1641 本有），多出仅剩 cred.paused 变体与误差动态化；GL02 补托盘标题原型三态 vs 后端二态（plan_service.py:51）、触发点改 app.py:2647；TF05/PB16 结论维持、行号见下。
3. **勘误的勘误**：前期修订「修正 4 处」中 3 处把本来正确的引用改反，已再勘误——正确值 Main:2422=dock 标题/副文、2423=修改中 dock、2425=结果 dock（2421 是 pwN 行、2424 是 running dock、2420 是空行）；素材甲原引 2422、素材乙原引 2425 本来就对；「修正 4 处」仅第 4 条（secondrun 零命中）属实；连带改正 TF05/PB16 正文行号、抽查复核记录「`:2419-2424` dock 四态」→「`:2422-2425`」、NEEDS-HUMAN 2 的 Main:2421→2422。
4. **其余行号修正**：TF04 btnLabels Main:2427→2428；LS16 plan-panel.js:54→53；TF05 副文 :1319/:1323→:1321/:1324；TF06 网格四列引文仅 Main:2459，Main:2181 窄档为三列 `1.25rem minmax(0,1fr) auto`；GL02 触发点 app.py:741/:4029→2647。
5. **差异统计重算**：修订前 已一致 34｜文案 10｜缺失 8｜多出 8｜状态 3｜结构 1｜样式 0；修订后 已一致 32｜文案 11｜缺失 9｜多出 7｜状态 3｜结构 3｜样式 0（LS01/LS14 已一致→结构、LS11 增缺失、PB03 减多出、GL02 增文案）。总行数 52 不变。
