# ADVERSARIAL-AA2 —— 漏项审计（对 tables.md 表 A/B/D/E，口径 D2/D3/D4/D6/D7）

落盘说明：本文为 AA2 代理返回文本的转录；返修后 tables.md 行号有整体位移，文中的行号是审计时点的快照。文末「转录注」之外的内容逐字未改。

## 0. 范围、基线与过程边界

- 审计对象：`design/evidence/2026-11-13/refactor-endpoint/tables.md`（基线提交 `dddc179`）。本轮只审口径 D2/D3（表 A）、D4（表 B）、D6（表 D）、D7（表 E）；表 C/F/G 对应口径 D5/D8/D9，不在本次独立推导范围（见 3.5）。
- 基线核对：`git rev-parse --show-toplevel` 得仓库根，`git rev-parse HEAD` = `dddc17909250e41cd6a2f297a25acc3ab641617c`，`git status --short` 仅未跟踪的 `design/evidence/2026-11-13/`，工作树与基线一致。已按仓库规约执行 `git log --oneline -5`。
- 过程边界声明：**第二节（独立推导）在本审计中先完成，该阶段未打开 `design/evidence/2026-11-13/refactor-endpoint/` 下任何文件**；推导只读了口径原文引用的仓库源文件（`tools/code_shape/baseline.json`、`tools/code_shape/ui_layer_allow.json`、`ruff.toml`、`local/tests/test_layer_boundaries.py`、`local/ui/index.html`、`local/ui` 与 `local`/`server` 下的源码枚举，以及 `tools/code_shape/ui_refs.mjs`、`local/tests/fixtures/ui_harness.py` 的语义核对）。第三节才读 `tables.md` 比对。计算脚本与中间产物全部放在 `tempfile.mkdtemp()` 的临时目录，未写入仓库任何文件；本报告只输出文本与仓库相对路径。

## 一、口径原文引用（逐字）

> **D2**：文件归属哪一步，按下面的固定对照表，执行方不自己判断；一个文件可以属于多步，对不上的一律记「未排进任何一步」。
> 步骤 1A 组件与手机访问：local/ui/views/phone.js、local/ui/views/settings.js
> 步骤 1B 登录：local/ui/state/login.js、local/ui/views/login.js、local/ui/views/relogin.js、local/ui/views/status-cards.js
> 步骤 1C 计划栏：local/ui/views/plan-panel.js、local/ui/controllers/plan.js、local/ui/controllers/plan-events.js、local/ui/state/plan.js、local/ui/state/task-display.js
> 步骤 1 共用：local/ui/controllers/refresh.js、local/ui/app.js、local/ui/state/store.js
> 手机页：local/ui/m/ 下全部文件
> 步骤 2：local/app.py
> 步骤 3：local/grab.py
>
> **D3**：表 A 名单归属：把 tools/code_shape/baseline.json 的每一项（文件两档、函数两档、测试函数、类）、tools/code_shape/ui_layer_allow.json 的每一项、local/tests/test_layer_boundaries.py 里 LEGACY_DIRECTION_VIOLATIONS 的每一项、ruff.toml 里 per-file-ignores 的每一个「文件×规则码」，按 D2 标上归属；输出每一步各管几项，以及「未排进任何一步」的完整清单（带当前行数或规则码）。前端白名单的项按「引用方文件」归属，同时另列一栏「被引用名字的定义文件」的归属。
>
> **D4**：表 B 前端文件耦合：对 local/ui 下不含 m/ 的每个脚本，量行数、顶层函数数、定义的全局名字数、对状态仓库 S 的写入处数；再对每个「未排进任何一步」的脚本，量它引用了多少个定义在步骤 1 文件（1A、1B、1C、共用）里的名字、它定义的名字被步骤 1 文件引用了多少个，各给名字清单。
>
> **D6**：表 D 类型标注覆盖：用 ast 数 local 与 server 下每个 Python 文件里的函数（含方法，不含测试目录），分三类——参数与返回值都标了、标了一部分、完全没标；self 与 cls 不算参数；按 local/domain、local/application、local/infrastructure、local 根目录、server 五组汇总，再列每组里函数最多的十个文件。
>
> **D7**：表 E 界面测试断言分类：对 local/tests 下文件名以 test_ui_ 开头的测试文件和 test_phone_ui.py，用 ast 找出所有 assertIn、assertNotIn、assertRegex、assertNotRegex、assertEqual 调用里的字符串字面量参数，按固定规则分类，先命中先算：一、含 aria-、role=、alt=、title= 之一的算「无障碍名称」；二、去掉空白与标点后全是汉字、数字或全角符号的算「文案」；三、其余算「源码形状」。另数每个文件里经 node 沙箱执行脚本的测试函数个数。每个文件一行，三类各多少条；每一类随机抽 20 条（固定随机种子 20261113）原文列出，带 文件:行号。

## 二、独立推导（先于读表完成）

### 2.1 表 A（D3）应有的项数与归属

**数法。**
- baseline.json：`files.over800`/`files.over500` 每个 key 记 1 项（文件两档）；`functions.over100`/`functions.over60` 每个 key 记 1 项，文件部分取键中第一个 `::` 之前的部分（键形如 `路径::类.方法.嵌套名`，嵌套名带点不影响切分）；`test_functions`、`classes` 同法。档位重复键检查：0 对。
- ui_layer_allow.json：顶层组键只有 `state`、`views` 两层，每个「文件×名字」对记 1 项；按 `tools/code_shape/ui_refs.mjs` 语义核对，组键是**引用方**所在层（state/ 引用上层、views/ 引用 controllers/root），故归属按引用方文件；另对每个名字在 local/ui（不含 m/）的顶层声明里定位定义文件。
- LEGACY_DIRECTION_VIOLATIONS：`local/tests/test_layer_boundaries.py:210-215`，键为（文件、完整模块名）二元组，共 2 项，文件补 `local/` 前缀后按 D2 归属。
- ruff.toml：`[lint.per-file-ignores]`（`ruff.toml:23-64`）41 个文件条目，其中 3 个文件各 2 条规则码（test_phone_http.py=F401+F841、test_phone_service.py=F401+F841、test_session_persistence.py=F401+F823），按「文件×规则码」展开共 44 项。
- 归属**只按 D2 固定表**：表内 14 个 ui 文件、`local/ui/m/` 全部、`local/app.py`、`local/grab.py`，其余一律「未排进」。baseline 各项的 reason 文本（「步骤 2 组件」「步骤 3」等）不是 D2 对照表，不参与归属——例如 `local/infrastructure/component_packages.py`、`local/application/plan_service.py`、`local/application/update_service.py`、`local/infrastructure/phone_http.py`、`local/ui/views/update.js`、`local/ui/controllers/terms.js`、`local/ui/led.js`、`local/business_clock.py` 的 reason 虽写「步骤 N」，D2 表里没有这些文件，应记未排进。

**四源项数与总项数。**

| 来源 | 项数 |
|---|---|
| baseline.json（文件 25 = over800 12 + over500 13；函数 119 = over100 33 + over60 86；测试函数 19；类 4） | 167 |
| ui_layer_allow.json（state 21：clock 5、filters 2、login 8、plan 6；views 20：clock-pop 1、conflict-tip 1、help 1、list 2、log 1、phone 2、plan-panel 2、relogin 4、selection 1、settings 3、status-cards 1、tour 1） | 41 |
| LEGACY_DIRECTION_VIOLATIONS | 2 |
| ruff.toml per-file-ignores（文件×码） | 44 |
| **合计** | **254** |

**每步项数（推导）。**

| 归属 | 项数 | 构成 |
|---|---|---|
| 1A | 10 | baseline 5（phone.js 文件、paintPhoneAccess、paintOcrDownload、paintRelogin、wire）+ 白名单 5（views/phone.js×2、views/settings.js×3） |
| 1B | 16 | baseline 3（relogin.js 文件、paintLogin、receiveReloginState）+ 白名单 13（state/login.js×8、views/relogin.js×4、views/status-cards.js×1） |
| 1C | 18 | baseline 10（plan-panel.js、plan.js 文件、startPlan、paintLed、paintSelected、reconcileStart、startPlan.#anon1、paintBanners、paintRunPanel、updateControls）+ 白名单 8（state/plan.js×6、views/plan-panel.js×2） |
| 1共用 | 6 | baseline 6（app.js、refresh.js、store.js 文件、refresh、settleSynchronous、#anon52、boot）；白名单 0 |
| 手机页 | 9 | baseline 9（local/ui/m/app.js 文件、buildRow、ingest、wire、buildWhy、ingestRelogin、reloginView、renderBoard、renderItems） |
| 步骤 2 | 17 | baseline 16（app.py 文件、Api.__init__、Api._start_plan_inner、12 个 app.py over60 函数、Api 类）+ ruff 1（local/app.py×F401） |
| 步骤 3 | 13 | baseline 12（grab.py 文件、cmd_grab、cmd_grab._settle_direct_event、cmd_list、8 个 grab.py over60 函数）+ ruff 1（local/grab.py×F401） |
| 未排进 | 165 | baseline 106 + 白名单（按引用方）15 + legacy 2 + ruff 42 |
| **合计** | **254** | |

baseline 每步小计：1A 5、1B 3、1C 10、1共用 6、手机页 9、步骤 2 16、步骤 3 12、未排进 106（= 文件 16〔over800 7 + over500 9〕+ 函数 68〔over100 17 + over60 51〕+ 测试函数 19 + 类 3）。

**未排进 165 项完整清单（推导，带当前行数或规则码）。** 当前行数取磁盘行数（文件项）、py 函数取 ast 行跨度、JS 函数取记录值、ruff 项记规则码。

- baseline 文件 over800（7）：`local/business_clock.py`(875)、`local/infrastructure/component_packages.py`(1666)、`server/bot/bot.js`(977)、`server/deploy/auto_login.py`(824)、`server/deploy/grab_signup.py`(819)、`tools/qa_runtime_reliability.py`(3311)、`tools/release.py`(1321)
- baseline 文件 over500（9）：`local/application/advanced_component_service.py`(503)、`local/application/login_relay_service.py`(551)、`local/build/build_installer.py`(518)、`local/login_relay.py`(717)、`local/signup_plan.py`(614)、`local/ui/views/terms.js`(507)、`local/update_check.py`(548)、`server/scripts/activity_watch.py`(524)、`server/scripts/notify.py`(515)
- baseline 函数 over100（17）：`local/application/advanced_component_service.py::AdvancedComponentService._run_split_assets`(101)、`local/application/login_relay_service.py::LoginRelayService._handle_line`(103)、`local/application/plan_service.py::run_plan_task`(361)、`local/application/update_service.py::run_version_download`(151)、`local/infrastructure/phone_http.py::_make_handler`(261)、`local/signup_plan.py::validate_plan`(117)、`local/ui/controllers/terms.js::acceptTerms`(108)、`local/ui/led.js::#anon1`(108)、`local/ui/views/update.js::paintUpdate`(146)、`server/bot/bot.js::#anon12`(186)、`server/deploy/auto_login.py::main`(123)、`server/deploy/grab_signup.py::run_submit_loop`(343)、`server/scripts/fetch.py::main`(109)、`server/scripts/run.py::main`(144)、`tools/qa_runtime_reliability.py::_#22`(130)、`tools/release.py::stage_local_assets`(140)、`tools/release.py::verify_release_assets`(125)
- baseline 函数 over60（51）：`local/application/advanced_component_service.py::AdvancedComponentService._run`(92)、`local/application/auto_relogin.py::AutoReloginMonitor.tick`(90)、`local/application/login_relay_service.py::LoginRelayService.begin`(85)、`local/application/plan_service.py::run_plan_task.feed`(77)、`local/build/build_advanced.py::_build_legacy`(76)、`local/business_clock.py::BusinessClock._accept_cluster`(72)、`local/domain/demo_data.py::demo_items`(79)、`local/domain/phone_rules.py::normalize_action`(76)、`local/domain/plan_rules.py::classify_task_stop`(63)、`local/infrastructure/component_packages.py::_helper`(61)、`…::install`(72)、`…::install_artifact`(64)、`local/infrastructure/tray_icon.py::TrayIcon._run`(73)、`local/infrastructure/tunnel_manager.py::CloudflareTunnel.start`(84)、`local/runtime_paths.py::_migrate_legacy_data`(86)、`local/signup_plan.py::PlanCoordinator._run`(66)、`local/signup_signing.py::_encrypt_block_cng`(100)、`local/ui/controllers/terms.js::acceptTerms.#anon1`(64)、`local/ui/controllers/terms.js::recheckTerms`(63)、`local/ui/controllers/tick.js::tick`(88)、`local/ui/state/clock.js::ingestBusinessClock`(80)、`local/ui/views/clock-pop.js::renderClockPop`(76)、`local/ui/views/list.js::paintEmpty`(95)、`local/ui/views/list.js::rowHtml`(68)、`local/ui/views/terms.js::applyTermsFooter`(77)、`local/update_delta.py::apply_delta`(70)、`local/update_launcher.py::apply_staged`(76)、`local/updater.py::download_installer`(88)、`server/bot/bot.js::handleCardAction`(66)、`…::handleGrabAction`(63)、`…::handleMessage`(74)、`server/deploy/auto_login.py::_submit_once`(99)、`server/deploy/grab_signup.py::main`(66)、`server/deploy/server_refresh.js::runDaemon`(80)、`server/scripts/activity_watch.py::_run_once`(71)、`…::compute_events`(85)、`server/scripts/dev/explore.py::main`(63)、`server/scripts/query.py::main`(71)、`server/scripts/regress.py::main`(76)、`server/scripts/scan.py::_scan`(81)、`server/scripts/token_probe.py::main`(69)、`server/scripts/watchlist_runner.py::main`(76)、`tools/qa_business_clock_worker.py::run_probe`(99)、`tools/qa_runtime_reliability.py::_#20`(75)、`…::_#62`(69)、`…::_#63`(61)、`…::_#7`(81)、`…::_narrow`(75)、`…::run_scenarios`(75)、`tools/release.py::write_manifest`(75)、`tools/verify_autologin_loop.py::main`(87)
- baseline 测试函数（19）：test_lifecycle_release.py 1 项、test_phone_ui.py 5 项、test_retry_phone_integration.py 1 项、test_ui_contract_list.py 1 项、test_ui_contract_shell.py 2 项、test_ui_contract_terms.py 7 项、test_ui_contract_update.py 1 项、test_worker_boundaries.py 1 项（键名清单已逐项记录，均未排进）
- baseline 类（3）：`local/application/advanced_component_service.py::AdvancedComponentService`(8)、`local/application/auto_relogin.py::AutoReloginMonitor`(8)、`local/application/phone_service.py::PhoneAccessService`(12)
- 白名单按引用方未排进（15）：`local/ui/state/clock.js`×5、`local/ui/state/filters.js`×2、`local/ui/views/clock-pop.js`×1、`local/ui/views/conflict-tip.js`×1、`local/ui/views/help.js`×1、`local/ui/views/list.js`×2、`local/ui/views/log.js`×1、`local/ui/views/selection.js`×1、`local/ui/views/tour.js`×1
- legacy（2）：`local/application/advanced_component_service.py × import infrastructure.component_packages`、`local/infrastructure/component_packages.py × import runtime_paths`
- ruff（42）：除 `local/app.py×F401`（步骤 2）与 `local/grab.py×F401`（步骤 3）外的全部 42 个文件×码项（清单逐项记录：local 下 26 项、server 下 7 项、tools 下 3 项、另 test_phone_http/test_phone_service/test_session_persistence 各 2 码）

**白名单「被引用名字的定义文件」归属（推导）。** 41 个名字全部在 local/ui（不含 m/）顶层唯一定位到定义文件，无一名多文件、无未定位：按定义文件归属为 1B 4（setResult、paintLogin、reloginAutoLive→views；setBusy→views/login.js）、1C 6（updateControls、paintBoardActions、paintSelected→views/plan-panel.js；noteStartedFromPhone、doLogin→controllers/plan.js；showTaskResult→controllers/plan-events.js）、1共用 6（noteSignedTasks、scheduleSignedRefresh、refresh×3、runtimeErrorCopy→controllers/refresh.js）、未排进 25（其余：views/clock-pop.js、views/clock.js、views/list.js、controllers/clock.js、controllers/prefs.js、controllers/tick.js、controllers/bridge.js、controllers/terms.js 的定义）。

### 2.2 表 B（D4）应有的行数、列与数值

**脚本枚举。** 磁盘枚举 local/ui 下不含 m/ 的 `.js` 共 **40 个**（根 2：app.js、led.js；controllers 11；state 11；views 16），与 `local/ui/index.html` 的 40 个 `<script>` 标签一一对应（加载顺序已逐条记录）。步骤 1 文件 14 个（1A 2、1B 4、1C 5、共用 3），未排进 26 个。

**应有结构。** 表 B 主体 40 行（每脚本一行），列：行数、顶层函数数、定义的全局名字数、对状态仓库 S 的写入处数；另有未排进脚本交叉引用段 26 行，列：引用步骤 1 定义的名字数+清单、被步骤 1 引用的名字数+清单。

**我方度量（自写 JS 词法＋正则；已知口径/盲区：顶层函数含绑定到函数表达式的顶层绑定、全局名不含 window.X、S 写入只计 `S.x=`/`S[..]=` 一层、交叉引用按词界匹配不排除属性访问、正则字面量内容不剥离）。**

| 文件 | 行数 | 顶层函数 | 全局名 | S 写入 |
|---|---|---|---|---|
| local/ui/led.js | 118 | 0 | 0 | 0 |
| local/ui/app.js | 655 | 2 | 6 | 13 |
| local/ui/state/store.js | 199 | 3 | 12 | 0 |
| local/ui/state/terms.js | 19 | 2 | 2 | 0 |
| local/ui/state/rounds.js | 85 | 7 | 9 | 0 |
| local/ui/controllers/bridge.js | 35 | 3 | 3 | 0 |
| local/ui/controllers/refresh.js | 614 | 23 | 32 | 29 |
| local/ui/views/list.js | 449 | 18 | 18 | 5 |
| local/ui/state/task-display.js | 248 | 11 | 12 | 0 |
| local/ui/views/plan-panel.js | 1367 | 56 | 58 | 5 |
| local/ui/controllers/plan.js | 532 | 20 | 21 | 20 |
| local/ui/state/clock.js | 314 | 18 | 29 | 0 |
| local/ui/views/clock.js | 32 | 1 | 1 | 0 |
| local/ui/controllers/clock.js | 61 | 3 | 3 | 1 |
| local/ui/state/plan.js | 175 | 14 | 16 | 9 |
| local/ui/controllers/plan-events.js | 134 | 5 | 5 | 7 |
| local/ui/state/login.js | 141 | 9 | 9 | 3 |
| local/ui/views/login.js | 173 | 4 | 5 | 1 |
| local/ui/views/relogin.js | 555 | 34 | 43 | 4 |
| local/ui/views/clock-pop.js | 152 | 8 | 8 | 3 |
| local/ui/views/status-cards.js | 204 | 14 | 17 | 2 |
| local/ui/views/log.js | 29 | 2 | 2 | 1 |
| local/ui/views/terms.js | 507 | 35 | 37 | 0 |
| local/ui/controllers/terms.js | 477 | 17 | 18 | 4 |
| local/ui/views/update.js | 187 | 6 | 8 | 0 |
| local/ui/views/help.js | 67 | 6 | 6 | 0 |
| local/ui/views/settings.js | 397 | 19 | 21 | 2 |
| local/ui/views/phone.js | 1252 | 10 | 13 | 0 |
| local/ui/controllers/update.js | 148 | 8 | 8 | 0 |
| local/ui/controllers/prefs.js | 41 | 3 | 3 | 12 |
| local/ui/state/filters.js | 393 | 25 | 25 | 7 |
| local/ui/state/conflict.js | 176 | 17 | 19 | 0 |
| local/ui/views/selection.js | 90 | 6 | 8 | 2 |
| local/ui/views/conflict-tip.js | 147 | 11 | 11 | 3 |
| local/ui/controllers/cancel.js | 94 | 6 | 6 | 0 |
| local/ui/state/labels.js | 107 | 10 | 10 | 0 |
| local/ui/controllers/tick.js | 165 | 10 | 11 | 4 |
| local/ui/state/time.js | 154 | 12 | 15 | 0 |
| local/ui/views/tour.js | 174 | 13 | 13 | 0 |
| local/ui/controllers/window.js | 276 | 14 | 15 | 1 |

**未排进 26 脚本的交叉引用（推导，名字清单已逐项记录，此处录计数与关键清单）。** led.js 0/0；bridge.js 0/3〔api、hasBridge、waitForBridge〕；cancel.js 3〔S、addLog、refresh〕/3〔cancelAsk、cancelAskDismiss、cancelConfirm〕；controllers/clock.js 2〔S、msg〕/3〔pollClockNow、resyncClock、startClockPolling〕；prefs.js 2〔S、addLog〕/1〔savePrefs〕；controllers/terms.js 6〔S、addLog、msg、paintBanners、refresh、updateControls〕/11〔acceptTerms、declineTerms、ensureLicenseText、ingestTerms、markTermsUnknown、noteTermsRequired、openTerms、openTermsReader、recheckTerms、restoreTermsFocus、resumeTermsTour〕；tick.js 20〔$、RUNNING_STATUSES、S、SLEEP_GAP_MS、addLog、addLogFresh、msg、paintBanners、paintCountdown、paintEditNote、paintLed、paintLogin、paintRoute、paintRunPanel、paintSelected、runHeadKey、runtimeErrorCopy、taskDisplayDetail、taskDisplayLabel、taskModePrefix〕/7〔cleanReason、doCheck、grabHint、listErrorCopy、receiveSecondOpen、stripLabel、tick〕；controllers/update.js 2〔S、msg〕/7〔cancelDownload、checkUpdate、confirmDownload、launchInstaller、receiveUpdate、restoreUpdate、startDownload〕；window.js 3〔S、addLog、msg〕/1〔openWindowCloseDialog〕；state/clock.js 2〔S、updateControls〕/11〔TASK_RUNTIME_FIELDS、_monoMs、bnLeftSec、bnowS、businessNowMs、clockParts、clockPopOpenNow、clockReading、clockUiState、clockUncertaintyText、ingestBusinessClock〕；state/conflict.js 1〔S〕/1〔cancelBlock〕；state/filters.js 3〔S、setResult、verifiedSigned〕/13〔clearSelection、findItem、groupSelected、isEligibleForPlan、nextOpen、normalize、selectedItems、signStartPending、signedClash、sleepMissedNames、taskMissedBySleep、toggleSelection、validateSelection〕；state/labels.js 1〔verifiedSigned〕/8〔activityTimeText、leftOf、modeOf、modeText、signStartKnown、stateOf、taskClass、taskLabel〕；state/rounds.js 1〔S〕/7〔bumpRoundGeneration、cacheRoundPayload、firstNotice、loginPresent、markRoundApplied、newRoundId、takeRoundPayload〕；state/terms.js 1〔S〕/2〔termsAccepted、termsLocked〕；state/time.js 2〔$、WEEK〕/9〔durText、esc、fmt、hm、schoolParts、shortTime、startOfDay、toTs、whenText〕；views/clock-pop.js 3〔$、S、numOrNull〕/3〔applyClock、closeClockPop、toggleClockPop〕；views/clock.js 1〔$〕/1〔paintClockStatus〕；views/conflict-tip.js 2〔$、S〕/8〔placeTip、tipClose、tipGoSigned、tipKey、tipLater、tipOpen、tipSoon、tipStay〕；views/help.js 6〔$、DEFAULT_HELP、PhonePanel、S、addLog、refresh〕/5〔fillHelp、helpStatus、paintReplayButtons、replayTourFrom、showHelp〕；views/list.js 14〔$、S、executionView、paintBanners、paintBoardState、paintChecks、paintLed、paintPlan、paintRoute、paintSelected、planOutcome、taskDisplayLabel、unknownLabel、updateControls〕/3〔paintRail、refreshLoginEmptyState、render〕；views/log.js 3〔$、S、addLog〕/2〔copyLog、setLogOpen〕；views/selection.js 3〔$、S、setResult〕/4〔paintChips、setFilter、setFilterOpen、showPlanError〕；views/terms.js 3〔$、FIRST_USE_POINTS、S〕/7〔applyTermsFooter、closeTermsIntroBox、closeTermsUpdateBox、reopenTermsBox、switchTermsDoc、termsCloseIntent、termsUpdateMode〕；views/tour.js 4〔$、S、TOUR_STEPS、TOUR_VERSION〕/11〔maybeStartTour、paintTour、requestAutoTour、tourClose、tourGuardClick、tourPauseNow、tourResumeNow、tourShouldAutoStart、tourSkip、tourTrapTab、tourVisible〕；views/update.js 2〔$、S〕/0。

### 2.3 表 D（D6）应有的组、行结构与扫描范围

- 扫描范围：local 与 server 下全部非测试 `.py`，排除 `local/tests/`、`server/tests/` 与 `__pycache__`，共 **83 个文件**：local 根目录直接 `.py` 15 个（app、grab、business_clock、login_relay、runtime_paths、signup_plan、signup_signing、signup_transport、site_target、time_contract、update_check、update_delta、update_launcher、updater、advanced_helper）、local/domain 14、local/application 8、local/infrastructure 13、local/build 4（build_advanced、build_exe、build_installer、make_portable）、server 29（含 `server/deploy/legacy/` 2 个与 `server/scripts/dev/` 3 个）。
- **口径缺口提示**：D6 五组里没有 local/build 的去处；按「local 根目录=直接位于 local/ 下的 .py」的严格读法，这 4 个文件 45 个函数在五组内无归属，表必须显式处理（单列或并入），否则就是整块漏。
- 行结构：每组一行（文件数、函数数、三列分类数）＋ 每组「函数最多的十个文件」子表。
- 三类判定：函数=FunctionDef/AsyncFunctionDef（含方法与嵌套）；self/cls 不计参数；全标=全部参数与返回值均有注；全不标=无任何参数注且无返回注（零参无返回注计全不标）；其余为部分。

**推导数字。**

| 组 | 文件数 | 函数数 | 都标 | 部分 | 未标 |
|---|---|---|---|---|---|
| local/domain | 14 | 83 | 16 | 49 | 18 |
| local/application | 8 | 96 | 46 | 30 | 20 |
| local/infrastructure | 13 | 208 | 74 | 48 | 86 |
| local 根目录 | 15 | 614 | 325 | 87 | 202 |
| server | 29 | 261 | 87 | 28 | 146 |
| （口径五组未覆盖的 local/build） | 4 | 45 | 31 | 0 | 14 |

五组合计 1262；含 build 共 1307（都标 579、部分 242、未标 486）。各组 top-10（推导）：domain＝phone_rules 28、login_rules 11、retry_rules 7、retry_window 7、plan_rules 6、log_events 5、time_text 5、lifecycle_rules 4、cancel_rules 3、signup_reply 3；application＝phone_service 27、login_relay_service 22、advanced_component_service 20、auto_relogin 11、update_service 8、plan_service 6、login_service 2、__init__ 0；infrastructure＝component_packages 70、phone_http 31、single_instance 20、tunnel_manager 17、credential_store 13、lifecycle_store 12、process_tree 12、tray_icon 10、advanced_features 8、phone_session_store 8；local 根＝app.py 218、grab.py 161、business_clock 50、login_relay 38、signup_plan 26、update_check 24、update_delta 18、updater 18、update_launcher 17、time_contract 13；server＝deploy/grab_signup 41、deploy/auto_login 29、card 22、notify 20、activity_watch 19、common 16、fetch 14、watchlist 12、run 10、render 8；build＝build_advanced 14、make_portable 13、build_installer 12、build_exe 6。每文件的三列细分均已记录。

### 2.4 表 E（D7）应有的文件清单与列

- 文件 17 个：`local/tests/` 下 test_ui_conflict_cancel.py、test_ui_contract_clock.py、test_ui_contract_components.py、test_ui_contract_feedback.py、test_ui_contract_list.py、test_ui_contract_login.py、test_ui_contract_plan.py、test_ui_contract_settings.py、test_ui_contract_shell.py、test_ui_contract_terms.py、test_ui_contract_update.py、test_ui_layers.py、test_ui_main_window_list.py、test_ui_main_window_plan.py、test_ui_reliability.py、test_ui_rewards.py（16 个 test_ui_*，字典序）＋ test_phone_ui.py。
- 列：每文件 无障碍名称/文案/源码形状 三类计数，另加经 node 沙箱执行脚本的测试函数个数；外加三类各 20 条抽样（seed 20261113）带 文件:行号 与原文。
- 我方主口径：五种断言调用的**全部**字符串实参（位置＋关键字，每个 ast.Constant str 记 1 条）；备用口径（仅首实参）同时算出供比对。
- node 沙箱函数判定：`def test_*` 且函数子树内含对 `run_js`（`local/tests/fixtures/ui_harness.py:282`）的调用。

**推导数字（主口径）。**

| 文件 | 无障碍 | 文案 | 源码形状 | node 测试函数 |
|---|---|---|---|---|
| test_ui_conflict_cancel.py | 6 | 40 | 61 | 26 |
| test_ui_contract_clock.py | 0 | 42 | 21 | 11 |
| test_ui_contract_components.py | 2 | 18 | 32 | 0 |
| test_ui_contract_feedback.py | 0 | 28 | 32 | 11 |
| test_ui_contract_list.py | 7 | 120 | 119 | 22 |
| test_ui_contract_login.py | 0 | 93 | 79 | 18 |
| test_ui_contract_plan.py | 2 | 161 | 188 | 29 |
| test_ui_contract_settings.py | 2 | 149 | 139 | 19 |
| test_ui_contract_shell.py | 2 | 122 | 115 | 14 |
| test_ui_contract_terms.py | 2 | 172 | 184 | 37 |
| test_ui_contract_update.py | 3 | 28 | 29 | 29 |
| test_ui_layers.py | 0 | 0 | 0 | 0 |
| test_ui_main_window_list.py | 4 | 35 | 28 | 17 |
| test_ui_main_window_plan.py | 0 | 51 | 19 | 16 |
| test_ui_reliability.py | 0 | 166 | 131 | 84 |
| test_ui_rewards.py | 4 | 3 | 37 | 2 |
| test_phone_ui.py | 2 | 403 | 257 | 0 |
| **合计** | **36** | **1631** | **1471** | **335** |

三类总数 3138；备用口径（仅首实参）31/477/594＝1102。抽样：池按（文件字典序、行号、实参序）排列，`random.Random(20261113).sample` 每类取 20，样本清单已记录。

## 三、与 tables.md 比对（行号定位＋判定）

### 3.1 表 A（tables.md:9-510）→ 判定：一致

- **A1 汇总（:19-29）**：1A 10、1B 16、1C 18、1共用 6、步骤 2 17、步骤 3 13、手机页 9、未排进 165、合计 254，与推导八项逐一相等；自校行（:31）「89 + 165 = 254」算术成立（89=10+16+18+6+17+13+9）。**一致**。
- **A2 未排进完整清单（:33-202）**：逐项键集合与推导的 165 项集合经脚本比对**完全相等**：baseline 106 行（:37-142，含 over800 7、over500 9、over100 17、over60 51、测试函数 19、类 3）、白名单 15 行（:143-157）、legacy 2 行（:158-159）、ruff 42 行（:160-201）；当前行数列与推导一致（如 `local/business_clock.py` 875、`test_worker_boundaries.py` 4131、白名单行 314/393/152/141/175/1252/1367/555/397/204），ruff 行规则码齐备（F823、F541、F811 等都在）；尾注（:202）「未排进共 165 项」。**一致，无少算**。
- **A3 明细（:204-503）**：254 行（over800 12〔:210-221〕、over500 13〔:227-239〕、over100 33〔:245-277〕、over60 86〔:283-368〕、测试函数 19〔:374-392〕、类 4〔:398-401〕、白名单 41〔:407-447〕、legacy 2〔:453-454〕、ruff 44〔:460-503〕），逐项归属与推导一致。关键点验证：reason 写「步骤 N」但不在 D2 表内的项全部正确判为未排进（:213 component_packages.py、:247-250 plan_service/update_service/login_relay_service、:254 phone_http、:259-260 terms.js/led.js、:269 paintUpdate）；`local/app.py×F401`→步骤 2（:461）、`local/grab.py×F401`→步骤 3（:466）；白名单 41 行的「引用方归属＋定义文件归属」双栏与推导的 1B 4/1C 6/1共用 6/未排进 25 完全一致（:413/:416/:420/:426 为 1B、:411/:414/:418/:423/:427/:440 为 1C、:422/:425/:435-437/:441 为 1共用）。**一致**。
- **抽查记录（:506-510）**：第 1、3 条与源文件相符（baseline 键值、LEGACY 键位置 `local/tests/test_layer_boundaries.py:213` 均核对无误）。**第 2 条（:509）有两处行号引错**：写「`ruff.toml:31` 为 `"local/tests/test_updater.py" = ["F811"]`」，实际 ruff.toml:31 是 `local/infrastructure/credential_store.py × F841`，test_updater 在 ruff.toml:53；写「`ruff.toml:3` `"local/app.py" = ["F401"]`」，实际 ruff.toml:3 是注释行，app.py 条目在 ruff.toml:25。属抽查记录的引用笔误，不影响表 A 本体数字与归属。（返修注明：主代理已按 ruff.toml 原文改正为 :53 与 :25，并在转录稿当场标注。）

### 3.2 表 B（tables.md:512-605）→ 判定：一致

- **行数与集合（:520-561、:563）**：40 行脚本集合与推导 40 个完全相等（磁盘枚举=index.html 顺序 40 个，「另外发现 0 个」与推导一致）；归属列 14 个步骤 1 文件＋26 个未排进与推导一致。**一致**。
- **行数列**：40/40 与推导逐一相等（如 plan-panel.js 1367、app.js 655、filters.js 393、led.js 118）。**一致**。
- **顶层函数数/全局名字数**：80 个数值格中 75 个与推导相等；4 个文件的 5 格存在差异，逐一核实后**均为推导方法盲区或口径声明内差异，表值成立**：
  - phone.js 全局名 14 vs 推导 13（:548）：`local/ui/views/phone.js:1252` 有顶层 `window.PhonePanel = PhonePanel`，表在 :518 明示「全局名字数是顶层定义（function/const/let/var/class/window.X）个数」，计入 window.X 成立；
  - app.js 全局名 7 vs 推导 6（:561）：`local/ui/app.js:90` 顶层 `window.onBackend = {`，同上；
  - time.js 顶层函数 15、全局名 18 vs 推导 12、15（:558）：推导的自写词法把 `local/ui/state/time.js:24,128` 的正则字面量当串处理吞掉声明，实测 time.js:138/149 确有顶层 `function hmsDay`、`function fmtClock`，表值更准；
  - store.js 顶层函数 2 vs 推导 3（:523）：表在 :518 明示「顶层函数数只数 function 声明」，推导把顶层绑定到函数表达式的绑定也计入了，属推导口径更宽，表按其声明口径成立。
- **S 写入处数列**：推导（只计 `S.x=`/`S[..]=` 一层）与表在 18 个纯零写/单层写文件上一致，22 个文件表值更大（:525 rounds 8 vs 0、:527 refresh 73 vs 29、:544 terms 85 vs 4、:531 plan.js 54 vs 20 等）。抽查 `local/ui/state/rounds.js:17,19,20,36-37,47,64` 确有 `S.round.cache/.gen/.applied/.notified` 嵌套属性写与变异调用，表值口径（含嵌套写与变异）成立，且与表 C 全仓口径（:625「S 的写入处数 444 / 27 个文件」）自洽。**判为口径差异，非少算**。
- **B2 交叉引用（:566-599）**：26 行与推导 26 个未排进脚本一致（尾注 :599）；23 行的名字清单与计数逐名相等；3 格差异核实后**表值正确**：help.js 引用数 5 vs 推导 6（:585）——推导把 `local/ui/views/help.js:14` 的 `PhonePanel.refresh()` 属性访问误计为引用全局 `refresh`，表在 :568 明示「排除属性访问」，表对；time.js 引用数 1 vs 推导 2（:595）——推导的 `$` 来自 time.js:24 正则字面量内容，非引用，表对；time.js 被引用数 11 vs 推导 9（:595）——`fmtClock`/`hmsDay` 定义于 time.js:138/149 且被 `local/ui/state/task-display.js:100-101,199` 引用，表对（推导词法漏扫）。**一致**。

### 3.3 表 D（tables.md:643-728）→ 判定：一致

- **D1 分组汇总（:653-661）**：七行（五组＋local/build 单列＋「local 其他子目录 0」）与推导完全相等（14/83、8/96、13/208、15/614、29/261、4/45、0/0，三类细分同）；local/build 单列的处理正好补上 D6 五组未覆盖的 4 文件 45 函数，**未造成整块漏**；「local 其他子目录 0」与推导枚举一致（local/ 下除 domain/application/infrastructure/build 与根目录外无其他 .py）。
- **合计（:720）**：1307 = 579+242+486 = 83+96+208+614+261+45，算术成立且与推导全等。
- **top-10（:665-718）**：五组各 10 行＋build 4 行共 44 行，文件、函数数、三列细分与推导逐行相等。**一致**。
- **扫描范围（:649、抽查 :727）**：不含测试目录、local 根 15 个 .py（无 `_site_build.py`）与推导一致。**一致**。

### 3.4 表 E（tables.md:730-835）→ 判定：结构与覆盖一致；**类别错并 27 条**（文案/源码形状 边界）；1 例行号口径差

- **文件清单与列（:740-759）**：17 个文件齐全、四列＋node 列齐全、合计行（:759）算术成立（36+1658+1444=3138）、自校行（:761）成立。**一致**。
- **总量与覆盖**：三类总 3138 与推导主口径（全部字符串实参）完全相等 → 五种断言调用的字符串实参**无漏采、无少算**；无障碍名称 36 及每文件分布与推导逐文件相等（17/17 文件相同）→ 规则一执行一致。
- **node 沙箱测试函数数**：17 个文件逐文件相等（26/11/0/11/22/18/29/19/14/37/29/0/17/16/84/2/0，合计 335）。**一致**。
- **类别错并（27 条）**：表 文案 1658/源码形状 1444 vs 推导严格口径 1631/1471，差 27 条且**全部单向**（表把 27 条归入文案，按口径严格读法应为源码形状）。涉及行：:742（conflict_cancel 文案 41 vs 40）、:748（plan 163 vs 161）、:749（settings 157 vs 149）、:750（shell 123 vs 122）、:751（terms 175 vs 172）、:755（main_window_plan 54 vs 51）、:757（rewards 9 vs 3）、:758（phone_ui 406 vs 403）。已逐条定位全部 27 个字符串，共同特征是**去空白与标点后仍含符号字符（×、→、≤、=、+、<、>、| 等数学/箭头/比较符号，非标点、非汉字、非数字、非全角符号）**：
  1. `local/tests/test_ui_conflict_cancel.py:299`「放得下：行下沿 + 8」
  2. `local/tests/test_ui_contract_plan.py:289`「次数输入必须能表达 0=不限」
  3. `local/tests/test_ui_contract_plan.py:661`「开放后不得倒退回启动点 + 时长」
  4. `local/tests/test_ui_contract_settings.py:56`「五步顺序固定：时刻表 → 勾选 → 核对 → 开始以后 → 顶部状态」
  5. `local/tests/test_ui_contract_settings.py:141`「窄窗（≤980）必须退回底部说明条」
  6. `local/tests/test_ui_contract_settings.py:481`「「设置 → 登录」缺保存账号卡片」
  7. `local/tests/test_ui_contract_settings.py:936`「帮助弹窗不得有 × 关闭按钮」
  8. `local/tests/test_ui_contract_settings.py:943`「重新登录弹窗不得有 × 关闭按钮」
  9. `local/tests/test_ui_contract_settings.py:951`「首次说明框不得有 × 关闭按钮」
  10. `local/tests/test_ui_contract_settings.py:952`「条款更新框不得有 × 关闭按钮」
  11. `local/tests/test_ui_contract_settings.py:956`「设置抽屉（阅读型面板）必须保留 × 关闭按钮」
  12. `local/tests/test_ui_contract_shell.py:444`「含 100 秒整（与后端 <= 一致）」
  13. `local/tests/test_ui_contract_terms.py:386`「× 不再等于拒绝」
  14. `local/tests/test_ui_contract_terms.py:1072`「从说明框打开的全文 ×＝回小框」
  15. `local/tests/test_ui_contract_terms.py:1076`「未知态直开的全文 × 只等于关闭」
  16. `local/tests/test_ui_main_window_plan.py:262`「1已报名|1名额已满|1报名未成功|2错过了|」
  17. `local/tests/test_ui_main_window_plan.py:478`「最多提交次数（0 = 不限）」
  18. `local/tests/test_ui_main_window_plan.py:479`「最多提交次数（0=不限）」
  19. `local/tests/test_ui_rewards.py:64`「>0.5 分 · 工资 5<」
  20. `local/tests/test_ui_rewards.py:69`「>0 分 · 工资 0<」
  21. `local/tests/test_ui_rewards.py:70`「>1 分 · 工资 0<」
  22. `local/tests/test_ui_rewards.py:74`「>分未公布 · 工资 20<」
  23. `local/tests/test_ui_rewards.py:76`「>3 分 · 工资未公布<」
  24. `local/tests/test_ui_rewards.py:78`「>分未公布 · 工资未公布<」
  25. `local/tests/test_phone_ui.py:4242`「已报名/已截止组照原型渲染进主列表（组条+行连排）」
  26. `local/tests/test_phone_ui.py:4755`「顺序必须是 状态→今天→即将开放→已报名→书签→更多」
  27. `local/tests/test_phone_ui.py:4775`「配对码在电脑的“设置 → 手机访问”里，5 分钟内有效，只能用一次。」
  按 D7 口径「去掉空白与标点后**全是**汉字、数字或全角符号的算文案」的严格读法，这 27 条应落「源码形状」；表把符号字符也按可去除处理（等价于把 Unicode 符号类并入「标点」），超出口径字面。**判：类别错并**——不改变三类总量（3138）、无障碍名称（36）与 node 数（335），但上述 8 个文件的 文案/源码形状 两列各偏 1-8 条。
  （返修注明：主代理按此口径返修脚本——「全角符号」按字面放行 FF 段符号（＝、＋），半角符号不放行——重出的表 E 为 36/1631/1471，与推导逐文件一致；上列 27 条全部转入「源码形状」。）
- **E2 抽样（:763-826）**：抽样池排序键与推导不同（表在 :763 声明「按 文件:行号+字面量 排序后抽样」，推导按文件序+行号），60 条样本无法逐条对位，属抽样口径差异而非错误；对表 60 条样本逐条按口径规则复核分类，无一与严格口径矛盾（27 条边界串均未进样本）；行号口径 1 例：:771 记 `test_phone_ui.py:3258`，推导取字符串字面量所在行为 3259（多行调用时取调用行 vs 字面量行），单例差异。
- **抽查记录（:830-835）**：第 1-3 条样本复核事实与源码相符；第 4 条 grep 量级核对自洽。

### 3.5 范围外的表

表 C（:607-641，D5）、表 F（:837-955，D8）、表 G（:957-980，D9）对应的口径不在本次推导范围，本轮不对其数字做独立推导；仅记录两点关联事实：表 B 的 S 写入口径与表 C 的全仓「444 处/27 文件」（:625）同源自洽；表 A 的基线提交声明（:3）与实测 HEAD 一致。

## 四、汇总

| 判定类别 | 数量 | 明细 |
|---|---|---|
| 整块漏 | 0 | 表 A 的 A1/A2/A3、表 B 的 B1/B2、表 D 的 D1/D2、表 E 的 E1/E2 全部存在；A2 未排进 165 项、B2 未排进 26 脚本、D top-10 44 行、E 17 文件齐全；D6 五组未覆盖的 local/build 45 个函数被表 D 显式单列，未漏 |
| 少算 | 0 | 全部总量与推导吻合：名单 254/未排进 165；脚本 40/未排进 26；函数 1307（579/242/486）；断言字面量 3138（36/1658/1444）与 node 335 |
| 类别错并 | 1 | 表 E 文案/源码形状 边界 27 条（3.4 节全清单；tables.md:742、748、749、750、751、755、757、758 八行受影响；总量、无障碍数、node 数不变） |
| 其他事实错误（三类之外，如实记录） | 1 | tables.md:509 表 A 抽查记录引错 ruff.toml 行号两处（:31 应为 :53、:3 应为 :25） |
| 口径差异（核实后表值成立，非错误） | 2 组 | 表 B 的 S 写入列含嵌套写与变异（:518/:525/:527 等，与 :625 全仓口径自洽）；表 B 全局名列含 window.X（:548/:561）；另有表 B 顶层函数列「只数 function 声明」（:523）与 E2 抽样排序键（:763）、行号取法 1 例（:771） |

其余全部核对项判定为**一致**：表 A（汇总、165 项未排进清单、254 行明细及全部归属）、表 B（40 行集合与行数列、B2 23/26 行逐名相等＋3 格经代码核实表值正确）、表 D（七行汇总、1307 及三类分解、44 行 top-10）、表 E（文件清单、覆盖总量、无障碍 36 逐文件、node 335 逐文件）。

转录注：正文「返修注明」三处与文首「落盘说明」为主代理加的返修标注，其余逐字转录。
