# Api 字段归属

- 生成脚本：`scripts/field_map.py`（ast 只读源码；锁区间与功能归类来自 `lock_graph.py`）
- 命令：`python -B design/evidence/<日期>/api-coordination/scripts/field_map.py --head 788b25c`
- 基线：`788b25c`；Api 实例属性 59 个（Api 上的 3 把锁另见 locks.md，不在此表）
- 「功能」按方法名归类，规则与例外写在 `lock_graph.py` 的 FEATURE_RULES / FEATURE_OVERRIDES。
- 「锁外访问」是该字段在没有任何锁的行上被读写过几次：这些点改归属时最容易漏。

## 只被一个功能读写的字段（可以随该服务走）

| 字段 | 功能 | 写处 | 读处 | 写方法数 | 读方法数 | 锁外访问 |
|---|---|---|---|---|---|---|
| `_canceled_start_ids` | 其他 | 1 | 0 | 1 | 0 | 1 |
| `_clock_monitor_started` | 时钟 | 1 | 0 | 1 | 0 | 1 |

## 被两个以上功能读写的字段（跨功能，必须先定归属）

| 字段 | 功能 | 写处 | 读处 | 写方法数 | 读方法数 | 锁外访问 |
|---|---|---|---|---|---|---|
| `_activities` | 其他、手机访问、活动列表、计划 | 3 | 10 | 2 | 6 | 4 |
| `_advanced_busy` | 其他、手机访问、登录恢复、组件、计划 | 7 | 7 | 5 | 7 | 3 |
| `_auto_relogin` | 其他、登录恢复、窗口与托盘、组件 | 1 | 21 | 1 | 20 | 13 |
| `_auto_relogin_started_at` | 其他、登录恢复 | 2 | 2 | 2 | 2 | 2 |
| `_aux_procs` | worker 进程、其他、窗口与托盘 | 1 | 3 | 1 | 2 | 1 |
| `_aux_trees` | worker 进程、其他、窗口与托盘 | 1 | 3 | 1 | 2 | 1 |
| `_cancelling` | 其他、活动列表、登录恢复、计划 | 3 | 6 | 2 | 6 | 3 |
| `_check_again` | 其他、登录恢复 | 3 | 1 | 3 | 1 | 1 |
| `_check_last` | 其他、登录恢复 | 2 | 1 | 2 | 1 | 2 |
| `_check_request_id` | 其他、登录恢复 | 2 | 3 | 2 | 2 | 2 |
| `_checking` | 其他、登录恢复、计划 | 4 | 5 | 3 | 5 | 2 |
| `_clock` | 其他、手机访问、时钟、登录恢复 | 1 | 11 | 1 | 10 | 12 |
| `_clock_syncing` | 其他、时钟 | 3 | 1 | 2 | 1 | 1 |
| `_close_approved` | 其他、窗口与托盘 | 2 | 0 | 2 | 0 | 2 |
| `_closing` | worker 进程、其他、手机访问、更新、活动列表、登录恢复、窗口与托盘、组件、计划 | 2 | 28 | 2 | 27 | 4 |
| `_cloudflare` | 其他、手机访问、登录恢复、组件 | 1 | 10 | 1 | 8 | 8 |
| `_cloudflare_exit_notice` | 其他、手机访问 | 4 | 1 | 4 | 1 | 5 |
| `_cloudflare_starting` | 其他、手机访问 | 3 | 1 | 2 | 1 | 4 |
| `_component_service` | 其他、组件 | 1 | 2 | 1 | 2 | 2 |
| `_expiry_pushed` | 其他、登录恢复 | 3 | 1 | 2 | 1 | 1 |
| `_finished_plan_ids` | 其他、计划 | 1 | 7 | 1 | 3 | 4 |
| `_last_check` | 其他、手机访问、登录恢复、计划 | 4 | 5 | 3 | 5 | 4 |
| `_last_login_origin` | 其他、登录恢复、组件 | 2 | 1 | 2 | 1 | 2 |
| `_last_plan` | 其他、手机访问、计划 | 4 | 3 | 3 | 2 | 1 |
| `_latest_plan_id` | 其他、计划 | 2 | 8 | 2 | 4 | 2 |
| `_list_last` | 其他、活动列表、计划 | 3 | 2 | 3 | 2 | 2 |
| `_list_request_id` | 其他、活动列表 | 2 | 3 | 2 | 2 | 2 |
| `_listing` | 其他、活动列表、登录恢复、计划 | 3 | 4 | 3 | 4 | 2 |
| `_login_expired_logged` | 其他、登录恢复 | 3 | 0 | 2 | 0 | 1 |
| `_login_seen_valid` | 其他、登录恢复 | 2 | 1 | 2 | 1 | 1 |
| `_login_wait_pending` | 其他、登录恢复 | 3 | 1 | 3 | 1 | 2 |
| `_next_plan_source` | 其他、计划 | 3 | 0 | 3 | 0 | 1 |
| `_ocr_component_service` | 其他、组件 | 1 | 1 | 1 | 1 | 2 |
| `_once_creds_rejected` | 其他、登录恢复 | 5 | 1 | 5 | 1 | 1 |
| `_pc_list_error` | 其他、手机访问、活动列表 | 4 | 2 | 3 | 1 | 1 |
| `_pc_list_ok_at` | 其他、活动列表 | 3 | 1 | 2 | 1 | 1 |
| `_pending_save` | 其他、登录恢复 | 6 | 1 | 6 | 1 | 1 |
| `_phone` | 其他、手机访问、窗口与托盘、组件 | 1 | 20 | 1 | 13 | 16 |
| `_phone_channel` | 其他、手机访问、窗口与托盘、组件 | 8 | 7 | 7 | 5 | 11 |
| `_plan` | 其他、手机访问、时钟、登录恢复、窗口与托盘、计划 | 5 | 24 | 3 | 16 | 7 |
| `_plan_generation` | 其他、计划 | 2 | 4 | 2 | 3 | 1 |
| `_plan_procs` | 其他、登录恢复、窗口与托盘、计划 | 1 | 6 | 1 | 6 | 5 |
| `_plan_sources` | 其他、计划 | 1 | 4 | 1 | 2 | 1 |
| `_plan_trees` | 其他、窗口与托盘、计划 | 1 | 3 | 1 | 3 | 2 |
| `_proc` | worker 进程、其他、登录恢复、窗口与托盘、计划 | 7 | 16 | 6 | 8 | 7 |
| `_proc_tree` | worker 进程、其他、登录恢复、窗口与托盘 | 7 | 6 | 6 | 4 | 1 |
| `_relay` | 其他、手机访问、登录恢复、窗口与托盘、组件 | 1 | 35 | 1 | 26 | 27 |
| `_relay_creds_source` | 其他、登录恢复 | 3 | 2 | 3 | 2 | 1 |
| `_relay_proc_tree` | 其他、登录恢复、窗口与托盘 | 4 | 2 | 4 | 2 | 1 |
| `_shutdown_done_event` | 其他、窗口与托盘 | 1 | 2 | 1 | 1 | 2 |
| `_start_order` | 其他、计划 | 1 | 6 | 1 | 1 | 7 |
| `_start_requests` | 其他、计划 | 1 | 16 | 1 | 9 | 7 |
| `_tray` | 其他、窗口与托盘、计划 | 4 | 8 | 3 | 6 | 12 |
| `_updates` | 其他、更新 | 1 | 7 | 1 | 7 | 8 |
| `_window` | 其他、窗口与托盘、组件 | 1 | 11 | 1 | 6 | 12 |
| `_window_hidden` | 其他、窗口与托盘、计划 | 3 | 2 | 3 | 2 | 4 |
| `_window_minimized` | 其他、窗口与托盘、计划 | 5 | 1 | 5 | 1 | 6 |

### 跨功能字段逐项：谁读、谁写、在哪把锁里

#### `_activities`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 手机访问 | — | `_phone_raw_state` | `Api._lock` |
| 活动列表 | `_do_list_inner` | `_merge_list_activities` | `Api._lock`、— |
| 计划 | — | `_after_cancelled`、`_confirm_signed`、`_start_plan_inner`、`cancel_signup` | `Api._lock`、— |

#### `_advanced_busy`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 手机访问 | — | `_start_phone_access` | `Api._lock` |
| 登录恢复 | — | `_auto_relogin_eligible` | `Api._lock` |
| 组件 | `_component_finished`、`download_advanced_feature`、`install_advanced_feature`、`remove_advanced_feature` | `advanced_features_state`、`download_advanced_feature`、`install_advanced_feature`、`remove_advanced_feature` | `Api._credential_lock`、`Api._phone_access_lock`、`Api._lock`、`Api._lock`、`Api._phone_access_lock`、`Api._lock`、— |
| 计划 | — | `_cancel_busy_reason_locked` | — |

#### `_auto_relogin`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `__init__`、`bootstrap` | — |
| 登录恢复 | — | `_begin_auto_relogin_once`、`_commit_pending_save`、`_do_check`、`_do_check_inner`、`_manual_relogin_wanted`、`_phone_relay_view`、`_relay_finished`、`_request_auto_relogin`、`_silent_relogin_state`、`clear_relogin_credentials`、`save_relogin_credentials` | `Api._credential_lock`、— |
| 窗口与托盘 | — | `shutdown` | — |
| 组件 | — | `_commit_downloaded_ocr_group`、`_install_downloaded_ocr`、`_install_selected_feature`、`advanced_features_state`、`enable_advanced_feature`、`remove_advanced_feature` | `Api._credential_lock`、`Api._credential_lock`、`Api._phone_access_lock`、— |

#### `_auto_relogin_started_at`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_begin_auto_relogin` | `_anchor_login_success`、`_relay_finished` | `Api._lock`、— |

#### `_aux_procs`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| worker 进程 | — | `_run` | `Api._lock` |
| 其他 | `__init__` | — | — |
| 窗口与托盘 | — | `shutdown` | `Api._lock` |

#### `_aux_trees`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| worker 进程 | — | `_run` | `Api._lock` |
| 其他 | `__init__` | — | — |
| 窗口与托盘 | — | `shutdown` | `Api._lock` |

#### `_cancelling`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `_is_busy_locked` | — |
| 活动列表 | — | `list_activities` | `Api._lock` |
| 登录恢复 | — | `_auto_relogin_eligible`、`_spawn_relay_worker`、`check` | `Api._lock` |
| 计划 | `cancel_signup` | `_cancel_busy_reason_locked` | `Api._lock`、— |

#### `_check_again`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_do_check`、`check` | `_do_check` | `Api._lock` |

#### `_check_last`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__`、`_emit` | — | — |
| 登录恢复 | — | `check` | `Api._lock` |

#### `_check_request_id`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `_emit` | — |
| 登录恢复 | `check` | `check` | `Api._lock` |

#### `_checking`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_do_check`、`check` | `_auto_relogin_eligible`、`_spawn_relay_worker`、`check` | `Api._lock` |
| 计划 | — | `_cancel_busy_reason_locked`、`_start_plan_inner` | `Api._lock`、— |

#### `_clock`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `bootstrap`、`monitor` | — |
| 手机访问 | — | `_phone_raw_state` | — |
| 时钟 | — | `_clock_now`、`_clock_ready`、`_start_clock_monitor`、`clock_snapshot`、`sync_clock` | — |
| 登录恢复 | — | `_anchor_login_success`、`_do_check_inner` | — |

#### `_clock_syncing`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 时钟 | `sync_clock` | `sync_clock` | `Api._lock` |

#### `_close_approved`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 窗口与托盘 | `request_window_close` | — | — |

#### `_closing`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| worker 进程 | — | `_run`、`_spawn` | `Api._lock` |
| 其他 | `__init__` | — | — |
| 手机访问 | — | `_start_phone_access`、`restore_phone_access` | `Api._lock` |
| 更新 | — | `_update_is_closing` | — |
| 活动列表 | — | `_wait_for_list_clock`、`list_activities` | `Api._lock` |
| 登录恢复 | — | `_auto_relogin_eligible`、`_do_check`、`_relogin_entry_gate`、`_spawn_relay_worker`、`check`、`login` | `Api._lock` |
| 窗口与托盘 | `shutdown` | `shutdown` | `Api._lock` |
| 组件 | — | `_commit_downloaded_component_group`、`_commit_downloaded_ocr_group`、`_install_downloaded_component`、`_install_downloaded_ocr`、`_install_selected_feature`、`_wait_component_settled`、`download_advanced_feature`、`enable_advanced_feature`、`install_advanced_feature`、`remove_advanced_feature` | `Api._credential_lock`、`Api._lock`、`Api._credential_lock`、`Api._phone_access_lock`、`Api._lock`、`Api._lock`、`Api._phone_access_lock`、`Api._lock` |
| 计划 | — | `_cancel_busy_reason_locked`、`_run_plan_task`、`_start_plan_inner` | `Api._lock`、— |

#### `_cloudflare`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 手机访问 | — | `_cloudflare_status_snapshot`、`_start_phone_access` | — |
| 登录恢复 | — | `_stop_cloudflare_checked` | — |
| 组件 | — | `_component_installed`、`_install_selected_feature`、`advanced_features_state`、`install_advanced_feature`、`remove_advanced_feature` | `Api._credential_lock`、`Api._phone_access_lock`、— |

#### `_cloudflare_exit_notice`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 手机访问 | `_cloudflare_status_snapshot`、`_start_phone_access`、`stop_phone_access` | `_cloudflare_status_snapshot` | — |

#### `_cloudflare_starting`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 手机访问 | `_start_phone_access` | `_start_phone_access` | — |

#### `_component_service`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 组件 | — | `_component_finished`、`remove_advanced_feature` | `Api._credential_lock`、`Api._phone_access_lock`、— |

#### `_expiry_pushed`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_note_login_conclusion` | `_note_login_conclusion` | `Api._lock` |

#### `_finished_plan_ids`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `emit` | `Api._lock`、— |
| 计划 | — | `_prune_finished_plans_locked`、`_start_plan_inner` | `Api._lock`、— |

#### `_last_check`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `bootstrap` | `Api._lock`、— |
| 手机访问 | — | `_phone_raw_state` | `Api._lock` |
| 登录恢复 | `_do_check`、`_do_check_inner` | `_do_check`、`_do_check_inner` | `Api._lock`、— |
| 计划 | — | `_start_plan_inner` | `Api._lock` |

#### `_last_login_origin`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_anchor_login_success` | — | `Api._lock` |
| 组件 | — | `advanced_features_state` | — |

#### `_last_plan`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__`、`emit` | — | `Api._lock`、— |
| 手机访问 | — | `_phone_raw_state` | `Api._lock` |
| 计划 | `_start_plan_inner` | `_bootstrap_plan_snapshot` | `Api._lock` |

#### `_latest_plan_id`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `emit` | `Api._lock`、— |
| 计划 | `_start_plan_inner` | `_protect_start`、`_start_plan_inner`、`start_request_state` | `Api._lock`、— |

#### `_list_last`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__`、`_emit` | — | — |
| 活动列表 | — | `list_activities` | `Api._lock` |
| 计划 | `_after_cancelled` | `_after_cancelled` | `Api._lock` |

#### `_list_request_id`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `_emit` | — |
| 活动列表 | `list_activities` | `list_activities` | `Api._lock` |

#### `_listing`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 活动列表 | `_do_list`、`list_activities` | `list_activities` | `Api._lock` |
| 登录恢复 | — | `_auto_relogin_eligible`、`_spawn_relay_worker` | `Api._lock` |
| 计划 | — | `_cancel_busy_reason_locked` | — |

#### `_login_expired_logged`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_note_login_conclusion` | — | `Api._lock` |

#### `_login_seen_valid`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_note_login_conclusion` | `_note_login_conclusion` | `Api._lock` |

#### `_login_wait_pending`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_begin_auto_relogin_once`、`_request_auto_relogin` | `_relogin_blocked_locked` | `Api._credential_lock`、`Api._lock`、`Api._lock`、— |

#### `_next_plan_source`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 计划 | `_start_plan_inner`、`start_plan` | — | `Api._lock` |

#### `_ocr_component_service`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 组件 | — | `_component_finished` | — |

#### `_once_creds_rejected`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_relay_finished`、`clear_relogin_credentials`、`prepare_phone_relogin`、`save_relogin_credentials` | `_auto_relogin_paused` | `Api._credential_lock`、`Api._lock`、`Api._lock` |

#### `_pc_list_error`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 手机访问 | — | `_phone_raw_state` | `Api._lock` |
| 活动列表 | `_do_list_inner`、`_note_pc_list_error` | — | `Api._lock` |

#### `_pc_list_ok_at`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 活动列表 | `_do_list_inner` | `_note_pc_list_error` | `Api._lock` |

#### `_pending_save`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_begin_auto_relogin_once`、`_begin_typed_relogin`、`_commit_pending_save`、`_relay_finished`、`prepare_phone_relogin` | `_commit_pending_save` | `Api._credential_lock`、`Api._lock`、`Api._lock` |

#### `_phone`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `_emit` | — |
| 手机访问 | — | `_reconcile_cloudflare_lifecycle`、`_start_phone_access`、`_stop_phone_access`、`phone_access_state`、`restore_phone_access` | `Api._phone_access_lock`、— |
| 窗口与托盘 | — | `ask_window_close`、`hide_window`、`shutdown` | — |
| 组件 | — | `_commit_downloaded_component_group`、`_install_downloaded_component`、`_install_selected_feature`、`install_advanced_feature` | `Api._credential_lock`、`Api._phone_access_lock` |

#### `_phone_channel`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 手机访问 | `_reconcile_cloudflare_lifecycle`、`_start_phone_access`、`_stop_phone_access` | `_reconcile_cloudflare_lifecycle`、`_start_phone_access`、`_stop_phone_access`、`phone_access_state`、`restore_phone_access` | `Api._phone_access_lock`、— |
| 窗口与托盘 | `shutdown` | — | — |
| 组件 | `_commit_downloaded_component_group`、`_install_downloaded_component` | — | `Api._credential_lock`、`Api._phone_access_lock` |

#### `_plan`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__`、`emit` | `_is_busy_locked`、`emit`、`monitor` | `Api._lock`、— |
| 手机访问 | — | `_phone_raw_state` | `Api._lock` |
| 时钟 | — | `_start_clock_monitor` | `Api._lock` |
| 登录恢复 | — | `_relogin_late_answer`、`login` | `Api._lock` |
| 窗口与托盘 | — | `shutdown`、`stop` | `Api._lock` |
| 计划 | `_start_plan_inner` | `_bootstrap_plan_snapshot`、`_cancel_busy_reason_locked`、`_protect_start`、`_start_plan_inner`、`cancel_task`、`start_request_state`、`stop_plan` | `Api._lock`、— |

#### `_plan_generation`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `bootstrap` | `Api._lock`、— |
| 计划 | `_start_plan_inner` | `_start_plan_inner`、`start_request_state` | `Api._lock` |

#### `_plan_procs`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `_is_busy_locked` | — |
| 登录恢复 | — | `_relogin_blocked_locked` | — |
| 窗口与托盘 | — | `shutdown` | `Api._lock` |
| 计划 | — | `_cancel_busy_reason_locked`、`_run_plan_task`、`_terminate_plan_procs` | `Api._lock`、— |

#### `_plan_sources`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 计划 | — | `_plan_source_of`、`_start_plan_inner` | `Api._lock` |

#### `_plan_trees`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 窗口与托盘 | — | `shutdown` | `Api._lock` |
| 计划 | — | `_run_plan_task`、`_terminate_plan_procs` | `Api._lock`、— |

#### `_proc`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| worker 进程 | `_spawn` | — | `Api._lock` |
| 其他 | `__init__`、`_pump` | `_is_busy_locked`、`_pump` | `Api._lock`、— |
| 登录恢复 | `_relay_finished`、`_spawn_relay_worker` | `_relay_finished`、`_relogin_blocked_locked`、`_spawn_relay_worker` | `Api._lock`、— |
| 窗口与托盘 | `stop` | `shutdown`、`stop` | `Api._lock` |
| 计划 | — | `_cancel_busy_reason_locked` | — |

#### `_proc_tree`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| worker 进程 | `_spawn` | — | `Api._lock` |
| 其他 | `__init__`、`_pump` | `_pump` | `Api._lock`、— |
| 登录恢复 | `_relay_finished`、`_spawn_relay_worker` | `_relay_finished` | `Api._lock` |
| 窗口与托盘 | `stop` | `shutdown`、`stop` | `Api._lock` |

#### `_relay`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `__init__`、`_pump` | — |
| 手机访问 | — | `_stop_phone_access` | — |
| 登录恢复 | — | `_begin_auto_relogin`、`_begin_auto_relogin_once`、`_begin_typed_relogin`、`_manual_relogin_wanted`、`_once_credentials_staged`、`_phone_relay_view`、`_relay_finished`、`_silent_relogin_state`、`clear_relogin_credentials`、`phone_relogin_begin`、`phone_relogin_cancel`、`phone_relogin_submit`、`prepare_phone_relogin`、`relogin_auto_once`、`relogin_begin`、`relogin_cancel`、`relogin_submit` | `Api._credential_lock`、— |
| 窗口与托盘 | — | `shutdown` | — |
| 组件 | — | `_commit_downloaded_ocr_group`、`_install_downloaded_ocr`、`_install_selected_feature`、`advanced_features_state`、`remove_advanced_feature` | `Api._credential_lock`、`Api._credential_lock`、`Api._phone_access_lock`、— |

#### `_relay_creds_source`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_begin_auto_relogin_once`、`prepare_phone_relogin` | `_once_credentials_staged`、`_relay_finished` | `Api._credential_lock`、`Api._lock`、`Api._lock` |

#### `_relay_proc_tree`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 登录恢复 | `_relay_finished`、`_spawn_relay_worker` | `_relay_finished` | `Api._lock` |
| 窗口与托盘 | `stop` | `stop` | `Api._lock` |

#### `_shutdown_done_event`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 窗口与托盘 | — | `shutdown` | `Api._lock`、— |

#### `_start_order`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 计划 | — | `_remember_start` | — |

#### `_start_requests`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `_find_request_id`、`annotated`、`emit` | `Api._lock`、— |
| 计划 | — | `_protect_start`、`_remember_start`、`_start_plan_inner`、`cancel_start_request`、`start_plan`、`start_request_state` | `Api._lock`、— |

#### `_tray`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 窗口与托盘 | `_ensure_tray`、`_stop_tray` | `_ensure_tray`、`_notify_window_hidden`、`_stop_tray`、`hide_window`、`show_window` | — |
| 计划 | — | `_notify_plan_done` | — |

#### `_updates`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `bootstrap` | — |
| 更新 | — | `_do_check_update`、`_do_update_download`、`check_update`、`update_cancel`、`update_download`、`update_launch` | — |

#### `_window`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | `_emit` | — |
| 窗口与托盘 | — | `hide_window`、`request_window_close`、`show_window` | — |
| 组件 | — | `_install_selected_feature`、`pick_advanced_component` | — |

#### `_window_hidden`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 窗口与托盘 | `hide_window`、`show_window` | `window_visibility` | `Api._lock`、— |
| 计划 | — | `_notify_plan_done` | — |

#### `_window_minimized`

| 功能 | 写的方法 | 读的方法 | 持锁 |
|---|---|---|---|
| 其他 | `__init__` | — | — |
| 窗口与托盘 | `_on_window_minimized`、`_on_window_restored`、`request_window_close`、`show_window` | — | — |
| 计划 | — | `_notify_plan_done` | — |

## 锁外读写的点

只列跨功能字段；单功能字段的锁外次数见上面两张表的最后一列。

| 字段 | 读写 | 方法 | 行 | 功能 |
|---|---|---|---|---|
| `_activities` | 写 | `Api.__init__` | 835 | 其他 |
| `_activities` | 读 | `Api._merge_list_activities` | 2536 | 活动列表 |
| `_activities` | 写 | `Api._do_list_inner` | 2541 | 活动列表 |
| `_activities` | 读 | `Api._start_plan_inner` | 2911 | 计划 |
| `_advanced_busy` | 写 | `Api.__init__` | 844 | 其他 |
| `_advanced_busy` | 读 | `Api.advanced_features_state` | 1527 | 组件 |
| `_advanced_busy` | 读 | `Api._cancel_busy_reason_locked` | 2403 | 计划 |
| `_auto_relogin` | 写 | `Api.__init__` | 972 | 其他 |
| `_auto_relogin` | 读 | `Api.__init__` | 977 | 其他 |
| `_auto_relogin` | 读 | `Api.bootstrap` | 1162 | 其他 |
| `_auto_relogin` | 读 | `Api.advanced_features_state` | 1593 | 组件 |
| `_auto_relogin` | 读 | `Api._silent_relogin_state` | 1842 | 登录恢复 |
| `_auto_relogin` | 读 | `Api._request_auto_relogin` | 1896 | 登录恢复 |
| `_auto_relogin` | 读 | `Api._manual_relogin_wanted` | 1923 | 登录恢复 |
| `_auto_relogin` | 读 | `Api._phone_relay_view` | 1934 | 登录恢复 |
| `_auto_relogin` | 读 | `Api._do_check` | 2189 | 登录恢复 |
| `_auto_relogin` | 读 | `Api._do_check` | 2194 | 登录恢复 |
| `_auto_relogin` | 读 | `Api._do_check_inner` | 2319 | 登录恢复 |
| `_auto_relogin` | 读 | `Api.shutdown` | 3421 | 窗口与托盘 |
| `_auto_relogin` | 读 | `Api._relay_finished` | 4184 | 登录恢复 |
| `_auto_relogin_started_at` | 写 | `Api.__init__` | 875 | 其他 |
| `_auto_relogin_started_at` | 写 | `Api._begin_auto_relogin` | 1995 | 登录恢复 |
| `_aux_procs` | 写 | `Api.__init__` | 833 | 其他 |
| `_aux_trees` | 写 | `Api.__init__` | 834 | 其他 |
| `_cancelling` | 写 | `Api.__init__` | 864 | 其他 |
| `_cancelling` | 读 | `Api._cancel_busy_reason_locked` | 2395 | 计划 |
| `_cancelling` | 读 | `Api._is_busy_locked` | 4288 | 其他 |
| `_check_again` | 写 | `Api.__init__` | 861 | 其他 |
| `_check_last` | 写 | `Api.__init__` | 868 | 其他 |
| `_check_last` | 写 | `Api._emit` | 1111 | 其他 |
| `_check_request_id` | 写 | `Api.__init__` | 866 | 其他 |
| `_check_request_id` | 读 | `Api._emit` | 1099 | 其他 |
| `_checking` | 写 | `Api.__init__` | 858 | 其他 |
| `_checking` | 读 | `Api._cancel_busy_reason_locked` | 2403 | 计划 |
| `_clock` | 写 | `Api.__init__` | 817 | 其他 |
| `_clock` | 读 | `Api._clock_now` | 984 | 时钟 |
| `_clock` | 读 | `Api._clock_ready` | 991 | 时钟 |
| `_clock` | 读 | `Api._clock_ready` | 989 | 时钟 |
| `_clock` | 读 | `Api.clock_snapshot` | 1036 | 时钟 |
| `_clock` | 读 | `Api.sync_clock` | 1053 | 时钟 |
| `_clock` | 读 | `Api._start_clock_monitor` | 1086 | 时钟 |
| `_clock` | 读 | `Api.bootstrap` | 1157 | 其他 |
| `_clock` | 读 | `Api._do_check_inner` | 2304 | 登录恢复 |
| `_clock` | 读 | `Api._phone_raw_state` | 3532 | 手机访问 |
| `_clock` | 读 | `Api._anchor_login_success` | 4432 | 登录恢复 |
| `_clock` | 读 | `Api.monitor` | 1086 | 其他 |
| `_clock_syncing` | 写 | `Api.__init__` | 818 | 其他 |
| `_close_approved` | 写 | `Api.__init__` | 853 | 其他 |
| `_close_approved` | 写 | `Api.request_window_close` | 3233 | 窗口与托盘 |
| `_closing` | 写 | `Api.__init__` | 851 | 其他 |
| `_closing` | 读 | `Api._update_is_closing` | 2057 | 更新 |
| `_closing` | 读 | `Api._cancel_busy_reason_locked` | 2393 | 计划 |
| `_closing` | 读 | `Api._run_plan_task` | 4315 | 计划 |
| `_cloudflare` | 写 | `Api.__init__` | 945 | 其他 |
| `_cloudflare` | 读 | `Api._stop_cloudflare_checked` | 1317 | 登录恢复 |
| `_cloudflare` | 读 | `Api._component_installed` | 1380 | 组件 |
| `_cloudflare` | 读 | `Api.advanced_features_state` | 1548 | 组件 |
| `_cloudflare` | 读 | `Api.advanced_features_state` | 1575 | 组件 |
| `_cloudflare` | 读 | `Api._cloudflare_status_snapshot` | 3600 | 手机访问 |
| `_cloudflare` | 读 | `Api._start_phone_access` | 3711 | 手机访问 |
| `_cloudflare` | 读 | `Api._start_phone_access` | 3722 | 手机访问 |
| `_cloudflare_exit_notice` | 写 | `Api.__init__` | 954 | 其他 |
| `_cloudflare_exit_notice` | 写 | `Api._cloudflare_status_snapshot` | 3602 | 手机访问 |
| `_cloudflare_exit_notice` | 读 | `Api._cloudflare_status_snapshot` | 3603 | 手机访问 |
| `_cloudflare_exit_notice` | 写 | `Api._start_phone_access` | 3733 | 手机访问 |
| `_cloudflare_exit_notice` | 写 | `Api.stop_phone_access` | 3880 | 手机访问 |
| `_cloudflare_starting` | 写 | `Api.__init__` | 957 | 其他 |
| `_cloudflare_starting` | 读 | `Api._start_phone_access` | 3694 | 手机访问 |
| `_cloudflare_starting` | 写 | `Api._start_phone_access` | 3720 | 手机访问 |
| `_cloudflare_starting` | 写 | `Api._start_phone_access` | 3724 | 手机访问 |
| `_component_service` | 写 | `Api.__init__` | 909 | 其他 |
| `_component_service` | 读 | `Api._component_finished` | 1359 | 组件 |
| `_expiry_pushed` | 写 | `Api.__init__` | 936 | 其他 |
| `_finished_plan_ids` | 写 | `Api.__init__` | 896 | 其他 |
| `_finished_plan_ids` | 读 | `Api._prune_finished_plans_locked` | 2664 | 计划 |
| `_finished_plan_ids` | 读 | `Api._prune_finished_plans_locked` | 2666 | 计划 |
| `_finished_plan_ids` | 读 | `Api._prune_finished_plans_locked` | 2667 | 计划 |
| `_last_check` | 写 | `Api.__init__` | 871 | 其他 |
| `_last_check` | 写 | `Api._do_check_inner` | 2310 | 登录恢复 |
| `_last_check` | 写 | `Api._do_check_inner` | 2264 | 登录恢复 |
| `_last_check` | 读 | `Api._do_check_inner` | 2313 | 登录恢复 |
| `_last_login_origin` | 写 | `Api.__init__` | 933 | 其他 |
| `_last_login_origin` | 读 | `Api.advanced_features_state` | 1597 | 组件 |
| `_last_plan` | 写 | `Api.__init__` | 830 | 其他 |
| `_latest_plan_id` | 写 | `Api.__init__` | 894 | 其他 |
| `_latest_plan_id` | 读 | `Api._protect_start` | 2682 | 计划 |
| `_list_last` | 写 | `Api.__init__` | 869 | 其他 |
| `_list_last` | 写 | `Api._emit` | 1114 | 其他 |
| `_list_request_id` | 写 | `Api.__init__` | 867 | 其他 |
| `_list_request_id` | 读 | `Api._emit` | 1101 | 其他 |
| `_listing` | 写 | `Api.__init__` | 862 | 其他 |
| `_listing` | 读 | `Api._cancel_busy_reason_locked` | 2403 | 计划 |
| `_login_expired_logged` | 写 | `Api.__init__` | 938 | 其他 |
| `_login_seen_valid` | 写 | `Api.__init__` | 935 | 其他 |
| `_login_wait_pending` | 写 | `Api.__init__` | 873 | 其他 |
| `_login_wait_pending` | 读 | `Api._relogin_blocked_locked` | 1886 | 登录恢复 |
| `_next_plan_source` | 写 | `Api.__init__` | 943 | 其他 |
| `_ocr_component_service` | 写 | `Api.__init__` | 920 | 其他 |
| `_ocr_component_service` | 读 | `Api._component_finished` | 1358 | 组件 |
| `_once_creds_rejected` | 写 | `Api.__init__` | 970 | 其他 |
| `_pc_list_error` | 写 | `Api.__init__` | 840 | 其他 |
| `_pc_list_ok_at` | 写 | `Api.__init__` | 841 | 其他 |
| `_pending_save` | 写 | `Api.__init__` | 971 | 其他 |
| `_phone` | 写 | `Api.__init__` | 899 | 其他 |
| `_phone` | 读 | `Api._emit` | 1105 | 其他 |
| `_phone` | 读 | `Api.ask_window_close` | 3183 | 窗口与托盘 |
| `_phone` | 读 | `Api.ask_window_close` | 3184 | 窗口与托盘 |
| `_phone` | 读 | `Api.hide_window` | 3257 | 窗口与托盘 |
| `_phone` | 读 | `Api.shutdown` | 3431 | 窗口与托盘 |
| `_phone` | 读 | `Api.phone_access_state` | 3633 | 手机访问 |
| `_phone` | 读 | `Api._start_phone_access` | 3715 | 手机访问 |
| `_phone` | 读 | `Api._start_phone_access` | 3691 | 手机访问 |
| `_phone` | 读 | `Api._start_phone_access` | 3731 | 手机访问 |
| `_phone` | 读 | `Api._start_phone_access` | 3726 | 手机访问 |
| `_phone` | 读 | `Api._start_phone_access` | 3739 | 手机访问 |
| `_phone` | 读 | `Api._start_phone_access` | 3722 | 手机访问 |
| `_phone` | 读 | `Api.restore_phone_access` | 3784 | 手机访问 |
| `_phone` | 读 | `Api.restore_phone_access` | 3786 | 手机访问 |
| `_phone` | 读 | `Api._stop_phone_access` | 3889 | 手机访问 |
| `_phone_channel` | 写 | `Api.__init__` | 906 | 其他 |
| `_phone_channel` | 写 | `Api.shutdown` | 3432 | 窗口与托盘 |
| `_phone_channel` | 读 | `Api.phone_access_state` | 3651 | 手机访问 |
| `_phone_channel` | 读 | `Api.phone_access_state` | 3653 | 手机访问 |
| `_phone_channel` | 写 | `Api._start_phone_access` | 3718 | 手机访问 |
| `_phone_channel` | 读 | `Api._start_phone_access` | 3691 | 手机访问 |
| `_phone_channel` | 读 | `Api._start_phone_access` | 3691 | 手机访问 |
| `_phone_channel` | 写 | `Api._start_phone_access` | 3727 | 手机访问 |
| `_phone_channel` | 读 | `Api.restore_phone_access` | 3785 | 手机访问 |
| `_phone_channel` | 写 | `Api._stop_phone_access` | 3891 | 手机访问 |
| `_phone_channel` | 读 | `Api._stop_phone_access` | 3890 | 手机访问 |
| `_plan` | 写 | `Api.__init__` | 825 | 其他 |
| `_plan` | 读 | `Api._cancel_busy_reason_locked` | 2397 | 计划 |
| `_plan` | 读 | `Api._cancel_busy_reason_locked` | 2397 | 计划 |
| `_plan` | 读 | `Api._protect_start` | 2683 | 计划 |
| `_plan` | 读 | `Api._protect_start` | 2683 | 计划 |
| `_plan` | 读 | `Api._is_busy_locked` | 4294 | 其他 |
| `_plan` | 读 | `Api._is_busy_locked` | 4295 | 其他 |
| `_plan_generation` | 写 | `Api.__init__` | 893 | 其他 |
| `_plan_procs` | 写 | `Api.__init__` | 826 | 其他 |
| `_plan_procs` | 读 | `Api._relogin_blocked_locked` | 1890 | 登录恢复 |
| `_plan_procs` | 读 | `Api._cancel_busy_reason_locked` | 2399 | 计划 |
| `_plan_procs` | 读 | `Api._is_busy_locked` | 4297 | 其他 |
| `_plan_procs` | 读 | `Api._run_plan_task` | 4313 | 计划 |
| `_plan_sources` | 写 | `Api.__init__` | 944 | 其他 |
| `_plan_trees` | 写 | `Api.__init__` | 828 | 其他 |
| `_plan_trees` | 读 | `Api._run_plan_task` | 4314 | 计划 |
| `_proc` | 写 | `Api.__init__` | 820 | 其他 |
| `_proc` | 读 | `Api._relogin_blocked_locked` | 1888 | 登录恢复 |
| `_proc` | 读 | `Api._relogin_blocked_locked` | 1888 | 登录恢复 |
| `_proc` | 读 | `Api._cancel_busy_reason_locked` | 2401 | 计划 |
| `_proc` | 读 | `Api._cancel_busy_reason_locked` | 2401 | 计划 |
| `_proc` | 读 | `Api._is_busy_locked` | 4292 | 其他 |
| `_proc` | 读 | `Api._is_busy_locked` | 4292 | 其他 |
| `_proc_tree` | 写 | `Api.__init__` | 822 | 其他 |
| `_relay` | 写 | `Api.__init__` | 959 | 其他 |
| `_relay` | 读 | `Api.__init__` | 974 | 其他 |
| `_relay` | 读 | `Api.advanced_features_state` | 1595 | 组件 |
| `_relay` | 读 | `Api.advanced_features_state` | 1596 | 组件 |
| `_relay` | 读 | `Api._silent_relogin_state` | 1836 | 登录恢复 |
| `_relay` | 读 | `Api._once_credentials_staged` | 1866 | 登录恢复 |
| `_relay` | 读 | `Api._manual_relogin_wanted` | 1916 | 登录恢复 |
| `_relay` | 读 | `Api._phone_relay_view` | 1933 | 登录恢复 |
| `_relay` | 读 | `Api._begin_auto_relogin` | 2004 | 登录恢复 |
| `_relay` | 读 | `Api.shutdown` | 3424 | 窗口与托盘 |
| `_relay` | 读 | `Api._stop_phone_access` | 3885 | 手机访问 |
| `_relay` | 读 | `Api.prepare_phone_relogin` | 3919 | 登录恢复 |
| `_relay` | 读 | `Api._begin_typed_relogin` | 4002 | 登录恢复 |
| `_relay` | 读 | `Api.relogin_begin` | 4034 | 登录恢复 |
| `_relay` | 读 | `Api.relogin_submit` | 4043 | 登录恢复 |
| `_relay` | 读 | `Api.relogin_cancel` | 4047 | 登录恢复 |
| `_relay` | 读 | `Api.relogin_cancel` | 4051 | 登录恢复 |
| `_relay` | 读 | `Api.relogin_auto_once` | 4061 | 登录恢复 |
| `_relay` | 读 | `Api.phone_relogin_begin` | 4100 | 登录恢复 |
| `_relay` | 读 | `Api.phone_relogin_begin` | 4085 | 登录恢复 |
| `_relay` | 读 | `Api.phone_relogin_begin` | 4097 | 登录恢复 |
| `_relay` | 读 | `Api.phone_relogin_submit` | 4105 | 登录恢复 |
| `_relay` | 读 | `Api.phone_relogin_cancel` | 4108 | 登录恢复 |
| `_relay` | 读 | `Api.phone_relogin_cancel` | 4114 | 登录恢复 |
| `_relay` | 读 | `Api._relay_finished` | 4158 | 登录恢复 |
| `_relay` | 读 | `Api._relay_finished` | 4178 | 登录恢复 |
| `_relay` | 读 | `Api._pump` | 4453 | 其他 |
| `_relay_creds_source` | 写 | `Api.__init__` | 967 | 其他 |
| `_relay_proc_tree` | 写 | `Api.__init__` | 824 | 其他 |
| `_shutdown_done_event` | 写 | `Api.__init__` | 856 | 其他 |
| `_shutdown_done_event` | 读 | `Api.shutdown` | 3478 | 窗口与托盘 |
| `_start_order` | 写 | `Api.__init__` | 887 | 其他 |
| `_start_order` | 读 | `Api._remember_start` | 2691 | 计划 |
| `_start_order` | 读 | `Api._remember_start` | 2693 | 计划 |
| `_start_order` | 读 | `Api._remember_start` | 2694 | 计划 |
| `_start_order` | 读 | `Api._remember_start` | 2692 | 计划 |
| `_start_order` | 读 | `Api._remember_start` | 2699 | 计划 |
| `_start_order` | 读 | `Api._remember_start` | 2695 | 计划 |
| `_start_requests` | 写 | `Api.__init__` | 886 | 其他 |
| `_start_requests` | 读 | `Api._protect_start` | 2675 | 计划 |
| `_start_requests` | 读 | `Api._remember_start` | 2690 | 计划 |
| `_start_requests` | 读 | `Api._remember_start` | 2700 | 计划 |
| `_start_requests` | 读 | `Api._remember_start` | 2687 | 计划 |
| `_start_requests` | 读 | `Api._start_plan_inner` | 2952 | 计划 |
| `_start_requests` | 读 | `Api.annotated` | 2952 | 其他 |
| `_tray` | 写 | `Api.__init__` | 855 | 其他 |
| `_tray` | 读 | `Api.hide_window` | 3269 | 窗口与托盘 |
| `_tray` | 读 | `Api._notify_window_hidden` | 3279 | 窗口与托盘 |
| `_tray` | 读 | `Api._notify_window_hidden` | 3280 | 窗口与托盘 |
| `_tray` | 读 | `Api.show_window` | 3300 | 窗口与托盘 |
| `_tray` | 读 | `Api._notify_plan_done` | 3350 | 计划 |
| `_tray` | 读 | `Api._notify_plan_done` | 3351 | 计划 |
| `_tray` | 读 | `Api._ensure_tray` | 3357 | 窗口与托盘 |
| `_tray` | 写 | `Api._ensure_tray` | 3365 | 窗口与托盘 |
| `_tray` | 写 | `Api._ensure_tray` | 3368 | 窗口与托盘 |
| `_tray` | 写 | `Api._stop_tray` | 3373 | 窗口与托盘 |
| `_tray` | 读 | `Api._stop_tray` | 3372 | 窗口与托盘 |
| `_updates` | 写 | `Api.__init__` | 881 | 其他 |
| `_updates` | 读 | `Api.bootstrap` | 1196 | 其他 |
| `_updates` | 读 | `Api.check_update` | 2061 | 更新 |
| `_updates` | 读 | `Api._do_check_update` | 2068 | 更新 |
| `_updates` | 读 | `Api.update_download` | 2074 | 更新 |
| `_updates` | 读 | `Api._do_update_download` | 2079 | 更新 |
| `_updates` | 读 | `Api.update_cancel` | 2089 | 更新 |
| `_updates` | 读 | `Api.update_launch` | 2098 | 更新 |
| `_window` | 写 | `Api.__init__` | 819 | 其他 |
| `_window` | 读 | `Api._emit` | 1106 | 其他 |
| `_window` | 读 | `Api._emit` | 1119 | 其他 |
| `_window` | 读 | `Api.pick_advanced_component` | 1628 | 组件 |
| `_window` | 读 | `Api.pick_advanced_component` | 1632 | 组件 |
| `_window` | 读 | `Api._install_selected_feature` | 1693 | 组件 |
| `_window` | 读 | `Api._install_selected_feature` | 1695 | 组件 |
| `_window` | 读 | `Api.request_window_close` | 3235 | 窗口与托盘 |
| `_window` | 读 | `Api.request_window_close` | 3228 | 窗口与托盘 |
| `_window` | 读 | `Api.hide_window` | 3263 | 窗口与托盘 |
| `_window` | 读 | `Api.show_window` | 3289 | 窗口与托盘 |
| `_window` | 读 | `Api.show_window` | 3294 | 窗口与托盘 |
| `_window_hidden` | 写 | `Api.__init__` | 940 | 其他 |
| `_window_hidden` | 写 | `Api.hide_window` | 3267 | 窗口与托盘 |
| `_window_hidden` | 写 | `Api.show_window` | 3297 | 窗口与托盘 |
| `_window_hidden` | 读 | `Api._notify_plan_done` | 3346 | 计划 |
| `_window_minimized` | 写 | `Api.__init__` | 941 | 其他 |
| `_window_minimized` | 写 | `Api.request_window_close` | 3231 | 窗口与托盘 |
| `_window_minimized` | 写 | `Api.show_window` | 3298 | 窗口与托盘 |
| `_window_minimized` | 写 | `Api._on_window_minimized` | 3313 | 窗口与托盘 |
| `_window_minimized` | 写 | `Api._on_window_restored` | 3316 | 窗口与托盘 |
| `_window_minimized` | 读 | `Api._notify_plan_done` | 3346 | 计划 |

## 只读过、没赋过值的 `self.X`（类常量与模块级名字，不归任何服务）

`CANCEL_BUSY_TEXT`、`CANCEL_WORKER_TIMEOUT_S`、`FINISHED_PLAN_KEEP`、`SIGNED_SYNC_WINDOW_S`、`START_KEEP`、`_after_cancelled`、`_anchor_login_success`、`_auto_relogin_eligible`、`_auto_relogin_paused`、`_begin_auto_relogin`、`_begin_auto_relogin_once`、`_begin_typed_relogin`、`_bootstrap_plan_snapshot`、`_cancel_busy_reason_locked`、`_cancel_refusal`、`_cancel_signup_run`、`_classify_captcha`、`_clock_now`、`_clock_payload`、`_clock_ready`、`_close_plan_burden`、`_cloudflare_status_snapshot`、`_commit_downloaded_component_group`、`_commit_downloaded_ocr_group`、`_commit_pending_save`、`_component_finished`、`_component_installed`、`_component_service_for`、`_confirm_signed`、`_do_check`、`_do_check_inner`、`_do_check_update`、`_do_list`、`_do_list_inner`、`_do_update_download`、`_emit`、`_ensure_tray`、`_find_request_id`、`_forget_phone_autostart`、`_install_downloaded_component`、`_install_downloaded_ocr`、`_install_selected_feature`、`_is_busy_locked`、`_log_event`、`_manual_relogin_wanted`、`_merge_list_activities`、`_note_login_conclusion`、`_note_pc_list_error`、`_notify_plan_done`、`_notify_window_hidden`、`_ocr_component_installed`、`_once_credentials_staged`、`_pc_clock_text`、`_phone_raw_state`、`_phone_relay_view`、`_phone_relogin_setup`、`_plan_source_of`、`_protect_start`、`_prune_finished_plans_locked`、`_pump`、`_push_login_expired`、`_reconcile_cloudflare_lifecycle`、`_relay_finished`、`_relogin_blocked_locked`、`_relogin_entry_gate`、`_relogin_late_answer`、`_relogin_manual_case`、`_relogin_ocr_ready`、`_relogin_wait_s`、`_remember_close_action`、`_remember_phone_channel`、`_remember_start`、`_request_auto_relogin`、`_resolve_component_asset`、`_run`、`_run_plan_task`、`_silent_relogin_ready`、`_silent_relogin_state`、`_spawn`、`_spawn_relay_worker`、`_start_phone_access`、`_start_plan_inner`、`_start_replay`、`_stop_cloudflare_checked`、`_stop_phone_access`、`_stop_tray`、`_terminate_plan_procs`、`_terms_gate`、`_trace`、`_update_is_closing`、`_wait_component_settled`、`_wait_for_list_clock`、`advanced_component_location`、`advanced_features_state`、`check`、`clock_snapshot`、`download_advanced_feature`、`help`、`hide_window`、`inspect_advanced_component`、`plan_active_for_close`、`prepare_phone_relogin`、`request_window_close`、`restore_phone_access`、`schedule_component_auto_update`、`show_window`、`start_phone_access`、`stop_phone_access`、`stop_plan`

## 动态访问（getattr / setdefault，不并进上面的计数）

| 位置 | 写法 | 行 | 表达式 |
|---|---|---|---|
| `Api._start_clock_monitor` | getattr | 1067 | `getattr(self, '_clock_monitor_started', False)` |
| `Api.bootstrap` | setdefault | 1203 | `boot_plan.setdefault('source', self._plan_source_of(boot_plan.get('pla` |
| `Api.bootstrap` | setdefault | 1204 | `boot_plan.setdefault('request_id', self._find_request_id(boot_plan.get` |
| `Api._component_service_for` | getattr | 1420 | `getattr(self, name)` |
| `Api.download_advanced_feature` | getattr | 1429 | `getattr(sys, 'frozen', False)` |
| `Api.enable_advanced_feature` | getattr | 1472 | `getattr(sys, 'frozen', False)` |
| `Api.advanced_features_state` | getattr | 1526 | `getattr(sys, 'frozen', False)` |
| `Api._install_selected_feature` | getattr | 1690 | `getattr(sys, 'frozen', False)` |
| `Api.remove_advanced_feature` | getattr | 1749 | `getattr(sys, 'frozen', False)` |
| `Api._note_login_conclusion` | getattr | 2214 | `getattr(self, '_login_expired_logged', False)` |
| `Api.start_request_state` | getattr | 2718 | `getattr(self, '_canceled_start_ids', set())` |
| `Api.cancel_start_request` | setdefault | 2757 | `self.__dict__.setdefault('_canceled_start_ids', set())` |
| `Api.start_plan` | getattr | 2799 | `getattr(self, '_canceled_start_ids', set())` |
| `Api._start_plan_inner` | setdefault | 2948 | `data.setdefault('plan_id', plan_id)` |
| `Api._start_plan_inner` | getattr | 2856 | `getattr(self, '_next_plan_source', 'desktop')` |
| `Api.plan_active_for_close` | getattr | 3132 | `getattr(self, '_plan', None)` |
| `Api._close_plan_burden` | getattr | 3150 | `getattr(self, '_plan', None)` |
| `Api.shutdown` | getattr | 3418 | `getattr(self, name, None)` |
| `Api._phone_raw_state` | setdefault | 3531 | `snapshot.setdefault('source', self._plan_source_of(snapshot.get('plan_` |
| `Api.phone_access_state` | getattr | 3636 | `getattr(sys, 'frozen', False)` |
| `Api.schedule_phone_restore` | getattr | 3804 | `getattr(getattr(window, 'events', None), 'loaded', None)` |
| `Api.schedule_phone_restore` | getattr | 3804 | `getattr(window, 'events', None)` |
| `Api.schedule_component_auto_update` | getattr | 3828 | `getattr(sys, 'frozen', False)` |
| `Api.schedule_component_auto_update` | getattr | 3833 | `getattr(getattr(window, 'events', None), 'loaded', None)` |
| `Api.schedule_component_auto_update` | getattr | 3833 | `getattr(window, 'events', None)` |
| `Api.schedule_component_auto_update` | getattr | 3840 | `getattr(sys, 'frozen', False)` |
| `Api.run` | getattr | 3833 | `getattr(getattr(window, 'events', None), 'loaded', None)` |
| `Api.run` | getattr | 3833 | `getattr(window, 'events', None)` |
| `Api.run` | getattr | 3840 | `getattr(sys, 'frozen', False)` |
| `Api.annotated` | setdefault | 2948 | `data.setdefault('plan_id', plan_id)` |

