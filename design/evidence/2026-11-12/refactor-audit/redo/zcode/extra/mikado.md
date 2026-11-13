# T10 重构前置：Mikado 静态依赖树（mikado）

## 声明与口径

- **本轮禁止改代码。本树不做「试改后回滚」的 Mikado 实验验证**：全部边来自静态阅读（基线 `7e2d31c`、plan/ 五份交付、提案 `design/proposals/engineering-refactor.md` §4 的审计数字）与既有测试的存在性核对，**未经实验证伪**。
- 每个节点给一条可跑命令或测试名证明「它已完成」。命令在执行轮次于当时的树上复跑（**不带** `7e2d31c` 提交钉）；本文括号里的基线数字只作期望值，都是本任务在基线上取证过的。
- 事实底座：Api 方法/字段/补丁面 `plan/prereq.md` §2；越层与桥接 `plan/prereq.md` §3-§4 与本任务复算（同目录 seams.md）；行为链 `plan/desktop.md`；提案数字经 `plan/reconcile.md` §3.3/§四 核过（153/60、62、24、42、66 等）。
- 目标节点两个：
  - **G1「Api 拆五块」**：更新、组件、手机访问、登录恢复、计划五块从 local/app.py:813 的 `class Api`（153 方法 / 60 公开 / 93 私有，prereq §2）抽成服务对象；跨块 24 方法安置；app.py 保留组合根与 `app.X` 旧名再导出。
  - **G2「state/ 越层清零」**：state/*.js 不再直接调用 views/controllers 顶层函数（提案口径 62 处；本任务复算 53 行 / 58 次 / 24 名，见 seams.md 接缝 3；完成判据按复算命令归零）。
- 两目标可并行：G1 动 local/app.py 与 local/tests；G2 动 local/ui/state、local/ui/controllers、local/ui/app.js，文件集不相交（G2 的注册点放现有 controllers 文件或 app.js 可避免动 index.html）。

## G1「Api 拆五块」树

```
G1 = E1(旧名再导出保全) + E2(分层边界扩展)
E1 ← D(跨块24安置) ← C1..C5(五块抽出，互不依赖可并行)
E2 ← C1..C5 + D
C1..C5 ← B3(共享上下文抽出) ← B1(归块表定案) + B2(字段锁表定案)
C1..C5、D 另需：A1(app补丁点改造) + A2(成员改写改造) + A3(构造夹具贯通)  —— 否则补丁悄悄落空
```

### A1 app 模块补丁点改造完
- 事实：基线 app 模块一级属性上的 patch 调用点 70 处（app.Api×6、app.subprocess×5、app.sys×5、local_app.updater×14、local_app.threading×6、local_app._advanced_features×6 等）；`patch("app.X")` 字符串形态 0 处。提案 §4 口径「42 个名字」（reconcile §3.3 判成立）。
- 为什么前置：提案 §4「拆的时候这些补丁会悄悄落空而不报错」——patch.object 落旧路径继续指向旧类，实例属性改写迁块后名字消失即静默失效。
- 完成判据：`git grep -nE "(mock\.)?patch(\.object)?\(\s*(app|local_app|self\.app|self\.local_app)\." -- local/tests` 清单为空或每处指向新模块路径；`python -m unittest discover -s local/tests -p "test_*.py" -v` 全绿。
- 依赖：无（叶子）

### A2 Api 实例成员改写改造完
- 事实：基线 `(self.api|api).X =` 272 行，去重 64 名（提案口径 66，差 setattr(`_cancelling`)与别名变体）；分布见 prereq §2.2 六个块的「被改写成员」表（_plan 16、_emit 36、_last_check 21、_activities 20、_window 16、_relay 11、_update_result 11 等）。
- 完成判据：`git grep -nE "(self\.api|api)\.[A-Za-z_0-9]+ ?=" -- local/tests` 计数 0（已改为替身服务或显式端口）；`python -m unittest discover -s local/tests -p "test_application_services.py" -v` 全绿。
- 依赖：无（叶子）

### A3 构造与清理夹具贯通
- 事实：`Api.__init__(clock=None)` 只注时钟（app.py:814）；构造即起自动重登线程，测试必须经 `local/tests/fixtures/api_threads.py` 的 `stop_auto_relogin_on_cleanup`（AGENTS.md、grab.md T5）。
- 要补的机制：五块服务对象同样持有线程/进程（更新下载线程、手机访问监听、计划 worker），夹具扩成「构造即登记、cleanup 即收」。
- 完成判据：`git grep -n "stop_auto_relogin_on_cleanup" -- local/tests/fixtures/api_threads.py` 命中且注释覆盖块服务；`python -m unittest discover -s local/tests -p "test_application_services.py" -v` 与 `-p "test_silent_relogin.py" -v` 全绿。
- 依赖：无（叶子）

### B1 六十公开方法归块表定案（文档动作）
- 底稿：prereq §2.1 全表——更新 4 / 组件 11 / 手机访问 6 / 登录恢复 10 / 计划 5 / 跨块 24（4+11+6+10+5=36+24=60）。
- 完成判据：`python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/api_methods.py` 输出方法总数 153、公开 60，跨块名单 24 个与归块表一致。
- 依赖：无（叶子）

### B2 字段与锁归块表定案（文档动作）
- 底稿：prereq §2.2——实例字段 67；实例锁 `_lock/_credential_lock/_phone_access_lock`、`_shutdown_done_event`；模块级 `_PHONE_LOG_LOCK`（q-036）、`_LIFECYCLE_LOCK`（q-037）；提案 §4「一把被 67 个方法用的锁」即 `_lock`、「23 个在三个以上方法里赋值的标志位」。
- 完成判据：api_methods.py 的 [fields] 节复算 67；`git grep -n "_PHONE_LOG_LOCK\|_LIFECYCLE_LOCK" -- local/app.py` 两把模块级锁的归属写进表。
- 依赖：无（叶子）

### B3 共享上下文抽出
- 内容：`_window/_emit/_clock/_lock/_phone/_plan` 等被 ≥2 块读写的成员收进显式上下文对象；`_emit` 保持唯一 evaluate_js 注入点（app.py:1119），12 个 kind 不变（prereq §4.3）。
- 完成判据：`git grep -n "evaluate_js" -- local/app.py` 仍仅 `_emit` 一处；`python -m unittest discover -s local/tests -p "test_application_services.py" -v` 全绿。
- 依赖：B1、B2

### C1 更新块抽出（4 方法）
- 方法：check_update(2057)/update_download(2117)/update_cancel(2171)/update_launch(2177)；字段 `_update_cancelled/_update_installer/_update_installer_path/_update_request_id/_update_result/_update_staging_path/_updating`；补丁 app.sys、app.subprocess（prereq §2.1/§2.2）。
- 完成判据：`python -m unittest discover -s local/tests -p "test_update_check.py" -v`；`python -m unittest discover -s local/tests -p "test_updater.py" -v`。
- 依赖：B3（另需 A1/A2 已迁移对应补丁与改写）

### C2 组件块抽出（11 方法）
- 方法清单 prereq §2.1 组件表（download_advanced_feature 1425 至 schedule_component_auto_update 3963）；前置拍板：`remove_advanced_feature` 全仓零调用点（prereq §4.4），删除或补调用方需计划定。
- 完成判据：`python -m unittest discover -s local/tests -p "test_advanced_features.py" -v`；`python -m unittest discover -s local/tests -p "test_release_audit.py" -v`。
- 依赖：B3

### C3 手机访问块抽出（6 方法）
- 方法清单 prereq §2.1 手机访问表（phone_access_state 3767 至 schedule_phone_restore 3937）；测试已有整块替身先例 FakePhoneService（test_application_services.py:283-289）。
- 完成判据：`python -m unittest discover -s local/tests -p "test_phone_service.py" -v`；`python -m unittest discover -s local/tests -p "test_phone_http.py" -v`。
- 依赖：B3

### C4 登录恢复块抽出（10 方法）
- 方法清单 prereq §2.1 登录恢复表（prepare_phone_relogin 4043 至 phone_relogin_cancel 4248）；`_relay` 11 处替身、`_credential_lock` 替换迁移（prereq §2.2）。
- 完成判据：`python -m unittest discover -s local/tests -p "test_silent_relogin.py" -v`；`python -m unittest discover -s local/tests -p "test_login_relay_service.py" -v`；`python -m unittest discover -s local/tests -p "test_login_relay.py" -v`。
- 依赖：B3

### C5 计划块抽出（5 方法）
- 方法：start_request_state(2854)/cancel_start_request(2891)/start_plan(2923)/cancel_task(3234)/stop_plan(3242)；补丁 `app.Api._run_plan_task`、`app.subprocess`；`_plan` 16 处、`_proc` 6 处改写迁移（prereq §2.2）。
- 完成判据：`python -m unittest discover -s local/tests -p "test_signup_plan.py" -v`；`python -m unittest discover -s local/tests -p "test_runtime_bundle.py" -v`。
- 依赖：B3

### D 跨块 24 方法安置
- 内容（prereq §2.1 跨块表）：clock_snapshot/sync_clock/bootstrap/help/front_ready、check/list_activities/cancel_signup/login/grab、窗口生命周期组 plan_active_for_close/ask_window_close/request_window_close/hide_window/show_window/window_visibility、shutdown/stop、open_data/open_latest_release/get_license_text、save_prefs/accept_terms/withdraw_terms——归入「窗口与生命周期」「学校动作」「条款与偏好」等块或保留 Api 壳。
- 完成判据：api_methods.py 复算「跨块」名单为空（每个公开方法都有归属）；`python -m unittest discover -s local/tests -p "test_terms_consent.py" -v` 全绿（条款跨块链路）。
- 依赖：C1..C5

### E1 app.X 旧名再导出保全
- 依据：AGENTS.md「app.py 保留了一批旧的模块级名字作再导出，因为测试按 app.X 打补丁，重构时不要删」。
- 完成判据：`python -m unittest discover -s local/tests -p "test_*.py" -v` 全量绿（约 1700 例）。
- 依赖：D

### E2 分层边界测试扩展到新服务模块
- 依据：提案 §原则「依赖单向，用测试守住（现有的 test_layer_boundaries 扩展）」；现测试守 domain/application 的 import 与注入边界（local/tests/test_layer_boundaries.py 的 ImportBoundaryTests/InjectionBoundaryTests）。
- 完成判据：`python -m unittest discover -s local/tests -p "test_layer_boundaries.py" -v`（含新服务模块的边界用例）。
- 依赖：C1..C5、D

## G2「state/ 越层清零」树

```
G2 = F3(前端分层守卫测试)
F3 ← F2.1..F2.6(六个 state 文件清零，按文件可并行) ← F1(store.js 通知/注入口)
相邻缝：F1b(window.onBackend 拆注册函数) ← F0(加载顺序契约保持，既有，全程须绿)
F1b 不阻塞 F2.x；ESM 迁移（提案已定采用）是另一条更大线，本树按「不动加载方式」口径搭，
若与 ESM 同批做，树根换成 ESM 迁移节点（提案 §待确认 1：随「前端按功能分目录」一步只拆一次）。
```

### F0 加载顺序契约保持（校验型节点）
- 事实：既有用例 `test_script_load_order_puts_views_before_dependents`（test_ui_contract.py:463-471）；`read_ui_scripts()`（test_ui_contract.py:35）按 index.html 加载序拼接全部业务脚本、不含 led.js；store.js 在 index.html:562 最先加载。
- 完成判据：`python -m unittest discover -s local/tests -p "test_ui_contract.py" -k load_order -v`。
- 依赖：无（叶子；G2 全程保持绿）

### F1 store.js 通知/注入口落地
- 内容：state/store.js（唯一状态仓库、最先加载）承载通知口 `onStatePainted/notifyStatePainted`（或反向注入口 setPainter）；同步派发；具体写法与等价性论证见 seams.md 接缝 3。store.js 同时是越层清零后 state 层的对外收口点（S 与通知口都在这里，不再散落）。
- 完成判据：`git grep -n "onStatePainted\|notifyStatePainted" -- local/ui/state/store.js` 命中；`python -m unittest discover -s local/tests -p "test_clock_tail.py" -v`（node 沙箱回放不红）。
- 依赖：无（叶子）

### F1b window.onBackend 拆注册函数（相邻缝，随批处理）
- 事实：app.js:90 的 12 键对象字面量 + 内联闭包；12 键名与后端 `_emit`（app.py:1119）和测试替身 runtime_bridge.js（按名直调 `window.onBackend.<kind>`，:370/:406/:429 等）共享，是事实契约（prereq §4.3：12 kind 与 12 键一一对应）。
- 内容：改为逐 kind 注册函数（`registerBackendHandler(kind, fn)` 或等价），键名不得改。
- 完成判据：`git grep -n "window.onBackend = {" -- local/ui/app.js` 字面量消失；`python -m unittest discover -s local/tests -p "test_ui_reliability.py" -v` 全绿（替身按 12 键直调仍通）。
- 依赖：F0 全程保持；不阻塞 F2.x

### F2.1 state/clock.js 越层清零（15 行）
- 调用点：78-81、114-116、134-137、159-162（paintClockStatus/clockPopOpenNow/renderClockPop/paintClockPopFeedback/updateControls/render）。
- 完成判据：`git grep -nE "\b(paintClockStatus|renderClockPop|clockPopOpenNow|paintClockPopFeedback|updateControls|render)\(" -- local/ui/state/clock.js` 计数 0；`python -m unittest discover -s local/tests -p "test_clock_tail.py" -v` 全绿。
- 依赖：F1

### F2.2 state/login.js 越层清零（12 行）
- 调用点：29、33、61、70、72-76、137-140（reloginAutoLive 防御、numOrNull、paintLogin/paintRail/paintSelected/paintBoardActions/refreshLoginEmptyState/paintClockStatus/render）；typeof 防御一并删除。
- 完成判据：`git grep -nE "\b(reloginAutoLive|numOrNull|paintLogin|paintRail|paintSelected|paintBoardActions|refreshLoginEmptyState|paintClockStatus|render)\(" -- local/ui/state/login.js` 计数 0；`python -m unittest discover -s local/tests -p "test_ui_reliability.py" -v` 全绿。
- 依赖：F1

### F2.3 state/plan.js 越层清零（10 行）
- 调用点：51、62、78、80、103、104、106、114、123、128（setBusy/noteStartedFromPhone/render/noteSignedTasks/scheduleSignedRefresh/showTaskResult/selectionSignature）。
- 完成判据：`git grep -nE "\b(setBusy|noteStartedFromPhone|render|noteSignedTasks|scheduleSignedRefresh|showTaskResult|selectionSignature)\(" -- local/ui/state/plan.js` 计数 0；`python -m unittest discover -s local/tests -p "test_signup_plan.py" -v` 全绿。
- 依赖：F1

### F2.4 state/filters.js 越层清零（8 行）
- 调用点：307、343、362、372、381、382、391、392（verifiedSigned 防御、termsLocked、render、setResult）。
- 完成判据：`git grep -nE "\b(verifiedSigned|termsLocked|render|setResult)\(" -- local/ui/state/filters.js` 计数 0；`python -m unittest discover -s local/tests -p "test_ui_conflict_cancel.py" -v` 全绿。
- 依赖：F1

### F2.5 state/task-display.js 越层清零（6 行）
- 调用点：58、100、101、104、148、150（verifiedSigned 防御、hmsDay、submittingDetail、effectiveRetryDeadline）。
- 完成判据：`git grep -nE "\b(verifiedSigned|hmsDay|submittingDetail|effectiveRetryDeadline)\(" -- local/ui/state/task-display.js` 计数 0；`python -m unittest discover -s local/tests -p "test_ui_contract.py" -v` 全绿。
- 依赖：F1

### F2.6 state/conflict.js 与 state/labels.js 越层清零（各 1 行）
- 调用点：conflict.js:147 `termsLocked()`；labels.js:61 `verifiedSigned` 防御。
- 完成判据：`git grep -nE "\b(termsLocked)\(" -- local/ui/state/conflict.js` 与 `git grep -nE "\b(verifiedSigned)\(" -- local/ui/state/labels.js` 计数均 0；`python -m unittest discover -s local/tests -p "test_ui_contract.py" -v` 全绿。
- 依赖：F1

### F3 前端分层守卫测试落地
- 内容：把 seams.md 接缝 3 的复算命令固化成契约用例（views/controllers 顶层函数名清单，剔除 state 自定义名后，与 state 调用 token 求交，期望 0），并入 test_layer_boundaries 的前端扩展（提案 §原则「依赖单向，用测试守住」）。
- 完成判据：`python -m unittest discover -s local/tests -p "test_layer_boundaries.py" -v`（含前端分层用例）；seams.md 接缝 3 复算命令输出 0。
- 依赖：F2.1..F2.6

## 第一批可并行的叶子节点

1. A1 app 模块补丁点改造（G1）
2. A2 Api 实例成员改写改造（G1）
3. A3 构造与清理夹具贯通（G1）
4. B1 六十公开方法归块表定案（G1，文档动作）
5. B2 字段与锁归块表定案（G1，文档动作）
6. F0 加载顺序契约保持（G2，校验型节点，验收 G2 全程）
7. F1 store.js 通知/注入口落地（G2）
8. F1b window.onBackend 拆注册函数（G2 相邻缝）

批次说明：
- C1..C5 在 A1/A2/A3 与 B3 完成后互不撞文件（每块只动自己的方法组与对应测试文件），五块可并行；D 收尾再安置跨块 24。
- F2.1..F2.6 在 F1 完成后按 state 文件并行（每文件一个节点，互不依赖）。
- G1 与 G2 文件集不相交，两条目标线整体可并行；G2 内 F1b 与 F2.x 无依赖边，也可并行。
- B1/B2 是文档动作，先于 B3 完成；A1/A2/A3 与 B1/B2 之间无依赖，可同批启动。

## 节点计数与风险备注

- 节点总数 24（G1 14：A1/A2/A3/B1/B2/B3/C1..C5/D/E1/E2；G2 10：F0/F1/F1b/F2.1..F2.6/F3）；叶子 8（上面第一批清单）。
- 口径备注（不影响完成判据）：提案 §4 的「42 个补丁名 / 66 个改写成员 / 62 处越层」与本文复算命令的口径（70 处调用点 / 64 名 / 53 行 58 次）存在提取范围差异，reconcile.md §3.3 已判提案数字成立；本文一律以「复跑命令计数」为完成判据，提案数字只作对账参照。
- 未验证项：所有节点命令未执行；行为等价（尤其 F2 各文件的 notify 改写）未经 node 沙箱实验，执行轮次按各节点判据命令逐条验证。


## T7 修正补记（2026-11-12，依 AA3 对抗结论与作者攻防辩认错修正，主执行方代录，作者修正方案原文见 extra/defense.md）

- **AA3-21（阻断）**：原树把 A1/A2/A3 列为无依赖叶子并放进「第一批可并行」——作废。三者完成判据都是拆分终态、依赖 C1..C5 产出物，按原树执行第一批即死锁。修正：A1/A2/A3 降级为「随块迁移的对账清单」，每个 C_i 提交成对落地「抽 C_i＋迁移 i 块名下补丁与改写＋全量绿」，分账按 prereq §2.2 补丁归属逐块对账（updater/_update_check 归 C1、_credential_store/_advanced_features 归 C4、_run_plan_task 归 C5、_run/_spawn 随跨块 D）；A3 并入各 C_i 验收。第一批可并行叶子改为 B1、B2、F0、F1、F1b。「先删光 70 处补丁再拆」不采纳（先废测试覆盖，方向反）。
- **AA3-12/13/14（文件交集实数）**：C1..C5 同改 local/app.py，须串行；test_application_services.py 被全部五个块工作项触碰；test_layer_boundaries.py 同时是 G1-E2 与 G2-F3 的目标文件——原「文件集不相交」声明作废，涉及文件按串行排队，不并行。
- **AA3-15**：F2.1..F2.6 共享通知分发面，同批文件，按分发面分组串行，不并行。
- **AA3-07/09（判据不可跑）**：D 的完成判据改为「先给 api_methods.py 增加块归属输出（含跨块名单），再 diff 清单」；E1 的「全量绿」空转判据改为附「新模块可测入口清单」一并验收。B2 后半、C2 的人工判据补命令：`git grep -n "patch(app\." 7e2d31c -- local/tests` 与 `git grep -n "app.Api" 7e2d31c -- local/tests` 计数归零为完成。
- **AA3-10**：B3 的 grep 判据改为排除注释行后恰 1 处 _emit 定义（复跑实测后把实测命令与期望值写死进该节点）。
- **AA3-22**：补边——G2（state/ 越层清零）与提案步骤 1（三块状态机）改同一批 login.js 收口行，相关节点禁止并行，先后由用户在切法拍板时定。
- **AA3-23**：F1b、F2.x 注册点与接缝 2 附注「24 处直发桥接同批处理」可能同改 app.js/controllers——三者并为一组，组内串行。
- **AA3-16**：迁移底稿补 _start_order、_cloudflare_starting 两个字段（见 plan/prereq.md 补记与 q-093/q-094）。
