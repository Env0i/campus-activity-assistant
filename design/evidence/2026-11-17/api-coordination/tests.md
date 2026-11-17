# 测试触点

- 生成脚本：`scripts/field_map.py`（ast 读 local/tests/*.py）
- 命令：`python -B design/evidence/<日期>/api-coordination/scripts/field_map.py --head 788b25c`
- 基线：`788b25c`；触点 1259 处，分布在 21 个测试文件
- 归类：字段触点按该字段所属功能（跨功能字段记「跨功能」），私有方法按方法名，app 补丁按名字。

## 汇总

| 功能 | 触点处数 | 涉及文件数 | 改造预算（行，按每处一行估） |
|---|---|---|---|
| 更新 | 48 | 4 | 48 |
| 组件 | 44 | 3 | 44 |
| 手机访问 | 58 | 2 | 58 |
| 登录恢复 | 82 | 8 | 82 |
| 计划 | 128 | 11 | 128 |
| 活动列表 | 28 | 6 | 28 |
| 窗口与托盘 | 49 | 5 | 49 |
| worker 进程 | 28 | 8 | 28 |
| 其他 | 377 | 20 | 377 |
| 跨功能 | 417 | 13 | 417 |

预算只估「改测试要动多少行」的量级：搬字段、换断言目标大约一处一行；跨功能字段按最坏情况（每个功能的责任测试都要改）单独记一档，不摊到任何单个服务。

## 更新（48 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 私有方法调用 | 34 | `_do_check_update`×4、`_do_update_download`×6、`check_update`×7、`update_cancel`×1、`update_download`×6、`update_launch`×10 | `local/tests/test_application_services.py` 3、`local/tests/test_runtime_bundle.py` 4、`local/tests/test_update_check.py` 27 |
| app 补丁 | 14 | `resolve_update_launcher_path`×4、`update_prefs`×2、`update_version_paths`×2、`version_switch_available`×6 | `local/tests/test_application_services.py` 5、`local/tests/test_clock_tail.py` 1、`local/tests/test_runtime_bundle.py` 6、`local/tests/test_update_check.py` 2 |

## 组件（44 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 私有方法调用 | 44 | `_commit_downloaded_component_group`×1、`_component_finished`×3、`_install_downloaded_component`×2、`_resolve_component_asset`×3、`advanced_component_location`×4、`advanced_features_state`×8、`cancel_advanced_feature_download`×1、`download_advanced_feature`×5、`enable_advanced_feature`×5、`inspect_advanced_component`×3、`install_advanced_feature`×2、`open_advanced_component_dir`×5、`pick_advanced_component`×2 | `local/tests/test_application_services.py` 35、`local/tests/test_release_audit.py` 7、`local/tests/test_update_check.py` 2 |

## 手机访问（58 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 私有方法调用 | 56 | `_phone_raw_state`×18、`_stop_phone_access`×1、`phone_access_state`×19、`restore_phone_access`×3、`set_phone_access_preferences`×6、`start_phone_access`×5、`stop_phone_access`×4 | `local/tests/test_application_services.py` 56 |
| app 补丁 | 2 | `phone_log`×2 | `local/tests/test_single_instance.py` 2 |

## 登录恢复（82 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 私有方法调用 | 69 | `_anchor_login_success`×2、`_auto_relogin_eligible`×12、`_auto_relogin_paused`×4、`_begin_auto_relogin`×3、`_begin_auto_relogin_once`×5、`_do_check`×10、`_phone_relay_view`×1、`_relay_finished`×3、`_relogin_wait_s`×3、`_spawn_relay_worker`×1、`check`×7、`login`×9、`phone_relogin_begin`×4、`prepare_phone_relogin`×2、`relogin_begin`×1、`relogin_cancel`×1、`save_relogin_credentials`×1 | `local/tests/test_application_services.py` 38、`local/tests/test_cancel_signup.py` 2、`local/tests/test_relogin_busy_order.py` 2、`local/tests/test_runtime_bundle.py` 12、`local/tests/test_signup_plan.py` 1、`local/tests/test_silent_relogin.py` 8、`local/tests/test_terms_consent.py` 6 |
| app 补丁 | 13 | `_credential_store`×1、`_credential_store_available`×1、`check_latest_release`×6、`login_state`×5 | `local/tests/test_application_services.py` 2、`local/tests/test_runtime_bundle.py` 1、`local/tests/test_silent_relogin.py` 3、`local/tests/test_update_check.py` 7 |

## 计划（128 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 私有方法调用 | 127 | `_cancel_signup_run`×1、`_close_plan_burden`×4、`_confirm_signed`×2、`_remember_start`×6、`_run_plan_task`×11、`cancel_signup`×21、`cancel_start_request`×6、`plan_active_for_close`×4、`start_plan`×61、`start_request_state`×8、`stop_plan`×3 | `local/tests/test_application_services.py` 8、`local/tests/test_cancel_signup.py` 22、`local/tests/test_real_data_contract.py` 2、`local/tests/test_release_audit.py` 5、`local/tests/test_retry_phone_policy.py` 6、`local/tests/test_retry_policy.py` 4、`local/tests/test_runtime_bundle.py` 32、`local/tests/test_session_persistence.py` 6、`local/tests/test_signup_plan.py` 33、`local/tests/test_terms_consent.py` 8、`local/tests/test_worker_line_stamp.py` 1 |
| app 补丁 | 1 | `validate_plan`×1 | `local/tests/test_runtime_bundle.py` 1 |

## 活动列表（28 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 私有方法调用 | 28 | `_do_list`×12、`_do_list_inner`×3、`_merge_list_activities`×4、`_note_pc_list_error`×4、`list_activities`×5 | `local/tests/test_application_services.py` 7、`local/tests/test_cancel_signup.py` 1、`local/tests/test_real_data_contract.py` 1、`local/tests/test_runtime_bundle.py` 13、`local/tests/test_signup_plan.py` 3、`local/tests/test_terms_consent.py` 3 |

## 窗口与托盘（49 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 私有方法调用 | 48 | `_on_second_open`×4、`ask_window_close`×2、`hide_window`×5、`request_window_close`×7、`shutdown`×16、`stop`×11、`window_visibility`×3 | `local/tests/test_application_services.py` 20、`local/tests/test_phone_http.py` 1、`local/tests/test_phone_service.py` 11、`local/tests/test_runtime_bundle.py` 12、`local/tests/test_single_instance.py` 4 |
| app 补丁 | 1 | `defer_close_action`×1 | `local/tests/test_application_services.py` 1 |

## worker 进程（28 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| app 补丁 | 26 | `worker_command`×26 | `local/tests/test_application_services.py` 1、`local/tests/test_cancel_signup.py` 1、`local/tests/test_relogin_busy_order.py` 1、`local/tests/test_retry_phone_policy.py` 5、`local/tests/test_retry_policy.py` 3、`local/tests/test_runtime_bundle.py` 11、`local/tests/test_signup_plan.py` 3、`local/tests/test_worker_line_stamp.py` 1 |
| 私有方法调用 | 2 | `_run`×2 | `local/tests/test_runtime_bundle.py` 2 |

## 其他（377 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| app 补丁 | 195 | `Api`×1、`BusinessClock`×1、`CREDENTIAL_FILE`×1、`DATA_DIR`×7、`DEMO`×27、`DEVICE_FILE`×9、`GRAB`×5、`LIST_CLOCK_POLL_S`×3、`LIST_CLOCK_WAIT_S`×5、`LOG_FILE`×3、`LOG_LOCK_FILE`×2、`PREFS`×32、`PlanCoordinator`×27、`RUNTIME_CHECK_TIMEOUT_S`×1、`SESSION_FILE`×15、`_CREDENTIAL_STORE_OK`×1、`_PREFS_SAVE_TIMEOUT_S`×1、`_env`×8、`_kill_tree`×4、`_prefs_transaction`×1、`_screen_size`×1、`_seconds_until`×1、`configure_time_source`×1、`ensure_data_dir`×2、`get_lifecycle`×3、`load_prefs`×2、`migration_record`×4、`save_session_timing_anchor`×1、`spawn_owned`×17、`spawn_owned_worker`×1、`worker_problem`×8 | `local/tests/test_application_services.py` 39、`local/tests/test_cancel_signup.py` 6、`local/tests/test_clock_tail.py` 5、`local/tests/test_relogin_busy_order.py` 9、`local/tests/test_retry_phone_policy.py` 7、`local/tests/test_retry_policy.py` 2、`local/tests/test_runtime_bundle.py` 62、`local/tests/test_session_persistence.py` 30、`local/tests/test_signup_plan.py` 15、`local/tests/test_silent_relogin.py` 6、`local/tests/test_single_instance.py` 9、`local/tests/test_ui_contract_login.py` 2、`local/tests/test_update_check.py` 2、`local/tests/test_worker_line_stamp.py` 1 |
| 字段写 | 80 | `_auto_relogin_paused`×1、`_begin_auto_relogin`×2、`_canceled_start_ids`×1、`_clock_now`×2、`_do_check_inner`×1、`_emit`×39、`_ensure_tray`×10、`_is_busy_locked`×1、`_once_credentials_staged`×1、`_pump`×1、`_push_login_expired`×3、`_relogin_blocked_locked`×1、`_silent_relogin_ready`×1、`_spawn`×1、`_terms_gate`×8、`accept_terms`×2、`check`×1、`plan_active_for_close`×1、`request_window_close`×1、`stop_phone_access`×1、`withdraw_terms`×1 | `local/tests/test_application_services.py` 31、`local/tests/test_cancel_signup.py` 2、`local/tests/test_release_audit.py` 6、`local/tests/test_relogin_busy_order.py` 4、`local/tests/test_retry_phone_policy.py` 5、`local/tests/test_retry_policy.py` 3、`local/tests/test_runtime_bundle.py` 10、`local/tests/test_session_persistence.py` 3、`local/tests/test_signup_plan.py` 1、`local/tests/test_silent_relogin.py` 3、`local/tests/test_single_instance.py` 1、`local/tests/test_terms_consent.py` 9、`local/tests/test_update_check.py` 1、`local/tests/test_worker_line_stamp.py` 1 |
| 字段读 | 55 | `_clock_now`×1、`_do_list`×5、`_emit`×16、`_start_plan_inner`×1、`login`×2、`request_window_close`×1、`shutdown`×6、`stop`×22、`stop_phone_access`×1 | `local/tests/test_application_services.py` 21、`local/tests/test_phone_http.py` 3、`local/tests/test_phone_service.py` 5、`local/tests/test_phone_ui.py` 1、`local/tests/test_release_audit.py` 6、`local/tests/test_relogin_busy_order.py` 1、`local/tests/test_retry_phone_integration.py` 3、`local/tests/test_runtime_bundle.py` 9、`local/tests/test_signup_plan.py` 1、`local/tests/test_silent_relogin.py` 1、`local/tests/test_update_check.py` 4 |
| 私有方法调用 | 47 | `_is_busy`×6、`_is_busy_locked`×9、`_pump`×6、`_terms_gate`×5、`accept_terms`×5、`bootstrap`×9、`grab`×2、`withdraw_terms`×5 | `local/tests/test_cancel_signup.py` 3、`local/tests/test_relogin_busy_order.py` 1、`local/tests/test_retry_policy.py` 2、`local/tests/test_runtime_bundle.py` 7、`local/tests/test_session_persistence.py` 10、`local/tests/test_signup_plan.py` 5、`local/tests/test_silent_relogin.py` 1、`local/tests/test_terms_consent.py` 17、`local/tests/test_update_check.py` 1 |

## 跨功能（417 处）

| 触点类型 | 处数 | 名字（次数） | 文件分布 |
|---|---|---|---|
| 字段读 | 270 | `_activities`×17、`_advanced_busy`×2、`_auto_relogin`×32、`_aux_procs`×2、`_aux_trees`×2、`_cancelling`×2、`_checking`×10、`_close_approved`×4、`_cloudflare`×1、`_cloudflare_exit_notice`×2、`_component_service`×2、`_last_check`×7、`_last_plan`×10、`_list_last`×1、`_listing`×6、`_ocr_component_service`×2、`_once_creds_rejected`×1、`_pc_list_ok_at`×2、`_phone`×25、`_phone_channel`×3、`_plan`×23、`_plan_procs`×20、`_proc`×2、`_proc_tree`×3、`_relay`×13、`_relay_creds_source`×3、`_shutdown_done_event`×1、`_start_requests`×1、`_updates`×69、`_window_hidden`×1、`_window_minimized`×1 | `local/tests/test_application_services.py` 72、`local/tests/test_cancel_signup.py` 11、`local/tests/test_real_data_contract.py` 1、`local/tests/test_release_audit.py` 7、`local/tests/test_relogin_busy_order.py` 2、`local/tests/test_retry_policy.py` 13、`local/tests/test_runtime_bundle.py` 57、`local/tests/test_session_persistence.py` 1、`local/tests/test_signup_plan.py` 22、`local/tests/test_silent_relogin.py` 26、`local/tests/test_single_instance.py` 2、`local/tests/test_terms_consent.py` 5、`local/tests/test_update_check.py` 51 |
| 字段写 | 147 | `_activities`×20、`_advanced_busy`×3、`_auto_relogin`×7、`_auto_relogin_started_at`×1、`_aux_procs`×1、`_aux_trees`×1、`_checking`×3、`_close_approved`×1、`_closing`×4、`_cloudflare`×5、`_cloudflare_starting`×1、`_component_service`×1、`_last_check`×21、`_list_last`×1、`_listing`×2、`_ocr_component_service`×2、`_phone`×8、`_phone_channel`×1、`_plan`×16、`_plan_procs`×1、`_proc`×6、`_proc_tree`×2、`_relay`×11、`_start_order`×2、`_start_requests`×2、`_tray`×3、`_window`×16、`_window_hidden`×4、`_window_minimized`×1 | `local/tests/test_application_services.py` 62、`local/tests/test_cancel_signup.py` 5、`local/tests/test_real_data_contract.py` 2、`local/tests/test_release_audit.py` 12、`local/tests/test_retry_policy.py` 4、`local/tests/test_runtime_bundle.py` 28、`local/tests/test_session_persistence.py` 8、`local/tests/test_signup_plan.py` 13、`local/tests/test_silent_relogin.py` 4、`local/tests/test_single_instance.py` 6、`local/tests/test_terms_consent.py` 1、`local/tests/test_update_check.py` 2 |

