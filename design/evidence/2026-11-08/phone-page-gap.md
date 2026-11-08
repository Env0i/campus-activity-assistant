# 手机页（local/ui/m/）：原型与现行代码的逐项差距（2026-11-08）

只读审计，没有改任何代码和原型。用途：后面的计划照这张表给执行者下具体指令。合并自 L3 两份素材（原型侧 28 板逐字抄录、代码侧 file:line 现状）。

## 范围与读法

- **基准**：`design/prototype/workbench-2026-11/Phone.dc.html`（工作区版 950 行）＋ `Main.dc.html`（工作区版 2498 行）。两文件本身在途修改（git status 为 M）：a85209e 的 Main 为 2283 行、Phone 为 842 行，工作区在途版 2498/950 行。**本表行号一律以工作区版为准**，标 `Phone:NNN` / `Main:NNN`。
- **分母 28 画板**：Phone 侧 24 板 = 组件本体 `Phone.dc.html`（scene=pair，非薄壳）＋ 23 个 `name="Phone"` 薄壳（scene 依次 pair/auto/cancelsheet/captcha/pending/expired/pairlock/offline/pairfail/pcclock/pclisterr/picked/relacct/relall/relbad/relconfirm/result/review/reviewwarn/running/search/stopsheet/phoneterms，全部 `height="844px"`）＋ Main 侧 4 板（`name="Main"` 薄壳 phonesetup/phonets/phonewait/phonelinked，`tier="wide"`，外层 1280x800）。素材称 27 个薄壳逐一核对 dc-import，name/scene/tier 无偏差（23 个 Phone 名薄壳 + 4 个 Main 名薄壳 = 27，本表按文件清单复核过这一账）。
- **排除**：`PhoneConflict.dc.html`（name="Phone" scene="conflict"，手机端时间重叠点按看原因）**未入库、在途新增**，不在本批 28 板分母里，不展开；其代码侧对应 m/app.js 在途冲突块，见下一条与 G06。另 `PhAddPair.dc.html`（name="Main" scene="phaddpair"，frozen）同为手机相关画板，不在本表分母（任务书口径只对账 Phone 侧 24 板＋Main 手机侧 4 板），点名备查。
- **现状**：`local/ui/m/`（`index.html` 156 行、`app.js` 1309 行、`styles.css` 199 行）＋ `local/infrastructure/phone_http.py`（389 行）。
- **在途改动影响**：当前工作区共 43 项在途（git status --porcelain 计数）。`app.js` +318/−4、`styles.css` +34，增量就是 20261107-conflict-cancel 整块（PhoneModel 冲突段约 186-384、buildRow 冲突/可退/可取消至渲染 510-558、buildWhy 564-640、goSigned 643-659；styles.css 162-199）；`index.html`、`phone_http.py` 干净。**对账以磁盘现状为准**；下表冲突相关行号属在途段，若在途改动被回退或重排会失效。m/ 只加载一个脚本（`index.html:154`），不 import 电脑端 conflict.js，冲突规则在 PhoneModel 内联复制（`app.js:187` 注释自述与电脑端同一套）。
- **行号抽查**：关键 file:line 已用 Grep 抽查复核 22 处，其中 1 处按实际修正：素材写 whyView 标题在 `app.js:330`，实际 `app.js:329`，本表已改。其余全部吻合（含 index.html:17/43/46/48/154、app.js:5/155-158/186-188/475/691/880/896/967/987/1027、Phone:234/253/486/868/872-879/910/921/923/928-931、Main:2453、a85209e 行数 2283/842）。
- **后端信号**：「有」写 m/ 实际拿到的字段——m/ 全部数据经 `GET /api/state?after=<seq>`（app.js:783 → phone_http.py:356-371），写动作统一 `POST /api/action`（phone_http.py:374-388），配对 `POST /pair`（334-353）。「需补」写最小新增字段。
- **差距类型**：文案 / 结构 / 缺失 / 多出 / 状态 / 样式 / 已一致。字符串一律反引号逐字抄录；原型文案含 U+2060（不可见字间连接符）的几处（`可取消至 …学校网站取消。`、Phone:473-474 两句）按可见字转录。
- 原型里标着「演示：」的控件不进产品（`design/evidence/2026-11-04/decision-agenda.md` D6），本表不为它们建行。「已一致」的行不要再动。

## 〇、共用外框与共用组件（多板复用，逐板只列差异）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| G01 | 顶栏与品牌 | SVG 徽标（aria `校园预报名`）＋`校园预报名`（Phone:236）；pill 仅 app 视图：`已连接`(ok)/`离线`(bad)/`同步中`(busy)（Phone:923）＋刷新钮 aria `刷新`＋更多钮 aria `更多`（Phone:239-240） | `index.html:33-39`：svg 徽标＋h1 `这次报名`＋`#conn` pill（初始 `已连接`，离线时 `离线/未知`，app.js:380-383）＋`#btn-refresh` `刷新`＋下一行 `#last-sync` `还没有同步过`（同步后 `最近同步 HH:MM`，app.js:896） | 文案＋结构 | 有：`GET /api/state` 成败由前端推 offline | 照原型改：标题换 `校园预报名`、pill 文案对齐、补 `更多` 钮（内容见 SH05） |
| G02 | 底部按钮条 | `.bar` 深色点阵底、左标题两行＋右侧主按钮（Phone:155-158,294）；结果态 `.bar.stack` 纵排两钮（Phone:159,295）；含 `env(safe-area-inset-bottom)`（Phone:155）；pair 视图无底栏 | `index.html:49-56`：`.row.actions` 纵排 `#btn-start`＋`#btn-stop` hidden，其下 `#plan-line`、`#pending-note`、`#btn-cancel-start`、`#btn-cancel-task`；styles.css:82 纵向 | 结构 | 有：`state.busy`、`state.plan` | 照原型改（左题右钮布局；safe-area 由 CSS 补） |
| G03 | sheet 外壳 | `.scrim` 遮罩 `rgba(17,29,38,.46)` 底部对齐＋`.sheet` 宽 100%、`max-height:88%`、圆角 `16px 16px 0 0`、rise .18s（Phone:167-168,230）；头部 amber 竖条；关闭钮 aria `关闭`、验证中隐藏（Phone:300,887）；Esc/点遮罩可关、验证中除外（Phone:925-926） | 无自定义 sheet/modal。三类替代：原生 `window.confirm`（app.js:948、967、987）；`<details>` 折叠（`#signed-summary` index.html:65-68、`#more-panel` 72-151）；`hidden` 属性显隐 | 缺失 | — | 需用户定（NEEDS-HUMAN 1：三处 confirm 与 review/更多 是否上 sheet 外壳） |
| G04 | LED 计划板 | 深色点阵板＋LED 大字＋cap/capB（如 Phone:788 `00:09:55`／`下一批开放`／`14:30:00`） | 无对应结构；计划信息落在 `#plan-line` 一行文本（app.js:681-692） | 缺失 | 有：`state.plan` | 照原型改（数值由 `state.plan`＋businessNowS 前端聚合） |
| G05 | 列表行 | 勾选框 aria `选择 {活动名}`；旗标 `立即报名`/`下一场`/`预报名`/`已报名`/`已截止`（Phone:744-747）；距开放 `N 分 N 秒`/`N 小时后`/`已开放`/`待校准`，<10 分钟 soon 橙色（Phone:369-376,760-762）；退报 `报后可退`/`报后不可退`（Phone:752）；奖励 `N 分 · 工资 N`/`分未公布 · 工资未公布`/`奖励同步中`（Phone:486-487）；行警 `与已选的「{名}」时间重叠`（Phone:761）；已报名行注 `可取消至 {11月X日 HH:MM}，在电脑上或学校网站取消。`（Phone:753，含 U+2060） | `buildRow`（app.js:482-561）：checkbox＋`.name`＋`.meta`，meta 为 `开放 <sign_start>`/`截止 <sign_end>`/`已报名` 用 ` · ` 连接（app.js:170-176）；在途段已补 `不可加入` 旗（513-521）、举办时段 actSpan（226-236）、`报后可退`/`报后不可退`（280-285）、`可取消至 …学校网站取消。`（287-291）；仍缺 时刻大字/距开放倒计时/旗标/奖励/行警 | 结构＋文案 | 有：`state.activities`（sign_start/sign_end 等）；`待校准` 需 `state.business_clock` | 照原型改：meta 重排为时刻大字＋旗标＋奖励；`可取消至`/`报后可退` 已在途，随在途块一并提交 |
| G06 | 冲突原因块 why | 标题 `和已报名的活动时间重叠`（原型 aria 带『的原因』尾缀：`和已报名的活动时间重叠的原因`，Phone:288；代码侧 aria=标题逐字，app.js:569）；两行 dt `已报名`/`这一场`（Phone:477）；时间线图例 `已报名` `这一场` `重叠`（Phone:142）；解除路径四态（Phone:472-475），路径 a 带钮 `去已报名那场`（Phone:481） | 在途已实现（未提交）：buildWhy（app.js:564-640），标题在 `app.js:329`；时间线图（role=img）＋图例（619）、clashWay 四分支（293-307）、`去已报名那场`（634）→ goSigned（643-659）；样式 styles.css:178-197；较原型多 `days.length > 7` 稀疏化（app.js:326-332，只留首末日），原型 whyOf（Phone:470）全量渲染日标签 | 已一致（在途） | 有：判定在前端（signedClash/businessNowS），不新增后端字段 | 不动（随在途块提交）；手机侧无取消按钮，符合 `app.js:186-188` 注释口径 |
| G07 | 分组条 | 组名 `正在开放/今天/明天/后天/待公布/已报名/已截止`（Phone:413-423,728）；组注 `现在就能报`/`只能查看`；计数 `N 场`；「现在」分隔行 `现在 {HH:MM}`（Phone:93-97） | `bucketOf` 只分三区（app.js:57-66）：signed→折叠区、开放≤now+86400s→今天、否则 upcoming；卡头 h2 `今天要参加`/`即将开放`（index.html:46、60） | 结构 | 有：`state.activities` 的开放时刻 | 照原型改（分组前端聚合即可） |
| G08 | 筛选条 | 段钮 `可报名` `已报名` `全部`＋计数（Phone:931）；搜索钮 aria `搜活动名或地点`（Phone:282）；输入 placeholder `搜活动名或地点`（Phone:283） | chips `全部`/`可报名`/`已报名`（index.html:79-83，次序与原型不同）＋时间 chips `不限`/`今天`/`7 天内`（84-88）＋搜索 input `#q` placeholder `搜活动名或地点` aria-label `名称或关键词`（77-78），**藏在 `#more-panel` 折叠内的 `#filter-panel`** | 结构＋文案 | 有：前端过滤（app.js:18-39） | 照原型改：段钮次序与计数对齐；搜索入口上浮（独立搜索页与否见 NEEDS-HUMAN 4） |
| G09 | 空态 | `没有符合筛选的活动。`（Phone:290） | `#empty` `今天没有可报名的活动，往下看即将开放的。`（index.html:48）＋`#upcoming-empty` `暂时没有更晚开放的活动。`（62）；筛选无结果复用同一空态 | 文案 | 有：前端 | 照原型改（补「无匹配」分支） |
| G10 | 运行提示与任务卡 | `手机能锁屏，电脑不能关机或睡眠。要改，回电脑点“修改计划”，或者停止后重新选。`（Phone:276）；卡状态 `等待开放/准备报名/提交中/报名成功/名额已满/报名未成功/待核对/已取消`（Phone:843）；等待明细 `等到 {HH:MM:SS} 开放`/`已准备好，{HH:MM:SS} 开放时提交`/`已开放，正在准备提交`（Phone:845）；提交明细 `已提交 N 次（上限 N 次/不限次数），重试到 {HH:MM:SS}`（Phone:847）；页点击 `。改用页面点击：{原因}`（Phone:846）；卡钮 `取消这一场`（Phone:273） | `renderPlan`（app.js:681-692）逐 task 拼一行：taskText（344-358）含 `已报名`/`名额已满（学校说满了，不再提交，不是工具出错）`/`待核对（…）`/`报名未成功：`、`；改用页面点击`＋path_reason；结尾固定 `。要修改计划，回电脑上改。`（691）；无任务卡结构；`#btn-cancel-task` `取消这一场`（index.html:56） | 缺失＋文案 | 有：`state.plan.tasks`（path、path_reason、attempts、retry_until） | 照原型改（卡片化＋`取消这一场` 移到卡上）；结尾句换原型句；`演示：快进到开放前 12 秒`（Phone:277）不进产品 |
| G11 | 重新登录表单（sheet 内共用） | 字段 `账号` `密码`（Phone:334-335）；验证码图 aria `验证码图片，原型示意`＋label `照图输入 4 位字母或数字`（Phone:338-339）；保存勾选 `登录成功后保存到这台电脑`＋小字 `加密保存，只有这台电脑能解开。下次失效时{saveGain}。不勾的话，只在这次运行中有效。`（Phone:342）；固定句 `工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。`（Phone:343）；主钮 `登录`/`提交验证码`＋`换一张图`＋`取消`（Phone:347,900） | `#relogin-panel`（index.html:111-138）：`#relogin-user`/`#relogin-pass`/`#relogin-save`（label `登录成功后保存到这台电脑`，132）；验证码组 `#code` maxlength=4 placeholder `4 位字母数字`（119-120）＋图 140×44（styles.css:152）；固定句 `登录时，工具会替你勾选学校登录页上的《隐私协议》。`（134，**少了「我已阅读并同意」**）；「加密保存…」小字无 | 文案＋结构 | 有：`state.login_relay`（mode、challenge 图 data:image/png 快照）；保存勾选走 `phone_relogin_begin` 参数 | 照原型改：固定句补「我已阅读并同意」；保存勾选小字与四态 lead 见 RL 组 |
| G12 | 视觉主题 | 深色点阵底（底栏、LED 板、配对屏、配对盒）、琥珀主钮、红色错误条（Phone:155-158,246-253 等） | styles.css 仅有 `#offline-note` 红条（85-87）、`#pending-note` 橙色（153）、today 卡重样式（48-52）；无点阵/琥珀体系 | 样式 | — | 照原型改（CSS 新增，跟 G02/G04/PA03 一起落） |
| G13 | 状态 pill 的 stale 档 | 中间态是 `同步中`(busy)（Phone:923） | styles.css:120 定义了 `.pill[data-state="stale"]`，但 app.js:460 只写 ok/off 两态，stale 样式不可达 | 多出＋状态 | 有：前端本地态 | 保留并说明：删除或接通二选一，列给用户（同 settings-gap PH14b 口径） |

## 一、配对组（Phone 本体＋PhoneApp，scene=pair）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| PA01 | 外框（pair 视图，两板共用） | 顶栏无 pill 无底栏（Phone:244-255）；`rootH` 取 `props.height="844px"`、冻结薄壳 `canDemo=false`（Phone:921）；点阵屏＋琥珀宽钮外框 | `section#pair.card`（index.html:15-29），h1 `连接电脑`，styles.css .card 41-46；`#pair`/`#app` 切换只靠 hidden（app.js:771-772、816-817） | 结构 | — | 照原型改（点阵屏、琥珀宽钮，随 G12） |
| PA02 | 配对说明 | `配对码在电脑的“设置 → 手机访问”里，5 分钟内有效，只能用一次。`＋`手机只是遥控器，真正报名的还是电脑，所以电脑要开着、不能睡眠。`（Phone:253） | `在电脑上的工具窗口里查看 6 位配对码，5 分钟内有效。`（index.html:17）＋步骤 ol 三条（18-22）；`手机只是遥控器…` 无对应（已核 m/ 无此句） | 文案 | — | 照原型改 |
| PA03 | 点阵屏输入 | 点阵屏 maxlength=6、autocomplete=one-time-code、aria `配对码，6 位数字`（Phone:248）；LED 显 `code+"------"` 前 6 位、满 3 位插空格（Phone:908-909）；屏下说明四态 `点上面的点阵屏，输入电脑上的 6 位数`/`还差 N 位`/`输完了，点“配对”`/`{N} 秒后可以再试`（Phone:910） | `#pair-code` inputmode=numeric autocomplete=one-time-code maxlength=6 placeholder `6 位数字` aria-label `配对码`（index.html:24-25）；无点阵屏、无四态说明 | 结构＋文案 | 有：`POST /pair`（phone_http.py:334-353，回会话 cookie+csrf） | 照原型改（点阵屏为视觉件，输入可仍走 input） |
| PA04 | 配对错误两态 | `配对码不对，请核对后重试。再错 {2|1} 次要等 60 秒。`（Phone:633）；`尝试次数过多，请稍后再试。换一台设备也一样要等。`（Phone:632） | 空输入 `请输入 6 位配对码`（app.js:755）；网络异常 `配对失败：网络不通，请确认手机和电脑连的是同一个网络`（761）；失败 `配对失败：`＋服务端 text（766）；服务端实际句：bad_code `配对码不对，请核对后重试`（phone_service.py:252-253）、锁定 `尝试次数过多，请稍后再试`（:241-242），均较原型（Phone:633/632）少次句（`再错 N 次要等 60 秒`/`换一台设备也一样要等`） | 文案＋状态 | 有：服务端 text 透传；**需补**：结构化 `{remaining_attempts, lock_seconds}` | 照原型改；锁定态见 EX03 |
| PA05 | PhoneApp 薄壳 | 与本体同 scene=pair、可交互（`renderVals yes:true`），canvas.json 标 is_interactive | m/ 的 `#pair` 即可交互实现（index.html:15-29、app.js:771-772），无冻结概念 | 已一致 | — | 不动 |

## 二、列表与详情组（PhonePick picked；PhoneSearch search）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| LD01 | 外框（picked） | app 视图＋pill＋底栏；板题 `核对后再开始`＋副题 `勾选不会开始报名。`（Phone:787）；底栏题 `已选 3 场`、副题 `1 场立即报名，2 场预报名`、钮 `核对并开始`（Phone:779,861） | 无独立详情确认页：选择在列表行 checkbox（app.js:492-500），确认在 `#review-panel`（index.html:141-150）；无 `已选 N 场` 计数与副题 | 缺失 | 有：`state.activities`＋前端选中态；`立即/预报名` 区分按开放时刻即可算（原型 Phone:778 按 stOf 开放状态区分，无需 retry_policy） | 需用户定（NEEDS-HUMAN 5）；底栏 `已选 N 场` 可先照原型补 |
| LD02 | 未选场详情卡 | 板 head `开放中`＋板题＋副题 `大学生活动中心二楼，11月3日 19:00–20:30`＋LED `已开放，可以立即报名｜现在`＋钮 `选这一场`（Phone:789-793,268） | 无活动详情卡（地点/时段/主办）；meta 只有 开放/截止/已报名（app.js:170-176）；无 `选这一场` 钮 | 缺失 | 有：`state.activities` 字段是否含地点/时段长文**需核实** | 随 NEEDS-HUMAN 5 一起定 |
| LD03 | 外框（search） | 搜索框展开、值 `讲座`；命中组 `正在开放｜现在就能报｜1 场`；板区＋`选这一场`（Phone:521,283,737,789-793） | 搜索在 `#more-panel` 内 `#q`，input 事件改 model.filter.q（app.js:1257）；过滤 filterItems（18-39）；无整页搜索视图 | 结构 | 有：前端过滤 | 需用户定（NEEDS-HUMAN 4）；搜索能力本身已一致 |
| LD04 | 勾选冲突提示 | `「{新}」与「{已}」的活动时间重叠，只能选其中一场。已保留原选择。`（Phone:700） | `actionable`（app.js:178-184）：signed/closed/时间未知/与已报名时段重叠都不可选——**静默禁用，无提示条** | 状态＋文案 | 有：冲突判定前端（在途 signedClash） | 照原型改（提示条文案照抄） |

## 三、运行与等待组（PhoneRun running；PhoneCheck pending）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| RW01 | 外框（running） | pill `已连接`；板 tag `等开放`；LED `00:09:53` amber、cap `开放时间`、capB `14:30:00`（Phone:815-816）；板题＋副题 `这一批 2 场同时提交，到点自动开始。`（Phone:817）；四站进度 `启动` `准备好` `开放提交` `核对结果`（Phone:820-825）；任务卡带 `取消这一场`；列表收起→钮 `查看活动列表`（Phone:930）；底栏题 `计划进行中`、副题 `断网时也可以点停止`、钮 `停止计划`（Phone:868） | 仍在 `#today-items` 卡内：`#btn-start` 换 `#btn-stop` `停止计划`（hidden=!busy，app.js:468）＋`#btn-cancel-task`（469）；无 LED/四站进度/任务卡；`#plan-line` 拼行＋`。要修改计划，回电脑上改。`（691） | 缺失＋文案 | 有：`state.busy`、`state.plan.tasks`；动作 `stop_plan`（970）、`cancel_task`（991-992，只取 tasks[0]） | 照原型改（G02/G04/G10 落地后本板大部分随之解决） |
| RW02 | 外框（pending） | 板 tag `核对中`(off)；LED `--:--:--`、cap `还没有查到开始结果`；板题 `开始请求已发出`＋副题 `电脑可能已经开始，也可能没收到。工具只查询结果，不会重复发送。`（Phone:800-802）；底栏题 `还没有查到结果`、副题 `请先不要重复点击`、钮 `取消等待`（Phone:867） | `#pending-note` hint `已发出开始请求，正在核对结果，请先不要重复点击。`（index.html:54）＋`#btn-cancel-start` `取消等待`（55）；对账文案 `还没有查到开始结果。可点「取消等待」结束本次请求，再重新选择。`（app.js:939） | 文案＋缺失 | 有：动作 `start_plan`（914-918）、`start_request_state`（931-932）、`cancel_start_request`（952-953）；15 秒 pending 窗口（161-164） | 照原型改（板卡化）；取消确认见 RW03 |
| RW03 | 取消等待确认 | 题 `取消这次等待？`、文 `只是不再等这次结果。如果计划其实已经启动，刷新后还要再点“停止计划”。`、钮 `继续等`/`取消等待`（Phone:879） | 原生 confirm `取消这次待确认的开始？已经启动的计划仍需点「停止计划」。`（app.js:948）；成功 `已取消这次开始，可以重新选择报名活动。`（956） | 文案 | 有：`cancel_start_request` | 文案照原型改；外壳随 NEEDS-HUMAN 1 |

## 四、重登与验证码组（captcha／auto／relall／relacct／relconfirm／relbad）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| RL01 | 外框（captcha） | sheet `在手机上重新登录`；lead `电脑会自动填账号密码，你只要输验证码。`（Phone:898）；验证码图＋`照图输入 4 位字母或数字`；主钮 `提交验证码`＋`换一张图`＋`取消`（Phone:900,347） | `#relogin-captcha-group`（index.html:116-126）：img `#captcha` alt `验证码`＋`#code`＋三按钮 `提交验证码`/`换一张图`/`取消`（122-124）；lead 无；label `验证码（只对这场重新登录有效，不过期计时）`（118） | 结构＋文案 | 有：`state.login_relay` challenge 图（只认 data:image/png，app.js:1074）；动作 `phone_relogin_submit`（1189-1192）、`phone_relogin_cancel`（1220-1221）、换图=cancel+begin（1233-1238） | 照原型改（sheet 化随 G03）；lead 见 RL05 |
| RL02 | 提交过程文案 | 忙态 `正在向电脑要验证码…`/`正在准备…`/`正在登录，请等结果`（Phone:886） | `正在校验验证码…`（app.js:1091）、`正在准备验证码…`（1101）、`等待验证码…`（1171）、`验证码已换代，请看新图`（1181）、`提交结果未知，正在对账…`（1196）、`duplicate_submit`→`验证码正在提交，请等待结果`（1204） | 文案 | 有：relogin_relay 状态机 | 照原型改（归并成原型三态） |
| RL03 | 外框（auto） | sheet 忙态 `电脑正在自动登录`＋文 `验证码由电脑识别，手机上不用操作。电脑连续认错 3 次，才会转给你输入。`＋钮 `收起，在后台继续`（Phone:888） | 无独立画面：`#relogin-note` `电脑正在自动登录`（＋rounds）＋`…`（app.js:1046-1047）、`电脑会自动识别验证码；连续失败几次之后才会转到这里手动输入`（1049-1050）、`电脑正在自动登录，手机上不用再操作`（1166）；手机不领图（1052） | 结构＋文案 | 有：`state.login_relay.mode=="auto"`；连续失败转 manual 由服务端决定 | 照原型改（sheet 化＋`收起，在后台继续`） |
| RL04 | 外框（relall／relacct） | relall lead `电脑上没有保存账号密码，账号、密码和验证码都要输。`（Phone:898）；relacct lead `电脑上没有保存账号密码，输入账号和密码就行。`＋自动认字条 `验证码由电脑自动识别，你不用输入。`（Phone:341） | 两态**不区分**：`#relogin-account` 显隐 `!(model.reloginSetup && (!setup.saved || setup.paused))`（app.js:475）；是否装识别只影响服务端 mode=auto 文案；无 lead、无自动认字条 | 缺失＋状态 | 有：`state.login_relay`＋`relogin_setup`（saved/account_hint/ocr_ready/paused 四字段已在，app.py:3042-3056；m 侧 app.js:863 已接收、:370 已消费 ocr_ready）——字段已存在，纯前端可做 | 纯前端可做（lead 四态字段已就绪，原「需后端先补」撤销）；文案照原型 |
| RL05 | lead 四态与错误 | `电脑连续 3 次没认对验证码，换你来输。账号密码由电脑自动填写。`/`电脑会自动填账号密码，你只要输验证码。`/`电脑上没有保存账号密码，账号、密码和验证码都要输。`/`电脑上没有保存账号密码，输入账号和密码就行。`（Phone:898）；错误 `学校说账号或密码不对。为了避免账号被锁，没有重试。核对后再登录。`（Phone:689） | 无 lead；失败 `重新登录结束：`/`上次重新登录未完成：`＋safe_error（app.js:1115-1122）；表单缺填 `账号和密码都要填。`（1146） | 文案 | 有：safe_error 服务端透传；`学校说账号或密码不对…` 是否已是取值之一**无法验证** | 照原型改；lead 依赖 RL04 字段 |
| RL06 | 外框（relconfirm） | sheet 文 `用电脑上存的账号密码登录一次，验证码由电脑识别。这会向学校发送一次账号密码，工具会替你勾选学校登录页上的“我已阅读并同意《隐私协议》”。成功后会刷新活动列表，计划不会自动开始。`＋钮 `自动登录一次`/`取消`（Phone:889,348） | **无确认步骤**：beginRelogin 直接 POST（app.js:1132-1174） | 缺失 | 有：begin 回 mode；确认仅前端步骤 | 需用户定（缺实现清单第 4 条）：建议照原型加确认层（纯前端） |
| RL07 | 外框（relbad） | sheet 顶部红错误 `电脑上保存的密码学校不认，自动登录已暂停。请输入新的账号密码；勾选保存会替换旧的。`（Phone:885）；无 lead | **无专门分支**：只能经 setup.paused 触发表单显隐（app.js:475）＋失败文案 safe_error 透传（1115-1122） | 缺失＋状态 | 有：`relogin_setup.paused` | 照原型改（前端判 paused 显示固定句，是否要新字段随 RL04） |
| RL08 | 完成态 | 钮 `完成`＋文 `重新登录成功，报名计划照常继续。`/`重新登录成功，活动列表已刷新。计划不会自动重新开始，要你重新核对后再点开始。`＋附言 `账号已加密保存到电脑，下次失效时{…}。`或 `账号只在这次运行中有效，关闭工具后清除。`（Phone:892-894,882） | `重新登录成功，报名计划照常继续`（busy）/`重新登录成功，正在刷新列表`（app.js:1108）；非 live `上次重新登录已完成；需要时点「重新登录」再试`（1113）；无附言 | 文案 | 有：busy 判定；saveGain 分支需 `relogin_setup` | 照原型改 |

## 五、sheet 组（review／reviewwarn／stopsheet／cancelsheet）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| SH01 | 外框（review） | sheet 题 `核对计划`（Phone:872）；批次头 `{HH:MM:SS 或 现在}`＋`立即报名 N 场`/`预报名，同时提交 N 场`/`预报名 1 场`（Phone:770,775）；条目名＋`活动 {时段}`＋移除钮 aria `从计划移除 {名}`（Phone:771）；字段 `尝试时长`＋`最多提交次数（0 = 不限）`（Phone:306）；提示 `自动延长，最多 25 分钟；报名截止仍是硬上限。`/`缺报名截止时间的场次，本次最多 2 分钟。`（Phone:917）；主钮 `开始报名计划`（Phone:941） | `#review-panel`（index.html:141-150）：h3 `核对计划`、`ul#review-items`、`#review-policy`（=retryHint，app.js:154-158：`没有报名截止时间：本次最多 2 分钟`/`自动延长，最多 25 分钟；报名截止仍是硬上限`）、`返回`＋开始钮（148-149）；`尝试时长` select `#retry-for`＋`#max-attempts` 在 `#more-panel`（91-98）；无批次头、无 `活动 {时段}`、无移除钮；`#retry-for` 选项 label 由服务端下发（app.py:249-264），其中 `自动延长（最多25分钟）` 较原型 `自动延长`（Phone:306）多「（最多25分钟）」括注 | 结构＋文案 | 有：`state.retry_options.choices`（app.js:869-872；label 后端下发且可验证：app.py:249-264 取值 `2 分钟/10 分钟/30 分钟/1 小时/自动延长（最多25分钟）/直到报名截止`） | 照原型改：批次头与移除钮补进面板，`尝试时长` 选项移进面板 |
| SH02 | 外框（reviewwarn） | 提醒 ul：`「{名}」没给报名截止时间，“直到报名截止”对它只会尝试 2 分钟。`（Phone:913）／`要等到 {HH:MM}，电脑上没装验证码识别/电脑上没开自动登录。中途登录失效要你输验证码；开放前 100 秒内失效，那场就结束。`（Phone:915）／`有场次在 24 小时后才开放，电脑要开着、不能睡眠。`（Phone:916）；主钮 `仍然开始报名计划`（Phone:941） | `ul#review-warns`（styles.css:163-164 琥珀条，在途段）：`北京时间在用上次的校准结果，电脑会自动重新校准。`（app.js:366）／`最晚一场要等 1 小时以上，电脑的自动登录没开全：中途登录失效要你重新登录；开放前 100 秒内失效的那场会直接结束。`（371）／`尝试时长选了「直到报名截止」，但有场次没给截止时间：这些场次最多试 2 分钟。`（375）／`最晚一场 24 小时以后才开放：这段时间别关电脑上的工具，也别让电脑睡眠。`（377）；按钮切换 `仍然开始报名计划`/`开始报名计划`（1027） | 文案＋已一致 | 有：retry_policy、sign_end、business_clock.state | 照原型改：提醒句式与「没装识别/没开自动登录」分支对齐原型 |
| SH03 | 外框（stopsheet） | confirm 题 `停止报名计划？`、文 `工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。`、钮 `继续计划`/`停止计划`（红）（Phone:874,313） | 原生 confirm `确定停止这次计划？`（app.js:967）；无解释文、无双钮样式 | 缺失＋文案 | 有：动作 `stop_plan`（970）；无 plan_id 直接 return（968-969） | 需用户定（NEEDS-HUMAN 1）；确认文案照原型 |
| SH04 | 外框（cancelsheet） | confirm 题 `取消这一场？`、文 `「{名}」还没提交，取消后不会再报名，其他场次继续。`、钮 `先不取消`/`取消这一场`（Phone:877） | 原生 confirm `确定取消这一场？`（app.js:987）；只对 plan.tasks[0]（989） | 缺失＋文案 | 有：动作 `cancel_task`（991-992） | 同 NEEDS-HUMAN 1 |
| SH05 | 更多 sheet | 题 `更多`（Phone:873）；节 `开放时间`（chips `不限` `今天` `7 天内`，Phone:936）；节 `登录`＋loginLine 四态＋钮 `在手机上重新登录`（Phone:319,937）；节 `电脑窗口`＋`窗口被隐藏到后台时，可以从这里叫回来。`＋钮 `显示电脑窗口`（Phone:320）；节 `运行记录` 日志（Phone:499,321） | `#more-panel` details（index.html:72-151）：筛选 chips（79-88）、重试设置（91-98）、`#window-panel` `电脑窗口`＋`电脑上的窗口可能被隐藏到后台了（程序还在跑）。`＋`显示电脑窗口`（105-109，action=`show_window`）、重新登录面板（111-138）、日志 `#logs` 最多 40 条（app.js:694-699）；loginLine 四态散在 relogin 面板，无独立 `登录` 节 | 结构＋文案 | 有：`show_window`；loginLine 需 `state.login`＋`relogin_setup` | 照原型改：节序与标题对齐；`登录` 节钮指向 relogin 面板 |
| SH06 | 操作失败红条 | `网络不通，这次操作没有发出去。电脑上的计划还在跑，恢复连接后再试。`（Phone:870） | 失败 log `没能停止计划：`/`没能取消这一场：`（app.js:972、994）＋通用 offline 条 | 缺失 | 有：前端 fetch 失败 | 照原型改（行内红条） |

## 六、结果组（PhoneResult result）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| RS01 | 外框 | 板 tag `部分完成`；统计 `1 已报名｜1 名额已满｜1 待核对`（Phone:535,829-832）；板题 `报名计划部分完成`＋副题 `有 1 场需要到活动页核对，结果以学校为准。`（Phone:836）；无 LED 换统计大数字区（Phone:262,828-840）；底栏纵排 `完成，回到活动列表`（Phone:295,833） | **无独立结果页**。三处替代：`#plan-line` 逐场结论（app.js:681-692＋taskText 344-358）；`details#signed-summary` `已报名 N 场`（index.html:65-68，计数 app.js:674-675）；`#logs`（694-699） | 缺失 | 有：`state.plan.tasks` 的 outcome/stop（前端可聚合统计） | 需用户定（NEEDS-HUMAN 2：独立结果页 vs 折叠区）；统计行可先补进 plan-line 上方 |
| RS02 | 任务卡原因 | `学校回“操作成功”，结束时向学校核对过：已报名`（Phone:564）／`学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。已提交 2 次`（Phone:560）／`已提交 4 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动页看一眼，或稍后刷新核对。工具不会再自动重发。`（Phone:565） | taskText：`已报名`／`名额已满（学校说满了，不再提交，不是工具出错）`／`待核对（去活动页看一眼，工具不会再自动重发）`（app.js:344-358）；无提交次数明细 | 文案 | 有：outcome、attempts | 照原型改（随 G10 卡片化） |

## 七、条款（PhoneTerms phoneterms）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| TM01 | 外框 | pill `已连接`；告警 `电脑上还没有同意使用条款`＋`回电脑同意后才能登录和报名。现在显示的是上次的缓存。`（无钮，Phone:853）；板 tag `已暂停`(off)、LED cap `电脑上同意条款后才能报名`、板题 `电脑上还没有同意条款`＋副题 `同意前只能看缓存，不能报名，也不能重新登录。`（Phone:798）；列表行全禁用（Phone:742）；底栏副题 `电脑上同意条款后才能开始`＋`核对并开始` 禁用（Phone:863） | `#banner.error` `电脑上还没同意使用条款：这里停在上次的结果，不能开始报名，也不能重新登录。`（app.js:880，kind=terms）＋`#btn-start` disabled 追加 termsOk===false（467）＋`#btn-relogin` 同（471）；无整页态、无行禁用 | 文案＋缺失 | 有：`state.terms_ok`（862）；服务端也会拦写动作 | 照原型改（告警文案对齐；板态随 G04） |

## 八、异常态（离线／过期／锁定／电脑侧）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| EX01 | 外框（offline） | pill `离线`(bad)（Phone:923）；告警 `连不上电脑，已重试 3 次`＋`确认电脑开着、程序没退出。如果只是手机断网，电脑上的计划不受影响。`＋钮 `重试`（Phone:852）；LED cap `状态已过时`、capB `最后同步 14:19:40`（Phone:826,508）；底栏 `停止计划` 仍可点（Phone:868） | `#offline-note.warn`（index.html:40，sticky 红条）：`连不上电脑：确认电脑上的程序还开着、手机和电脑在同一网络，再点右上角「刷新」。`／重试后 `连不上电脑（已重试 N 次）：…`（app.js:452-453）；`#stale-note` `状态已过时：先点右上角「刷新」，拿到最新状态后才能开始报名。`（index.html:41）；`#conn` `离线/未知`；退避 1s→15s（app.js:69-72）；恢复自动清（444-447） | 文案＋结构 | 有：前端断网推（无后端字段） | 照原型改：告警句加 `重试` 钮、措辞对齐原型（`确认电脑开着、程序没退出…`） |
| EX02 | 外框（expired） | pill `已连接`；告警 `电脑上的登录已失效`＋`可以在手机上重新登录，也可以回电脑处理。`＋钮 `重新登录`（Phone:854）；底栏题 `已选 1 场`、副题 `还差一步：重新登录`、钮 `重新登录`（Phone:864） | `#login-expired-banner.warn` `电脑上的登录已失效：可以在下面「更多 → 重新登录」里处理，也能回电脑上点重新登录。`（index.html:43，静态）；显隐 `state.login.session_expired || !session_present`（app.js:886-890）；无横幅内 `重新登录` 钮、无底栏变化 | 文案＋缺失 | 有：`state.login.session_expired`/`session_present` | 照原型改（横幅内加 `重新登录` 钮指向 relogin 面板） |
| EX03 | 外框（pairlock） | tag `已锁定`(红)（Phone:910）；错误条 `尝试次数过多，请稍后再试。换一台设备也一样要等。`（Phone:501）；说明 `47 秒后可以再试`；`配对` 钮禁用、输入禁用（Phone:248,910） | **无锁定 UI**：锁定语义全在服务端 text，进 `配对失败：…`（app.js:766）；服务端实际句 `尝试次数过多，请稍后再试`（phone_service.py:241-242），较原型（Phone:501）少 `换一台设备也一样要等` 尾句（文案差计在 PA04） | 缺失＋状态 | **需补**：`POST /pair` 回包结构化 `{locked, retry_after_s, remaining}` | 需后端先补（锁定秒数/次数），前端再做禁用与倒计时 |
| EX04 | 外框（pairfail） | tag `输入配对码`；错误条 `配对码不对，请核对后重试。再错 2 次要等 60 秒。`（Phone:525）；LED 红色调（Phone:909） | `#pair-error` role=alert＋`配对失败：`＋text（app.js:766）；无剩余次数、无 LED 变色 | 文案＋状态 | 同 EX03 | 同 EX03（剩余次数文案） |
| EX05 | 外框（pclisterr） | 告警 `电脑上的活动列表没加载`＋`电脑那边连不上学校站点，现在显示的是 14:12 更新的列表。恢复后会自动更新。`（无钮，Phone:855）；底栏不出现（Phone:860） | **无对应实现**：手机列表直接吃 `state.activities`，电脑列表失败无专门提示；最接近通用 `#offline-note`/`#stale-note`（index.html:40-41） | 缺失 | **需补**：`GET /api/state` 增 `pc_list_error`（或 `activities_stale_at`） | 需后端先补 |
| EX06 | 外框（pcclock） | 顶栏北京时间换 `待校准`（Phone:928）；告警 `电脑上的北京时间还没校准`＋`校准后才能开始报名计划，现在可以先选活动。`（无钮，Phone:856）；LED `--:--:--`、cap `电脑上的北京时间待校准`（Phone:797）；行内距开放 `待校准`（Phone:760）；底栏副题 `电脑校准北京时间后才能开始`＋`核对并开始` 禁用（Phone:865） | **无整页/横幅态**：`state.business_clock.state` 入 model.clockState（app.js:864-867，ready/holdover，超 900 秒不可信 252-258）；holdover 时提醒 `北京时间在用上次的校准结果，电脑会自动重新校准。`（366）；canStart 只看 stale/busy（112-116），**时钟完全不可用不拦开始**——与决策 012「时钟不可用时不能开始报名」的缺口要单独核 | 缺失＋状态 | 有：`state.business_clock.state`（后端词汇 syncing/ready/holdover/unavailable，business_clock.py:254；快照异常兜底亦回 `unavailable`，app.py:816）——down 档已存在，缺前端消费（app.js:247-249 只认 ready/holdover），纯前端可做 | 纯前端可做（`unavailable` 档后端已下发，前端补识别与横幅；原「需后端先补」撤销）；开始禁用联动是否属手机侧见 NEEDS-HUMAN 6 |

## 九、Main 承载的 4 个画板（电脑侧画面，m/ 不承载）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| MN01 | 外框（phonesetup，可交互） | 双栏＋设置抽屉手机访问节：`下载并安装`、lead、体积、位置条（Main:1362-1372,701-708） | m/ 无设置页：最接近配对页三步说明（index.html:18-22）＋`#more-panel` 重试设置（91-98） | 缺失（对 m/ 而言合理） | —（电脑端 `advanced_features_state`） | 保留并说明：安装引导属电脑端画面，对账走 `design/evidence/2026-11-07/settings-gap.md` PH03-PH15；m/ 不补 |
| MN02 | 外框（phonets） | chip `未开启`、通道单选组、`开启手机访问` 禁用、提示 `还差一步：登录 Tailscale 后点“重新检测”，或者改用 Cloudflare。`（Main:1375-1385,717-718） | m/ 无任何 Tailscale UI/文案；最接近 phone_http.py https 隧道 Host/Origin 白名单（45-59、223-233），手机侧无感 | 缺失（对 m/ 而言合理） | — | 同上，走 settings-gap PH16-PH21 |
| MN03 | 外框（phonewait） | 顶栏手机 pill `等手机连接`(warn)（Main:2453）；配对盒 `482 913`＋`4:32 后失效，一码只能用一次`＋地址行＋`关闭手机访问`（Main:1391-1411,726-735） | m/ 对应物 `#pair` 未配对态（index.html:15-29）；无电脑侧画面 | 缺失（对 m/ 而言合理） | — | 同上，走 settings-gap PH23-PH31 |
| MN04 | 外框（phonelinked） | pill `手机已连接`(ok)（Main:2453）；绿条 `手机已连接。配对码已换成新的，旧码不能再用。`、凭据提示＋`去保存`、`再配对一台手机`（Main:1391-1411,723-733） | m/ 对应物 `#conn` pill `已连接`＋`#last-sync`（index.html:33-39、app.js:380-383）；无「手机已连接」专门态 | 缺失（对 m/ 而言合理） | 电脑端已需补 `paired_count`（settings-gap B1） | 同上；m/ 侧无需改动 |

## 差异统计（按类型，双类型行各计一次）

- 缺失 23 ｜ 文案 28 ｜ 结构 14 ｜ 状态 8 ｜ 已一致 3 ｜ 样式 1 ｜ 多出 1（共 52 行，78 个类型计次）
- 已一致 3 行：G06（冲突 why，在途；对抗审阅记两处小偏差：原型 aria 带『的原因』尾缀、代码 >7 天稀疏化，见该行）、PA05（PhoneApp 机制）、SH02 的按钮切换（该行其余部分是文案）
- 「需后端先补」明确落在 2 行：EX03、EX05；PA04、EX04 依赖同批字段；LD02 需字段核实；RL05 保留无法验证；RL04/EX06 已降为纯前端可做（对抗审阅 2026-11-08）

## NEEDS-HUMAN（需用户定）

1. **原生 confirm 是否换 sheet**：SH03/SH04/RW03 三处 `window.confirm`（app.js:967、987、948）与 review/更多面板要不要上 G03 的 sheet 外壳。上外壳是 m/ 纯前端工程量最大的一项；不上则保留 confirm、只把确认文案照原型改。
2. **PhoneResult 独立结果页 vs 折叠区**：RS01。建议折中：先补统计行与任务卡原因文案（RS02、G10），独立页另批。
3. **12 个缺实现的取舍顺序**（l3-code 缺状态清单 1-12）：建议顺序 ①sheet 外壳＋stop/cancel 确认（NEEDS-HUMAN 1 定后）→ ②relogin lead 四态与 relconfirm 确认层（RL04-RL07，纯前端）→ ③pair 锁定态（EX03/EX04，需后端）→ ④pclisterr/pcclock 横幅（EX05 需后端、EX06 纯前端）→ ⑤独立搜索页/详情确认页（LD01-LD03）。顺序本身需确认。
4. **独立搜索页 vs 折叠内搜索**（LD03）：原型是整页搜索视图，现藏 `#more-panel`。
5. **详情确认页 vs checkbox＋复核面板**（LD01/LD02）：原型 PhonePick 是独立确认页＋`选这一场` 钮，现无。
6. **时钟不可用不拦开始**：EX06 发现 canStart 只看 stale/busy（app.js:112-116），决策 012 写「时钟不可用时不能开始报名」。手机侧要不要补禁用、还是依赖电脑端/服务端拦截，需用户定（可能超出 m/ UI 范围）。

## 无法验证清单

- 像素级排版、断行、动画（sheet rise、LED 闪烁、pair 输入联动）——需 Edge/WebView2 实测（AGENTS.md：断行以 Edge 为准）；素材未运行浏览器，本表沿用其静态结论。
- 冻结薄壳的动态过程（配对码到点换新、倒计时走表）。
- 服务端下发文案的实际取值：relogin safe_error（对抗审阅复核：手机侧取值经 worker reason，静态不可断，保留）。〔pair 锁定 text、retry_options label 已销案 2026-11-08：phone_service.py:241-242/252-253、app.py:249-264，见 PA04/EX03/SH01 行〕
- 原型合成数值（`00:09:53/55`、`4:32`、`1 已报名｜1 名额已满｜1 待核对`）由状态机推算，未渲染核对。
- Main 四板的手机 pill 详情卡（phoneCard）默认不展开，可见性靠交互触发。
- `state.activities` 是否已含地点/时段长文/奖励/冲突字段全集（LD02 需核实；在途 conflict-cancel 块已引用其中一部分）。
- styles.css:120 `.pill[data-state="stale"]` 不可达为静态推断，未运行验证。

## 修订记录（对抗审阅 2026-11-08）

对抗审阅合并见同目录 `ADVERSARIAL-L3.md`（依据共享暂存区 `<过程留证>/adv-L3-a.md`、`adv-L3-b.md`；以本表 52 行对账为基准，同行不一致取更严格）。本次只改本报告，不改代码。

- **红牌②（8 条）**：原型引文直引号改回全角弯引号——G10（Phone:276 `“修改计划”`）、G11（Phone:343）、PA03（Phone:910 `点“配对”`）、RW03（Phone:879 `“停止计划”`）、RL06（Phone:889）、SH02（Phone:913 `“直到报名截止”`）、RS02（Phone:564 `学校回“操作成功”`）、MN02（Main:1385 `点“重新检测”`）。
- **红牌①（2 条）**：PA05、MN04 现状格补 file:line（index.html:15-29＋app.js:771-772；index.html:33-39＋app.js:380-383）。
- **判定修正**：G06 原型 aria 实带『的原因』尾缀（Phone:288），代码侧 aria=标题逐字（app.js:569），并补代码 `days.length > 7` 稀疏化（app.js:326-332）差异；LD01 删「需 retry_policy」（原型 Phone:778 按开放状态区分）；SH01 补 label 差（app.py:249-264，`自动延长（最多25分钟）` 对原型 `自动延长`（Phone:306）），差距类型改 `结构＋文案`。
- **降档**：RL04、EX06「需后端先补」→「纯前端可做」（`relogin_setup` 四字段已在 app.py:3042-3056 且 m 侧 app.js:863/370 已消费；时钟 `unavailable` 档已在 business_clock.py:254、app.py:816）；NEEDS-HUMAN 3 同步。
- **销案**：无法验证两条关闭——pair 锁定 text＝phone_service.py:241-242/252-253（与原型少次句，补进 PA04/EX03 现状格）、retry_options label＝app.py:249-264；RL05 safe_error 保留。
- **记法修正**：`app.js` 在途增量 +322/−4 → +318/−4（git diff --numstat，原值系 `--stat` 柱数误读）；排除条点名 `PhAddPair.dc.html`（不属本表分母，任务书口径）。对抗 A 报「scene 枚举漏 relbad」经机器比对不成立（第 8 行枚举 23 项与磁盘逐一相同、relbad 在列，A 所阅疑为提交前草稿），未改；RL07 引 Phone:885（赋值行，字面串在 519/666/690）与 G06 引 Phone:142（图例 CSS，文本在 288）记 ADVERSARIAL-L3.md §6，报告本次不改。
- **统计**：修订前 缺失 23｜文案 27｜结构 14｜状态 8｜已一致 3｜样式 1｜多出 1（77 计次）→ 修订后 缺失 23｜文案 28｜结构 14｜状态 8｜已一致 3｜样式 1｜多出 1（78 计次）。落点：SH01 增计文案一次；pair 锁定文案差经 PA04（原类型已含文案）承载不重复计次；G06 维持已一致归类、两处偏差记入行内。
