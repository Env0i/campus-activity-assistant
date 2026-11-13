# 清点结果（inventory）

- **基线提交**：`7e2d31c`。所有行号以它为准。
- **执行日期**：2026-11-12（北京时间）。
- **性质**：只有脚本数出来的事实，不下判断。判断在 `code-issues.md` 和 `ui-states.md`。
- **口径**：见 `README.md`。每一节开头给了复跑命令，都从仓库根执行。
- **本文件怎么来的**：`py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/build_inventory.py` 的标准输出，原样保存。复跑后逐字相同才算一致。

## 读数前要知道的

1. **「产品」两个字只表示「不是测试」**。`tools/` 下的发版和 QA 脚本、`local/build/` 下的打包脚本、`server/scripts/dev/` 都算在「产品 Python」里。定大小参考值时主要看「本机版 Python」和「本机版前端」两行。
2. **函数行数是物理行**，含空行、注释和文档字符串；嵌套函数既单独算，也计入外层。
3. **JS 的表达式体箭头函数没有计入**，所以 JS 的 P50 偏大；带花括号体的回调（`forEach(x => { … })`）计入了，名字是 `<anonymous@行号>`。
4. **前端的「引用」按名字匹配**，已经排除了被函数参数或局部变量遮住的同名标识符，但没有做完整的作用域分析。
5. **`Api` 属性的写入点要把第三节的两张表加起来看**：`Api` 自己的方法里的赋值，加上应用层服务从外面的赋值。
6. **测试对 `app` 模块和 `Api` 实例的用法是按变量名认的**（`app`、`local_app`、`api` 等），夹具换了名字就数不到。

## 一、大小分布（C1 ③）

复跑：`py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/measure.py`

JS 文件括号全部配平。

### 文件行数

| 组 | 文件数 | 总行数 | P50 | P90 | P99 | 最大 | 0–99 | 100–199 | 200–399 | 400–799 | 800–1499 | ≥1500 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 产品 Python | 90 | 37070 | 201 | 717 | 4873 | 4873 | 22 | 21 | 25 | 13 | 5 | 4 |
| 产品 JS | 44 | 15969 | 170 | 655 | 3357 | 3357 | 10 | 17 | 6 | 7 | 3 | 1 |
| 测试 Python | 69 | 55519 | 364 | 1809 | 9682 | 9682 | 6 | 11 | 20 | 17 | 6 | 9 |
| 测试 JS | 4 | 1981 | 187 | 856 | 856 | 856 | 0 | 2 | 0 | 1 | 1 | 0 |
| 本机版 Python（local/，不含测试） | 55 | 24882 | 214 | 717 | 4873 | 4873 | 13 | 11 | 16 | 10 | 2 | 3 |
| 本机版前端（local/ui/） | 40 | 14441 | 170 | 614 | 3357 | 3357 | 9 | 16 | 5 | 7 | 2 | 1 |

#### 400 行以上的文件

| 行数 | 文件 | 组 |
|---|---|---|
| 9682 | `local/tests/test_ui_contract.py` | 测试 Python |
| 5466 | `local/tests/test_phone_ui.py` | 测试 Python |
| 4873 | `local/app.py` | 产品 Python |
| 4131 | `local/tests/test_worker_boundaries.py` | 测试 Python |
| 4076 | `local/grab.py` | 产品 Python |
| 3357 | `local/ui/m/app.js` | 产品 JS |
| 3311 | `tools/qa_runtime_reliability.py` | 产品 Python |
| 3083 | `local/tests/test_application_services.py` | 测试 Python |
| 2415 | `local/tests/test_ui_reliability.py` | 测试 Python |
| 2090 | `local/tests/test_runtime_bundle.py` | 测试 Python |
| 1809 | `local/tests/test_signup_plan.py` | 测试 Python |
| 1746 | `local/tests/test_session_persistence.py` | 测试 Python |
| 1692 | `local/tests/test_lifecycle_release.py` | 测试 Python |
| 1666 | `local/infrastructure/component_packages.py` | 产品 Python |
| 1467 | `local/ui/views/plan-panel.js` | 产品 JS |
| 1321 | `tools/release.py` | 产品 Python |
| 1252 | `local/ui/views/phone.js` | 产品 JS |
| 1192 | `local/tests/test_component_packages.py` | 测试 Python |
| 1116 | `local/gui.py` | 产品 Python |
| 1067 | `local/tests/test_login_relay.py` | 测试 Python |
| 998 | `local/tests/test_retry_policy.py` | 测试 Python |
| 977 | `server/bot/bot.js` | 产品 JS |
| 912 | `local/tests/test_business_clock.py` | 测试 Python |
| 901 | `local/tests/test_phone_service.py` | 测试 Python |
| 875 | `local/business_clock.py` | 产品 Python |
| 858 | `local/tests/test_update_check.py` | 测试 Python |
| 856 | `server/bot/test_bot_runtime.js` | 测试 JS |
| 824 | `server/deploy/auto_login.py` | 产品 Python |
| 819 | `server/deploy/grab_signup.py` | 产品 Python |
| 773 | `local/tests/fixtures/runtime_bridge.js` | 测试 JS |
| 736 | `local/tests/test_tunnel_manager.py` | 测试 Python |
| 719 | `local/tests/test_cancel_signup.py` | 测试 Python |
| 717 | `local/login_relay.py` | 产品 Python |
| 655 | `local/ui/app.js` | 产品 JS |
| 643 | `local/tests/test_single_instance.py` | 测试 Python |
| 632 | `local/tests/test_retry_phone_policy.py` | 测试 Python |
| 620 | `local/tests/test_phone_http.py` | 测试 Python |
| 614 | `local/signup_plan.py` | 产品 Python |
| 614 | `local/ui/controllers/refresh.js` | 产品 JS |
| 608 | `local/tests/test_login_relay_service.py` | 测试 Python |
| 590 | `local/tests/test_ui_conflict_cancel.py` | 测试 Python |
| 590 | `server/tests/test_grab_signup_retry.py` | 测试 Python |
| 582 | `server/tests/test_runtime_safety.py` | 测试 Python |
| 551 | `local/application/login_relay_service.py` | 产品 Python |
| 548 | `local/ui/views/relogin.js` | 产品 JS |
| 548 | `local/update_check.py` | 产品 Python |
| 546 | `local/tests/test_terms_consent.py` | 测试 Python |
| 540 | `local/tests/test_installer_script.py` | 测试 Python |
| 533 | `local/tests/test_signup_transport.py` | 测试 Python |
| 533 | `local/tests/test_updater.py` | 测试 Python |
| 524 | `server/scripts/activity_watch.py` | 产品 Python |
| 518 | `local/build/build_installer.py` | 产品 Python |
| 515 | `server/scripts/notify.py` | 产品 Python |
| 507 | `local/ui/views/terms.js` | 产品 JS |
| 503 | `local/application/advanced_component_service.py` | 产品 Python |
| 503 | `local/ui/controllers/plan.js` | 产品 JS |
| 492 | `local/ui/controllers/terms.js` | 产品 JS |
| 478 | `local/tests/test_ui_main_window_plan.py` | 测试 Python |
| 461 | `local/application/phone_service.py` | 产品 Python |
| 449 | `local/ui/views/list.js` | 产品 JS |
| 449 | `local/updater.py` | 产品 Python |
| 447 | `server/tests/test_activity_watch.py` | 测试 Python |
| 444 | `local/domain/phone_rules.py` | 产品 Python |
| 438 | `local/tests/test_ui_main_window_list.py` | 测试 Python |
| 435 | `server/scripts/card.py` | 产品 Python |
| 419 | `local/application/plan_service.py` | 产品 Python |
| 415 | `local/tests/test_list_signed.py` | 测试 Python |

### 函数行数（类单独列在后面）

| 组 | 函数数 | P50 | P90 | P99 | 最大 | 1–10 | 11–20 | 21–40 | 41–60 | 61–100 | ≥101 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 产品 Python | 1595 | 12 | 40 | 114 | 1467 | 715 | 406 | 315 | 80 | 60 | 19 |
| 产品 JS | 1075 | 7 | 32 | 108 | 262 | 681 | 206 | 110 | 36 | 28 | 14 |
| 测试 Python | 4066 | 8 | 25 | 53 | 166 | 2506 | 938 | 511 | 86 | 19 | 6 |
| 测试 JS | 216 | 8 | 19 | 50 | 763 | 132 | 67 | 14 | 1 | 0 | 2 |
| 本机版 Python（local/，不含测试） | 1111 | 12 | 39 | 101 | 1467 | 496 | 298 | 215 | 49 | 41 | 12 |
| 本机版前端（local/ui/） | 1008 | 7 | 31 | 107 | 262 | 647 | 193 | 98 | 33 | 24 | 13 |

#### 产品 Python：超过本组 P99（114 行）的函数，共 15 个

| 行数 | 位置 | 名字 |
|---|---|---|
| 1467 | `local/grab.py:2502-3968` | `cmd_grab` |
| 359 | `local/application/plan_service.py:61-419` | `run_plan_task` |
| 343 | `server/deploy/grab_signup.py:405-747` | `run_submit_loop` |
| 261 | `local/infrastructure/phone_http.py:129-389` | `_make_handler` |
| 239 | `local/app.py:2994-3232` | `Api._start_plan_inner` |
| 167 | `local/app.py:814-980` | `Api.__init__` |
| 162 | `local/gui.py:493-654` | `App._build_ui` |
| 151 | `local/application/update_service.py:126-276` | `run_version_download` |
| 144 | `server/scripts/run.py:202-345` | `main` |
| 143 | `local/grab.py:1333-1475` | `cmd_list` |
| 140 | `tools/release.py:624-763` | `stage_local_assets` |
| 130 | `tools/qa_runtime_reliability.py:1342-1471` | `_` |
| 125 | `tools/release.py:928-1052` | `verify_release_assets` |
| 123 | `server/deploy/auto_login.py:698-820` | `main` |
| 117 | `local/signup_plan.py:186-302` | `validate_plan` |

#### 产品 JS：超过本组 P99（108 行）的函数，共 9 个

| 行数 | 位置 | 名字 |
|---|---|---|
| 262 | `local/ui/views/phone.js:437-698` | `paintPhoneAccess` |
| 186 | `server/bot/bot.js:759-944` | `<anonymous@759>` |
| 163 | `local/ui/m/app.js:3184-3346` | `wire` |
| 146 | `local/ui/views/update.js:35-180` | `paintUpdate` |
| 124 | `local/ui/views/plan-panel.js:4-127` | `paintSelected` |
| 123 | `local/ui/controllers/refresh.js:122-244` | `refresh` |
| 119 | `local/ui/views/settings.js:193-311` | `paintOcrDownload` |
| 117 | `local/ui/controllers/plan.js:2-118` | `startPlan` |
| 116 | `local/ui/views/plan-panel.js:930-1045` | `paintLed` |

#### 测试 Python：超过本组 P99（53 行）的函数，共 40 个

| 行数 | 位置 | 名字 |
|---|---|---|
| 166 | `local/tests/test_worker_boundaries.py:346-511` | `FakePage.fire_from_confirm` |
| 156 | `local/tests/test_worker_boundaries.py:607-762` | `run_worker` |
| 138 | `local/tests/test_ui_contract.py:9329-9466` | `WorkbenchUiContractTests.test_close_dialog_three_exits` |
| 127 | `local/tests/test_ui_contract.py:5960-6086` | `TermsConsentContractTests.test_terms_dialog_structure_contract` |
| 106 | `local/tests/test_ui_contract.py:1130-1235` | `TimetableGroupingBehaviorTests.test_group_timetable_places_each_activity_in_its_correct_group` |
| 102 | `local/tests/test_ui_contract.py:5658-5759` | `TermsConsentContractTests._embedded_canonical_texts` |
| 92 | `local/tests/test_lifecycle_release.py:971-1062` | `AssetVerificationTests.test_verify_rejects_each_bad_candidate` |
| 84 | `local/tests/test_phone_ui.py:3998-4081` | `ResultTermsModelTests.test_result_view_counts_and_heads_follow_prototype` |
| 83 | `server/tests/test_dedup.py:56-138` | `main` |
| 77 | `local/tests/test_ui_contract.py:5305-5381` | `TermsConsentContractTests.test_accept_terms_writes_prefs_transaction_only` |
| 75 | `local/tests/test_ui_contract.py:4840-4914` | `UpdateBoardPaintTests.test_one_primary_action_per_state` |
| 72 | `local/tests/test_phone_ui.py:3065-3136` | `RunWaitModelTests.test_task_card_follows_prototype_detail_priority` |
| 72 | `local/tests/test_retry_policy.py:656-727` | `_WorkerCase._run_task` |
| 71 | `local/tests/test_phone_ui.py:4110-4180` | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| 69 | `local/tests/test_ui_contract.py:7234-7302` | `TermsInteractionLoopTests.test_boot_defers_intro_until_terms_accepted` |
| 68 | `local/tests/test_ui_contract.py:6415-6482` | `TermsConsentBehaviorTests.test_unknown_terms_accept_rejects_bad_receipts` |
| 67 | `local/tests/test_phone_ui.py:5349-5415` | `WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` |
| 67 | `server/tests/test_notify.py:181-247` | `check_public_copy` |
| 66 | `local/tests/test_retry_phone_integration.py:202-267` | `FullChainTests.test_pair_read_start_extend_stop_relogin_chain` |
| 65 | `local/tests/test_phone_ui.py:3195-3259` | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| 64 | `local/tests/test_ui_contract.py:6819-6882` | `TermsInteractionLoopTests.test_save_timeout_keeps_gate_reopens_close_and_drops_late_receipt` |
| 63 | `local/tests/test_worker_boundaries.py:1087-1149` | `ListEntryTests.test_cmd_list_without_clock_keeps_full_enrich` |
| 62 | `local/tests/test_ui_contract.py:6484-6545` | `TermsConsentBehaviorTests.test_decline_does_not_reprompt_and_keeps_help_available` |
| 62 | `local/tests/test_ui_contract.py:7171-7232` | `TermsInteractionLoopTests.test_close_restores_banner_focus_without_stacking_dialogs` |
| 61 | `local/tests/test_ui_contract.py:9103-9163` | `WorkbenchUiContractTests.test_five_pre_start_warnings_only_remind` |
| 60 | `local/tests/test_phone_ui.py:5275-5334` | `WorkbenchPhoneTests.test_terms_not_accepted_keeps_the_phone_read_only` |
| 60 | `local/tests/test_ui_contract.py:7439-7498` | `TermsInteractionLoopTests.test_terms_status_feedback_resets_reading_scroll_zero_side_effects` |
| 59 | `local/tests/test_worker_boundaries.py:1251-1309` | `ListEntryTests.test_exhausted_lookup_budget_never_opens_browser` |
| 58 | `local/tests/test_signup_plan.py:451-508` | `ApiBusyLockTests.test_run_plan_task_keeps_future_start_when_os_date_is_30_days_off` |
| 58 | `local/tests/test_ui_contract.py:3537-3594` | `RuntimeDisplayBehaviorTests.test_single_failure_does_not_paint_plan` |
| 58 | `local/tests/test_ui_contract.py:6356-6413` | `TermsConsentBehaviorTests.test_unknown_terms_accept_with_matching_receipt_unlocks_once` |
| 57 | `local/tests/test_session_persistence.py:942-998` | `LifecycleContractTests.test_check_anchor_switches_on_relogin_and_never_writes` |
| 57 | `local/tests/test_session_persistence.py:1686-1742` | `LifecycleTransactionTests.test_takeover_and_cross_process_lock` |
| 57 | `local/tests/test_ui_reliability.py:2000-2056` | `AutoListRefreshTests.test_background_round_has_no_skeleton_checking_capsule_or_result_box` |
| 56 | `local/tests/test_session_persistence.py:1014-1069` | `LifecycleContractTests.test_login_state_hours_left_follows_anchor_but_never_expires` |
| 55 | `local/tests/test_worker_boundaries.py:932-986` | `ListEntryTests._run_list` |
| 54 | `local/tests/test_phone_ui.py:1660-1713` | `OcrAndLoginRecoveryTests.test_missing_is_one_click_and_the_import_link_only_follows_a_failure` |
| 54 | `local/tests/test_runtime_bundle.py:1097-1150` | `ShutdownAcceptTests.test_concurrent_start_plans_accept_exactly_one` |
| 54 | `local/tests/test_ui_contract.py:3049-3102` | `ErrorFeedbackRoundtripTests.test_next_round_recovery_and_no_permanent_pending` |
| 54 | `local/tests/test_worker_boundaries.py:2761-2814` | `UnifiedDirectLoopTests.test_foreign_and_mismatched_events_have_no_side_effects` |

#### 测试 JS：超过本组 P99（50 行）的函数，共 2 个

| 行数 | 位置 | 名字 |
|---|---|---|
| 763 | `local/tests/fixtures/runtime_bridge.js:11-773` | `<anonymous@11>` |
| 164 | `server/bot/test_bot_runtime.js:69-232` | `createHarness` |

### 产品代码里 60 行以上的函数（按文件汇总）

| 文件 | 60 行以上 | 100 行以上 | 最长 |
|---|---|---|---|
| `local/app.py` | 14 | 2 | `Api._start_plan_inner` 239 行 |
| `local/grab.py` | 11 | 3 | `cmd_grab` 1467 行 |
| `local/ui/m/app.js` | 8 | 2 | `wire` 163 行 |
| `tools/qa_runtime_reliability.py` | 7 | 1 | `_` 130 行 |
| `local/ui/views/plan-panel.js` | 5 | 2 | `paintSelected` 124 行 |
| `server/bot/bot.js` | 4 | 1 | `<anonymous@759>` 186 行 |
| `local/infrastructure/component_packages.py` | 3 | 0 | `install` 72 行 |
| `tools/release.py` | 3 | 2 | `stage_local_assets` 140 行 |
| `local/ui/controllers/plan.js` | 3 | 1 | `startPlan` 117 行 |
| `local/ui/controllers/terms.js` | 3 | 1 | `acceptTerms` 107 行 |
| `local/ui/views/phone.js` | 3 | 1 | `paintPhoneAccess` 262 行 |
| `local/application/advanced_component_service.py` | 2 | 1 | `AdvancedComponentService._run_split_assets` 101 行 |
| `local/application/login_relay_service.py` | 2 | 1 | `LoginRelayService._handle_line` 103 行 |
| `local/application/plan_service.py` | 2 | 1 | `run_plan_task` 359 行 |
| `local/gui.py` | 2 | 1 | `App._build_ui` 162 行 |
| `local/signup_plan.py` | 2 | 1 | `validate_plan` 117 行 |
| `server/deploy/auto_login.py` | 2 | 1 | `main` 123 行 |
| `server/deploy/grab_signup.py` | 2 | 1 | `run_submit_loop` 343 行 |
| `server/scripts/activity_watch.py` | 2 | 0 | `compute_events` 85 行 |
| `local/ui/app.js` | 2 | 0 | `boot` 77 行 |
| `local/ui/controllers/refresh.js` | 2 | 2 | `refresh` 123 行 |
| `local/ui/views/list.js` | 2 | 0 | `paintEmpty` 95 行 |
| `local/application/auto_relogin.py` | 1 | 0 | `AutoReloginMonitor.tick` 90 行 |
| `local/application/update_service.py` | 1 | 1 | `run_version_download` 151 行 |
| `local/build/build_advanced.py` | 1 | 0 | `_build_legacy` 76 行 |
| `local/business_clock.py` | 1 | 0 | `BusinessClock._accept_cluster` 72 行 |
| `local/domain/demo_data.py` | 1 | 0 | `demo_items` 79 行 |
| `local/domain/phone_rules.py` | 1 | 0 | `normalize_action` 76 行 |
| `local/domain/plan_rules.py` | 1 | 0 | `classify_task_stop` 62 行 |
| `local/infrastructure/phone_http.py` | 1 | 1 | `_make_handler` 261 行 |
| `local/infrastructure/tray_icon.py` | 1 | 0 | `TrayIcon._run` 73 行 |
| `local/infrastructure/tunnel_manager.py` | 1 | 0 | `CloudflareTunnel.start` 84 行 |
| `local/runtime_paths.py` | 1 | 0 | `_migrate_legacy_data` 86 行 |
| `local/signup_signing.py` | 1 | 0 | `_encrypt_block_cng` 100 行 |
| `local/update_delta.py` | 1 | 0 | `apply_delta` 70 行 |
| `local/update_launcher.py` | 1 | 0 | `apply_staged` 76 行 |
| `local/updater.py` | 1 | 0 | `download_installer` 88 行 |
| `server/scripts/dev/explore.py` | 1 | 0 | `main` 63 行 |
| `server/scripts/fetch.py` | 1 | 1 | `main` 109 行 |
| `server/scripts/query.py` | 1 | 0 | `main` 71 行 |
| `server/scripts/regress.py` | 1 | 0 | `main` 76 行 |
| `server/scripts/run.py` | 1 | 1 | `main` 144 行 |
| `server/scripts/scan.py` | 1 | 0 | `_scan` 81 行 |
| `server/scripts/token_probe.py` | 1 | 0 | `main` 69 行 |
| `server/scripts/watchlist_runner.py` | 1 | 0 | `main` 76 行 |
| `tools/qa_business_clock_worker.py` | 1 | 0 | `run_probe` 99 行 |
| `tools/verify_autologin_loop.py` | 1 | 0 | `main` 87 行 |
| `local/ui/controllers/tick.js` | 1 | 0 | `tick` 88 行 |
| `local/ui/led.js` | 1 | 1 | `<anonymous@11>` 108 行 |
| `local/ui/state/clock.js` | 1 | 0 | `ingestBusinessClock` 80 行 |
| `local/ui/views/clock-pop.js` | 1 | 0 | `renderClockPop` 76 行 |
| `local/ui/views/login.js` | 1 | 1 | `paintLogin` 103 行 |
| `local/ui/views/relogin.js` | 1 | 0 | `receiveReloginState` 63 行 |
| `local/ui/views/settings.js` | 1 | 1 | `paintOcrDownload` 119 行 |
| `local/ui/views/terms.js` | 1 | 0 | `applyTermsFooter` 77 行 |
| `local/ui/views/update.js` | 1 | 1 | `paintUpdate` 146 行 |
| `server/deploy/server_refresh.js` | 1 | 0 | `runDaemon` 80 行 |

### Python 类行数

| 组 | 类数 | P50 | P90 | P99 | 最大 |
|---|---|---|---|---|---|
| 产品 Python | 61 | 29 | 385 | 3808 | 3808 |
| 测试 Python | 636 | 44 | 185 | 533 | 1086 |

#### 产品 Python 里 200 行以上的类

| 行数 | 位置 | 类 | 方法数 |
|---|---|---|---|
| 3808 | `local/app.py:813-4620` | `Api` | 153 |
| 663 | `local/gui.py:420-1082` | `App` | 34 |
| 493 | `local/business_clock.py:224-716` | `BusinessClock` | 26 |
| 439 | `local/application/advanced_component_service.py:65-503` | `AdvancedComponentService` | 17 |
| 432 | `local/application/login_relay_service.py:115-546` | `LoginRelayService` | 19 |
| 425 | `local/application/phone_service.py:27-451` | `PhoneAccessService` | 26 |
| 385 | `local/grab.py:1907-2291` | `BurstPolicy` | 26 |
| 341 | `tools/qa_runtime_reliability.py:154-494` | `Session` | 41 |
| 299 | `local/signup_plan.py:316-614` | `PlanCoordinator` | 18 |
| 255 | `local/infrastructure/phone_http.py:133-387` | `_make_handler.Handler` | 24 |
| 253 | `local/infrastructure/single_instance.py:115-367` | `SingleInstance` | 13 |
| 229 | `local/infrastructure/lifecycle_store.py:36-264` | `AppLifecycle` | 11 |

## 二、后端跨层 import（C1 ② 后端）

复跑：`py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/py_layers.py`

扫了 51 个文件（local/ 下非测试、非 build）。`test_layer_boundaries` 的黑名单：app, business_clock, grab, gui, runtime_paths, signup_plan, time_contract, update_check, update_delta, update_launcher, updater, webview。

### 各层之间的 import 条数

| 从 ＼ 到 | domain | application | infrastructure | top |
|---|---|---|---|---|
| domain | 8 | 0 | 0 | 0 |
| application | 12 | 0 | 1（越界） | 0 |
| infrastructure | 3 | 0 | 12 | 1（越界） |
| top | 14 | 7 | 16 | 25 |

### 越界的 import，共 2 条

| 位置 | 从 | import 了 | 到 | 延迟 import | 现有测试拦不拦 |
|---|---|---|---|---|---|
| `local/application/advanced_component_service.py:29` | application | `infrastructure.component_packages` | infrastructure | 否 | 不拦 |
| `local/infrastructure/component_packages.py:101` | infrastructure | `runtime_paths` | top | 是 | 不拦 |

### 现有测试没覆盖到的方向

`test_layer_boundaries` 只检查 `domain/`、`application/` 两个包，只拦黑名单里的模块名。下面这些 import 即使出现也不会让它变红：

| 方向 | 现在有几条 | 位置 |
|---|---|---|
| domain → application | 0 | — |
| domain → infrastructure | 0 | — |
| application → infrastructure | 1 | `local/application/advanced_component_service.py:29`（`infrastructure.component_packages`） |
| infrastructure → application | 0 | — |
| infrastructure → 顶层 | 1 | `local/infrastructure/component_packages.py:101`（`runtime_paths`） |

### 字符串 import（0 处，人工看）

| 位置 | 调用 | 参数 |
|---|---|---|

### 顶层模块对三层的依赖（事实，不算越界）

| 顶层模块 | domain | application | infrastructure | 其他顶层模块 |
|---|---|---|---|---|
| `local/advanced_helper.py` | — | — | 2：advanced_features、phone_qr | — |
| `local/app.py` | 10：cancel_rules、demo_data、errors、lifecycle_rules、log_events、login_rules、plan_rules、retry_rules、time_text、worker_lines | 7：advanced_component_service、auto_relogin、login_relay_service、login_service、phone_service、plan_service、update_service | 12：advanced_features、component_packages、credential_store、lifecycle_store、phone_http、phone_qr、phone_session_store、prefs_store、process_tree、single_instance、tray_icon、tunnel_manager | 6：business_clock、runtime_paths、signup_plan、time_contract、update_check、updater |
| `local/grab.py` | 4：cancel_rules、log_events、retry_window、signup_reply | — | 1：prefs_store | 7：business_clock、login_relay、runtime_paths、signup_signing、signup_transport、site_target、time_contract |
| `local/login_relay.py` | — | — | — | 1：site_target |
| `local/runtime_paths.py` | — | — | 1：prefs_store | — |
| `local/signup_plan.py` | — | — | — | 2：business_clock、time_contract |
| `local/update_launcher.py` | — | — | — | 1：updater |
| `local/updater.py` | — | — | — | 1：update_delta |

## 三、Python 隐式状态（C1 ④）

复跑：`py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/py_state.py`

### A. 模块级可变全局（扫了 80 个文件，共 23 个）

| 定义位置 | 名字 | 初值 | 写的位置（函数:行 方式）| 读它的函数数 |
|---|---|---|---|---|
| `local/app.py:114` | `_CREDENTIAL_STORE_OK` | None | `_credential_store_available`:140 global 赋值；`_credential_store_available`:142 global 赋值 | 1 |
| `local/app.py:388` | `DEMO` | False | `main`:4784 global 赋值 | 22 |
| `local/app.py:397` | `_CLOCK_ENV` | dict | `main`:4817 下标赋值；`main`:4818 下标赋值 | 2 |
| `local/app.py:541` | `_QR_CACHE` | dict | `_phone_qr_data`:555 .clear()；`_phone_qr_data`:556 下标赋值 | 1 |
| `local/app.py:778` | `_LIFECYCLE` | None | `get_lifecycle`:788 global 赋值 | 1 |
| `local/grab.py:88` | `_CLOCK` | dict | `configure_business_clock`:92 下标赋值；`configure_business_clock`:93 下标赋值；`configure_business_clock`:94 下标赋值 | 6 |
| `local/grab.py:311` | `_EVENT_CONTEXT` | dict | `cmd_grab`:2754 下标赋值 | 2 |
| `local/grab.py:585` | `_SCHOOL_DATE` | dict | `_remember_school_date`:603 下标赋值；`_remember_school_date`:604 下标赋值；`clear_school_date`:615 .update() | 3 |
| `local/grab.py:807` | `DETAIL_CACHE` | dict | `fetch_activity_detail`:904 下标赋值 | 1 |
| `local/infrastructure/advanced_features.py:51` | `_OCR_ENGINES` | dict | `classify_captcha`:207 下标赋值 | 1 |
| `local/infrastructure/advanced_features.py:54` | `_PACKAGE_CACHE` | dict | `_frozen_package`:95 下标赋值 | 1 |
| `local/infrastructure/component_packages.py:62` | `_STATUS_CACHE` | dict | `_recover_replacement`:665 .pop()；`_recover_replacement`:672 .pop()；`_recover_replacement`:680 .pop()；`_recover_replacement`:683 .pop()；`_recover_replacement`:687 .pop()；`_recover_replacement`:697 .pop()；`status`:736 下标赋值；`status`:744 下标赋值 等 11 处 | 4 |
| `local/infrastructure/component_packages.py:63` | `_ARTIFACT_STATUS_CACHE` | dict | `_reclaim_group_cache`:599 .pop()；`_handle`:970 .pop()；`_handle`:988 .pop()；`_handle`:989 下标赋值 | 2 |
| `local/infrastructure/component_packages.py:66` | `_CLOUDFLARED_PROBE_CACHE` | dict | `stored_cloudflared`:1564 .clear()；`stored_cloudflared`:1565 下标赋值 | 1 |
| `local/infrastructure/component_packages.py:67` | `_TRANSACTION_LOCAL` | local() | `_file_transaction`:125 属性赋值；`_file_transaction`:128 属性赋值 | 1 |
| `local/infrastructure/process_tree.py:97` | `_KERNEL32` | None | `win_kernel32`:133 global 赋值 | 1 |
| `local/runtime_paths.py:35` | `_MIGRATION_RECORD` | None | `_migrate_legacy_data`:112 global 赋值；`_migrate_legacy_data`:122 global 赋值；`_migrate_legacy_data`:169 global 赋值 | 1 |
| `local/runtime_paths.py:39` | `_MIGRATION_DONE` | False | `_migrate_legacy_data`:108 global 赋值；`_migrate_legacy_data`:114 global 赋值；`_migrate_legacy_data`:124 global 赋值；`_migrate_legacy_data`:172 global 赋值 | 1 |
| `local/time_contract.py:28` | `_BUSINESS_NOW` | None | `configure_time_source`:70 global 赋值 | 1 |
| `server/deploy/auto_login.py:251` | `_DDDD_ENGINES` | dict | `_ddddocr_engine`:273 下标赋值 | 1 |
| `server/scripts/common.py:50` | `_HELD` | dict | `file_lock`:215 下标赋值；`file_lock`:238 下标赋值 | 1 |
| `server/scripts/regress.py:12` | `CASES` | list | `run`:29 .append() | 2 |
| `server/scripts/trigger_server.py:38` | `_last_run` | list | `Handler.do_GET`:88 下标赋值 | 1 |

### B. `Api` 实例属性（`local/app.py`，153 个方法，74 个属性）

赋值方法数的分布：0 个方法：6 个属性、1 个方法：24 个属性、2 个方法：21 个属性、3 个方法：13 个属性、4 个方法：3 个属性、≥5 个方法：7 个属性。

#### 在 3 个及以上方法里赋值的属性，共 23 个

| 属性 | 赋值的方法数 | 赋值的位置（方法:行）| 原地修改的方法数 | 读的方法数 |
|---|---|---|---|---|
| `self._phone_channel` | 7 | `__init__`:909、`_install_downloaded_component`:1336、`_commit_downloaded_component_group`:1348、`shutdown`:3573、`_reconcile_cloudflare_lifecycle`:3762、`_start_phone_access`:3859,3868、`_stop_phone_access`:4032 | 0 | 5 |
| `self._pending_save` | 6 | `__init__`:974、`_begin_auto_relogin_once`:2034、`prepare_phone_relogin`:4067、`_commit_pending_save`:4079、`_begin_typed_relogin`:4149、`_relay_finished`:4307 | 0 | 1 |
| `self._proc` | 6 | `__init__`:820、`stop`:3640、`_spawn_relay_worker`:4272、`_relay_finished`:4289,4291、`_spawn`:4534、`_pump`:4613 | 0 | 8 |
| `self._proc_tree` | 6 | `__init__`:822、`stop`:3638、`_spawn_relay_worker`:4273、`_relay_finished`:4287,4293、`_spawn`:4535、`_pump`:4615 | 0 | 4 |
| `self._advanced_busy` | 5 | `__init__`:844、`_component_finished`:1358、`download_advanced_feature`:1440、`install_advanced_feature`:1661,1686、`remove_advanced_feature`:1740,1768 | 0 | 7 |
| `self._once_creds_rejected` | 5 | `__init__`:973、`save_relogin_credentials`:1788、`clear_relogin_credentials`:1800、`prepare_phone_relogin`:4066、`_relay_finished`:4321 | 0 | 1 |
| `self._window_minimized` | 5 | `__init__`:944、`request_window_close`:3372、`show_window`:3439、`_on_window_minimized`:3454、`_on_window_restored`:3457 | 0 | 1 |
| `self._cloudflare_exit_notice` | 4 | `__init__`:957、`_cloudflare_status_snapshot`:3743、`_start_phone_access`:3874、`stop_phone_access`:4021 | 0 | 1 |
| `self._relay_proc_tree` | 4 | `__init__`:824、`stop`:3642、`_spawn_relay_worker`:4274、`_relay_finished`:4280 | 0 | 2 |
| `self._updating` | 4 | `__init__`:880、`check_update`:2076,2088、`_publish_update`:2112、`update_download`:2131,2139 | 0 | 3 |
| `self._check_again` | 3 | `__init__`:861、`check`:2270、`_do_check`:2327 | 0 | 1 |
| `self._checking` | 3 | `__init__`:858、`check`:2278、`_do_check`:2322,2329 | 0 | 5 |
| `self._last_check` | 3 | `__init__`:871、`_do_check`:2315、`_do_check_inner`:2405,2451 | 0 | 5 |
| `self._list_last` | 3 | `__init__`:869、`_emit`:1117、`_after_cancelled`:2631 | 0 | 2 |
| `self._listing` | 3 | `__init__`:862、`list_activities`:2302、`_do_list`:2515 | 0 | 4 |
| `self._login_wait_pending` | 3 | `__init__`:873、`_request_auto_relogin`:1898、`_begin_auto_relogin_once`:2044 | 0 | 1 |
| `self._next_plan_source` | 3 | `__init__`:946、`start_plan`:2964、`_start_plan_inner`:2998 | 0 | 0 |
| `self._pc_list_error` | 3 | `__init__`:840、`_note_pc_list_error`:2485、`_do_list_inner`:2684,2751 | 0 | 1 |
| `self._relay_creds_source` | 3 | `__init__`:970、`_begin_auto_relogin_once`:2033、`prepare_phone_relogin`:4063 | 0 | 2 |
| `self._tray` | 3 | `__init__`:855、`_ensure_tray`:3506,3509、`_stop_tray`:3514 | 0 | 6 |
| `self._update_cancelled` | 3 | `__init__`:886、`update_download`:2133、`update_cancel`:2174 | 0 | 0 |
| `self._update_request_id` | 3 | `__init__`:881、`check_update`:2077、`update_download`:2132 | 0 | 3 |
| `self._window_hidden` | 3 | `__init__`:943、`hide_window`:3408、`show_window`:3438 | 0 | 2 |

#### 在 2 个方法里赋值的属性，共 21 个

| 属性 | 赋值的位置（方法:行）| 原地修改的方法数 | 读的方法数 |
|---|---|---|---|
| `self._activities` | `__init__`:835、`_do_list_inner`:2682,2750 | 2 | 6 |
| `self._auto_relogin_started_at` | `__init__`:875、`_begin_auto_relogin`:1998 | 0 | 2 |
| `self._cancelling` | `__init__`:864、`cancel_signup`:2575,2580 | 0 | 6 |
| `self._check_last` | `__init__`:868、`_emit`:1114 | 0 | 1 |
| `self._check_request_id` | `__init__`:866、`check`:2279 | 0 | 2 |
| `self._clock_syncing` | `__init__`:818、`sync_clock`:1051,1060 | 0 | 1 |
| `self._close_approved` | `__init__`:853、`request_window_close`:3374 | 0 | 0 |
| `self._closing` | `__init__`:851、`shutdown`:3545 | 0 | 30 |
| `self._cloudflare_starting` | `__init__`:960、`_start_phone_access`:3861,3865 | 0 | 1 |
| `self._expiry_pushed` | `__init__`:939、`_note_login_conclusion`:2346,2353 | 0 | 1 |
| `self._last_login_origin` | `__init__`:936、`_anchor_login_success`:4562 | 0 | 1 |
| `self._last_plan` | `__init__`:830、`_start_plan_inner`:3140,3206 | 0 | 2 |
| `self._latest_plan_id` | `__init__`:897、`_start_plan_inner`:3211 | 0 | 3 |
| `self._list_request_id` | `__init__`:867、`list_activities`:2303 | 0 | 2 |
| `self._login_expired_logged` | `__init__`:941、`_note_login_conclusion`:2347,2356 | 0 | 0 |
| `self._login_seen_valid` | `__init__`:938、`_note_login_conclusion`:2345 | 0 | 1 |
| `self._pc_list_ok_at` | `__init__`:841、`_do_list_inner`:2686,2753 | 0 | 1 |
| `self._plan` | `__init__`:825、`_start_plan_inner`:3127,3205,3225 | 0 | 14 |
| `self._plan_generation` | `__init__`:896、`_start_plan_inner`:3209 | 0 | 3 |
| `self._update_result` | `__init__`:882、`_publish_update`:2110 | 0 | 4 |
| `self._update_staging_path` | `__init__`:885、`check_update`:2075 | 0 | 2 |

#### 只在一两处赋值、但在 3 个及以上方法里原地修改的容器，共 1 个

| 属性 | 原地修改的位置（方法:行）| 读的方法数 |
|---|---|---|
| `self._cloudflare` | `_component_installed`:1383、`install_advanced_feature`:1680、`_install_selected_feature`:1729、`remove_advanced_feature`:1761、`_start_phone_access`:3852 | 8 |

#### 被最多方法读取的 15 个属性

| 属性 | 读的方法数 | 赋值的方法数 |
|---|---|---|
| `self._lock` | 67 | 1 |
| `self._closing` | 30 | 2 |
| `self._relay` | 26 | 1 |
| `self._auto_relogin` | 18 | 1 |
| `self._plan` | 14 | 2 |
| `self._phone` | 13 | 1 |
| `self._credential_lock` | 12 | 1 |
| `self._clock` | 9 | 1 |
| `self._phone_access_lock` | 9 | 1 |
| `self._proc` | 8 | 6 |
| `self._cloudflare` | 8 | 1 |
| `self._advanced_busy` | 7 | 5 |
| `self._start_requests` | 7 | 1 |
| `self._window` | 6 | 1 |
| `self._plan_procs` | 6 | 1 |

#### 别的模块从外面改写 `Api` 属性的位置，共 9 处

`Api` 把自己当参数传给服务，服务直接给它的下划线属性赋值。上面几张表只数了 `Api` 自己的方法，这些要加上才是全部写入点。

| 位置 | 所在函数 | 接收者 | 属性 |
|---|---|---|---|
| `local/application/update_service.py:48` | `run_check` | `state` | `_update_result` |
| `local/application/update_service.py:49` | `run_check` | `state` | `_update_installer` |
| `local/application/update_service.py:51` | `run_check` | `state` | `_update_installer_path` |
| `local/application/update_service.py:52` | `run_check` | `state` | `_update_staging_path` |
| `local/application/update_service.py:53` | `run_check` | `state` | `_update_cancelled` |
| `local/application/update_service.py:54` | `run_check` | `state` | `_updating` |
| `local/application/update_service.py:112` | `run_download` | `state` | `_update_installer_path` |
| `local/application/update_service.py:206` | `run_version_download.fallback_to_installer` | `state` | `_update_installer_path` |
| `local/application/update_service.py:264` | `run_version_download` | `state` | `_update_staging_path` |

### C. 测试改写 `Api` 实例成员的位置（66 个名字）

接收者按名字认（`api`、`self.api`、`self._api`）。「是什么」一列对照 `Api` 的方法名和属性名。

| 名字 | 是什么 | 次数 | 文件数 | 位置（每个文件第一处）|
|---|---|---|---|---|
| `_emit` | 方法 | 36 | 11 | `local/tests/test_application_services.py:469`、`local/tests/test_cancel_signup.py:469`、`local/tests/test_release_audit.py:32`、`local/tests/test_retry_phone_policy.py:142`、`local/tests/test_retry_policy.py:232`、`local/tests/test_runtime_bundle.py:179` 等 |
| `_last_check` | 属性 | 21 | 5 | `local/tests/test_application_services.py:2532`、`local/tests/test_retry_policy.py:234`、`local/tests/test_runtime_bundle.py:380`、`local/tests/test_session_persistence.py:490`、`local/tests/test_signup_plan.py:595` |
| `_activities` | 属性 | 20 | 6 | `local/tests/test_cancel_signup.py:470`、`local/tests/test_real_data_contract.py:63`、`local/tests/test_retry_policy.py:249`、`local/tests/test_runtime_bundle.py:394`、`local/tests/test_session_persistence.py:520`、`local/tests/test_signup_plan.py:601` |
| `_plan` | 属性 | 18 | 5 | `local/tests/test_application_services.py:325`、`local/tests/test_cancel_signup.py:553`、`local/tests/test_runtime_bundle.py:643`、`local/tests/test_session_persistence.py:638`、`local/tests/test_signup_plan.py:404` |
| `_window` | 属性 | 16 | 2 | `local/tests/test_application_services.py:341`、`local/tests/test_single_instance.py:397` |
| `_relay` | 属性 | 11 | 2 | `local/tests/test_application_services.py:1367`、`local/tests/test_silent_relogin.py:116` |
| `_update_result` | 属性 | 11 | 3 | `local/tests/test_application_services.py:2566`、`local/tests/test_runtime_bundle.py:1856`、`local/tests/test_update_check.py:615` |
| `_clock_ready` | 方法 | 10 | 3 | `local/tests/test_application_services.py:493`、`local/tests/test_cancel_signup.py:567`、`local/tests/test_runtime_bundle.py:529` |
| `_ensure_tray` | 方法 | 10 | 1 | `local/tests/test_application_services.py:361` |
| `_terms_gate` | 方法 | 10 | 5 | `local/tests/test_application_services.py:1424`、`local/tests/test_cancel_signup.py:478`、`local/tests/test_release_audit.py:85`、`local/tests/test_silent_relogin.py:82`、`local/tests/test_terms_consent.py:527` |
| `_update_installer` | 属性 | 9 | 2 | `local/tests/test_application_services.py:2718`、`local/tests/test_update_check.py:588` |
| `_phone` | 属性 | 8 | 2 | `local/tests/test_application_services.py:283`、`local/tests/test_release_audit.py:102` |
| `_run` | 方法 | 8 | 3 | `local/tests/test_cancel_signup.py:479`、`local/tests/test_runtime_bundle.py:530`、`local/tests/test_silent_relogin.py:103` |
| `_auto_relogin` | 属性 | 7 | 1 | `local/tests/test_application_services.py:1368` |
| `_proc` | 属性 | 7 | 4 | `local/tests/test_application_services.py:2955`、`local/tests/test_cancel_signup.py:535`、`local/tests/test_runtime_bundle.py:626`、`local/tests/test_signup_plan.py:415` |
| `_update_staging_path` | 属性 | 7 | 3 | `local/tests/test_application_services.py:2568`、`local/tests/test_runtime_bundle.py:1858`、`local/tests/test_update_check.py:544` |
| `_cloudflare` | 属性 | 5 | 2 | `local/tests/test_application_services.py:700`、`local/tests/test_release_audit.py:103` |
| `_checking` | 属性 | 4 | 3 | `local/tests/test_cancel_signup.py:534`、`local/tests/test_runtime_bundle.py:381`、`local/tests/test_session_persistence.py:484` |
| `_clock_now` | 方法 | 4 | 3 | `local/tests/test_application_services.py:2461`、`local/tests/test_cancel_signup.py:568`、`local/tests/test_retry_phone_policy.py:166` |
| `_closing` | 属性 | 4 | 3 | `local/tests/test_release_audit.py:29`、`local/tests/test_runtime_bundle.py:563`、`local/tests/test_update_check.py:581` |
| `_updating` | 属性 | 4 | 1 | `local/tests/test_update_check.py:521` |
| `_window_hidden` | 属性 | 4 | 2 | `local/tests/test_application_services.py:2807`、`local/tests/test_single_instance.py:398` |
| `_advanced_busy` | 属性 | 3 | 2 | `local/tests/test_release_audit.py:30`、`local/tests/test_terms_consent.py:525` |
| `_listing` | 属性 | 3 | 2 | `local/tests/test_cancel_signup.py:533`、`local/tests/test_silent_relogin.py:180` |
| `_silent_relogin_state` | 方法 | 3 | 1 | `local/tests/test_application_services.py:2533` |
| `_tray` | 属性 | 3 | 1 | `local/tests/test_application_services.py:545` |
| `_update_installer_path` | 属性 | 3 | 1 | `local/tests/test_update_check.py:533` |
| `_update_request_id` | 属性 | 3 | 1 | `local/tests/test_update_check.py:522` |
| `_begin_auto_relogin` | 方法 | 2 | 1 | `local/tests/test_application_services.py:1441` |
| `_begin_auto_relogin_once` | 方法 | 2 | 1 | `local/tests/test_silent_relogin.py:266` |
| `_ocr_component_service` | 属性 | 2 | 1 | `local/tests/test_release_audit.py:54` |
| `_proc_tree` | 属性 | 2 | 1 | `local/tests/test_application_services.py:2956` |
| `_push_login_expired` | 方法 | 2 | 2 | `local/tests/test_application_services.py:2067`、`local/tests/test_silent_relogin.py:85` |
| `_start_order` | 属性 | 2 | 1 | `local/tests/test_release_audit.py:82` |
| `_start_plan_inner` | 方法 | 2 | 1 | `local/tests/test_signup_plan.py:1393` |
| `_start_requests` | 属性 | 2 | 1 | `local/tests/test_release_audit.py:81` |
| `accept_terms` | 方法 | 2 | 1 | `local/tests/test_terms_consent.py:333` |
| `check` | 方法 | 2 | 2 | `local/tests/test_application_services.py:1475`、`local/tests/test_silent_relogin.py:304` |
| `_auto_relogin_paused` | 方法 | 1 | 1 | `local/tests/test_terms_consent.py:531` |
| `_auto_relogin_started_at` | 属性 | 1 | 1 | `local/tests/test_silent_relogin.py:303` |
| `_aux_procs` | 属性 | 1 | 1 | `local/tests/test_runtime_bundle.py:741` |
| `_aux_trees` | 属性 | 1 | 1 | `local/tests/test_runtime_bundle.py:740` |
| `_canceled_start_ids` | 属性 | 1 | 1 | `local/tests/test_release_audit.py:92` |
| `_cancelling` | 属性 | 1 | 1 | `local/tests/test_cancel_signup.py:536` |
| `_close_approved` | 属性 | 1 | 1 | `local/tests/test_application_services.py:1275` |
| `_cloudflare_starting` | 属性 | 1 | 1 | `local/tests/test_application_services.py:812` |
| `_component_service` | 属性 | 1 | 1 | `local/tests/test_release_audit.py:33` |
| `_credential_lock` | 属性 | 1 | 1 | `local/tests/test_release_audit.py:28` |
| `_do_check_inner` | 方法 | 1 | 1 | `local/tests/test_application_services.py:1489` |
| `_endpoint` | Api 里没有 | 1 | 1 | `local/tests/test_application_services.py:288` |
| `_is_busy_locked` | 方法 | 1 | 1 | `local/tests/test_release_audit.py:31` |
| `_list_last` | 属性 | 1 | 1 | `local/tests/test_cancel_signup.py:621` |
| `_lock` | 属性 | 1 | 1 | `local/tests/test_release_audit.py:26` |
| `_once_credentials_staged` | 方法 | 1 | 1 | `local/tests/test_terms_consent.py:530` |
| `_phone_access_lock` | 属性 | 1 | 1 | `local/tests/test_release_audit.py:27` |
| `_phone_channel` | 属性 | 1 | 1 | `local/tests/test_application_services.py:701` |
| `_plan_procs` | 属性 | 1 | 1 | `local/tests/test_signup_plan.py:416` |
| `_relogin_blocked_locked` | 方法 | 1 | 1 | `local/tests/test_terms_consent.py:526` |
| `_silent_relogin_ready` | 方法 | 1 | 1 | `local/tests/test_terms_consent.py:532` |
| `_window_minimized` | 属性 | 1 | 1 | `local/tests/test_single_instance.py:399` |
| `ack_lost` | Api 里没有 | 1 | 1 | `local/tests/test_retry_phone_integration.py:271` |
| `fail` | Api 里没有 | 1 | 1 | `local/tests/test_phone_service.py:532` |
| `plan_active_for_close` | 方法 | 1 | 1 | `local/tests/test_terms_consent.py:436` |
| `request_window_close` | 方法 | 1 | 1 | `local/tests/test_application_services.py:2607` |
| `stop_phone_access` | 方法 | 1 | 1 | `local/tests/test_release_audit.py:104` |
| `withdraw_terms` | 方法 | 1 | 1 | `local/tests/test_terms_consent.py:437` |

## 四、app.py 再导出与测试补丁（C3）

复跑：`py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/app_reexports.py`

`local/app.py` 模块级共 177 个名字：自己定义（def） 44 个、自己定义（class） 3 个、别名 28 个、import 进来 69 个、赋值（常量或变量） 33 个。
`local/tests/` 和 `tools/` 里有 15 个文件用到了 app 模块。

### 被测试打补丁的模块级名字，共 42 个

拆 `Api` 时这些名字必须留在 `app` 模块上，并且 `Api` 的代码必须仍然经 `app` 模块的全局名字去取它们，否则补丁打不到。

| 名字 | 种类 | app.py 行号 | 指向 | 打补丁次数 | 文件数 | 读取次数 | 打补丁的位置（每个文件第一处）|
|---|---|---|---|---|---|---|---|
| `PREFS` | 别名 | 107 | `UI_STATE_FILE` | 30 | 8 | 0 | `local/tests/test_application_services.py:273`、`local/tests/test_clock_tail.py:40`、`local/tests/test_retry_phone_policy.py:610`、`local/tests/test_retry_policy.py:74`、`local/tests/test_runtime_bundle.py:88`、`local/tests/test_session_persistence.py:412`、`local/tests/test_signup_plan.py:84`、`local/tests/test_ui_contract.py:282` |
| `PlanCoordinator` | import 进来 | 45 | `signup_plan.PlanCoordinator` | 30 | 2 | 0 | `local/tests/test_runtime_bundle.py:400`、`local/tests/test_signup_plan.py:1241` |
| `DEMO` | 赋值（常量或变量） | 388 | — | 24 | 6 | 0 | `local/tests/test_application_services.py:2237`、`local/tests/test_cancel_signup.py:475`、`local/tests/test_retry_phone_policy.py:611`、`local/tests/test_runtime_bundle.py:172`、`local/tests/test_session_persistence.py:496`、`local/tests/test_single_instance.py:413` |
| `worker_command` | 自己定义（def） | 414 | — | 24 | 6 | 1 | `local/tests/test_application_services.py:2219`、`local/tests/test_cancel_signup.py:477`、`local/tests/test_retry_phone_policy.py:163`、`local/tests/test_retry_policy.py:250`、`local/tests/test_runtime_bundle.py:189`、`local/tests/test_signup_plan.py:602` |
| `spawn_owned` | 别名 | 4632 | `_process_tree.spawn_owned` | 16 | 2 | 0 | `local/tests/test_application_services.py:2977`、`local/tests/test_runtime_bundle.py:235` |
| `SESSION_FILE` | import 进来 | 55 | `runtime_paths.SESSION_FILE` | 15 | 3 | 0 | `local/tests/test_runtime_bundle.py:171`、`local/tests/test_session_persistence.py:326`、`local/tests/test_ui_contract.py:281` |
| `DEVICE_FILE` | 赋值（常量或变量） | 145 | — | 7 | 1 | 0 | `local/tests/test_application_services.py:275` |
| `worker_problem` | 自己定义（def） | 356 | — | 7 | 3 | 5 | `local/tests/test_application_services.py:2976`、`local/tests/test_cancel_signup.py:476`、`local/tests/test_runtime_bundle.py:484` |
| `_env` | 自己定义（def） | 400 | — | 6 | 2 | 6 | `local/tests/test_retry_phone_policy.py:164`、`local/tests/test_retry_policy.py:711` |
| `check_latest_release` | import 进来 | 48 | `update_check.check_latest_release` | 6 | 1 | 0 | `local/tests/test_update_check.py:500` |
| `version_switch_available` | 自己定义（def） | 489 | — | 6 | 3 | 1 | `local/tests/test_application_services.py:2722`、`local/tests/test_runtime_bundle.py:1864`、`local/tests/test_update_check.py:631` |
| `DATA_DIR` | import 进来 | 55 | `runtime_paths.DATA_DIR` | 5 | 2 | 0 | `local/tests/test_application_services.py:1009`、`local/tests/test_single_instance.py:509` |
| `GRAB` | 赋值（常量或变量） | 106 | — | 5 | 1 | 2 | `local/tests/test_runtime_bundle.py:1360` |
| `LIST_CLOCK_WAIT_S` | 赋值（常量或变量） | 809 | — | 5 | 1 | 0 | `local/tests/test_runtime_bundle.py:527` |
| `_kill_tree` | 别名 | 4628 | `_process_tree.kill_tree` | 4 | 1 | 0 | `local/tests/test_runtime_bundle.py:710` |
| `resolve_update_launcher_path` | 自己定义（def） | 421 | — | 4 | 2 | 0 | `local/tests/test_application_services.py:2581`、`local/tests/test_runtime_bundle.py:1908` |
| `LIST_CLOCK_POLL_S` | 赋值（常量或变量） | 810 | — | 3 | 1 | 0 | `local/tests/test_runtime_bundle.py:528` |
| `get_lifecycle` | 自己定义（def） | 782 | — | 3 | 3 | 0 | `local/tests/test_runtime_bundle.py:468`、`local/tests/test_single_instance.py:513`、`local/tests/test_update_check.py:503` |
| `migration_record` | import 进来 | 55 | `runtime_paths.migration_record` | 3 | 1 | 0 | `local/tests/test_session_persistence.py:329` |
| `SUPERVISE_GRACE_S` | 赋值（常量或变量） | 4668 | — | 2 | 2 | 2 | `local/tests/test_retry_phone_policy.py:122`、`local/tests/test_retry_policy.py:640` |
| `ensure_data_dir` | import 进来 | 55 | `runtime_paths.ensure_data_dir` | 2 | 2 | 0 | `local/tests/test_application_services.py:2216`、`local/tests/test_single_instance.py:510` |
| `load_prefs` | 自己定义（def） | 517 | — | 2 | 2 | 5 | `local/tests/test_application_services.py:1244`、`local/tests/test_update_check.py:501` |
| `login_state` | 自己定义（def） | 692 | — | 2 | 2 | 19 | `local/tests/test_runtime_bundle.py:466`、`local/tests/test_update_check.py:502` |
| `phone_log` | 自己定义（def） | 151 | — | 2 | 1 | 0 | `local/tests/test_single_instance.py:389` |
| `update_version_paths` | 自己定义（def） | 210 | — | 2 | 2 | 2 | `local/tests/test_application_services.py:2583`、`local/tests/test_runtime_bundle.py:1867` |
| `Api` | 自己定义（class） | 813 | — | 1 | 1 | 85 | `local/tests/test_single_instance.py:514` |
| `BusinessClock` | import 进来 | 46 | `business_clock.BusinessClock` | 1 | 1 | 0 | `local/tests/test_single_instance.py:511` |
| `CREDENTIAL_FILE` | 赋值（常量或变量） | 113 | — | 1 | 1 | 0 | `local/tests/test_application_services.py:2214` |
| `LOG_FILE` | import 进来 | 55 | `runtime_paths.LOG_FILE` | 1 | 1 | 0 | `local/tests/test_application_services.py:2215` |
| `RUNTIME_CHECK_TIMEOUT_S` | 赋值（常量或变量） | 353 | — | 1 | 1 | 0 | `local/tests/test_runtime_bundle.py:1349` |
| `_CREDENTIAL_STORE_OK` | 赋值（常量或变量） | 114 | — | 1 | 1 | 0 | `local/tests/test_application_services.py:2218` |
| `_PREFS_SAVE_TIMEOUT_S` | 别名 | 613 | `_prefs_store.SAVE_TIMEOUT_S` | 1 | 1 | 0 | `local/tests/test_clock_tail.py:77` |
| `_credential_store` | import 进来 | 77 | `infrastructure.credential_store` | 1 | 1 | 0 | `local/tests/test_application_services.py:2217` |
| `_prefs_transaction` | 别名 | 514 | `_prefs_store.prefs_transaction` | 1 | 1 | 0 | `local/tests/test_clock_tail.py:41` |
| `_screen_size` | 自己定义（def） | 4740 | — | 1 | 1 | 0 | `local/tests/test_single_instance.py:515` |
| `_seconds_until` | 自己定义（def） | 757 | — | 1 | 1 | 0 | `local/tests/test_runtime_bundle.py:262` |
| `configure_time_source` | import 进来 | 47 | `time_contract.configure_time_source` | 1 | 1 | 0 | `local/tests/test_single_instance.py:512` |
| `defer_close_action` | 自己定义（def） | 635 | — | 1 | 1 | 0 | `local/tests/test_application_services.py:2586` |
| `save_session_timing_anchor` | 自己定义（def） | 597 | — | 1 | 1 | 3 | `local/tests/test_session_persistence.py:1264` |
| `spawn_owned_worker` | 别名 | 4631 | `_process_tree.spawn_owned_worker` | 1 | 1 | 0 | `local/tests/test_signup_plan.py:499` |
| `update_prefs` | 自己定义（def） | 616 | — | 1 | 1 | 7 | `local/tests/test_clock_tail.py:48` |
| `validate_plan` | import 进来 | 45 | `signup_plan.validate_plan` | 1 | 1 | 1 | `local/tests/test_runtime_bundle.py:1127` |

### 只被读取、没被打补丁的别名和 import 名，共 12 个

测试经 `app.X` 取这些名字；拆分后要么留再导出，要么改测试的 import。

| 名字 | 种类 | app.py 行号 | 指向 | 读取次数 | 文件数 |
|---|---|---|---|---|---|
| `AppLifecycle` | 别名 | 772 | `_lifecycle_store.AppLifecycle` | 16 | 1 |
| `compute_lifecycle` | 别名 | 767 | `_lifecycle_rules.compute_lifecycle` | 15 | 1 |
| `_ClosingError` | import 进来 | 70 | `domain.errors.ClosingError` | 3 | 2 |
| `compute_lifecycle_v2` | 别名 | 768 | `_lifecycle_rules.compute_lifecycle_v2` | 3 | 1 |
| `_SpawnFailure` | 别名 | 4629 | `_process_tree.SpawnFailure` | 2 | 2 |
| `_advanced_features` | import 进来 | 75 | `infrastructure.advanced_features` | 2 | 1 |
| `_parse_local_time` | 别名 | 748 | `_time_text.parse_local_time` | 2 | 1 |
| `_retry_payload` | 别名 | 4638 | `_retry_rules.retry_payload` | 2 | 1 |
| `subprocess` | import 进来 | 26 | `subprocess` | 2 | 1 |
| `Path` | import 进来 | 41 | `pathlib.Path` | 1 | 1 |
| `_PrefsLockTimeout` | 别名 | 511 | `_prefs_store.PrefsLockTimeout` | 1 | 1 |
| `_win_kernel32` | 别名 | 4633 | `_process_tree.win_kernel32` | 1 | 1 |

### 测试没碰过的别名，共 14 个

只统计了 `local/tests/` 和 `tools/`；`app.py` 自己内部可能在用。

`_ATTEMPT_RE`（4639）、`_PREFS_LOCK`（611）、`_PREFS_LOCK_TIMEOUT_S`（612）、`_ProcessTree`（4630）、`_acquire_prefs_file_lock`（512）、`_atomic_write_prefs`（510）、`_attempts_of`（4636）、`_latest_moment`（749）、`_parse_checkpoint_line`（4634）、`_parse_clock_line`（4635）、`_release_prefs_file_lock`（513）、`_task_deadline`（4627）、`_with_attempts`（4637）、`load_prefs_from`（509）

### 只被读取的自己定义的名字，共 16 个（前 40 个）

| 名字 | 种类 | app.py 行号 | 读取次数 | 文件数 |
|---|---|---|---|---|
| `_check_result` | 自己定义（def） | 4652 | 12 | 1 |
| `_credential_id` | 自己定义（def） | 592 | 5 | 1 |
| `_runtime_check_main` | 自己定义（def） | 4677 | 5 | 1 |
| `main` | 自己定义（def） | 4770 | 5 | 1 |
| `TERMS_VERSION` | 赋值（常量或变量） | 236 | 4 | 4 |
| `_check_hint` | 自己定义（def） | 4657 | 4 | 2 |
| `_component_error` | 自己定义（def） | 375 | 4 | 1 |
| `_parse_retry_line` | 自己定义（def） | 4642 | 4 | 1 |
| `_window_geometry` | 自己定义（def） | 4749 | 4 | 1 |
| `sweep_versions_in_background` | 自己定义（def） | 458 | 4 | 1 |
| `handle_window_close` | 自己定义（def） | 654 | 2 | 1 |
| `resolve_worker_path` | 自己定义（def） | 97 | 2 | 1 |
| `APP_VERSION` | 赋值（常量或变量） | 207 | 1 | 1 |
| `HERE` | 赋值（常量或变量） | 90 | 1 | 1 |
| `_check_reason_line` | 自己定义（def） | 4647 | 1 | 1 |
| `demo_items` | 自己定义（def） | 391 | 1 | 1 |

### 测试用到、但 app.py 模块级找不到的名字，共 0 个

多半是测试自己往 `app` 上挂的，或者在函数里才绑定的；逐个人工看。

—

### 测试直接在 `app.Api` 类上打补丁的属性，共 3 个

| 属性 | 打补丁次数 | 位置（每个文件第一处）|
|---|---|---|
| `Api._run` | 4 | `local/tests/test_runtime_bundle.py:350` |
| `Api._run_plan_task` | 1 | `local/tests/test_runtime_bundle.py:1029` |
| `Api._spawn` | 1 | `local/tests/test_runtime_bundle.py:443` |

### 测试经 app 去补别的模块（`app.模块.名字`），共 19 种

这些补丁依赖 `app.py` 里 import 了那个模块、并且被测代码在 `app.py` 里调用它。代码搬到别的模块后，补丁仍然生效（补的是模块对象本身），但读起来会误导。

| 目标 | 次数 | 位置（每个文件第一处）|
|---|---|---|
| `app.subprocess.Popen` | 7 | `local/tests/test_application_services.py:2585`、`local/tests/test_runtime_bundle.py:988`、`local/tests/test_signup_plan.py:438` |
| `app.threading.Thread` | 7 | `local/tests/test_application_services.py:2942`、`local/tests/test_update_check.py:511` |
| `app.sys.frozen` | 5 | `local/tests/test_application_services.py:2579`、`local/tests/test_runtime_bundle.py:1893` |
| `app.updater.download_installer` | 5 | `local/tests/test_application_services.py:2724`、`local/tests/test_update_check.py:623` |
| `app._advanced_features.feature_ready` | 3 | `local/tests/test_application_services.py:1341` |
| `app._single_instance.SingleInstance` | 3 | `local/tests/test_single_instance.py:519` |
| `app._update_check._fetch_bytes` | 3 | `local/tests/test_release_audit.py:47`、`local/tests/test_update_check.py:787` |
| `app.updater.download_payload` | 3 | `local/tests/test_application_services.py:2727`、`local/tests/test_update_check.py:647` |
| `app._advanced_features.module_available` | 2 | `local/tests/test_application_services.py:1012` |
| `app._tunnel_manager.tailscale_endpoint` | 2 | `local/tests/test_application_services.py:1014` |
| `app.updater.cleanup_download` | 2 | `local/tests/test_update_check.py:651` |
| `app.updater.cleanup_staging` | 2 | `local/tests/test_application_services.py:2941`、`local/tests/test_update_check.py:546` |
| `app.updater.launch_installer` | 2 | `local/tests/test_update_check.py:722` |
| `app.updater.stage_update` | 2 | `local/tests/test_update_check.py:649` |
| `app.AppLifecycle.INTERVAL_S` | 1 | `local/tests/test_session_persistence.py:1333` |
| `app._component_packages.install` | 1 | `local/tests/test_release_audit.py:105` |
| `app.atexit.register` | 1 | `local/tests/test_single_instance.py:518` |
| `app.webview.create_window` | 1 | `local/tests/test_single_instance.py:516` |
| `app.webview.start` | 1 | `local/tests/test_single_instance.py:517` |

## 五、前端全局依赖、跨层引用与可变全局（C2、C1 ② 前端、C1 ④）

复跑：`node design/evidence/2026-11-12/refactor-audit/scripts/globals.mjs`

### 桌面端（local/ui/）

按 `local/ui/index.html` 的加载顺序读了 39 个脚本，顶层定义了 560 个全局名字。

#### 每个文件：定义了什么、依赖谁、被谁依赖

「依赖」= 引用了别的文件定义的名字。行数是物理行。

| 序 | 文件 | 层 | 行数 | 顶层定义（函数 / const / let·var）| 依赖的文件数 | 依赖的名字数 | 被几个文件依赖 | 被引用的名字数 |
|---|---|---|---|---|---|---|---|---|
| 1 | `led.js` | root | 118 | 0 / 0 / 0 | 0 | 0 | 0 | 0 |
| 2 | `state/store.js` | state | 192 | 0 / 10 / 0 | 0 | 0 | 35 | 10 |
| 3 | `state/rounds.js` | state | 85 | 7 / 2 / 0 | 2 | 2 | 3 | 7 |
| 4 | `controllers/bridge.js` | controllers | 35 | 3 / 0 / 0 | 1 | 1 | 13 | 3 |
| 5 | `controllers/refresh.js` | controllers | 614 | 23 / 7 / 2 | 19 | 40 | 10 | 14 |
| 6 | `views/list.js` | views | 449 | 18 / 0 / 0 | 14 | 57 | 13 | 6 |
| 7 | `state/task-display.js` | state | 170 | 7 / 1 / 0 | 6 | 12 | 4 | 6 |
| 8 | `views/plan-panel.js` | views | 1467 | 63 / 2 / 0 | 13 | 49 | 17 | 27 |
| 9 | `controllers/plan.js` | controllers | 503 | 18 / 1 / 0 | 15 | 45 | 3 | 13 |
| 10 | `state/clock.js` | state | 308 | 17 / 11 / 0 | 5 | 7 | 19 | 20 |
| 11 | `views/clock.js` | views | 32 | 1 / 0 / 0 | 3 | 8 | 4 | 1 |
| 12 | `controllers/clock.js` | controllers | 61 | 3 / 0 / 0 | 6 | 12 | 2 | 3 |
| 13 | `state/plan.js` | state | 169 | 13 / 2 / 0 | 8 | 9 | 6 | 13 |
| 14 | `controllers/plan-events.js` | controllers | 129 | 5 / 0 / 0 | 8 | 21 | 4 | 3 |
| 15 | `state/login.js` | state | 141 | 9 / 0 / 0 | 9 | 14 | 5 | 6 |
| 16 | `views/login.js` | views | 173 | 4 / 0 / 1 | 8 | 13 | 17 | 4 |
| 17 | `views/relogin.js` | views | 548 | 34 / 5 / 4 | 9 | 13 | 2 | 4 |
| 18 | `views/clock-pop.js` | views | 155 | 9 / 0 / 0 | 5 | 18 | 6 | 6 |
| 19 | `views/status-cards.js` | views | 204 | 14 / 3 / 0 | 7 | 10 | 5 | 6 |
| 20 | `views/log.js` | views | 29 | 2 / 0 / 0 | 3 | 4 | 2 | 2 |
| 21 | `views/terms.js` | views | 507 | 35 / 2 / 0 | 2 | 5 | 3 | 31 |
| 22 | `controllers/terms.js` | controllers | 492 | 19 / 0 / 1 | 10 | 42 | 13 | 13 |
| 23 | `views/update.js` | views | 187 | 6 / 2 / 0 | 2 | 3 | 2 | 2 |
| 24 | `views/help.js` | views | 67 | 6 / 0 / 0 | 7 | 9 | 5 | 6 |
| 25 | `views/settings.js` | views | 397 | 19 / 1 / 1 | 11 | 13 | 3 | 7 |
| 26 | `views/phone.js` | views | 1252 | 10 / 4 / 0 | 6 | 8 | 3 | 3 |
| 27 | `controllers/update.js` | controllers | 148 | 8 / 0 / 0 | 4 | 5 | 1 | 7 |
| 28 | `controllers/prefs.js` | controllers | 41 | 3 / 0 / 0 | 3 | 4 | 9 | 2 |
| 29 | `state/filters.js` | state | 393 | 25 / 0 / 0 | 8 | 15 | 12 | 21 |
| 30 | `state/conflict.js` | state | 176 | 17 / 2 / 0 | 5 | 8 | 6 | 10 |
| 31 | `views/selection.js` | views | 90 | 6 / 2 / 0 | 7 | 9 | 5 | 5 |
| 32 | `views/conflict-tip.js` | views | 147 | 11 / 0 / 0 | 7 | 11 | 2 | 9 |
| 33 | `controllers/cancel.js` | controllers | 94 | 6 / 0 / 0 | 9 | 11 | 1 | 3 |
| 34 | `state/labels.js` | state | 107 | 10 / 0 / 0 | 5 | 11 | 7 | 10 |
| 35 | `controllers/tick.js` | controllers | 167 | 12 / 0 / 1 | 14 | 37 | 14 | 9 |
| 36 | `state/time.js` | state | 132 | 13 / 3 / 0 | 2 | 2 | 18 | 14 |
| 37 | `views/tour.js` | views | 174 | 13 / 0 / 0 | 3 | 6 | 6 | 12 |
| 38 | `controllers/window.js` | controllers | 276 | 14 / 1 / 0 | 5 | 5 | 1 | 1 |
| 39 | `app.js` | root | 655 | 2 / 5 / 0 | 30 | 128 | 0 | 0 |

#### 同一个名字在两个文件里都有顶层定义：0 处


#### 被 5 个及以上其他文件引用的名字：25 个

| 名字 | 定义位置 | 种类 | 引用它的文件数 | 引用次数 |
|---|---|---|---|---|
| `S` | `local/ui/state/store.js:63` | const | 32 | 1344 |
| `$` | `local/ui/state/store.js:2` | const | 20 | 552 |
| `addLog` | `local/ui/views/login.js:141` | function | 13 | 45 |
| `api` | `local/ui/controllers/bridge.js:6` | function | 13 | 54 |
| `render` | `local/ui/views/list.js:2` | function | 12 | 43 |
| `esc` | `local/ui/state/time.js:123` | function | 11 | 115 |
| `termsLocked` | `local/ui/controllers/terms.js:13` | function | 11 | 28 |
| `bnowS` | `local/ui/state/clock.js:210` | function | 9 | 23 |
| `businessNowMs` | `local/ui/state/clock.js:205` | function | 9 | 23 |
| `msg` | `local/ui/controllers/tick.js:163` | function | 9 | 20 |
| `paintBanners` | `local/ui/views/plan-panel.js:1371` | function | 8 | 22 |
| `refresh` | `local/ui/controllers/refresh.js:122` | function | 8 | 18 |
| `toTs` | `local/ui/state/time.js:22` | function | 8 | 80 |
| `_monoMs` | `local/ui/state/clock.js:18` | const | 7 | 18 |
| `findItem` | `local/ui/state/filters.js:2` | function | 7 | 16 |
| `savePrefs` | `local/ui/controllers/prefs.js:26` | function | 7 | 10 |
| `clockPopOpenNow` | `local/ui/views/clock-pop.js:29` | function | 6 | 12 |
| `hm` | `local/ui/state/time.js:78` | function | 6 | 8 |
| `setResult` | `local/ui/views/login.js:117` | function | 6 | 28 |
| `updateControls` | `local/ui/views/plan-panel.js:1224` | function | 6 | 24 |
| `durText` | `local/ui/state/time.js:48` | function | 5 | 5 |
| `hasBridge` | `local/ui/controllers/bridge.js:2` | function | 5 | 8 |
| `modeOf` | `local/ui/state/labels.js:7` | function | 5 | 8 |
| `paintLogin` | `local/ui/views/login.js:2` | function | 5 | 8 |
| `setBusy` | `local/ui/views/login.js:106` | function | 5 | 17 |

#### 循环依赖（文件级）

**全部引用都算**（函数体里的调用也算一条边）：1 组。

- 33 个文件互相可达：`state/rounds.js`、`controllers/bridge.js`、`controllers/refresh.js`、`views/list.js`、`state/task-display.js`、`views/plan-panel.js`、`controllers/plan.js`、`state/clock.js`、`views/clock.js`、`controllers/clock.js`、`state/plan.js`、`controllers/plan-events.js`、`state/login.js`、`views/login.js`、`views/relogin.js`、`views/clock-pop.js`、`views/status-cards.js`、`views/log.js`、`views/terms.js`、`controllers/terms.js`、`views/update.js`、`views/help.js`、`views/settings.js`、`views/phone.js`、`controllers/prefs.js`、`state/filters.js`、`state/conflict.js`、`views/selection.js`、`views/conflict-tip.js`、`state/labels.js`、`controllers/tick.js`、`state/time.js`、`views/tour.js`

不在任何循环里的文件（6 个）：`led.js`、`state/store.js`、`controllers/update.js`、`controllers/cancel.js`、`controllers/window.js`、`app.js`。

**只算加载时就执行的引用**（不在任何函数体里的顶层代码）：没有循环。

加载时引用的明细（改成 ES Modules 后，这些是必须在求值前就绪的 import）：

| 文件 | 加载时用到的别的文件 | 名字 |
|---|---|---|
| `controllers/tick.js` | `state/clock.js` | `_monoMs` |
| `app.js` | `views/login.js` | `addLog` |
| `app.js` | `controllers/window.js` | `openWindowCloseDialog` |
| `app.js` | `controllers/refresh.js` | `applyActivities`、`refresh` |
| `app.js` | `controllers/plan.js` | `handleDone`、`startPlan`、`modifyPlan`、`reselectFailed`、`finishResult`、`stopPlan`、`closeStopAsk`、`confirmStopPlan` |
| `app.js` | `state/plan.js` | `handlePlan`、`handleTask` |
| `app.js` | `controllers/plan-events.js` | `handlePlanDone` |
| `app.js` | `controllers/tick.js` | `receiveSecondOpen`、`msg`、`tick` |
| `app.js` | `controllers/update.js` | `receiveUpdate`、`checkUpdate`、`startDownload`、`confirmDownload`、`launchInstaller`、`cancelDownload` |
| `app.js` | `views/relogin.js` | `receiveReloginState`、`loginEntry`、`wireRelogin` |
| `app.js` | `views/plan-panel.js` | `bindPlaceToggle`、`setPlanOpen`、`applyBand` |
| `app.js` | `state/store.js` | `$`、`S` |
| `app.js` | `views/selection.js` | `setFilter`、`setFilterOpen` |
| `app.js` | `views/conflict-tip.js` | `tipLater`、`tipStay` |
| `app.js` | `views/help.js` | `showHelp`、`replayTourFrom` |
| `app.js` | `views/terms.js` | `applyTermsFooter` |
| `app.js` | `controllers/terms.js` | `ensureLicenseText`、`acceptTerms`、`declineTerms`、`openTerms`、`recheckTerms`、`openTermsReader` |
| `app.js` | `views/status-cards.js` | `wireStatusCards` |
| `app.js` | `views/settings.js` | `wireSettings` |
| `app.js` | `controllers/bridge.js` | `api` |
| `app.js` | `views/log.js` | `copyLog`、`setLogOpen` |
| `app.js` | `state/filters.js` | `clearSelection` |
| `app.js` | `controllers/prefs.js` | `savePrefs` |
| `app.js` | `views/tour.js` | `tourSkip`、`tourGuardClick` |

#### 两个文件直接互相引用：32 对（列名字数最多的 25 对）

| 文件 A | 文件 B | A 用 B 的名字数 | B 用 A 的名字数 |
|---|---|---|---|
| `state/clock.js` | `views/clock-pop.js` | 3 | 12 |
| `views/list.js` | `state/filters.js` | 12 | 1 |
| `views/plan-panel.js` | `state/filters.js` | 10 | 1 |
| `state/task-display.js` | `views/plan-panel.js` | 4 | 6 |
| `views/plan-panel.js` | `state/clock.js` | 6 | 1 |
| `views/plan-panel.js` | `state/labels.js` | 6 | 1 |
| `state/clock.js` | `views/clock.js` | 1 | 6 |
| `state/plan.js` | `controllers/plan-events.js` | 1 | 6 |
| `controllers/terms.js` | `views/tour.js` | 5 | 1 |
| `state/filters.js` | `state/labels.js` | 5 | 1 |
| `controllers/refresh.js` | `state/plan.js` | 3 | 2 |
| `controllers/refresh.js` | `controllers/plan-events.js` | 1 | 4 |
| `controllers/refresh.js` | `controllers/tick.js` | 3 | 2 |
| `views/list.js` | `controllers/tick.js` | 2 | 3 |
| `controllers/plan.js` | `state/plan.js` | 4 | 1 |
| `controllers/refresh.js` | `views/plan-panel.js` | 2 | 2 |
| `controllers/refresh.js` | `controllers/terms.js` | 3 | 1 |
| `views/list.js` | `state/clock.js` | 3 | 1 |
| `views/plan-panel.js` | `state/plan.js` | 3 | 1 |
| `controllers/clock.js` | `views/clock-pop.js` | 3 | 1 |
| `views/settings.js` | `views/phone.js` | 1 | 3 |
| `state/conflict.js` | `state/labels.js` | 1 | 3 |
| `views/list.js` | `state/plan.js` | 2 | 1 |
| `views/list.js` | `views/selection.js` | 2 | 1 |
| `views/list.js` | `views/conflict-tip.js` | 1 | 2 |

#### 层与层之间的引用（名字数，去重后）

| 从 ＼ 到 | state | views | controllers | root |
|---|---|---|---|---|
| state | 28 | 19 | 6 | 0 |
| views | 81 | 39 | 15 | 0 |
| controllers | 50 | 66 | 23 | 0 |
| root | 18 | 58 | 52 | 0 |

#### 越界引用：state/ 用了 views/、controllers/ 或根目录的名字

去重后 25 个名字，出现在 7 个 state 文件里，共 62 处引用（下表一行是一个「文件 × 名字」，32 行）。

| 位置（引用的行）| 用了 | 定义在 | 层 |
|---|---|---|---|
| `local/ui/state/task-display.js:58,58` | `verifiedSigned` | `local/ui/views/plan-panel.js:614` | views |
| `local/ui/state/task-display.js:100,101` | `hmsDay` | `local/ui/views/plan-panel.js:139` | views |
| `local/ui/state/task-display.js:104` | `submittingDetail` | `local/ui/views/plan-panel.js:1102` | views |
| `local/ui/state/task-display.js:148,150` | `effectiveRetryDeadline` | `local/ui/views/plan-panel.js:1188` | views |
| `local/ui/state/clock.js:78,114,134,159` | `paintClockStatus` | `local/ui/views/clock.js:2` | views |
| `local/ui/state/clock.js:79,115,135,160` | `clockPopOpenNow` | `local/ui/views/clock-pop.js:29` | views |
| `local/ui/state/clock.js:79,115,135,160` | `renderClockPop` | `local/ui/views/clock-pop.js:65` | views |
| `local/ui/state/clock.js:80,136,161` | `updateControls` | `local/ui/views/plan-panel.js:1224` | views |
| `local/ui/state/clock.js:81,137,162` | `render` | `local/ui/views/list.js:2` | views |
| `local/ui/state/clock.js:116` | `paintClockPopFeedback` | `local/ui/views/clock-pop.js:142` | views |
| `local/ui/state/plan.js:51,62` | `setBusy` | `local/ui/views/login.js:106` | views |
| `local/ui/state/plan.js:78` | `noteStartedFromPhone` | `local/ui/controllers/plan.js:336` | controllers |
| `local/ui/state/plan.js:80,106` | `render` | `local/ui/views/list.js:2` | views |
| `local/ui/state/plan.js:103` | `noteSignedTasks` | `local/ui/controllers/refresh.js:398` | controllers |
| `local/ui/state/plan.js:103` | `scheduleSignedRefresh` | `local/ui/controllers/refresh.js:451` | controllers |
| `local/ui/state/plan.js:104` | `showTaskResult` | `local/ui/controllers/plan-events.js:80` | controllers |
| `local/ui/state/plan.js:114,123,128` | `selectionSignature` | `local/ui/views/plan-panel.js:901` | views |
| `local/ui/state/login.js:29,29` | `reloginAutoLive` | `local/ui/views/relogin.js:23` | views |
| `local/ui/state/login.js:33,61` | `numOrNull` | `local/ui/controllers/tick.js:162` | controllers |
| `local/ui/state/login.js:70,137` | `paintLogin` | `local/ui/views/login.js:2` | views |
| `local/ui/state/login.js:72` | `paintRail` | `local/ui/views/list.js:408` | views |
| `local/ui/state/login.js:73` | `paintSelected` | `local/ui/views/plan-panel.js:4` | views |
| `local/ui/state/login.js:74` | `paintBoardActions` | `local/ui/views/plan-panel.js:244` | views |
| `local/ui/state/login.js:76,139` | `refreshLoginEmptyState` | `local/ui/views/list.js:276` | views |
| `local/ui/state/login.js:138` | `paintClockStatus` | `local/ui/views/clock.js:2` | views |
| `local/ui/state/login.js:140` | `render` | `local/ui/views/list.js:2` | views |
| `local/ui/state/filters.js:307,307` | `verifiedSigned` | `local/ui/views/plan-panel.js:614` | views |
| `local/ui/state/filters.js:343` | `termsLocked` | `local/ui/controllers/terms.js:13` | controllers |
| `local/ui/state/filters.js:362,372,382,392` | `render` | `local/ui/views/list.js:2` | views |
| `local/ui/state/filters.js:381,391` | `setResult` | `local/ui/views/login.js:117` | views |
| `local/ui/state/conflict.js:147` | `termsLocked` | `local/ui/controllers/terms.js:13` | controllers |
| `local/ui/state/labels.js:61,61` | `verifiedSigned` | `local/ui/views/plan-panel.js:614` | views |

#### 越界引用：views/ 用了 controllers/ 或根目录的名字

去重后 15 个名字，出现在 13 个 views 文件里，共 80 处引用（下表一行是一个名字）。

| 名字 | 定义在 | 用它的 views 文件（行）| 次数 |
|---|---|---|---|
| `api` | `local/ui/controllers/bridge.js:6` | `views/relogin.js`:355,371,371,385,413；`views/settings.js`:110,183,322,338；`views/phone.js`:200,219,745,770,798… | 24 |
| `termsLocked` | `local/ui/controllers/terms.js:13` | `views/list.js`:155,332,335,397；`views/plan-panel.js`:41,257,320,373,428…；`views/login.js`:80；`views/relogin.js`:294,294,319,319；`views/status-cards.js`:108；`views/tour.js`:25,25 | 21 |
| `savePrefs` | `local/ui/controllers/prefs.js:26` | `views/log.js`:8；`views/help.js`:15；`views/settings.js`:69；`views/selection.js`:44,50；`views/conflict-tip.js`:118 | 6 |
| `doLogin` | `local/ui/controllers/plan.js:402` | `views/relogin.js`:294,319,339,514,515 | 5 |
| `refresh` | `local/ui/controllers/refresh.js:122` | `views/plan-panel.js`:624；`views/relogin.js`:438,438；`views/phone.js`:198 | 4 |
| `msg` | `local/ui/controllers/tick.js:163` | `views/relogin.js`:373,387,415；`views/settings.js`:112 | 4 |
| `doCheck` | `local/ui/controllers/tick.js:102` | `views/relogin.js`:437,437；`views/status-cards.js`:196 | 3 |
| `numOrNull` | `local/ui/controllers/tick.js:162` | `views/clock-pop.js`:7,8,9 | 3 |
| `termsAccepted` | `local/ui/controllers/terms.js:2` | `views/settings.js`:93,93 | 2 |
| `ingestTerms` | `local/ui/controllers/terms.js:62` | `views/settings.js`:122,122 | 2 |
| `savePrefsNow` | `local/ui/controllers/prefs.js:34` | `views/tour.js`:92,97 | 2 |
| `tick` | `local/ui/controllers/tick.js:4` | `views/list.js`:16 | 1 |
| `listErrorCopy` | `local/ui/controllers/tick.js:140` | `views/list.js`:308 | 1 |
| `runtimeErrorCopy` | `local/ui/controllers/refresh.js:383` | `views/plan-panel.js`:1375 | 1 |
| `resyncClock` | `local/ui/controllers/clock.js:3` | `views/clock-pop.js`:138 | 1 |

其中 views/ 直接发桥接请求（调 `api(…)`）的文件 3 个，共 24 处：`views/relogin.js` 5 处、`views/settings.js` 4 处、`views/phone.js` 15 处。

#### 状态仓库 `S` 的写入：441 处，分布在 27 个文件

按 `S` 的一级字段汇总。「写入」含赋值、自增、`delete`、`Object.assign` 和容器的变更方法（`.set()` `.add()` `.push()` 等）。

| 字段 | 写入处数 | state/ | views/ | controllers/ | 根目录 | 写它的文件 |
|---|---|---|---|---|---|---|
| `S.terms` | 90 | 0 | 0 | 81 | 9 | `controllers/terms.js`、`app.js` |
| `S.login` | 51 | 19 | 3 | 27 | 2 | `controllers/refresh.js`、`controllers/plan.js`、`state/login.js`、`views/login.js`、`views/relogin.js`、`app.js` |
| `S.plan` | 29 | 10 | 0 | 19 | 0 | `controllers/refresh.js`、`controllers/plan.js`、`state/plan.js`、`controllers/plan-events.js`、`state/filters.js` |
| `S.update` | 18 | 0 | 3 | 15 | 0 | `views/update.js`、`controllers/update.js` |
| `S.round` | 17 | 8 | 0 | 9 | 0 | `state/rounds.js`、`controllers/refresh.js` |
| `S.relogin` | 17 | 0 | 17 | 0 | 0 | `views/relogin.js` |
| `S.startRequest` | 15 | 0 | 0 | 15 | 0 | `controllers/plan.js` |
| `S.cancel` | 14 | 0 | 0 | 14 | 0 | `controllers/refresh.js`、`controllers/cancel.js` |
| `S.tour` | 14 | 0 | 12 | 0 | 2 | `views/tour.js`、`app.js` |
| `S.runtime` | 13 | 0 | 0 | 8 | 5 | `controllers/refresh.js`、`app.js` |
| `S.selected` | 12 | 3 | 0 | 9 | 0 | `controllers/refresh.js`、`controllers/plan.js`、`controllers/plan-events.js`、`state/filters.js` |
| `S.listState` | 9 | 0 | 0 | 8 | 1 | `controllers/refresh.js`、`app.js` |
| `S.listError` | 8 | 0 | 0 | 8 | 0 | `controllers/refresh.js` |
| `S.starting` | 8 | 0 | 0 | 8 | 0 | `controllers/plan.js` |
| `S.selectionNotice` | 8 | 5 | 1 | 2 | 0 | `controllers/plan.js`、`controllers/plan-events.js`、`state/filters.js`、`views/selection.js` |
| `S.stopping` | 7 | 0 | 0 | 7 | 0 | `controllers/plan.js`、`controllers/plan-events.js` |
| `S.tip` | 6 | 0 | 6 | 0 | 0 | `views/conflict-tip.js` |
| `S.businessClock` | 5 | 0 | 0 | 4 | 1 | `controllers/clock.js`、`app.js` |
| `S.filter` | 4 | 0 | 2 | 2 | 0 | `controllers/refresh.js`、`views/selection.js`、`views/conflict-tip.js` |
| `S.editing` | 4 | 2 | 0 | 2 | 0 | `controllers/plan.js`、`state/plan.js`、`state/filters.js` |
| `S.autoLogin` | 4 | 3 | 1 | 0 | 0 | `state/login.js`、`views/relogin.js` |
| `S.licenseText` | 4 | 0 | 0 | 4 | 0 | `controllers/terms.js` |
| `S.savePending` | 4 | 0 | 0 | 4 | 0 | `controllers/prefs.js` |
| `S.saveFailures` | 4 | 0 | 0 | 4 | 0 | `controllers/prefs.js` |
| `S.prefs` | 3 | 0 | 0 | 3 | 0 | `controllers/refresh.js`、`controllers/prefs.js` |
| `S.confirmed` | 3 | 0 | 0 | 3 | 0 | `controllers/refresh.js`、`controllers/cancel.js` |
| `S.rowStates` | 3 | 0 | 3 | 0 | 0 | `views/list.js` |
| `S.resultSel` | 3 | 3 | 0 | 0 | 0 | `state/plan.js` |
| `S.statusCard` | 3 | 0 | 3 | 0 | 0 | `views/status-cards.js` |
| `S.online` | 3 | 0 | 0 | 0 | 3 | `app.js` |
| `S.logOpen` | 2 | 0 | 1 | 1 | 0 | `controllers/refresh.js`、`views/log.js` |
| `S.filterOpen` | 2 | 0 | 1 | 1 | 0 | `controllers/refresh.js`、`views/selection.js` |
| `S.retryPolicy` | 2 | 0 | 0 | 1 | 1 | `controllers/refresh.js`、`app.js` |
| `S.maxPlanGen` | 2 | 1 | 0 | 1 | 0 | `controllers/refresh.js`、`state/plan.js` |
| `S.items` | 2 | 0 | 0 | 2 | 0 | `controllers/refresh.js` |
| `S.byId` | 2 | 0 | 0 | 2 | 0 | `controllers/refresh.js` |
| `S.rowEls` | 2 | 0 | 2 | 0 | 0 | `views/list.js` |
| `S.rowCancel` | 2 | 0 | 2 | 0 | 0 | `views/list.js` |
| `S.verifyAsked` | 2 | 0 | 2 | 0 | 0 | `views/plan-panel.js` |
| `S.resultOpen` | 2 | 2 | 0 | 0 | 0 | `state/plan.js` |
| `S.recheckPending` | 2 | 0 | 0 | 2 | 0 | `controllers/plan-events.js` |
| `S.recentLogs` | 2 | 0 | 2 | 0 | 0 | `views/login.js` |
| `S.clockPopOpen` | 2 | 0 | 2 | 0 | 0 | `views/clock-pop.js` |
| `S.settingsOpen` | 2 | 0 | 2 | 0 | 0 | `views/settings.js` |
| `S.saveBusy` | 2 | 0 | 0 | 2 | 0 | `controllers/prefs.js` |
| `S.saveWarned` | 2 | 0 | 0 | 2 | 0 | `controllers/prefs.js` |
| `S.saveTimer` | 2 | 0 | 0 | 2 | 0 | `controllers/prefs.js` |
| `S.flashId` | 2 | 0 | 2 | 0 | 0 | `views/conflict-tip.js` |
| `S.sleepGap` | 2 | 0 | 0 | 1 | 1 | `controllers/tick.js`、`app.js` |
| `S.secondOpen` | 2 | 0 | 0 | 1 | 1 | `controllers/tick.js`、`app.js` |
| `S.demo` | 2 | 0 | 0 | 0 | 2 | `app.js` |
| `S.listAtMono` | 1 | 0 | 0 | 1 | 0 | `controllers/refresh.js` |
| `S.preWarnCount` | 1 | 0 | 1 | 0 | 0 | `views/plan-panel.js` |
| `S.band` | 1 | 0 | 1 | 0 | 0 | `views/plan-panel.js` |
| `S.short` | 1 | 0 | 1 | 0 | 0 | `views/plan-panel.js` |
| `S.planOpen` | 1 | 0 | 1 | 0 | 0 | `views/plan-panel.js` |
| `S.clockTimer` | 1 | 0 | 0 | 1 | 0 | `controllers/clock.js` |
| `S.busy` | 1 | 0 | 1 | 0 | 0 | `views/login.js` |
| `S.clock` | 1 | 0 | 1 | 0 | 0 | `views/clock-pop.js` |
| `S.sleepWindow` | 1 | 0 | 0 | 1 | 0 | `controllers/tick.js` |
| `S.lastRunPhase` | 1 | 0 | 0 | 1 | 0 | `controllers/tick.js` |
| `S.closeAsk` | 1 | 0 | 0 | 1 | 0 | `controllers/window.js` |
| `S.lifecycle` | 1 | 0 | 0 | 0 | 1 | `app.js` |
| `S.migration` | 1 | 0 | 0 | 0 | 1 | `app.js` |
| `S.retryOptions` | 1 | 0 | 0 | 0 | 1 | `app.js` |
| `S.advanced` | 1 | 0 | 0 | 0 | 1 | `app.js` |
| `S.migrationDismissed` | 1 | 0 | 0 | 0 | 1 | `app.js` |

##### `S` 的字段：字面量里声明了 45 个，别处写入但没有声明的 22 个

没有声明、运行中才挂上去的字段（读 `state/store.js` 看不到它们）：

| 字段 | 第一处写入 | 写入处数 |
|---|---|---|
| `S.advanced` | `local/ui/app.js:44` | 1 |
| `S.autoLogin` | `local/ui/state/login.js:27` | 4 |
| `S.band` | `local/ui/views/plan-panel.js:1306` | 1 |
| `S.clockPopOpen` | `local/ui/views/clock-pop.js:36` | 2 |
| `S.clockTimer` | `local/ui/controllers/clock.js:57` | 1 |
| `S.closeAsk` | `local/ui/controllers/window.js:173` | 1 |
| `S.editing` | `local/ui/controllers/plan.js:90` | 4 |
| `S.listAtMono` | `local/ui/controllers/refresh.js:504` | 1 |
| `S.planOpen` | `local/ui/views/plan-panel.js:1319` | 1 |
| `S.preWarnCount` | `local/ui/views/plan-panel.js:339` | 1 |
| `S.relogin` | `local/ui/views/relogin.js:198` | 17 |
| `S.resultOpen` | `local/ui/state/plan.js:113` | 2 |
| `S.resultSel` | `local/ui/state/plan.js:114` | 3 |
| `S.rowCancel` | `local/ui/views/list.js:27` | 2 |
| `S.saveBusy` | `local/ui/controllers/prefs.js:6` | 2 |
| `S.saveFailures` | `local/ui/controllers/prefs.js:9` | 4 |
| `S.saveWarned` | `local/ui/controllers/prefs.js:10` | 2 |
| `S.settingsOpen` | `local/ui/views/settings.js:16` | 2 |
| `S.short` | `local/ui/views/plan-panel.js:1307` | 1 |
| `S.sleepWindow` | `local/ui/controllers/tick.js:13` | 1 |
| `S.statusCard` | `local/ui/views/status-cards.js:22` | 3 |
| `S.verifyAsked` | `local/ui/views/plan-panel.js:622` | 2 |

声明了、但脚本没数到写入的字段（只在声明时给初值，或经别名修改）：没有。

##### views/ 里直接写 `S` 的位置：73 处

| 位置 | 写了什么 | 方式 | 所在函数 |
|---|---|---|---|
| `local/ui/views/list.js:26` | `S.rowEls` | `=` | `paintList` |
| `local/ui/views/list.js:27` | `S.rowCancel` | `=` | `paintList` |
| `local/ui/views/list.js:33` | `S.rowStates` | `=` | `paintList` |
| `local/ui/views/list.js:42` | `S.rowStates` | `=` | `paintList` |
| `local/ui/views/list.js:50` | `S.rowStates` | `=` | `paintList` |
| `local/ui/views/list.js:52` | `S.rowCancel` | `.set()` | `paintList > <anonymous@52>` |
| `local/ui/views/list.js:55` | `S.rowEls` | `.set()` | `paintList > <anonymous@53>` |
| `local/ui/views/plan-panel.js:339` | `S.preWarnCount` | `=` | `paintChecks` |
| `local/ui/views/plan-panel.js:622` | `S.verifyAsked` | `=` | `verifyTask` |
| `local/ui/views/plan-panel.js:623` | `S.verifyAsked` | `.add()` | `verifyTask` |
| `local/ui/views/plan-panel.js:1306` | `S.band` | `=` | `applyBand` |
| `local/ui/views/plan-panel.js:1307` | `S.short` | `=` | `applyBand` |
| `local/ui/views/plan-panel.js:1319` | `S.planOpen` | `=` | `setPlanOpen` |
| `local/ui/views/login.js:88` | `S.login.view` | `=` | `paintLogin` |
| `local/ui/views/login.js:107` | `S.busy` | `=` | `setBusy` |
| `local/ui/views/login.js:147` | `S.recentLogs` | `.push()` | `addLog` |
| `local/ui/views/login.js:148` | `S.recentLogs` | `.shift()` | `addLog` |
| `local/ui/views/relogin.js:198` | `S.relogin.step` | `=` | `reloginStep` |
| `local/ui/views/relogin.js:240` | `S.relogin.way` | `=` | `reloginResetForm` |
| `local/ui/views/relogin.js:241` | `S.relogin.fromLogin` | `=` | `reloginResetForm` |
| `local/ui/views/relogin.js:267` | `S.relogin.challengeId` | `=` | `reloginShowChallenge` |
| `local/ui/views/relogin.js:296` | `S.relogin` | `=` | `openRelogin` |
| `local/ui/views/relogin.js:303` | `S.relogin.flowId` | `=` | `openRelogin` |
| `local/ui/views/relogin.js:321` | `S.relogin` | `=` | `openLogin` |
| `local/ui/views/relogin.js:331` | `S.relogin.way` | `=` | `reloginPickWay` |
| `local/ui/views/relogin.js:346` | `S.relogin` | `=` | `closeRelogin` |
| `local/ui/views/relogin.js:377` | `S.relogin.flowId` | `=` | `beginRelogin` |
| `local/ui/views/relogin.js:391` | `S.relogin.flowId` | `=` | `autoReloginOnce` |
| `local/ui/views/relogin.js:400` | `S.relogin.fromLogin` | `=` | `submitReloginForm` |
| `local/ui/views/relogin.js:458` | `S.login.handoff` | `=` | `receiveReloginState` |
| `local/ui/views/relogin.js:459` | `S.login.handoff` | `=` | `receiveReloginState` |
| `local/ui/views/relogin.js:466` | `S.autoLogin` | `=` | `receiveReloginState` |
| `local/ui/views/relogin.js:480` | `S.relogin.flowId` | `=` | `receiveReloginState` |
| `local/ui/views/relogin.js:494` | `S.relogin.flowId` | `=` | `receiveReloginState` |
| `local/ui/views/relogin.js:502` | `S.relogin.flowId` | `=` | `receiveReloginState` |
| `local/ui/views/relogin.js:516` | `S.relogin.fromLogin` | `=` | `wireRelogin > <anonymous@516>` |
| `local/ui/views/relogin.js:517` | `S.relogin.fromLogin` | `=` | `wireRelogin > <anonymous@517>` |
| `local/ui/views/clock-pop.js:5` | `S.clock` | `=` | `applyClock` |
| `local/ui/views/clock-pop.js:36` | `S.clockPopOpen` | `=` | `closeClockPop` |
| `local/ui/views/clock-pop.js:46` | `S.clockPopOpen` | `=` | `toggleClockPop` |
| `local/ui/views/status-cards.js:22` | `S.statusCard` | `=` | `openStatusCard` |
| `local/ui/views/status-cards.js:38` | `S.statusCard` | `=` | `closeStatusCards` |
| `local/ui/views/status-cards.js:184` | `S.statusCard.pinned` | `=` | `wireStatusCards > <anonymous@152> > <anonymous@176>` |
| `local/ui/views/log.js:3` | `S.logOpen` | `=` | `setLogOpen` |
| `local/ui/views/update.js:169` | `S.update.paintedState` | `=` | `paintUpdate` |
| `local/ui/views/update.js:171` | `S.update.guardUntil` | `=` | `paintUpdate` |
| `local/ui/views/update.js:173` | `S.update.guardTimer` | `=` | `paintUpdate` |
| `local/ui/views/settings.js:16` | `S.settingsOpen` | `=` | `openSettings` |
| `local/ui/views/settings.js:42` | `S.settingsOpen` | `=` | `closeSettings` |
| `local/ui/views/selection.js:43` | `S.filterOpen` | `=` | `setFilterOpen` |
| `local/ui/views/selection.js:49` | `S.filter[…]` | `=` | `setFilter` |
| `local/ui/views/selection.js:83` | `S.selectionNotice` | `=` | `showPlanError` |
| `local/ui/views/conflict-tip.js:31` | `S.tip.id` | `=` | `tipOpen` |
| `local/ui/views/conflict-tip.js:40` | `S.tip.openTimer` | `=` | `tipSoon` |
| `local/ui/views/conflict-tip.js:47` | `S.tip.id` | `=` | `tipClose` |
| `local/ui/views/conflict-tip.js:56` | `S.tip.timer` | `=` | `tipLater` |
| `local/ui/views/conflict-tip.js:66` | `S.tip.id` | `=` | `paintTip` |
| `local/ui/views/conflict-tip.js:112` | `S.filter` | `=` | `tipGoSigned` |
| `local/ui/views/conflict-tip.js:120` | `S.flashId` | `=` | `tipGoSigned` |
| `local/ui/views/conflict-tip.js:125` | `S.tip.flashTimer` | `=` | `tipGoSigned` |
| `local/ui/views/conflict-tip.js:126` | `S.flashId` | `=` | `tipGoSigned > <anonymous@125>` |
| `local/ui/views/tour.js:19` | `S.tour.autoPending` | `=` | `requestAutoTour` |
| `local/ui/views/tour.js:28` | `S.tour.autoPending` | `=` | `maybeStartTour` |
| `local/ui/views/tour.js:56` | `S.tour.restoreFocus` | `=` | `startTour` |
| `local/ui/views/tour.js:57` | `S.tour.open` | `=` | `startTour` |
| `local/ui/views/tour.js:58` | `S.tour.paused` | `=` | `startTour` |
| `local/ui/views/tour.js:59` | `S.tour.step` | `=` | `startTour` |
| `local/ui/views/tour.js:84` | `S.tour.open` | `=` | `tourClose` |
| `local/ui/views/tour.js:85` | `S.tour.paused` | `=` | `tourClose` |
| `local/ui/views/tour.js:88` | `S.tour.restoreFocus` | `=` | `tourClose` |
| `local/ui/views/tour.js:102` | `S.tour.paused` | `=` | `tourPauseNow` |
| `local/ui/views/tour.js:108` | `S.tour.paused` | `=` | `tourResumeNow` |
| `local/ui/views/tour.js:125` | `S.tour.rowEl` | `=` | `paintTour` |

#### `S` 以外的可变全局：13 个

顶层的 `let` / `var`，以及被别处改写了属性或内容的顶层 `const` 对象。

| 名字 | 定义位置 | 种类 | 写入处数 | 写的位置（文件:行 路径 方式）| 读它的文件 |
|---|---|---|---|---|---|
| `confirmedRefreshTimer` | `local/ui/controllers/refresh.js:391` | let | 2 | `controllers/refresh.js:453` `confirmedRefreshTimer` `=`；`controllers/refresh.js:454` `confirmedRefreshTimer` `=` | `controllers/refresh.js`（本文件 4 处） |
| `autoRefreshState` | `local/ui/controllers/refresh.js:526` | const | 6 | `controllers/refresh.js:147` `autoRefreshState.attemptMono` `=`；`controllers/refresh.js:507` `autoRefreshState.fails` `=`；`controllers/refresh.js:509` `autoRefreshState.okLabel` `=`；`controllers/refresh.js:542` `autoRefreshState.fails` `+=`；`controllers/refresh.js:601` `autoRefreshState.attemptMono` `=`；`controllers/refresh.js:612` `autoRefreshState.attemptMono` `=` | `controllers/refresh.js`（本文件 11 处） |
| `autoRefreshTimer` | `local/ui/controllers/refresh.js:527` | let | 1 | `controllers/refresh.js:613` `autoRefreshTimer` `=` | `controllers/refresh.js`（本文件 2 处） |
| `termsUnknownLogged` | `local/ui/controllers/terms.js:39` | let | 2 | `controllers/terms.js:51` `termsUnknownLogged` `=`；`controllers/terms.js:76` `termsUnknownLogged` `=` | `controllers/terms.js`（本文件 3 处） |
| `lastBeat` | `local/ui/controllers/tick.js:2` | let | 1 | `controllers/tick.js:8` `lastBeat` `=` | `controllers/tick.js`（本文件 2 处） |
| `resultTimer` | `local/ui/views/login.js:115` | let | 2 | `views/login.js:120` `resultTimer` `=`；`views/login.js:138` `resultTimer` `=` | `views/login.js`（本文件 3 处） |
| `PhonePanel` | `local/ui/views/phone.js:154` | const | 96 | `views/phone.js:201` `PhonePanel.state` `=`；`views/phone.js:201` `PhonePanel.state` `Object.assign`；`views/phone.js:220` `PhonePanel.location` `=`；`views/phone.js:223` `PhonePanel.location` `=`；`views/phone.js:243` `PhonePanel.pollTicks` `=`；`views/phone.js:244` `PhonePanel.pollTimer` `=`；`views/phone.js:247` `PhonePanel.pollTicks` `+=`；`views/phone.js:259` `PhonePanel.pollTimer` `=`；`views/phone.js:264` `PhonePanel.tickTimer` `=`；`views/phone.js:266` `PhonePanel.codeLeft` `-=` 等 96 处 | `views/phone.js`（本文件 272 处）、`views/help.js` |
| `reloginRefreshedFlow` | `local/ui/views/relogin.js:13` | let | 1 | `views/relogin.js:436` `reloginRefreshedFlow` `=` | `views/relogin.js`（本文件 2 处） |
| `reloginRelay` | `local/ui/views/relogin.js:17` | let | 1 | `views/relogin.js:444` `reloginRelay` `=` | `views/relogin.js`（本文件 10 处） |
| `reloginHandoffSeen` | `local/ui/views/relogin.js:19` | let | 2 | `views/relogin.js:448` `reloginHandoffSeen` `=`；`views/relogin.js:455` `reloginHandoffSeen` `=` | `views/relogin.js`（本文件 3 处） |
| `reloginBrowserWatch` | `local/ui/views/relogin.js:245` | let | 2 | `views/relogin.js:248` `reloginBrowserWatch` `=`；`views/relogin.js:253` `reloginBrowserWatch` `=` | `views/relogin.js`（本文件 4 处） |
| `termsWithdrawAskOpen` | `local/ui/views/settings.js:78` | let | 4 | `views/settings.js:47` `termsWithdrawAskOpen` `=`；`views/settings.js:114` `termsWithdrawAskOpen` `=`；`views/settings.js:365` `termsWithdrawAskOpen` `=`；`views/settings.js:372` `termsWithdrawAskOpen` `=` | `views/settings.js`（本文件 5 处） |
| `OcrPanel` | `local/ui/views/settings.js:142` | const | 17 | `views/settings.js:184` `OcrPanel.location` `=`；`views/settings.js:187` `OcrPanel.location` `=`；`views/settings.js:210` `OcrPanel.note` `=`；`views/settings.js:212` `OcrPanel.lastDownload` `=`；`views/settings.js:316` `OcrPanel.busy` `=`；`views/settings.js:317` `OcrPanel.error` `=`；`views/settings.js:318` `OcrPanel.note` `=`；`views/settings.js:326` `OcrPanel.busy` `=`；`views/settings.js:328` `OcrPanel.note` `=`；`views/settings.js:329` `OcrPanel.error` `=` 等 17 处 | `views/settings.js`（本文件 21 处）、`views/phone.js` |

其中由 views/ 文件写入的有 125 处，涉及 8 个名字：`resultTimer`、`reloginRefreshedFlow`、`reloginRelay`、`reloginHandoffSeen`、`reloginBrowserWatch`、`termsWithdrawAskOpen`、`OcrPanel`、`PhonePanel`。

##### `OcrPanel` 按字段：5 个字段，17 处写入

| 字段 | 写入处数 | 写它的函数（行）|
|---|---|---|
| `OcrPanel.note` | 6 | `paintOcrDownload`:210、`enableOcr`:318,328、`installComponent`:813、`downloadComponent`:1027、`cancelComponent`:1049 |
| `OcrPanel.error` | 6 | `enableOcr`:317,329、`openOcrDir`:343、`installComponent`:814、`downloadComponent`:1028、`cancelComponent`:1050 |
| `OcrPanel.location` | 2 | `ocrLoadLocation`:184,187 |
| `OcrPanel.busy` | 2 | `enableOcr`:316,326 |
| `OcrPanel.lastDownload` | 1 | `paintOcrDownload`:212 |

##### `PhonePanel` 按字段：26 个字段，96 处写入

| 字段 | 写入处数 | 写它的函数（行）|
|---|---|---|
| `PhonePanel.notes` | 26 | `installComponent`:810,811、`enableFeature`:848,858,859、`toggleStart`:868,869,874,876…、`toggleStop`:892,897,899,900…、`addPairing`:932、`openComponentDir`:963,964,965、`copyAddress`:999、`downloadComponent`:1014,1031 等 11 个函数 |
| `PhonePanel.busy` | 10 | `enableFeature`:847,856、`toggleStart`:866,883、`toggleStop`:890,906、`downloadComponent`:1013,1022、`saveCredentials`:1099,1111 |
| `PhonePanel.credNote` | 6 | `goSaveCredentials`:940、`saveCredentials`:1115,1118、`openCredForm`:1127、`askClearCredentials`:1151、`clearCredentials`:1173 |
| `PhonePanel.stopAsk` | 4 | `paintPhoneAccess`:467、`askStop`:913、`cancelStop`:918、`confirmStop`:923 |
| `PhonePanel.addPair` | 4 | `paintPhoneAccess`:468,627、`toggleStart`:877、`addPairing`:930 |
| `PhonePanel.verified` | 4 | `openComponents`:717、`inspectComponent`:762,772、`installComponent`:804 |
| `PhonePanel.pending` | 4 | `toggleStart`:867,882、`toggleStop`:891,905 |
| `PhonePanel.credForm` | 4 | `goSaveCredentials`:944、`saveCredentials`:1114、`openCredForm`:1126、`cancelCredForm`:1140 |
| `PhonePanel.picked` | 3 | `openComponents`:716、`inspectComponent`:761、`installComponent`:803 |
| `PhonePanel.credNoteTone` | 3 | `saveCredentials`:1116,1119、`clearCredentials`:1174 |
| `PhonePanel.clearConfirm` | 3 | `askClearCredentials`:1150、`cancelClearCredentials`:1156、`confirmClearCredentials`:1161 |
| `PhonePanel.state` | 2 | `refresh`:201,201 |
| `PhonePanel.location` | 2 | `loadLocation`:220,223 |
| `PhonePanel.pollTicks` | 2 | `startPolling`:243,247 |
| `PhonePanel.pollTimer` | 2 | `startPolling`:244、`stopPolling`:259 |
| `PhonePanel.tickTimer` | 2 | `startTick`:264、`stopTick`:276 |
| `PhonePanel.codeLeft` | 2 | `startTick`:266、`paintPhoneAccess`:636 |
| `PhonePanel.lastCode` | 2 | `paintPhoneAccess`:648,650 |
| `PhonePanel.installing` | 2 | `installComponent`:793,820 |
| `PhonePanel.copied` | 2 | `copyAddress`:1000,1003 |
| `PhonePanel.copyTimer` | 2 | `copyAddress`:1002,1003 |
| `PhonePanel.lastDownload` | 1 | `paintPhoneAccess`:465 |
| `PhonePanel.codeSync` | 1 | `paintPhoneAccess`:635 |
| `PhonePanel.importKey` | 1 | `openComponents`:715 |
| `PhonePanel.addPairAt` | 1 | `addPairing`:931 |
| `PhonePanel.channel` | 1 | `changeChannel`:1065 |

#### 依赖明细：每个文件用了别的文件的哪些名字

- `led.js`：不依赖别的文件。
- `state/store.js`：不依赖别的文件。
- `state/rounds.js` →
  - `state/clock.js`（1）：`_monoMs`
  - `state/store.js`（1）：`S`
- `controllers/bridge.js` →
  - `state/clock.js`（1）：`_monoMs`
- `controllers/refresh.js` →
  - `state/rounds.js`（6）：`bumpRoundGeneration`、`cacheRoundPayload`、`firstNotice`、`markRoundApplied`、`newRoundId`、`takeRoundPayload`
  - `views/login.js`（4）：`addLog`、`paintLogin`、`setBusy`、`setResult`
  - `state/plan.js`（3）：`PLAN_TERMINAL`、`mergeTask`、`syncResultSelection`
  - `controllers/terms.js`（3）：`noteTermsRequired`、`openTerms`、`termsLocked`
  - `state/clock.js`（3）：`_monoMs`、`bnowS`、`businessNowMs`
  - `controllers/tick.js`（3）：`cleanReason`、`listErrorCopy`、`msg`
  - `state/store.js`（2）：`$`、`S`
  - `views/plan-panel.js`（2）：`paintBanners`、`updateControls`
  - `controllers/bridge.js`（2）：`api`、`hasBridge`
  - `state/filters.js`（2）：`findItem`、`normalize`
  - `state/time.js`（2）：`hm`、`toTs`
  - `views/selection.js`（1）：`paintChips`
  - `views/log.js`（1）：`setLogOpen`
  - `controllers/prefs.js`（1）：`savePrefs`
  - `views/list.js`（1）：`render`
  - `controllers/plan-events.js`（1）：`presentPlanDone`
  - `state/login.js`（1）：`syncLoginDependentView`
  - `views/tour.js`（1）：`maybeStartTour`
  - `state/task-display.js`（1）：`RUNNING_STATUSES`
- `views/list.js` →
  - `state/filters.js`（12）：`armedTaskByActivity`、`conflictIds`、`filtered`、`isEligibleForPlan`、`missedBySleep`、`nextOpen`、`requirementFlags`、`rewardChips`、`rewardInline`、`selectedClash`、`signStartPending`、`signedClash`
  - `views/plan-panel.js`（8）：`paintBanners`、`paintBoardState`、`paintChecks`、`paintLed`、`paintPlan`、`paintRoute`、`paintSelected`、`updateControls`
  - `state/labels.js`（8）：`activityTimeText`、`leftOf`、`leftTextOf`、`modeOf`、`modeText`、`signStartKnown`、`stateOf`、`validActivityTime`
  - `state/time.js`（8）：`dayLabel`、`durText`、`esc`、`hm`、`relDayText`、`startOfDay`、`toTs`、`whenText`
  - `state/conflict.js`（5）：`canCancelNow`、`cancelBlock`、`cancelResultView`、`cancelUntilText`、`refundFlag`
  - `state/clock.js`（3）：`_monoMs`、`bnowS`、`businessNowMs`
  - `views/selection.js`（2）：`paintChips`、`paintMoreFilters`
  - `controllers/tick.js`（2）：`listErrorCopy`、`tick`
  - `state/store.js`（2）：`$`、`S`
  - `state/task-display.js`（2）：`executionView`、`taskDisplayLabel`
  - `state/plan.js`（2）：`planOutcome`、`unknownLabel`
  - `views/conflict-tip.js`（1）：`paintTip`
  - `views/tour.js`（1）：`paintTour`
  - `controllers/terms.js`（1）：`termsLocked`
- `state/task-display.js` →
  - `views/plan-panel.js`（4）：`effectiveRetryDeadline`、`hmsDay`、`submittingDetail`、`verifiedSigned`
  - `state/labels.js`（3）：`modeOf`、`modeText`、`taskLabel`
  - `state/filters.js`（2）：`findItem`、`taskMissedBySleep`
  - `state/clock.js`（1）：`bnowS`
  - `state/time.js`（1）：`toTs`
  - `state/store.js`（1）：`S`
- `views/plan-panel.js` →
  - `state/filters.js`（10）：`findItem`、`groupSelected`、`isEligibleForPlan`、`nextOpen`、`selectedItems`、`signStartPending`、`signedClash`、`sleepMissedNames`、`taskMissedBySleep`、`validateSelection`
  - `state/time.js`（8）：`durText`、`esc`、`fmt`、`schoolParts`、`shortTime`、`startOfDay`、`toTs`、`whenText`
  - `state/task-display.js`（6）：`RUNNING_STATUSES`、`executionView`、`taskDisplayDetail`、`taskDisplayItem`、`taskDisplayLabel`、`taskModePrefix`
  - `state/labels.js`（6）：`activityTimeText`、`leftOf`、`modeOf`、`signStartKnown`、`stateOf`、`taskClass`
  - `state/clock.js`（6）：`bnLeftSec`、`bnowS`、`businessNowMs`、`clockReading`、`clockUiState`、`clockUncertaintyText`
  - `state/store.js`（3）：`$`、`RETRY_WINDOW_S`、`S`
  - `state/plan.js`（3）：`PLAN_TERMINAL`、`TASK_TERMINAL`、`resultPageOpen`
  - `controllers/refresh.js`（2）：`refresh`、`runtimeErrorCopy`
  - `controllers/terms.js`（1）：`termsLocked`
  - `views/terms.js`（1）：`termsUpdateMode`
  - `views/phone.js`（1）：`maskAccount`
  - `views/help.js`（1）：`paintReplayButtons`
  - `state/conflict.js`（1）：`cancelBlock`
- `controllers/plan.js` →
  - `views/plan-panel.js`（8）：`paintBanners`、`paintPlan`、`paintSelected`、`planLate`、`reselectableIds`、`selectionSignature`、`setPlanOpen`、`updateControls`
  - `controllers/refresh.js`（6）：`RUNTIME_ERRORS`、`addLogFresh`、`ingestBootstrapPlan`、`notePlanGeneration`、`noteRoundError`、`refresh`
  - `controllers/tick.js`（5）：`cleanReason`、`doCheck`、`grabHint`、`msg`、`stripLabel`
  - `views/login.js`（4）：`addLog`、`paintLogin`、`setBusy`、`setResult`
  - `state/plan.js`（4）：`PLAN_TERMINAL`、`TASK_TERMINAL`、`closeResultPage`、`mergeTask`
  - `state/login.js`（4）：`loginSnapshotState`、`restoreLoginSnapshotState`、`setLogin`、`syncLoginDependentView`
  - `controllers/terms.js`（3）：`noteTermsRequired`、`openTerms`、`termsLocked`
  - `state/filters.js`（3）：`clearSelection`、`selectedItems`、`validateSelection`
  - `state/store.js`（2）：`$`、`S`
  - `state/labels.js`（1）：`modeOf`
  - `state/rounds.js`（1）：`newRoundId`
  - `controllers/bridge.js`（1）：`api`
  - `views/selection.js`（1）：`showPlanError`
  - `views/list.js`（1）：`render`
  - `controllers/plan-events.js`（1）：`presentPlanDone`
- `state/clock.js` →
  - `views/clock-pop.js`（3）：`clockPopOpenNow`、`paintClockPopFeedback`、`renderClockPop`
  - `state/store.js`（1）：`S`
  - `views/clock.js`（1）：`paintClockStatus`
  - `views/plan-panel.js`（1）：`updateControls`
  - `views/list.js`（1）：`render`
- `views/clock.js` →
  - `state/clock.js`（6）：`CLOCK_COPY`、`CLOCK_ICONS`、`businessNowMs`、`clockParts`、`clockRetryText`、`clockUiState`
  - `state/store.js`（1）：`$`
  - `views/clock-pop.js`（1）：`clockPopOpenNow`
- `controllers/clock.js` →
  - `state/clock.js`（4）：`CLOCK_POLL_MS`、`_monoMs`、`ingestBusinessClock`、`markClockUnavailable`
  - `views/clock-pop.js`（3）：`clockPopOpenNow`、`paintClockPopFeedback`、`renderClockPop`
  - `controllers/bridge.js`（2）：`api`、`hasBridge`
  - `state/store.js`（1）：`S`
  - `views/clock.js`（1）：`paintClockStatus`
  - `controllers/tick.js`（1）：`msg`
- `state/plan.js` →
  - `controllers/refresh.js`（2）：`noteSignedTasks`、`scheduleSignedRefresh`
  - `state/clock.js`（1）：`TASK_RUNTIME_FIELDS`
  - `state/store.js`（1）：`S`
  - `views/login.js`（1）：`setBusy`
  - `controllers/plan.js`（1）：`noteStartedFromPhone`
  - `views/list.js`（1）：`render`
  - `controllers/plan-events.js`（1）：`showTaskResult`
  - `views/plan-panel.js`（1）：`selectionSignature`
- `controllers/plan-events.js` →
  - `state/plan.js`（6）：`PLAN_TERMINAL`、`admitPlanEvent`、`closeResultPage`、`mergeTask`、`openResultPage`、`planEventOwns`
  - `controllers/refresh.js`（4）：`notePlanGeneration`、`noteSignedTasks`、`refresh`、`scheduleSignedRefresh`
  - `views/login.js`（3）：`addLog`、`setBusy`、`setResult`
  - `views/plan-panel.js`（2）：`selectionSignature`、`stopReasonText`
  - `state/filters.js`（2）：`findItem`、`isEligibleForPlan`
  - `controllers/tick.js`（2）：`cleanReason`、`grabHint`
  - `state/store.js`（1）：`S`
  - `views/list.js`（1）：`render`
- `state/login.js` →
  - `views/list.js`（3）：`paintRail`、`refreshLoginEmptyState`、`render`
  - `state/time.js`（3）：`schoolParts`、`startOfDay`、`whenText`
  - `views/plan-panel.js`（2）：`paintBoardActions`、`paintSelected`
  - `state/store.js`（1）：`S`
  - `views/relogin.js`（1）：`reloginAutoLive`
  - `controllers/tick.js`（1）：`numOrNull`
  - `views/login.js`（1）：`paintLogin`
  - `state/clock.js`（1）：`businessNowMs`
  - `views/clock.js`（1）：`paintClockStatus`
- `views/login.js` →
  - `state/store.js`（2）：`$`、`S`
  - `views/status-cards.js`（2）：`lastCheckText`、`paintStatusCards`
  - `views/tour.js`（2）：`tourPauseNow`、`tourResumeNow`
  - `state/time.js`（2）：`esc`、`toTs`
  - `state/clock.js`（2）：`businessNowMs`、`clockParts`
  - `state/login.js`（1）：`loginEstimateShort`
  - `controllers/terms.js`（1）：`termsLocked`
  - `views/plan-panel.js`（1）：`updateControls`
- `views/relogin.js` →
  - `state/store.js`（2）：`$`、`S`
  - `views/plan-panel.js`（2）：`autoLoginCredential`、`paintBanners`
  - `views/login.js`（2）：`addLog`、`paintLogin`
  - `controllers/tick.js`（2）：`doCheck`、`msg`
  - `controllers/terms.js`（1）：`termsLocked`
  - `controllers/plan.js`（1）：`doLogin`
  - `views/status-cards.js`（1）：`closeStatusCards`
  - `controllers/bridge.js`（1）：`api`
  - `controllers/refresh.js`（1）：`refresh`
- `views/clock-pop.js` →
  - `state/clock.js`（12）：`CLOCK_COPY`、`CLOCK_ICONS`、`CLOCK_SYNC_FAILURE`、`businessNowMs`、`clockFailureReasonText`、`clockFailureSourceText`、`clockLastSyncText`、`clockParts`、`clockReading`、`clockRetryDueText`、`clockUiState`、`clockUncertaintyText`
  - `state/store.js`（2）：`$`、`S`
  - `state/time.js`（2）：`durText`、`esc`
  - `controllers/tick.js`（1）：`numOrNull`
  - `controllers/clock.js`（1）：`resyncClock`
- `views/status-cards.js` →
  - `views/clock-pop.js`（3）：`clockPopOpenNow`、`closeClockPop`、`toggleClockPop`
  - `state/store.js`（2）：`$`、`S`
  - `state/time.js`（1）：`esc`
  - `state/login.js`（1）：`loginEstimateText`
  - `controllers/terms.js`（1）：`termsLocked`
  - `controllers/tick.js`（1）：`doCheck`
  - `views/settings.js`（1）：`openSettings`
- `views/log.js` →
  - `state/store.js`（2）：`$`、`S`
  - `controllers/prefs.js`（1）：`savePrefs`
  - `views/login.js`（1）：`addLog`
- `views/terms.js` →
  - `state/store.js`（3）：`$`、`FIRST_USE_POINTS`、`S`
  - `state/time.js`（2）：`consentTimeText`、`esc`
- `controllers/terms.js` →
  - `views/terms.js`（27）：`applyTermsFooter`、`closeHelpIfOpen`、`closeTermsDialog`、`closeTermsIntroBox`、`closeTermsUpdateBox`、`focusHelpButton`、`paintLicenseDoc`、`paintTerms`、`paintTermsIntro`、`paintTermsNewMarks`、`paintTermsToc`、`paintTermsUpdateBox`、`paintTermsViewOnlyStatus`、`resetTermsAgree`、`resetTermsReaderView`、`restoreTermsFocusTo`、`setRecheckBusy`、`showTermsDialog`、`showTermsIntroBox`、`showTermsUpdateBox`、`termsActiveSurface`、`termsAgreeMissing`、`termsBoxAvailable`、`termsDialogAvailable`、`termsDialogIsOpen`、`termsDocVersion`、`termsStatus`
  - `views/tour.js`（5）：`requestAutoTour`、`tourPauseNow`、`tourResumeNow`、`tourShouldAutoStart`、`tourVisible`
  - `views/plan-panel.js`（2）：`paintBanners`、`updateControls`
  - `controllers/bridge.js`（2）：`api`、`hasBridge`
  - `state/store.js`（1）：`S`
  - `views/login.js`（1）：`addLog`
  - `views/help.js`（1）：`showHelp`
  - `controllers/prefs.js`（1）：`savePrefsNow`
  - `controllers/refresh.js`（1）：`refresh`
  - `controllers/tick.js`（1）：`msg`
- `views/update.js` →
  - `state/store.js`（2）：`$`、`S`
  - `views/help.js`（1）：`revealHelpStatus`
- `views/help.js` →
  - `state/store.js`（3）：`$`、`DEFAULT_HELP`、`S`
  - `state/time.js`（1）：`esc`
  - `views/update.js`（1）：`paintUpdate`
  - `views/phone.js`（1）：`PhonePanel`
  - `controllers/prefs.js`（1）：`savePrefs`
  - `views/login.js`（1）：`addLog`
  - `views/tour.js`（1）：`startTour`
- `views/settings.js` →
  - `state/store.js`（2）：`$`、`S`
  - `controllers/terms.js`（2）：`ingestTerms`、`termsAccepted`
  - `views/status-cards.js`（1）：`closeStatusCards`
  - `controllers/prefs.js`（1）：`savePrefs`
  - `controllers/bridge.js`（1）：`api`
  - `controllers/tick.js`（1）：`msg`
  - `views/help.js`（1）：`helpStatus`
  - `views/login.js`（1）：`addLog`
  - `views/plan-panel.js`（1）：`paintBanners`
  - `views/list.js`（1）：`render`
  - `views/phone.js`（1）：`downloadFailText`
- `views/phone.js` →
  - `views/settings.js`（3）：`OcrPanel`、`openSettings`、`paintOcrDownload`
  - `state/store.js`（1）：`$`
  - `controllers/refresh.js`（1）：`refresh`
  - `controllers/bridge.js`（1）：`api`
  - `views/status-cards.js`（1）：`paintStatusCards`
  - `views/plan-panel.js`（1）：`paintCountdown`
- `controllers/update.js` →
  - `views/update.js`（2）：`paintUpdate`、`revealUpdateStatus`
  - `state/store.js`（1）：`S`
  - `controllers/bridge.js`（1）：`api`
  - `controllers/tick.js`（1）：`msg`
- `controllers/prefs.js` →
  - `controllers/bridge.js`（2）：`api`、`hasBridge`
  - `state/store.js`（1）：`S`
  - `views/login.js`（1）：`addLog`
- `state/filters.js` →
  - `state/labels.js`（5）：`activityTimeText`、`leftOf`、`modeOf`、`signStartKnown`、`stateOf`
  - `state/time.js`（4）：`esc`、`hm`、`startOfDay`、`toTs`
  - `state/store.js`（1）：`S`
  - `state/clock.js`（1）：`bnowS`
  - `views/plan-panel.js`（1）：`verifiedSigned`
  - `controllers/terms.js`（1）：`termsLocked`
  - `views/list.js`（1）：`render`
  - `views/login.js`（1）：`setResult`
- `state/conflict.js` →
  - `state/time.js`（4）：`SCHOOL_OFFSET_S`、`hm`、`schoolParts`、`toTs`
  - `state/labels.js`（1）：`validActivityTime`
  - `state/clock.js`（1）：`bnowS`
  - `state/store.js`（1）：`S`
  - `controllers/terms.js`（1）：`termsLocked`
- `views/selection.js` →
  - `state/store.js`（2）：`$`、`S`
  - `state/time.js`（2）：`esc`、`shortTime`
  - `state/filters.js`（1）：`isEligibleForPlan`
  - `state/clock.js`（1）：`bnowS`
  - `controllers/prefs.js`（1）：`savePrefs`
  - `views/list.js`（1）：`render`
  - `views/login.js`（1）：`setResult`
- `views/conflict-tip.js` →
  - `state/filters.js`（3）：`armedTaskByActivity`、`filtered`、`findItem`
  - `state/store.js`（2）：`$`、`S`
  - `views/list.js`（2）：`clashOf`、`render`
  - `state/time.js`（1）：`esc`
  - `state/conflict.js`（1）：`conflictTipModel`
  - `views/selection.js`（1）：`paintChips`
  - `controllers/prefs.js`（1）：`savePrefs`
- `controllers/cancel.js` →
  - `state/conflict.js`（3）：`canCancelNow`、`cancelBlock`、`cancelWindowOpen`
  - `state/time.js`（1）：`cssEscape`
  - `state/filters.js`（1）：`findItem`
  - `state/store.js`（1）：`S`
  - `views/list.js`（1）：`render`
  - `controllers/terms.js`（1）：`noteTermsRequired`
  - `views/login.js`（1）：`addLog`
  - `controllers/refresh.js`（1）：`refresh`
  - `controllers/bridge.js`（1）：`api`
- `state/labels.js` →
  - `state/time.js`（4）：`durText`、`hm`、`toTs`、`whenText`
  - `state/conflict.js`（3）：`actSpanAbs`、`endsAtMidnight`、`spanDays`
  - `state/clock.js`（2）：`bnLeftSec`、`bnowS`
  - `state/filters.js`（1）：`taskMissedBySleep`
  - `views/plan-panel.js`（1）：`verifiedSigned`
- `controllers/tick.js` →
  - `views/plan-panel.js`（8）：`paintBanners`、`paintCountdown`、`paintEditNote`、`paintLed`、`paintRoute`、`paintRunPanel`、`paintSelected`、`runHeadKey`
  - `state/clock.js`（4）：`_monoMs`、`bnowS`、`businessNowMs`、`clockParts`
  - `state/task-display.js`（4）：`RUNNING_STATUSES`、`taskDisplayDetail`、`taskDisplayLabel`、`taskModePrefix`
  - `state/store.js`（3）：`$`、`S`、`SLEEP_GAP_MS`
  - `views/list.js`（3）：`paintFreshness`、`paintList`、`paintRail`
  - `state/labels.js`（3）：`leftOf`、`leftTextOf`、`stateOf`
  - `state/time.js`（3）：`cssEscape`、`durText`、`hm`
  - `views/login.js`（2）：`addLog`、`paintLogin`
  - `controllers/refresh.js`（2）：`addLogFresh`、`runtimeErrorCopy`
  - `views/clock.js`（1）：`paintClockStatus`
  - `views/clock-pop.js`（1）：`clockPopOpenNow`
  - `state/filters.js`（1）：`findItem`
  - `state/conflict.js`（1）：`canCancelNow`
  - `controllers/bridge.js`（1）：`api`
- `state/time.js` →
  - `state/clock.js`（1）：`businessNowMs`
  - `state/store.js`（1）：`WEEK`
- `views/tour.js` →
  - `state/store.js`（4）：`$`、`S`、`TOUR_STEPS`、`TOUR_VERSION`
  - `controllers/terms.js`（1）：`termsLocked`
  - `controllers/prefs.js`（1）：`savePrefsNow`
- `controllers/window.js` →
  - `state/time.js`（1）：`esc`
  - `state/store.js`（1）：`S`
  - `controllers/bridge.js`（1）：`api`
  - `views/login.js`（1）：`addLog`
  - `controllers/tick.js`（1）：`msg`
- `app.js` →
  - `controllers/terms.js`（11）：`acceptTerms`、`declineTerms`、`ensureLicenseText`、`ingestTerms`、`markTermsUnknown`、`openTerms`、`openTermsReader`、`recheckTerms`、`restoreTermsFocus`、`resumeTermsTour`、`termsLocked`
  - `controllers/plan.js`（11）：`cancelTask`、`closeStopAsk`、`confirmStopPlan`、`finishResult`、`handleDone`、`modifyPlan`、`reselectFailed`、`startPlan`、`stopAskKey`、`stopAskOpen`、`stopPlan`
  - `views/tour.js`（9）：`maybeStartTour`、`paintTour`、`requestAutoTour`、`tourClose`、`tourGuardClick`、`tourShouldAutoStart`、`tourSkip`、`tourTrapTab`、`tourVisible`
  - `controllers/refresh.js`（8）：`RUNTIME_ERRORS`、`applyActivities`、`applyPrefs`、`autoRefreshTick`、`clearFilters`、`ingestBootstrapPlan`、`refresh`、`startAutoRefresh`
  - `views/conflict-tip.js`（8）：`placeTip`、`tipClose`、`tipGoSigned`、`tipKey`、`tipLater`、`tipOpen`、`tipSoon`、`tipStay`
  - `controllers/update.js`（7）：`cancelDownload`、`checkUpdate`、`confirmDownload`、`launchInstaller`、`receiveUpdate`、`restoreUpdate`、`startDownload`
  - `views/plan-panel.js`（7）：`applyBand`、`bindPlaceToggle`、`paintBanners`、`paintChecks`、`setPlanOpen`、`togglePlace`、`verifyTask`
  - `views/terms.js`（6）：`applyTermsFooter`、`closeTermsIntroBox`、`closeTermsUpdateBox`、`reopenTermsBox`、`switchTermsDoc`、`termsCloseIntent`
  - `state/store.js`（5）：`$`、`DEFAULT_HELP`、`RELEASES_LATEST_URL`、`S`、`TOUR_STEPS`
  - `views/settings.js`（5）：`closeSettings`、`openSettings`、`openSettingsSection`、`settingsOpen`、`wireSettings`
  - `views/help.js`（4）：`fillHelp`、`helpStatus`、`replayTourFrom`、`showHelp`
  - `state/rounds.js`（4）：`cacheRoundPayload`、`firstNotice`、`loginPresent`、`markRoundApplied`
  - `views/status-cards.js`（4）：`closeStatusCards`、`openStatusCard`、`statusCardOpen`、`wireStatusCards`
  - `controllers/bridge.js`（3）：`api`、`hasBridge`、`waitForBridge`
  - `views/login.js`（3）：`addLog`、`setBusy`、`setResult`
  - `controllers/clock.js`（3）：`pollClockNow`、`resyncClock`、`startClockPolling`
  - `views/clock-pop.js`（3）：`applyClock`、`clockPopOpenNow`、`toggleClockPop`
  - `controllers/tick.js`（3）：`msg`、`receiveSecondOpen`、`tick`
  - `views/relogin.js`（3）：`loginEntry`、`receiveReloginState`、`wireRelogin`
  - `views/selection.js`（3）：`paintChips`、`setFilter`、`setFilterOpen`
  - `state/filters.js`（3）：`clearSelection`、`nextOpen`、`toggleSelection`
  - `controllers/cancel.js`（3）：`cancelAsk`、`cancelAskDismiss`、`cancelConfirm`
  - `state/clock.js`（2）：`_monoMs`、`ingestBusinessClock`
  - `state/login.js`（2）：`setLogin`、`syncLoginDependentView`
  - `state/plan.js`（2）：`handlePlan`、`handleTask`
  - `views/log.js`（2）：`copyLog`、`setLogOpen`
  - `controllers/prefs.js`（1）：`savePrefs`
  - `views/list.js`（1）：`render`
  - `controllers/window.js`（1）：`openWindowCloseDialog`
  - `controllers/plan-events.js`（1）：`handlePlanDone`

### 手机页（local/ui/m/）

`local/ui/m/index.html` 只加载 1 个脚本：`m/app.js`。没有文件间依赖。

- `PhoneModel`（纯函数对象）：`local/ui/m/app.js:7-1361`，1355 行。
- 页面逻辑（`if (typeof document !== "undefined")` 块）：`local/ui/m/app.js:1367-3357`，1991 行。

#### `PhoneModel` 成员：101 个（函数 90 个，常量 11 个）

最长的 15 个函数：

| 行数 | 位置 | 名字 |
|---|---|---|
| 88 | `local/ui/m/app.js:1187` | `PhoneModel.reloginView` |
| 59 | `local/ui/m/app.js:878` | `PhoneModel.taskCard` |
| 58 | `local/ui/m/app.js:977` | `PhoneModel.resultView` |
| 53 | `local/ui/m/app.js:627` | `PhoneModel.rowView` |
| 44 | `local/ui/m/app.js:728` | `PhoneModel.listView` |
| 43 | `local/ui/m/app.js:683` | `PhoneModel.draftBoard` |
| 42 | `local/ui/m/app.js:829` | `PhoneModel.runBoard` |
| 38 | `local/ui/m/app.js:440` | `PhoneModel.preStartWarnings` |
| 34 | `local/ui/m/app.js:1055` | `PhoneModel.reviewBatches` |
| 29 | `local/ui/m/app.js:380` | `PhoneModel.whyView` |
| 22 | `local/ui/m/app.js:18` | `PhoneModel.filterItems` |
| 21 | `local/ui/m/app.js:1298` | `PhoneModel.ledOf` |
| 21 | `local/ui/m/app.js:1322` | `PhoneModel.pairView` |
| 18 | `local/ui/m/app.js:940` | `PhoneModel.confirmView` |
| 18 | `local/ui/m/app.js:1278` | `PhoneModel.glyphs` |

#### 页面块里的定义：函数 67 个，`const` 5 个，`let` / `var` 1 个

非函数的定义：`$`（const，1368）、`REQUEST_TIMEOUT_MS`（const，1371）、`model`（const，1386）、`SHEET_TITLES`（const，1559）、`LIST_ZONES`（const，1991）、`PhoneUI`（window，3348）。

#### 页面块里的可变状态：55 个被写入的目标，共 146 处写入

按「对象.一级字段」汇总；「所在函数」取最外层的具名函数。

| 目标 | 写入处数 | 写它的函数（行）| 用到它的函数数 |
|---|---|---|---|
| `model.reloginSubmitting` | 10 | `ingestRelogin`:2988,2997,3004,3020…、`submitRelogin`:3123,3148 | 4 |
| `model.notice` | 7 | `buildRow`:1789、`ingest`:2645、`startPlan`:2731、`reselectFailed`:2865、`finishPlanView`:2875、`removeFromReview`:2952、`wire`:3292 | 8 |
| `model.selected` | 6 | `buildRow`:1788、`ingest`:2639、`reselectFailed`:2863、`finishPlanView`:2873、`removeFromReview`:2951、`wire`:3291 | 12 |
| `model.filter` | 6 | `goSigned`:1973、`toggleSearch`:2210、`wire`:3276,3283,3297,3305 | 5 |
| `model.tickTimer` | 6 | `onNeedPair`:2472、`scheduleTick`:2504,2507,2508、`wire`:3327,3337 | 3 |
| `model.challenge` | 6 | `ingestRelogin`:2987,3001,3028,3044…、`cancelRelogin`:3171 | 4 |
| `model.pairErr` | 5 | `setPairError`:2351、`schedulePairTick`:2366、`pair`:2397,2420、`wire`:3192 | 5 |
| `model.pollTimer` | 5 | `onNeedPair`:2470、`schedule`:2494,2497、`wire`:3325,3335 | 3 |
| `model.relConfirm` | 4 | `closeSheet`:1602、`openRelogin`:1666、`beginRelogin`:3067、`wire`:3262 | 5 |
| `model.csrf` | 4 | `api`:2287、`pair`:2416、`poll`:2433、`onForbidden`:2484 | 4 |
| `model.listOpen` | 4 | `startPlan`:2732、`reselectFailed`:2864、`finishPlanView`:2874、`wire`:3249 | 5 |
| `model.reloginStarting` | 4 | `ingestRelogin`:2989、`beginRelogin`:3065,3079,3092 | 4 |
| `model.nowMs` | 3 | `canWrite`:1496、`refreshControls`:1501、`renderItems`:1998 | 4 |
| `model.pairLockLeft` | 3 | `beginPairLock`:2358、`schedulePairTick`:2364、`stopPairLock`:2373 | 4 |
| `model.pairTickTimer` | 3 | `schedulePairTick`:2362,2363、`stopPairLock`:2372 | 2 |
| `model.paired` | 3 | `pair`:2417、`poll`:2443、`onNeedPair`:2468 | 9 |
| `model.backoff` | 3 | `poll`:2442、`onPollFail`:2464、`onForbidden`:2488 | 3 |
| `model.seenEventSeq` | 3 | `ingest`:2624,2683,2685 | 1 |
| `model.seq` | 3 | `ingest`:2625,2680,2697 | 2 |
| `model.plan` | 3 | `ingest`:2650、`reselectFailed`:2853、`finishPlanView`:2872 | 10 |
| `model.retry` | 3 | `ingest`:2668、`wire`:3312,3318 | 6 |
| `model.pending` | 3 | `startPlan`:2730,2741,2742 | 10 |
| `model.retryDirty` | 3 | `saveRetry`:2885、`wire`:3313,3319 | 3 |
| `model.offlineTries` | 2 | `syncOffline`:1446、`onPollFail`:2463 | 2 |
| `model.sheetOpener` | 2 | `openSheet`:1564、`closeSheet`:1604 | 2 |
| `model.sheetId` | 2 | `openSheet`:1565、`closeSheet`:1586 | 6 |
| `model.confirm` | 2 | `closeSheet`:1601、`askConfirm`:1681 | 3 |
| `model.flashId` | 2 | `goSigned`:1980,1984 | 2 |
| `model.pickId` | 2 | `renderBoard`:2164,2182 | 2 |
| `model.pairing` | 2 | `pair`:2401,2426 | 1 |
| `model.pairOkPending` | 2 | `pair`:2418、`wire`:3204 | 3 |
| `model.flying` | 2 | `poll`:2434,2453 | 7 |
| `model.reconciling` | 2 | `reconcile`:2753,2773 | 1 |
| `model.cancelingStart` | 2 | `cancelPendingStart`:2783,2798 | 1 |
| `model.dismissedPlanId` | 2 | `reselectFailed`:2852、`finishPlanView`:2871 | 3 |
| `model.relEnteredAcct` | 2 | `beginRelogin`:3068,3087 | 2 |
| `model.relSavedChoice` | 2 | `beginRelogin`:3069,3088 | 2 |
| `model.bannerKind` | 1 | `setBanner`:1429 | 2 |
| `model.whyId` | 1 | `goSigned`:1968 | 2 |
| `model.searchOpen` | 1 | `toggleSearch`:2207 | 2 |
| `model.lastOkAt` | 1 | `poll`:2441 | 4 |
| `model.tickMark` | 1 | `tickClock`:2521 | 1 |
| `model.clock` | 1 | `tickClock`:2523 | 2 |
| `model.probed` | 1 | `probeExistingSession`:2617 | 1 |
| `model.items` | 1 | `ingest`:2636 | 11 |
| `model.termsOk` | 1 | `ingest`:2652 | 8 |
| `model.reloginSetup` | 1 | `ingest`:2653 | 4 |
| `model.clockState` | 1 | `ingest`:2655 | 3 |
| `model.lastOkText` | 1 | `ingest`:2660 | 3 |
| `model.pcListError` | 1 | `ingest`:2664 | 3 |
| `model.busy` | 1 | `ingest`:2665 | 12 |
| `model.retryHydrated` | 1 | `ingest`:2672 | 1 |
| `model.retryOptions` | 1 | `ingest`:2675 | 1 |
| `model.login` | 1 | `ingest`:2703 | 5 |
| `model.flow` | 1 | `ingestRelogin`:2972 | 9 |

#### 页面块对 `PhoneModel` 的调用：用到 50 个成员，共 98 处

页面块没有直接调用的函数成员 41 个（可能只在 `PhoneModel` 内部互调，或只给测试用）：`filterItems`、`openEpochOf`、`bucketOf`、`isActive`、`challengeExpired`、`taskDeadline`、`itemTitle`、`itemMeta`、`glue`、`schoolSec`、`pad2`、`absWhen`、`dayOf`、`endsAtMidnight`、`lastDayOf`、`actRange`、`spanDays`、`actSpan`、`cancelWindowOpen`、`signedClash`、`refundFlag`、`rewardText`、`cancelNote`、`clashWay`、`taskText`、`hms`、`hmsAt`、`leftCn`、`groupKeyOf`、`overlapFirst`、`conflictNotice`、`nextPick`、`draftBoard`、`taskOpenOf`、`taskRail`、`planFinished`、`relSaveGain`、`relHandoff`、`relLead`、`glyphs`、`ledOf`。

