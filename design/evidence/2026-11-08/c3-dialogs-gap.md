# 对话框与横幅：原型与现行代码的逐项差距（2026-11-08）

只读审计，没有改任何代码和原型。由原型侧素材（23 画板逐字文案、外框、结构、状态覆盖、父子关系）与代码侧素材（file:line 现状）两份只读扫描合并而成。用途：后面的计划照这张表给执行者下具体指令。

## 范围与读法

- **基准**：`design/prototype/workbench-2026-11/Main.dc.html`（下称「原型」）的**工作区版本，2498 行**；a85209e 提交里的同名文件是 2283 行。**本报告所有 `Main:NNNN` 行号一律指工作区版本**（工作区相对 a85209e 为 +232/−17 行）。
- **现状**：`local/ui/index.html`、`local/ui/styles.css`、`local/ui/state/store.js`、`local/ui/views/{tour,terms,help,update,settings,plan-panel,list}.js`、`local/ui/controllers/{window,update,terms,prefs,bridge}.js`、`local/ui/app.js`，后端 `local/app.py`、`local/runtime_paths.py`。行号为 2026-11-08 磁盘现状。
- **在途改动**：工作区有 40 余项他人在途改动（本报告开工时 `git status --short` 实测 43 项），不属本表。23 画板直接命中的文件里，views/tour.js、views/terms.js、views/help.js、views/update.js、controllers/window.js、controllers/update.js、controllers/terms.js、controllers/prefs.js、controllers/bridge.js 相对 a85209e 干净；index.html、styles.css、app.js、state/store.js、views/plan-panel.js、views/list.js 带在途修改，行号会随他人继续漂移。
- **23 画板清单**（scene 名随画板列出）：关窗组 5——CloseAsk（closeask）、CloseConfirm（closeexit）、CloseHidden（closehidden）、CloseIdle（closeidle）、CloseLive（closerun）；更新组 5——UpdateAvail（upavail）、UpdateDown（updown）、UpdateFail（upfail）、UpdateLive（update）、UpdateReady（upready）；引导组 3——TourTable（tour）、TourPick（tour2）、TourRun（tour4）；FirstUse（first）1；条款组 6——TermsDoc（termsdoc）、TermsPrivacy（termsprivacy）、TermsOff（termsoff）、TermsUnknown（termsunknown）、TermsUpdate（termsupdate）、TermsWithdraw（termswithdraw）；HelpKeys（helpkeys）1；迁移组 2——Migrated（migrated）、MigrateFail（migratefail）。合计 23（任务描述写「条款 7」，两份素材均为条款 6 块、合计 23，以素材为准）。
- **范围外（只提一句）**：登录对话框（rl 状态机）、手机页、计划面板运行态文案、LED 与状态卡，属 L2 其他组。
- 原型里标「演示：」的控件（UpdateLive 的演示下拉等）不进产品，沿用 2026-11-07 设置抽屉对账表的既定口径；本表不为它们建行。
- 字符串都用反引号包着逐字抄自原型或代码，其中的引号、标点就是原样。原型里的数值（`2 场`、`14:30:00`、`92.4 MB` 等）是画板示意值。

### 列的含义

- **差距类型**：文案 / 结构 / 缺失 / 多出 / 状态 / 样式 / 已一致。
- **后端信号**：「有」后面写现成的桥方法或字段；「需补」后面写最小新增。
- **建议**：照原型改 / 保留并说明 / 需后端先补 / 需用户定 / 不动。
- 「已一致」的行不要再动。
- 每个画板至少一组行，**第一行必须是「外框」**（原型对话框宽度、标题栏、关闭按钮、分组标题、按钮排布 对 代码外框现状）；共用外框在组内第一行全量描述，后续画板的外框行只写差异。

---

## 一、关窗组（画板 1-5）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| CW01 | 外框（CloseAsk／CloseConfirm／CloseIdle 共用） | 窗口标题栏（chromeOn，Main:531）＋模态遮罩＋`.dlg.sm` 内联覆盖宽 `min(30rem,100%)`（Main:811，覆盖 266 的 26rem）；标题栏深色板底＋h2 琥珀左线（Main:267-269）；无关闭 X；脚部勾选框居左＋`先不关` 线框钮居右（Main:820） | 原生 `<dialog class="dlg dlg-close">`（index.html:396）；宽 `min(460px, 92vw)`（styles.css:391）；`.dlg-head` 无深色板底（index.html:397-400）；无关闭 X；勾选框是脚部上方独立一行（index.html:421）；`.dlg-foot` 只有左侧 `先不关`＋右侧弹簧（index.html:422-425） | 结构＋样式 | — | 照原型改：宽度、深色标题栏、勾选框与按钮分区（勾选居左、主钮居右） |
| CW02 | CloseAsk · 标题与副题 | 标题随计划状态切换：运行时 `报名计划还在运行`（Main:1724）；副题 `最小化或隐藏都不影响计划，退出会停止它。`（Main:1725） | 标题固定 `要关闭这个窗口吗？`（index.html:398）；副行三态：默认 `关掉窗口会停掉手机访问和报名计划。`（index.html:399）；运行 `报名计划正在运行：退出会停掉计划，手机立刻失去访问。建议最小化或隐藏到后台，让它继续跑。`／空闲 `退出后手机访问和电脑端的推送、自动报名都会停。想让它继续干活就选「隐藏到后台运行」。`（controllers/window.js:43-45） | 文案＋状态 | 有：window_close_ask 载荷 plan_running（app.py:2778） | 照原型改（标题随状态切换） |
| CW03 | CloseAsk · 利害清单 | `.stakes`（aria-label `正在运行的事`，Main:815）两条：`报名计划`＋`2 场等开放，最近一批 14:30:00`（Main:1706）；`手机访问`＋`手机已连接`（绿点，Main:1709） | `#dlg-close-running`（aria-label `正在运行`，index.html:401；styles.css:968-969）；行文案 `报名计划正在运行`／`手机访问开着，手机已连接`／`手机访问开着`（window.js:50-52） | 文案 | 有：plan_running、phone_running、phone_live（window.js:47-54）；「等开放场数与最近一批时刻」需补 | 照原型改；场次细节需后端先补 |
| CW04 | CloseAsk · 三张选择卡 | 顺序 `最小化到任务栏`（`推荐` 徽章）→`隐藏到后台`→`退出程序`（红）；正文 `窗口缩到任务栏，计划和手机访问都照常。`／`窗口不见了，工具在后台继续运行。从右下角托盘图标或手机页叫回来。`／`报名计划会停止，还没提交的 2 场不会再报名。手机也会断开。`（Main:1715-1718） | 顺序 `隐藏到后台运行`→`最小化到任务栏`（#close-rec `推荐`）→`直接退出`（is-danger）；正文 `窗口收起来，电脑继续推送、手机照常可用、报名计划不停；托盘图标或手机页都能叫回来，两者都没有时工具不会隐藏。`／`只是把窗口缩下去，任务栏还留着按钮，点一下就回来。`／`手机访问和报名计划都会立刻停止，未完成的计划不会自己继续。`（index.html:406-420） | 文案＋结构 | — | 照原型改文案；卡序是否调整需用户定 |
| CW05 | CloseAsk · 隐藏禁用原因 | `现在叫不回来：托盘图标没建起来，手机也没连着，所以不能隐藏。`（Main:1715 定义、1719 承载） | `现在不能隐藏：托盘图标没建起来，手机也没连，藏起来就叫不回来。`（window.js:62，#close-hide-why） | 文案 | 有：tray_ok、phone_live（window.js:58-59；老载荷缺 tray_ok 按可用处理） | 照原型改 |
| CW06 | CloseAsk · 焦点与 Esc | 出现即聚焦第一张选择卡（Main:1818-1822）；Esc＝`先不关`（Main:2446） | `#btn-close-minimize` autofocus（index.html:412）＋JS 兜底 focusSafestClose（window.js:23-31，失败静默）；Esc 走 `<dialog>` 原生 cancel 静默关闭、对话框本身不发动作（window.js 无 cancel 监听）；按键仍先经过全局 Esc 链（app.js:516-528：引导→气泡→状态卡→设置→输入→结果→清空选择逐层匹配，空闲且有勾选时会被 clearSelection 消费） | 状态 | — | 保留并说明（关闭不发动作与原型「先不关」等价；全局 Esc 链副作用见现状列） |
| CW07 | CloseConfirm · 外框 | 同 CW01 框换内容：无勾选框、无选择卡；脚部 `返回`（data-close="back"）＋`停止计划并退出`（btn-stop 红色实心，Main:821） | 同一 `#dlg-close`：`#dlg-close-confirm`（role=alert，红底块，index.html:402-405；styles.css:970-972）内含文案与两钮 `返回`（#btn-close-exit-back）／`仍然退出`（#btn-close-exit-confirm） | 结构 | — | 照原型改（脚部两钮与红色 btn-stop；钮名见 CW08） |
| CW08 | CloseConfirm · 文案与行为 | 正文段 `还没提交的 2 场不会再报名。已经成功的报名不受影响。`（Main:1722）；运行中点 `退出程序` 转 confirm 步（Main:1742-1752）；焦点在 `返回`（Main:1820）；Esc 退回选择步（Main:2446） | `<b>报名计划还在运行。</b>退出会停掉计划，还没提交的场次不会自己继续；手机也会立刻失去访问。`（index.html:402-405）；plan_running 时点 `直接退出` 不发请求，换 confirm 块并隐藏 choices、焦点移 `返回`（window.js:113-125）；`返回` 换回 choices（window.js:129-138）；`仍然退出` 才 submitWindowClose("exit")（window.js:127-128） | 文案＋状态 | 有：request_window_close（app.py:2781；window.js:94） | 照原型改（补 `已经成功的报名不受影响` 一句） |
| CW09 | CloseHidden · 外框 | 整窗替换为模拟桌面（`.desk` 渐变 z-20，Main:869-875）＋中央白卡 `.desk-card` min(25rem)（Main:492-497）＋底部任务栏托盘图标＋时钟（Main:871-873）；不是对话框 | 无对应实现：窗口隐藏后无任何 UI 呈现（无横幅、无托盘气泡 DOM、无 onBackend 事件；grep `已隐藏`、`托盘`、`hide_window`、`tray` 全量复核） | 缺失 | 有：hide_window（app.py:2836-2854），成功只写手机页日志 `窗口已隐藏到后台；进程继续运行，托盘或手机页可以唤回`（app.py:2854）；失败经运行记录（window.js:96-100 ← app.py:2809、2847-2848） | 需后端先补（隐藏态 UI 信号）＋需用户定（模拟桌面是演示形态还是产品形态） |
| CW10 | CloseHidden · 卡文案 | 卡顶小字 `原型演示：关窗以后`（Main:871）；卡标题 `窗口已隐藏，工具在后台运行`＋正文 `报名计划照常运行。点右下角托盘图标回来，也可以在手机页点“显示电脑窗口”。`（Main:1738）；钮 `回到窗口`（Main:1732）；托盘 aria `托盘里的校园活动预报名工具`（Main:873） | 无（同 CW09） | 缺失 | — | 同 CW09；`原型演示：` 小字与静态时钟属演示包装，不进产品 |
| CW11 | CloseIdle · 外框 | 同 CloseAsk 框；利害清单整块不渲染（Main:815 hasStakes=false） | 同一 `#dlg-close`：空闲时运行列表隐藏（window.js:53）、`推荐` 徽章隐藏（window.js:64-65）、`直接退出` 立即提交无二次确认（window.js:113-125 else 分支） | 已一致 | — | 不动（行为差异见 CW12 与 NEEDS-HUMAN 5） |
| CW12 | CloseIdle · 文案 | 标题 `要关闭窗口吗？`；副题 `选一个关闭方式。Esc 先不关。`；`最小化到任务栏`＋`窗口缩到任务栏，点一下就回来。`；`隐藏到后台` disabled＋`现在叫不回来：…`；`退出程序`＋`登录状态会保留，下次打开不用重新登录。`（Main:1715-1719、1724-1725） | 标题仍 `要关闭这个窗口吗？`（index.html:398，不随态变）；副行 idle 版（window.js:45）；三出口文案与运行态同一套（index.html:406-420 不随 idle 换）；隐藏禁用句见 CW05 | 文案＋状态 | — | 照原型改（idle 时退出卡强调 `登录状态会保留…`） |
| CW13 | CloseLive · 外框 | 无对话框——wbar＋完整主界面（计划运行：进度提示 Main:661、`修改计划`／`停止计划` Main:665、顶栏 `设置`／`帮助` Main:558-559）；最大化钮 disabled、关闭钮 `.wbtn x`，供演示点 X | 主窗口即宿主（pywebview 原生窗口框，无自绘 wbar）；点系统关闭 → 后端推 window_close_ask → openWindowCloseDialog（app.js:78；window.js:36-80）；UI 主动调 ask_window_close 仅 `关闭本工具…`（app.js:439） | 结构 | 有：ask_window_close（app.py:2759，emit :2778） | 保留并说明（窗口 chrome 属系统）；计划面板文案属其他组范围 |
| CW14 | CloseAsk · 勾选框文案 | `以后都这样，不再询问`（Main:820） | `以后都这样，别再问我`（index.html:421） | 文案 | — | 照原型改（对抗审阅补记，原表漏记） |

## 二、更新组（画板 6-10）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| UP01 | 外框（5 画板共用） | 设置抽屉 `.draw`（右出 34rem，Main:287-291）内「程序」组「版本与更新」小节（Main:771-786）；节行＝标题＋右侧一枚动作钮；抽屉头部深色＋右上 X（aria `关闭设置`，Main:697） | 同为设置抽屉 `#settings`（index.html:207；styles.css:923 `min(34rem, 100vw)`）→`#set-prog`（index.html:304）→`.help-tool-row.set-update`（index.html:310-313）；标题行同位（index.html:311）；动作钮是一组显隐按钮：`#update-flow` 5 枚初始 hidden＋常驻 `检查更新`／`前往下载页`（index.html:312） | 已一致＋结构 | — | 载体不动；钮组是否收成「每态一枚」需用户定（`前往下载页` 见 UP10） |
| UP02 | UpdateAvail · 外框 | 同 UP01；本态差异：新版本块 `.up-v` 与实心主钮（见 UP04） | 同 UP01；无新版本块 | 已一致 | — | 不动（内容差异见 UP03、UP04） |
| UP03 | UpdateAvail · 版本头与状态行 | `版本与更新 1.2.0`（Main:772）；绿 `发现新版本 1.3.0。`（Main:1434）；`检查时间 11-03 14:20`（Main:773） | `版本与更新`＋`当前 <b id="help-version">—</b>`（index.html:311；版本由 bootstrap 写入 app.js:18）；available `发现新版本 X。`（X=result.latest_version，views/update.js:21-37）；`检查时间 MM-DD HH:mm`（views/update.js:42，toLocaleString("zh-CN",…)，Chromium 实际渲染为斜杠 `MM/DD HH:mm`） | 文案 | 有：check_update（app.py:1726） | 示意值双轨列 NEEDS-HUMAN 2；时间分隔符降档：代码 zh-CN 实际产出斜杠、原型为连字符，格式待定（原「已同构，不动」撤销） |
| UP04 | UpdateAvail · 新版本块与确认步 | `.up-v` 大版本数字 `1.3.0`＋`完整安装包 92.4 MB，下载后先校验，再由你决定什么时候安装`（Main:775）；确认中间态 `下载 1.3.0 安装包（92.4 MB）？只写临时目录，不动现在的程序和你的数据。校验通过后，什么时候安装由你决定。`＋`确认下载`／`取消`（Main:776，无独立画板） | 无新版本块；confirm 态状态行仍是 `发现新版本 X。`（update.js:21-37）；有 `确认下载` #btn-update-confirm／`取消` #btn-update-cancel（index.html:312）；`下载并安装` 先转 confirm 不联网（controllers/update.js:75-81），`确认下载` 才 api("update_download")（controllers/update.js:83-108） | 缺失＋文案 | 有：update_download（app.py:1763）；体积字段有：installer.bytes（update_check.py:100/106） | 照原型改（confirm 问句与体积说明，体积取 installer.bytes）；原「体积来源列无法验证清单」已销案为有 |
| UP05 | UpdateDown · 外框 | 同 UP01；本态差异：进度块＋进度条＋`取消下载` 钮 | 同 UP01；进度为文字行，无 progressbar 元素（全 index.html 仅手机 ：227、验证码 ：275 有 role=progressbar） | 缺失 | 有：download.downloaded、total_bytes、state | 照原型改（见 UP06） |
| UP06 | UpdateDown · 进度与注 | 状态行 `正在下载安装包…`（Main:1436）；进度块左 `已下载` 右 `37.9 / 92.4 MB（41%）`（Main:1459）；进度条 aria `安装包下载进度`（Main:778）；注 `下载不影响报名计划，可以关掉设置继续用。`（Main:779）；钮 `取消下载`（Main:1449）；校验中 `下载完成，正在校验`＋`正在比对大小和 SHA-256…`＋钮 `校验中…` disabled（Main:1437/1459/1449） | 状态行与 verifying 行同字（update.js:21-37）；进度行 `已下载 A / B（P%）`（update.js:49，fmtBytes:2-7）；注同字（index.html:311，downloading 时显示 update.js:60）；钮 `取消`（index.html:312，非 `取消下载`） | 缺失＋文案 | 有：update_cancel（app.py:1797） | 照原型改（补进度条、钮改 `取消下载`） |
| UP07 | UpdateFail · 外框 | 同 UP01；本态差异：错误框 `.ph-err`（role=alert，红底，Main:307） | 同 UP01；红底错误样式未单列（素材未给对应类名） | 已一致 | — | 不动（文案见 UP08） |
| UP08 | UpdateFail · 文案与钮 | 红 `更新没有完成。`（Main:1441）；错误框 `下载内容的哈希校验没通过，已放弃并删掉临时文件。旧版本和你的数据都没动。`（Main:1123/1456）；钮 `重新下载`（btn-solid，Main:1451） | `更新没有完成。`＋result.text（update.js:21-37 failed 分支）；钮 `重试检查`（failed/error 分支）；`下载并安装` 在 available/failed 且有 installer 时出现（update.js:66） | 文案 | 有：update_download 回包 text | 照原型改（哈希失败专句、钮名 `重新下载`） |
| UP09 | UpdateLive · 外框 | 同 UP01；本态差异：常驻 `检查更新`（btn-line，Main:1446）＋演示下拉六项（Main:785，canDemo 才有） | 同 UP01；`检查更新` #btn-update-check（index.html:312）；演示控件无 | 已一致 | — | 不动；演示控件不做（沿用既定口径） |
| UP10 | UpdateLive · 发布页入口与启动交回关窗 | 底注 `打开发布页，看更新说明，或者手动下载完整包。`（`打开发布页` 为链接钮，Main:784）；`正在启动安装程序…`（钮 disabled `启动中…`）→`安装程序已启动。`（钮 `关闭本工具…`）＋提示 `先关闭本工具，再按向导完成安装。旧版本和你的数据在安装完成前都不会变。`（Main:782/1440）；`关闭本工具…` 弹关窗框并带一句 `要安装新版本，这次选“退出程序”。…`（Main:1873） | 常驻独立钮 `前往下载页` → open_latest_release（app.js:440-451；app.py:3571），失败 `发布页没能打开（系统浏览器可能被拦）。地址：`＋RELEASES_LATEST_URL（store.js:26）；launching 态优先后端下发 text、兜底固定文案（update.js:31-37）；`仍然启动安装程序`（busy 时，update.js:74）；`关闭本工具…` 出现（update.js:70、77）→ api("ask_window_close") 交回关窗对话框（app.js:438-439）；是否携带 closeWhy 未列 | 文案＋状态 | 有：open_latest_release（app.py:3571）、update_launch（app.py:1803）、ask_window_close（app.py:2759） | 照原型改或保留并说明；closeWhy 是否传达列无法验证清单 |
| UP11 | UpdateReady · 外框 | 同 UP01；本态差异：黄警示 `.ph-warn` 块（Main:781） | 同 UP01；busy 追加句写在进度行内（update.js:52-55），无独立黄警示块 | 结构 | 有：S.busy | 照原型改（见 UP12） |
| UP12 | UpdateReady · 文案与钮 | 绿 `安装包已通过大小和 SHA-256 校验。`（Main:1438）＋`检查时间 11-03 14:20`；黄警示 `报名计划还在运行。安装时要先关闭本工具，计划会停止，建议等这次计划结束再装。`；正文 `启动后按安装向导操作。工具不会自己退出或重启。`（Main:781）；钮 `仍然启动安装程序`（btn-solid，Main:1450） | ready_to_install `安装包已通过大小和 SHA-256 校验。`＋进度行 `已通过大小和 SHA-256 校验`，busy 追加 `。报名计划还在运行：安装要先关闭本工具，会中断计划`（update.js:52-55）；`仍然启动安装程序`（update.js:74）；无 `启动后按安装向导操作…` 句 | 文案 | — | 照原型改（警示独立成块、补向导句） |

## 三、引导组（画板 11-13）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| TR01 | 外框（3 画板共用） | 四块半透明遮罩板挖洞（rgba(17,29,38,.52)，Main:507-509）＋琥珀描边圈＋白卡 `.t-card` 宽 22rem（352px）圆角 12px（Main:510；定位常量 cw=352,ch=240，Main:1305）；卡头深色；无蒙层全遮 | `.tour` fixed inset:0 z-index:60（styles.css:663）；`.tour-mask` rgba(17,24,20,.55)（:665）；`.tour-spot` 琥珀 2px 描边（:666）；`.tour-card` width 340px、圆角 12px（:667）；非 `<dialog>`，卡片 role=dialog aria-modal=true tabindex=-1（index.html:336）；头部步数＋圆点（index.html:337） | 样式＋结构 | — | 照原型改（卡宽 352px、遮罩色）；挖洞实现方式需读 styles.css 全量再定 |
| TR02 | TourTable · 外框 | 同 TR01；第 1 点 now 琥珀；`上一步` disabled（first=true）；本步非 interactive（目标上有 `.t-block` 挡点击，Main:906） | 同 TR01；圆点 #tour-dots；三钮 `跳过引导`｜`上一步`｜`下一步`（index.html:341-344）；is-interactive 放行点击（styles.css:682-683）、no-target/is-bottom 落底部（:680/:684） | 已一致 | — | 不动 |
| TR03 | TourTable · 第 1 步文案 | `第 1/5 步`＋`这是活动时刻表`／`活动按开放时间排好。“预报名”等开放后自动提交，“立即报名”点开始后马上提交。上面可以搜索和筛选。`（Main:910/1257；原引 912 是引导卡脚部钮行，归 TR02） | TOUR_STEPS 第 1 步 target=list 同题同文，引号 `「预报名」`／`「立即报名」`（state/store.js:30-41）；渲染 `第 N/5 步`（views/tour.js:118）；静态残留 `第 1/6 步`（index.html:337） | 文案 | — | 照原型改引号（口径同 2026-11-07 设置抽屉对账表 DT04）；删 `1/6` 残留 |
| TR04 | TourPick · 外框 | 同 TR01；本步 interactive（block=false，目标行可点） | 同 TR01；interactive 遮罩只放行该行（views/tour.js:33-36 tourRowTarget 现找第一行可勾选活动；tourGuardClick :39-50＋document capture app.js:468） | 已一致 | — | 不动 |
| TR05 | TourPick · 第 2 步文案与换卡态 | `勾选想报的活动`／`点这一行试试。勾选只是加入计划，不会开始报名；举办时间重叠的活动不能同时选。`（Main:1258）；勾选后卡换 `加入计划了`／`右边的清单多了一场，报名还没有开始。想取消，再点一次这一行。`（Main:1302） | 第 2 步 target=row 同题同文、两侧均无引号（store.js:33-34 与 Main:1258 逐字相同，原「引号差」删除）；勾选后换卡态代码无实现（views/tour.js 全文无 `加入计划了`，grep 全 local/ 零命中） | 缺失 | — | 文案不动；换卡态照原型补（原列无法验证清单，已销案为缺失） |
| TR06 | TourRun · 外框 | 同 TR01；非 interactive | 同 TR01 | 已一致 | — | 不动 |
| TR07 | TourRun · 第 4 步文案 | `开始以后看这里`／`这里显示倒计时，下面是每场进度。可以最小化窗口，但不要关闭工具或让电脑睡眠。看到“待核对”时，到学校活动页确认。`（Main:1260）；`下一步` 非 `完成`（Main:1302） | 第 4 步 target=run 同文（`「待核对」` 引号差，store.js:30-41）；最后一步钮变 `完成` 的处理素材未列 | 文案 | — | 照原型改引号 |
| TR08 | 第 3、5 步（无画板） | 第 5 步 `出问题先看顶部`／`…想再看一遍引导，点“帮助”。`（Main:1261）；第 3 步 `核对计划，再点开始`／`选好的活动都列在这里，可以逐场移除，也能修改尝试时长。开始不了时，按钮下面会写还差什么。`（Main:1259）——5 步全表在原型 tourSteps（Main:1255-1263），仅无画板 | 代码共 5 步：第 3 步 target=select 同题同文、与 Main:1259 逐字相同（store.js:35-36，原无法验证 #1 销案为一致）；第 5 步 target=login 同原型（`「帮助」` 引号差，store.js:30-41） | 文案 | — | 需用户定是否补画板（原「多出」撤销：原型本含第 3/5 步，属画板未覆盖非代码多出）；第 5 步引号照原型改 |
| TR09 | 引导行为链 | 素材只给结构与焦点（卡 tabindex=-1 出现即聚焦，Main:1812-1815） | 自动开始三条件与登记点（views/tour.js:7-30；app.js:56/125；controllers/refresh.js:416）；busy 暂停 tourPauseNow（views/login.js:105；tour.js:101-104），恢复仅条款让位链调用（controllers/terms.js:137-141）；Esc=跳过（app.js:491；tour.js:95-99）、Tab 循环（tour.js:68-81）、背景快捷键不穿透（app.js:493-499）；完成/跳过落盘（tour.js:92-98；controllers/prefs.js:34-41）；重看引导（views/help.js:43-67） | 状态 | 有：save_prefs（app.py:3603） | 行为需专项测试，本表只登记不判定 |

## 四、首次使用（画板 14）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| FU01 | 外框（独立同意模态） | 模态 `.dlg` 38rem（Main:800）；深色标题栏、无 X；正文 6 条 `.pts` 列表（分隔线）；脚部勾选框居左＋`暂不使用`（btn-line）｜`同意并继续`（btn-solid，disabled 直到勾选，Main:2484） | 无独立首启模态；首启体验三件拼成：boot 首跑（firstRun→welcome_seen；条款锁定时记 deferredIntro、同意后 runDeferredIntro 只续播一次；否则 showHelp 或 requestAutoTour，app.js:46-57；controllers/terms.js:145-154）＋计划栏 `首次使用` 标签（views/plan-panel.js:16-20）＋帮助弹窗（index.html:190）；同意职能由 `#dlg-terms` 承担 | 缺失 | 有：accept_terms（app.py:3610）、save_prefs | 需用户定（新建首启框，还是维持 `#dlg-terms` 承担同意职能，见 TM01） |
| FU02 | 六条要点 | `非官方工具`／`工具会直接调用学校接口`／`保存账号后会自动登录`／`风险由你判断`／`数据只在这台电脑`／`完整条款`（Main:799-807） | `#dlg-terms` 条款要点 5 条：`非官方个人作品`／`数据与对外通信`／`只做重复操作自动化`／`你的义务`／`责任限制`（index.html:131-135）＋离线句 `本份条款可离线阅读：全文就在本窗口内，不依赖网络或仓库文档。`（index.html:137） | 文案＋结构 | — | 需用户定（以条款 r5 正文为准还是照原型六条重排；内容覆盖面相近） |
| FU03 | 首启背景空态 | 右栏标签 `首次使用`、卡题 `登录后开始`、副题 `活动会在登录完成后自动加载。`（Main:2324）；LED／列表空态／日志／胶囊（Main:2314/2415/1103/2400；原引 2408 是登录弹卡 pending 行） | 计划栏标签、卡题、副题同字（plan-panel.js:16-20）；LED、列表空态、日志、胶囊属 L2 其他组素材范围，本表不对账 | 已一致 | — | 不动（已对账部分） |

## 五、条款组（画板 15-20）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| TM01 | 外框（TermsDoc／TermsPrivacy 共用） | 全屏 `.scrim.tscrim` z-9＋`.dlg.tdoc` min(60rem)×min(46rem)（Main:386-387）；头部深色＋右 X（aria `关闭条款`，Main:887）；头下页签行＋右侧注 `标着“本版新增”的是这次的改动`（Main:888）；正文左右分栏：左 11rem 章节导航＋右滚动（Main:394）；脚部 consent＝勾选＋`暂不使用`＋`同意并继续`，view＝`Esc 关闭`＋`关闭`（Main:894-895） | `<dialog class="dlg dlg-terms">`（index.html:109）；宽 min(680px, calc(100vw - 32px))（styles.css:470-475，头部站牌深色＋琥珀短线）；右上 X 在 form method=dialog 里，aria `暂不使用并关闭条款`（index.html:112）；章节导航有：`#terms-toc`（index.html:139）经 paintTermsToc（views/terms.js:132-145）渲染、左栏 10rem sticky（styles.css:950-952），全文视图显示、要点视图与 ≤719px 隐藏——与原型 11rem 常驻分栏是展示范围差，非「无」；无页签右侧注；页签 `用户协议`／`隐私政策`／`MIT 许可证`（index.html:141）；脚部（index.html:185）：勾选行＋说明＋`关闭`（只读态）／`暂不使用`／`我已阅读并同意`（初始 disabled）＋Esc 提示（index.html:181） | 结构＋文案 | — | 需用户定（全屏与章节导航展示范围——代码导航仅全文视图显示，原型 11rem 常驻）；X aria、`同意并继续`、页签名照原型改 |
| TM02 | TermsDoc · 标题与元信息 | 标题 `使用条款与隐私`（Main:887）；元信息 `版本 2026-11-03-r4（原型草案）。你之前同意的是 2026-10-27-r3，新版还没同意。`（Main:1571） | 标题 `使用条款与隐私告知`（index.html:111）；副行 `本份《用户协议》与《隐私政策》 2026-11-07-r5；程序要求版本 —。同意后才能登录、查看活动列表与开始报名计划。`（index.html:119；r5 静态 #dlg-terms-document-version，#dlg-terms-version=S.terms.version，unknown→`尚未确认`，views/terms.js:6） | 文案 | 有：terms 快照（bootstrap app.py:923） | 版本示意值双轨列 NEEDS-HUMAN 2；「你之前同意的是」在代码移到更新区块（TM08） |
| TM03 | TermsDoc · 页签与全文 | 三页签 `用户协议`／`隐私政策`／`开源许可`（Main:888）；章节导航 a1-a7（Main:1544-1550）；正文条目带 `本版新增` 徽章 `.td-new`（Main:886-892） | 三页签 `用户协议`／`隐私政策`／`MIT 许可证`（index.html:141）；协议与隐私全文内嵌（index.html:143-164，与 docs 逐字同步契约）；MIT 页签懒加载三态（index.html:166-175；views/terms.js:150-175；controllers/terms.js:358-377；app.py:3584）；节标标新 data-new（TERMS_NEW_SECTIONS agreement=["1.","2.","3.","8."]，views/terms.js:98-129） | 文案＋结构＋状态 | 有：get_license_text（app.py:3584） | 需用户定（章节导航）；页签名 `开源许可` 照原型改；懒加载三态列 NEEDS-HUMAN 6 |
| TM04 | TermsDoc · 脚部与拒绝语义 | consent 勾选 `我已阅读并同意《用户协议》和《隐私政策》`＋`暂不使用`＋`同意并继续`（Main:894）；view 脚部 `Esc 关闭`＋`关闭`（Main:895） | 勾选行 `我已阅读并同意《用户协议》与《隐私政策》`（index.html:185，「和」→「与」）；Esc 提示动态三态 `正在保存…`／`Esc 关闭`（views/terms.js:58-61）；Esc／X／`暂不使用` 统一拒绝语义、保存中拦截、程序性关闭跳过（app.js:276-294）；只读态合并行 `已同意《用户协议》与《隐私政策》 <b>版本</b>（… 同意）；更新后会再次展示并要求重新同意。`（views/terms.js:223-247） | 文案＋状态 | 有：accept_terms（app.py:3610；controllers/terms.js:202 回执自证三字段） | 照原型改按钮名与连接词；`正在保存…`／`保存结果未确认`／只读三态列 NEEDS-HUMAN 6 |
| TM05 | TermsPrivacy · 外框与隐私全文 | 同 TM01；本态差异：页签 `隐私政策` on、showNew=false 无徽章、脚部只读 `Esc 关闭`＋`关闭`（Main:895）；章节导航 p1-p4（Main:1553-1556）；开源许可页签 l1-l2（Main:1558-1560） | 同一 `#dlg-terms` 隐私页签 switchTermsDoc("privacy")（views/terms.js:67-88）；章节导航同 TM01（全文视图显示）；只读态为合并行＋`关闭`（views/terms.js:223-247）；doc-link 点开切对应页签、preventDefault 不翻转勾选（app.js:243-253）；MIT 页签懒加载三态（TM03 已列） | 结构＋状态 | — | 需用户定（章节导航展示范围，同 TM01）；只读脚部形态照原型改或保留并说明 |
| TM06 | TermsOff · 横幅 | 顶部警示横幅：`使用条款更新了，还没有同意新版。`＋`同意后才能登录、查看活动和开始报名计划。`＋钮 `查看条款`（Main:2138 termsPrev 非空分支）；登录胶囊 `等同意条款`（Main:2400） | 横幅 `还没有同意使用条款。`＋declined 分支 `登录、活动列表和报名计划保持停用。`／未拒绝分支 `同意后才能登录、查看活动列表与开始报名计划。`＋钮 `查看条款`（views/plan-panel.js:1354-1358；data-act="terms-open" → openTerms("banner")，app.js:385-391）；计划栏标签、列表空态、开始门禁另有三处呈现（plan-panel.js:39-44；views/list.js:326-331/392；plan-panel.js:322/427-428），原型均有对应物（「已暂停」head Main:2334-2337、列表 lnote Main:597/2491、开始门禁 blocker Main:2125＋checks Main:2465），非代码多出 | 文案 | 有：terms 快照 | 需用户定（横幅是否区分「更新未同意」）；门禁等呈现两侧均有对应物、代码更细，保留并说明（原「多出」撤销） |
| TM07 | TermsUnknown · 横幅 | 横幅 `条款状态没能确认。`＋`读不到你同意过哪一版。登录、活动列表和报名计划暂时停用，打开条款重新确认后恢复。`＋钮 `查看条款`（Main:2138）；日志 `[!] 没读到条款同意记录，学校相关操作已暂停`（Main:1180）；胶囊 `等确认条款` | markTermsUnknown（controllers/terms.js:38-48；bootstrap 失败、缺 terms、版本空、结构非法触发，terms.js:53-61 注释）；横幅 `条款状态没能确认。登录、活动列表和报名计划暂时停用；点「查看条款」打开全文并重新确认，确认成功才会恢复。`（views/plan-panel.js:1350-1352）；弹窗内说明 `本机没读到条款状态，登录、列表和报名计划已停用。下面的完整条款仍可阅读；点「我已阅读并同意」会按程序的当前条款版本记录。`（controllers/terms.js:113-116）；版本 `尚未确认`（views/terms.js:6） | 文案 | — | 照原型改（横幅正文拆两句）；日志行列无法验证清单 |
| TM08 | TermsUpdate · 外框 | 独立模态 `.dlg.sm` 内联覆盖宽 min(32rem)（Main:878）；深色标题栏、无 X；脚部 `看完整条款`（无底钮）｜弹性空隙｜`暂不同意`（btn-line）｜`同意新版条款`（btn-solid，焦点自动落此，Main:1828） | 无独立模态：`#dlg-terms` 内嵌区块 `#terms-update`（index.html:120-124）；触发 termsUpdateMode＝acceptedVersion!==version 且非 unknown（views/terms.js:103-106）；脚部沿用 `#dlg-terms` 标准三钮 | 结构 | 有：terms_declined_version 清/写（terms.js:247、303、348） | 需用户定（独立模态 vs 内嵌区块，见 NEEDS-HUMAN 1） |
| TM09 | TermsUpdate · 副题与变更清单 | 副题 `新版 2026-11-03-r4，你之前同意的是 2026-10-27-r3。同意新版后才能继续登录和报名。`（Main:879）；`这次主要改了：`＋6 条变更各带琥珀徽章 `新增`（tuItems，Main:2487）；注 `不同意也可以继续用帮助和设置，但登录、自动登录、活动列表和报名计划会停用。已保存的账号密码和登录信息不会删除。` | `使用条款更新了`／`你之前同意的是 —。这一版改了下面几处，正文里标「本版新增」的就是这些地方：`（#terms-update-from 动态旧版号，index.html:120-124）＋TERMS_CHANGES 4 条（views/terms.js:92-97）＋节标 data-new；无独立注句 | 文案 | — | 变更 6 条对 4 条且内容分属不同版本节奏（原型 r4、代码 r5），列 NEEDS-HUMAN 2 与 6 |
| TM10 | TermsWithdraw · 外框与条款行 | 设置抽屉「条款与隐私」节（Main:788-790）＋节内嵌红色确认条 `.ph-confirm`（bad-tint，Main:340）；条款行 `你在 11-03 09:12 同意了 2026-11-03-r4 版。用户协议、隐私政策和开源许可的全文都可以在这里查看。`＋句内链接钮 `撤回同意`（termsWAsk 时隐藏，Main:2490/2492） | 同承载（index.html:318-321）：行静态 `当前条款版本 —；同意记录保存在本机设置里。`＋动态 `你在 <时间> 同意了这一版。`／未同意 `还没有同意这一版：登录、登录检查、自动登录、刷新活动和开始计划都已停用。`（views/settings.js:72-87）；`撤回同意` 是独立线框钮（accepted 才显示，busy 禁用，title `计划运行中不能撤回，先停止计划`） | 结构＋文案 | 有：withdraw_terms（app.py:3636） | 照原型改（句式与链接钮形态） |
| TM11 | TermsWithdraw · 确认条 | 确认条 `撤回后，登录、自动登录、活动列表和报名计划会停用。已保存的账号密码和登录信息不会删除。要删除账号密码，在“登录恢复”里清除。`＋`先不撤回`（btn-line）｜`确认撤回`（btn-stop 红色实心）；运行中 `报名计划运行中不能撤回同意，先停止计划。`（Main:789/2490） | busy 原因行同字（index.html:323）；确认块 `撤回后，登录、登录检查、自动登录、刷新活动和开始计划都会停用；保存的账号密码和登录信息不会删除，重新同意就能继续用。`＋`先不撤回`｜`确认撤回`（btn-solid，index.html:325-326）；点撤回只展开确认块（views/settings.js:326-336），确认才 api("withdraw_terms")（settings.js:89-109），关抽屉强制收起（settings.js:45-46） | 文案＋样式 | 有：withdraw_terms（app.py:3636） | 照原型改（btn-stop 红钮；补 `要删除账号密码，在“登录恢复”里清除` 指引句） |

## 六、帮助快捷键（画板 21）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| HK01 | 外框 | 模态 `.dlg` 38rem（Main:796）；深色标题栏；无 X | `<dialog class="dlg dlg-help">`（index.html:188）；宽 min(680px, calc(100vw - 32px))（styles.css:422）；头部站牌深色 .help-head（styles.css:424-428）；右上 X aria `关闭帮助`（index.html:191，form method=dialog） | 样式＋多出 | — | 需用户定（X 为代码既有便利；原型对话框默认无 X） |
| HK02 | 三步说明 | `确认登录`／`选活动并开始`／`看结果` 三条（Main:796；第 2 条 `再点“开始报名计划”。`）；无分组标题 | `#help-steps`（index.html:196）fillHelp（views/help.js:2-7，DEFAULT_HELP store.js:4-14 或 bootstrap.info.help app.js:16）；逐字同，第 2 条引号 `「开始报名计划」`；区块前另有 h3 `三步使用说明`（index.html:195） | 文案＋多出 | — | 照原型改引号；分组标题保留并说明 |
| HK03 | 键盘快捷键表 | 分组标题 `键盘快捷键`（h3）＋dl 五行 `F5`／`Ctrl + F`／`Esc`／`Tab`／`空格`（同在 Main:796 单行内；Main:439/443 是 .keys／.kbd 样式行，原引作废） | h3 `键盘快捷键`（index.html:199）＋dl.keys 五行逐字同（index.html:200） | 已一致 | — | 不动 |
| HK04 | 脚部 | `重看引导`（btn-line；running 态 `计划结束后可重看引导` 且 disabled，Main:2477）｜`知道了`（btn-solid） | `#btn-help-tour`（busy 时文案/标题改 `计划结束后可重看引导`，views/help.js:59-67）＋`知道了`（form method=dialog，index.html:203）；重看引导 → replayTourFrom（help.js:43-56；app.js:432）；showHelp 写 welcome_seen（help.js:9-16）；条款打开先关帮助（views/terms.js:276-280） | 已一致 | 有：save_prefs（welcome_seen） | 不动 |

## 七、迁移组（画板 22-23）

| 编号 | 区域 | 原型 | 现状 | 差距类型 | 后端信号 | 建议 |
|---|---|---|---|---|---|---|
| MG01 | Migrated | 信息横幅 `.banner.note`：`已把旧版本的数据搬到新位置。`＋`登录、设置和运行记录都在，不用重新登录。位置在设置的“本机数据”里。`＋钮 `知道了`（Main:2146）；日志 `14:20:01  已把 3 个旧数据文件搬到新的数据目录`（Main:1182）；设置「本机数据」小节指引可达（Main:787） | 无对应实现（grep `Migrated`、`MigrateFail` 全 local/ 零命中）；迁移成功只 print stderr `[i] 已把 %d 个旧数据文件搬到统一数据目录：%s`（runtime_paths.py:88-90），不经 addLog、无 onBackend 事件、无 UI 呈现 | 缺失 | 有：_migrate_legacy_data（runtime_paths.py:57-90，只补缺失、临时文件＋os.replace 原子落位） | 需后端先补（迁移结果进运行记录或事件）＋照原型改（横幅） |
| MG02 | MigrateFail | 警示横幅：`旧版本的登录信息没能搬过来。`＋`设置和运行记录已经搬好；重新登录一次就行，旧文件还留在原来的位置。`＋钮 `登录`（Main:2147）；日志 `14:20:01  [!] 旧版本的登录信息没能搬过来，其他数据已搬好`（Main:1183）；整站未登录空态，后续接登录框 | 无对应实现；失败只 stderr `[!] 旧登录数据迁移失败（不影响启动，可手动拷贝）：%s`（runtime_paths.py:91-93），不阻断启动、不进运行记录 | 缺失 | — | 同 MG01 |

---

## 差异统计

按行计，组合行（如「文案＋状态」）在每个标注的类型下各计一次，所以次数大于行数；全表 55 行（修订后，原 54 行／计次 76）。

| 类型 | 次数 | 主要落点 |
|---|---|---|
| 文案 | 27 | 关窗组文案整组（含勾选框句 CW14）、更新组 confirm/失败/就绪句、引导第 5 步引号、条款组标题脚部、迁移横幅（缺实现） |
| 结构 | 13 | 关窗外框与卡序、更新钮组与黄警示块、引导浮层、FirstUse 拼装、条款全屏与章节导航展示范围、TermsUpdate 内嵌区块、撤回链接钮 |
| 缺失 | 9 | CloseHidden 整块（2 行）、更新进度条与新版本块（3 行）、FirstUse 独立模态、引导勾选换卡态（TR05）、Migrated／MigrateFail 整块（2 行） |
| 多出 | 2 | 帮助关闭 X 与分组标题（HK01/HK02） |
| 状态 | 9 | 关窗标题随态、Esc 语义、空闲退出无确认、引导行为链、条款懒加载与只读态、更新交回关窗 |
| 样式 | 4 | 关窗深色标题栏、引导卡宽遮罩、撤回确认红钮、帮助宽度 |
| 已一致 | 11 | 关窗框、更新抽屉载体与三处外框、引导交互规则、首启空态（已对账部分）、帮助快捷键表与脚部 |

## 需用户定（NEEDS-HUMAN）

1. **原型内矛盾：TermsUpdate 与条款全文框叠层**。`tuFull`/`openTermsDoc`（Main:2486）只设 `td` 不关 `tuOpen`，两框叠加且 tscrim（z-9）盖住 tu 框（z-8），关掉全文框后 tu 框还在。实现若按单模态处理需产品裁决。代码现状用 `#dlg-terms` 内嵌区块（TM08），叠层问题自然消失，但「独立 tu 框 vs 内嵌区块」的结构取舍仍需用户定。
2. **示意值双轨**。条款版本：原型 `2026-11-03-r4`（Main:1539）／旧版 `2026-10-27-r3`（Main:1065/1098）对 代码 `2026-11-07-r5`（index.html:119，与 docs 逐字同步契约）；程序版本：原型 `1.2.0`／新版本 `1.3.0`（Main:772/775）对 代码读真实版本（app.js:18）；同意时间：原型 init 默认 `11-03 09:12`（Main:1058）而 accept 后写 `11-03 14:20`（Main:1879）。验收比对需明确取哪一组。
3. **`termsFocus` 不在原型 init 初始 state 表**（Main:1058 无此键，1099 直接赋值）；依赖它的居中滚动（Main:1784）在严格实现下需确认初始 undefined 不报错。
4. **`upGuard` 同不在初始 state 表**（Main:1058 无键，1856 赋值）；0.8 秒按钮防误触（Main:1854）是否纳入验收需人工确认。代码已有对应实现（UPDATE_GUARD_MS=800，update.js:82-95），主要影响原型验收口径。
5. **CloseIdle 入口是构造态**。`tray=false` 由原型 init 直接构造（Main:1140）；真实交互 winClose（Main:1948-1953）在无计划时按偏好退出或弹问，画板值以快照为准。另代码侧空闲时点 `直接退出` 立即提交、无二次确认（window.js:113-125 else 分支），原型未画该分支的后果。
6. **反向差异（代码有、画板没有；需确认是否补画板）**。更新组：confirm／preview／no_installer／unavailable／launching 等态在代码与原型状态机里都有（Main:776/785、1426-1442；update.js:21-37、66-77），属画板清单不全而非代码超出原型；条款组：`正在保存…`／`保存结果未确认`／只读查看三态与 MIT 懒加载（views/terms.js:13-61、163-336；index.html:141、166-175）为代码多出、原型未画；引导组：代码 5 步对 画板 3 块（第 3、5 步无画板）。
7. **views/terms.js:349 死引用**。`#btn-help-terms-view` 已不存在于 index.html（帮助内的查看条款按钮已搬去设置 #btn-help-terms），grep 全量仅此一处（修订补记：全仓另有 local/tests/test_ui_contract.py:2452 的反向断言 `assertNotIn('id="btn-help-terms-view"', …)`——测试恰在守该 id 不得存在，源码命中仍仅此一处）；help 来源的焦点回还总是落 #btn-help 兜底。属功能搬移遗留，修复要改 views/terms.js（本表只记不改）。
8. **TermsOff 横幅标题句**。原型按「更新未同意」措辞（`使用条款更新了，还没有同意新版。`），代码统一为 `还没有同意使用条款。`（TM06）——横幅是否要区分更新场景需用户定。

## 无法验证清单

1. 【已销案 2026-11-08 对抗审阅】原型引导第 3 步的逐字全文未抄录于素材（素材只引 1257/1258/1260/1261 四处）——补验：Main:1259 与 store.js:35-36 逐字相同，结论「一致」，无差异（TR08 已改）。
2. 【已销案 2026-11-08 对抗审阅】TourPick 勾选后换卡态（`加入计划了`，Main:1302）：代码侧对应行为素材未列——补验：views/tour.js 全文无该实现、grep 全 local/「加入计划」零命中，结论「代码缺失」（TR05 已改判缺失）。
3. 【后半已销案 2026-11-08 对抗审阅】更新 launching 态兜底文案：update_check.py:221/227/230 三类安装器缺失文案实存，与原型 `先关闭本工具，再按向导完成安装。…`（Main:782/1440）的逐句比对仍缺，前半保留；closeWhy——app.py:2776-2777 载荷（plan_running/default_action/tray_ok/phone_running/phone_live）无该字段，代码确实不携带（UP10）。
4. 【已销案 2026-11-08 对抗审阅】UpdateAvail 确认步的体积说明：原型 `92.4 MB` 是画板示意、代码 confirm 态只有 `发现新版本 X。` 不变；体积字段已核实为「有」——installer 带 `bytes`（update_check.py:100/106，UP04 已改记）。
5. 【已销案 2026-11-08 对抗审阅】条款未知态的日志行（原型 `[!] 没读到条款同意记录，学校相关操作已暂停`，Main:1180）：代码侧对应 addLog 句素材未列——补验：全 UI grep 零命中，结论「代码缺失」（TM07 横幅行维持，日志不另记）。
6. CloseLive 画板所列计划面板运行态文案（`可以最小化窗口，但不要关闭工具或让电脑睡眠。` 等，Main:661/665）：属计划面板范围，本批素材未含代码侧对照（CW13）。
7. 样式细节（深色标题栏、红底块、btn-stop 用色）按素材转述加个别抽查（如 `确认撤回` btn-solid，index.html:326 实测），未逐一打开 styles.css 全量核对。
8. 行号漂移：index.html、styles.css、app.js、state/store.js 带他人在途改动，本报告行号为 2026-11-08 磁盘现状，后续会漂移；原型行号全部按工作区版（2498 行）转引素材，未逐条回开原型复核（素材已做薄壳核对与复现标注）。

## 抽查复核记录

任务要求 grep 抽查 ≥10 处，实际抽查 36 处（含 4 个区间）：index.html:396/398/399/401/402/406-420/421/337/311/312/333/109/111/119/143-164/185/196-203/318-327；styles.css:391/667/923/968-969/970-972（区间转述核对 ：391/:667/:923 实测）；state/store.js:26/30；views/terms.js:92/98/349；views/update.js:74/95；controllers/window.js:40-66；views/plan-panel.js:16-20；app.js:46-57；app.py:2759/2836；runtime_paths.py:88-93。结论：**31 处与素材一致，1 处修正**——

- 修正：素材记迁移成功/失败 stderr 为 `已把 %d 个旧数据文件搬到统一数据目录：%s`／`旧登录数据迁移失败（不影响启动，可手动拷贝）：%s`（runtime_paths.py:88-90、91-93）。实测两处 print 带 `[i] `／`[!] ` 前缀（`[i] 已把 …`、`[!] 旧登录数据迁移失败…`）。行号无误，本表 MG01/MG02 已按实测抄录。

## 修订记录（对抗审阅 2026-11-08）

依据 `design/evidence/2026-11-08/ADVERSARIAL-L2.md`（对抗双方 `<过程留证>/adv-L2-a.md` 机械核验、`<过程留证>/adv-L2-b.md` 实质反证，互盲；合并人对全部争议点按素材复核后定档）。本次修订只动本报告文字，未改任何代码与原型。三档结果：54 行对账，站得住 46、部分站不住 8（CW06、UP03、UP04、TR05、TR08、TM01、TM05、TM06）、推翻 0、红牌 0。

- **行号与归属修正（12 项＋范围声明补漏）**：TM08 触发逻辑归属 views/terms.js:103-106；TM06/TM07 的 plan-panel.js 行号漂移，现盘分别为 1354-1358／1350-1352；HK03 内容在 Main:796（439/443 是样式行）；HK02 h3 在 index.html:195；TR03 去 912；CW05 补定义行 1715；FU03 列表空态改 2415（2408 是登录弹卡 pending）；TM04 补 controllers/ 前缀（terms.js:202）；UP04 补 controllers/ 前缀（update.js:75-81/83-108）；NEEDS-HUMAN 2 补旧版行号 Main:1065/1098；「仅此一处」补 local/tests/test_ui_contract.py:2452 反向断言；范围声明补 views/plan-panel.js、views/list.js 为在途修改。另记法说明两条不改文：`min(30rem,100%)` 实为 `min(30rem, 100%)`、`tray=false` 实为 `s.tray = false;`（空白/记法级）。
- **实质改判（8 行）**：CW06 补全局 Esc 链副作用（app.js:516-528，空闲有勾选时 clearSelection 连带触发）；UP03 时间分隔符降档（views/update.js:42 zh-CN 在 Chromium 产出斜杠，原型为连字符，「已同构，不动」撤销）；UP04 体积字段销案为「有：installer.bytes（update_check.py:100/106）」；TR05 删「引号差」（store.js:33-34 与 Main:1258 逐字相同、两侧均无引号）、换卡态改判缺失；TR08 撤销「多出」（原型 tourSteps 本含第 3/5 步，Main:1259/1261，属画板未覆盖非代码多出）；TM06 撤销「多出」（门禁呈现原型有对应物：Main:2334-2337/597/2491/2125/2465）；TM01/TM05 撤销「无左侧章节导航」（index.html:139 `#terms-toc` ＋ styles.css:950-952 左栏 10rem，全文视图显示，与原型 11rem 常驻为展示范围差）；新增 CW14 勾选框文案差（Main:820 `以后都这样，不再询问` 对 index.html:421 `以后都这样，别再问我`）。
- **销案（无法验证 5 项）**：#1 第 3 步逐字＝一致（Main:1259 对 store.js:35-36）；#2 换卡态＝缺失（views/tour.js 无实现，grep 零命中）；#3 后半 closeWhy＝代码不携带（app.py:2776-2777 载荷无该字段）；#4 体积字段＝有（update_check.py:100/106）；#5 条款日志＝缺失（全 UI grep 零命中）。#3 前半（update_check.py:221/227/230 三类文案对原型句）、#6、#7、#8 保留。
- **差异统计**：修订前 54 行／计次 76（文案 26、结构 13、缺失 8、多出 4、状态 10、样式 4、已一致 11）；修订后 55 行／计次 75（文案 27、结构 13、缺失 9、多出 2、状态 9、样式 4、已一致 11）。红牌 0、推翻 0。

## 执行记录（20261108-c3-dialogs）

计划 `20261108-c3-dialogs` 的 8 个实现任务落盘后，按 55 行逐条核对实现（2026-11-08；命令在仓库根执行，证据均为 grep / 契约测试，未改原表）。终态类型：已改、已一致、保留并说明、已由他人做完、本计划不做。

| 编号 | 终态 | 核对说明 |
|---|---|---|
| CW01 | 已改 | 深色点阵标题栏＋琥珀左线、无 ×、三卡竖排；勾选框移进脚部居左 |
| CW02 | 已改 | 标题/副题随计划状态三态切换（运行、空闲、确认步） |
| CW03 | 已改 | 利害清单两行；场次数字取 BE1 `waiting_count` / `next_batch_at` |
| CW04 | 已改 | 卡序「最小化→隐藏→退出」，正文逐字；手机断开句按 `phone_running` 动态拼 |
| CW05 | 已改 | 隐藏禁用句「现在叫不回来：托盘图标没建起来，手机也没连着，所以不能隐藏。」 |
| CW06 | 已改 | Esc 在 dialog 捕获并阻断全局链；确认步 Esc 回选择步 |
| CW07 | 已改 | 确认步脚部「返回」｜「停止计划并退出」（红色实心 btn-stop） |
| CW08 | 已改 | 确认正文补「已经成功的报名不受影响」；确认后才 submit exit |
| CW09 | 已改（按决策） | 模拟桌面为原型演示包装，不做；隐藏成功改为托盘气泡一次（BE2） |
| CW10 | 已改（按决策） | 气泡标题「窗口已隐藏，工具在后台运行」＋正文照决策第 3 条；`原型演示：` 小字与静态时钟不做 |
| CW11 | 已一致 | 空闲不渲染利害清单、隐藏推荐徽章、退出无二次确认；未改 |
| CW12 | 已改 | 空闲标题/副题/卡文；退出卡「登录状态会保留，下次打开不用重新登录。」 |
| CW13 | 已一致 | 窗口 chrome 属系统；保留并说明，未改 |
| CW14 | 已改 | 勾选框「以后都这样，不再询问」 |
| UP01 | 已改 | 每个状态只露一枚主钮；流程钮出现时收起「检查更新」 |
| UP02 | 已一致 | 设置抽屉载体与标题行位置未动 |
| UP03 | 已改 | 检查时间自拼 `MM-DD HH:mm`（连字符），不靠 `toLocaleString` |
| UP04 | 已改 | `available` 新版本块＋`confirm` 问句；体积取 `installer.bytes`，无值降级 |
| UP05 | 已改 | 进度块＋`role="progressbar"` |
| UP06 | 已改 | 左「已下载」右「X / Y MB（N%）」、aria「安装包下载进度」、按钮「取消下载」、校验中「校验中…」 |
| UP07 | 已一致 | 错误框 `role=alert` 红底规则未动 |
| UP08 | 已改 | `error_code=hash_mismatch` 用哈希失败专句；`failed` 钮「重新下载」；`error` 保留「重试检查」（检查失败没有安装包可重下） |
| UP09 | 已一致 | 常驻「检查更新」未动；演示下拉不做（沿用既定口径） |
| UP10 | 已改 | 底注「打开发布页」为句内链接钮；`closeWhy` 仍不携带，无法验证 #3 前半保留 |
| UP11 | 已改 | 黄警示独立成 `.ph-warn` 块，不再塞进进度行 |
| UP12 | 已改 | 警示句＋「启动后按安装向导操作。工具不会自己退出或重启。」；计划运行中「仍然启动安装程序」 |
| TR01 | 已改 | 卡宽 352px、遮罩 `rgba(17,29,38,.52)`；挖洞用 `.tour-spot` 9999px 外扩阴影，视觉等价 |
| TR02 | 已一致 | 首点琥珀、上一步 disabled、三钮结构未动 |
| TR03 | 已改 | 第 1 步弯引号；静态「第 1/6 步」已删 |
| TR04 | 已一致 | interactive 放行与守点规则未动 |
| TR05 | 已改 | 勾选高亮行后换卡「加入计划了」，再点换回 |
| TR06 | 已一致 | 第 4 步非 interactive 未动 |
| TR07 | 已改 | 第 4 步「待核对」弯引号 |
| TR08 | 已改 | 第 5 步「帮助」弯引号；第 3 步原已一致 |
| TR09 | 保留并说明 | 七项行为链（自动开始、暂停、Esc、Tab、背景隔离、落盘、重看）核对全部在位，未改 |
| FU01 | 已改 | `#dlg-terms-intro` 38rem、无 ×、六条 `.pts`、勾选＋「暂不使用」｜「同意并继续」 |
| FU02 | 已改 | 六条按 r5 改写；改写清单待用户定稿 |
| FU03 | 已一致 | 首启空态标签/卡题/副题未动 |
| TM01 | 已改 | `.tdoc` 960×736、深色头、× aria「关闭条款」、三页签＋右侧注、章节导航宽档常显 |
| TM02 | 已改 | 标题「使用条款与隐私」；元信息按真实版本与同意状态拼 |
| TM03 | 已改 | 页签「开源许可」；章节导航与「本版新增」节标 |
| TM04 | 已改 | 勾选「我已阅读并同意《用户协议》和《隐私政策》」＋「暂不使用」「同意并继续」；只读「关闭」 |
| TM05 | 已改 | 隐私页签与只读脚部 |
| TM06 | 已改 | 更新未同意「使用条款更新了，还没有同意新版。」与从没同意两句分流 |
| TM07 | 已改 | 未知横幅拆标题＋两句；日志「[!] 没读到条款同意记录，学校相关操作已暂停」只写一次 |
| TM08 | 已改 | `#dlg-terms-update` 32rem 独立模态、无 ×、脚部三钮、焦点落同意钮 |
| TM09 | 已改 | 变更清单用 r5 内容＋原型版式（每条「新增」徽章） |
| TM10 | 已改 | 设置条款行句式＋句内链接钮「撤回同意」，确认条展开时隐藏 |
| TM11 | 已改 | 确认条三句（含「登录恢复」指引）＋「确认撤回」红色实心；运行中原因句 |
| HK01 | 已由他人做完 | 22427fd 删除 ×；8287d27 重做头部与宽度，本计划未再改 |
| HK02 | 已改 | 第 2 条引号改弯引号；分组标题已由他人做完 |
| HK03 | 已一致 | 快捷键表逐字同，未改 |
| HK04 | 已一致 | 页脚两钮与运行中禁用逻辑未改 |
| MG01 | 已改 | BE3 迁移记录＋`bootstrap.migration`；note 横幅「已把旧版本的数据搬到新位置。」＋「知道了」；运行记录写真实 `moved` |
| MG02 | 已改 | `login_failed` 警示横幅「旧版本的登录信息没能搬过来。」＋「登录」；运行记录「[!] 旧版本的登录信息没能搬过来，其他数据已搬好」 |

**本计划不做**：原型演示包装——UpdateLive 的演示下拉、CloseHidden 的模拟桌面与静态时钟。产品形态按决策：隐藏成功弹一次托盘气泡。

**终态统计**：55 行全部有交代——已改 42（含 CW09/CW10 的按决策实现）、已一致 11、保留并说明 1、已由他人做完 1、本计划不做 0（模拟桌面与演示下拉已并入 CW09/CW10/UP09 的「按决策/已一致」说明，不另立行）。

**文档同步**：`docs/UI_SPEC.md`（bootstrap `migration`、`window_close_ask` 事件、五步引导、× 规则、更新七态与文案）；`design/specs/terms-consent.md`（三件套打开时机与 ×/Esc）；`design/specs/copywriting.md`（关窗、更新、引导、条款、迁移逐字文案）；`design/specs/assistance-panels.md`（条款弹窗共享行为）。

**核对命令**（仓库根执行；只读）：

```bash
grep -n "waiting_count" docs/UI_SPEC.md
grep -n "migration" docs/UI_SPEC.md
grep -n "首次说明" design/specs/terms-consent.md
git diff -- design/evidence/2026-11-08/c3-dialogs-gap.md
```
