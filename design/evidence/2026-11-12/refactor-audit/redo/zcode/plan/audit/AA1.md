# AA1 对抗审计意见（事实核对，2026-11-13）

- 被审对象：`design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/` 下 desktop.md + desktop.cites.jsonl、phone.md + phone.cites.jsonl、rules.md + rules.cites.jsonl、grab.md + grab.cites.jsonl、prereq.md + prereq.cites.jsonl（共 674 条）。reconcile.md 作为对账口径参照一并核。
- 基线：提交 `7e2d31c`。所有复核只用 `git show 7e2d31c:<仓库相对路径>` 取基线原文；被审文件一字未改。
- 方法：(1) 独立重跑 `scripts/verify_cites.py` 五份各一次（`python -I`，缺省 git show 基线）；(2) 按固定随机种子抽样重读基线，逐条判「原文是这几行」与「这一行真是这个意思」；(3) 三个专项（kind 误标 / 摘录截断改义 / 计数与清单口径）。
- 抽样：`random.Random(20261113).sample(range(1, N+1), k)` 后排序，k = max(15, ceil(0.2N))：desktop 52、phone 25、rules 17、grab 24、prereq 19，共 137 条（20.3%）。
- 独立 verify 结果（全部 0 失败，与 plan/verify/*.txt 一致）：
  - desktop.cites.jsonl：共 257 条，失败 0；desktop.md 引用 502 处，缺失 id 0，未被引用 0
  - phone.cites.jsonl：共 123 条，失败 0；phone.md 引用 347 处，缺失 id 0，未被引用 0
  - rules.cites.jsonl：共 84 条，失败 0；rules.md 引用 224 处，缺失 id 0，未被引用 0
  - grab.cites.jsonl：共 118 条，失败 0；grab.md 引用 235 处，缺失 id 0，未被引用 0
  - prereq.cites.jsonl：共 92 条，失败 0；prereq.md 引用 105 处，缺失 id 0，未被引用 0
- 抽样判定汇总：137 条 = 133 成立 + 2 部分成立（q-003、q-015）+ 2 推翻（d-257、q-082）。明细见附录一。

## 意见逐条

严重度分布：阻断 0、重要 2（意见 1、3）、次要 9（意见 2、4-11）。

### 意见 1（重要，事实错 + 摘录截断改义）：q-082「固定四文件映射」与基线不符

- 原文：prereq.cites.jsonl q-082（基线 `local/infrastructure/phone_http.py:24-29`）；prereq.md 第 299 行「PHONE_STATIC 只放行 `/`、`/index.html`、`/styles.css`、`/app.js` 四个名字 [[q-082]]」。
- 代码实际是什么：基线 PHONE_STATIC 共 **6 个映射、5 份文件**（24-32 行）：`/`、`/index.html`、`/styles.css`、`/app.js`、`/favicon.ico`、`/apple-touch-icon.png`。q-082 的行区间止于第 29 行——恰是「品牌图标：head link rel="icon" 和 apple-touch-icon 走同一个白名单映射」这条注释行，第 31-32 行两条图标映射被行区间盖掉；claim「固定四文件映射」与摘录自己的尾行注释直接矛盾。
- 判定：推翻。prereq.md「只放行四个名字」随之失实；「映射之外的文件一律取不到」这半句仍成立。
- 类别：事实错 + excerpt 截断改义。
- 建议：q-082 行区间扩到 24-32，claim 改为「PHONE_STATIC 六个映射放行五份静态文件（index/styles/app/favicon/apple-touch-icon）」；prereq.md 第 299 行同步改枚举。这是白名单类清点，重构者照抄会把两个图标文件当成「映射之外」处理。

### 意见 2（次要，事实错）：d-257 对 lastDownload 的用途表述错误

- 原文：desktop.cites.jsonl d-257（基线 `local/ui/views/phone.js:465`，claim「PhonePanel.lastDownload 在下载收尾时写入，决定红条原因与重新下载按钮」）；desktop.md 第 337 行（⑧ A2 补记「lastDownload：红条原因与『重新下载』按钮」）。
- 代码实际是什么：`lastDownload` 全文件仅 3 处——181 声明、461 读（PH32 迁移检测）、465 写；写入点在 `paintPhoneAccess`（437-698）内，**每次重画都执行**，不是「下载收尾时」。它唯一用途是 PH32：检出 `downloading/verifying → installed` 迁移时补一句「已安装」提示。红条 `#phone-feature-error` 由 `phase === "broken" || phase === "disabled"` 取 `notes.feature` 决定（约 523 行附近），「重新下载」按钮由下载状态直接派生——都不读 `lastDownload`。
- 判定：推翻（claim 两个分句都不成立；摘录行本身真实存在，verify 才会通过）。
- 类别：事实错。
- 建议：d-257 claim 改为「lastDownload 记上次呈现的下载状态，供 PH32 检出 downloading/verifying→installed 迁移补一句『已安装』」；desktop.md 第 337 行同步改。红条与重下按钮的真实驱动（phase/notes.feature）在补记里应指向对应条目。

### 意见 3（重要，漏项 + 计数不符）：phone.md ② 缺「7. 取消一场」小节，与口径说明「共 12 个等待操作」不符

- 原文：phone.md 第 20 行（口径说明列「轮询同步、配对、开始计划、对账、取消等待、停止计划、**取消一场**、重新登录开始、提交验证码、取消重登/换图、保存重试设置、显示电脑窗口，共 12 个」）；② 章节编号从「### 6. 停止计划」（144 行）直接跳「### 8. 重新登录开始」（151 行）。
- 代码实际是什么：② 成节的等待操作只有 **11 个**；「取消一场（cancelTask）」没有独立小节，其七出口未按本件自己定的口径铺开（cancelTask 只在第 77 行字段总表的读取点列和第 201 行 V2 里被带过）。第 6 节末条「取消/超时/页面隐藏/配对失效：与『停止计划』同构」的写法（在自己小节里说与停止计划同构）也说明这节混入了两套内容。
- 判定：部分推翻（12 个的口径承诺 vs 11 节实际）。
- 类别：漏项 + 内部计数不符。
- 建议：补「### 7. 取消一场（cancelTask）」七出口小节，或把口径说明改成 11 个并写明「取消一场并入停止计划一节、按同构记」——两种改法任选，但编号断裂必须消除。

### 意见 4（次要，事实错）：phone.md 第 6 节失败文案张冠李戴

- 原文：phone.md 第 148 行（「6. 停止计划」的失败行：「回包 error → sheet 红条『没能取消这一场：…』、回 false [[p-121]]」）。
- 代码实际是什么：stopPlan 的失败文案是「**没能停止计划**：…」（`local/ui/m/app.js` 2809-2812，[[p-120]] 的摘录里就有）；「没能取消这一场：…」是 cancelTask 的（2837-2840，[[p-121]]）。条目本身都对，错在 md 行的归属。
- 判定：该行不成立（其余行成立）。
- 类别：事实错（文案错配）。
- 建议：第 6 节失败行改引 [[p-120]] 与「没能停止计划：…」；若按意见 3 补了第 7 节，此行移入第 7 节。

### 意见 5（次要，推测当事实）：q-015 的 kind 误标

- 原文：prereq.cites.jsonl q-015（基线 `local/ui/m/app.js:2706-2711`，kind=**事实**，claim「…改显北京时间的目标行为尚未实现」）。
- 代码实际是什么：前半句是代码事实（「最近同步」用 `new Date()` 取手机本地时钟，摘录属实）；后半句「改显北京时间的目标行为尚未实现」是对提案目标行为（目标行为不在基线 7e2d31c 内）的推断，按本重做自己的 F1 口径应为非事实 kind 且必须写 missing。prereq.md 第 347 行自己的抽查段已承认「q-015 的 claim 含『目标行为尚未实现』的推断成分……按有条件属实记录」，但 jsonl 未改，形成「行文承认推断、数据仍标事实」的不一致。
- 判定：部分成立（代码事实半句成立；kind 标注违反 F1 规则）。
- 类别：推测当事实（kind 误标）。这是全 674 条里唯一一处明确的 kind 误标（我用推断关键词全量扫过 674 条 claim，其余含「可能/恒/唯一」等词的条目逐一核过，均有代码或检索依据）。
- 建议：q-015 改 kind=推测并补 missing（写明缺「提案目标行为与基线比对的出处」），或把 claim 截到代码事实半句。

### 意见 6（次要，事实错·局部）：q-003「同一函数」表述不准

- 原文：prereq.cites.jsonl q-003（基线 `local/ui/controllers/plan.js:353-355`）；prereq.md 第 23 行「基线在发起 stop_plan 的同一函数里同步写『计划已暂停：N 场放回草稿修改』」。
- 代码实际是什么：「计划已暂停」句在 `modifyPlan()` 第 355 行写入，随后第 356 行调用 `doStopPlan()`；`api("stop_plan", …)` 桥接调用在 `doStopPlan()`（387 行）里发——**两个函数**。「同步写入、不等停止结果」成立，「同一函数」不成立。prereq.md 第 312 行自己的抽查判「claim 成立」，口径偏宽。
- 判定：部分成立。
- 类别：事实错（局部表述），不影响「拒绝后日志已写出」这一结论。
- 建议：改为「在发起停止的入口函数 modifyPlan 里同步写、随后才调 doStopPlan 发 stop_plan」，并把第 312 行的抽查结论改为「部分成立」。

### 意见 7（次要，计数不符）：desktop.md 头部与 ⑦ 的条目数停留在 245

- 原文：desktop.md 第 6 行「引用条目：245 条（d-001 至 d-245）」；第 297 行「从 245 条里…抽 14 条」；第 327 行「verify_cites.py 复跑 245 条 0 失败存 plan/verify/desktop.txt」。
- 实际：jsonl 为 **257 条**（d-001..d-257；d-246..d-257 是 ⑧ T6 对账补记新增）。独立复跑 verify_cites.py：257 条 0 失败；其所引 plan/verify/desktop.txt 工件本身就写着「共 257 条」。reconcile.md 用的是 257（正确）。头部、⑤、⑦ 三处没跟着补记更新。
- 判定：不符（簿记陈旧，实质核对不受影响）。
- 类别：计数不符。
- 建议：第 6 行改 257；第 327 行补「补记 d-246..d-257 后共 257 条，复跑 0 失败」；第 297 行的「约 6%」按 14/257 重算。

### 意见 8（次要，计数不符）：rules.md 头部与抽查段的条目数停留在 81

- 原文：rules.md 第 5 行「引用条目：81 条」；第 292 行「verify_cites.py 复跑 81 条 0 失败存 plan/verify/rules.txt」。
- 实际：jsonl 为 **84 条**（r-001..r-084；r-082..r-084 是文末「补记：分组日界的时钟口径（T6 对补充轮 U19 的裁定）」新增）。独立复跑 84 条 0 失败；plan/verify/rules.txt 写的是 84。
- 判定：不符（簿记陈旧）。
- 类别：计数不符。
- 建议：第 5 行改 84；第 292 行补记后口径。

### 意见 9（次要，计数不符）：reconcile.md 五、四类汇总的「一致 39」无法从分表推出

- 原文：reconcile.md 第 77 行「一致 39」+ 注「含三个整块（review §3.1/§3.2/§3.3 与补充轮 A 改动表，按整块各计 1）」；第 84 行「对账条目合计 56（含整块折算）」。
- 实际：三张分表（一/二/三/四）可数数据行 **44**，其中标「一致*」的 **26** 行。按注明的口径（整块各计 1）应得 26，不是 39；若把 §3.1 的 13 条展开得 36，三块全展开则 26-3+13+11+9=56——恰好等于总数而非「一致」数。另外：U19 行的「分类」列写的是「补充轮漏→重做收口」，汇总把它计入「重做推翻 3」并使「补充轮漏」由分表 5 行变 4；「范围外 4 处来源归 3 组」有明注（成立）。
- 判定：汇总的「合计 56」与参照口径一致、可加总成立；但「一致 39」与分表行数对不上、折算规则无法复算，U19 的归类与分表列不一致。
- 类别：计数不符（内部，口径不透明）。
- 建议：给出一致 39 的逐项折算明细，或按分表行数直接重列汇总并统一 U19 的归类。

### 意见 10（次要，判断站不住）：grab.md 对「输出调用 187 vs 159」的口径说明未闭环

- 原文：grab.md 头部「计数口径说明：任务书给的参考口径『输出调用 187 处』与本脚本 159 处不同，是计数口径差异（本脚本按调用点计，并把 grab 自有日志出口单列），不是矛盾」。
- 实际：159 这一侧我独立复算成立——grep 基线 `local/grab.py`：print( 85、log( 全文 67 = 61 个调用点 + def 1 + 注释/docstring 提及 4、log_event( 7 = 6 调用 + def 1、_stderr_note( 7 = 6 调用 + def 1、sys.stderr.write 1，合计 159 个调用点；grab-script.txt 的 85/61/6/6/1 与之一致。但 **187 无法从基线用任何明显枚举复算**：print+log+log_event+_stderr_note+stderr.write+notify(4 次调用)+input(2 次调用) 全算上约 165 个调用点，把 def 行与文本匹配全算约 174。说明断言「不是矛盾」却没有给出 187 的可能构成。
- 判定：159 成立；「不是矛盾」的断言无法核验（对方口径的构成不明）。
- 类别：判断站不住（说明只做了单向解释）。
- 建议：补一句 187 的可能构成（按行计数 / 含 notify / 含测试与工具脚本等），或把措辞弱化为「未能对上，待与参照口径作者对齐后回填」。

### 意见 11（次要，判断站不住）：reconcile.md 未与参照口径「对账 80 条」对账

- 原文：reconcile.md 第 84 行「对账条目合计 56（含整块折算）」；头部「范围标注」。
- 实际：56 是本表自己的可加总结果；参照口径的「对账 80 条」在全文未出现，差异只能靠头部的「范围外不重做」标注和「整块折算」间接推断，没有一处写明 56 与 80 差在哪里（哪些来源条目被归并/范围外）。
- 判定：部分成立（有间接口径说明，无显式对账）。
- 类别：判断站不住。
- 建议：在第五节补一行「参照口径 80 条与本表 56 的差异＝……」，与意见 9 一并修。

## 复核中确认成立的关键点（供 AA2/仲裁参考）

- 五份 verify 独立复跑全过、md 引用无缺失、无未引用条目（desktop/rules 两份 md 自述条数陈旧除外，见意见 7/8）。
- 实质计数全部与参照口径对上：Api 方法 153/公开 60（我用 ast 直属子节点复算 153/60/93；我自己第一遍 tokenizer 数出的 154/94 是把 `main()` 里嵌套的 `_closing`（4840 行）误计入，以 ast 为准）；手机字段 55（字面量 47 逐行数过 + 8 个动态字段逐一 grep 到）；写入 154（脚本 148 + 6 处别名，与参照 136+3+9+6 总数同）；读取 296；rules 9 条规则（§1-§9）；esc 115 处调用（脚本输出 115 调用 + 3 处非调用引用，与 prereq.md ③ 一致）。
- desktop.md 范围口径核过：state-trace.md 行尾来源标记只有 核/数 两种（我按行尾标记数：核 83、数 18，另有 36 行标记内嵌于句中；「子」只出现在文件头图例，没有任何行标「子」）；「本表没有判『不属实』的行」核过（① 表 144 行 = 130 属实 + 11 有条件属实 + 1 需测试定 + 2 属实变体）。
- desktop.md 所记的 state-trace 行号偏差抽查核过：preLoginSnapshot 清点恰 5 处（424/433/450/466/477，466/477 与其修正一致）；CANCEL_WORKER_TIMEOUT_S = 90 在 app.py:2521；update.js 的 S.update.requestId 共 19 处、其中严格相等比对 8 处。
- phone.md V2 链核过：showSheetError 在 model.sheetId 为空时静默返回（1607-1613），Esc/遮罩/关闭钮三路走 closeSheet——V2 的代码依据成立。

## 附录一：抽样判定明细（种子 20261113，137 条）

判定口径：成立＝摘录落在声明行内且 claim 语义成立；部分成立＝主体成立但有一处表述/kind 问题（意见号随注）；推翻＝claim 与基线不符。

### desktop（52 条：51 成立 + 1 推翻；d-254 成立但注「失败写 notes.feature」在摘录后一行）

| id | 判定 | 依据 |
|---|---|---|
| d-003 | 成立 | 182-187 正是 check 100 秒超时分支：清 checking、result=unknown、addLog、settle |
| d-004 | 成立 | 217-223 桥接异常分支同构收口，addLog「检查登录状态失败」 |
| d-008 | 成立 | res.result 当场 onBackend.check；否则 takeRoundPayload 暂存重放 |
| d-010 | 成立 | res.demo 分支清 loginPending/preLoginSnapshot，注释 R20 |
| d-013 | 成立 | catch 分支 restoreLoginSnapshotState+清快照+「登录没能开始」 |
| d-014 | 成立 | done 事件 kind==="login" 清 loginPending、setBusy(false) |
| d-017 | 成立 | auto 四条件（origin/live/handoff/valid）推导并写 S.autoLogin |
| d-019 | 成立 | success/live===false 清 handoff，else if handoff 置真 |
| d-025 | 成立 | 写 check/list 请求号并 clearTimeout 两个兜底定时器 |
| d-029 | 成立 | self._proc = tree.proc，行内注释即「占住 busy 位」 |
| d-034 | 成立 | 自动重登凭据路径（_relay.prepare→begin(origin="auto")）内置 _pending_save=None |
| d-035 | 成立 | store.js:78 login 字面量确无 handoff/recovering/view 键 |
| d-043 | 成立 | failed/canceled 切 bad/msg 步、清 flowId，摘录内无自动关 |
| d-067 | 成立 | phonePhase 优先级 on→downloading→verifying→checking→outdated→broken→off→disabled→missing |
| d-073 | 成立 | install_advanced_feature 的 finally 清 _advanced_busy（锁内） |
| d-077 | 成立 | with self._lock 内置 _active；thread.start() 也在锁内 try 中 |
| d-078 | 成立 | 下载线程 finally：on_finished 回调+清 _installing/_active |
| d-079 | 成立 | catch 仅注释吞异常，不改状态不提示 |
| d-086 | 成立 | schedule_phone_restore（window.events.loaded 时机）内调用，注释「一次性启动任务共用时机」 |
| d-092 | 成立 | toggleStop catch 写 onErr、finally 清 pending/busy+refresh |
| d-094 | 成立 | watchdog：stalled==="checking"→error，其余→failed，15000ms |
| d-101 | 成立 | run_check 的 finally 内锁下写 _update_result、清 _updating |
| d-112 | 成立 | 非 background（前台轮）路径 listState="error"、130 秒文案；后台轮另有分支 |
| d-118 | 成立 | ready 出口清 autoRefreshState.fails、记 listAtMono/okLabel |
| d-124 | 成立 | check 事件两分支清 checkPending（roundError 收口语义完整） |
| d-125 | 成立 | AUTO_REFRESH_NOTE_AFTER=3（523 行），仅第 3 次写一条运行记录 |
| d-128 | 成立 | busyId 置位+then/catch 双路 cancelSettle，均先核 busyId===id |
| d-130 | 成立 | cancelNo 绑 cancelAskDismiss（app.js:189），清 askId |
| d-132 | 成立 | busyId 挡刷新；!quiet 清 res/askId |
| d-142 | 成立 | visibilitychange 非 hidden 时 bootstrap 对账、非 busy refresh(true) |
| d-154 | 成立 | start_request_state 对账 rejected/canceled 清 starting |
| d-164 | 成立 | stopped+editing 放回未提交场次，S.editing 不清（摘录内可见） |
| d-168 | 成立 | clearSelection 函数体内 S.editing=null |
| d-174 | 成立 | _plan/_plan_generation 同临界区赋值，注释 P1 |
| d-176 | 成立 | _emit("plan_done", forward_payload) 确凿 |
| d-180 | 成立 | btn-stop disabled/textContent 按 S.stopping |
| d-187 | 成立 | 401 直接 return；ok&&!pending 记 accepted 终态（A-BUG-1 注） |
| d-191 | 成立 | state==="unknown" 横幅文案含「取消等待」 |
| d-196 | 成立 | !user||!pass 清 reloginStarting+提示，注释即「保险丝」 |
| d-206 | 成立 | git grep：renderReview 仅 2955/2959 两处调用（3353 是导出名单） |
| d-214 | 成立 | start 按钮 hidden/disabled/textContent 三条件与 claim 一致 |
| d-217 | 成立 | cancel 按钮 hidden=!downloading、verifying 时「校验中…」 |
| d-221 | 成立 | 四个 ocrShow 相位条件与 claim 一致 |
| d-227 | 成立 | grep ph-err：OCR 区仅 319 一条（其余是 phone-*/update-* 元素） |
| d-228 | 成立 | 取消说明条件 phase==="missing" 且无 error/failText |
| d-234 | 成立 | with 块闭合后锁外 terminate，随后同步 _on_finish() |
| d-236 | 成立 | on_finish=self._relay_finished 注入确凿 |
| d-242 | 成立 | if not self._window: return（UI 投递不发生；手机入缓冲在其前，注释已说明） |
| d-243 | 成立 | checkUpdate 内生成/写 requestId、置 checking、挂 watchdog |
| d-250 | 成立 | PhonePanel.location 由 advanced_component_location 写 |
| d-254 | 成立 | busy 进出 try/finally 属实；「失败写 notes.feature」在紧邻摘录后的 859 行，claim 整体成立 |
| d-257 | 推翻（意见 2） | lastDownload 全文件仅 3 处（181/461/465），每次重画都写；红条与重下按钮由 phase/notes.feature 与 dl 直接派生，不读它 |

### phone（25 条：25 成立）

| id | 判定 | 依据 |
|---|---|---|
| p-002 | 成立 | change 回调走 PhoneModel.pickItem，写 model.selected/notice，注释 LD04 |
| p-003 | 成立 | reselectFailed：记 dismissedPlanId、清 plan、actionable 放回；skipped 在摘录后一行 addLog（2866） |
| p-004 | 成立 | finishPlanView 五件事齐全（dismissedPlanId/plan/selected/listOpen/notice） |
| p-007 | 成立 | goSigned 先清 whyId；不可见时重置 filter 并同步两个搜索框+段钮 aria-pressed |
| p-009 | 成立 | #q input 写 filter.q 并同步 search-q |
| p-013 | 成立 | retry_policy 对象且未 hydrate 未 dirty 才写并置 retryHydrated |
| p-015 | 成立 | max-attempts change 写 retry.max_attempts、置 retryDirty、void saveRetry() |
| p-017 | 成立 | payload.reset 清 seenEventSeq、seq=0、清日志 |
| p-023 | 成立 | 200 分支记 lastOkAt、backoff=1000、paired=true、进主界面、clearStaleBanner；ingest 在 2449 |
| p-039 | 成立 | duplicate_submit 不解锁只 poll；其余收 reloginSubmitting 并写原因 |
| p-040 | 成立 | beginRelogin 置 reloginStarting 并清 relConfirm/relEnteredAcct/relSavedChoice |
| p-047 | 成立 | 无未决时 newRequestId 写 model.pending{done:false}、清 notice、收 listOpen |
| p-051 | 成立 | 配对网络异常 setPairError 并 return；api 的 REQUEST_TIMEOUT_MS=8000（1371/2294 行） |
| p-059 | 成立 | tickClock 记 (wall,mono)，sleepJumped 时 clock=null 并补 poll |
| p-064 | 成立 | setClock 三时刻齐+state ready/holdover 才记锚，否则 null |
| p-066 | 成立 | model.pcListError = state.pc_list_error || null，无条件 |
| p-071 | 成立 | closeSheet 清三个输入、confirm、relConfirm，焦点归还 opener |
| p-077 | 成立 | setPairError 写 model.pairErr 并 renderPair |
| p-082 | 成立 | relogin_setup 为对象时整份替换（2653 行单行） |
| p-084 | 成立 | reconcile 单飞守卫、置 reconciling、取 pending.request_id；调用点 2712 有 !pending.done 守卫 |
| p-107 | 成立 | accepted 记录回 ok=false+plan_id+「请用『停止计划』结束」 |
| p-110 | 成立 | beginRelogin 两道守卫原文（单飞+canWrite） |
| p-116 | 成立 | isActive 四类忙判定；IDLE_SYNC_MS=15000、ACTIVE_SYNC_MS=2000，退避优先 |
| p-118 | 成立 | index.html:35 `<section id="app" hidden>`；2445 行配对成功后 hidden=false |
| p-120 | 成立 | stopPlan 三分支齐全；onConfirmYes 在途禁双钮（3245 行附近），无独立在途标志 |

### rules（17 条：17 成立）

| id | 判定 | 依据 |
|---|---|---|
| r-002 | 成立 | probe_token docstring 只认 4001+复查；LOGIN_RECHECK_S=1.5（1895 行）且 2453-2458 实际 sleep |
| r-003 | 成立 | build_check_event 载荷 "result": result，注释四态 |
| r-004 | 成立 | 三态快照 docstring 区分缺 token 与过期 |
| r-007 | 成立 | status-cards.js:87 四态标签逐字命中 |
| r-009 | 成立 | loginExpired 带 flow 时 !loginRecovering，注释「自动重登不算失效」 |
| r-013 | 成立 | plan_rules docstring：已截止不进 worker、两模式可混合 |
| r-015 | 成立 | labels.js:19 三标签逐字命中 |
| r-017 | 成立 | stOf 优先级 signed→closed→open→pre→unknown，注释注明与 classify_signup_mode 同口径 |
| r-023 | 成立 | filters.js:197-198 注释：已报名外部占用、开放时间不参与 |
| r-040 | 成立 | rank：signed=2、时钟缺失=1、now<sign_start=0、else 1 |
| r-047 | 成立 | titles 固定数组遍历过滤映射，摘录内无排序调用 |
| r-051 | 成立 | 批次头 instant→「现在」/note 文案逐字命中 |
| r-059 | 成立 | SCHOOL_TZ="Asia/Shanghai"、SCHOOL_OFFSET_S=8*3600 |
| r-066 | 成立 | component_error 三码：FileNotFoundError/PermissionError/其余 |
| r-071 | 成立 | _NON_CONFLICT_TEXT 四句与 selection.js PLAN_ERROR_TEXT 逐字一致（我比对过） |
| r-074 | 成立 | retryText 概括行「尝试 X，最多 N 次/不限次数」 |
| r-082 | 成立 | startOfDay 用 schoolParts 切天 |

### grab（24 条：24 成立）

| id | 判定 | 依据 |
|---|---|---|
| g-002 | 成立 | setup_console reconfigure utf-8/replace（stdout+stderr），main 里统一调用 |
| g-003 | 成立 | _stdout_to_stderr docstring 即契约注释 |
| g-004 | 成立 | log() 末行 print(line, flush=True)；锁超时 _stderr_note 降级 |
| g-007 | 成立 | 有快照走 ClockClient，失败 return None（135/140/142 行），docstring「调用方显式处理」 |
| g-009 | 成立 | [OK]+[clock] JSON 行+可选 [!] 偏差+return 0 |
| g-013 | 成立 | 空列表 --json 打 []、文本模式提示语，两路 return 0 |
| g-015 | 成立 | print(json.dumps(out, ensure_ascii=False)) 单行+return 0 |
| g-017 | 成立 | stdout 恰一行 JSON；return 0 if kind=="cancelled" else 2（条件表达式） |
| g-023 | 成立 | unconfirmed→[?]+return 2；clock_unavailable→[X]+return 3 |
| g-039 | 成立 | 候选表 print+input 序号交互 |
| g-040 | 成立 | 找不到 sign_start 打 [X] 并要求 --at，return None |
| g-047 | 成立 | save_storage_state 锁对象默认 SESSION_FILE，经 _write_login_file |
| g-051 | 成立 | ensure_data_dir mkdir+frozen 且未迁移时 _migrate_legacy_data |
| g-059 | 成立 | worker_command docstring+if frozen 分支 |
| g-064 | 成立 | 2607-2608 注释与代码：超时/读不出都归 unknown_result，只取 stdout |
| g-066 | 成立 | normalize_worker_result docstring：只认最后一个非空行、ok 由 kind 推出 |
| g-071 | 成立 | 四态判定 if 链逐行命中 |
| g-077 | 成立 | ATTEMPT_RE 正则与注释一致，[i] 前缀可选 |
| g-082 | 成立 | 倒序 tail 找带 stop_reason 的 [retry]，注释「进度行不得冒充终态」 |
| g-084 | 成立 | code==3 且 tail 含「登录失效」才 login_invalid；reason=倒序第一条 [X]（211-215 行，摘录前紧邻） |
| g-106 | 成立 | 需测试定+missing 齐备，claim 即「缺子进程级测试」 |
| g-107 | 成立 | 打不开登录页 [X]+log_event+return 2 |
| g-112 | 成立 | PermissionError/Exception 两分支都 [X]+return 2 |
| g-115 | 成立 | parse_ts ValueError→[X] 格式不对+return 2 |

### prereq（19 条：16 成立 + 2 部分成立 + 1 推翻）

| id | 判定 | 依据 |
|---|---|---|
| q-002 | 成立 | 393 行把 stop_plan 桩成永不 resolve；「断言已写出」半句由 q-001 的用例佐证 |
| q-003 | 部分成立（意见 6） | 句在 modifyPlan 写、stop_plan 桥接在 doStopPlan 发——非「同一函数」；同步、不等结果成立 |
| q-004 | 成立 | 148-150 即「重新开始被接纳清修改态」用例 docstring；「只有一条」与检索一致 |
| q-007 | 成立 | 9216 docstring 即名额满不放回规则用例 |
| q-009 | 成立 | cancelSettle 成功路径 addLog+render+refresh(true) |
| q-013 | 成立 | N1 docstring+test def 在 8648-8650 |
| q-015 | 部分成立（意见 5） | new Date() 属实；「目标行为尚未实现」是推断成分，kind=事实 误标 |
| q-017 | 成立 | 该轮询函数只认 log/phone_relogin 两种 kind（grep 复核） |
| q-023 | 成立 | download_advanced_feature docstring「单飞，重复点击直接回 busy」 |
| q-039 | 成立 | check_update docstring「只登记轻量后台查询」 |
| q-040 | 成立 | update_launch docstring「启动前先回推 launching」 |
| q-047 | 成立 | _spawn def 即一次性 worker 启动入口（4520） |
| q-051 | 成立 | patch.object(app.sys, "frozen", True, create=True) 样例确凿 |
| q-059 | 成立 | test_launcher_started… 用例内 2607 行替换 request_window_close |
| q-064 | 成立 | list.js:120 组头 <b>+esc(label) 文本落点 |
| q-066 | 成立 | esc(text).replace 固定按钮；grep 复核 ui 内其余 replace 均非 esc 后加工，唯一成立 |
| q-071 | 成立 | window.onBackend 表头 log/window_close_ask/check+迟到守卫（cacheRoundPayload） |
| q-077 | 成立 | ACTION_PARAMS 前半含 save_retry_policy 与 show_window |
| q-082 | 推翻（意见 1） | PHONE_STATIC 实为 6 映射（24-32 行含 favicon/apple-touch-icon）；行区间止于 29 行注释，恰好盖漏 31-32 行 |

## 附录二：verify_cites.py 独立复跑输出（2026-11-13，AA1 原样存档）

复跑命令（仓库根）：`python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/verify_cites.py <cites> <md>`，每份单独跑，基线取 `git show 7e2d31c:<路径>`（脚本缺省路径）。

### desktop

```
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/desktop.cites.jsonl: 共 257 条，失败 0 ==
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/desktop.md（配对 …desktop.cites.jsonl）: 引用 502 处，缺失 id 0，未被引用条目 0 ==
---- 合计: 257 条，失败 0 ----
```

### phone

```
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/phone.cites.jsonl: 共 123 条，失败 0 ==
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/phone.md（配对 …phone.cites.jsonl）: 引用 347 处，缺失 id 0，未被引用条目 0 ==
---- 合计: 123 条，失败 0 ----
```

### rules

```
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/rules.cites.jsonl: 共 84 条，失败 0 ==
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/rules.md（配对 …rules.cites.jsonl）: 引用 224 处，缺失 id 0，未被引用条目 0 ==
---- 合计: 84 条，失败 0 ----
```

### grab

```
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/grab.cites.jsonl: 共 118 条，失败 0 ==
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/grab.md（配对 …grab.cites.jsonl）: 引用 235 处，缺失 id 0，未被引用条目 0 ==
---- 合计: 118 条，失败 0 ----
```

### prereq

```
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/prereq.cites.jsonl: 共 92 条，失败 0 ==
== design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/prereq.md（配对 …prereq.cites.jsonl）: 引用 105 处，缺失 id 0，未被引用条目 0 ==
---- 合计: 92 条，失败 0 ----
```

（输出里的路径为完整绝对形式，此处省略号仅压缩展示 `design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/` 中段，不影响结论。）

## 附录三：计数核对台账（专项三）

| 口径 | 参照（他人重做） | 本重做 | AA1 独立核 | 结论 |
|---|---|---|---|---|
| desktop 条数 | 424 | 257 | verify 257 | 颗粒度/覆盖面差异；desktop.md 有范围口径（只逐行覆盖 state-trace「核」行），未与 424 显式对账，不算缺陷 |
| phone 条数 | 292 | 123 | verify 123 | 方法差异；字段/读写点等实质计数见下 |
| rules 条数 | 88 | 84 | verify 84 | 规则数一致（9 条），条目颗粒度差异 |
| grab 条数 | 62 | 118 | verify 118 | 本重做覆盖更细（输出协议逐行） |
| prereq 条数 | 194 | 92 | verify 92 | prereq.md 第 218 行已注明「194 仅作完备性参照，按事实需要落 92 条」 |
| 对账条数 | 80 | 56 | 汇总表加总 56 成立 | 差异无显式对账说明 → 意见 11；汇总内部折算不透明 → 意见 9 |
| Api 方法/公开 | 153 / 60 | 153 / 60（api-script.txt、prereq.md ②） | ast 直属子节点复算 153/60/93 | 一致（注意：tokenizer 按 813 行后 4 缩进 def 会误数出 154，main() 里嵌套的 _closing 不属类） |
| 手机字段 | 55 | 55（phone-script.txt fields=55，47 字面量+8 动态） | 47 逐行数过+8 个动态逐一 grep 到 | 一致 |
| 手机写入点 | 136+3+9+6（=154） | 148+6 别名（=154） | 脚本输出 148+6，分组法差异已被 phone.md 注明 | 一致 |
| 手机读取点 | 296 | 296 | 脚本输出 296 | 一致 |
| 规则条数 | 9 | 9（rules.md §1-§9） | 章节逐一数过 | 一致 |
| grab 输出调用 | 187 | 159（85/61/6/6/1） | grep 复算 159 成立；187 无法复算 | 见意见 10 |
| esc 调用 | 115/11 文件 | 115+3 非调用引用 | esc-script.txt：115 行 cat=分类 + 3 处非调用 + 1 表头 = 我数到的 119 行 | 一致（文本节点 77+其他 14 复核后归 91、双引号属性 24） |

工件备注：verify/api-script.txt 是 GBK 编码（其余 verify 工件为 UTF-8），不影响数字，建议统一为 UTF-8；verify/esc-script.txt、grab-script.txt、phone-script.txt 均为 UTF-8 可复算。

## 附：本意见文件自身的边界

- 只按基线 7e2d31c 读产品代码；第一轮 state-trace.md 作为 desktop.md 的输入材料读过（核对其行尾标记与三处行号偏差），其余 redo/ 下材料未打开。
- 抽样外的 537 条未逐条重读，其正确性仅由 verify_cites.py 的结构核对与专项关键词扫描背书。
- 未运行任何测试、构建或外部网络操作。
