# tables.md——离线七张表（表 A 到表 G）

- 基线提交：`dddc179`（T0 时 `git rev-parse --short HEAD` 的值，原文见 README「基线与开工核对」）。
- 所有命令从仓库根执行；Python 一律 `python -B`，node 不带 -B。
- 时间口径见 README「时间口径」，本文件不另写时间戳。
- 表 A、表 B、表 D、表 E、表 F、表 G 的正文是对应脚本的标准输出原样（含脚本自带的「量什么」、自校行与复跑命令）；表 C 是五个旧脚本重跑后的对照，由派发代理转录、主代理落盘。
- 每张表后的「抽查记录」是派发代理做的行级核对事实，主代理逐字转录；转录中发现的笔误改正处均已当场标注。
- 同一事实在多张表出现时的对照关系：表 B 的「S 写入处数」列与表 C 的「S 的写入处数 / 写入文件数」同源同口径（B1 列可求和对照）；全局名字唯一名计数（表 C 的 562，来自 globals.mjs）与逐文件定义合计（表 B B1 列求和 563）之差是同一文件内同名顶层定义 1 处，表 B 尾注已写明；Api 方法总数 153 见表 C 与表 G 实测；local/grab.py 4076 行、local/app.py 4873 行见表 A「当前值」列与表 G 实测；本机测试数 2581 见表 G 实测与 online.md H3 的「Ran 2581 tests」。

**表 A：四份名单的每项归属（D2、D3）**

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ownership.py`

## 表 A：四份名单的每项归属（按计划 D2 对照表）

量什么：baseline.json 的四份名单（文件两档、函数两档、测试函数、类）、ui_layer_allow.json 的每一项、LEGACY_DIRECTION_VIOLATIONS 的每一项、ruff.toml per-file-ignores 的每个「文件×规则码」，按 D2 的固定对照表标归属；对照表没有的文件记「未排进任何一步」。

### A1 归属汇总与自校

| 归属 | 项数 |
|---|---|
| 步骤 1A 组件与手机访问 | 10 |
| 步骤 1B 登录 | 16 |
| 步骤 1C 计划栏 | 18 |
| 步骤 1 共用 | 6 |
| 步骤 2 | 17 |
| 步骤 3 | 13 |
| 手机页 | 9 |
| 未排进任何一步 | 165 |
| 合计 | 254 |

表 A 自校：各步项数 89 + 未排进项数 165 = 四份名单总项数 254 -> 成立

### A2 未排进任何一步的完整清单

| 来源 | 条目 | 当前行数 | 规则码 |
|---|---|---|---|
| baseline 文件名单（over800） | `local/business_clock.py` | 875 | — |
| baseline 文件名单（over800） | `local/infrastructure/component_packages.py` | 1666 | — |
| baseline 文件名单（over800） | `server/bot/bot.js` | 977 | — |
| baseline 文件名单（over800） | `server/deploy/auto_login.py` | 824 | — |
| baseline 文件名单（over800） | `server/deploy/grab_signup.py` | 819 | — |
| baseline 文件名单（over800） | `tools/qa_runtime_reliability.py` | 3311 | — |
| baseline 文件名单（over800） | `tools/release.py` | 1321 | — |
| baseline 文件名单（over500） | `local/application/advanced_component_service.py` | 503 | — |
| baseline 文件名单（over500） | `local/application/login_relay_service.py` | 551 | — |
| baseline 文件名单（over500） | `local/build/build_installer.py` | 518 | — |
| baseline 文件名单（over500） | `local/login_relay.py` | 717 | — |
| baseline 文件名单（over500） | `local/signup_plan.py` | 614 | — |
| baseline 文件名单（over500） | `local/ui/views/terms.js` | 507 | — |
| baseline 文件名单（over500） | `local/update_check.py` | 548 | — |
| baseline 文件名单（over500） | `server/scripts/activity_watch.py` | 524 | — |
| baseline 文件名单（over500） | `server/scripts/notify.py` | 515 | — |
| baseline 函数名单（over100） | `local/application/advanced_component_service.py::AdvancedComponentService._run_split_assets` | 101 | — |
| baseline 函数名单（over100） | `local/application/login_relay_service.py::LoginRelayService._handle_line` | 103 | — |
| baseline 函数名单（over100） | `local/application/plan_service.py::run_plan_task` | 361 | — |
| baseline 函数名单（over100） | `local/application/update_service.py::run_version_download` | 151 | — |
| baseline 函数名单（over100） | `local/infrastructure/phone_http.py::_make_handler` | 261 | — |
| baseline 函数名单（over100） | `local/signup_plan.py::validate_plan` | 117 | — |
| baseline 函数名单（over100） | `local/ui/controllers/terms.js::acceptTerms` | 108 | — |
| baseline 函数名单（over100） | `local/ui/led.js::#anon1` | 108 | — |
| baseline 函数名单（over100） | `local/ui/views/update.js::paintUpdate` | 146 | — |
| baseline 函数名单（over100） | `server/bot/bot.js::#anon12` | 186 | — |
| baseline 函数名单（over100） | `server/deploy/auto_login.py::main` | 123 | — |
| baseline 函数名单（over100） | `server/deploy/grab_signup.py::run_submit_loop` | 343 | — |
| baseline 函数名单（over100） | `server/scripts/fetch.py::main` | 109 | — |
| baseline 函数名单（over100） | `server/scripts/run.py::main` | 144 | — |
| baseline 函数名单（over100） | `tools/qa_runtime_reliability.py::_#22` | 130 | — |
| baseline 函数名单（over100） | `tools/release.py::stage_local_assets` | 140 | — |
| baseline 函数名单（over100） | `tools/release.py::verify_release_assets` | 125 | — |
| baseline 函数名单（over60） | `local/application/advanced_component_service.py::AdvancedComponentService._run` | 92 | — |
| baseline 函数名单（over60） | `local/application/auto_relogin.py::AutoReloginMonitor.tick` | 90 | — |
| baseline 函数名单（over60） | `local/application/login_relay_service.py::LoginRelayService.begin` | 85 | — |
| baseline 函数名单（over60） | `local/application/plan_service.py::run_plan_task.feed` | 77 | — |
| baseline 函数名单（over60） | `local/build/build_advanced.py::_build_legacy` | 76 | — |
| baseline 函数名单（over60） | `local/business_clock.py::BusinessClock._accept_cluster` | 72 | — |
| baseline 函数名单（over60） | `local/domain/demo_data.py::demo_items` | 79 | — |
| baseline 函数名单（over60） | `local/domain/phone_rules.py::normalize_action` | 76 | — |
| baseline 函数名单（over60） | `local/domain/plan_rules.py::classify_task_stop` | 63 | — |
| baseline 函数名单（over60） | `local/infrastructure/component_packages.py::_helper` | 61 | — |
| baseline 函数名单（over60） | `local/infrastructure/component_packages.py::install` | 72 | — |
| baseline 函数名单（over60） | `local/infrastructure/component_packages.py::install_artifact` | 64 | — |
| baseline 函数名单（over60） | `local/infrastructure/tray_icon.py::TrayIcon._run` | 73 | — |
| baseline 函数名单（over60） | `local/infrastructure/tunnel_manager.py::CloudflareTunnel.start` | 84 | — |
| baseline 函数名单（over60） | `local/runtime_paths.py::_migrate_legacy_data` | 86 | — |
| baseline 函数名单（over60） | `local/signup_plan.py::PlanCoordinator._run` | 66 | — |
| baseline 函数名单（over60） | `local/signup_signing.py::_encrypt_block_cng` | 100 | — |
| baseline 函数名单（over60） | `local/ui/controllers/terms.js::acceptTerms.#anon1` | 64 | — |
| baseline 函数名单（over60） | `local/ui/controllers/terms.js::recheckTerms` | 63 | — |
| baseline 函数名单（over60） | `local/ui/controllers/tick.js::tick` | 88 | — |
| baseline 函数名单（over60） | `local/ui/state/clock.js::ingestBusinessClock` | 80 | — |
| baseline 函数名单（over60） | `local/ui/views/clock-pop.js::renderClockPop` | 76 | — |
| baseline 函数名单（over60） | `local/ui/views/list.js::paintEmpty` | 95 | — |
| baseline 函数名单（over60） | `local/ui/views/list.js::rowHtml` | 68 | — |
| baseline 函数名单（over60） | `local/ui/views/terms.js::applyTermsFooter` | 77 | — |
| baseline 函数名单（over60） | `local/update_delta.py::apply_delta` | 70 | — |
| baseline 函数名单（over60） | `local/update_launcher.py::apply_staged` | 76 | — |
| baseline 函数名单（over60） | `local/updater.py::download_installer` | 88 | — |
| baseline 函数名单（over60） | `server/bot/bot.js::handleCardAction` | 66 | — |
| baseline 函数名单（over60） | `server/bot/bot.js::handleGrabAction` | 63 | — |
| baseline 函数名单（over60） | `server/bot/bot.js::handleMessage` | 74 | — |
| baseline 函数名单（over60） | `server/deploy/auto_login.py::_submit_once` | 99 | — |
| baseline 函数名单（over60） | `server/deploy/grab_signup.py::main` | 66 | — |
| baseline 函数名单（over60） | `server/deploy/server_refresh.js::runDaemon` | 80 | — |
| baseline 函数名单（over60） | `server/scripts/activity_watch.py::_run_once` | 71 | — |
| baseline 函数名单（over60） | `server/scripts/activity_watch.py::compute_events` | 85 | — |
| baseline 函数名单（over60） | `server/scripts/dev/explore.py::main` | 63 | — |
| baseline 函数名单（over60） | `server/scripts/query.py::main` | 71 | — |
| baseline 函数名单（over60） | `server/scripts/regress.py::main` | 76 | — |
| baseline 函数名单（over60） | `server/scripts/scan.py::_scan` | 81 | — |
| baseline 函数名单（over60） | `server/scripts/token_probe.py::main` | 69 | — |
| baseline 函数名单（over60） | `server/scripts/watchlist_runner.py::main` | 76 | — |
| baseline 函数名单（over60） | `tools/qa_business_clock_worker.py::run_probe` | 99 | — |
| baseline 函数名单（over60） | `tools/qa_runtime_reliability.py::_#20` | 75 | — |
| baseline 函数名单（over60） | `tools/qa_runtime_reliability.py::_#62` | 69 | — |
| baseline 函数名单（over60） | `tools/qa_runtime_reliability.py::_#63` | 61 | — |
| baseline 函数名单（over60） | `tools/qa_runtime_reliability.py::_#7` | 81 | — |
| baseline 函数名单（over60） | `tools/qa_runtime_reliability.py::_narrow` | 75 | — |
| baseline 函数名单（over60） | `tools/qa_runtime_reliability.py::run_scenarios` | 75 | — |
| baseline 函数名单（over60） | `tools/release.py::write_manifest` | 75 | — |
| baseline 函数名单（over60） | `tools/verify_autologin_loop.py::main` | 87 | — |
| baseline 测试函数名单 | `local/tests/test_lifecycle_release.py::AssetVerificationTests.test_verify_rejects_each_bad_candidate` | 92 | — |
| baseline 测试函数名单 | `local/tests/test_phone_ui.py::ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` | 71 | — |
| baseline 测试函数名单 | `local/tests/test_phone_ui.py::ResultTermsModelTests.test_result_view_counts_and_heads_follow_prototype` | 84 | — |
| baseline 测试函数名单 | `local/tests/test_phone_ui.py::RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` | 65 | — |
| baseline 测试函数名单 | `local/tests/test_phone_ui.py::RunWaitModelTests.test_task_card_follows_prototype_detail_priority` | 72 | — |
| baseline 测试函数名单 | `local/tests/test_phone_ui.py::WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` | 67 | — |
| baseline 测试函数名单 | `local/tests/test_retry_phone_integration.py::FullChainTests.test_pair_read_start_extend_stop_relogin_chain` | 66 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_list.py::TimetableGroupingBehaviorTests.test_group_timetable_places_each_activity_in_its_correct_group` | 106 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_shell.py::WorkbenchUiContractTests.test_close_dialog_three_exits` | 138 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_shell.py::WorkbenchUiContractTests.test_five_pre_start_warnings_only_remind` | 61 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_terms.py::TermsConsentBehaviorTests.test_decline_does_not_reprompt_and_keeps_help_available` | 62 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_terms.py::TermsConsentBehaviorTests.test_unknown_terms_accept_rejects_bad_receipts` | 68 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_terms.py::TermsConsentContractTests.test_accept_terms_writes_prefs_transaction_only` | 77 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_terms.py::TermsConsentContractTests.test_terms_dialog_structure_contract` | 127 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_boot_defers_intro_until_terms_accepted` | 69 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_close_restores_banner_focus_without_stacking_dialogs` | 62 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_save_timeout_keeps_gate_reopens_close_and_drops_late_receipt` | 64 | — |
| baseline 测试函数名单 | `local/tests/test_ui_contract_update.py::UpdateBoardPaintTests.test_one_primary_action_per_state` | 75 | — |
| baseline 测试函数名单 | `local/tests/test_worker_boundaries.py::ListEntryTests.test_cmd_list_without_clock_keeps_full_enrich` | 63 | — |
| baseline 类名单 | `local/application/advanced_component_service.py::AdvancedComponentService` | 8 | — |
| baseline 类名单 | `local/application/auto_relogin.py::AutoReloginMonitor` | 8 | — |
| baseline 类名单 | `local/application/phone_service.py::PhoneAccessService` | 12 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/state/clock.js × paintClockPopFeedback` | 314 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/state/clock.js × paintClockStatus` | 314 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/state/clock.js × render` | 314 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/state/clock.js × renderClockPop` | 314 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/state/clock.js × updateControls` | 314 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/state/filters.js × render` | 393 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/state/filters.js × setResult` | 393 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/clock-pop.js × resyncClock` | 152 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/conflict-tip.js × savePrefs` | 147 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/help.js × savePrefs` | 67 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/list.js × listErrorCopy` | 449 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/list.js × tick` | 449 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/log.js × savePrefs` | 29 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/selection.js × savePrefs` | 90 | — |
| 前端分层白名单 ui_layer_allow.json | `local/ui/views/tour.js × savePrefsNow` | 174 | — |
| 分层测试存量例外 LEGACY_DIRECTION_VIOLATIONS | `local/application/advanced_component_service.py import infrastructure.component_packages` | 503 | — |
| 分层测试存量例外 LEGACY_DIRECTION_VIOLATIONS | `local/infrastructure/component_packages.py import runtime_paths` | 1666 | — |
| ruff.toml per-file-ignores | `local/advanced_helper.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/application/advanced_component_service.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/application/login_relay_service.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/application/phone_service.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/build/build_installer.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/infrastructure/credential_store.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `local/infrastructure/lifecycle_store.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `local/signup_plan.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_advanced_features.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_auto_relogin.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_business_clock.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_business_clock_wiring.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_cancel_signup.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_lifecycle_release.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `local/tests/test_login_relay.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_login_relay_service.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_network_policy.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_phone_http.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_phone_http.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `local/tests/test_phone_service.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_phone_service.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `local/tests/test_release_audit.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_retry_phone_policy.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_retry_policy.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `local/tests/test_session_persistence.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_session_persistence.py × F823` | F823 | F823 |
| ruff.toml per-file-ignores | `local/tests/test_signup_plan.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `local/tests/test_time_contract.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_ui_contract_settings.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_ui_contract_shell.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `local/tests/test_updater.py × F811` | F811 | F811 |
| ruff.toml per-file-ignores | `local/tests/test_worker_boundaries.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `server/deploy/auto_login.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `server/deploy/grab_signup.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `server/scripts/common.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `server/scripts/dev/explore.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `server/scripts/fetch.py × F541` | F541 | F541 |
| ruff.toml per-file-ignores | `server/scripts/token_probe.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `server/scripts/token_report.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `tools/qa_business_clock_worker.py × F401` | F401 | F401 |
| ruff.toml per-file-ignores | `tools/qa_runtime_reliability.py × F841` | F841 | F841 |
| ruff.toml per-file-ignores | `tools/split_branches.py × F401` | F401 | F401 |
未排进共 165 项。

### A3 明细

#### baseline 文件名单（over800）

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/app.py` | 4873 | 4873 | 步骤 2 |
| `local/business_clock.py` | 875 | 875 | 未排进任何一步 |
| `local/grab.py` | 4076 | 4076 | 步骤 3 |
| `local/infrastructure/component_packages.py` | 1666 | 1666 | 未排进任何一步 |
| `local/ui/m/app.js` | 3365 | 3365 | 手机页 |
| `local/ui/views/phone.js` | 1252 | 1252 | 步骤 1A 组件与手机访问 |
| `local/ui/views/plan-panel.js` | 1367 | 1367 | 步骤 1C 计划栏 |
| `server/bot/bot.js` | 977 | 977 | 未排进任何一步 |
| `server/deploy/auto_login.py` | 824 | 824 | 未排进任何一步 |
| `server/deploy/grab_signup.py` | 819 | 819 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py` | 3311 | 3311 | 未排进任何一步 |
| `tools/release.py` | 1321 | 1321 | 未排进任何一步 |

#### baseline 文件名单（over500）

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/application/advanced_component_service.py` | 503 | 503 | 未排进任何一步 |
| `local/application/login_relay_service.py` | 551 | 551 | 未排进任何一步 |
| `local/build/build_installer.py` | 518 | 518 | 未排进任何一步 |
| `local/login_relay.py` | 717 | 717 | 未排进任何一步 |
| `local/signup_plan.py` | 614 | 614 | 未排进任何一步 |
| `local/ui/app.js` | 655 | 655 | 步骤 1 共用 |
| `local/ui/controllers/plan.js` | 532 | 532 | 步骤 1C 计划栏 |
| `local/ui/controllers/refresh.js` | 614 | 614 | 步骤 1 共用 |
| `local/ui/views/relogin.js` | 555 | 555 | 步骤 1B 登录 |
| `local/ui/views/terms.js` | 507 | 507 | 未排进任何一步 |
| `local/update_check.py` | 548 | 548 | 未排进任何一步 |
| `server/scripts/activity_watch.py` | 524 | 524 | 未排进任何一步 |
| `server/scripts/notify.py` | 515 | 515 | 未排进任何一步 |

#### baseline 函数名单（over100）

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/app.py::Api.__init__` | 167 | 167 | 步骤 2 |
| `local/app.py::Api._start_plan_inner` | 239 | 239 | 步骤 2 |
| `local/application/advanced_component_service.py::AdvancedComponentService._run_split_assets` | 101 | 101 | 未排进任何一步 |
| `local/application/login_relay_service.py::LoginRelayService._handle_line` | 103 | 103 | 未排进任何一步 |
| `local/application/plan_service.py::run_plan_task` | 361 | 361 | 未排进任何一步 |
| `local/application/update_service.py::run_version_download` | 151 | 151 | 未排进任何一步 |
| `local/grab.py::cmd_grab` | 1467 | 1467 | 步骤 3 |
| `local/grab.py::cmd_grab._settle_direct_event` | 114 | 114 | 步骤 3 |
| `local/grab.py::cmd_list` | 143 | 143 | 步骤 3 |
| `local/infrastructure/phone_http.py::_make_handler` | 261 | 261 | 未排进任何一步 |
| `local/signup_plan.py::validate_plan` | 117 | 117 | 未排进任何一步 |
| `local/ui/controllers/plan.js::startPlan` | 117 | 117 | 步骤 1C 计划栏 |
| `local/ui/controllers/refresh.js::refresh` | 123 | 123 | 步骤 1 共用 |
| `local/ui/controllers/refresh.js::settleSynchronous` | 108 | 108 | 步骤 1 共用 |
| `local/ui/controllers/terms.js::acceptTerms` | 108 | 108 | 未排进任何一步 |
| `local/ui/led.js::#anon1` | 108 | 108 | 未排进任何一步 |
| `local/ui/m/app.js::buildRow` | 102 | 102 | 手机页 |
| `local/ui/m/app.js::ingest` | 101 | 101 | 手机页 |
| `local/ui/m/app.js::wire` | 163 | 163 | 手机页 |
| `local/ui/views/login.js::paintLogin` | 103 | 103 | 步骤 1B 登录 |
| `local/ui/views/phone.js::paintPhoneAccess` | 262 | 262 | 步骤 1A 组件与手机访问 |
| `local/ui/views/plan-panel.js::paintLed` | 116 | 116 | 步骤 1C 计划栏 |
| `local/ui/views/plan-panel.js::paintSelected` | 124 | 124 | 步骤 1C 计划栏 |
| `local/ui/views/settings.js::paintOcrDownload` | 119 | 119 | 步骤 1A 组件与手机访问 |
| `local/ui/views/update.js::paintUpdate` | 146 | 146 | 未排进任何一步 |
| `server/bot/bot.js::#anon12` | 186 | 186 | 未排进任何一步 |
| `server/deploy/auto_login.py::main` | 123 | 123 | 未排进任何一步 |
| `server/deploy/grab_signup.py::run_submit_loop` | 343 | 343 | 未排进任何一步 |
| `server/scripts/fetch.py::main` | 109 | 109 | 未排进任何一步 |
| `server/scripts/run.py::main` | 144 | 144 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py::_#22` | 130 | 130 | 未排进任何一步 |
| `tools/release.py::stage_local_assets` | 140 | 140 | 未排进任何一步 |
| `tools/release.py::verify_release_assets` | 125 | 125 | 未排进任何一步 |

#### baseline 函数名单（over60）

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/app.py::Api._do_check_inner` | 61 | 61 | 步骤 2 |
| `local/app.py::Api._do_list_inner` | 81 | 81 | 步骤 2 |
| `local/app.py::Api._phone_raw_state` | 64 | 64 | 步骤 2 |
| `local/app.py::Api._start_phone_access` | 66 | 66 | 步骤 2 |
| `local/app.py::Api._start_plan_inner.emit` | 61 | 61 | 步骤 2 |
| `local/app.py::Api.advanced_features_state` | 80 | 80 | 步骤 2 |
| `local/app.py::Api.bootstrap` | 62 | 62 | 步骤 2 |
| `local/app.py::Api.shutdown` | 99 | 99 | 步骤 2 |
| `local/app.py::Api.start_plan` | 70 | 70 | 步骤 2 |
| `local/app.py::Api.update_launch` | 73 | 73 | 步骤 2 |
| `local/app.py::_runtime_check_main` | 61 | 61 | 步骤 2 |
| `local/app.py::main` | 100 | 100 | 步骤 2 |
| `local/application/advanced_component_service.py::AdvancedComponentService._run` | 92 | 92 | 未排进任何一步 |
| `local/application/auto_relogin.py::AutoReloginMonitor.tick` | 90 | 90 | 未排进任何一步 |
| `local/application/login_relay_service.py::LoginRelayService.begin` | 85 | 85 | 未排进任何一步 |
| `local/application/plan_service.py::run_plan_task.feed` | 77 | 77 | 未排进任何一步 |
| `local/build/build_advanced.py::_build_legacy` | 76 | 76 | 未排进任何一步 |
| `local/business_clock.py::BusinessClock._accept_cluster` | 72 | 72 | 未排进任何一步 |
| `local/domain/demo_data.py::demo_items` | 79 | 79 | 未排进任何一步 |
| `local/domain/phone_rules.py::normalize_action` | 76 | 76 | 未排进任何一步 |
| `local/domain/plan_rules.py::classify_task_stop` | 63 | 63 | 未排进任何一步 |
| `local/grab.py::clock_sample` | 61 | 61 | 步骤 3 |
| `local/grab.py::cmd_grab._apply_conclusion` | 74 | 74 | 步骤 3 |
| `local/grab.py::cmd_grab._finalize_once` | 80 | 80 | 步骤 3 |
| `local/grab.py::cmd_grab._try_direct_fire` | 62 | 62 | 步骤 3 |
| `local/grab.py::cmd_grab.terminal` | 75 | 75 | 步骤 3 |
| `local/grab.py::cmd_login` | 77 | 77 | 步骤 3 |
| `local/grab.py::main` | 76 | 76 | 步骤 3 |
| `local/grab.py::run_cancel` | 76 | 76 | 步骤 3 |
| `local/infrastructure/component_packages.py::_helper` | 61 | 61 | 未排进任何一步 |
| `local/infrastructure/component_packages.py::install` | 72 | 72 | 未排进任何一步 |
| `local/infrastructure/component_packages.py::install_artifact` | 64 | 64 | 未排进任何一步 |
| `local/infrastructure/tray_icon.py::TrayIcon._run` | 73 | 73 | 未排进任何一步 |
| `local/infrastructure/tunnel_manager.py::CloudflareTunnel.start` | 84 | 84 | 未排进任何一步 |
| `local/runtime_paths.py::_migrate_legacy_data` | 86 | 86 | 未排进任何一步 |
| `local/signup_plan.py::PlanCoordinator._run` | 66 | 66 | 未排进任何一步 |
| `local/signup_signing.py::_encrypt_block_cng` | 100 | 100 | 未排进任何一步 |
| `local/ui/app.js::#anon52` | 62 | 62 | 步骤 1 共用 |
| `local/ui/app.js::boot` | 77 | 77 | 步骤 1 共用 |
| `local/ui/controllers/plan.js::reconcileStart` | 75 | 75 | 步骤 1C 计划栏 |
| `local/ui/controllers/plan.js::startPlan.#anon1` | 64 | 64 | 步骤 1C 计划栏 |
| `local/ui/controllers/terms.js::acceptTerms.#anon1` | 64 | 64 | 未排进任何一步 |
| `local/ui/controllers/terms.js::recheckTerms` | 63 | 63 | 未排进任何一步 |
| `local/ui/controllers/tick.js::tick` | 88 | 88 | 未排进任何一步 |
| `local/ui/m/app.js::buildWhy` | 85 | 85 | 手机页 |
| `local/ui/m/app.js::ingestRelogin` | 90 | 90 | 手机页 |
| `local/ui/m/app.js::reloginView` | 88 | 88 | 手机页 |
| `local/ui/m/app.js::renderBoard` | 65 | 65 | 手机页 |
| `local/ui/m/app.js::renderItems` | 97 | 97 | 手机页 |
| `local/ui/state/clock.js::ingestBusinessClock` | 80 | 80 | 未排进任何一步 |
| `local/ui/views/clock-pop.js::renderClockPop` | 76 | 76 | 未排进任何一步 |
| `local/ui/views/list.js::paintEmpty` | 95 | 95 | 未排进任何一步 |
| `local/ui/views/list.js::rowHtml` | 68 | 68 | 未排进任何一步 |
| `local/ui/views/phone.js::paintRelogin` | 88 | 88 | 步骤 1A 组件与手机访问 |
| `local/ui/views/phone.js::wire` | 65 | 65 | 步骤 1A 组件与手机访问 |
| `local/ui/views/plan-panel.js::paintBanners` | 95 | 95 | 步骤 1C 计划栏 |
| `local/ui/views/plan-panel.js::paintRunPanel` | 71 | 71 | 步骤 1C 计划栏 |
| `local/ui/views/plan-panel.js::updateControls` | 70 | 70 | 步骤 1C 计划栏 |
| `local/ui/views/relogin.js::receiveReloginState` | 63 | 63 | 步骤 1B 登录 |
| `local/ui/views/terms.js::applyTermsFooter` | 77 | 77 | 未排进任何一步 |
| `local/update_delta.py::apply_delta` | 70 | 70 | 未排进任何一步 |
| `local/update_launcher.py::apply_staged` | 76 | 76 | 未排进任何一步 |
| `local/updater.py::download_installer` | 88 | 88 | 未排进任何一步 |
| `server/bot/bot.js::handleCardAction` | 66 | 66 | 未排进任何一步 |
| `server/bot/bot.js::handleGrabAction` | 63 | 63 | 未排进任何一步 |
| `server/bot/bot.js::handleMessage` | 74 | 74 | 未排进任何一步 |
| `server/deploy/auto_login.py::_submit_once` | 99 | 99 | 未排进任何一步 |
| `server/deploy/grab_signup.py::main` | 66 | 66 | 未排进任何一步 |
| `server/deploy/server_refresh.js::runDaemon` | 80 | 80 | 未排进任何一步 |
| `server/scripts/activity_watch.py::_run_once` | 71 | 71 | 未排进任何一步 |
| `server/scripts/activity_watch.py::compute_events` | 85 | 85 | 未排进任何一步 |
| `server/scripts/dev/explore.py::main` | 63 | 63 | 未排进任何一步 |
| `server/scripts/query.py::main` | 71 | 71 | 未排进任何一步 |
| `server/scripts/regress.py::main` | 76 | 76 | 未排进任何一步 |
| `server/scripts/scan.py::_scan` | 81 | 81 | 未排进任何一步 |
| `server/scripts/token_probe.py::main` | 69 | 69 | 未排进任何一步 |
| `server/scripts/watchlist_runner.py::main` | 76 | 76 | 未排进任何一步 |
| `tools/qa_business_clock_worker.py::run_probe` | 99 | 99 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py::_#20` | 75 | 75 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py::_#62` | 69 | 69 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py::_#63` | 61 | 61 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py::_#7` | 81 | 81 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py::_narrow` | 75 | 75 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py::run_scenarios` | 75 | 75 | 未排进任何一步 |
| `tools/release.py::write_manifest` | 75 | 75 | 未排进任何一步 |
| `tools/verify_autologin_loop.py::main` | 87 | 87 | 未排进任何一步 |

#### baseline 测试函数名单

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/tests/test_lifecycle_release.py::AssetVerificationTests.test_verify_rejects_each_bad_candidate` | 92 | 92 | 未排进任何一步 |
| `local/tests/test_phone_ui.py::ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` | 71 | 71 | 未排进任何一步 |
| `local/tests/test_phone_ui.py::ResultTermsModelTests.test_result_view_counts_and_heads_follow_prototype` | 84 | 84 | 未排进任何一步 |
| `local/tests/test_phone_ui.py::RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` | 65 | 65 | 未排进任何一步 |
| `local/tests/test_phone_ui.py::RunWaitModelTests.test_task_card_follows_prototype_detail_priority` | 72 | 72 | 未排进任何一步 |
| `local/tests/test_phone_ui.py::WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` | 67 | 67 | 未排进任何一步 |
| `local/tests/test_retry_phone_integration.py::FullChainTests.test_pair_read_start_extend_stop_relogin_chain` | 66 | 66 | 未排进任何一步 |
| `local/tests/test_ui_contract_list.py::TimetableGroupingBehaviorTests.test_group_timetable_places_each_activity_in_its_correct_group` | 106 | 106 | 未排进任何一步 |
| `local/tests/test_ui_contract_shell.py::WorkbenchUiContractTests.test_close_dialog_three_exits` | 138 | 138 | 未排进任何一步 |
| `local/tests/test_ui_contract_shell.py::WorkbenchUiContractTests.test_five_pre_start_warnings_only_remind` | 61 | 61 | 未排进任何一步 |
| `local/tests/test_ui_contract_terms.py::TermsConsentBehaviorTests.test_decline_does_not_reprompt_and_keeps_help_available` | 62 | 62 | 未排进任何一步 |
| `local/tests/test_ui_contract_terms.py::TermsConsentBehaviorTests.test_unknown_terms_accept_rejects_bad_receipts` | 68 | 68 | 未排进任何一步 |
| `local/tests/test_ui_contract_terms.py::TermsConsentContractTests.test_accept_terms_writes_prefs_transaction_only` | 77 | 77 | 未排进任何一步 |
| `local/tests/test_ui_contract_terms.py::TermsConsentContractTests.test_terms_dialog_structure_contract` | 127 | 127 | 未排进任何一步 |
| `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_boot_defers_intro_until_terms_accepted` | 69 | 69 | 未排进任何一步 |
| `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_close_restores_banner_focus_without_stacking_dialogs` | 62 | 62 | 未排进任何一步 |
| `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_save_timeout_keeps_gate_reopens_close_and_drops_late_receipt` | 64 | 64 | 未排进任何一步 |
| `local/tests/test_ui_contract_update.py::UpdateBoardPaintTests.test_one_primary_action_per_state` | 75 | 75 | 未排进任何一步 |
| `local/tests/test_worker_boundaries.py::ListEntryTests.test_cmd_list_without_clock_keeps_full_enrich` | 63 | 63 | 未排进任何一步 |

#### baseline 类名单

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/app.py::Api` | 23 | 23 | 步骤 2 |
| `local/application/advanced_component_service.py::AdvancedComponentService` | 8 | 8 | 未排进任何一步 |
| `local/application/auto_relogin.py::AutoReloginMonitor` | 8 | 8 | 未排进任何一步 |
| `local/application/phone_service.py::PhoneAccessService` | 12 | 12 | 未排进任何一步 |

#### 前端分层白名单 ui_layer_allow.json（归属按「引用方文件」；另列「被引用名字的定义文件」的归属）

| 条目（引用方文件 × 名字）| 引用方归属 | 当前行数 | 定义文件 | 定义文件归属 |
|---|---|---|---|---|
| `local/ui/state/clock.js × paintClockPopFeedback` | 未排进任何一步 | 314 | `local/ui/views/clock-pop.js` | 未排进任何一步 |
| `local/ui/state/clock.js × paintClockStatus` | 未排进任何一步 | 314 | `local/ui/views/clock.js` | 未排进任何一步 |
| `local/ui/state/clock.js × render` | 未排进任何一步 | 314 | `local/ui/views/list.js` | 未排进任何一步 |
| `local/ui/state/clock.js × renderClockPop` | 未排进任何一步 | 314 | `local/ui/views/clock-pop.js` | 未排进任何一步 |
| `local/ui/state/clock.js × updateControls` | 未排进任何一步 | 314 | `local/ui/views/plan-panel.js` | 步骤 1C 计划栏 |
| `local/ui/state/filters.js × render` | 未排进任何一步 | 393 | `local/ui/views/list.js` | 未排进任何一步 |
| `local/ui/state/filters.js × setResult` | 未排进任何一步 | 393 | `local/ui/views/login.js` | 步骤 1B 登录 |
| `local/ui/state/login.js × paintBoardActions` | 步骤 1B 登录 | 141 | `local/ui/views/plan-panel.js` | 步骤 1C 计划栏 |
| `local/ui/state/login.js × paintClockStatus` | 步骤 1B 登录 | 141 | `local/ui/views/clock.js` | 未排进任何一步 |
| `local/ui/state/login.js × paintLogin` | 步骤 1B 登录 | 141 | `local/ui/views/login.js` | 步骤 1B 登录 |
| `local/ui/state/login.js × paintRail` | 步骤 1B 登录 | 141 | `local/ui/views/list.js` | 未排进任何一步 |
| `local/ui/state/login.js × paintSelected` | 步骤 1B 登录 | 141 | `local/ui/views/plan-panel.js` | 步骤 1C 计划栏 |
| `local/ui/state/login.js × refreshLoginEmptyState` | 步骤 1B 登录 | 141 | `local/ui/views/list.js` | 未排进任何一步 |
| `local/ui/state/login.js × reloginAutoLive` | 步骤 1B 登录 | 141 | `local/ui/views/relogin.js` | 步骤 1B 登录 |
| `local/ui/state/login.js × render` | 步骤 1B 登录 | 141 | `local/ui/views/list.js` | 未排进任何一步 |
| `local/ui/state/plan.js × noteSignedTasks` | 步骤 1C 计划栏 | 175 | `local/ui/controllers/refresh.js` | 步骤 1 共用 |
| `local/ui/state/plan.js × noteStartedFromPhone` | 步骤 1C 计划栏 | 175 | `local/ui/controllers/plan.js` | 步骤 1C 计划栏 |
| `local/ui/state/plan.js × render` | 步骤 1C 计划栏 | 175 | `local/ui/views/list.js` | 未排进任何一步 |
| `local/ui/state/plan.js × scheduleSignedRefresh` | 步骤 1C 计划栏 | 175 | `local/ui/controllers/refresh.js` | 步骤 1 共用 |
| `local/ui/state/plan.js × setBusy` | 步骤 1C 计划栏 | 175 | `local/ui/views/login.js` | 步骤 1B 登录 |
| `local/ui/state/plan.js × showTaskResult` | 步骤 1C 计划栏 | 175 | `local/ui/controllers/plan-events.js` | 步骤 1C 计划栏 |
| `local/ui/views/clock-pop.js × resyncClock` | 未排进任何一步 | 152 | `local/ui/controllers/clock.js` | 未排进任何一步 |
| `local/ui/views/conflict-tip.js × savePrefs` | 未排进任何一步 | 147 | `local/ui/controllers/prefs.js` | 未排进任何一步 |
| `local/ui/views/help.js × savePrefs` | 未排进任何一步 | 67 | `local/ui/controllers/prefs.js` | 未排进任何一步 |
| `local/ui/views/list.js × listErrorCopy` | 未排进任何一步 | 449 | `local/ui/controllers/tick.js` | 未排进任何一步 |
| `local/ui/views/list.js × tick` | 未排进任何一步 | 449 | `local/ui/controllers/tick.js` | 未排进任何一步 |
| `local/ui/views/log.js × savePrefs` | 未排进任何一步 | 29 | `local/ui/controllers/prefs.js` | 未排进任何一步 |
| `local/ui/views/phone.js × api` | 步骤 1A 组件与手机访问 | 1252 | `local/ui/controllers/bridge.js` | 未排进任何一步 |
| `local/ui/views/phone.js × refresh` | 步骤 1A 组件与手机访问 | 1252 | `local/ui/controllers/refresh.js` | 步骤 1 共用 |
| `local/ui/views/plan-panel.js × refresh` | 步骤 1C 计划栏 | 1367 | `local/ui/controllers/refresh.js` | 步骤 1 共用 |
| `local/ui/views/plan-panel.js × runtimeErrorCopy` | 步骤 1C 计划栏 | 1367 | `local/ui/controllers/refresh.js` | 步骤 1 共用 |
| `local/ui/views/relogin.js × api` | 步骤 1B 登录 | 555 | `local/ui/controllers/bridge.js` | 未排进任何一步 |
| `local/ui/views/relogin.js × doCheck` | 步骤 1B 登录 | 555 | `local/ui/controllers/tick.js` | 未排进任何一步 |
| `local/ui/views/relogin.js × doLogin` | 步骤 1B 登录 | 555 | `local/ui/controllers/plan.js` | 步骤 1C 计划栏 |
| `local/ui/views/relogin.js × refresh` | 步骤 1B 登录 | 555 | `local/ui/controllers/refresh.js` | 步骤 1 共用 |
| `local/ui/views/selection.js × savePrefs` | 未排进任何一步 | 90 | `local/ui/controllers/prefs.js` | 未排进任何一步 |
| `local/ui/views/settings.js × api` | 步骤 1A 组件与手机访问 | 397 | `local/ui/controllers/bridge.js` | 未排进任何一步 |
| `local/ui/views/settings.js × ingestTerms` | 步骤 1A 组件与手机访问 | 397 | `local/ui/controllers/terms.js` | 未排进任何一步 |
| `local/ui/views/settings.js × savePrefs` | 步骤 1A 组件与手机访问 | 397 | `local/ui/controllers/prefs.js` | 未排进任何一步 |
| `local/ui/views/status-cards.js × doCheck` | 步骤 1B 登录 | 204 | `local/ui/controllers/tick.js` | 未排进任何一步 |
| `local/ui/views/tour.js × savePrefsNow` | 未排进任何一步 | 174 | `local/ui/controllers/prefs.js` | 未排进任何一步 |

#### 分层测试存量例外 LEGACY_DIRECTION_VIOLATIONS

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/application/advanced_component_service.py import infrastructure.component_packages` | — | 503 | 未排进任何一步 |
| `local/infrastructure/component_packages.py import runtime_paths` | — | 1666 | 未排进任何一步 |

#### ruff.toml per-file-ignores

| 条目 | 记录值 | 当前值 | 归属 |
|---|---|---|---|
| `local/advanced_helper.py × F401` | — | F401 | 未排进任何一步 |
| `local/app.py × F401` | — | F401 | 步骤 2 |
| `local/application/advanced_component_service.py × F401` | — | F401 | 未排进任何一步 |
| `local/application/login_relay_service.py × F401` | — | F401 | 未排进任何一步 |
| `local/application/phone_service.py × F401` | — | F401 | 未排进任何一步 |
| `local/build/build_installer.py × F401` | — | F401 | 未排进任何一步 |
| `local/grab.py × F401` | — | F401 | 步骤 3 |
| `local/infrastructure/credential_store.py × F841` | — | F841 | 未排进任何一步 |
| `local/infrastructure/lifecycle_store.py × F841` | — | F841 | 未排进任何一步 |
| `local/signup_plan.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_advanced_features.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_auto_relogin.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_business_clock.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_business_clock_wiring.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_cancel_signup.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_lifecycle_release.py × F841` | — | F841 | 未排进任何一步 |
| `local/tests/test_login_relay.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_login_relay_service.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_network_policy.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_phone_http.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_phone_http.py × F841` | — | F841 | 未排进任何一步 |
| `local/tests/test_phone_service.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_phone_service.py × F841` | — | F841 | 未排进任何一步 |
| `local/tests/test_release_audit.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_retry_phone_policy.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_retry_policy.py × F841` | — | F841 | 未排进任何一步 |
| `local/tests/test_session_persistence.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_session_persistence.py × F823` | — | F823 | 未排进任何一步 |
| `local/tests/test_signup_plan.py × F841` | — | F841 | 未排进任何一步 |
| `local/tests/test_time_contract.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_ui_contract_settings.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_ui_contract_shell.py × F401` | — | F401 | 未排进任何一步 |
| `local/tests/test_updater.py × F811` | — | F811 | 未排进任何一步 |
| `local/tests/test_worker_boundaries.py × F841` | — | F841 | 未排进任何一步 |
| `server/deploy/auto_login.py × F401` | — | F401 | 未排进任何一步 |
| `server/deploy/grab_signup.py × F401` | — | F401 | 未排进任何一步 |
| `server/scripts/common.py × F401` | — | F401 | 未排进任何一步 |
| `server/scripts/dev/explore.py × F401` | — | F401 | 未排进任何一步 |
| `server/scripts/fetch.py × F541` | — | F541 | 未排进任何一步 |
| `server/scripts/token_probe.py × F841` | — | F841 | 未排进任何一步 |
| `server/scripts/token_report.py × F841` | — | F841 | 未排进任何一步 |
| `tools/qa_business_clock_worker.py × F401` | — | F401 | 未排进任何一步 |
| `tools/qa_runtime_reliability.py × F841` | — | F841 | 未排进任何一步 |
| `tools/split_branches.py × F401` | — | F401 | 未排进任何一步 |


### 表 A 抽查记录（代码库入职引导工程师核对，主代理转录）

1. 记录值与归属抽查一致：`tools/code_shape/baseline.json` 键 `files.over800["local/ui/views/plan-panel.js"]` 记录值 1367、键 `functions.over60["local/ui/views/phone.js::paintRelogin"]` 记录值 88，脚本输出 A3 中两条的「记录值」列同为 1367、88，归属同为「步骤 1C 计划栏」「步骤 1A 组件与手机访问」，与 D2 对照表（plan-panel.js=1C、phone.js=1A）一致；`tools/code_shape/ui_layer_allow.json` 键 `state/login.js` 含名字 `paintLogin`，输出对应行引用方归属「步骤 1B 登录」、定义文件 `local/ui/views/login.js` 归属「步骤 1B 登录」，与 D2（state/login.js=1B、views/login.js=1B）一致。
2. ruff 与分层白名单抽查一致：`ruff.toml:53` 为 `"local/tests/test_updater.py" = ["F811"]`，输出记「未排进任何一步」（该文件不在 D2 对照表）；`ruff.toml:25` `"local/app.py" = ["F401"]` 输出记「步骤 2」；`local/tests/test_layer_boundaries.py:213` 的键 `("infrastructure/component_packages.py", "runtime_paths")`（脚本补 `local/` 前缀）输出记「未排进任何一步」，均与 D2 对照表相符。（返修注明：本条转录自派发代理，原文把两处 ruff.toml 行号写成 31 与 3，经对 ruff.toml 原文核对改正为 53 与 25；其余内容未动。）
3. 汇总自校一致：A2 各来源行数为 baseline 106 + 前端白名单 15 + 分层测试 2 + ruff 42 = 165，等于 A1「未排进任何一步 165」；A3 明细按归属列逐条计数为 1A=10、1B=16、1C=18、1共用=6、步骤2=17、步骤3=13、手机页=9、未排进=165，合计 254，与 A1 各行及自校行「89 + 165 = 254 -> 成立」完全一致。

**表 B：前端文件耦合（D4）**

复跑命令：`node design/evidence/2026-11-13/refactor-endpoint/scripts/ui_coupling.mjs`

### B1 每个脚本：行数、顶层函数、全局名字、S 写入

量什么：local/ui 下不含 m/ 的每个脚本（按 index.html 加载顺序，不在顺序里的附后并标注）；行数是物理行；顶层函数数只数 function 声明；全局名字数是顶层定义（function/const/let/var/class/window.X）个数；S 写入处数按 globals.mjs 的写入判定。

| 序 | 文件 | 层 | 归属 | 行数 | 顶层函数数 | 全局名字数 | S 写入处数 |
|---|---|---|---|---|---|---|---|
| 1 | `local/ui/led.js` | root | 未排进任何一步 | 118 | 0 | 0 | 0 |
| 2 | `local/ui/state/store.js` | state | 步骤 1 共用 | 199 | 2 | 12 | 0 |
| 3 | `local/ui/state/terms.js` | state | 未排进任何一步 | 19 | 2 | 2 | 0 |
| 4 | `local/ui/state/rounds.js` | state | 未排进任何一步 | 85 | 7 | 9 | 8 |
| 5 | `local/ui/controllers/bridge.js` | controllers | 未排进任何一步 | 35 | 3 | 3 | 0 |
| 6 | `local/ui/controllers/refresh.js` | controllers | 步骤 1 共用 | 614 | 23 | 32 | 73 |
| 7 | `local/ui/views/list.js` | views | 未排进任何一步 | 449 | 18 | 18 | 7 |
| 8 | `local/ui/state/task-display.js` | state | 步骤 1C 计划栏 | 248 | 11 | 12 | 0 |
| 9 | `local/ui/views/plan-panel.js` | views | 步骤 1C 计划栏 | 1367 | 56 | 58 | 6 |
| 10 | `local/ui/controllers/plan.js` | controllers | 步骤 1C 计划栏 | 532 | 20 | 21 | 54 |
| 11 | `local/ui/state/clock.js` | state | 未排进任何一步 | 314 | 18 | 29 | 0 |
| 12 | `local/ui/views/clock.js` | views | 未排进任何一步 | 32 | 1 | 1 | 0 |
| 13 | `local/ui/controllers/clock.js` | controllers | 未排进任何一步 | 61 | 3 | 3 | 5 |
| 14 | `local/ui/state/plan.js` | state | 步骤 1C 计划栏 | 175 | 14 | 16 | 16 |
| 15 | `local/ui/controllers/plan-events.js` | controllers | 步骤 1C 计划栏 | 134 | 5 | 5 | 16 |
| 16 | `local/ui/state/login.js` | state | 步骤 1B 登录 | 141 | 9 | 9 | 22 |
| 17 | `local/ui/views/login.js` | views | 步骤 1B 登录 | 173 | 4 | 5 | 4 |
| 18 | `local/ui/views/relogin.js` | views | 步骤 1B 登录 | 555 | 34 | 43 | 20 |
| 19 | `local/ui/views/clock-pop.js` | views | 未排进任何一步 | 152 | 8 | 8 | 3 |
| 20 | `local/ui/views/status-cards.js` | views | 步骤 1B 登录 | 204 | 14 | 17 | 3 |
| 21 | `local/ui/views/log.js` | views | 未排进任何一步 | 29 | 2 | 2 | 1 |
| 22 | `local/ui/views/terms.js` | views | 未排进任何一步 | 507 | 35 | 37 | 0 |
| 23 | `local/ui/controllers/terms.js` | controllers | 未排进任何一步 | 477 | 17 | 18 | 85 |
| 24 | `local/ui/views/update.js` | views | 未排进任何一步 | 187 | 6 | 8 | 3 |
| 25 | `local/ui/views/help.js` | views | 未排进任何一步 | 67 | 6 | 6 | 0 |
| 26 | `local/ui/views/settings.js` | views | 步骤 1A 组件与手机访问 | 397 | 19 | 21 | 2 |
| 27 | `local/ui/views/phone.js` | views | 步骤 1A 组件与手机访问 | 1252 | 10 | 14 | 0 |
| 28 | `local/ui/controllers/update.js` | controllers | 未排进任何一步 | 148 | 8 | 8 | 15 |
| 29 | `local/ui/controllers/prefs.js` | controllers | 未排进任何一步 | 41 | 3 | 3 | 16 |
| 30 | `local/ui/state/filters.js` | state | 未排进任何一步 | 393 | 25 | 25 | 10 |
| 31 | `local/ui/state/conflict.js` | state | 未排进任何一步 | 176 | 17 | 19 | 0 |
| 32 | `local/ui/views/selection.js` | views | 未排进任何一步 | 90 | 6 | 8 | 3 |
| 33 | `local/ui/views/conflict-tip.js` | views | 未排进任何一步 | 147 | 11 | 11 | 9 |
| 34 | `local/ui/controllers/cancel.js` | controllers | 未排进任何一步 | 94 | 6 | 6 | 13 |
| 35 | `local/ui/state/labels.js` | state | 未排进任何一步 | 107 | 10 | 10 | 0 |
| 36 | `local/ui/controllers/tick.js` | controllers | 未排进任何一步 | 165 | 10 | 11 | 4 |
| 37 | `local/ui/state/time.js` | state | 未排进任何一步 | 154 | 15 | 18 | 0 |
| 38 | `local/ui/views/tour.js` | views | 未排进任何一步 | 174 | 13 | 13 | 12 |
| 39 | `local/ui/controllers/window.js` | controllers | 未排进任何一步 | 276 | 14 | 15 | 1 |
| 40 | `local/ui/app.js` | root | 步骤 1 共用 | 655 | 2 | 7 | 33 |

文件总数：40（index.html 顺序 40 个，另外发现 0 个）。
同一名字在两个文件里都有顶层定义：0 处。
同一文件内同名顶层定义：1 处：PhonePanel: views/phone.js:154 与 :1252；全局名字按唯一名计 562 个，逐文件定义合计 563 个（两数之差即同名重复定义）。

### B2 未排进任何一步的脚本与步骤 1 文件的相互引用

量什么：左边是它引用的定义在步骤 1 文件（1A、1B、1C、共用）里的名字数与清单；右边是它定义、被步骤 1 文件引用的名字数与清单。按名字匹配，排除属性访问、对象字面量键、本文件同名局部声明。

| 文件 | 引用步骤 1 定义的名字数 | 名字 | 被步骤 1 引用的名字数 | 名字 |
|---|---|---|---|---|
| `local/ui/led.js` | 0 | — | 0 | — |
| `local/ui/state/terms.js` | 1 | S | 2 | termsAccepted、termsLocked |
| `local/ui/state/rounds.js` | 1 | S | 7 | bumpRoundGeneration、cacheRoundPayload、firstNotice、loginPresent、markRoundApplied、newRoundId、takeRoundPayload |
| `local/ui/controllers/bridge.js` | 0 | — | 3 | api、hasBridge、waitForBridge |
| `local/ui/views/list.js` | 14 | $、S、executionView、paintBanners、paintBoardState、paintChecks、paintLed、paintPlan、paintRoute、paintSelected、planOutcome、taskDisplayLabel、unknownLabel、updateControls | 3 | paintRail、refreshLoginEmptyState、render |
| `local/ui/state/clock.js` | 2 | S、updateControls | 11 | TASK_RUNTIME_FIELDS、_monoMs、bnLeftSec、bnowS、businessNowMs、clockParts、clockPopOpenNow、clockReading、clockUiState、clockUncertaintyText、ingestBusinessClock |
| `local/ui/views/clock.js` | 1 | $ | 1 | paintClockStatus |
| `local/ui/controllers/clock.js` | 2 | S、msg | 3 | pollClockNow、resyncClock、startClockPolling |
| `local/ui/views/clock-pop.js` | 3 | $、S、numOrNull | 3 | applyClock、closeClockPop、toggleClockPop |
| `local/ui/views/log.js` | 3 | $、S、addLog | 2 | copyLog、setLogOpen |
| `local/ui/views/terms.js` | 3 | $、FIRST_USE_POINTS、S | 7 | applyTermsFooter、closeTermsIntroBox、closeTermsUpdateBox、reopenTermsBox、switchTermsDoc、termsCloseIntent、termsUpdateMode |
| `local/ui/controllers/terms.js` | 6 | S、addLog、msg、paintBanners、refresh、updateControls | 11 | acceptTerms、declineTerms、ensureLicenseText、ingestTerms、markTermsUnknown、noteTermsRequired、openTerms、openTermsReader、recheckTerms、restoreTermsFocus、resumeTermsTour |
| `local/ui/views/update.js` | 2 | $、S | 0 | — |
| `local/ui/views/help.js` | 5 | $、DEFAULT_HELP、PhonePanel、S、addLog | 5 | fillHelp、helpStatus、paintReplayButtons、replayTourFrom、showHelp |
| `local/ui/controllers/update.js` | 2 | S、msg | 7 | cancelDownload、checkUpdate、confirmDownload、launchInstaller、receiveUpdate、restoreUpdate、startDownload |
| `local/ui/controllers/prefs.js` | 2 | S、addLog | 1 | savePrefs |
| `local/ui/state/filters.js` | 3 | S、setResult、verifiedSigned | 13 | clearSelection、findItem、groupSelected、isEligibleForPlan、nextOpen、normalize、selectedItems、signStartPending、signedClash、sleepMissedNames、taskMissedBySleep、toggleSelection、validateSelection |
| `local/ui/state/conflict.js` | 1 | S | 1 | cancelBlock |
| `local/ui/views/selection.js` | 3 | $、S、setResult | 4 | paintChips、setFilter、setFilterOpen、showPlanError |
| `local/ui/views/conflict-tip.js` | 2 | $、S | 8 | placeTip、tipClose、tipGoSigned、tipKey、tipLater、tipOpen、tipSoon、tipStay |
| `local/ui/controllers/cancel.js` | 3 | S、addLog、refresh | 3 | cancelAsk、cancelAskDismiss、cancelConfirm |
| `local/ui/state/labels.js` | 1 | verifiedSigned | 8 | activityTimeText、leftOf、modeOf、modeText、signStartKnown、stateOf、taskClass、taskLabel |
| `local/ui/controllers/tick.js` | 20 | $、RUNNING_STATUSES、S、SLEEP_GAP_MS、addLog、addLogFresh、msg、paintBanners、paintCountdown、paintEditNote、paintLed、paintLogin、paintRoute、paintRunPanel、paintSelected、runHeadKey、runtimeErrorCopy、taskDisplayDetail、taskDisplayLabel、taskModePrefix | 7 | cleanReason、doCheck、grabHint、listErrorCopy、receiveSecondOpen、stripLabel、tick |
| `local/ui/state/time.js` | 1 | WEEK | 11 | durText、esc、fmt、fmtClock、hm、hmsDay、schoolParts、shortTime、startOfDay、toTs、whenText |
| `local/ui/views/tour.js` | 4 | $、S、TOUR_STEPS、TOUR_VERSION | 11 | maybeStartTour、paintTour、requestAutoTour、tourClose、tourGuardClick、tourPauseNow、tourResumeNow、tourShouldAutoStart、tourSkip、tourTrapTab、tourVisible |
| `local/ui/controllers/window.js` | 3 | S、addLog、msg | 1 | openWindowCloseDialog |

未排进脚本共 26 个。

### 表 B 抽查记录（代码库入职引导工程师核对，主代理转录；返修后作者重出）

1. 行数抽查仍成立且数据未变：重跑退出码 0，与上一轮 stdout 逐行 diff 仅新增尾注一行，B1 40 行数据、B2 26 行数据逐行未变；抽 `local/ui/views/plan-panel.js`（序 9）1367 行、`local/ui/app.js`（序 40）655 行、`local/ui/state/filters.js`（序 30）393 行，python -c 按行数与「行数」列一致。
2. 全局名字数抽查仍成立：`local/ui/views/clock.js`（序 12，32 行）顶层仅 `function paintClockStatus()`（local/ui/views/clock.js:2），无其他顶层 function/const/let/var/class 声明，计数 1 与重跑输出一致。
3. 新尾注行核实：B1「全局名字数」列逐文件合计 563（40 行 awk 求和）；`node ui_coupling.mjs --defs` 返回唯一顶层名 562 个，PhonePanel 记在 views/phone.js；`local/ui/views/phone.js:154` 顶层 `const PhonePanel = {` 与 `:1252` 顶层 `window.PhonePanel = PhonePanel` 两处均按脚本口径计入定义，逐文件合计比唯一名恰多 1，与尾注行所述一致。

**表 C：审计数字对照（D5）**

量什么：在当前提交（`dddc179`）上重跑那轮基线（`7e2d31c`）的五个清点脚本，把两轮都写过的数字逐个列成「审计时｜现在」两栏；按口径，旧时间戳不做换算，对照时只写「那轮基线 / 本轮」。

复跑命令（五个脚本各一行，均从仓库根执行）：

```bash
python -B design/evidence/2026-11-12/refactor-audit/scripts/measure.py
python -B design/evidence/2026-11-12/refactor-audit/scripts/py_layers.py
python -B design/evidence/2026-11-12/refactor-audit/scripts/py_state.py
python -B design/evidence/2026-11-12/refactor-audit/scripts/app_reexports.py
node design/evidence/2026-11-12/refactor-audit/scripts/globals.mjs
```

| 指标 | 审计时（那轮基线 7e2d31c） | 现在（本轮基线 dddc179） | 出处脚本 |
|---|---|---|---|
| 前端全局名字总数 | 560 | 562 | globals.mjs |
| S 的引用次数 / 引用文件数 | 1344 / 32 | 1356 / 33 | globals.mjs |
| S 的写入处数 / 写入文件数 | 441 / 27 | 444 / 27 | globals.mjs |
| 依赖环里的脚本数 / 脚本总数 | 33 / 39 | 33 / 40 | globals.mjs |
| state 引用上层的名字数 / 处数 | 25 / 62 | 17 / 40 | globals.mjs |
| views 引用 controllers 的名字数 / 处数 | 15 / 80 | 11 / 50 | globals.mjs |
| Api 的方法数 | 153 | 153 | py_state.py |
| Api 上在 3 个及以上方法里赋值的标志位数 | 23 | 23 | py_state.py |
| 用到主锁 self._lock 的方法数 | 67 | 67 | py_state.py |
| 测试按 app.X 打补丁的名字数 | 42 | 42 | app_reexports.py |
| 测试改写的 Api 实例成员数 | 66 | 67 | py_state.py |

### 表 C 运行情况与出处（后端架构师核对，主代理转录）

- 五个命令均按那轮 README 的复跑段照抄执行（Python 一律加 -B），退出码全 0，stderr 全空，全部产出完整 stdout，无一行「输出里没有该行」。
- 各脚本 stdout 行数：measure.py 275、py_layers.py 49、py_state.py 203、app_reexports.py 139、globals.mjs 878。
- 「现在」值的取行位置（与本轮 stdout 核对过列序与小节归属）：globals.mjs 的「读了 40 个脚本，顶层定义了 562 个全局名字」「状态仓库 S 的写入：444 处，分布在 27 个文件」「33 个文件互相可达」、高扇入表（表头 名字/定义位置/种类/引用它的文件数/引用次数）S 行 33 与 1356、state 段与 views 段两条「去重后 N 个名字…共 K 处引用」（分别位于「越界引用：state/…」与「越界引用：views/…」小节下，17/40 与 11/50）；py_state.py 的「Api 实例属性（local/app.py，153 个方法，74 个属性）」「在 3 个及以上方法里赋值的属性，共 23 个」「被最多方法读取的 15 个属性」表首行 self._lock 67、「测试改写 Api 实例成员的位置（67 个名字）」；app_reexports.py 的「被测试打补丁的模块级名字，共 42 个」。
- 伴随事实（仅陈述，不做解读）：py_layers.py 本轮「扫了 50 个文件」（那轮 51）；py_state.py 本轮「扫了 79 个文件」（那轮 80）；app_reexports.py 本轮「local/tests/ 和 tools/ 里有 18 个文件用到了 app 模块」（那轮 15）；measure.py 本轮产品 Python 90 个文件、总行数 36439（那轮 37070）。
- measure.py / py_layers.py 概要数字：measure.py 文件行数表「产品 Python」一行本轮 90 个文件（总行数 36439），文件数与那轮 inventory.md 的 90 一致；py_layers.py「越界的 import，共 2 条」，条数与那轮 inventory.md 的 2 条一致。两个脚本本轮都跑出了完整输出。

**表 D：类型标注覆盖（D6）**

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/annotations.py`

## 表 D：类型标注覆盖

量什么：local 与 server 下的 Python 函数（含方法与嵌套函数；不含测试目录），按参数与返回值标注分三类；self、cls 不算参数。分组：五组照计划 D6，local/build 与 local 其他子目录的文件不在五组内，单列。

### D1 分组汇总

| 组 | 文件数 | 函数数 | 参数与返回值都标了 | 标了一部分 | 完全没标 |
|---|---|---|---|---|---|
| local/domain | 14 | 83 | 16 | 49 | 18 |
| local/application | 8 | 96 | 46 | 30 | 20 |
| local/infrastructure | 13 | 208 | 74 | 48 | 86 |
| local 根目录 | 15 | 614 | 325 | 87 | 202 |
| server | 29 | 261 | 87 | 28 | 146 |
| local/build | 4 | 45 | 31 | 0 | 14 |
| local 其他子目录 | 0 | 0 | 0 | 0 | 0 |

### D2 每组函数最多的十个文件

| 组 | 文件 | 函数数 | 都标了 | 一部分 | 完全没标 |
|---|---|---|---|---|---|
| local/domain | `local/domain/phone_rules.py` | 28 | 0 | 18 | 10 |
| local/domain | `local/domain/login_rules.py` | 11 | 6 | 5 | 0 |
| local/domain | `local/domain/retry_rules.py` | 7 | 3 | 4 | 0 |
| local/domain | `local/domain/retry_window.py` | 7 | 0 | 0 | 7 |
| local/domain | `local/domain/plan_rules.py` | 6 | 0 | 6 | 0 |
| local/domain | `local/domain/log_events.py` | 5 | 0 | 5 | 0 |
| local/domain | `local/domain/time_text.py` | 5 | 0 | 5 | 0 |
| local/domain | `local/domain/lifecycle_rules.py` | 4 | 3 | 0 | 1 |
| local/domain | `local/domain/cancel_rules.py` | 3 | 1 | 2 | 0 |
| local/domain | `local/domain/signup_reply.py` | 3 | 0 | 3 | 0 |
| local/application | `local/application/phone_service.py` | 27 | 19 | 7 | 1 |
| local/application | `local/application/login_relay_service.py` | 22 | 7 | 14 | 1 |
| local/application | `local/application/advanced_component_service.py` | 20 | 14 | 3 | 3 |
| local/application | `local/application/auto_relogin.py` | 11 | 0 | 0 | 11 |
| local/application | `local/application/update_service.py` | 8 | 1 | 3 | 4 |
| local/application | `local/application/plan_service.py` | 6 | 4 | 2 | 0 |
| local/application | `local/application/login_service.py` | 2 | 1 | 1 | 0 |
| local/application | `local/application/__init__.py` | 0 | 0 | 0 | 0 |
| local/infrastructure | `local/infrastructure/component_packages.py` | 70 | 0 | 8 | 62 |
| local/infrastructure | `local/infrastructure/phone_http.py` | 31 | 13 | 2 | 16 |
| local/infrastructure | `local/infrastructure/single_instance.py` | 20 | 10 | 8 | 2 |
| local/infrastructure | `local/infrastructure/tunnel_manager.py` | 17 | 4 | 8 | 5 |
| local/infrastructure | `local/infrastructure/credential_store.py` | 13 | 13 | 0 | 0 |
| local/infrastructure | `local/infrastructure/lifecycle_store.py` | 12 | 10 | 2 | 0 |
| local/infrastructure | `local/infrastructure/process_tree.py` | 12 | 6 | 5 | 1 |
| local/infrastructure | `local/infrastructure/tray_icon.py` | 10 | 8 | 2 | 0 |
| local/infrastructure | `local/infrastructure/advanced_features.py` | 8 | 3 | 5 | 0 |
| local/infrastructure | `local/infrastructure/phone_session_store.py` | 8 | 4 | 4 | 0 |
| local 根目录 | `local/app.py` | 218 | 184 | 22 | 12 |
| local 根目录 | `local/grab.py` | 161 | 10 | 4 | 147 |
| local 根目录 | `local/business_clock.py` | 50 | 41 | 9 | 0 |
| local 根目录 | `local/login_relay.py` | 38 | 0 | 9 | 29 |
| local 根目录 | `local/signup_plan.py` | 26 | 26 | 0 | 0 |
| local 根目录 | `local/update_check.py` | 24 | 14 | 10 | 0 |
| local 根目录 | `local/update_delta.py` | 18 | 9 | 8 | 1 |
| local 根目录 | `local/updater.py` | 18 | 6 | 10 | 2 |
| local 根目录 | `local/update_launcher.py` | 17 | 10 | 5 | 2 |
| local 根目录 | `local/time_contract.py` | 13 | 5 | 7 | 1 |
| server | `server/deploy/grab_signup.py` | 41 | 0 | 0 | 41 |
| server | `server/deploy/auto_login.py` | 29 | 1 | 0 | 28 |
| server | `server/scripts/card.py` | 22 | 3 | 1 | 18 |
| server | `server/scripts/notify.py` | 20 | 10 | 10 | 0 |
| server | `server/scripts/activity_watch.py` | 19 | 14 | 5 | 0 |
| server | `server/scripts/common.py` | 16 | 11 | 1 | 4 |
| server | `server/scripts/fetch.py` | 14 | 10 | 3 | 1 |
| server | `server/scripts/watchlist.py` | 12 | 8 | 3 | 1 |
| server | `server/scripts/run.py` | 10 | 7 | 2 | 1 |
| server | `server/scripts/render.py` | 8 | 0 | 0 | 8 |
| local/build | `local/build/build_advanced.py` | 14 | 0 | 0 | 14 |
| local/build | `local/build/make_portable.py` | 13 | 13 | 0 | 0 |
| local/build | `local/build/build_installer.py` | 12 | 12 | 0 | 0 |
| local/build | `local/build/build_exe.py` | 6 | 6 | 0 | 0 |

全部函数合计：1307；都标了 579、一部分 242、完全没标 486。

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/annotations.py`

### 表 D 抽查记录（测试自动化工程师核对，主代理转录）

1. 用 `python -I -c` 自写 ast 计数（按 D6 口径：FunctionDef/AsyncFunctionDef 含方法与嵌套，self/cls 不算参数，零参无返回注算未标）独立复算 `local/domain/phone_rules.py`：总数 28，都标 0、部分 18、未标 10，与 D2 该行一致；同法复算 `local/app.py`：总数 218，都标 184、部分 22、未标 12，与 D2 该行一致。
2. `local/` 下直接的 `.py` 文件共 15 个（列表中无 `_site_build.py`，与脚本排除项一致），与 D1「local 根目录」文件数 15 一致。
3. D1 七行函数数相加 83+96+208+614+261+45+0=1307，三类相加 579+242+486=1307，与文末「全部函数合计 1307」一致。

**表 E：界面测试字面断言分类（D7）**

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_assertions.py`

## 表 E：界面测试字面断言分类

量什么：local/tests 的 test_ui_*.py 与 test_phone_ui.py 里，assertIn、assertNotIn、assertRegex、assertNotRegex、assertEqual 调用的直接实参里的字符串字面量，按 D7 固定规则分三类（先命中先算）；node 沙箱测试函数指调用了 ui_harness.run_js 的 test_ 函数。

### E1 每文件计数

| 文件 | 无障碍名称 | 文案 | 源码形状 | 合计 | node 沙箱测试函数数 |
|---|---|---|---|---|---|
| `local/tests/test_ui_conflict_cancel.py` | 6 | 40 | 61 | 107 | 26 |
| `local/tests/test_ui_contract_clock.py` | 0 | 42 | 21 | 63 | 11 |
| `local/tests/test_ui_contract_components.py` | 2 | 18 | 32 | 52 | 0 |
| `local/tests/test_ui_contract_feedback.py` | 0 | 28 | 32 | 60 | 11 |
| `local/tests/test_ui_contract_list.py` | 7 | 120 | 119 | 246 | 22 |
| `local/tests/test_ui_contract_login.py` | 0 | 93 | 79 | 172 | 18 |
| `local/tests/test_ui_contract_plan.py` | 2 | 161 | 188 | 351 | 29 |
| `local/tests/test_ui_contract_settings.py` | 2 | 149 | 139 | 290 | 19 |
| `local/tests/test_ui_contract_shell.py` | 2 | 122 | 115 | 239 | 14 |
| `local/tests/test_ui_contract_terms.py` | 2 | 172 | 184 | 358 | 37 |
| `local/tests/test_ui_contract_update.py` | 3 | 28 | 29 | 60 | 29 |
| `local/tests/test_ui_layers.py` | 0 | 0 | 0 | 0 | 0 |
| `local/tests/test_ui_main_window_list.py` | 4 | 35 | 28 | 67 | 17 |
| `local/tests/test_ui_main_window_plan.py` | 0 | 51 | 19 | 70 | 16 |
| `local/tests/test_ui_reliability.py` | 0 | 166 | 131 | 297 | 84 |
| `local/tests/test_ui_rewards.py` | 4 | 3 | 37 | 44 | 2 |
| `local/tests/test_phone_ui.py` | 2 | 403 | 257 | 662 | 0 |
| 合计 | 36 | 1631 | 1471 | 3138 | 335 |

自校：三类之和 3138 = 脚本找到的字面量断言总数 3138 -> 成立

### E2 三类抽样各 20 条（random.Random(20261113)，按 文件:行号+字面量 排序后抽样）

| 类别 | 文件:行号 | 原文 |
|---|---|---|
| 无障碍名称 | `local/tests/test_ui_contract_list.py:888` | `aria-selected="false">可报名` |
| 无障碍名称 | `local/tests/test_phone_ui.py:5347` | `id="offline-note" class="alert bad" role="alert"` |
| 无障碍名称 | `local/tests/test_ui_contract_components.py:32` | `id="phone-component-state" aria-live="polite"` |
| 无障碍名称 | `local/tests/test_ui_contract_terms.py:385` | `aria-label="关闭条款"` |
| 无障碍名称 | `local/tests/test_phone_ui.py:3258` | `点钮展开列表并随动 aria-expanded/文案` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:891` | `chip.setAttribute("aria-selected"` |
| 无障碍名称 | `local/tests/test_ui_conflict_cancel.py:104` | `aria-describedby="cx-tip"` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:904` | `aria-expanded="false"` |
| 无障碍名称 | `local/tests/test_ui_conflict_cancel.py:499` | `title="正在刷新，等它结束再取消"` |
| 无障碍名称 | `local/tests/test_ui_conflict_cancel.py:498` | `data-cancel="s1" disabled title="计划在运行，先停下来再取消"` |
| 无障碍名称 | `local/tests/test_ui_rewards.py:62` | `<span class="rw-i" title="实践分 2，虚拟工资 20">2 分 · 工资 20</span>` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:888` | `button 上的 aria-selected 非法，必须用 aria-pressed` |
| 无障碍名称 | `local/tests/test_ui_contract_update.py:451` | `role="progressbar"` |
| 无障碍名称 | `local/tests/test_ui_contract_plan.py:998` | `data-tone="ok"><i aria-hidden="true">✓</i>` |
| 无障碍名称 | `local/tests/test_ui_contract_update.py:452` | `aria-label="安装包下载进度"` |
| 无障碍名称 | `local/tests/test_ui_contract_settings.py:32` | `#tour-card 是 role=dialog 且 aria-labelledby=tour-title：标题静态不能为空，否则引导没开始前读屏只念「对话框」` |
| 无障碍名称 | `local/tests/test_ui_contract_components.py:33` | `id="phone-status" role="status"` |
| 无障碍名称 | `local/tests/test_ui_main_window_list.py:132` | `aria-expanded 跟展开状态` |
| 无障碍名称 | `local/tests/test_ui_contract_settings.py:466` | `role="dialog"` |
| 无障碍名称 | `local/tests/test_ui_contract_list.py:903` | `role="button"` |
| 文案 | `local/tests/test_phone_ui.py:5318` | `电脑上还没有同意使用条款` |
| 文案 | `local/tests/test_phone_ui.py:826` | `填写账号密码` |
| 文案 | `local/tests/test_phone_ui.py:3823` | `电脑正在自动重新登录。` |
| 文案 | `local/tests/test_ui_contract_plan.py:35` | `工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。` |
| 文案 | `local/tests/test_ui_contract_terms.py:1957` | `打开阅读器绝不保存` |
| 文案 | `local/tests/test_phone_ui.py:414` | `后台恢复必须按事件游标补齐，且只读、不重放写操作` |
| 文案 | `local/tests/test_ui_contract_settings.py:149` | `计划运行中必须暂停引导` |
| 文案 | `local/tests/test_phone_ui.py:1994` | `后端原话` |
| 文案 | `local/tests/test_ui_contract_shell.py:85` | `帮助标题描述用途，正式名称仍由窗口标题表达` |
| 文案 | `local/tests/test_phone_ui.py:3868` | `底栏计数随动` |
| 文案 | `local/tests/test_phone_ui.py:3105` | `等待开放` |
| 文案 | `local/tests/test_phone_ui.py:1624` | `「启用」不能再打开导入弹窗` |
| 文案 | `local/tests/test_ui_contract_plan.py:660` | `开放瞬间不得换锚` |
| 文案 | `local/tests/test_phone_ui.py:1713` | `导入链接打开的是验证码识别的导入` |
| 文案 | `local/tests/test_ui_contract_shell.py:685` | `要关闭窗口吗？` |
| 文案 | `local/tests/test_phone_ui.py:3183` | `工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。` |
| 文案 | `local/tests/test_ui_contract_terms.py:978` | `使用条款更新了` |
| 文案 | `local/tests/test_ui_contract_list.py:798` | `点重试不得顺手清筛选把错误藏掉` |
| 文案 | `local/tests/test_phone_ui.py:1010` | `已复制` |
| 文案 | `local/tests/test_ui_contract_list.py:745` | `检查没结束时不得提前宣布「登录是有效的」` |
| 源码形状 | `local/tests/test_ui_contract_components.py:179` | `cloudflared_missing` |
| 源码形状 | `local/tests/test_phone_ui.py:1124` | `下载没有完成：GitHub 暂时无法响应，请稍后重试，可以重试。` |
| 源码形状 | `local/tests/test_ui_conflict_cancel.py:226` | `` |
| 源码形状 | `local/tests/test_ui_contract_plan.py:630` | `partial` |
| 源码形状 | `local/tests/test_ui_reliability.py:55` | `unknown` |
| 源码形状 | `local/tests/test_phone_ui.py:744` | `还差一步：装好 Tailscale 后点“重新检测”，或者改用 Cloudflare。` |
| 源码形状 | `local/tests/test_ui_contract_shell.py:108` | `cy="9.5"` |
| 源码形状 | `local/tests/test_phone_ui.py:3133` | `ok` |
| 源码形状 | `local/tests/test_ui_contract_terms.py:125` | `'terms': terms_state(prefs)` |
| 源码形状 | `local/tests/test_ui_conflict_cancel.py:242` | `b1` |
| 源码形状 | `local/tests/test_phone_ui.py:4246` | `汇总行集与计数同一口径（不过段钮过滤，R-P3-7）` |
| 源码形状 | `local/tests/test_phone_ui.py:2854` | `原型 submitPair：失败清空重输` |
| 源码形状 | `local/tests/test_ui_contract_settings.py:105` | `340px` |
| 源码形状 | `local/tests/test_phone_ui.py:2897` | `归零只放开呈现层（输入不再禁用；空输入仍不可提交），服务端是唯一闸门；UI-F6（原型 lockLeft 归零清 pairErr）：旧错误条一并收回` |
| 源码形状 | `local/tests/test_ui_contract_terms.py:1114` | `提交的 documentVersion 必须等于可见内嵌版本节点` |
| 源码形状 | `local/tests/test_phone_ui.py:4795` | `id="btn-phone-feature-install"` |
| 源码形状 | `local/tests/test_ui_contract_update.py:128` | `launching` |
| 源码形状 | `local/tests/test_ui_contract_plan.py:59` | `停止确认不再是原生 dialog` |
| 源码形状 | `local/tests/test_phone_ui.py:1927` | `id="relogin-ocr-status"` |
| 源码形状 | `local/tests/test_ui_contract_plan.py:42` | `class="dlg sm"` |

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_assertions.py`

### 表 E 抽查记录（测试自动化工程师核对，主代理转录；返修后作者重出）

1. 复跑退出码 0；新 E1 合计 36/1631/1471/3138，较旧表文案 -27、源码形状 +27，无障碍名称与总数 3138 不变；E1 每行三类相加与合计列一致，自校行成立；原抽查 3 条样本（`local/tests/test_ui_contract_terms.py:385` 无障碍名称、`local/tests/test_ui_contract_list.py:793` 文案、`local/tests/test_phone_ui.py:1124` 源码形状）在新口径下类别均不变。
2. 新 E2 抽样核对一：`local/tests/test_ui_contract_plan.py:35` 行源码为 `self.assertIn("工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。", ask,`，与 E2 原文一致；类别：脚本 文案 / 按字面规则判 文案（规则一不命中，句读为标点去除后全为汉字）。
3. 新 E2 抽样核对二：`local/tests/test_phone_ui.py:5318` 行源码为 `self.assertEqual(r["locked"]["alertTitle"], "电脑上还没有同意使用条款")`，原文一致；类别：脚本 文案 / 判 文案。另核 `local/tests/test_phone_ui.py:4246`：该行是 assertEqual 调用首行，样本原文 `汇总行集与计数同一口径（不过段钮过滤，R-P3-7）` 实际在 4247 续行（行号取调用行，差 1，与 AA2 所记一致）；类别：脚本 源码形状 / 判 源码形状（含拉丁字母 R-P3-7，规则二不满足）。
4. 翻类项复核：`local/tests/test_ui_contract_settings.py:936` 行源码为 `self.assertNotIn("dlg-x", block, "帮助弹窗不得有 × 关闭按钮")`，× 为半角符号（U+00D7，Sm 类），按字面规则二不满足、应判 源码形状，与返修方向一致；自写探针按同法判 AA2 另一例 `1已报名|1名额已满|…`（| 为 Sm）亦为 源码形状。新 E2 的 20 条文案样本逐条目检均不含半角符号，与 -27 位移方向相符。

**表 E2：界面测试函数分类（本计划 decisions D7）**

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_test_kinds.py`

## 表 E2：界面测试函数分类（本计划 decisions D7）

量什么：表 E 的同一批 17 个文件（test_ui_*.py 加 test_phone_ui.py，清单与 ui_assertions.py 同一条规则）。ast 找「运行函数」：函数体（含嵌套 def）调用了 run_js，或函数源码段里同时出现 subprocess 和 node；再把调用了运行函数的函数也算作运行函数，反复到不再增加（按名字匹配，只看同一文件里定义的函数名）。每个 test_ 开头的函数：是运行函数记「跑 node」，其余记「不跑 node」。函数收集用 ast.walk（含类方法）。

| 文件 | 测试函数数 | 跑 node | 不跑 node |
|---|---|---|---|
| `local/tests/test_ui_conflict_cancel.py` | 30 | 26 | 4 |
| `local/tests/test_ui_contract_clock.py` | 12 | 11 | 1 |
| `local/tests/test_ui_contract_components.py` | 15 | 0 | 15 |
| `local/tests/test_ui_contract_feedback.py` | 19 | 11 | 8 |
| `local/tests/test_ui_contract_list.py` | 42 | 22 | 20 |
| `local/tests/test_ui_contract_login.py` | 35 | 18 | 17 |
| `local/tests/test_ui_contract_plan.py` | 55 | 39 | 16 |
| `local/tests/test_ui_contract_settings.py` | 45 | 19 | 26 |
| `local/tests/test_ui_contract_shell.py` | 39 | 14 | 25 |
| `local/tests/test_ui_contract_terms.py` | 73 | 37 | 36 |
| `local/tests/test_ui_contract_update.py` | 30 | 29 | 1 |
| `local/tests/test_ui_layers.py` | 4 | 2 | 2 |
| `local/tests/test_ui_main_window_list.py` | 19 | 17 | 2 |
| `local/tests/test_ui_main_window_plan.py` | 19 | 16 | 3 |
| `local/tests/test_ui_reliability.py` | 95 | 94 | 1 |
| `local/tests/test_ui_rewards.py` | 6 | 2 | 4 |
| `local/tests/test_phone_ui.py` | 210 | 195 | 15 |
| 合计 | 748 | 552 | 196 |

自校：跑 node + 不跑 node = 测试函数数（552 + 196 = 748）-> 成立
对照：计划 decisions D7 参照数 合计 748、552、196，test_phone_ui.py 210、195、15，test_ui_contract_components.py 15、0、15；本次 合计 748、552、196，test_phone_ui.py 210、195、15，test_ui_contract_components.py 15、0、15 -> 逐项一致

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_test_kinds.py`

**表 F：工程设施盘点（D8）**

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py`（表 F 与表 G 由这一条命令一次跑出）

## 表 F：工程设施盘点

量什么：只查「有没有」。配置文件给路径或「无」；requirements 文件给行数与未锁到精确版本（没有 ==）的行数与行；.githooks、.github/workflows 给文件名；release.py 的 --prepare 与单元测试、ruff 的出现位置按字符串查找给 文件:行号。

### F1 配置文件有没有

| 项目 | 结果 |
|---|---|
| mypy.ini | 无 |
| .mypy.ini | 无 |
| .coveragerc | 无 |
| .eslintrc.js | 无 |
| .eslintrc.cjs | 无 |
| .eslintrc.json | 无 |
| .eslintrc.yml | 无 |
| .eslintrc.yaml | 无 |
| .eslintrc | 无 |
| eslint.config.js | 无 |
| eslint.config.cjs | 无 |
| eslint.config.mjs | 无 |
| .prettierrc | 无 |
| .prettierrc.json | 无 |
| .prettierrc.yml | 无 |
| .prettierrc.yaml | 无 |
| .prettierrc.js | 无 |
| .prettierrc.cjs | 无 |
| .prettierrc.toml | 无 |
| prettier.config.js | 无 |
| prettier.config.cjs | 无 |
| pyproject.toml | 无 |
| setup.cfg | 无 |
| package.json | 无 |
| .editorconfig | 无 |
| .pre-commit-config.yaml | 无 |
| mypy 配置节（pyproject.toml / setup.cfg 内 [tool.mypy]） | 无 |
| coverage 配置节（pyproject.toml / setup.cfg 内 [tool.coverage]） | 无 |

### F2 requirements 文件

| 文件 | 总行数 | 非注释非空行数 | 未锁精确版本行数 | 未锁的行 |
|---|---|---|---|---|
| `local/requirements-advanced-ocr.txt` | 3 | 3 | 3 | `ddddocr>=1.6.1`；`onnxruntime>=1.17`；`pyinstaller>=6.0` |
| `local/requirements-advanced-phone.txt` | 2 | 2 | 2 | `segno>=1.6`；`pyinstaller>=6.0` |
| `local/requirements.txt` | 14 | 7 | 2 | `playwright>=1.40`；`pillow>=9.0` |
| `requirements-dev.txt` | 3 | 1 | 0 | — |
| `server/requirements.txt` | 15 | 2 | 2 | `playwright>=1.40`；`ddddocr>=1.6.1` |

### F3 hooks 与 CI

| .githooks 下的文件名 | 无 |
| .github/workflows 下的文件名 | 无 |

### F4 release.py 与测试、code_shape、ruff

tools/release.py 里含 unittest / pytest / compileall 的行（判断 --prepare 路径有没有调用单元测试就看这些行落在哪个分支）：
- 无

tools/release.py 里含 --prepare 的行：
- tools/release.py:8
- tools/release.py:17
- tools/release.py:27
- tools/release.py:660
- tools/release.py:803
- tools/release.py:809
- tools/release.py:933
- tools/release.py:941
- tools/release.py:946
- tools/release.py:948
- tools/release.py:951
- tools/release.py:957
- tools/release.py:961
- tools/release.py:968
- tools/release.py:988
- tools/release.py:993
- tools/release.py:1000
- tools/release.py:1046
- tools/release.py:1059
- tools/release.py:1269
- tools/release.py:1292
- tools/release.py:1302

tools/code_shape/check.py 存在：是（tools/code_shape/check.py）

ruff 按字符串查找（git 已跟踪的文本文件，大小写不敏感），共 21 行：
- AGENTS.md:112
- AGENTS.md:115
- AGENTS.md:224
- AGENTS.md:227
- design/proposals/engineering-refactor.md:67
- design/proposals/engineering-refactor.md:74
- local/tests/test_code_shape.py:228
- local/tests/test_code_shape.py:229
- local/tests/test_code_shape.py:233
- local/tests/test_code_shape.py:234
- local/tests/test_code_shape.py:244
- local/tests/test_code_shape.py:249
- local/tests/test_code_shape.py:250
- local/tests/test_code_shape.py:255
- local/tests/test_code_shape.py:256
- local/tests/test_code_shape.py:257
- local/tests/test_code_shape.py:262
- local/tests/test_code_shape.py:270
- requirements-dev.txt:3
- ruff.toml:1
- ruff.toml:3

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py`


### 表 F 抽查记录（技术文档工程师核对，主代理转录）

1. F1 抽查 5 行（pyproject.toml、setup.cfg、package.json、.editorconfig、.pre-commit-config.yaml）：test -e 逐个检测全部不存在，与表中「无」一致。
2. F2 抽查 `local/requirements.txt`：`grep -c ''` 计 14 行；`grep -v '^[[:space:]]*#'` 再滤空行计 7 行非注释非空；对结果再 `grep -v '=='` 恰剩 `playwright>=1.40`、`pillow>=9.0` 两行，与表中 14/7/2 及未锁行列一致。
3. ruff 字符串查找抽查 AGENTS.md：`grep -ni ruff AGENTS.md` 命中第 112、115、224、227 行，与表列 AGENTS.md:112/115/224/227 一致。
4. ruff 字符串查找抽查 requirements-dev.txt：`grep -ni ruff requirements-dev.txt` 命中第 3 行（内容 `ruff==0.17.5`），与表列 requirements-dev.txt:3 一致。

**表 G：文档数字对账（D9）**

复跑命令：同表 F；实测值复跑用表内「量法」列。

## 表 G：文档数字对账

量什么：AGENTS.md、README.md、local/README.md、docs/ 下的 md 文件里，写了具体数字的四类句子（正则见脚本顶部）：测试用例个数（3 位以上数字+例/用例）、Api 方法个数（同一句含 Api）、决策记录篇数（数字+篇）、某个源文件的行数（3 位以上数字+行，且句里有 .py/.js/.mjs 文件名；「第 N 行」「文件:行号」式引用排除）。原文含主机路径时替换为 <主机路径> 并标注，其余字符不动。

| 文件:行号 | 类别 | 原文 | 实测值 | 量法 |
|---|---|---|---|---|
| `AGENTS.md:91` | 测试用例个数 | # 本机版全量，约 1700 例；仓库在共享盘上，要跑几分钟 | local/tests 2581；server/tests 123；合计 2704 | `python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py --measure tests` |
| `docs/ARCHITECTURE.md:179` | Api 方法个数 | \| interface \| `app.py` \| Api 49 个公开方法、条款门禁、事件发射、worker 命令装配、main；composition root：向 domain/application 注入 signup_plan 纯函数、time_contract 换算、business_clock 异常类型 \| pywebview / 测试 \| 全部下层（裸名注入缝保持 app.X 可替换） \| | 总数 153；非下划线 60 | `python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py --measure api` |
| `docs/UI_SPEC.md:884` | 测试用例个数 | > 历史截图与「385 例」等测试总数只描述当时那一轮，不作为本轮证据。 | local/tests 2581；server/tests 123；合计 2704 | `python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py --measure tests` |

### 已排除：位置引用

量什么：docs/superpowers/specs/2026-11-03-architecture-revision-design.md 第 39、121、194 行里的「约 N 行」指「这个函数或常量在文件的第几行附近」，是位置引用，不是「这个文件有多少行」，按计划 plan-20261114-refactor-endpoint-evidence-fix 的 decisions D2，这三行不属于 D9 的四类句子。第 39、121 行原先被行数正则命中、在正表里，本节把它们移出正表；第 194 行的「约 61 行」低于三位数下限，原本就未进正表，也列入本节备查。行数正则（含三位数下限）照旧未改；排除清单写在脚本顶部注释。

| 文件:行号 | 类别 | 原文 | 排除理由 |
|---|---|---|---|
| `docs/superpowers/specs/2026-11-03-architecture-revision-design.md:39` | 位置引用 | - 现在的开关 `_detect_direct_signer`（`local/grab.py` 约 2176 行）只比对 `KNOWN_DIRECT_SCRIPT_BASENAME`（57 行）。学校换文件名后，它返回 `None`，静默走点击。 | 「约 N 行」指函数或常量在文件中的位置，不是文件总行数，不属于 D9 的四类句子 |
| `docs/superpowers/specs/2026-11-03-architecture-revision-design.md:121` | 位置引用 | - 现在 `_auto_relogin_eligible`（`local/app.py` 约 1364 行）在计划运行时排除自动登录，要放开。 | 「约 N 行」指函数或常量在文件中的位置，不是文件总行数，不属于 D9 的四类句子 |
| `docs/superpowers/specs/2026-11-03-architecture-revision-design.md:194` | 位置引用 | - **另外两个静态值**：`REQUEST_SECURITY_RAW_KEY` 和 `REQUEST_SECURITY_CLIENT_KEY`（`local/grab.py` 约 61 行）也是从学校页面脚本里摘出来的，现在只有 `_post` 用它们算签名头，而 server 不带签名头的 POST 一直正常。先核实登录接口需不需要签名头：不需要就删掉 `sign_request_headers` 和这两个值；需要就改成构建时注入。 | 「约 N 行」指函数或常量在文件中的位置，不是文件总行数，不属于 D9 的四类句子 |

复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/facilities.py` （表 G 段）；实测值复跑用上表「量法」列。

### 表 G 抽查记录（技术文档工程师核对，主代理转录）

1. AGENTS.md:91 与 docs/UI_SPEC.md:884 两行：用 Python repr 对原文件该行逐字符比对，与「原文」列逐字一致，无前导空白或其他空格差异。
2. docs/superpowers/specs/2026-11-03-architecture-revision-design.md:121：原文件该行开头有两个空格（`  - 现在 …`），「原文」列未含这两个前导空格（脚本打印前对行做了 strip），其余字符逐字一致。
3. docs/ARCHITECTURE.md:179：原文件该行与「原文」列逐字一致，唯一差别是原文中的 `|` 在表中写作 `\|`（脚本为防破坏表格做的转义），无其他差异。
4. 复跑「量法」列命令（`--measure tests`）：输出 `local/tests 2581；server/tests 123；合计 2704`，与 AGENTS.md:91 及 docs/UI_SPEC.md:884 两行的「实测值」一致。
