# 验收记录 2026-10-31（B02 起，逐切片落盘）

- 工作树：`campus-activity-watch-acceptance` @ `wip/ui-acceptance-20261030`（本地分支，不 push）
- 基线：单测 `Ran 1084 tests / OK (skipped=4)`；条款 10 场景 10/10（`acceptance-evidence/20261031-baseline/`）
- 口径：本记录全部为**源码线**（工作树 HEAD 实测行为）；实包线仅在明确标注处出现，两者禁止混谈。
- 分级：通过 / 缺陷 / blocked（无法验证）/ unproven（证据不足以判通过）。

## B02 登录态四态
- 结论：通过 8 / 缺陷 1（已修）/ blocked 0 / unproven 2
- 判据：`docs/UI_SPEC.md` §5.9（启动校验四态、`result ∈ {valid,expired,unknown,none}`、`hours_left=null` 口径、开始门禁、refresh 失败落 unknown、重登快照回滚、`request_id` 代次丢弃）
- 证据：`acceptance-evidence/20261031-b02/`（8 份场景报告、7 张截图、反向对照红/绿、全量单测日志）
- 缺陷与修复：`owner-reuse-cross-round` 日志计数断言 `[0,0]` 恒真空过——根因 `local/ui/app.js:107` 文案「已复用本机登录状态」与契约「已复用本机登录**态**」一字差，needle 按契约写法永远数到 0。修复：文案对齐契约 + 场景补存在性断言（`before >= 1`）。反向对照：旧文案下新断言红（detail=0），修复后 `[1,1]` 绿。提交 `3ee2b7d`。
- 审阅：无 🔴；🟡×2（README:158 同源残留、快速契约守护缺失）→ 同轮收尾提交处理；💭×2（存在性断言来源可含 boot 轮、§5.9 无 5.9.4 小节编号引用）记录在案不改。
- unproven：①非 valid 态 + 已选择 → `#btn-plan.disabled` 四态 DOM 矩阵（缺场景断言；后端用例 + 源码级用例已双向钉住）②浏览器级重登取消/失败场景（bridge 已支持 `loginOk`，缺场景）→ 已记 BACKLOG。
- 关联：`legacy-session-valid-no-estimate` 2/6 红**已定性**为场景断言停旧基线（产品 c98776c 有意改版且被单测钉死）→ 归 B08 收口，见 BACKLOG。

## B03 活动列表与筛选
- 结论：通过 9 / 缺陷 0 / blocked-unproven 3
- 判据：§5.6（三态归一化/筛选语义/行内四态文案/偏好/隔离/静态回归）、§5.7.1+§5.13.10（失败归因唯一）、§5.13.5+§5.14.7（加载态/已知零）、§5.10.2（已截止门禁）、§5.14.6（清筛选六键）
- 命名口径：任务书「待签到/已签到」实为契约的「**需要/无需**」（`checkin_required`/`checkout_required` 活动要求字段 tri-state），按 §5.6 验收。
- 证据：`acceptance-evidence/20261031-b03/`（4 份场景报告 + 补充驱动 36 断言 qa-report-b03-extra.json + 10 张截图；后端 `closed_items_error` 实跑输出带活动名+截止时间）
- 提交：无代码改动，本记录即落点。
- unproven/blocked：①重载恢复整环——QA 桥 `prefsInfo()` 不回放 filter，缺能回放的桥或真机后端（后端落盘部分归 B16）②真实学校详情接口（sfxyqd/qdkssj 等）只有静态/单测证据，**永远 blocked**（需真实学校窗口）③「没登录/登录失效 + 列表失败」归因分支缺浏览器级场景（bridge 可造，已记 BACKLOG）。

## B04 选择冲突与开始门禁
- 结论：通过 8 / 缺陷 0 / blocked 0；**同时关闭 B02-unproven-1**（四态×已选择→disabled 矩阵）
- 判据：§5.10（act 只用于冲突）、§5.6.6（跨批次冲突+筛选隔离）、§5.9.6（开始门禁）、§5.11.3+§5.10.8（估算=提示不拦截）、条款门
- 证据：`acceptance-evidence/20261031-b04/`（17 张截图 + conflict-selection 场景 11/11 + 自研驱动 78/78 + 后端直调 28/28 `b04-backend-report.json`）
- 关键判定：①冲突三层防线（勾选拒绝→validateSelection→后端 activity_overlap，半开区间）②登录估算撑不到窗口=橙色提醒且开始可用（`board.js:246-265` 只提醒；`updateControls` 不读 expireAt），与 §5.11.3「估算不得参与放行/拦截」一致 ③demo 只绕登录门禁，冲突/空选择/已截止照拦 ④checking/unknown/none/expired 四态全禁用开始且刷新/登录可点，全程零 start_plan 调用
- 观察（非缺陷，记 BACKLOG 批处理）：①§5.10.8 已开放场次 `base=now` 分支缺行为级用例 ②`plan_rules.py:93-98` 把非冲突类失败包进「不能同时报名」文案（直调消费者可能被误导）③条款未同意时 boot 胶囊显示「检查登录…」而 refresh 实际被拒（`login.js:35` + `refresh.js:123`），fail-closed 但文案误导
- 提交：无代码改动，本记录即落点（48db059）。

## B05 报名计划执行
- 结论：通过 8 / 缺陷 0 / blocked 1 / unproven 2（轻缺口）
- 判据：§5.10（快照定格/lead_s=100 提前准备/同刻同启/重试不阻塞/checkpoint 先到先得）、§5.14（executionView 唯一模型/批次数=非终态且 attempts>0/任务级 vs 计划级分层/整屏 data-plan-state/taskDisplayPhase）、§5.8.4-6（attempts 只数真实提交/stop_reason 枚举）、§5.7.3/5.7.5/5.7.7
- 证据：`acceptance-evidence/20261031-b05/`（后端直调 30/30 `b05-backend-report.json`、4 份场景报告+5 张截图、worker 全模块 156 用例 OK、test_signup_plan 58 OK、test_ui_contract 225 OK）
- 关键实证：同准备时刻两场启动间隔 0.0s、重试场阻塞 6s 时未来场仍按自己准备时刻 +1.64s 启动（无批次 join）；plan_done 恰一次（`_finished_plan_ids` 守卫）；忙互斥返回人话且 plan_done 后解除；「未确认」不画失败叉、停止后待核对保留；max_attempts 终态与进程级 can_attempt 三重封禁
- unproven：①`headed` 开关进入 start_plan 载荷缺契约用例（代码链证据 plan.js:46 实时读 DOM）②失败后自动静默复查 `refresh(true)` 无回归守护（plan-events.js:145-151 代码证据）③真实学校窗口端到端 = **永久 blocked**
- 提交：无代码改动，与 B06 记录同笔 docs 提交落盘。

## B06 重试策略与扩窗
- 结论：通过 7 / 缺陷 3（已修）/ 文档冲突 2（已裁定修文档）/ blocked·unproven 4
- 判据：`docs/RETRY_POLICY_GUIDE.md`（本切片权威）+ UI_SPEC §5.8；选项集合实测 6 项 `[120,600,1800,3600,-1,0]`（任务书口径少列「1 小时」，实现与指南一致）
- 三方对照：实现↔权威指南一致；UI_SPEC:235 枚举缺 -1、:239 节奏表滞后（两处已修文档，81f670f）
- 缺陷与修复（反向对照证据 `20261031-b06/fix{1,2,3}-red/green.txt`）：
  - ①done 行 `last_reason` 粘尾、`pending/streak_404/phase` 不可解析（发射居中 vs 解析契约「恒为末字段」）→ `51ae316` 发射端挪行末，解析器零改动
  - ②无终态行退出时兜底分支 attempts 归零（plan_rules.py:200-204）→ `33f85ff` 改 `with_attempts(stop, attempts_seen)`，如实入账
  - ③UI_SPEC:240 阶段显示从未实现 → `e2dbca3` plan_service/retry_rules 转发 phase + 任务卡显示「黄金风暴/常规全速/404 自适应」（未知/缺失不显示）
- 审阅：无 🔴；🟡×1（指南 :105 对服务器副本「完全相同」声称不实）→ `a9376f7` 如实注记；💭：用例名名实不符 → `feaaf6e` 重命名；`board.js:645` 写法 nit 记录不动
- 裁定记录：`acceptance-evidence/DEFERRED-DECISIONS.md` D-B06-01（404 节奏语义改文档不回退实现）/ D-B06-02（阶段显示补实现不删契约）/ D-B06-03（server/deploy 副本旧语义本轮不同步，记 BACKLOG）
- blocked/unproven：①**C01/RISK-001**（页面自发同路径请求可能计入提交统计，指南 :125-182 自declared，恒 blocked，发布验收必须显式写出）②真实学校接口 404/429/扩窗全链 ③真机/实包形态 ④手机真机链路——均缺真实环境/授权
- 提交：51ae316、33f85ff、e2dbca3、81f670f、a9376f7、feaaf6e；全量单测 Ran 1089 / OK (skipped=4)

## B07 停止与结果对账（补录：初版记录落盘时遗漏本节，内容依据 20261031-b07/ 证据补写）
- 结论：通过 8 / 缺陷 0 / blocked 1（unproven 3，均属其他切片/真实环境）
- 判据：§5.7.8（停止时限与顺序/幂等）、§5.8.5+§5.16.2（「结果未确认」如实成态）、§5.14.5（任务级 vs 计划级分层）、§5.17.4/5.17.10/5.17.12（结果分类贯穿/终态快照/停止入口归属）、§5.16.8
- 证据：`acceptance-evidence/20261031-b07/`（后端直调 23/23 `b07-backend-report.json`、前端真实点击 9/9、停止标签 5/5、场景 stopped-unconfirmed 8 断言、unknown-outcomes 13 断言、f5-terminal-restore 12 断言、全量单测 1089 OK 日志）
- 关键实证：停止链 **140ms 收树**（判据 ≤1 秒），引导进程+孙进程随树死亡（tasklist 实证）；重复 stop_plan 幂等返回人话不挂起；未决场保留 attempts=3+「待核对」+locally_stopped、排队标 canceled、`plan_done` 恰一次 status=stopped；停止前已收「已报过/报名成功」结论保留不改写（退出码非 0 不掩盖）；`taskkill` 仅 `/F /T /PID` 形式、全库无 `/IM` 扫杀（test_kill_tree_is_pid_only）；F5 终态恢复不重发 start_plan；取消路径不等管道 EOF（canceled 即可 break）
- 备注（非缺陷）：收尾极快时重复 stop_plan 返回 `ok:false`+人话——幂等契约合法分支，实现/测试/界面三面对齐
- unproven：①onefile 实包真机停止链（B15 已补 runtime-check 与 GUI 取证）②手机端停止入口（B13/B14 暂缓）③真实报名窗口的未决笔数乱序结算（永久口径）
- 提交：无代码改动，本节即落点。

## B08 运行时间线与 F5 恢复
- 结论：通过 6 / 缺陷 2（已修）/ blocked 0 / unproven 1；**三条红灯场景全部定性并转绿**
- 判据：§5.16/§5.17（事件按代次归属、恢复、断线整体重置、浮层同源）、§5.7.3+§5.10.7（mergeTask 不空值抹 checkpoint）、§5.10.9（路线图只认真实 checkpoint）
- 证据：`acceptance-evidence/20261031-b08/`（6 组场景/驱动报告 + 三条红灯原始输出 + 反向对照红/绿 + after-fix 报告）
- 关键实证：旧计划迟到三类事件不劫持（`stop_plan` 实参指向正确计划）；同会话与 F5 后快照缺字段不用空值抹 attempts/checkpoint；断线重连 attempts 9→2 整体重置不拼接假连续；armedAt/open-100/open-5 注入不冒充站点时间；恢复全程 start_plan=0
- 缺陷与修复（反向对照齐全）：
  - ①DEF-1/DEF-2 时钟浮层不随状态收口重画（§5.16.13 同源契约；校准失败后浮层按钮永久锁死，用户可感）→ `007dddb` state/clock.js 四处收口补 `renderClockPop`（state→views 直连即仓库既有模式）+ 行为式单测；cold 9/9、manual 10/10 绿
  - ②`legacy-session-valid-no-estimate` 场景断言停 9afc7f0 旧基线（产品 c98776c 有意改版，被 test_ui_contract.py:1614 用例钉死）→ `8205dcf` 断言反转为 5 条正向（与契约同向，行为变了才改断言）；legacy 9/9 绿
- 审阅：无 🔴🟡；💭×4 记 BACKLOG 低优先（:108/:72 单行删除仅浏览器场景兜底、提交信息行号随 HEAD 漂移、paintClockPopFeedback 双调为既有代码）
- unproven：真实 worker telemetry → 协调器持久化 → bootstrap 端到端（需真实报名窗口，永久口径）
- 提交：007dddb、8205dcf；全量单测 Ran 1090 / OK (skipped=4)

## B09 生命周期与关闭时长
- 结论：通过 8 / 缺陷 0 / blocked 0 / unproven 4（均属实包/真机线）
- 判据：§5.11.1/5.11.2（原子写、心跳、进程内同锁、跨进程排他事务、三分口径、v2 quality）、§5.13.6（关闭收尾顺序）、§5.13.9（关闭屏障与创建同锁）
- 证据：`acceptance-evidence/20261031-b09/`（直调矩阵 42/42、回环真后端 F5 3/3、四模块单测 129 用例全绿）
- 关键实证：崩溃残留法证明启动三件套同批原子写；60 次 update_prefs 与心跳并发交错互不丢键（真双进程持锁 0.4s 阻塞且合并不覆盖）；`taskkill /F /T` 真跑收登记进程、外部进程存活、shutdown 0.34s；关闭时长三分 13 矩阵（回拨 unknown 不给时长、旧格式矛盾降 abnormal、v2 quality=unknown 不沿用旧 epoch）；F5 前后 bootstrap.lifecycle 逐键一致；shutdown 中四入口拒绝话术无 error 字段（非组件码）；lifecycle 字段零进入 session.json/storage_state.json
- unproven（缺实包/真机轮）：①真窗口点 X 关闭 continue/stop 弹窗与关闭耗时 ②onefile 实包资源根消失的孤儿回收 ③真实 grab-worker+playwright 整树终止 ④qa 工具无 lifecycle 场景（专用回环真后端桥补位）
- 观察（非缺陷）：条款门先于关闭门（app.py:882/906/1129），四入口拒绝话术以同意条款后实测为准
- 提交：无代码改动，与 B08 记录同笔 docs 提交。

## B10 六步引导
- 结论：通过 8 / 缺陷 0 / blocked 0 / unproven 1（真机级落盘回路，归 B15 真机轮）
- 判据：§5.11.4/5.11.5（六步与目标、内容版本判定、重播单入口、键盘边界、重定位与窄窗回退、运行中暂停、禁代操作）
- 证据：`acceptance-evidence/20261031-b10/`（自建驱动 38/38 断言 0 异常 0 外联、keyboard-dialogs 9 断言、5 张截图、单测 280 OK）
- **welcome_seen 定性：设计保留，非缺陷**——旧版 Tkinter 欢迎弹窗时代的兼容键（gui.py:453，已停用界面）+ 桌面 web「首次兜底弹帮助已消费」标记（app.js:45-53）；六步引导自动开始只读 `tour_version`（tour.js:7-13，函数内无 welcome_seen），首启写 true 与引导照弹并存。建议处理（产品口径，记 BACKLOG）：§5.5 键表语义可改「首次说明兜底已消费」或随 gui.py 退役
- 关键实证：完成/跳过 `savePrefsNow` 立即落盘且同版本不再弹；tour_version=1 旧完成记录被新内容版本重弹（`>=` 判定）；重播唯一入口行为（关帮助/焦点回 #btn-help/startTour(0)/运行中禁用带文案）；Esc=跳过、Tab 首尾循环、背景 Ctrl+F/`/`/Enter 隔离；render 重定位不重开、≤980 退回底部说明条；引导代码零 `login/start_plan/check/list_activities` 调用（grep 0 + 契约双保险）
- 小瑕疵（记录）：test_ui_contract.py:826-827 docstring「两处重播入口」过时（断言本体无冲突）→ BACKLOG
- 提交：无代码改动，落 docs 提交。

## B11 帮助与检查更新
- 结论：通过 8 / 缺陷 0 / unproven 3 + 夹具失真 1（本轮修复）
- 判据：§5.15（决策 011 单入口帮助，取代 §5.13.1 双入口）、§5.11.6（版本唯一显示位/固定下载地址/失败局部反馈）、§5.18（检查永不自动下载、下载双确认）、§5.13.2（弹窗键盘隔离）
- 证据：`acceptance-evidence/20261031-b11/`（自建驱动 30/30、update-five-states 19 断言、keyboard-dialogs 9 断言、10 张截图、三模块单测 122 用例全绿）
- 关键实证：版本三处一致（VERSION 文件==bootstrap==帮助显示）且唯一显示位、不写死候选号；启动/开帮助/F5 后 `check_update` 调用恒 0、外发请求 0；下载需「下载并安装→确认下载」两道确认；`open_latest_release` 无参仅开 `RELEASES_LATEST_URL` 常量、WebView 不导航、不收任意 URL；失败仅在帮助内局部反馈+固定地址摆可选文本；未登录/组件失败/列表失败/运行中四态帮助可用且单模态
- 夹具失真（非产品缺陷）：`runtime_bridge.js:545` check_update 替身发 epoch 秒，生产契约 ISO（update_check.py:110）→「检查时间」Date.parse 得 NaN 被隐藏——会误导未来依赖该事件的场景；本轮修夹具+场景断言钉死
- unproven：①`os.startfile` 真实唤起系统浏览器（缺真机 EXE 轮）②实包版本链与启动零外联（归 B15/§5.13.8 门禁）③真实 GitHub 链路（纪律不真访，mock 已证全部分类）
- 夹具修复：`7812a3d` test(qa) check_update 替身 checked_at 对齐 ISO 契约（复用桥内 clockNowS()），update-five-states 补「检查时间可解析」断言，反向对照红→绿精确命中，20/20 绿
- 追记 follow-up（记 BACKLOG）：桥夹具 `current/latest` 与生产 `current_version/latest_version` 字段名同类失真（current 态未被前端消费）；`test_phone_http.RejectionTests.test_oversized_body_is_rejected` 一次全量偶发（单跑/干净 HEAD 全量/复跑均绿，判定既有偶发，值得单独排查）
- 提交：7812a3d；本记录落 docs 提交。

## B15 分发形态
- 结论：通过 8 / 缺陷 0 / blocked·unproven 3；**每条结论已分标 [源码线]/[实包线]**
- 判据：§5.12（VERSION 唯一来源/manifest/ZIP 白名单）、§5.13.7/5.13.8（--runtime-check 与实包门禁）、任务书旧包预警
- 证据：`acceptance-evidence/20261031-b15/`（runtime-check 两份报告、GUI 三张截图、资产 SHA-256 对照、单测映射）
- **[实包线] 关键实证**：manifest 逐项核验全对——version=1.1.1、完整 HEAD=a57a3cb、`source_dirty` 显式布尔 false、三资产 SHA-256+字节数全一致、ZIP 成员恰 4 项白名单、ZIP 内主 EXE 与单独 EXE 字节一致；`--runtime-check` 真跑退出码 0（5 秒，报告脱敏：`{"version":"1.1.1","frozen":true,"worker":"..._MEI.../grab-worker.exe","ok":true,"exit_code":0}`，data-rc 目录零副作用）；缺 `CAMPUS_DATA_DIR` 退出码 1 + 人话拒绝，时间戳取证真实 LOCALAPPDATA 零触碰；实包 GUI 启动（记录 PID=25344 树）截图链：首启条款门 → 暂不使用横幅 → 帮助「当前 1.1.1」，收尾 taskkill 自启树、ui.json 只落临时根
- **[实包线] 旧包定性坐实**：`dist/installer/校园活动报名工具-安装版-1.1.1.exe`＝60,026,666 字节、SHA-256 a9f2efe2…、10-27 16:18 旧模板 iss 产物——**不在 manifest、与现行安装包（60,010,189 字节 c167ce09…）哈希不符，非发布物，不得分发**
- **[源码线] 关键实证**：五个构建/发布脚本（build_exe/make_portable/runtime_paths/release/build_installer）与发布提交 a57a3cb 逐字节一致→源码线结论对发布物有效；VERSION 读取顺序三候选+非法 SystemExit 不回退；release.py 门禁（`dirty_flag is not False` 一票拒绝、构建前后来源比对、安装器与单独 EXE 同源派生）；installer 静态证据 92 tests OK
- unproven：①真机安装与卸载残留实测（写系统属真机轮）②实包 `component` 字段未触发（需破坏发布物，单测已覆盖 6/6）③3 个真实 Git fixture 单测按设计跳过（需 CAMPUS_GIT_FIXTURE_AUTH=1，属 --publish 远端核验）
- 文档级备注（记 BACKLOG）：UI_SPEC:314 写中文资产名，实现/发布物为 ASCII 名（release.py 有明确理由：GitHub 规范化中文前缀）——建议后续对齐措辞
- 提交：无代码改动，落 docs 提交。

## B16 数据根与迁移
- 结论：通过 9 / 缺陷 0 / blocked 1（unproven 1）
- 判据：§5.9.1/5.9.2/5.9.3（CAMPUS_DATA_DIR 覆盖与相对 resolve/frozen 默认根/迁移只补缺失绝不覆盖/构建保留 OUT/data）
- 证据：`acceptance-evidence/20261031-b16/`（直调探针 10 PASS、单测 53+9 复跑、文件系统 sha256 取证、真实 WinError 32 注入）
- 关键实证：`CAMPUS_DATA_DIR` 相对路径 `.resolve()`（runtime_paths.py:30-33，单测 :68-78）；frozen 默认 `%LOCALAPPDATA%\TianSoftActivityPreRegistration\data` 常量单源（app.py 与 grab.py 同从 runtime_paths 导入）；`_env()` 两侧同根同文件（worker 子进程读到主程序写入的假 session）；迁移 `mkstemp+copy2+os.replace` 只补缺失、`target.exists() → continue` 绝不覆盖（预置同名文件 sha256 逐一不变、旧文件留原地）；真实 Win32 独占锁注入 grab.log → 迁移失败不阻断启动（`[!] 旧登录数据迁移失败（不影响启动，可手动拷贝）`，其余 3 文件照常迁入）；`MIGRATE_FILES` 恰 4 项、诱饵 tokens.json/credentials.db/subdir 全部不搬；合成 session.json 字段恰 5 键无任何密码类字段（未读真实文件）；`prune_output` 保留 OUT/data 动态证实
- 观察（非缺陷，记 BACKLOG）：①迁移是 copy-in 非 move（源文件保留，符合「可手动拷贝」兜底与「构建不删登录态」；若要求搬走后清理旧目录属产品决策）②迁移失败粒度按整轮（首个文件失败即停本轮剩余，下轮再试，不违反失败不阻断）
- unproven：真实冻结 EXE 的真机迁移链路（本轮以 `sys.frozen=True`+假 LOCALAPPDATA 子进程复现生产全部分支；缺真实打包+真机首启冒烟——B15 已覆盖构建产物存在性与 runtime-check）
- 提交：无代码改动，落 docs 提交。
