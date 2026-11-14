## review2 表 A 独立复算

| 归属 | 项数 |
|---|---|
| 步骤 1A | 10 |
| 步骤 1B | 16 |
| 步骤 1C | 18 |
| 步骤 1 共用 | 6 |
| 步骤 2 | 17 |
| 步骤 3 | 13 |
| 手机页 | 9 |
| 未排进任何一步 | 165 |
| 合计 | 254 |

名单构成：baseline 167（文件 25+函数 119+测试函数 19+类 4）+ 白名单 41 + 分层例外 2 + ruff 44 = 254

自校：各步项数 89 + 未排进项数 165 = 总项数 254 -> 成立

### 未排进清单（独立重算）

| 来源 | 条目 | 当前值 |
|---|---|---|
| baseline文件(over800) | `local/business_clock.py` | 875 |
| baseline文件(over800) | `local/infrastructure/component_packages.py` | 1666 |
| baseline文件(over800) | `server/bot/bot.js` | 977 |
| baseline文件(over800) | `server/deploy/auto_login.py` | 824 |
| baseline文件(over800) | `server/deploy/grab_signup.py` | 819 |
| baseline文件(over800) | `tools/qa_runtime_reliability.py` | 3311 |
| baseline文件(over800) | `tools/release.py` | 1321 |
| baseline文件(over500) | `local/application/advanced_component_service.py` | 503 |
| baseline文件(over500) | `local/application/login_relay_service.py` | 551 |
| baseline文件(over500) | `local/build/build_installer.py` | 518 |
| baseline文件(over500) | `local/login_relay.py` | 717 |
| baseline文件(over500) | `local/signup_plan.py` | 614 |
| baseline文件(over500) | `local/ui/views/terms.js` | 507 |
| baseline文件(over500) | `local/update_check.py` | 548 |
| baseline文件(over500) | `server/scripts/activity_watch.py` | 524 |
| baseline文件(over500) | `server/scripts/notify.py` | 515 |
| baseline函数(over100) | `local/application/advanced_component_service.py::AdvancedComponentService._run_split_assets` | 101 |
| baseline函数(over100) | `local/application/login_relay_service.py::LoginRelayService._handle_line` | 103 |
| baseline函数(over100) | `local/application/plan_service.py::run_plan_task` | 361 |
| baseline函数(over100) | `local/application/update_service.py::run_version_download` | 151 |
| baseline函数(over100) | `local/infrastructure/phone_http.py::_make_handler` | 261 |
| baseline函数(over100) | `local/signup_plan.py::validate_plan` | 117 |
| baseline函数(over100) | `local/ui/controllers/terms.js::acceptTerms` | 108 |
| baseline函数(over100) | `local/ui/led.js::#anon1` | 108 |
| baseline函数(over100) | `local/ui/views/update.js::paintUpdate` | 146 |
| baseline函数(over100) | `server/bot/bot.js::#anon12` | 186 |
| baseline函数(over100) | `server/deploy/auto_login.py::main` | 123 |
| baseline函数(over100) | `server/deploy/grab_signup.py::run_submit_loop` | 343 |
| baseline函数(over100) | `server/scripts/fetch.py::main` | 109 |
| baseline函数(over100) | `server/scripts/run.py::main` | 144 |
| baseline函数(over100) | `tools/qa_runtime_reliability.py::_#22` | 130 |
| baseline函数(over100) | `tools/release.py::stage_local_assets` | 140 |
| baseline函数(over100) | `tools/release.py::verify_release_assets` | 125 |
| baseline函数(over60) | `local/application/advanced_component_service.py::AdvancedComponentService._run` | 92 |
| baseline函数(over60) | `local/application/auto_relogin.py::AutoReloginMonitor.tick` | 90 |
| baseline函数(over60) | `local/application/login_relay_service.py::LoginRelayService.begin` | 85 |
| baseline函数(over60) | `local/application/plan_service.py::run_plan_task.feed` | 77 |
| baseline函数(over60) | `local/build/build_advanced.py::_build_legacy` | 76 |
| baseline函数(over60) | `local/business_clock.py::BusinessClock._accept_cluster` | 72 |
| baseline函数(over60) | `local/domain/demo_data.py::demo_items` | 79 |
| baseline函数(over60) | `local/domain/phone_rules.py::normalize_action` | 76 |
| baseline函数(over60) | `local/domain/plan_rules.py::classify_task_stop` | 63 |
| baseline函数(over60) | `local/infrastructure/component_packages.py::_helper` | 61 |
| baseline函数(over60) | `local/infrastructure/component_packages.py::install` | 72 |
| baseline函数(over60) | `local/infrastructure/component_packages.py::install_artifact` | 64 |
| baseline函数(over60) | `local/infrastructure/tray_icon.py::TrayIcon._run` | 73 |
| baseline函数(over60) | `local/infrastructure/tunnel_manager.py::CloudflareTunnel.start` | 84 |
| baseline函数(over60) | `local/runtime_paths.py::_migrate_legacy_data` | 86 |
| baseline函数(over60) | `local/signup_plan.py::PlanCoordinator._run` | 66 |
| baseline函数(over60) | `local/signup_signing.py::_encrypt_block_cng` | 100 |
| baseline函数(over60) | `local/ui/controllers/terms.js::acceptTerms.#anon1` | 64 |
| baseline函数(over60) | `local/ui/controllers/terms.js::recheckTerms` | 63 |
| baseline函数(over60) | `local/ui/controllers/tick.js::tick` | 88 |
| baseline函数(over60) | `local/ui/state/clock.js::ingestBusinessClock` | 80 |
| baseline函数(over60) | `local/ui/views/clock-pop.js::renderClockPop` | 76 |
| baseline函数(over60) | `local/ui/views/list.js::paintEmpty` | 95 |
| baseline函数(over60) | `local/ui/views/list.js::rowHtml` | 68 |
| baseline函数(over60) | `local/ui/views/terms.js::applyTermsFooter` | 77 |
| baseline函数(over60) | `local/update_delta.py::apply_delta` | 70 |
| baseline函数(over60) | `local/update_launcher.py::apply_staged` | 76 |
| baseline函数(over60) | `local/updater.py::download_installer` | 88 |
| baseline函数(over60) | `server/bot/bot.js::handleCardAction` | 66 |
| baseline函数(over60) | `server/bot/bot.js::handleGrabAction` | 63 |
| baseline函数(over60) | `server/bot/bot.js::handleMessage` | 74 |
| baseline函数(over60) | `server/deploy/auto_login.py::_submit_once` | 99 |
| baseline函数(over60) | `server/deploy/grab_signup.py::main` | 66 |
| baseline函数(over60) | `server/deploy/server_refresh.js::runDaemon` | 80 |
| baseline函数(over60) | `server/scripts/activity_watch.py::_run_once` | 71 |
| baseline函数(over60) | `server/scripts/activity_watch.py::compute_events` | 85 |
| baseline函数(over60) | `server/scripts/dev/explore.py::main` | 63 |
| baseline函数(over60) | `server/scripts/query.py::main` | 71 |
| baseline函数(over60) | `server/scripts/regress.py::main` | 76 |
| baseline函数(over60) | `server/scripts/scan.py::_scan` | 81 |
| baseline函数(over60) | `server/scripts/token_probe.py::main` | 69 |
| baseline函数(over60) | `server/scripts/watchlist_runner.py::main` | 76 |
| baseline函数(over60) | `tools/qa_business_clock_worker.py::run_probe` | 99 |
| baseline函数(over60) | `tools/qa_runtime_reliability.py::_#20` | 75 |
| baseline函数(over60) | `tools/qa_runtime_reliability.py::_#62` | 69 |
| baseline函数(over60) | `tools/qa_runtime_reliability.py::_#63` | 61 |
| baseline函数(over60) | `tools/qa_runtime_reliability.py::_#7` | 81 |
| baseline函数(over60) | `tools/qa_runtime_reliability.py::_narrow` | 75 |
| baseline函数(over60) | `tools/qa_runtime_reliability.py::run_scenarios` | 75 |
| baseline函数(over60) | `tools/release.py::write_manifest` | 75 |
| baseline函数(over60) | `tools/verify_autologin_loop.py::main` | 87 |
| baseline测试函数 | `local/tests/test_lifecycle_release.py::AssetVerificationTests.test_verify_rejects_each_bad_candidate` | 92 |
| baseline测试函数 | `local/tests/test_phone_ui.py::ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` | 71 |
| baseline测试函数 | `local/tests/test_phone_ui.py::ResultTermsModelTests.test_result_view_counts_and_heads_follow_prototype` | 84 |
| baseline测试函数 | `local/tests/test_phone_ui.py::RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` | 65 |
| baseline测试函数 | `local/tests/test_phone_ui.py::RunWaitModelTests.test_task_card_follows_prototype_detail_priority` | 72 |
| baseline测试函数 | `local/tests/test_phone_ui.py::WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` | 67 |
| baseline测试函数 | `local/tests/test_retry_phone_integration.py::FullChainTests.test_pair_read_start_extend_stop_relogin_chain` | 66 |
| baseline测试函数 | `local/tests/test_ui_contract_list.py::TimetableGroupingBehaviorTests.test_group_timetable_places_each_activity_in_its_correct_group` | 106 |
| baseline测试函数 | `local/tests/test_ui_contract_shell.py::WorkbenchUiContractTests.test_close_dialog_three_exits` | 138 |
| baseline测试函数 | `local/tests/test_ui_contract_shell.py::WorkbenchUiContractTests.test_five_pre_start_warnings_only_remind` | 61 |
| baseline测试函数 | `local/tests/test_ui_contract_terms.py::TermsConsentBehaviorTests.test_decline_does_not_reprompt_and_keeps_help_available` | 62 |
| baseline测试函数 | `local/tests/test_ui_contract_terms.py::TermsConsentBehaviorTests.test_unknown_terms_accept_rejects_bad_receipts` | 68 |
| baseline测试函数 | `local/tests/test_ui_contract_terms.py::TermsConsentContractTests.test_accept_terms_writes_prefs_transaction_only` | 77 |
| baseline测试函数 | `local/tests/test_ui_contract_terms.py::TermsConsentContractTests.test_terms_dialog_structure_contract` | 127 |
| baseline测试函数 | `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_boot_defers_intro_until_terms_accepted` | 69 |
| baseline测试函数 | `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_close_restores_banner_focus_without_stacking_dialogs` | 62 |
| baseline测试函数 | `local/tests/test_ui_contract_terms.py::TermsInteractionLoopTests.test_save_timeout_keeps_gate_reopens_close_and_drops_late_receipt` | 64 |
| baseline测试函数 | `local/tests/test_ui_contract_update.py::UpdateBoardPaintTests.test_one_primary_action_per_state` | 75 |
| baseline测试函数 | `local/tests/test_worker_boundaries.py::ListEntryTests.test_cmd_list_without_clock_keeps_full_enrich` | 63 |
| baseline类 | `local/application/advanced_component_service.py::AdvancedComponentService` | 8 |
| baseline类 | `local/application/auto_relogin.py::AutoReloginMonitor` | 8 |
| baseline类 | `local/application/phone_service.py::PhoneAccessService` | 12 |
| 前端白名单 | `local/ui/state/clock.js × paintClockPopFeedback` | 314 |
| 前端白名单 | `local/ui/state/clock.js × paintClockStatus` | 314 |
| 前端白名单 | `local/ui/state/clock.js × render` | 314 |
| 前端白名单 | `local/ui/state/clock.js × renderClockPop` | 314 |
| 前端白名单 | `local/ui/state/clock.js × updateControls` | 314 |
| 前端白名单 | `local/ui/state/filters.js × render` | 393 |
| 前端白名单 | `local/ui/state/filters.js × setResult` | 393 |
| 前端白名单 | `local/ui/views/clock-pop.js × resyncClock` | 152 |
| 前端白名单 | `local/ui/views/conflict-tip.js × savePrefs` | 147 |
| 前端白名单 | `local/ui/views/help.js × savePrefs` | 67 |
| 前端白名单 | `local/ui/views/list.js × listErrorCopy` | 449 |
| 前端白名单 | `local/ui/views/list.js × tick` | 449 |
| 前端白名单 | `local/ui/views/log.js × savePrefs` | 29 |
| 前端白名单 | `local/ui/views/selection.js × savePrefs` | 90 |
| 前端白名单 | `local/ui/views/tour.js × savePrefsNow` | 174 |
| 分层例外 | `local/application/advanced_component_service.py import infrastructure.component_packages` | 503 |
| 分层例外 | `local/infrastructure/component_packages.py import runtime_paths` | 1666 |
| ruff | `local/advanced_helper.py × F401` | F401 |
| ruff | `local/application/advanced_component_service.py × F401` | F401 |
| ruff | `local/application/login_relay_service.py × F401` | F401 |
| ruff | `local/application/phone_service.py × F401` | F401 |
| ruff | `local/build/build_installer.py × F401` | F401 |
| ruff | `local/infrastructure/credential_store.py × F841` | F841 |
| ruff | `local/infrastructure/lifecycle_store.py × F841` | F841 |
| ruff | `local/signup_plan.py × F401` | F401 |
| ruff | `local/tests/test_advanced_features.py × F401` | F401 |
| ruff | `local/tests/test_auto_relogin.py × F401` | F401 |
| ruff | `local/tests/test_business_clock.py × F401` | F401 |
| ruff | `local/tests/test_business_clock_wiring.py × F401` | F401 |
| ruff | `local/tests/test_cancel_signup.py × F401` | F401 |
| ruff | `local/tests/test_lifecycle_release.py × F841` | F841 |
| ruff | `local/tests/test_login_relay.py × F401` | F401 |
| ruff | `local/tests/test_login_relay_service.py × F401` | F401 |
| ruff | `local/tests/test_network_policy.py × F401` | F401 |
| ruff | `local/tests/test_phone_http.py × F401` | F401 |
| ruff | `local/tests/test_phone_http.py × F841` | F841 |
| ruff | `local/tests/test_phone_service.py × F401` | F401 |
| ruff | `local/tests/test_phone_service.py × F841` | F841 |
| ruff | `local/tests/test_release_audit.py × F401` | F401 |
| ruff | `local/tests/test_retry_phone_policy.py × F401` | F401 |
| ruff | `local/tests/test_retry_policy.py × F841` | F841 |
| ruff | `local/tests/test_session_persistence.py × F401` | F401 |
| ruff | `local/tests/test_session_persistence.py × F823` | F823 |
| ruff | `local/tests/test_signup_plan.py × F841` | F841 |
| ruff | `local/tests/test_time_contract.py × F401` | F401 |
| ruff | `local/tests/test_ui_contract_settings.py × F401` | F401 |
| ruff | `local/tests/test_ui_contract_shell.py × F401` | F401 |
| ruff | `local/tests/test_updater.py × F811` | F811 |
| ruff | `local/tests/test_worker_boundaries.py × F841` | F841 |
| ruff | `server/deploy/auto_login.py × F401` | F401 |
| ruff | `server/deploy/grab_signup.py × F401` | F401 |
| ruff | `server/scripts/common.py × F401` | F401 |
| ruff | `server/scripts/dev/explore.py × F401` | F401 |
| ruff | `server/scripts/fetch.py × F541` | F541 |
| ruff | `server/scripts/token_probe.py × F841` | F841 |
| ruff | `server/scripts/token_report.py × F841` | F841 |
| ruff | `tools/qa_business_clock_worker.py × F401` | F401 |
| ruff | `tools/qa_runtime_reliability.py × F841` | F841 |
| ruff | `tools/split_branches.py × F401` | F401 |
未排进共 165 项。

### 排进了的项（独立重算，按步分组）

**步骤 1A（10 项）**
- baseline文件(over800) `local/ui/views/phone.js` 记录 1252 当前 1252
- baseline函数(over100) `local/ui/views/phone.js::paintPhoneAccess` 记录 262 当前 262
- baseline函数(over100) `local/ui/views/settings.js::paintOcrDownload` 记录 119 当前 119
- baseline函数(over60) `local/ui/views/phone.js::paintRelogin` 记录 88 当前 88
- baseline函数(over60) `local/ui/views/phone.js::wire` 记录 65 当前 65
- 白名单 `local/ui/views/phone.js × api` 当前行数 1252
- 白名单 `local/ui/views/phone.js × refresh` 当前行数 1252
- 白名单 `local/ui/views/settings.js × api` 当前行数 397
- 白名单 `local/ui/views/settings.js × ingestTerms` 当前行数 397
- 白名单 `local/ui/views/settings.js × savePrefs` 当前行数 397

**步骤 1B（16 项）**
- baseline文件(over500) `local/ui/views/relogin.js` 记录 555 当前 555
- baseline函数(over100) `local/ui/views/login.js::paintLogin` 记录 103 当前 103
- baseline函数(over60) `local/ui/views/relogin.js::receiveReloginState` 记录 63 当前 63
- 白名单 `local/ui/state/login.js × paintBoardActions` 当前行数 141
- 白名单 `local/ui/state/login.js × paintClockStatus` 当前行数 141
- 白名单 `local/ui/state/login.js × paintLogin` 当前行数 141
- 白名单 `local/ui/state/login.js × paintRail` 当前行数 141
- 白名单 `local/ui/state/login.js × paintSelected` 当前行数 141
- 白名单 `local/ui/state/login.js × refreshLoginEmptyState` 当前行数 141
- 白名单 `local/ui/state/login.js × reloginAutoLive` 当前行数 141
- 白名单 `local/ui/state/login.js × render` 当前行数 141
- 白名单 `local/ui/views/relogin.js × api` 当前行数 555
- 白名单 `local/ui/views/relogin.js × doCheck` 当前行数 555
- 白名单 `local/ui/views/relogin.js × doLogin` 当前行数 555
- 白名单 `local/ui/views/relogin.js × refresh` 当前行数 555
- 白名单 `local/ui/views/status-cards.js × doCheck` 当前行数 204

**步骤 1C（18 项）**
- baseline文件(over800) `local/ui/views/plan-panel.js` 记录 1367 当前 1367
- baseline文件(over500) `local/ui/controllers/plan.js` 记录 532 当前 532
- baseline函数(over100) `local/ui/controllers/plan.js::startPlan` 记录 117 当前 117
- baseline函数(over100) `local/ui/views/plan-panel.js::paintLed` 记录 116 当前 116
- baseline函数(over100) `local/ui/views/plan-panel.js::paintSelected` 记录 124 当前 124
- baseline函数(over60) `local/ui/controllers/plan.js::reconcileStart` 记录 75 当前 75
- baseline函数(over60) `local/ui/controllers/plan.js::startPlan.#anon1` 记录 64 当前 64
- baseline函数(over60) `local/ui/views/plan-panel.js::paintBanners` 记录 95 当前 95
- baseline函数(over60) `local/ui/views/plan-panel.js::paintRunPanel` 记录 71 当前 71
- baseline函数(over60) `local/ui/views/plan-panel.js::updateControls` 记录 70 当前 70
- 白名单 `local/ui/state/plan.js × noteSignedTasks` 当前行数 175
- 白名单 `local/ui/state/plan.js × noteStartedFromPhone` 当前行数 175
- 白名单 `local/ui/state/plan.js × render` 当前行数 175
- 白名单 `local/ui/state/plan.js × scheduleSignedRefresh` 当前行数 175
- 白名单 `local/ui/state/plan.js × setBusy` 当前行数 175
- 白名单 `local/ui/state/plan.js × showTaskResult` 当前行数 175
- 白名单 `local/ui/views/plan-panel.js × refresh` 当前行数 1367
- 白名单 `local/ui/views/plan-panel.js × runtimeErrorCopy` 当前行数 1367

**步骤 1 共用（6 项）**
- baseline文件(over500) `local/ui/app.js` 记录 655 当前 655
- baseline文件(over500) `local/ui/controllers/refresh.js` 记录 614 当前 614
- baseline函数(over100) `local/ui/controllers/refresh.js::refresh` 记录 123 当前 123
- baseline函数(over100) `local/ui/controllers/refresh.js::settleSynchronous` 记录 108 当前 108
- baseline函数(over60) `local/ui/app.js::#anon52` 记录 62 当前 62
- baseline函数(over60) `local/ui/app.js::boot` 记录 77 当前 77

**步骤 2（16 项）**
- baseline文件(over800) `local/app.py` 记录 4873 当前 4873
- baseline函数(over100) `local/app.py::Api.__init__` 记录 167 当前 167
- baseline函数(over100) `local/app.py::Api._start_plan_inner` 记录 239 当前 239
- baseline函数(over60) `local/app.py::Api._do_check_inner` 记录 61 当前 61
- baseline函数(over60) `local/app.py::Api._do_list_inner` 记录 81 当前 81
- baseline函数(over60) `local/app.py::Api._phone_raw_state` 记录 64 当前 64
- baseline函数(over60) `local/app.py::Api._start_phone_access` 记录 66 当前 66
- baseline函数(over60) `local/app.py::Api._start_plan_inner.emit` 记录 61 当前 61
- baseline函数(over60) `local/app.py::Api.advanced_features_state` 记录 80 当前 80
- baseline函数(over60) `local/app.py::Api.bootstrap` 记录 62 当前 62
- baseline函数(over60) `local/app.py::Api.shutdown` 记录 99 当前 99
- baseline函数(over60) `local/app.py::Api.start_plan` 记录 70 当前 70
- baseline函数(over60) `local/app.py::Api.update_launch` 记录 73 当前 73
- baseline函数(over60) `local/app.py::_runtime_check_main` 记录 61 当前 61
- baseline函数(over60) `local/app.py::main` 记录 100 当前 100
- baseline类 `local/app.py::Api` 记录 23 当前 23

**步骤 3（12 项）**
- baseline文件(over800) `local/grab.py` 记录 4076 当前 4076
- baseline函数(over100) `local/grab.py::cmd_grab` 记录 1467 当前 1467
- baseline函数(over100) `local/grab.py::cmd_grab._settle_direct_event` 记录 114 当前 114
- baseline函数(over100) `local/grab.py::cmd_list` 记录 143 当前 143
- baseline函数(over60) `local/grab.py::clock_sample` 记录 61 当前 61
- baseline函数(over60) `local/grab.py::cmd_grab._apply_conclusion` 记录 74 当前 74
- baseline函数(over60) `local/grab.py::cmd_grab._finalize_once` 记录 80 当前 80
- baseline函数(over60) `local/grab.py::cmd_grab._try_direct_fire` 记录 62 当前 62
- baseline函数(over60) `local/grab.py::cmd_grab.terminal` 记录 75 当前 75
- baseline函数(over60) `local/grab.py::cmd_login` 记录 77 当前 77
- baseline函数(over60) `local/grab.py::main` 记录 76 当前 76
- baseline函数(over60) `local/grab.py::run_cancel` 记录 76 当前 76

**手机页（9 项）**
- baseline文件(over800) `local/ui/m/app.js` 记录 3365 当前 3365
- baseline函数(over100) `local/ui/m/app.js::buildRow` 记录 102 当前 102
- baseline函数(over100) `local/ui/m/app.js::ingest` 记录 101 当前 101
- baseline函数(over100) `local/ui/m/app.js::wire` 记录 163 当前 163
- baseline函数(over60) `local/ui/m/app.js::buildWhy` 记录 85 当前 85
- baseline函数(over60) `local/ui/m/app.js::ingestRelogin` 记录 90 当前 90
- baseline函数(over60) `local/ui/m/app.js::reloginView` 记录 88 当前 88
- baseline函数(over60) `local/ui/m/app.js::renderBoard` 记录 65 当前 65
- baseline函数(over60) `local/ui/m/app.js::renderItems` 记录 97 当前 97


## 复核说明（代码审查员，全量核）

- baseline.json 逐键重数 25+119+19+4=167、ui_layer_allow.json 逐「文件×名字」重数 41、LEGACY 逐键 2、ruff.toml 逐「文件×规则码」44，与脚本一致；未排进 165 项集合差集双向为空；自校独立重算 89+165=254 成立；当前值抽核 3 条（phone.js 1252、Api.shutdown 99、paintSelected 124）一致。
- 口径注：明细段「步骤 2（16 项）/步骤 3（12 项）」只列 baseline 与白名单两类行，归入这两步的 ruff 项各 1 条只计入汇总；汇总口径本身正确。D2 文件中 plan-events.js、task-display.js、store.js 在四份名单里没有任何条目（0 项）。
