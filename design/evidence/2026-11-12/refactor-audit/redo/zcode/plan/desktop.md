# T1 桌面复核（desktop）

- **基线提交**：`7e2d31c`。本件所有行号与摘录都以它为准（读法：`git show 7e2d31c:<路径>` 与只读基线树，两者交叉使用）。
- **执行日期**：2026-11-12 至 2026-11-13（北京时间）。
- **输入材料**：第一轮 `design/evidence/2026-11-12/refactor-audit/state-trace.md`，**按开工时（2026-11-12）内容核对**。
- **引用条目**：245 条（`d-001` 至 `d-245`），见同目录 `desktop.cites.jsonl`。摘录是基线原文的整行连续串，逐字节核对过唯一性。
- **结论档位**：属实 / 有条件属实（实质成立，但行号、措辞或覆盖面有偏差）/ 不属实 / 需测试定（运行期时序，读代码定不了）。本表没有判「不属实」的行。
- **范围口径**：对 state-trace.md 里标了来源「核」或「子」的行逐行给结论。state-trace 正文实际只出现「核」「数」两种标记，没有「子」标记的行；逐行表因此覆盖全部「核」行与第七节的执行方核对行。「数」来源的行不在逐行范围，但被「核」行引用到的行号都随行核对过。
- **U6/U11/U12 的编号说明**：三条均已对回第一轮 `ui-states.md` 的原始定义并核一致——U6＝验证码页点「改用浏览器登录」，取消和登录两个请求挨着发，登录会被「已有任务在跑」拒掉吗（中，推测；对应 state-trace.md 第 82 行）；U11＝停止成功后只等计划结束事件清「正在停止」，没有兜底（低；对应 state-trace.md 第 291 行）；U12＝取消报名没有前端超时，桥接不返回就一直挡着刷新（低；对应 state-trace.md 第 237 行）。

## ① 逐行结论总表

### 第一节 登录与重新登录

| state-trace 行号 | 内容摘要 | 结论 | 依据 |
|---|---|---|---|
| 26 | S.login.checking 的进（仅前台轮）与六处出 | 属实 | [[d-001]] [[d-002]] [[d-003]] [[d-004]] [[d-005]] [[d-006]] [[d-007]] |
| 27 | S.login.loginPending 的进（413）与四出（423/430/448/461） | 属实 | [[d-009]] [[d-010]] [[d-011]] [[d-012]] [[d-013]] [[d-014]] |
| 28 | S.login.preLoginSnapshot 共五处清（失败分支 457、成功分支 468） | 有条件属实：五处成立，但两处行号应为 466、477 | [[d-015]] [[d-009]] |
| 29 | S.autoLogin 的进（state/login.js:45、relogin.js:466）与出（27、29、466） | 属实 | [[d-016]] [[d-017]] [[d-018]] |
| 30 | S.login.handoff 进 459、出 458 与 state/login.js:47 | 属实 | [[d-019]] [[d-016]] |
| 31 | S.relogin 进 296（openRelogin）、321（openLogin）、出 346（closeRelogin） | 属实 | [[d-020]] [[d-021]] [[d-022]] |
| 32 | reloginRelay 进 444，每次事件整份替换、不清 | 属实 | [[d-023]] |
| 33 | reloginHandoffSeen 进 448、出 455 | 属实 | [[d-024]] |
| 34 | S.round.check/checkTimer 进 156/175、每轮开头 158 清旧定时器、事件到达 app.js:104 | 属实 | [[d-025]] [[d-026]] |
| 35 | 后端 Api._checking 进 2278、出 2322/2329 | 属实 | [[d-027]] [[d-028]] |
| 36 | 后端 Api._proc（中继占用）进 4272、出 _relay_finished 4289/4291 | 属实 | [[d-029]] [[d-030]] |
| 37 | 后端 Api._pending_save 进 2034/4067/4149、出 4079/4307 | 属实 | [[d-031]] [[d-032]] [[d-033]] [[d-034]] [[d-035]] |
| 39 | handoff/autoLogin/relogin/recovering/view 未在 store.js 的 S 字面量里声明 | 属实 | [[d-035]]（另经 store.js 全文检索复核，S 顶层无这些键） |
| 47 | 成功失败经 check 事件收口（107 清、124 setLogin） | 属实 | [[d-002]] |
| 48 | 桥接异常清掉、落「暂时无法确认」、写运行记录（206-224） | 属实 | [[d-004]] |
| 49 | 100 秒超时同上（175-188） | 属实 | [[d-003]] |
| 50 | skipped 接续旧请求号、重挂定时器、带回结论当场落地（266-268）、暂存重放（270-275） | 属实 | [[d-007]] [[d-008]] |
| 51 | 条款回绝、没能开始（313-319、330-342） | 属实 | [[d-005]] [[d-006]] |
| 52 | 旧一轮迟到事件按请求号暂存或丢弃（app.js:98-102） | 属实 | [[d-037]] |
| 53 | 后台自动刷新不进检查中、超时与失败静默收口 | 属实 | [[d-001]] [[d-038]] |
| 54 | 没有取消入口；校验是后台线程，后端 _checking 无对外取消路径 | 属实 | [[d-039]]（js_api 的取消类方法全量检索仅有组件下载/取消报名/单场取消/重登取消，无 check 取消） |
| 62 | 中继成功失败取消经 live 为假收回（463-466） | 属实 | [[d-017]] |
| 63 | 转人工后 463 的条件不再成立 | 属实 | [[d-019]] [[d-017]] |
| 64 | 校验结论变成有效收回（state/login.js:47、27） | 属实 | [[d-016]] [[d-018]] |
| 65 | 校验超时失败没能开始都走 syncLoginDependentView → reconcileAutoLogin | 属实 | [[d-003]] [[d-004]] [[d-006]] [[d-018]] [[d-056]] |
| 66 | 用户关对话框只有非「电脑自己正在做的那一场」才发取消 | 属实 | [[d-040]] [[d-054]] [[d-057]] |
| 72 | loginPending 没有前端超时，api() 不带 timeout | 属实 | [[d-036]] |
| 78 | 用户关（取消、×、Esc）路径 342-356 | 属实 | [[d-022]] [[d-042]] |
| 79 | 对话框不自动关，终态切到结果说明那一步 | 属实 | [[d-043]] |
| 80 | 验证码页点「改用浏览器登录」先 closeRelogin 再 doLogin（514） | 属实 | [[d-041]] |
| 82 | 改用浏览器登录时 relogin_cancel 与 login 的竞态（原文自标「推测，不能判定」） | 需测试定：机制链成立，走向无法由代码定，见 ② U6 | [[d-040]] [[d-041]] [[d-229]] [[d-230]] [[d-231]] [[d-232]] [[d-233]] [[d-234]] [[d-235]] [[d-236]] [[d-029]] [[d-030]] [[d-054]] [[d-237]] |
| 88 | 胶囊「检查登录…」与「登录待确认」（views/login.js:71-73）、运行记录 | 有条件属实：「登录待确认」基线在 views/login.js:55-60，非 71-73；其余属实 | [[d-048]] [[d-047]] [[d-003]] [[d-004]] [[d-006]] |
| 89 | 浏览器登录「登录中…」、计划栏显示、结果框「登录没能开始」（445、453） | 属实 | [[d-049]] [[d-050]] [[d-012]] |
| 90 | 输验证码提交：对话框等待页与结果说明（reloginStep("result")） | 有条件属实：失败切的步骤名是 msg，不是 result | [[d-044]] [[d-045]] |
| 91 | 静默自动登录的显示、第一次失败回失效、60/120/300/900 退避、无「正在重试」显示 | 属实 | [[d-046]] [[d-051]] [[d-047]] |
| 95 | S.login.result 四态直取后端 check 事件 | 属实 | [[d-002]] |
| 96 | S.autoLogin 是前端用 recovering 与中继快照两个来源拼的 | 属实 | [[d-016]] [[d-017]] |
| 97 | S.login.checking 只有前端有，后端 _checking 不下发 | 属实 | [[d-052]] |

### 第二节 组件：手机访问与验证码识别

| state-trace 行号 | 内容摘要 | 结论 | 依据 |
|---|---|---|---|
| 109 | PhonePanel.busy 五进（847/866/890/1013/1099）五出（856/883/906/1022/1111）、出口在 finally | 属实 | [[d-058]] [[d-059]] [[d-060]] [[d-061]] [[d-062]] [[d-063]] |
| 110 | PhonePanel.pending 进 867/891、出 882/905（finally） | 属实 | [[d-059]] [[d-060]] [[d-061]] [[d-092]] |
| 111 | installing[key] 进 793、出 820（finally，两键） | 属实 | [[d-064]] [[d-065]] |
| 112 | OcrPanel.busy 进 316、出 326 | 属实 | [[d-066]] |
| 113 | 下载中/校验中由后端服务 _state 经快照下发，前端不另存 | 属实 | [[d-067]] [[d-068]] [[d-078]] |
| 114 | 检查中：事务锁超时且无上次成功结果时返回 checking | 属实 | [[d-069]] |
| 115 | 需要更新：component_outdated 映射 | 属实 | [[d-070]] |
| 116 | Api._advanced_busy 三进（1440/1661/1740）三出（1358/1686/1768） | 属实 | [[d-071]] [[d-072]] [[d-073]] [[d-074]] [[d-075]] [[d-076]] |
| 117 | 服务 _state：start 置 _active（180），线程 finally 回调 on_finished 并清（329-339） | 属实 | [[d-077]] [[d-078]] |
| 125 | installing 无漏清路径（try…finally） | 属实 | [[d-064]] [[d-065]] |
| 127 | 下载忙碌位无漏清路径 | 属实 | [[d-071]] [[d-076]] [[d-078]] |
| 129 | 检查中无超时出口、无重试按钮、有旧结果时沿用并带 busy | 有条件属实：代码行为属实；「蓝点」样式在 CSS，未核 | [[d-069]] [[d-085]] [[d-089]] |
| 131 | 读状态失败不改状态、不提示、照旧快照重画（198-207） | 属实 | [[d-079]] |
| 137 | 下载失败红条原因表、后端写运行记录（app.py:1369）、「重新下载」按钮 | 有条件属实：运行记录的 _emit 在 app.py:1375，非 1369；其余属实 | [[d-080]] [[d-081]] [[d-082]] [[d-083]] |
| 138 | 「安装中…」（796）与对话框里一句（801） | 属实 | [[d-084]] [[d-064]] [[d-065]] |
| 139 | 开启手机访问 pending="starting"、失败写 offErr（874、880） | 属实 | [[d-059]] [[d-060]] |
| 140 | 读组件状态失败无显示，重开抽屉再读 | 属实 | [[d-079]] |
| 141 | 检查中蓝点、不转失败、无按钮等下次轮询 | 有条件属实：同 129 | [[d-085]] |
| 142 | 启用后自动更新走下载显示、只写运行记录、停在「需要更新」 | 属实 | [[d-086]] [[d-087]] |
| 146 | 两面板四段结构基本相同；settings 多 OcrPanel.error 覆盖与 installing 复合检查 | 属实 | [[d-067]] [[d-068]] [[d-088]] [[d-089]] [[d-090]] |

### 第三节 版本更新

| state-trace 行号 | 内容摘要 | 结论 | 依据 |
|---|---|---|---|
| 158 | S.update.state 16 个取值（22-24）、检查中 55、启动中 133、其余事件写（25） | 属实 | [[d-091]] [[d-243]] [[d-244]] |
| 159 | requestId 进 54、132；迟到回执按它丢弃；「18 处比对」 | 有条件属实：进/出与认主属实；「18 处比对」与基线不符——update.js 内 S.update.requestId 共 19 处、其中严格相等比对 8 处 | [[d-093]] [[d-243]] [[d-244]] [[d-094]] |
| 160 | 看门狗检查 15 秒、下载与校验每次进度续 60 秒、出 19 | 属实 | [[d-094]] [[d-095]] [[d-243]] |
| 161 | Api._updating 进 2076/2131、出 2112（事件带 finished）/2088/2139、update_service.py:54 | 属实 | [[d-096]] [[d-097]] [[d-098]] [[d-099]] [[d-100]] [[d-101]] |
| 162 | Api._update_result 最近一份状态，界面重载恢复 | 属实 | [[d-098]] [[d-101]] |
| 166 | 检查中事件到达即出、无事件由看门狗 15 秒收、没有取消入口 | 属实 | [[d-094]] [[d-102]] |
| 172 | 安装程序没能启动：后端推 failed 并返回 ok=false，前端按失败落地 | 属实 | [[d-105]] [[d-108]] |
| 173 | 桥接异常按失败落地（141-145） | 属实 | [[d-105]] |
| 174 | 版本目录切换路径，启动器没拉起推 failed（2218） | 属实 | [[d-106]] |
| 175 | 启动器拉起，约 1 秒后程序自己走退出（2231） | 属实 | [[d-107]] |
| 176 | 安装程序启动成功「不出」：后端仍推 launching（finished 为假）、checkUpdate 在该态直接返回、后端 skipped、续时名单不含 launching | 属实 | [[d-108]] [[d-103]] [[d-104]] [[d-095]] |
| 178 | 已知限制；界面上有「关闭本工具…」按钮（views/update.js:139） | 属实 | [[d-110]] [[d-109]] |
| 184 | 检查更新「正在检查…」、按钮禁用 | 属实 | [[d-109]] |
| 185 | 下载与校验的进度、取消、续看门狗 60 秒 | 属实 | [[d-095]] [[d-102]] |
| 186 | 启动安装程序的显示与失败 | 属实 | [[d-244]] [[d-105]] |
| 190 | 状态以后端 _update_result 为准、bootstrap 恢复；写状态的两处 | 属实 | [[d-098]] [[d-101]] |

### 第四节 活动列表刷新与自动刷新

| state-trace 行号 | 内容摘要 | 结论 | 依据 |
|---|---|---|---|
| 202 | S.listState 的 loading（161，仅前台轮）、ready（503）、六处 error（197/238/288/322/350/483）、idle（app.js:77） | 属实 | [[d-111]] [[d-112]] [[d-113]] [[d-114]] [[d-115]] [[d-116]] [[d-117]] [[d-118]] [[d-119]] |
| 203 | S.round.list/listTimer 进 157/189、每轮开头 159 清旧定时器、回包 469 | 属实 | [[d-025]] [[d-120]] |
| 204 | S.round.background 进 149、下一轮覆盖 | 属实 | [[d-121]] |
| 205 | runtime.checkPending/listPending 进 165-166、出 settleRefreshBranch 与 app.js:116-119 | 属实 | [[d-122]] [[d-123]] [[d-124]] |
| 206 | autoRefreshState 进 147/542/601/612、出 507/509 | 属实 | [[d-121]] [[d-125]] [[d-126]] [[d-127]] [[d-118]] |
| 207 | S.cancel.busyId 进 84、出 37（cancelSettle 第一句） | 属实 | [[d-128]] [[d-129]] |
| 208 | S.cancel.askId 的进与出（29、74；手动刷新 refresh.js:131） | 属实 | [[d-130]] [[d-131]] [[d-132]] |
| 209 | Api._listing 进 2302、出 2515 | 属实 | [[d-134]] [[d-135]] |
| 210 | Api._cancelling 进 2575、出 2580 | 属实 | [[d-136]] |
| 214 | 六个 error 出口一个 ready 出口、请求号与代次校验（204/211/226/231） | 属实 | [[d-112]] [[d-113]] [[d-114]] [[d-115]] [[d-116]] [[d-117]] [[d-118]] [[d-139]] [[d-140]] |
| 216 | 后台自动刷新不进 loading 不清列表，失败只累计次数 | 属实 | [[d-141]] |
| 218 | 前台轮失败清 items/byId/selected（479-481，行号经基线复核无误）；程序发起的静默刷新同走此路——实为六处不是四处（T6 对账补正：补 [[d-246]] 单场失败后 400ms 复查、[[d-247]] 浏览器登录成功后刷新，两处同为程序发起且走前台轮） | 有条件属实 | [[d-117]] [[d-142]] [[d-143]] [[d-144]] [[d-145]] [[d-246]] [[d-247]] [[d-248]] |
| 227 | 窗口恢复先 bootstrap 再 refresh(true)、骨架行（list.js:29-35） | 属实 | [[d-142]] [[d-111]] [[d-146]] |
| 233 | 后端回结果 → cancel.js:87-89 → cancelSettle 清 busyId | 属实 | [[d-128]] [[d-129]] |
| 234 | 桥接异常按「没能确认」处理 | 属实 | [[d-128]] |
| 235 | 前端没有定时器、api() 不带 timeout | 属实 | [[d-036]] |
| 237 | busyId 挡刷新、按钮禁用、后端 90 秒超时（app.py:2572）、桥接挂住是推测 | 有条件属实：90 秒常量基线在 app.py:2521，非 2572；「桥接挂住」需测试定（见 ② U11） | [[d-132]] [[d-133]] [[d-137]] [[d-138]] [[d-240]] |
| 243 | 手动刷新骨架行、计数「正在刷新…」（list.js:381）、刷新按钮禁用 | 属实 | [[d-146]] [[d-148]] [[d-133]] |
| 244 | 后台自动刷新无显示、连续 3 次失败才写一句 | 属实 | [[d-125]] |
| 245 | 「北京时间校准中，稍后加载活动」、等不到照常拉列表 | 属实 | [[d-053]] |
| 246 | 取消报名结果句写在这一行（cancel.js:55-63） | 属实 | [[d-129]] |

### 第五节 报名计划栏

| state-trace 行号 | 内容摘要 | 结论 | 依据 |
|---|---|---|---|
| 259 | S.starting 四进（43/54/132/153）四出（58/180/187/211） | 属实 | [[d-149]] [[d-150]] [[d-151]] [[d-152]] [[d-154]] [[d-155]] |
| 262 | S.plan.status 进 state/plan.js:50、59 与 plan-events.js:8；终态不回退（state/plan.js:49） | 属实 | [[d-157]] [[d-158]] [[d-159]] |
| 263 | S.stopping 进 383、出 389/395/91 与 plan-events.js:10、47 | 属实 | [[d-160]] [[d-161]] [[d-156]] [[d-159]] [[d-162]] |
| 264 | S.editing 进 353、出 plan.js:90、state/plan.js:60、state/filters.js:390 | 属实 | [[d-163]] [[d-156]] [[d-158]] [[d-168]] |
| 268 | S.editing 没有在 state/store.js 里声明 | 属实 | [[d-035]]（store.js 全文检索无 editing 键） |
| 274 | modifyPlan 记 editing、写「计划已暂停」运行记录、调 doStopPlan | 属实 | [[d-163]] |
| 278 | 停止以 stopped 结束：放回勾选、清计划、S.editing 保留 | 属实 | [[d-164]] |
| 279 | 重新开始被接纳清 editing（plan.js:90） | 属实 | [[d-156]] |
| 280 | 用户清空选择清 editing（state/filters.js:390） | 属实 | [[d-168]] |
| 281 | 停止没成功只清 S.stopping，S.editing 留着 | 属实 | [[d-161]] |
| 282 | 计划先自然结束 editing 不清、回草稿仍「修改中」、「放弃修改」按钮出现 | 属实 | [[d-165]] [[d-166]] [[d-167]] [[d-169]] [[d-170]] |
| 284 | 「放弃修改」按钮绑 startPlan、用当前勾选、不读 editing.ids | 属实 | [[d-171]] [[d-172]] [[d-163]] |
| 291 | 停止成功等 plan_done 事件清 stopping；事件链 evaluate_js 投递；「presentPlanDone 第一句」；「bootstrap 只对账 busy 与 plan.status」 | 有条件属实：事件链属实；presentPlanDone 的 S.stopping=false 在第 10 行、不是第一句；bootstrap 的终态快照会经 presentPlanDone 清 stopping，原话不准确；事件是否丢失需测试定（见 ② U12） | [[d-159]] [[d-162]] [[d-161]] [[d-176]] [[d-177]] [[d-178]] [[d-181]] [[d-180]] |
| 293 | starting 对账无结论时保持禁用、「重新确认」入口（160） | 属实 | [[d-152]] [[d-153]] |
| 299 | 开始计划的进行中显示与失败显示 | 属实 | [[d-153]] [[d-149]] |
| 300 | 停止计划：运行记录一句、按钮按停止中画、没有结果框 | 属实 | [[d-160]] [[d-161]] [[d-180]] |
| 301 | 修改计划同停止 | 属实 | [[d-163]] |
| 302 | 单场取消只在运行记录写一行，planLive 时不 setResult | 属实 | [[d-179]] |

### 第六节 手机页

| state-trace 行号 | 内容摘要 | 结论 | 依据 |
|---|---|---|---|
| 314 | model.flying 进 2434、出 2453（finally） | 属实 | [[d-182]] [[d-183]] |
| 316 | model.pending 进 2730、出 2741（后端当场受理）、2760（对账查到终态） | 属实 | [[d-186]] [[d-187]] [[d-189]] |
| 317 | model.reconciling 进 2753、出 2773（finally） | 属实 | [[d-188]] [[d-190]] |
| 318 | model.cancelingStart 进 2783、出 2798 | 属实 | [[d-192]] [[d-193]] |
| 320 | reloginSubmitting 进 3123、出 3148（被拒）与其余由 ingest 按场次状态清 | 属实 | [[d-198]] [[d-200]] [[d-195]] [[d-196]] [[d-197]] |
| 323 | model.lastOkAt 取手机本机时钟（2441） | 属实 | [[d-185]] |
| 329 | 轮询 2436-2459 try/catch/finally，失败累计次数、拉长间隔 | 属实 | [[d-182]] [[d-183]] [[d-184]] |
| 331 | 开始请求：postAction 接住网络异常、401 直接返回、当场受理记终态、ingest 末尾触发对账、unknown 给「取消等待」 | 属实 | [[d-194]] [[d-186]] [[d-187]] [[d-189]] [[d-191]] |
| 333 | 提交验证码网络异常故意不清在途标志、提示后立刻触发轮询 | 属实 | [[d-199]] |
| 335 | 对账 2754-2775，reconciling 一定清 | 属实 | [[d-188]] [[d-190]] |
| 337 | 两处靠下一次轮询成功才收（提交验证码网络异常、开始请求 401） | 属实 | [[d-199]] [[d-187]] |
| 343 | 轮询「同步中」、刷新钮禁用（2435） | 属实 | [[d-182]] |
| 344 | 开始计划底栏按核对中画、横幅写原因（2744、2765-2767） | 属实 | [[d-187]] [[d-191]] |
| 345 | 提交验证码「正在登录，请等结果」、弹层锁定（3124）、失败弹层里一句（3149-3151） | 属实 | [[d-198]] [[d-200]] |
| 346 | 配对按钮禁用（pairing 置位/finally）与锁定倒计时（pairView lockLeft、applyPairFailure 置 pairLockLeft） | 有条件属实：置位与 finally 属实；pairView 两成员未逐行核 | [[d-207]] [[d-208]] |
| 350 | 计划、活动、登录都来自 /api/state 快照，model.busy 完全以后端为准（2665） | 属实 | [[d-201]] |
| 351 | 登录是否失效是手机页自己用三个字段拼的，没用后端四态结论 | 属实 | [[d-202]] |
| 352 | 「立即报名还是预报名」手机页自己按开放时刻算 | 属实 | [[d-203]] |
| 353 | 「最近同步」用手机本机时钟 | 属实 | [[d-204]] |

### 第七节 状态残留对账（C5，执行方核对行）

| state-trace 行号 | 内容摘要 | 结论 | 依据 |
|---|---|---|---|
| 363 | (1) 「放弃修改」不恢复原勾选——未修 | 属实 | [[d-172]] [[d-163]] |
| 364 | (2) 停止没成功或自然结束时卡「修改中」——未修 | 属实 | [[d-161]] [[d-165]] [[d-166]] [[d-169]] [[d-170]] |
| 365 | (3) 程序发起的刷新失败清空列表——部分（每 10 分钟自动刷新已修） | 属实 | [[d-141]] [[d-117]] [[d-142]] [[d-143]] [[d-144]] [[d-145]] |
| 366 | (4) 窗口从最小化恢复列表闪一次——未修 | 属实 | [[d-142]] [[d-111]] [[d-146]] |
| 367 | (5) 胶囊停「自动登录中」——已修（52fd5b2，reconcileAutoLogin 在 50 与 136 两处调用） | 属实 | [[d-018]] [[d-055]] [[d-056]] |
| 368 | (6) 关对话框取消电脑正在进行的自动登录——已修（52fd5b2，relogin.js:23-27、355） | 属实 | [[d-057]] [[d-040]] |
| 369 | (7) 手机页仍写「电脑上的登录有效」——已修（ddd4edc；loginRaw 认 last_check_state=expired） | 属实 | [[d-202]] |
| 370 | (8) 手机核对弹层不随轮询更新——未修（renderReview 只有两处调用）；「点开始可能没反应」没有复现 | 属实（调用点属实）；后半句是提案原话，代码不能定 | [[d-206]] |
| 371 | (9) 「最近同步」用手机本机时钟——未修（2707-2710 用 new Date；离线档 2657-2661 已用北京时间） | 属实 | [[d-204]] [[d-205]] |
| 372 | (10) 安装程序启动后「检查更新」不可点——已知限制，代码没改 | 属实 | [[d-108]] [[d-103]] [[d-104]] [[d-110]] |
| 373 | (11) 「错过了」把原因写进行里——未按提案改，行内只有两句短说明 | 属实 | [[d-147]] |
| 375 | 合计：已修 3、部分 1、未修 5、已知限制 1、未按提案改 1 | 属实（与逐行结论一致） | 同上各行 |

## ② U6 / U11 / U12 调用链与补测

三条都是运行期时序问题，桌面复核只能把链路核清、把「哪一环代码定不了」指出来，结论一律为需测试定。

### U6 「改用浏览器登录」时 relogin_cancel 与 login 的竞态（state-trace.md 第 82 行）

调用链（每步挂条目）：

1. 用户在验证码页点「改用浏览器登录」，按钮处理是先 `closeRelogin()` 再 `doLogin()`（relogin.js:514-515）[[d-041]]。
2. `closeRelogin` 对「不是电脑自动进行中」的那一场发 `api("relogin_cancel", flowId)` 且 `.catch(() => {})`——发出后不等待结果（relogin.js:352-356）[[d-040]]；「电脑自动进行中」的口径是 reloginAutoLive（relogin.js:23-27）[[d-057]]。
3. `doLogin` 先存登录快照、置 loginPending，然后 `api("login")` [[d-009]]。
4. 后端 `relogin_cancel` 校验 flow 后转 `self._relay.cancel()`（app.py:4186-4192）[[d-232]]。
5. `relay.cancel` 在服务自己的锁内清掉 `_flow/_proc/_stdin`（login_relay_service.py:282-294）——**清的是服务自己的 `_proc`，不是 `Api._proc`** [[d-233]]。
6. 锁外 `tree.terminate()` 且不等它退出，随后同步调 `self._on_finish()`（295-302）[[d-234]]。
7. `terminate` 的实现注释写明：Job 终止后进程异步收尾，紧接着看 poll() 几乎总是还没退（process_tree.py:235-240）[[d-235]]。
8. `_on_finish` 在构造时注入为 `Api._relay_finished`（app.py:962-967）[[d-236]]；`_relay_finished` 只在进程已退出（poll() 非 None）时才收走 `Api._proc`，未退时留着占位（app.py:4282-4293）[[d-030]]。
9. `Api._proc` 是中继 worker 起进程时就占住的（app.py:4270-4274）[[d-029]]；worker 正常读完的另一条收口路径同样回调 `_on_finish`（login_relay_service.py:535-546）[[d-054]]。
10. `login`（app.py:2768-2778）做关闭/计划占用与条款检查后交 `_spawn` [[d-229]]；`_spawn` 在锁内跑 `_is_busy_locked`，忙则回「已经有一个任务在跑，先等它结束」并占位（app.py:4527-4536）[[d-230]]；`_is_busy_locked` 把存活的 `_proc` 视为忙（app.py:4428-4438）[[d-231]]。

与任务书背景提示的比对结论：**这条链与背景提示一致**——中继 worker 占 `Api._proc`（第 8、10 步），cancel 只清服务自己的 `_proc`（第 5 步），terminate 后 `_relay_finished` 在进程未退时保留 `Api._proc`（第 7、8 步），login 的忙碌检查会看到它（第 10 步）。争议点是运行期的两处前提：terminate 后 worker 何时真正退出、两次 js_api 调用（relogin_cancel 与 login）在 pywebview 里各起线程、无先后保证——[[d-237]]。

与第一轮的对齐：第一轮 U6 的建议已写明补测口径——「relogin_cancel 与 login 两个桥接调用以任意顺序到达时，login 不被 busy 拒绝」；「每一块动手前要先补的测试」步骤 1B 第二句同义（「验证码页改用浏览器：浏览器登录能开始」）；第一节「需要后端配合」给的两条修复方向是「取消并等它结束」的接口，或 login 在中继正被取消时等一下而不是直接拒绝。那些是修复后的目标行为；本件先补现状对账测试把竞态钉住，再以目标行为作修复验收。样板写法可参照 `SilentReloginResidualTests`（local/tests/test_ui_reliability.py:2206 起，随提交 52fd5b2 加入）——每条用例一条退出路径。

补测建议（与第一轮口径对齐）：
- 现状对账（先钉住竞态）：测试名 `test_relogin_cancel_then_login_races_busy_slot`，放 `local/tests/test_login_relay_service.py`（端到端可加在 `local/tests/test_login_relay.py`）。用「terminate 后进程不立即退出」的替身树（poll() 先恒 None、之后可翻转为已退出），断言 (a) `relay.cancel()` 返回后立刻调 `Api.login()` 得到 ok=false、文案为「已经有一个任务在跑，先等它结束」；(b) 进程退出并再次触发 `_relay_finished` 后，同一 `Api.login()` 能成功占位。
- 目标行为（第一轮 U6 的验收口径）：修复后（login 等中继收尾，或取消路径先把槽位收干净），relogin_cancel 与 login 两个桥接调用以任意顺序到达时 login 不被 busy 拒绝。
- 前端契约：在 `local/tests/test_ui_contract.py` 断言 `btn-rl-browser` 的处理是 `closeRelogin(); doLogin()`，且 `relogin_cancel` 调用不带 await。

### U12 取消报名没有前端超时，busyId 挡刷新（state-trace.md 第 237 行；ui-states.md U12）

调用链：

1. 确认取消：`cancelConfirm` 清 askId、置 `busyId`（cancel.js:72-75）[[d-131]]，`api("cancel_signup")` 的 then/catch 两条路都指向 `cancelSettle`（cancel.js:84-93）[[d-128]]。
2. 前端 `api()` 直接返回桥接 promise，没有超时参数（bridge.js:6-11）[[d-036]]。
3. 后端 `cancel_signup` 约定成败只信 worker 复查（app.py:2555-2561）[[d-238]]，锁内前置检查并占位 `_cancelling`（app.py:2566-2574）[[d-239]]；worker 以 `CANCEL_WORKER_TIMEOUT_S = 90` 超时运行（app.py:2596-2600、2519-2522）[[d-138]] [[d-137]]，finally 收口 `_cancelling`（app.py:2574-2581）[[d-136]]。
4. 回包或桥接异常 → `cancelSettle` 开头清 busyId（cancel.js:34-38）[[d-129]]。
5. busyId 在途时刷新入口直接返回（refresh.js:129）[[d-240]]，刷新按钮禁用（plan-panel.js:1230）[[d-133]]。

争议点：后端 90 秒超时保证 worker 会结束并返回，「桥接 promise 是否可能长期不 settle」无法由仓库代码证明——[[d-240]]。若桥接挂住，busyId 不清、刷新被挡、按钮禁用，前端没有任何兜底（第 2 步）。

与第一轮的对齐：第一轮 U12 已确认 bridge.js 的 api() 无 timeout、后端 90 秒超时挡住大多数情形（与本件 [[d-036]] [[d-137]] [[d-138]] 的核对一致），建议「需加前端 95 秒兜底」；第四节取消报名的小状态机也写明「取消中要有超时出口（U12），超时按『没能确认，请到学校网站核对』处理」。

补测建议（与第一轮口径对齐）：
- 现状对账：测试名 `test_cancel_busyid_bridge_never_settles`，放 `local/tests/test_ui_conflict_cancel.py`（行为用例如不便落位，放 `local/tests/test_cancel_signup.py` 的桥接替身用例）。用永不 settle 的假 `api` 替身调 `cancelConfirm`，断言 busyId 不被清、随后 `refresh()` 直接返回、刷新按钮保持禁用；再让替身 settle 后断言 busyId 清掉、刷新恢复。
- 目标行为（第一轮 U12 的验收口径）：给前端加 95 秒兜底后，超时把结果按「没能确认，请到学校网站核对」写在这一行、busyId 清掉、刷新恢复，不再无限挡刷新。
- 契约断言：bridge.js 的 `api()` 不含 timeout。

### U11 停止成功后只等 plan_done 事件清「正在停止」，没有兜底（state-trace.md 第 291 行；ui-states.md U11）

调用链：

1. `doStopPlan` 置 `S.stopping`、写「正在停止计划」运行记录、发 `stop_plan`（plan.js:379-387）[[d-160]]；停止按钮按 stopping 画「正在停止…」（plan-panel.js:1253-1254）[[d-180]]。
2. 后端 `stop_plan` 幂等，先停协调器再杀 worker（app.py:3242-3249）[[d-181]]。
3. 协调器终态回调在锁内清 `_plan`（app.py:3124-3128）[[d-173]]，最终接纳点写 `_plan` 并递增代次（app.py:3205-3211）[[d-174]]；协调器 start 失败时撤销预留、同样清 `_plan`（app.py:3221-3230）[[d-175]]，随后经 `_emit` 发 plan_done（app.py:3155-3159）[[d-176]]。
4. `_emit` 经 `evaluate_js` 投递且异常被吞（app.py:1117-1124）[[d-177]]，窗口缺失时直接返回、事件不投递（app.py:1097-1110）[[d-242]]——这是事件丢失的两个面。
5. 前端 plan_done 入口（app.js:157-158）[[d-178]] → `presentPlanDone` 写终态并清 stopping（plan-events.js:7-10）[[d-159]]；重复终态分支自己收口 stopping（plan-events.js:41-48）[[d-162]]。
6. 恢复面：窗口恢复时 bootstrap 的终态快照也会经 presentPlanDone 清 stopping（app.js:637-642 → plan-events.js:7-10）[[d-142]] [[d-159]]。

争议点：evaluate_js 投递失败或窗口缺失时事件丢失，界面停在「正在停止」，要等下一次窗口恢复对账才解——实际发生概率与场景无法由代码证明——[[d-241]]。

与第一轮的对齐：第一轮 U11 对事件链已「从推测转实」（后端 emit("plan_done") → pywebview evaluate_js → 前端 handlePlanDone → presentPlanDone 清 stopping），与本件 [[d-176]] [[d-177]] [[d-178]] [[d-159]] 的核对一致；其建议里「窗口恢复时 bootstrap 不改 stopping」一句按基线不准确——终态快照会经 ingestBootstrapPlan → presentPlanDone 清掉 stopping（总表第 291 行已标有条件属实）；第五节还把「停止请求的回话要区分『已经停下』『正在停，等结束事件』『没有这个计划』」列为需要后端配合项。「每一块动手前要先补的测试」步骤 1C 的补测口径是：「停止成功但结束事件没到：窗口重新可见后『正在停止』能收掉」。

补测建议（与第一轮口径对齐）：
- 目标行为（步骤 1C 口径）：测试名 `test_stop_stuck_then_window_refocus_recovers`——停止成功但 plan_done 事件没到，窗口重新可见（visibilitychange bootstrap 拉到终态快照）后「正在停止」能收掉。
- 现状对账：node 沙箱回放 plan-events.js——(a) 不投递 plan_done 时 S.stopping 保持真、停止按钮保持「正在停止…」；(b) 以终态快照走 ingestBootstrapPlan → presentPlanDone 后 S.stopping 清掉（即「重新可见后能收掉」的现有实现面）。
- 放哪：行为用例放 `local/tests/test_ui_reliability.py`（跟随 SilentReloginResidualTests 的样板风格）或 `local/tests/test_signup_plan.py` 的沙箱回放；契约断言（app.py 的 `_emit` 把 evaluate_js 包在 try/except，事件丢失是代码允许的路径）放 `local/tests/test_ui_contract.py`。

## ③ 两个组件面板四段比对

口径：只比「组件包下载/安装/启停」这一组呈现。手机访问面板的实现是 `paintPhoneAccess`（基线 phone.js 437-698），验证码识别面板是 `paintOcrDownload`（基线 settings.js 193-311）。四段＝阶段、主按钮、提示行、错误条。

### 手机访问面板（views/phone.js）

- **阶段**：`phonePhase` 九档，`st.running` 优先判 on，再 downloading/verifying，然后 checking/outdated/broken/ready(off)/available(disabled)/missing [[d-067]]；按相位显隐五个块（missing/loading/access-detail/off/on）[[d-213]]；loading 复合 downloading/verifying/checking/installing [[d-090]]；进度块文案四档（安装中/检查中/校验中/下载中）[[d-085]]。
- **主按钮**：标题行下载按钮只在 missing/outdated 显示，文案「更新组件 / 重新下载 / 下载并安装」三态 [[d-080]]；取消下载按钮 downloading 显示、verifying 禁用、文案「校验中…」[[d-217]]；broken/disabled/off 缺 cloudflared 三态的副按钮 [[d-218]]；「开启手机访问」按 busy/pending/loading/Tailscale 未连禁用，启动中显示「启动中…」[[d-214]]；「关闭手机访问」停止中显示「关闭中…」[[d-216]]。
- **提示行**：chip 六档（未开启/手机已连接/等手机连接/需要更新/加载失败/已停用）[[d-211]]；lead 五分支，on 区分已连接与未连接，off 区分启动中，downloading 有专门一句「可以关掉设置继续用…」[[d-212]]；通道提示三种（Tailscale 未登录/未安装、Cloudflare 建隧道最多等 20 秒）[[d-215]]；取消后的说明有两处：missing 相位「下载已取消，没有装任何东西。」[[d-209]]、off 相位「下载已取消，现有组件没有改动。」[[d-210]]。
- **错误条**：五条、全部按相位门控——DOM 里 #phone-feature-error 与 #phone-component-error 各占一条（index.html 268/270）[[d-226]]；missing/outdated 相位的组件错误与下载失败文案（原因表 [[d-081]]、拼句 [[d-082]]）[[d-209]]；loading 相位取 notes.loading [[d-245]]；off 相位取 offErr 或下载失败或隧道断 [[d-210]]；on 相位取 onErr [[d-216]]。

### 验证码识别面板（views/settings.js）

- **阶段**：`ocrPhase` 七档，没有 running 与 disabled 档，ready 直接判 on [[d-068]]；按相位显隐四个块（missing/import-line/off-note/loading）[[d-221]]；loading 复合 downloading/verifying/checking 与 `PhonePanel.installing.relogin_ocr` [[d-088]]；进度块文案四档 [[d-222]]。
- **主按钮**：下载按钮与手机面板同一套文案规则（更新组件/重新下载/下载并安装）[[d-223]]；「启用」仅 off 相位显示、「重新导入组件包」仅 broken 相位显示 [[d-224]]；取消下载按钮 downloading 显示、verifying 禁用、文案「校验中…」[[d-225]]。
- **提示行**：chip 三档（已启用/需要更新/加载失败）加 off 相位的标题 chip [[d-219]]；lead 三分支（on/off/outdated），downloading/verifying/checking/broken 全部落到 else 的通用句 [[d-220]]；取消后的说明只有一处、且只在 missing 相位派生 [[d-228]]。
- **错误条**：只有一条（index.html 319）[[d-227]]，取值是 `installing ? "" : (OcrPanel.error || failText)`——OcrPanel.error 优先于下载失败文案，且不按相位收口 [[d-089]]。

### 差异清单（逐条）

1. 相位函数不同构：phone 有 on（服务在跑）与 disabled 档，OCR 没有；「装好未开启」在 phone 是 off、在 OCR 是 on（语义不同名）[[d-067]] [[d-068]]。
2. 错误条数量与门控：phone 五条全按相位门控 [[d-209]] [[d-210]] [[d-216]] [[d-226]] [[d-245]]；OCR 一条，OcrPanel.error 在任何相位都会盖上去显示 [[d-089]] [[d-227]]——见 ④ V1。
3. 取消后的说明：phone 在 missing 与 off 两个相位都有 [[d-209]] [[d-210]]；OCR 只在 missing 相位派生、条件还要求没有 error 与 failText [[d-228]]——见 ④ V2。
4. installing 复合检查两边都有；OCR 的 busy 还复合 `PhonePanel.busy`（手机面板有动作时 OCR 的按钮也禁用）[[d-088]] [[d-090]]。
5. lead 的下载中分支：phone 有专门一句，OCR 落 else 通用句 [[d-212]] [[d-220]]。
6. chip：phone 六档含「未开启/已停用」，OCR 三档加 off 标题 chip [[d-211]] [[d-219]]。
7. 主按钮与取消按钮的文案规则两边一致 [[d-080]] [[d-223]] [[d-217]] [[d-225]]。

## ④ 新发现的界面缺陷与代码问题

第一轮 U 系列编号不复用；本轮新编号如下。

- **V1（界面缺陷）验证码识别面板的红色错误条不随阶段收口**：`OcrPanel.error` 一旦写上（例如「打不开所在文件夹。」「没有启用，请重试。」），在 downloading/verifying/on 等任何相位都仍显示；手机访问面板的每条错误条都按相位门控，不存在这个面。代码依据：OCR 错误条取值与单条布局 [[d-089]] [[d-227]]，安装中才强行清空 [[d-088]]；对照手机面板的相位门控 [[d-210]] [[d-216]] [[d-226]]。表现为旧错误跟着新状态一起显示，用户可能把「上一次失败」读成「这次下载/启用的结论」。
- **V2（界面缺陷）取消下载后的说明不对称**：组件已装好（off/on 相位）时取消一次下载，验证码识别面板没有任何说明（派生条件要求 missing 相位）[[d-228]]；手机访问面板在 off 相位有「下载已取消，现有组件没有改动。」[[d-210]]，missing 相位也有 [[d-209]]。用户在 OCR 面板取消后得不到「没有装坏东西」的确认。
- **W1（代码问题）V1/V2 的共同根因在 paintOcrDownload 的取值条件**：错误条把 `OcrPanel.error` 放在相位判断之外 [[d-089]]，取消说明把相位收紧到 missing 并附加 error/failText 反条件 [[d-228]]；`paintOcrDownload` 里没有任何相位变化时清 `OcrPanel.error` 的路径（只有动作成功路径清它，见 installComponent 成功分支 [[d-088]] 的对照写法）。修 V1/V2 应改这一处取值逻辑，而不是各加一条清空调用。

## ⑤ spot_checks

抽样方式：从 245 条里按覆盖面抽 14 条（约 6%，含后端、前端、手机页、面板四类文件），每条用第二条访问路径（`git show 7e2d31c:<file>`，不经基线树）重新取行，与 jsonl 里的 excerpt 逐字节比对，并复核摘录语义与 claim 一致。结果 14/14 一致、摘录在各自文件全文中唯一。

| 条目 | 文件:行 | 复读结论 |
|---|---|---|
| d-002 | local/ui/app.js:106-108 | 一致；确为 check 事件清 checking、写四态 |
| d-015 | local/ui/controllers/plan.js:463-477 | 一致；确为成功分支 466 作废快照、失败分支 476-477 整份回滚（state-trace 记 457/468 确系行号偏差） |
| d-030 | local/app.py:4282-4293 | 一致；确为进程未退时保留 Api._proc、退了才收 |
| d-040 | local/ui/views/relogin.js:352-356 | 一致；确为关对话框对非电脑自动那一场发 relogin_cancel 且不等结果 |
| d-068 | local/ui/views/settings.js:152-162 | 一致；确为 ocrPhase 无 running/disabled 档 |
| d-089 | local/ui/views/settings.js:265-268 | 一致；确为 OcrPanel.error 优先且不按相位收口（V1 依据成立） |
| d-098 | local/app.py:2109-2115 | 一致；确为 _publish_update 留档、finished 才释放单飞 |
| d-117 | local/ui/controllers/refresh.js:479-484 | 一致；确为前台轮失败清 items/byId/selected |
| d-137 | local/app.py:2519-2522 | 一致；CANCEL_WORKER_TIMEOUT_S = 90 在 2521，state-trace 记 2572 系行号偏差 |
| d-164 | local/ui/controllers/plan-events.js:16-25 | 一致；确为 stopped+editing 时放回勾选、S.editing 保留 |
| d-178 | local/ui/app.js:157-158 | 一致；确为 plan_done 事件入口 |
| d-199 | local/ui/m/app.js:3131-3137 | 一致；确为网络异常分支不清在途标志、触发轮询 |
| d-230 | local/app.py:4527-4536 | 一致；确为 _spawn 锁内 _is_busy_locked 检查并置 _proc |
| d-235 | local/infrastructure/process_tree.py:235-240 | 一致；确为 terminate 注释写明 Job 终止异步收尾、poll() 几乎总是还没退 |

## ⑥ 未尽事项

1. `ui-states.md` 的阅读授权在本件初稿之后才补齐；初稿曾把 U11/U12 的内容映射反了（初稿 U11＝busyId 桥接兜底、U12＝plan_done 事件丢失），本修订已按 `ui-states.md` 的原始定义改对（U11＝停止无事件兜底、U12＝取消报名无前端超时），三条 U 的代码链路本身未变，补测建议已与第一轮「每一块动手前要先补的测试」清单对齐。
2. 三条运行期结论（U6/U11/U12）以及第 291 行的事件时序部分一律需测试定；本任务只读、没有跑任何测试或行为验证，② 里给出的只是补测方案。
3. 样式层（「检查中」的蓝点等 CSS 类）与手机页 `PhoneModel.pairView` 的 lockLeft/applyPairFailure 两个成员没有逐行核，相关总表行已标「有条件属实」。
4. state-trace 的行号偏差共记六处，都写进了总表对应行：第 28 行（457/468 应为 466/477）、第 88 行（71-73 应为 55-60）、第 90 行（步骤名是 msg 不是 result）、第 137 行（app.py:1369 的 _emit 实际在 1375）、第 159 行（「18 处比对」与基线计数不符）、第 237 行（CANCEL_WORKER_TIMEOUT_S 在 2521 非 2572）。这些都属摘录行号/计数偏差，不改变对应行的实质结论。
5. state-trace 第 291 行「窗口恢复时 bootstrap 只对账 S.busy 和 S.plan.status，不改 S.stopping」一句，按基线不准确：窗口恢复的终态快照会走 ingestBootstrapPlan → presentPlanDone，而 presentPlanDone 会清 S.stopping；运行态快照情形下原话成立。已在总表该行标「有条件属实」。第一轮 ui-states.md U11 的建议里也有同一句（「窗口恢复时 bootstrap 不改 stopping」），同样按基线修正，见 ② U11 的对齐段。
6. 「数」来源的行（inventory.md 脚本给的行号与计数）不在逐行范围；本件引用条目里涉及的字段计数（如 26 处写入、96 处写入）一律未复核。

## ⑦ 主执行方复核抽查（2026-11-12，基线 7e2d31c）

随机抽样两批共 25 条（种子 20261112 抽 13、种子 7311 抽 12，10.2%），逐条重读基线核对「原文是这几行」且「这一行真是这个意思」：25/25 成立，无推翻。抽样明细与基线原文存 plan/verify/desktop-spot.txt；verify_cites.py 复跑 257 条 0 失败存 plan/verify/desktop.txt。


## ⑧ T6 对账补记（2026-11-12，A1/A2/A4）

- **A1（静默刷新四处→六处）**：第 218 行总表已由「属实」改「有条件属实」并补 [[d-246]] [[d-247]] [[d-248]]。原逐行核对只验了「这行代码存在」，未对「四处」的计数口径复查，属重做漏，本轮补做。
- **A4（清空行号 479-481→480-482）**：经基线复核（[[d-248]] 唯一命中 479-481），第一轮原行号正确，对抗审计 A4 的修正自身算错行——本重做推翻 A4，不采纳。
- **A2（组件 C4 覆盖不全）**：state-trace 组件一节的状态表只列 6 项，第一轮 inventory 自数 PhonePanel 26 字段。本重做的四段比对覆盖了两面板的显示链，但未逐字段列全，属重做漏，补记如下（字段→决定什么）：
  - PhonePanel.state [[d-249]]、location [[d-250]]：组件状态与安装位置文案；
  - PhonePanel.pollTicks/pollTimer [[d-251]]、tickTimer/codeLeft [[d-256]]：轮询节奏与配对码倒计时；
  - PhonePanel.lastDownload [[d-257]]：下载状态留存，用于迁移提示（PH32）判断（AA1 复核：原「决定红条原因与重新下载按钮」表述不成立，已改）；
  - OcrPanel.lastDownload/note [[d-252]]、error/note [[d-253]]：验证码识别面板的覆盖说明与错误条（error 不随相位收口即 V1）；
  - 等待操作两处：启用组件（busy 进出 try…finally、失败写 notes.feature）[[d-254]]；清除保存的账号（无 busy 位、结果写 credNote/credNoteTone）[[d-255]]。
- **A3/A5/A6（1A/1B/1C 文件交集、H5 可变全局 11 vs 13、Api 属性 74 vs 68）**：属第一轮 code-issues/inventory 的范围，本计划明确不重做第一轮数字清点，本重做未覆盖，不判「重做漏」，见 plan/reconcile.md 的范围外标注。

> 计数勘误（T7）：初版头部与 spot_checks 节写 245 条，为 T6 补做前的旧数；现共 257 条（d-246..d-257 为对账新增）。
