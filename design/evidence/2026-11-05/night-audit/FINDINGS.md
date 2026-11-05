# FINDINGS — 逐条发现清单(2026-11-05 夜审计)

三档口径:**缺陷**=做错事(有证据);**风险**=可能做错;**漂移**=与文档/原型/规格不一致。三态标记:**已复现**=实际运行复现;**静态推断**=仅读代码/文档推断;**无法验证**=说明原因。修没修:只修「已复现且根因已定位」项,由代码执行者串行完成,红→绿→反向对照齐全(见 PATCHES/)。

## L1 代码层

### F-01 [缺陷|P2|已复现] 文档占位符 `<tmp>` 被夹具字面量化,Windows 上 105 例测试必红,验收门槛失效
- **现象**:本机套件 1696 例中 39 例 ERROR(OSError WinError 123 / Errno 22),server 套件 66 例全红,全部为 `'<tmp>\...'` 路径错误。
- **证据**:local/tests/test_updater.py、test_component_packages.py、test_component_builder.py、test_login_relay.py、test_phone_ui.py(:1425)、test_application_services.py、test_update_check.py;server/tests/test_activity_watch.py(:45-50)、test_watchlist_safety.py、test_runtime_safety.py、test_grab_signup_retry.py。Win32 探针:`Path('<tmp>').is_dir()`=False,文件名禁含 `<`/`>`。
- **根因**:AGENTS.md 的 `<tmp>` 是"每周清理一次"的文档占位符约定,被测试夹具当成真实路径;JS 侧(server/bot/test_bot_runtime.js:43-56 resolveRoot)有 win32 退回 os.tmpdir() 的兜底,Python 侧没有等价处理。
- **修没修**:✅ Fix A(11 文件 16 处映射 `tempfile.gettempdir()`,相对子路径与用途逐字保留)。改前 1696 FAILED(failures=1, errors=40)/server 66 failed → 改后 1696 FAILED(failures=1, errors=2,全部为已知另案)/server **122 passed 0 failed**。反向对照:代表用例 test_updater.DownloadTests::test_https_only 改回字面量→红(WinError 123),恢复→绿。patch:PATCHES/fix-A-tmp-fixtures.patch。
- F-01b [风险|P3|静态推断] 生产同款死分支 local/updater.py:33-36 `Path("<tmp>")` 恒走不到、恒回退 tempfile.gettempdir(),无害但留坑。**未修**(最小变更纪律,只记录建议)。

### F-02 [缺陷|P2|已复现] 扩窗路径重读业务时钟,违反仓库不变量「clock_now 只在入口取一次」,守卫测试长期红
- **现象**:`test_backward_clock_recalibration_cannot_extend_monotonic_duration` 稳定 FAIL:`AssertionError: 2 != 1`。
- **证据**:断言 local/tests/test_retry_phone_policy.py:512;第二次读数 local/application/plan_service.py:304(进度事件分支统一 `event_now = clock_now()`);domain/retry_rules.py:57-77 对 window_extended 返回 `{}`——读数算出即丢弃;引入提交 6a46032(2026-11-03,`git log -S` 定位)。扩窗数学本身不受污染(增量只由 candidate−accepted 决定),是"测试与实现意图冲突"+无效读数。
- **根因**:feed() 进度事件分支未按 kind 门控读钟;真正消费 event_now 的只有 login_wait(retry_rules.py:60-63 login_wait_until 换算)。
- **修没修**:✅ Fix B(读钟收进 `kind=="login_wait"` 门控,其余传 None,行为逐字不变;domain 未动)。改前红(2!=1)→改后单测 OK+全模块 25 OK+test_signup_plan/test_ui_contract 347 OK;反向对照:撤门控→红,恢复→绿。patch:PATCHES/fix-B-clock-single-read.patch。

### F-03 [缺陷|P2|已复现] `_component_service_for` 急切求值缺失属性,任何未走完整 __init__ 的实例一碰组件查询即 AttributeError
- **现象**:`test_release_audit.ApiComponentCoordinationTests.test_online_download_reserves_existing_advanced_operation_guard` 报 `AttributeError: 'Api' object has no attribute '_ocr_component_service'`。
- **证据**:local/app.py:1121-1124 字典字面量两个 self 属性先求值再 .get(key);测试 setUp(test_release_audit.py:17-31)用 `Api.__new__` 绕过 __init__ 只补 `_component_service`;同文件 shutdown 收口 app.py:2688 用 `getattr(self, name, None)` 防御——两种风格不一致。
- **根因**:急切求值 + 属性存在性未防御。
- **修没修**:✅ Fix C(mapping 存属性名,`getattr(self, name) if name else None`,对真实 Api 行为一字不差)。改前红(errors=1)→改后单测 OK+test_release_audit 7 OK+test_ui_contract/test_runtime_bundle 343 OK(PYTHONPATH=local);反向对照:HEAD 急切求值→红,恢复→绿。patch:PATCHES/fix-C-component-service-lazy.patch。附:Fix C 证实 test_runtime_bundle.py 需 `PYTHONPATH=local` 调用形态(直接 `python -m unittest local.tests.test_runtime_bundle` 会 ModuleNotFoundError,已反证与本修复无关——HEAD 态同样复现)。

### F-04 [缺陷|P3|Fix D 转已复现] update.js 把后端 launching 第二段文案丢弃
- **现象**:安装器启动成功后,后端发 state="launching" 且文案换为「安装程序已启动。请先关闭本工具,再按向导完成安装。」(local/app.py:1701-1705),前端固定渲染「正在启动安装程序…」(update.js:30),指引不再上屏。
- **根因**:文案 1:1 照抄原型 Main:1261-1276 时把动态 `result.text ||` 去掉;契约测试状态循环不含 launching,无钉。
- **修没修**:🔧 Fix D(新增契约测试红→修 update.js 恢复 `result.text ||` 兜底→绿+反向对照)。结果见 PATCHES/fix-D-update-dynamic-text.patch 与下文 Fix D 小节。

### F-05 [缺陷|P3|Fix D 转已复现] update.js 的 no_installer 固定文案覆盖后端三分类原因
- **现象**:后端区分「没有可校验的安装包」(update_check.py:219-222)、「安装包校验信息不可用」(:224-228)、「安装包大小与校验信息不一致」(:229-231);前端固定渲染第一类(update.js:23),后两类被错报。
- **根因**:同 F-04。
- **修没修**:🔧 Fix D(同上)。

### F-06 [风险|P3|静态推断] 空 flow_id 的重新登录 success 事件没有去重依据
- **现象**:local/ui/views/relogin.js:158 `if (flow && flow === reloginRefreshedFlow) return;`——flow 为空串时每次都放行 `doCheck()+refresh(true)`;注释自称"放行一次",实际"放行每一次";若中继重放多个无 flow_id 的 success 快照,列表被反复打回加载态。
- **缓解**:现行后端事件均带 flow_id(测试全带),现网风险低。
- **修没修**:🔧 Fix E(哨兵去重,匹配注释意图;红→绿→反向对照)。见 Fix E 小节。

### F-07 [漂移|P3|静态推断] 帮助快捷键清单与键盘行为的两处出入
- **现象 A**:新快捷键清单删了「Enter 焦点不在输入框时开始报名计划」,但行为仍在(app.js:484-490)。存在而未记载。
- **现象 B**:清单写「空格 勾选或取消当前活动」,而 app.js:173-179 实现是「Enter/Space 只翻转 aria-expanded」(焦点在 .c-place 上时 Space 是展开地点),勾选仅在焦点位于 checkbox 上时原生生效。
- **说明**:assistance-panels.md 已同步五键清单,规格与 UI 不漂移;漂移发生在"帮助文案 vs 代码实际行为"。未修(文案取舍属产品口径,记录)。

### F-08 [漂移|P2|静态推断] 服务器版报名回包登录失效判定用子串匹配,违反决策 006/015「只认 4001」口径(本机已修,服务器独立实现未同步)
- **证据**:server/deploy/grab_signup.py:530-532 `"登录" in message or "身份验证" in message` 即判 login_invalid;对照 local/domain/signup_reply.py:86-88(仅 code=="4001")与 local/grab.py:2688-2692 注释;决策 006:19、015:38-43。
- **附加差异**:server 单次 4001 立即判死,无本机版 1.5 秒复查(决策 003:23「连续两次才算失效」);fetch.py 有 4001 重试,报名路径没有。
- **后果**:任何含「登录」字样的业务回包会当场终止本场真实报名并私聊误报。
- **修没修**:❌ 未修——需真实学校回包验证行为,按硬边界不访问学校接口;属"已定位但未复现",记 BACKLOG/DEFERRED。

### F-09 [风险|P3|静态推断] 服务器报名执行链依赖「部署时区=Asia/Shanghai」隐式前提,无本机版式 UTC+8 防护
- **证据**:grab_signup.py:764/768 naive strptime→timestamp;watchlist.py:126、grab_card.py:64-79 datetime.now();对照 common.py:136-143 显式 business_now()+08:00 且注释自警。docs/OPERATIONS.md:9 要求部署时区 Asia/Shanghai——前提成立时无害,迁机即静默错位。未修(部署前提问题,记录)。

### F-10 [漂移|P3|静态推断] 服务器版 BurstPolicy.settle 按结算序累加 404 连击,乱序迟到 404 可重建连击并重进 adaptive 扩窗
- **证据**:grab_signup.py:344-350;对照本机 grab.py:1610-1631 发送序倒扫(1843-1846 注释「旧 404 后到不得重建连击」)。仅节奏/扩窗影响(上限 25 分钟、sign_end 硬截),不产生错误提交。未修(与 F-08 同属 server 独立实现漂移,需真实回包验证)。

### F-11 [漂移|P3|静态推断] 服务器版 is_joined 把「查询失败」当「未报名」
- **证据**:grab_signup.py:98-103(code!=1→False,网络异常 code=-1 也 False);对照本机三态 grab.py:868-886(查询没成功返回 None,注释明说后果)。开抢前核对失败→照常提交;学校以 conflict/4001 兜底,后果=有界浪费而非学校侧重复报名。未修(同上)。

### F-12 [漂移|P3|静态推断] 遗留 tkinter 壳 gui.py 三处漂移(无启动器入口,非产品路径)
- **证据**:gui.py:328「大约能用 17 小时」vs UI_SPEC.md:321「不编 17 小时」;gui.py:852/1022 naive strptime 本机时区折算(signup_plan.py:18、time_contract.py:6-11 明令禁止);gui.py:1071 proc.terminate() 不杀浏览器树(对照 app.py 经 process_tree.py Job Object)。launchers 实际启动 app.py。未修(遗留壳,B7 决定是删除——见 F-26)。

### F-13 [风险|P3|静态推断] auto_login.py 的 storage_state 与 session 两次独立原子写,无跨文件事务
- **证据**:server/deploy/auto_login.py:414-427;对照本机 grab.py:383-425 save_verified_files 双文件事务(第二文件失败恢复原字节)。中间崩溃留"新 storage+旧 session"错配,5 分钟 timer 下一轮自愈。未修(服务器无人值守场景,改动需真机验证)。

### F-14 [风险|P3|静态推断] ClockClient 每次读数完整读盘+JSON 解析,黄金风暴按 90ms 节奏放大
- **证据**:business_clock.py:739-791;grab.py 主循环每拍 2-3 次读盘。Windows 文件缓存单次<1ms,实测不构成瓶颈(本机 229 例含时钟全过)。余量问题非正确性。未修(记录)。

### F-15 [风险|P3|已复现(间歇)] test_login_state_hours_left_is_always_none 间歇 PermissionError(WinError 32)
- **证据**:Fix A 后全量跑三次出现一次;traceback 在 `tempfile.TemporaryDirectory()` 退出清理(ui.json 句柄被占用);单跑必绿;Fix A 沙盒回退基线复跑同样出现——非 Fix A 引入。建议:该夹具加 `ignore_cleanup_errors=True` 或排查句柄泄漏。未修(间歇性,根因未完全定位,记 BACKLOG)。

### F-16 [观察项,不计发现] plan-panel.js:41 注释与实际条件措辞矛盾(代码行为与原型一致);tick.js:124-128 把"已登录仍拉不到列表"钉成固定网络话术(V1/V3,后端架构师/代码审查员观察项)。

## L2 原型层(详见 PROTOTYPE-GAP.md,99/99 逐条)

### F-17 [漂移|P2|已复现(文档比对)] prototype-gap.md 台账自身 10 处记录错误 + 14 条已过时
- 演示控件数「13」不成立(实际 16 处标注/19 行/19 个控件);S2/P17/P11 原型侧描述错误;P21/M24 应剔除;M7/P9/P20/S24 结论过时;台账 2026-11-04 20:45 定稿后实现继续改,14 条(W4/W8/W11/W16/P13/P17/P20/S3/S10/S11/S16/S17/S18/S23)已修复。

### F-18 [漂移|阻断级(产品范围留人定)] 99 处中 72 条未实现 1:1
- 集中区:手机页 M1–M25(整块,除 M7)、计划栏结果态 P1–P8、设置抽屉 S24–S30;另 10 条部分偏差、15 条已 1:1、2 条不计。
- 按任务书口径「原型有的必须 1:1 实现,未实现即阻断」全部成立;但落地为数天工程,不属于今晚修复范围(只修已复现且根因已定位的缺陷),处置排期留人定(DEFERRED.md)。

## L3 契约文档层(63/63 逐条,详见 L3 报告)

### F-19 [结论] §9 63 条:已验 60(其中 7 条带漂移注记)、blocked 3(#14 五视口渲染、#30 runtime-check 实包、#57 680×480 真实指针——均需真实环境实跑,QA 工具与场景已就绪)、未覆盖 0。契约主测试 test_ui_contract.py 286 例全绿;41 红无一落在 §9 证据链上。

### F-20 [漂移|P3] §9 七条旧口径残留(#24 登录预计还剩、#25 估算提醒、#26 六步、#27/#39 版本入口在帮助、#61 时钟五态缺 retrying、#63 登录剩余按条件报数)——实现与测试已推进到更严格版本,§9 未回改。

### F-21 [漂移|P3] assistance-panels.md §3 七态表落后 update.js 实际状态机(缺 no_installer/confirm/downloading/verifying/ready_to_install/launching;「查看发布页」已改「下载并安装」)。

### F-22 [漂移|P3] copywriting.md 三处:§10:192/195 浮层「登录预计剩余时间」残留——**实现已删且契约测试 test_ui_contract.py:1007 断言不得出现,文档与测试互相矛盾**;§11:224-230 六步 vs 实现五步(store.js:31-39,测试钉住);§2/§7/§15 三条「抢单旧标签待收敛」注记已过时(用户可见字符串已无抢单)。

### F-23 [漂移|P3] versioning-and-release.md 基线行与 v1.2.0 manifest 事实并存观感不一致(非规则冲突);README.md:256 版本候选口径过时(见 F-29)。

### F-24 [漂移|P4] specs/README.md 索引漏 terms-consent.md;对 assistance-panels 的描述仍是旧「六步引导」口径。

## L4 决策层(详见 DECISION-CHECK.md)

### F-25 [缺陷(流程)|P2|已复现] B5 回执标「已完成」但仓库未落地
- 验证码文案 index.html:370 仍旧、014:55 仍「未确认」、redesign-design.md:322 待定项仍在。

### F-26 [缺陷(流程)|P2|已复现] B7 回执标「已删除(工作区)」但 local/gui.py 仍在且与 HEAD 一致
- 回执自身重做记录(receipt:141「25 个文件 git checkout,gui.py 恢复」)与「已删除」自相矛盾。

### F-27 [缺陷(流程)|P2|已复现] C1 规格红线残留 copywriting.md:195(与 F-22 §10 条目同源)
- B5/B7/C1 三处"回执说做了、仓库里没有"高度疑似同一根因:收据 :139-142 自述的中途清空重做还原了这批文件后未重做。**处理方式(重做改动 vs 修订回执)属交接流程,留人定(DEFERRED.md),今晚不擅自重做。**

## L5 发布层(详见 RELEASE-STATE.md)

### F-28 [blocked] v1.1.1「已发布」声明在本机不可追溯(git tag=0)
- 任务书预告结论成立;需 GitHub Release 侧证据,本审计无网络授权。

### F-29 [漂移|P3|已复现] README.md:256「版本仍为未发布 1.1.1 候选」与 VERSION=1.2.0、CHANGELOG「1.1.1 已发布」矛盾
- 未擅自改(发布口径属产品声明,记 DEFERRED)。

## 密钥与凭据治理(正面结论,无缺陷)

- 真密钥 **0**(当前 469 文件 + 近 7 天 68 笔历史新增行);43 条字面量命中全部为示例占位/测试夹具固定值/非密钥。
- 两条硬编码常量(grab.py:62-63 REQUEST_SECURITY_RAW_KEY/CLIENT_KEY、AUTH_CLIENT)为**学校官网公开前端 JS 内嵌协议常量**,非用户凭据,仓库内已有决策/证据跟踪(2026-11-02 audit:144、架构方案 :194 整改方向),建议按 spec 推进搬移(记 DEFERRED)。
- AGENTS.md 规则(日志/文档/提交信息不含账号密码验证码 token 学号):抽查全合规;contracts 样例已脱敏;log_events.py:25 黑名单在位。
- 凭据机制与文档宣称一致:DPAPI(credential_store.py:24-58)、server 600 权限(auto_login.py:154、common.py:159、atomic_json.js:52-53)、token 指纹化(token_probe.py:194)。
- .gitignore 覆盖完整:server/config.json、local/config.json、local/data/、server/data/、dist/ 等全命中,跟踪列表无 config/.env/.pem。
- 静态扫描兜底:eval/exec 在生产代码 0 处(29 处命中=归档原型 JS 的正则 .exec() 与测试受控片段);shell=True 0;bare except 0;except:pass 在真实代码 0 处(2 处命中在证据文档里引用该模式);生产 naive datetime 46 处分诊=日志/展示戳良性 + server 业务判断(即 F-09)+ lifecycle 本机经过时长(设计如此)。

## 修复记录汇总(代码执行者串行,全部红→绿→反向对照)

| Fix | 内容 | 改前 | 改后 | 反向对照 | patch |
|---|---|---|---|---|---|
| A | `<tmp>` 夹具映射(11 文件 16 处) | 1696 FAILED(f=1,e=40)/server 66 failed | 1696 FAILED(f=1,e=2)/server 122 passed | test_https_only 红↔绿 | fix-A-tmp-fixtures.patch |
| B | plan_service 时钟单读门控 | 单测 2!=1 红 | 单测+25+347 全绿 | 撤门控红↔恢复绿 | fix-B-clock-single-read.patch |
| C | _component_service_for 惰性化 | AttributeError e=1 红 | 单测+7+343 全绿 | HEAD 态红↔恢复绿 | fix-C-component-service-lazy.patch |
| D | update.js 动态文案透传(2 状态)+新契约测试 | 2 新用例红 | 全量 test_ui_contract 绿 | 改回固定文案红↔恢复绿 | fix-D-update-dynamic-text.patch |
| E | relogin.js 空 flow_id 哨兵去重+新测试 | 新用例红 | 相关模块绿 | 撤哨兵红↔恢复绿 | fix-E-relogin-empty-flow.patch |

## 观察项(不计发现)

- V1 plan-panel.js:41「具体原因看左边列表」指向的空态文案已是固定话术,特定失败原因不上 UI——原型本身就是该组合,1:1 继承。
- V2 plan-panel.js:46 注释「加载态与有没有选中无关」与实际条件 `!items.length` 措辞矛盾,代码行为与原型一致,仅注释误导。
- V3 test_ui_contract.py 新增 test_list_failure_uses_prototype_copy 把"已登录仍拉不到列表"钉成固定网络话术,与 list.js:250 旧注释语义不一致,建议后续统一措辞。
- 正面确认:D3 _join_state 保守判据与决策逐条一致且 6 用例钉住;00e1bce 登录态写锁无绕锁残留;5781bab 飞书推送内容干净;e16d268 凭据中继 stdout 无敏感字段;b0e4448 预检取舍如实披露;AGENTS.md 硬边界(只服务本人账号/不批量占位/只点指定活动)在 grab.py、grab_signup.py、bot.js 全面检查无违反。

## 第二轮追加(2026-11-05)

### F-30 [缺陷|P2|已复现] HEAD 固有:test_state_exposes_download_snapshot_for_phone_control_only 与 HEAD 的 advanced_features_state 自相矛盾
- **现象**:提交树 099ded3(=HEAD+五修)全量验证 1682 例中此用例 FAIL:断言 relogin_ocr 无 'download' 键,实际该键存在('ddddocr 走已装依赖,没有下载概念')。
- **归因**:在纯 HEAD(4ec0b3d)的临时 worktree 单跑同用例同样 FAILED → **HEAD 固有矛盾,非五修引入**。既有 27 项改动已把该用例重写为 both_components 口径(工作区绿)。
- **关联**:提交树另 1 个 ERROR(test_mobile_layout_statics 的 `<tmp>` Errno 22)为计划内遗留——该 A hunk 嵌在既有 27 项内,commit body 已声明。
- **三态**:已复现(两个树各跑一次)。处置:登记不修(修=动既有 27 项,越权)。
