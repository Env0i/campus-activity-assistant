# 新工作台原型快照（2026-11-06，版本 33）

这是 [新工作台设计](../../../docs/superpowers/specs/2026-11-02-workbench-ui-redesign-design.md) 的原型源码快照（2026-11-02 已批准，待实现），给写代码的人对照状态规则和文案用。上一层目录是 2026-10-22 的旧原型，和这里无关。

- 只用假数据，不连学校、不连网；活动、账号打码、版本号、条款版本号都是编的。
- 原有 83 张画板和 claude.ai 上的私有原型一致，可以在本机打开、点击操作。2026-11-06 在本机分三轮补了 37 张（见下三条），再加 2026-11-07 补的 9 张（见下面一条），画布现有 129 张；私有原型暂不同步（用户 2026-11-06 定）。
- 2026-11-06 补画板（困难计划 prototype-backfill）：给已有场景补画板（列表加载失败、北京时间没校准、登录已失效、还没选活动）；停止计划前确认、停止后的逐场结果；组件安装位置（下载前写会装到哪，装好后写装在哪并能打开所在文件夹）；组件大小按发布页实际大小、读不到时写以发布页为准；验证码识别“本机已装、还没启用”这一态，以及登录恢复里对应的说明。截图在 [design/evidence/2026-11-06/prototype-backfill/](../../evidence/2026-11-06/prototype-backfill/)。
- 2026-11-06 第二轮补画板：已有交互里够得着、但没单独成画板的状态（更多筛选、搜索没结果、时间重叠、修改尝试时长、运行记录展开、关闭手机访问前确认、再配对一台、清除已保存账号前确认、组件下载失败、验证码认错）；新状态（条款状态没能确认、又打开了一次、旧数据搬迁成功与失败）；窄窗口的结果和设置；手机页的搜索、停止与取消确认、配对码输错、电脑上列表没加载、电脑上北京时间没校准。同时活动列表每场加了两项奖励：实践分和虚拟工资（宽、中窗口在活动名右侧两枚标签，窄窗口和手机页合成一枚放进说明行；详情没回来写“奖励同步中”，没公布写“未公布”）。不做活动详情页。
- 2026-11-06 登录框：点“登录”先弹登录框，“在这里输入”和“用学校登录页”两种方式并列，由用户选自己放心的那种。在这里输入时，表单下面直接写明密码只发给学校、不勾保存就不留；用学校登录页时写明工具看不到密码、代价是不能自动登录。代码里已有工具内登录，但样式不照搬，按这组画板重做。
- 2026-11-07 冲突与取消（计划 20261107-conflict-cancel，用户看效果稿后确认）：与已报名活动时间重叠的行改成灰选框加虚线“不可加入”，悬停整行或 Tab 聚焦弹出原因气泡（双方时段、时间条、解除路径）；跨天时段写绝对日期和天数；未报名行写“报后可退 / 报后不可退”；已报名且能取消的行写“可取消至”并给“取消报名”按钮，点后先出红色确认块，再有“正在取消…”和四种结果；手机页点按展开原因，不放取消按钮。新画板 11 张（ConflictTip 到 PhoneConflict，含取消时间已过、还不知道能不能取消两种原因），冲突和取消的演示数据只在这些场景里用一份精简名单，其余画板不受影响。截图在 [design/evidence/2026-11-07/conflict-cancel/](../../evidence/2026-11-07/conflict-cancel/)。
- 2026-11-08 冲突气泡改为鼠标停在“不可加入”上约 140ms 才弹（键盘聚焦照旧立即弹），扫过整行不再弹，和代码与决策 016 一致；画板本身不变。
- 2026-11-03 按[架构方案](../../../docs/superpowers/specs/2026-11-03-architecture-revision-design.md)回填：登录只显示上次校验时刻、计划等开放时原地重新登录、每场写明直接提交还是页面点击、名额已满单列、条款草案升到 r4。标志换成入场券（见 [design/brand/](../../brand/README.md)）。

## 在本机打开

双击 `打开原型.bat`。它会：

1. 用本机 Python 起一个只监听本机的静态服务器（端口 8790）。
2. 用默认浏览器打开查看器。

关掉服务器那个窗口就停止。也可以在仓库根手动运行：

```bash
python -m http.server 8790 --bind 127.0.0.1 --directory design/prototype/workbench-2026-11
```

然后打开 <http://127.0.0.1:8790/>。

查看器的用法：

- 左边按画布的行分组列出全部画板，点一下右边按原尺寸缩放显示。
- ↑↓ 键切换画板。
- “在新标签页打开这张”可以全尺寸操作。

不能双击 `index.html` 用 `file://` 打开：画板要用请求读取 `Main.dc.html` 等文件，浏览器会拦。

### 运行时文件

画板页面靠同目录的 `support.js` 渲染。它是 claude.ai 设计画布的运行时：里面除了 React（MIT 许可），还有画布自己的代码，许可不明。所以它被本目录的 `.gitignore` 排除，只留在这台电脑上，不进仓库、不随公开源码发布。

换一台电脑，或者这个文件丢了，有两种办法：

- 让 Claude 从私有原型的画布类型里重新取一份，放回本目录，改名为 `support.js`。
- 直接看 claude.ai 上的私有原型（链接在设计文档开头）。

## 文件

| 文件 | 内容 |
|---|---|
| `index.html` | 本机查看器（自己写的，只做画板列表和缩放显示） |
| `打开原型.bat` | 双击启动本机服务器并打开查看器 |
| `canvas.json` | 画布布局：每张画板的位置、尺寸、标题 |
| `Main.dc.html` | 电脑端工作台。`init(scene)` 列出每个场景的初始状态，`renderVals()` 是全部界面规则和文案 |
| `Phone.dc.html` | 手机页，结构同上 |
| `DesignSpec.dc.html` | 字体、字号、色板、按钮层级、对比度表 |
| `ImplNotes.dc.html` | 实现备注：只为演示存在的控件、假数据、待定事项 |
| 其余 `*.dc.html` | 126 张画板，每张只是“引用 Main 或 Phone + 一个场景名 + 尺寸” |
| `support.js` | 画布运行时，不进仓库（见上一节） |

## 怎么读源码

- 场景名就是 `Component.init(scene)` 里的 `scene`。例如 `runexpired` 是“计划等开放时登录失效”。
- 状态字段集中在 `init()` 开头的对象里（如 `login`、`clock`、`phase`、`tasks`、`ph`、`cred`、`ocr`、`terms`）。
- 一个场景显示成什么，看 `renderVals()` 里对应字段的取值。
- 带“演示”“原型”“模拟”字样的控件和函数只为切换画板存在，实现时删掉（清单见 `ImplNotes.dc.html`）。

## 场景目录

尺寸后面括号里的是窗口档位：medium 为中等宽度，narrow 为窄窗口，“矮”为矮窗口。没写的都是宽窗口。

| 画板 | 标题 | 源码 | 场景 | 尺寸 |
|---|---|---|---|---|
| Main | 主工作台（可操作） | Main.dc.html | draft（默认） | 1280×800 |
| Running | 计划运行中 | Main.dc.html | running | 1280×800 |
| Result | 部分成功与待核对 | Main.dc.html | result | 1280×800 |
| Attention | 登录待确认 | Main.dc.html | unknown | 1280×800 |
| FirstUse | 首次使用（可操作：条款、登录、引导） | Main.dc.html | first | 1280×800 |
| Settings | 设置 | Main.dc.html | settings | 1280×800 |
| Short | 短窗口 | Main.dc.html | draft | 1280×620（矮） |
| Narrow | 窄窗口 | Main.dc.html | draft | 430×820（narrow） |
| Waiting | 等开放，可以修改 | Main.dc.html | waiting | 1280×800 |
| Editing | 修改中，计划已暂停 | Main.dc.html | editing | 1280×800 |
| TourTable | 引导第 1 步：时刻表 | Main.dc.html | tour | 1280×800 |
| TourPick | 引导第 2 步：动手勾选 | Main.dc.html | tour2 | 1280×800 |
| TourRun | 引导第 4 步：开始以后 | Main.dc.html | tour4 | 1280×800 |
| PhoneSetup | 电脑端手机访问（可操作：安装、选通道、配对） | Main.dc.html | phonesetup | 1280×800 |
| PhoneTs | 通道还差一步：Tailscale 未登录 | Main.dc.html | phonets | 1280×800 |
| PhoneWait | 已开启，等手机连接 | Main.dc.html | phonewait | 1280×800 |
| PhoneLinked | 手机已连接 | Main.dc.html | phonelinked | 1280×800 |
| PhoneApp | 手机页（可操作，配对码 482913） | Phone.dc.html | pair | 390×844 |
| PhonePick | 手机页：选活动 | Phone.dc.html | picked | 390×844 |
| PhoneReview | 手机页：核对计划 | Phone.dc.html | review | 390×844 |
| PhoneRun | 手机页：计划运行中 | Phone.dc.html | running | 390×844 |
| PhoneResult | 手机页：结果 | Phone.dc.html | result | 390×844 |
| PhoneLock | 手机页：配对码错太多被锁 | Phone.dc.html | pairlock | 390×844 |
| PhoneOffline | 手机页：连不上电脑 | Phone.dc.html | offline | 390×844 |
| PhoneCheck | 手机页：开始没回应 | Phone.dc.html | pending | 390×844 |
| PhoneExpired | 手机页：登录失效 | Phone.dc.html | expired | 390×844 |
| PhoneCaptcha | 手机上重新登录：电脑有账号、没装识别 | Phone.dc.html | captcha | 390×844 |
| PhoneAuto | 手机上重新登录：电脑正在自动登录 | Phone.dc.html | auto | 390×844 |
| CloseLive | 关闭窗口（可操作：点标题栏的关闭） | Main.dc.html | closerun | 1280×800 |
| CloseAsk | 关窗：计划运行中 | Main.dc.html | closeask | 1280×800 |
| CloseConfirm | 关窗：退出要再确认 | Main.dc.html | closeexit | 1280×800 |
| CloseIdle | 关窗：没有计划，托盘也不可用 | Main.dc.html | closeidle | 1280×800 |
| CloseHidden | 关窗：隐藏到后台以后 | Main.dc.html | closehidden | 1280×800 |
| UpdateLive | 检查更新（可操作：检查、下载、安装） | Main.dc.html | update | 1280×800 |
| UpdateAvail | 更新：发现新版本 | Main.dc.html | upavail | 1280×800 |
| UpdateDown | 更新：下载中 | Main.dc.html | updown | 1280×800 |
| UpdateReady | 更新：校验通过，计划还在运行 | Main.dc.html | upready | 1280×800 |
| UpdateFail | 更新：校验失败 | Main.dc.html | upfail | 1280×800 |
| CompLive | 高级功能：一键下载安装（可操作） | Main.dc.html | comp | 1280×800 |
| CompWrong | 手动导入时选错了文件 | Main.dc.html | compwrong | 1280×800 |
| CompOk | 高级功能：下载中 | Main.dc.html | compok | 1280×800 |
| CredForm | 填写账号密码 | Main.dc.html | credform | 1280×800 |
| CredSaved | 已保存账号，自动登录已启用 | Main.dc.html | credsaved | 1280×800 |
| CompFail | 下载失败：重试或手动导入 | Main.dc.html | compfail | 1280×800 |
| Relogin | 重新登录（可操作：有账号、没装识别） | Main.dc.html | relogin | 1280×800 |
| RlCap | 电脑上输验证码 | Main.dc.html | rlcap | 1280×800 |
| RlConfirm | 电脑上自动登录一次 | Main.dc.html | rlconfirm | 1280×800 |
| RlBad | 保存的密码不对 | Main.dc.html | rlbad | 1280×800 |
| LoginShort | 登录撑不到开放的提醒 | Main.dc.html | loginshort | 1280×800 |
| PhoneRelAll | 手机上重新登录：电脑没账号、没装识别 | Phone.dc.html | relall | 390×844 |
| PhoneRelAcct | 手机上重新登录：电脑没账号、装了识别 | Phone.dc.html | relacct | 390×844 |
| PhoneRelConfirm | 手机上重新登录：自动登录一次 | Phone.dc.html | relconfirm | 390×844 |
| PhoneRelBad | 手机上重新登录：保存的密码不对 | Phone.dc.html | relbad | 390×844 |
| TermsUpdate | 条款更新后重新同意（可操作） | Main.dc.html | termsupdate | 1280×800 |
| TermsDoc | 完整条款：同意新版 | Main.dc.html | termsdoc | 1280×800 |
| TermsPrivacy | 完整条款：隐私政策（只读） | Main.dc.html | termsprivacy | 1280×800 |
| TermsOff | 没同意条款时（可操作） | Main.dc.html | termsoff | 1280×800 |
| TermsWithdraw | 撤回条款同意 | Main.dc.html | termswithdraw | 1280×800 |
| PhoneTerms | 手机页：电脑上没同意条款 | Phone.dc.html | phoneterms | 390×844 |
| PopClock | 北京时间详情卡（可操作：悬停预览、点击固定） | Main.dc.html | popclock | 1280×800 |
| PopLogin | 登录详情卡 | Main.dc.html | poplogin | 1280×800 |
| PopDown | 北京时间没校准 | Main.dc.html | popdown | 1280×800 |
| DesignSpec | 字体与配色规范 | DesignSpec.dc.html | — | 1280×1960 |
| PopPhone | 手机访问详情卡 | Main.dc.html | popphone | 1280×800 |
| PreWarn | 开始前提醒（只提醒不拦） | Main.dc.html | prewarn | 1280×800 |
| NetOff | 计划运行中断网 | Main.dc.html | netoff | 1280×800 |
| Slept | 电脑睡眠错过了开放 | Main.dc.html | slept | 1280×800 |
| Broken | 程序组件缺失 | Main.dc.html | broken | 1280×800 |
| HelpKeys | 帮助里的键盘快捷键 | Main.dc.html | helpkeys | 1280×800 |
| LongName | 超长活动名和地点 | Main.dc.html | longname | 1280×800 |
| NarrowPop | 窄窗口：详情卡铺满宽度 | Main.dc.html | poplogin | 430×820（narrow） |
| NarrowWarn | 窄窗口：有提醒时先看计划再开始 | Main.dc.html | prewarn | 430×820（narrow） |
| ZeroAct | 学校没返回活动 | Main.dc.html | zeroact | 1280×800 |
| ClockHold | 沿用上次校准 | Main.dc.html | clockhold | 1280×800 |
| RunExpired | 运行中登录失效 | Main.dc.html | runexpired | 1280×800 |
| ToastMin | 后台结束的通知 | Main.dc.html | toastmin | 1280×800 |
| RunPhone | 从手机开始的计划 | Main.dc.html | runphone | 1280×800 |
| RunAuto | 等开放时自动登录 | Main.dc.html | runauto | 1280×800 |
| RunClick | 本场改用页面点击 | Main.dc.html | runclick | 1280×800 |
| PhoneReviewWarn | 手机核对计划带提醒 | Phone.dc.html | reviewwarn | 390×844 |
| Medium | 中等宽度 900：草稿 | Main.dc.html | draft | 900×700（medium） |
| MediumRun | 中等宽度 900：运行中 | Main.dc.html | running | 900×700（medium） |
| ListErr | 活动列表加载失败 | Main.dc.html | listerr | 1280×800 |
| ClockDown | 北京时间没校准 | Main.dc.html | clock | 1280×800 |
| Expired | 登录已失效 | Main.dc.html | expired | 1280×800 |
| Normal | 常态：还没选活动 | Main.dc.html | normal | 1280×800 |
| StopAsk | 停止计划前确认 | Main.dc.html | stopask | 1280×800 |
| Stopped | 停止后的逐场结果 | Main.dc.html | stopped | 1280×800 |
| CompAfter | 组件已装：位置与验证码识别未启用 | Main.dc.html | compafter | 1280×800 |
| CompNoSize | 读不到发布页：大小以发布页为准 | Main.dc.html | compnosize | 1280×800 |
| CredOcrOff | 登录恢复：验证码识别已装未启用 | Main.dc.html | credocroff | 1280×800 |
| Filters | 更多筛选展开 | Main.dc.html | filters | 1280×800 |
| NoResult | 搜索没有结果 | Main.dc.html | noresult | 1280×800 |
| Conflict | 时间重叠，保留原选择 | Main.dc.html | conflict | 1280×800 |
| Policy | 修改尝试时长与次数 | Main.dc.html | policy | 1280×800 |
| LogOpen | 运行记录展开 | Main.dc.html | logopen | 1280×800 |
| PhStopAsk | 关闭手机访问前确认 | Main.dc.html | phstopask | 1280×800 |
| PhAddPair | 再配对一台手机 | Main.dc.html | phaddpair | 1280×800 |
| CredClear | 清除已保存账号前确认 | Main.dc.html | credclear | 1280×800 |
| PhFail | 手机控制组件下载失败 | Main.dc.html | phfail | 1280×800 |
| RlCapBad | 重新登录：验证码认错 | Main.dc.html | rlcapbad | 1280×800 |
| TermsUnknown | 条款状态没能确认 | Main.dc.html | termsunknown | 1280×800 |
| SecondRun | 又打开了一次（只运行一份） | Main.dc.html | secondrun | 1280×800 |
| Migrated | 旧版本数据已搬到新位置 | Main.dc.html | migrated | 1280×800 |
| MigrateFail | 旧登录信息没能搬过来 | Main.dc.html | migratefail | 1280×800 |
| NarrowResult | 窄窗口：计划结果 | Main.dc.html | result | 430×820（narrow） |
| NarrowSettings | 窄窗口：设置 | Main.dc.html | settings | 430×820（narrow） |
| PhoneSearch | 手机页：搜索 | Phone.dc.html | search | 390×844 |
| PhoneStop | 手机页：停止计划前确认 | Phone.dc.html | stopsheet | 390×844 |
| PhoneCancel | 手机页：取消这一场前确认 | Phone.dc.html | cancelsheet | 390×844 |
| PhonePairFail | 手机页：配对码输错 | Phone.dc.html | pairfail | 390×844 |
| PhonePcList | 手机页：电脑上的列表没加载 | Phone.dc.html | pclisterr | 390×844 |
| PhonePcClock | 手机页：电脑上的北京时间没校准 | Phone.dc.html | pcclock | 390×844 |
| Login | 登录：在这里输入账号密码 | Main.dc.html | login | 1280×800 |
| LoginBrowser | 登录：选用学校登录页 | Main.dc.html | loginbrowser | 1280×800 |
| LoginWait | 登录：等在学校登录页登完 | Main.dc.html | loginwait | 1280×800 |
| LoginCap | 登录：下一步输验证码 | Main.dc.html | logincap | 1280×800 |
| LoginBad | 登录：账号或密码不对 | Main.dc.html | loginbad | 1280×800 |
| NarrowLogin | 窄窗口：登录 | Main.dc.html | login | 430×820（narrow） |
| ConflictTip | 时间重叠：不可加入与原因气泡 | Main.dc.html | conflicttip | 1280×800 |
| ConflictNoCancel | 时间重叠：已报名那场不能取消 | Main.dc.html | conflictnocancel | 1280×800 |
| ConflictPast | 时间重叠：已报名那场取消时间已过 | Main.dc.html | conflictpast | 1280×800 |
| ConflictUnknown | 时间重叠：还不知道能不能取消 | Main.dc.html | conflictunknown | 1280×800 |
| CrossDay | 跨天时段与报后可退、不可退 | Main.dc.html | crossday | 1280×800 |
| CancelAsk | 取消报名前确认 | Main.dc.html | cancelask | 1280×800 |
| CancelBusy | 正在取消报名 | Main.dc.html | cancelbusy | 1280×800 |
| CancelDone | 取消报名：已取消 | Main.dc.html | canceldone | 1280×800 |
| CancelRefused | 取消报名：学校没有取消 | Main.dc.html | cancelrefused | 1280×800 |
| CancelUnknown | 取消报名：没能确认 | Main.dc.html | cancelunknown | 1280×800 |
| PhoneConflict | 手机页：时间重叠，点按看原因 | Phone.dc.html | conflict | 390×844 |
| ImplNotes | 实现备注 | ImplNotes.dc.html | — | 1280×2120 |
