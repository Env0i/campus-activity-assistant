# AA3 对抗审计：方案对抗（可行性攻击）

- 审计人：AA3（对抗审计员丙，只攻可行性；引用对错不在本轮范围）。
- 攻击对象：extra/seams.md、extra/mikado.md、extra/plan-redteam.md，与 design/proposals/engineering-refactor.md 工作区版（含未提交的审计结果小节）。
- 基线：7e2d31c。全部证据来自 git grep / git show 对该提交的只读取证；plan/scripts/api_methods.py 为只读清点脚本（内部只 git show，不写文件），已复跑一次核对 153/60/93。未跑测试与构建、未联网；除本文件外未写任何文件。
- 意见格式：对象 / 反例内容 / 基线证据 / 判定 / 严重度。判定两值：反例成立 / 未发现反例。行号一律基线口径。

## 总判定（六角度各一行）

| 角度 | 判定 |
|---|---|
| 1 四类接缝是否真满足「不改被测源码即可替换行为」 | 接缝 1/2/4 未发现反例（接缝 1 有漏项，次要）；接缝 3 反例成立：机制现缺且自指、查询型调用罩不住、最脆弱点按文档写法改完红绿照旧全绿 |
| 2 mikado 节点是否有真正可跑判据 | 反例成立：D 的主判据引用了清点脚本不具备的能力；B1/B2 后半、A3、C2 是人工判定；E1 判据空转；B3 命令输出与判据表述不符；各文档引用的基线期望值（24 名 / 64 名）与自家命令实测（25 名 / 79 名）对不上 |
| 3 每步文件集与交集 | 反例成立：C1..C5 全部改同一个 app.py；test_application_services.py 被全部五个块工作项触碰；E2 与 F3 同改 test_layer_boundaries.py，与「文件集不相交」两处声明矛盾 |
| 4 测试改造成本估计 | 反例成立：红队与依赖树对该成本零量化；实测写点+补丁约 900 行、另有约 395 处私有成员读触点无人计账，总量约为生产拆分的一半，且工序上无法先行 |
| 5 目标值「依赖环 <=3」「state/ 越层 0」 | 反例成立：实测已见 4 个两模块调用环（目标值在基线即已破）；越层 0 要么必须同时改 >=12 个文件，要么被「注入查询闭包」路线字面满足而耦合仍在 |
| 6 并列安排但实有先后依赖的项 | 反例成立：A1/A2/A3 被画成可并行叶子、C 块又依赖它们，而三者完成判据只能由 C 块产出物满足——按树执行死锁（阻断） |

意见合计 21 条：阻断 1、重要 13、次要 7。

---

## 角度 1：四类接缝逐条验证

### AA3-01 接缝 3 判「成立」与接缝 2 的判法自相矛盾（自指问题）

- 对象：seams.md「接缝 3：state/ 越层」判定行（:74）与「接缝 2」判定行（:43、:57）；mikado.md F1（:111-113）。
- 反例内容：接缝 3 的替换机制（store.js 通知口 onStatePainted/notifyStatePainted）在基线不存在，建立它必须修改被测源码本体（store.js + 七个 state 文件的调用行）——替换点就在被测源码里。接缝 2 对结构完全相同的情况（桥接名改名，机制现缺）判「不成立……要成立需补机制（现缺）」，接缝 3 却在机制同样现缺的情况下判「成立」。同一份清单、同一判据（「不改被测源码即可替换行为」），两处适用标准相反。按接缝 2 的标准，接缝 3 应判「现状不成立；补通知口后才成立」，且成立范围还要再打对折（见 AA3-02）。
- 基线证据：`git grep -n "onStatePainted" 7e2d31c -- local/ui` 零命中（机制不存在）；seams.md:74 判定行自称「机制前提是 store.js 承载注册口」，:57 接缝 2 改名判「不成立……缺的机制」；store.js 基线全文无任何通知口。
- 判定：反例成立。
- 严重度：重要。

### AA3-02 通知口机制罩不住查询型调用：21/58 次越层调用（10/25 名）返回值参与 state 决策

- 对象：seams.md 接缝 3「怎么替换」（:103「带参调用同构」）；mikado.md F2.3（:131-134）把 state/plan.js 当成与 labels.js 同权重的单文件清零节点。
- 反例内容：seams.md 把「带参调用」与「返回值查询」混为一谈。按调用次数实测，58 次越层调用里有 21 次（36%）、25 个函数名里有 10 个是查询/纯函数，其返回值直接参与 state 层的条件判断与数据构造，notifyStatePainted() 返回 undefined，等价性论证对这 21 处不成立：
  - if (noteSignedTasks([task])) scheduleSignedRefresh();（state/plan.js:103）——按控制器函数返回值分支；
  - S.resultSel = selectionSignature() / if (S.resultSel !== selectionSignature())（plan.js:114/123/128）——视图函数返回值被存进 S 并参与比较；
  - typeof reloginAutoLive 门（login.js:29）——视图函数返回值决定是否清自动登录态；
  - verifiedSigned 三处门（filters.js:307、task-display.js:58、labels.js:61）、termsLocked 两处门（filters.js:343、conflict.js:147）——布尔门；
  - numOrNull（login.js:33/61）、hmsDay、submittingDetail、effectiveRetryDeadline（task-display.js:100/101/104/148/150）——纯函数被算进显示串与比较。
  反向注入路线（seams.md:103 只写了「注入假 painter」）要覆盖查询必须升级为「注入查询闭包」——文档没写；而一旦走注入闭包，state 层运行期仍依赖 views 提供的函数，「越层清零」只剩 grep 词面上的零（见 AA3-19）。
- 基线证据：定义层 `git grep -nE "^function (noteSignedTasks|selectionSignature|reloginAutoLive|verifiedSigned|termsLocked|numOrNull|hmsDay|submittingDetail|effectiveRetryDeadline)" 7e2d31c -- local/ui` → controllers/refresh.js:398、views/plan-panel.js:901/614/139/1102/1188、views/relogin.js:23、controllers/terms.js:13、controllers/tick.js:162；调用次数按 seams.md:113-115 复算命令逐名统计得 21/58。
- 判定：反例成立。
- 严重度：重要。

### AA3-03 最脆弱接缝（接缝 3）的完整替换写法：按文档三步改完，判据两命令全绿，行为已变

- 对象：seams.md 接缝 3「怎么替换」三步写法（:87-103）与「替换后如何验证行为不变」（:106-109）；mikado.md F2.3 完成判据（:133）。
- 反例内容：挑 state/plan.js:103-104 为最脆弱点，完整写出文档规定的替换，再证明它跑不通：
  1. store.js 末尾追加通知口（seams.md:89-94 原文的 paintListeners / onStatePainted / notifyStatePainted 三段）。
  2. state/plan.js:103-104 中按 :95-98 写法把刷新分支换成 notifyStatePainted()，:104 showTaskResult(task) 同样并入 notify。
  3. app.js 启动段注册 onStatePainted(() => { ... })（seams.md:100-102）。
  跑不通的原因：第 2 步丢掉 noteSignedTasks 的返回值链——「有场次转为已确认，800ms 有界补刷新」（controllers/refresh.js:398-421 返回 changed，:451 scheduleSignedRefresh）整个消失；若把 noteSignedTasks 挪进监听器补回来，它内部还要调 syncResultSelection()（state/plan.js:122）并写 S.confirmed/S.items/S.selected，必须同步派发且注册先于首个 plan 事件才等价——这是跨 store.js/plan.js/refresh.js/app.js 四文件的行为保持重写，不是文档三步。而红绿网抓不住它：git grep "scheduleSignedRefresh" 7e2d31c -- local/tests 计 0（prereq q-010 同结论），该行为零测试覆盖；F2.3 判据的 grep 归零 + test_signup_plan.py 全绿会照常通过——「替换后如何验证行为不变」在最能出事的那一行上是空的。
  要让这条接缝真成立，必须一个提交内同时做三件事：(a) 先补红——在 test_ui_reliability 沙箱里经 runtime_bridge.js:754 的 __QA_EMIT 注入 success 任务事件，断言 800ms 有界刷新恰被安排一次且 busy/starting 跳过（对齐 refresh.js:451-459 现状语义）；(b) 把 noteSignedTasks（约 24 行，含 syncResultSelection 交互）整体搬进 state 层——它本来就是纯状态变更，controllers/plan-events.js:16 的调用点方向合规可留；(c) scheduleSignedRefresh 的触发反转为 store 监听（S.confirmed 变更时安排）。三件缺一，F2.3 的「清零」就是假零。
- 基线证据：state/plan.js:103（返回值分支）；controllers/refresh.js:398-421（noteSignedTasks 写 S.confirmed/S.items/S.selected 并 return changed）、:451（scheduleSignedRefresh）；`git grep -c "scheduleSignedRefresh" 7e2d31c -- local/tests` = 0；test_signup_plan.py 不含该链路用例（prereq 第一节第 6 小节：仅 q-022 覆盖重复 plan_done）。
- 判定：反例成立。
- 严重度：重要。

### AA3-04 接缝 1 未发现反例，但清单只计「写」面：同族命令实测私有成员触点 667 处，约 395 处读/断言无人计账

- 对象：seams.md 接缝 1（:8-39）的补丁面体量口径（70 处补丁点、272 行成员改写）；mikado.md A1/A2。
- 反例内容：接缝 1 的判定本身成立——实例属性遮蔽（test_application_services.py:1473/1478/1489）、类级补丁（test_runtime_bundle.py:397/441/443）、字段塞入（:283-289）、模块级补丁都有基线实样，测试侧替换不改源码。但迁移体量口径只数了「写」：`git grep -hoE "(self\.api|api)\._[A-Za-z_0-9]+" 7e2d31c -- local/tests | wc -l` = 667，减去 272 个写点，约 395 处是读/断言（如 assertEqual(api._last_check["result"], ...)、assertFalse(api._checking)，test_runtime_bundle.py:407-411 一带成串）。拆块后这些状态进服务对象，门面若不再转发字段，每一处读点都要改指服务（1-2 行/处）——接缝清单与 mikado A2 都没有这一项。
- 基线证据：上述两条 grep 计数（667 / 272）。
- 判定：未发现反例（对「接缝成立」而言）；迁移口径漏项，次要。
- 严重度：次要。

### AA3-05 接缝 2 未发现反例

- 对象：seams.md 接缝 2（:41-69）。
- 反例内容：传输层替换的两种现成写法均验证属实：QA 全替身 window.pywebview = { api: api }（local/tests/fixtures/runtime_bridge.js:752）；契约测试动态替换全局函数先例（test_ui_contract.py:2383-2385，window[name] / eval）。44 个桥接名、24 处视图直发复算一致（`git grep -hoE 'api\("[a-z_0-9]+"' 7e2d31c -- local/ui ':!local/ui/m' | sort -u | wc -l` = 44；三视图文件 -o 计数 = 24）。改名判「不成立」与机制缺失的写法自洽。
- 基线证据：同上三条命令与文件行号。
- 判定：未发现反例。
- 严重度：不计条。

### AA3-06 接缝 4 未发现反例

- 对象：seams.md 接缝 4（:120-148）。
- 反例内容：测试侧覆写在基线沙箱可行：test_ui_contract.py:1659-1684 用 vm.createContext + 逐文件 vm.runInContext 顺序注入，function esc（state/time.js:123）声明落 context 全局，后置赋值可覆写——「不改源码替换行为」成立。实现替换点唯一（time.js:123 一行、115 处调用运行期按名解析）属实。两个挡路项（terms.js:46 局部遮蔽、转义集无契约测试）文档已如实标注。
- 基线证据：test_ui_contract.py:1659-1684；`git grep -n "function esc" 7e2d31c -- local/ui/state/time.js` = :123。
- 判定：未发现反例。
- 严重度：不计条。

---

## 角度 2：只能靠「读代码判断」、没有真正可跑判据的节点

### AA3-07 D「跨块 24 方法安置」主判据引用了清点脚本不具备的能力

- 对象：mikado.md D 节点完成判据（:80-83）「api_methods.py 复算『跨块』名单为空」；B1（:40-43）后半「跨块名单 24 个与归块表一致」。
- 反例内容：plan/scripts/api_methods.py 全文 152 行只有 [summary]/[public]/[detail]/[fields]/[locks] 五节输出，没有任何块归属逻辑（全文无「跨块」或 block 字样）。「复算跨块名单为空」用现有脚本跑不出来；「与归块表一致」也只能人工读表。B1 自称「文档动作」，但它真正的产出物（机器可读的归块清单）在树上不存在，导致 D 的完成无法机器验收。
- 基线证据：`grep -n "跨块\|block" plan/scripts/api_methods.py` 零命中；脚本输出节名见其 docstring 与 main()。
- 判定：反例成立。
- 严重度：重要。
- 补的可跑命令（先落清单，再校验；临时目录用 %TEMP% 或 tempfile.gettempdir()）：

```bash
# 前提：B1 把归块表落成 blocks.tsv（每行一个公开方法名），这是现缺的机制
python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/api_methods.py \
  | awk '/^\[public\]/{f=1;next} /^\[/{f=0} f && NF {sub(/ \|.*/,""); print}' | sort > "$TEMP/have.txt"
sort blocks.tsv > "$TEMP/want.txt"
comm -23 "$TEMP/have.txt" "$TEMP/want.txt"   # 期望 0 行：每个公开方法都有归属
comm -13 "$TEMP/have.txt" "$TEMP/want.txt"   # 期望 0 行：清单一不多不少
```

### AA3-08 B2 后半、A3、C2 的判据含人工动作，机器验不了

- 对象：mikado.md B2（:46-47「两把模块级锁的归属写进表」）、A3（:34-38「注释覆盖块服务」）、C2（:60-63「remove_advanced_feature 删除或补调用方需计划定」）。
- 反例内容：「写进表」「注释覆盖」是写作动作，「删除或补调用方需计划定」是人工拍板——三者都没有「跑什么命令、期望什么」的形态。A3 还有个时序洞：块服务尚不存在时，「注释覆盖块服务」无从谈起（与 AA3-21 同根）。
- 基线证据：mikado.md :37（A3 判据原文含「注释覆盖块服务」）；prereq.md 4.4（remove_advanced_feature 全仓零调用点，q-045）。
- 判定：反例成立。
- 严重度：次要。
- 补的可跑命令：

```bash
# A3：新写夹具泄漏守卫（凡构造块服务必须登记进夹具，否则红），先写后用
python -m unittest discover -s local/tests -p "test_fixture_leak_guard.py" -v
# C2：把拍板结果冻结成断言（删=0；留=大于定义行数的命中）
git grep -c "remove_advanced_feature" -- local/
# B2 锁归属：[locks] 节已给来源行，归属判定并入 AA3-07 的 blocks.tsv 一并 comm 校验
```

### AA3-09 E1「app.X 旧名再导出保全」的判据空转：全量绿证明不了节点内容

- 对象：mikado.md E1（:85-88），完成判据只有「全量绿」。
- 反例内容：E1 的内容是「旧名再导出不能删」，但它的保护理由（AGENTS.md：测试按 app.X 打补丁）在 A1 完成后即消失——70 处补丁全迁走后，删光全部再导出照样全量绿。判据测不到节点声称要保的东西。
- 基线证据：mikado.md :20（A1 是 C 块前置）+ :87（E1 判据仅全量绿）；A1 判据（:26）要求补丁清单为空。
- 判定：反例成立。
- 严重度：次要。
- 补的可跑命令：

```bash
python -I -c "import app; names='Api DEMO PREFS worker_command AppLifecycle PlanCoordinator updater _advanced_features _tunnel_manager _credential_store _update_check _single_instance _component_packages check_latest_release'.split(); missing=[n for n in names if not hasattr(app,n)]; assert not missing, missing"
```

### AA3-10 B3 判据命令在基线就输出 3 行，与「仍仅 _emit 一处」不符

- 对象：mikado.md B3 完成判据（:51-52）。
- 反例内容：`git grep -n "evaluate_js" -- local/app.py` 在基线命中 3 行：app.py:1122（真调用）+ :638 与 :4837（两行注释）。「仍仅 _emit 一处」要人工剔注释，命令本身不保证。
- 基线证据：`git grep -n "evaluate_js" 7e2d31c -- local/app.py` → 638 / 1122 / 4837。
- 判定：反例成立（判据命令与表述不匹配，非机制问题）。
- 严重度：次要。
- 补的可跑命令：`git grep -nE "self\._window\.evaluate_js\(" -- local/app.py | wc -l`（期望 1）。

### AA3-11 各文档引用的基线期望值与自家复算命令实测对不上（24 vs 25；64/66 vs 79）

- 对象：seams.md 接缝 3（:77「24 个函数名」、:118「基线输出 24」）；mikado.md 口径（:10「24 名」）与 A2（:30「去重 64 名」）；prereq.md §2.2（272 行去重 64 名口径）；提案 §4（「66 个成员」，reconcile §3.3 判成立）。
- 反例内容：seams.md 自己的复算命令（:113-115）在基线实测输出 25 个名字——paintClockPopFeedback（state/clock.js:116）被漏数；mikado 转引了同一个 24。A2 引「去重 64 名」，但按其自报命令去重实测 79 名，其中至少 sync_api.sync_playwright/TimeoutError（test_business_clock_wiring.py:307-308、test_worker_boundaries.py:549-550）与 self.api.fail/ack_lost（test_phone_service.py:532、test_retry_phone_integration.py:271，fake 对象同形赋值）不是 Api 实例成员——剔除规则未写进任何口径；64（prereq/seams/mikado）、66（提案）、79（命令实测）三个数互不对账。完成判据用命令计数是自洽的，但「引用值」不能用作命令输出的人工核对基准——照着 24 验命令的人会把正确的 25 判成跑错。
- 基线证据：seams.md:113-115 命令实测 25（名单含 paintClockPopFeedback）；成员名去重 79；prereq.md 全文无 _start_order/_cloudflare_starting（另见 AA3-16）。
- 判定：反例成立。
- 严重度：次要。

---

## 角度 3：文件集映射与交集（基线实数）

### AA3-12 C1..C5 五个工作项改的是同一个 local/app.py

- 对象：mikado.md 批次说明（:168「C1..C5 …… 互不撞文件（每块只动自己的方法组与对应测试文件）」）与树图（:19「C1..C5 互不依赖可并行」）。
- 反例内容：五块是同一个约 4900 行文件的连续切片（更新块方法体集中 app.py:2057-2231 一带、计划块 2854-3270 一带、组件块 1425-1733，prereq §2.1 均带行号），加上 B3 要动的共享上下文与 _emit（:1119 唯一 evaluate_js 注入点），行组不相交但文件同一——五路「并行」在 Git 上只能串行提交或手工叠加。mikado 用「不撞文件」为并行辩护，字面即假。
- 基线证据：prereq.md §2.1 各块方法行号；app.py 基线行数约 4900。
- 判定：反例成立。
- 严重度：重要。

### AA3-13 测试文件交集实数：test_application_services.py 被全部五个块工作项触碰

- 对象：mikado.md :168「每块只动自己的方法组与对应测试文件」；mikado C1..C5 各节。
- 反例内容：272 个写点分布在 19 个测试文件、70 个补丁点分布在 8 个测试文件（两条复算命令实测，与声称的总量一致）。按块归组后，同一文件被多个块工作项同时认领：
  - test_application_services.py：C1（api._update_result x3、_update_staging_path x2、_update_installer x1）+ C3（_phone x7、_cloudflare x4、_phone_channel、_cloudflare_starting）+ C4（_relay x10、_auto_relogin x7、_begin_auto_relogin x2、_push_login_expired x2）+ C5（_plan x7、_proc x2、_proc_tree x2）+ D（_window x12、_emit x8、_tray x3、check/_do_check_inner/request_window_close 等）——五个工作项全占；
  - test_release_audit.py（mikado 把它归 C2 的验收文件）：C2（_advanced_busy/_component_service/_ocr_component_service）+ C3（:102-104 _phone/_cloudflare/stop_phone_access、:27 _phone_access_lock）+ C4（:28 _credential_lock）+ C5（:81/82/90/91/92 _start_requests/_start_order/_canceled_start_ids）+ D（:32 _emit、:31 _is_busy_locked、:85/97 _terms_gate）；
  - test_runtime_bundle.py：C1（app.sys.frozen 补丁）+ C5（46 个写点中 _plan/_proc 系与 app.Api._run_plan_task 补丁）+ D（app.Api._run/_spawn 补丁、worker_command 补丁 :433）。
- 基线证据：`git grep -cE "(self\.api|api)\.[A-Za-z_0-9]+ ?=" 7e2d31c -- local/tests`（19 文件 272 行）；`git grep -cE "(mock\.)?patch(\.object)?\(\s*(app|local_app|self\.app|self\.local_app)\." 7e2d31c -- local/tests`（8 文件 70 处）；逐文件成员名单来自同命令 -o 提取。
- 判定：反例成立。
- 严重度：重要。

### AA3-14 G1 与 G2 的文件集相交于 test_layer_boundaries.py，与两处「文件集不相交」声明矛盾

- 对象：mikado.md :11（「两目标可并行……文件集不相交」）、:170（「G1 与 G2 文件集不相交，两条目标线整体可并行」）；对照 E2（:90-93）与 F3（:151-154）。
- 反例内容：E2（G1）要求「分层边界测试扩展到新服务模块」，F3（G2）要求前端分层守卫「并入 test_layer_boundaries 的前端扩展」——两个叶子节点改同一个 local/tests/test_layer_boundaries.py。并行执行必撞；先后执行则谁后谁重基。声明与自家节点清单冲突。
- 基线证据：mikado.md :11/:92/:153/:170 原文；test_layer_boundaries.py 基线存在。
- 判定：反例成立。
- 严重度：重要。

### AA3-15 G2 内部 F2.1..F2.6「互不依赖、按文件并行」：通知分发面是共享文件

- 对象：mikado.md :169（「F2.1..F2.6 在 F1 完成后按 state 文件并行（每文件一个节点，互不依赖）」）；seams.md 接缝 3 注册样例（:99-102）。
- 反例内容：seams.md 的样例机制是单条全局回调（onStatePainted(() => { paintLogin(); paintRail(); ... })），六个 state 文件的 painter 全部注册进同一处；若改为按 kind 分流，kind 到 painter 的映射表也是同一个共享文件。六个节点无论哪种设计都要编辑同一段注册代码，「互不依赖、可并行」只在「每节点自带独立监听器且注册点分散到各自 controllers 文件」这一未写明的前提下才成立。
- 基线证据：seams.md:93-102；store.js 基线无任何分发机制（见 AA3-01）。
- 判定：反例成立。
- 严重度：次要。

### AA3-16 迁移底稿有洞：prereq §2.2 六张「被改写成员」表漏了两个真实 Api 字段

- 对象：seams.md :20（「prereq §2.2 分块列全」）；mikado.md A2（:30「分布见 prereq §2.2 六个块的被改写成员表」）；prereq.md §2.2。
- 反例内容：_start_order（app.py:890 实例字段，测试改写 test_release_audit.py:82/91）与 _cloudflare_starting（app.py:960，改写 test_application_services.py）都是真实 Api 成员且被测试改写，但 prereq §2.2 六张块表与跨块表均未收录（prereq.md 全文检索零命中）。按这张底稿做 A2 迁移与 B2 字段归块会漏。
- 基线证据：`git grep -n "_start_order" 7e2d31c -- local/app.py`（:890 起）；`git grep -n "_cloudflare_starting" 7e2d31c -- local/app.py`（:960 起）；`grep -n "_start_order\|_cloudflare_starting" plan/prereq.md` 退出码 1。
- 判定：反例成立。
- 严重度：重要。

---

## 角度 4：三个真实用例推算测试改造成本

### AA3-17 三样板逐处改动量实测

- 对象：seams.md 接缝 1「怎么替换」；mikado.md A1/A2；plan-redteam.md 判据 6。
- 反例内容：三个样板（均为基线原行）：
  1. 类级补丁 mock.patch.object(app.Api, "_run", ok_run)（test_runtime_bundle.py:397，同一 with 块还叠了 login_service.check_reason_line 与 app.PlanCoordinator 两个不同层的补丁；:443/445 是同一实例两轮补丁）：构造注入化要求服务构造缝先存在，2-6 行/处；同一实例在 with 块内外换行为的（397 到 443 两段），还要把假件改成有状态，另 +3-8 行。一个 with 块混三种补丁形态（类方法/他模块函数/app 模块类），各需不同注入机制。
  2. 实例方法遮蔽 self.api.check = lambda request_id="": fired.set()（test_application_services.py:1473）：若拆后的服务仍按可替换属性读，1-2 行/处，是最便宜的一类。
  3. 模块级补丁 mock.patch.object(local_app, "worker_command", lambda ...)（test_application_services.py:2219、test_cancel_signup.py:477、test_runtime_bundle.py:433）：构造 kwarg 化 1-3 行/处；但 :2219 的 setUp 一次打 12 个模块补丁（PREFS/DATA_DIR/CREDENTIAL_FILE/LOG_FILE/ensure_data_dir/_credential_store/_CREDENTIAL_STORE_OK/worker_command/DEMO/_advanced_features x2/_tunnel_manager），字段横跨全部五个块的依赖——这一处注入化必须等五块全部存在，一次就是十几行。
- 基线证据：上述文件:行号（git show 7e2d31c 逐段核对过）。
- 判定：反例成立（成本无法按「机械改写」平推）。
- 严重度：重要。

### AA3-18 总量推算：红队与依赖树对该成本零量化，实际约「半个生产拆分」

- 对象：mikado.md A1/A2（两个「叶子」，零成本注记）；plan-redteam.md 判据 6 与总评（把测试先行列为头号卡点但全文无一处数字）。
- 反例内容：按 AA3-17 的每处行数平推：写点 272 x 2~3 行 + 补丁点 70 x 2~5 行 ≈ 800-1000 行测试侧 diff，撒在 19 个改写文件 + 8 个补丁文件（其中 13 个文件经 stop_auto_relogin_on_cleanup 夹具构造 Api，夹具本身要随 A3 扩）。再叠加无人计账的约 395 处私有成员读点（AA3-04）：门面若按提案「只做转发和参数检查」不再转发数据字段，每处 1-2 行，全量约 1200-1800 行。对照生产侧：153 个方法切片搬移约 2500-3000 行（app.py:1036-4409 一带）——测试改造是半个生产拆分的隐藏工序，且按 AA3-21 无法先行，只能与五个 C 块一一绑定。机械改写按熟练密度估 2-4 人日，逐块假件与夹具设计另计；三份文档给出的信息量是零。
- 基线证据：667/272/70 三条计数命令；`git grep -l "stop_auto_relogin_on_cleanup" 7e2d31c -- local/tests | wc -l` = 13；mikado.md :26-38、plan-redteam.md :73-82/:111。
- 判定：反例成立。
- 严重度：重要。

---

## 角度 5：目标值「依赖环 <=3」「state/ 越层 0」

### AA3-19 「state/ 越层 0」：要么同时改 >=12 个文件，要么被注入路线字面满足而实质未达成

- 对象：提案 §4（「state/ 层有 62 处调用」）与红队判据 4（「越层 = 0 加白名单」）；mikado.md G2 整树。
- 反例内容：「可能达不到」的具体机制与「必须同时改哪几处」：
  1. 25 个被调名里 10 个是查询/纯函数（AA3-02），清零的唯一合规路径是把定义搬层：noteSignedTasks（controllers/refresh.js:398 搬入 state）、selectionSignature（views/plan-panel.js:901，只读 S.selected，可直搬）、verifiedSigned（plan-panel.js:614，依赖 findItem，findItem 已在 state/filters.js:2，可直搬）、numOrNull（controllers/tick.js:162）、hmsDay/submittingDetail/effectiveRetryDeadline（plan-panel.js:139/1102/1188）、termsLocked（controllers/terms.js:13，读 S.terms，可直搬）、clockPopOpenNow（views/clock-pop.js:29，读 S.clockPopOpen，可直搬）——十个定义、至少 4 个源文件；
  2. reloginAutoLive 读的是 views 层模块变量 reloginRelay（views/relogin.js:17 定义、:444 唯一写点）——所有权必须先搬进 S；
  3. scheduleSignedRefresh 触发反转成 store 监听（AA3-03）；
  4. 四处 typeof 防御（login.js:29、filters.js:307、task-display.js:58、labels.js:61）随搬层一并删除。
  合计至少 12 个文件一次成势——逐文件「grep 归零」判据逼每个文件一步到位，无法小步。另一条路：对查询型统一注入闭包，grep 照样归零、F3 守卫照样绿，但 state 层运行期依赖 views 提供的函数原封不动——目标被字面满足，它声称要消灭的耦合没被消灭；现有判据（词法 grep）测不出这两条路的区别。
- 基线证据：AA3-02 的定义层 grep；views/relogin.js:17/444；seams.md:109 与 mikado.md:153（均为词法口径）。
- 判定：反例成立。
- 严重度：重要。

### AA3-20 「依赖环 <=3」：基线已实测 4 个两模块调用环，环清单三份文档都没给全

- 对象：红队判据 3 的目标值（环数终点）；mikado.md G2（未含任何环节点）；提案 §4（「33 个在同一个依赖环里」「先把放错层的十来个函数搬走」，无清单）。
- 反例内容：按调用图实测（state 文件调用 views/controllers 定义 + 反向调用），基线至少存在 4 个两模块环，每个都要函数搬层才能断：
  1. state/plan.js 与 controllers/refresh.js 互调：state 调 noteSignedTasks（plan.js:103）与 scheduleSignedRefresh（:104）；refresh.js 三处调 syncResultSelection（:421/482/502，定义在 state/plan.js:122）；
  2. state/clock.js 与 views/clock-pop.js 互调：state 调 renderClockPop/clockPopOpenNow/paintClockPopFeedback（clock.js:79/115/116/135/160）；clock-pop.js 调 clockUiState（:72，定义 state/clock.js:221）与 businessNow（:149）；
  3. state/filters.js 与 views/plan-panel.js 互调：state 调 verifiedSigned（filters.js:307）与 setResult；plan-panel.js 的 verifiedSigned 调 findItem（定义 state/filters.js:2）；
  4. state/task-display.js 与 views/plan-panel.js 互调：state 7 次调 plan-panel 定义的 verifiedSigned/hmsDay/submittingDetail/effectiveRetryDeadline；plan-panel.js:1118/1128 调 state 定义的 taskDisplayLabel/taskDisplayDetail。
  「<=3」意味着只容许剩 3 个环——而基线起点已是 4 个小环加第一轮所称 33 脚本大环；要可判，必须先有完整的「搬走哪些函数」清单，这份清单三份文档都没给（红队判据 3 自己点了「连十来个函数的清单都没给」）。另外 ESM 渐进混迁期间，未迁脚本间的环不经静态 import，红队建议的 check_ui_layers.mjs 对它们不可见——混迁态下「环数」这个目标值不可测。
- 基线证据：上述文件:行号；`git grep -n "syncResultSelection" 7e2d31c -- local/ui/controllers/refresh.js`（3 处）；plan-redteam.md :43（清单缺失）、:49（判定脚本尚需新写）。
- 判定：反例成立。
- 严重度：重要。

---

## 角度 6：并列安排、实有先后依赖的项

### AA3-21 A1/A2/A3 与 C1..C5 互为前后，树却画成无环叶子——按树执行死锁（阻断）

- 对象：mikado.md :20（「C1..C5、D 另需：A1 + A2 + A3 —— 否则补丁悄悄落空」）、:24-38（A1/A2/A3 三节点全标「依赖：无（叶子）」）、:156-166（「第一批可并行的叶子节点」把三者列为第 1-3 项）。
- 反例内容：三个叶子的完成判据全都以 C 块的产出物为指称对象：
  - A1 判据「清单为空或每处指向新模块路径」（:26）——新模块路径在 C1..C5 抽出服务前不存在；唯一能在 C 之前满足的分支是「清单为空」，即删光 70 处补丁，等于先废掉测试覆盖再动结构，与 A1 自己的存在理由（「否则补丁悄悄落空」）矛盾；
  - A2 判据「计数 0（已改为替身服务或显式端口）」（:31）——替身服务不存在时无处可改；
  - A3 判据「注释覆盖块服务」（:37）——块服务不存在时无从覆盖。
  即 C 依赖 A 完成、A 的完成又依赖 C——树自锁死。实证：test_application_services.py:2206-2225 的 setUp 12 个模块补丁横跨五块依赖字段，构造注入化必须等五块全部存在（AA3-17 样板 3）。
  修复：把 A1/A2 拆成 A1.i/A2.i 并入各 C.i（每块先迁自己的补丁与改写、再抽服务，同提交）；A3 拆成「夹具机制就绪（现在可做）+ 每块接入时登记（随各 C.i）」两段判据；A1 与 A2 的同文件交叠（test_runtime_bundle 15 补丁点 + 46 写点、test_update_check 21+26、test_release_audit 2+21）也要求同文件内排队，不是三个互不相关叶子。
- 基线证据：mikado.md :20/:26/:31/:37/:158-160；test_application_services.py:2206-2225；三组同文件计数（AA3-13 命令）。
- 判定：反例成立。
- 严重度：阻断（树是执行调度物，按图推进在第 1 批就卡死）。

### AA3-22 mikado G2 与提案步骤 1（三块状态机）从未排布，而两者改同一批收口行

- 对象：mikado.md F2.2（:126-129，目标行 login.js:70-76、137-140）与 G2 作用域声明（:5-11）；提案 §2 步骤 1（:41「组件、登录、计划栏三块先改成状态机」）与审计结果候选切法（:65「先修六条缺陷，再铺路、三块状态机、拆 Api、grab.py」）；plan-redteam.md 判据 1/2。
- 反例内容：F2.2 要替换的 state/login.js:70-76（paintLogin/paintRail/paintSelected/paintBoardActions/refreshLoginEmptyState 五连）与 :134 syncLoginDependentView（注释自称「登录态关联视口的统一收口（P1）」）正是登录状态机步要重构的同一批收口；提案候选切法把状态机排在拆 Api 之前，mikado 树则把 G2 当作独立可执行目标、F2.2 依赖只挂 F1。三份文档没有任何一处声明这两个工作项的先后：G2 先做，状态机步把同一批行重写一遍（前一轮白做）；状态机先做，mikado 全部行号口径与 F2.2 的 grep 判据坐标作废。红队判据 2 只点了「状态机与 ESM/分目录交叠」，没点「状态机与 G2 越层清零交叠」。
- 基线证据：state/login.js:70-76、:134（git show 原文与注释）；提案 :41/:65；mikado.md :126-129。
- 判定：反例成立。
- 严重度：重要。

### AA3-23 F1b、F2.x 注册点、接缝 2 附注的「24 处直发桥接同批处理」三者可能同改 app.js/controllers，被标成两两可并行

- 对象：mikado.md :119（F1b「不阻塞 F2.x」）、:170（「G2 内 F1b 与 F2.x 无依赖边，也可并行」）；seams.md :104（注册「放现有 controllers 文件或 app.js 可不动 index.html」）与 :152（「24 处视图直发桥接……建议同一计划批次处理」）。
- 反例内容：F1b 改 app.js:90 的 12 键字面量；F2.x 的注册点按 seams.md 可落 app.js 启动段；「24 处直发桥接收口」要把 views/phone.js、views/relogin.js、views/settings.js 的 api() 调用挪进 controllers——三者的落点文件重叠（app.js、controllers/*），mikado 既没把 24 处收口立节点，也没写 F1b/F2 并行的规避条件（注册点进 controllers 专属文件才不撞）。
- 基线证据：seams.md:104/:152；mikado.md :119/:170；`git grep -hoE 'api\("[a-z_0-9]+"' 7e2d31c -- local/ui/views/phone.js local/ui/views/relogin.js local/ui/views/settings.js | wc -l` = 24。
- 判定：反例成立。
- 严重度：次要。

（E2 与 F3 的先后问题并入 AA3-14，不另立条。）

---

## 严重度汇总

| 严重度 | 条数 | 条目 |
|---|---|---|
| 阻断 | 1 | AA3-21 |
| 重要 | 13 | AA3-01、02、03、07、12、13、14、16、17、18、19、20、22 |
| 次要 | 7 | AA3-04、08、09、10、11、15、23 |

三条最狠发现：
1. AA3-21（阻断）：mikado 树把 A1/A2/A3 画成可并行叶子，而它们的完成判据只能由 C1..C5 的产出物满足——按树执行第一批就死锁；修复是拆成每块自带的迁移步骤，不是三个独立前置。
2. AA3-03（重要）：接缝 3 在最脆弱点（plan.js:103 返回值分支）按文档写法替换后，判据的 grep 与测试照常全绿而「成功后有界刷新」链已丢——该链零测试覆盖，接缝自己的验收网在最需要的地方是空的。
3. AA3-13/AA3-14（重要）：「互不撞文件」「文件集不相交」两处并行性声明被基线实数直接推翻——test_application_services.py 被全部五个块工作项触碰，G1 与 G2 相交于 test_layer_boundaries.py；所谓可并行，实际上是同一批文件上的串行排队。

## 边界声明

- 只读清单内的文件：提案工作区版、plan/ 五份 md、extra/ 三份；基线代码与测试经 `git show 7e2d31c:<路径>` 读取。未打开 redo/ 根其他文件、supplement/、review/、code-issues.md、ui-states.md、.claude/、local/data、server/data、config.json、.env。
- 执行过的命令全部只读：git grep / git show / git cat-file -e / git log / git status、ls / wc / grep / awk / comm（临时文件写在系统临时目录）、python -I plan/scripts/api_methods.py（只读清点脚本，复跑一次核对 153/60/93）。未跑测试与构建、未联网、未改除本文件外的任何文件。
- 未验证项：所有判据命令的「改造后」行为只能静态推断；AA3-03 的等价性反例基于对同步派发语义与事件时序的静态推演，未经 node 沙箱实跑（本轮禁跑测试）。行号与计数均可按文中命令在基线上复现。
