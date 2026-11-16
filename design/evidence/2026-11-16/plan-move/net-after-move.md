# 搬完重跑安全网：已守的 354 条、等价的 10 条与出口 P14 在新位置重做一次

## 口径

- **行清单**：`rows.json`，一条一行。来自计划栏安全网那一批的候选，**函数名、那一行的文字、第几次出现、变异写法一个字不改**，只把文件路径换成搬完的新位置；`verdict` 记它在那一批里的结论（`已守` / `等价`）。
- **怎么跑**：与那一批同一条执行路径——只在仓库副本里改一处，改完先过 `node --check`；已守的先跑它在那一批里记录的那个测试文件（首红即停），没红再跑其余四个；等价的跑完五个文件，结果仍应不红。四进程并行。
- **另加一行**：出口那一批的 P14（`handlePlan` 里删掉 `S.editing = null`），在新位置 `features/plan/actions.js` 上重做一次。

## 数字

| 项 | 条数 |
|---|---:|
| 已守：仍然变红 | 355 |
| 已守：没变红 | 0 |
| 已守：变异不成立（语法错） | 0 |
| 等价：仍不改变可见结果（五个文件都没红） | 10 |
| 等价：变红了 | 0 |
| 等价：变异不成立（语法错） | 0 |
| 合计 | 365 |


## 不是红的那几行

| 文件 · 函数 | 结论 | 条数 |
|---|---|---:|
| view.js · `paintBoardActions` | 等价（仍不红） | 3 |
| view.js · `paintRunPanel` | 等价（仍不红） | 2 |
| view.js · `setBoardTag` | 等价（仍不红） | 1 |
| view.js · `paintBoardState` | 等价（仍不红） | 1 |
| view.js · `paintEditNote` | 等价（仍不红） | 1 |
| state-board.js · `resultMode` | 等价（仍不红） | 1 |
| plan-panel.js · `paintWhy` | 等价（仍不红） | 1 |

## 逐行对照

| 编号 | 新位置：文件 · 函数 | 那一批的结论 | 搬后 | 首红用例 |
|---|---|---|---|---|
| M001 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_first_use_board_invites_login` |
| M005 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_login_start_reports_failure_and_keeps_previous_session` |
| M009 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M013 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_terms_hold_board_stops_at_terms_before_selection` |
| M017 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M021 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M025 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M029 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_contract_plan.py | `test_future_prewarm_is_not_reported_as_submitting` |
| M033 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M037 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M041 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_separates_school_empty_from_no_target` |
| M045 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M049 | `state-board.js` · `selectionSummary` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M053 | `state-board.js` · `runTagText` | 已守 | 红 · test_ui_plan_board.py | `test_waiting_plan_shows_waiting_target_and_cancel_action` |
| M062 | `view.js` · `setBoardTag` | 等价 | 没红 |  |
| M068 | `state-board.js` · `boardPlanState` | 已守 | 红 · test_ui_contract_plan.py | `test_result_all_success_shows_mini_led` |
| M072 | `view.js` · `paintBoardState` | 等价 | 没红 |  |
| M078 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_pick_and_clear_controls_follow_selection_and_run_state` |
| M085 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_pick_and_clear_controls_follow_selection_and_run_state` |
| M089 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M094 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M099 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_flow.py | `test_restore_edited_plan_sends_original_selection` |
| M103 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M108 | `view.js` · `paintEditNote` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M116 | `state-board.js` · `resultMode` | 已守 | 红 · test_ui_exit_paths_plan.py | `test_P14_a_new_plan_event_leaves_editing` |
| M128 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M132 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M137 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M145 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| M152 | `plan-panel.js` · `paintWhy` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| M159 | `state-board.js` · `planLate` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M165 | `view.js` · `paintRunPanel` | 等价 | 没红 |  |
| M174 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_run_warning_explains_auto_login_and_both_relogin_windows` |
| M181 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M186 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M193 | `actions.js` · `verifyTask` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M202 | `state-board.js` · `resultCounts` | 已守 | 红 · test_ui_main_window_plan.py | `test_missed_is_counted_apart_and_never_double_counted` |
| M206 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_plan_flow.py | `test_natural_end_cancels_editing_and_opens_result` |
| M212 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_plan_board.py | `test_result_page_distinguishes_pending_from_total_failure` |
| M217 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_contract_plan.py | `test_result_only_full_has_no_reselect` |
| M223 | `state-board.js` · `reselectableIds` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M228 | `view.js` · `paintResultPanel` | 已守 | 红 · test_ui_contract_plan.py | `test_result_all_success_shows_mini_led` |
| M234 | `view.js` · `paintPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_task_events_keep_the_terminal_fact_and_update_the_card` |
| M245 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M249 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M254 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M260 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M267 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M278 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_unconfirmed_task_switches_from_cancel_to_verify` |
| M283 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_controls_disable_login_refresh_and_clear_at_their_own_gates` |
| M287 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_start_timeout_enters_reconciliation_without_restarting` |
| M298 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_enter_during_running_plan_does_not_start_again` |
| M302 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_start_timeout_enters_reconciliation_without_restarting` |
| M306 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_start_and_stop_buttons_follow_the_run_phase` |
| M311 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M316 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_controls_disable_login_refresh_and_clear_at_their_own_gates` |
| M329 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M337 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M348 | `state.js` · `maxPlanGen` | 已守 | 红 · test_ui_plan_flow.py | `test_old_plan_event_cannot_replace_current_running_plan` |
| M357 | `actions.js` · `handlePlan` | 已守 | 红 · test_ui_plan_flow.py | `test_old_plan_event_cannot_replace_current_running_plan` |
| M367 | `actions.js` · `handlePlan` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_started_plan_logs_one_start_line` |
| M383 | `state.js` · `resultPageOpen` | 已守 | 红 · test_ui_contract_plan.py | `test_result_partial_with_pending_and_no_fallback` |
| M411 | `state-task.js` · `taskDisplayPhase` | 已守 | 红 · test_ui_contract_plan.py | `test_snapshot_restore_without_selection_or_list_item` |
| M415 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_contract_plan.py | `test_activity_row_tracks_phase_and_open_time` |
| M420 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M424 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M431 | `state-task.js` · `taskPrepared` | 已守 | 红 · test_ui_contract_plan.py | `test_task_prepared_uses_checkpoint_time` |
| M436 | `state-task.js` · `taskDisplayDetail` | 已守 | 红 · test_ui_plan_board.py | `test_prepared_task_uses_checkpoint_in_visible_detail` |
| M442 | `state-task.js` · `taskDisplayDetail` | 已守 | 红 · test_ui_plan_board.py | `test_task_cards_explain_login_wait_and_submission_phase` |
| M453 | `state-task.js` · `executionView` | 已守 | 红 · test_ui_plan_board.py | `test_modify_gate_closes_on_each_late_condition` |
| M459 | `state-task.js` · `telemetryDeadline` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M464 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_run_submitting_single_caption_and_cancel_label` |
| M468 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_absolute_deadline_needs_no_anchor` |
| M475 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_truncation_fallback_and_telemetry` |
| M479 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_enter_during_running_plan_does_not_start_again` |
| M488 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_refuses_before_sending_anything` |
| M505 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_sends_full_items_and_waits_on_pending` |
| M510 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_rejection_branches_show_their_own_exit` |
| M519 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` |
| M532 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M547 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconciliation_failure_leaves_visible_unknown_result` |
| M562 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M580 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconciliation_failure_leaves_visible_unknown_result` |
| M599 | `plan.js` · `adoptPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M623 | `plan.js` · `stopAskKey` | 已守 | 红 · test_ui_contract_plan.py | `test_escape_closes_and_returns_focus_to_stop_button` |
| M629 | `plan.js` · `stopAskKey` | 已守 | 红 · test_ui_contract_plan.py | `test_enter_and_search_keys_do_not_reach_background` |
| M635 | `plan.js` · `confirmStopPlan` | 已守 | 红 · test_ui_contract_plan.py | `test_confirm_runs_existing_stop_flow_once` |
| M641 | `plan.js` · `noteStartedFromPhone` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_started_plan_logs_one_start_line` |
| M651 | `plan.js` · `restoreEditedPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_restore_edited_plan_sends_original_selection` |
| M656 | `plan.js` · `restoreEditedPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_restore_edited_plan_sends_original_selection` |
| M670 | `plan.js` · `doLogin` | 已守 | 红 · test_ui_plan_flow.py | `test_login_start_reports_failure_and_keeps_previous_session` |
| P14 | `actions.js` · `handlePlan` | 已守 | 红 · test_ui_exit_paths_plan.py | `test_P14_a_new_plan_event_leaves_editing` |
| M002 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_late_same_plan_events_do_not_revive_terminal_plan` |
| M006 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_late_same_plan_events_do_not_revive_terminal_plan` |
| M010 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_terms_hold_board_stops_at_terms_before_selection` |
| M014 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M018 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_names_login_component_error_and_loading_states` |
| M022 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M026 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M030 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M034 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` |
| M038 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M042 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_separates_school_empty_from_no_target` |
| M046 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_start_and_stop_buttons_follow_the_run_phase` |
| M050 | `state-board.js` · `runTagText` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_uses_tone_and_caption_for_each_phase` |
| M055 | `state-board.js` · `runCaption` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_uses_tone_and_caption_for_each_phase` |
| M065 | `state-board.js` · `boardPlanState` | 已守 | 红 · test_ui_contract_plan.py | `test_all_terminal_waits_for_plan_done` |
| M069 | `state-board.js` · `boardPlanState` | 已守 | 红 · test_ui_plan_board.py | `test_result_page_distinguishes_pending_from_total_failure` |
| M073 | `view.js` · `paintBoardActions` | 等价 | 没红 |  |
| M080 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M086 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_pick_and_clear_controls_follow_selection_and_run_state` |
| M090 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M095 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M100 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M104 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M111 | `view.js` · `paintEditNote` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M120 | `state-board.js` · `boardTargetItem` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M129 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M133 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_flow.py | `test_enter_during_running_plan_does_not_start_again` |
| M138 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M146 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M153 | `plan-panel.js` · `paintWhy` | 已守 | 红 · test_ui_plan_flow.py | `test_enter_during_running_plan_does_not_start_again` |
| M160 | `state-board.js` · `planLate` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M170 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M175 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_run_warning_explains_auto_login_and_both_relogin_windows` |
| M182 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M190 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M195 | `actions.js` · `verifyTask` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M203 | `state-board.js` · `resultCounts` | 已守 | 红 · test_ui_plan_board.py | `test_result_page_distinguishes_pending_from_total_failure` |
| M207 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_contract_plan.py | `test_result_stopped_counts_canceled` |
| M213 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_main_window_plan.py | `test_result_dock_shows_the_conclusion_from_the_result_page` |
| M220 | `state-board.js` · `reselectableIds` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M224 | `view.js` · `paintResultPanel` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M229 | `view.js` · `paintResultPanel` | 已守 | 红 · test_ui_contract_plan.py | `test_result_all_success_shows_mini_led` |
| M239 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_prepared_task_uses_checkpoint_in_visible_detail` |
| M246 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M251 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M256 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M262 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M270 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M280 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_waiting_plan_shows_waiting_target_and_cancel_action` |
| M284 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_controls_disable_login_refresh_and_clear_at_their_own_gates` |
| M290 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_start_timeout_enters_reconciliation_without_restarting` |
| M299 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_enter_during_running_plan_does_not_start_again` |
| M303 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_start_timeout_enters_reconciliation_without_restarting` |
| M307 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_start_and_stop_buttons_follow_the_run_phase` |
| M312 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_stop_rejection_clears_stopping_and_editing` |
| M318 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_controls_disable_login_refresh_and_clear_at_their_own_gates` |
| M332 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M338 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M351 | `state.js` · `planEventOwns` | 已守 | 红 · test_ui_plan_flow.py | `test_natural_end_cancels_editing_and_opens_result` |
| M358 | `actions.js` · `handlePlan` | 已守 | 红 · test_ui_plan_flow.py | `test_natural_end_cancels_editing_and_opens_result` |
| M368 | `actions.js` · `handlePlan` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_plan_restored_after_reload_does_not_log_again` |
| M405 | `state-task.js` · `taskDisplayPhase` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M412 | `state-task.js` · `taskDisplayPhase` | 已守 | 红 · test_ui_contract_plan.py | `test_snapshot_restore_without_selection_or_list_item` |
| M417 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M421 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M425 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M432 | `state-task.js` · `taskPrepared` | 已守 | 红 · test_ui_plan_board.py | `test_prepared_task_uses_checkpoint_in_visible_detail` |
| M438 | `state-task.js` · `taskDisplayDetail` | 已守 | 红 · test_ui_plan_board.py | `test_prepared_task_uses_checkpoint_in_visible_detail` |
| M445 | `state-task.js` · `executionView` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M455 | `state-task.js` · `executionView` | 已守 | 红 · test_ui_plan_board.py | `test_pick_and_clear_controls_follow_selection_and_run_state` |
| M460 | `state-task.js` · `submittingDetail` | 已守 | 红 · test_ui_contract_plan.py | `test_run_submitting_single_caption_and_cancel_label` |
| M465 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_truncation_fallback_and_telemetry` |
| M469 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_absolute_deadline_needs_no_anchor` |
| M476 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_absolute_deadline_needs_no_anchor` |
| M481 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_enter_during_running_plan_does_not_start_again` |
| M489 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_refuses_before_sending_anything` |
| M507 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_rejection_branches_show_their_own_exit` |
| M511 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_rejection_branches_show_their_own_exit` |
| M521 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` |
| M533 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M558 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M568 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_exit_paths_plan.py | `test_P03_canceled_reconciliation_releases_the_start_button` |
| M590 | `plan.js` · `adoptPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M607 | `plan.js` · `adoptPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M624 | `plan.js` · `stopAskKey` | 已守 | 红 · test_ui_contract_plan.py | `test_tab_cycles_between_the_two_buttons_only` |
| M632 | `plan.js` · `stopPlan` | 已守 | 红 · test_ui_contract_plan.py | `test_no_plan_means_no_prompt` |
| M636 | `plan.js` · `confirmStopPlan` | 已守 | 红 · test_ui_contract_plan.py | `test_confirm_runs_existing_stop_flow_once` |
| M642 | `plan.js` · `noteStartedFromPhone` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_started_plan_logs_one_start_line` |
| M653 | `plan.js` · `restoreEditedPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_restore_edited_plan_sends_original_selection` |
| M661 | `plan.js` · `doStopPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_stop_rejection_clears_stopping_and_editing` |
| M672 | `plan.js` · `doLogin` | 已守 | 红 · test_ui_plan_flow.py | `test_login_start_reports_failure_and_keeps_previous_session` |
| M003 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M007 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M011 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M015 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M019 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M023 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M027 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M031 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_uses_tone_and_caption_for_each_phase` |
| M035 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_uses_tone_and_caption_for_each_phase` |
| M039 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M043 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_never_falls_back_to_draft_states` |
| M047 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M051 | `state-board.js` · `runTagText` | 已守 | 红 · test_ui_contract_plan.py | `test_future_prewarm_is_not_reported_as_submitting` |
| M058 | `state-board.js` · `runCaption` | 已守 | 红 · test_ui_contract_plan.py | `test_run_submitting_single_caption_and_cancel_label` |
| M066 | `state-board.js` · `boardPlanState` | 已守 | 红 · test_ui_contract_plan.py | `test_all_terminal_waits_for_plan_done` |
| M070 | `state-board.js` · `boardPlanState` | 已守 | 红 · test_ui_plan_board.py | `test_result_page_distinguishes_pending_from_total_failure` |
| M074 | `view.js` · `paintBoardActions` | 等价 | 没红 |  |
| M082 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M087 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M091 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M096 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M101 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M105 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M113 | `view.js` · `paintEditNote` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M126 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M130 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M134 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M141 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_contract_plan.py | `test_draft_clock_blocker_resyncs_directly` |
| M147 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M154 | `plan-panel.js` · `paintWhy` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M161 | `view.js` · `paintRunPanel` | 等价 | 没红 |  |
| M172 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M176 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M183 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M191 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M198 | `state-board.js` · `resultCounts` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M204 | `state-board.js` · `resultCounts` | 已守 | 红 · test_ui_main_window_plan.py | `test_all_missed_conclusion_title_body_and_red_frame` |
| M209 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_contract_plan.py | `test_single_failure_does_not_paint_plan` |
| M215 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_plan_board.py | `test_result_page_distinguishes_pending_from_total_failure` |
| M221 | `state-board.js` · `reselectableIds` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M226 | `view.js` · `paintResultPanel` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M232 | `view.js` · `paintPlan` | 已守 | 红 · test_ui_plan_board.py | `test_unconfirmed_task_switches_from_cancel_to_verify` |
| M243 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M247 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M252 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M258 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M263 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M272 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M281 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_controls_disable_login_refresh_and_clear_at_their_own_gates` |
| M285 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_start_and_stop_buttons_follow_the_run_phase` |
| M292 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| M300 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_sends_full_items_and_waits_on_pending` |
| M304 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_start_and_stop_buttons_follow_the_run_phase` |
| M309 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M313 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_stop_rejection_clears_stopping_and_editing` |
| M319 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_controls_disable_login_refresh_and_clear_at_their_own_gates` |
| M333 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M342 | `state.js` · `mergeTask` | 已守 | 红 · test_ui_plan_flow.py | `test_natural_end_cancels_editing_and_opens_result` |
| M352 | `state.js` · `planEventOwns` | 已守 | 红 · test_ui_contract_plan.py | `test_result_all_success_shows_mini_led` |
| M359 | `actions.js` · `handlePlan` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_started_plan_logs_one_start_line` |
| M376 | `actions.js` · `handleTask` | 已守 | 红 · test_ui_plan_flow.py | `test_task_events_keep_the_terminal_fact_and_update_the_card` |
| M406 | `state-task.js` · `taskDisplayPhase` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_uses_tone_and_caption_for_each_phase` |
| M413 | `state-task.js` · `taskDisplayPhase` | 已守 | 红 · test_ui_plan_flow.py | `test_task_events_keep_the_terminal_fact_and_update_the_card` |
| M418 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M422 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_main_window_plan.py | `test_task_cards_use_the_missed_verb_and_the_prototype_reason` |
| M426 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M433 | `state-task.js` · `taskPrepared` | 已守 | 红 · test_ui_contract_plan.py | `test_task_prepared_uses_checkpoint_time` |
| M440 | `state-task.js` · `taskDisplayDetail` | 已守 | 红 · test_ui_plan_board.py | `test_prepared_task_uses_checkpoint_in_visible_detail` |
| M446 | `state-task.js` · `executionView` | 已守 | 红 · test_ui_plan_flow.py | `test_enter_during_running_plan_does_not_start_again` |
| M456 | `state-task.js` · `verifiedSigned` | 已守 | 红 · test_ui_contract_plan.py | `test_result_stopped_counts_canceled` |
| M462 | `state-task.js` · `submittingDetail` | 已守 | 红 · test_ui_contract_plan.py | `test_run_submitting_single_caption_and_cancel_label` |
| M466 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_absolute_deadline_needs_no_anchor` |
| M473 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_anchor_is_stable_across_open` |
| M477 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_truncation_fallback_and_telemetry` |
| M484 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_refuses_before_sending_anything` |
| M501 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_rejection_branches_show_their_own_exit` |
| M508 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_rejection_branches_show_their_own_exit` |
| M512 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` |
| M526 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_timeout_enters_reconciliation_without_restarting` |
| M544 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconciliation_failure_leaves_visible_unknown_result` |
| M559 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M577 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconciliation_failure_leaves_visible_unknown_result` |
| M592 | `plan.js` · `adoptPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M610 | `plan.js` · `adoptPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M625 | `plan.js` · `stopAskKey` | 已守 | 红 · test_ui_contract_plan.py | `test_tab_cycles_between_the_two_buttons_only` |
| M633 | `plan.js` · `confirmStopPlan` | 已守 | 红 · test_ui_contract_plan.py | `test_confirm_after_plan_ended_does_not_call_backend` |
| M637 | `plan.js` · `noteStartedFromPhone` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_started_plan_logs_one_start_line` |
| M645 | `plan.js` · `modifyPlan` | 已守 | 红 · test_ui_main_window_plan.py | `test_modify_plan_logs_the_paused_line_with_the_draft_count` |
| M654 | `plan.js` · `restoreEditedPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_restore_edited_plan_sends_original_selection` |
| M662 | `plan.js` · `doStopPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_stop_rejection_clears_stopping_and_editing` |
| M673 | `plan.js` · `doLogin` | 已守 | 红 · test_ui_plan_flow.py | `test_login_start_reports_failure_and_keeps_previous_session` |
| M004 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M008 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_never_falls_back_to_draft_states` |
| M012 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_terms_hold_board_stops_at_terms_before_selection` |
| M016 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_never_falls_back_to_draft_states` |
| M020 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_never_falls_back_to_draft_states` |
| M024 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_running_board_never_falls_back_to_draft_states` |
| M028 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M032 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M036 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_board_keeps_busy_terms_and_cached_list_apart` |
| M040 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_separates_school_empty_from_no_target` |
| M044 | `view.js` · `paintSelected` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_separates_school_empty_from_no_target` |
| M048 | `state-board.js` · `selectionSummary` | 已守 | 红 · test_ui_main_window_plan.py | `test_draft_dock_uses_the_summary_sentence_not_the_countdown` |
| M052 | `state-board.js` · `runTagText` | 已守 | 红 · test_ui_plan_board.py | `test_waiting_plan_turns_to_soon_inside_five_seconds` |
| M061 | `state-board.js` · `runCaption` | 已守 | 红 · test_ui_contract_plan.py | `test_run_tag_turns_soon_inside_five_seconds` |
| M067 | `state-board.js` · `boardPlanState` | 已守 | 红 · test_ui_contract_plan.py | `test_single_failure_does_not_paint_plan` |
| M071 | `state-board.js` · `boardPlanState` | 已守 | 红 · test_ui_plan_board.py | `test_result_page_distinguishes_pending_from_total_failure` |
| M075 | `view.js` · `paintBoardActions` | 等价 | 没红 |  |
| M083 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M088 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M092 | `view.js` · `paintBoardActions` | 已守 | 红 · test_ui_plan_board.py | `test_board_actions_show_only_what_the_phase_allows` |
| M097 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M102 | `state-board.js` · `editNoteText` | 已守 | 红 · test_ui_plan_board.py | `test_edit_note_is_visible_only_for_the_editing_draft` |
| M106 | `view.js` · `paintEditNote` | 等价 | 没红 |  |
| M115 | `state-board.js` · `resultMode` | 等价 | 没红 |  |
| M127 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M131 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M136 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M144 | `plan-panel.js` · `startBlocker` | 已守 | 红 · test_ui_plan_board.py | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| M148 | `plan-panel.js` · `paintWhy` | 等价 | 没红 |  |
| M158 | `state-board.js` · `planLate` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M164 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M173 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_run_warning_explains_auto_login_and_both_relogin_windows` |
| M179 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_run_warning_explains_auto_login_and_both_relogin_windows` |
| M185 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_run_warning_explains_auto_login_and_both_relogin_windows` |
| M192 | `view.js` · `paintRunPanel` | 已守 | 红 · test_ui_plan_board.py | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| M201 | `state-board.js` · `resultCounts` | 已守 | 红 · test_ui_contract_plan.py | `test_result_stopped_counts_canceled` |
| M205 | `state-board.js` · `resultCounts` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M211 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M216 | `state-board.js` · `resultView` | 已守 | 红 · test_ui_main_window_plan.py | `test_all_missed_conclusion_title_body_and_red_frame` |
| M222 | `state-board.js` · `reselectableIds` | 已守 | 红 · test_ui_plan_board.py | `test_result_actions_reselect_only_eligible_tasks` |
| M227 | `view.js` · `paintResultPanel` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M233 | `view.js` · `paintPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_task_events_keep_the_terminal_fact_and_update_the_card` |
| M244 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_main_window_plan.py | `test_task_cards_use_the_missed_verb_and_the_prototype_reason` |
| M248 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M253 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_verify_task_switches_the_card_wording` |
| M259 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M264 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M274 | `view.js` · `taskHtml` | 已守 | 红 · test_ui_plan_board.py | `test_waiting_plan_shows_waiting_target_and_cancel_action` |
| M282 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_controls_disable_login_refresh_and_clear_at_their_own_gates` |
| M286 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_main_window_plan.py | `test_draft_priority_blocker_then_warnings_then_summary` |
| M294 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_start_blocker_names_each_missing_step_with_its_action` |
| M301 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_sends_full_items_and_waits_on_pending` |
| M305 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_start_and_stop_buttons_follow_the_run_phase` |
| M310 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M315 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_start_and_stop_buttons_follow_the_run_phase` |
| M327 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M335 | `plan-panel.js` · `updateControls` | 已守 | 红 · test_ui_plan_board.py | `test_stop_button_and_stop_ask_follow_the_plan` |
| M346 | `state.js` · `maxPlanGen` | 已守 | 红 · test_ui_plan_flow.py | `test_old_plan_event_cannot_replace_current_running_plan` |
| M355 | `actions.js` · `advancePlanStatus` | 已守 | 红 · test_ui_plan_flow.py | `test_late_same_plan_events_do_not_revive_terminal_plan` |
| M364 | `actions.js` · `handlePlan` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_started_plan_logs_one_start_line` |
| M379 | `actions.js` · `handleTask` | 已守 | 红 · test_ui_plan_flow.py | `test_task_events_keep_the_terminal_fact_and_update_the_card` |
| M407 | `state-task.js` · `taskDisplayPhase` | 已守 | 红 · test_ui_contract_plan.py | `test_activity_row_tracks_phase_and_open_time` |
| M414 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_contract_plan.py | `test_activity_row_tracks_phase_and_open_time` |
| M419 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M423 | `state-task.js` · `taskDisplayLabel` | 已守 | 红 · test_ui_plan_board.py | `test_task_card_writes_each_outcome_in_plain_words` |
| M429 | `state-task.js` · `taskModePrefix` | 已守 | 红 · test_ui_main_window_plan.py | `test_task_cards_use_the_missed_verb_and_the_prototype_reason` |
| M435 | `state-task.js` · `taskDisplayDetail` | 已守 | 红 · test_ui_plan_board.py | `test_task_cards_explain_login_wait_and_submission_phase` |
| M441 | `state-task.js` · `taskDisplayDetail` | 已守 | 红 · test_ui_contract_plan.py | `test_future_prewarm_is_not_reported_as_submitting` |
| M447 | `state-task.js` · `executionView` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` |
| M457 | `state-task.js` · `verifiedSigned` | 已守 | 红 · test_ui_contract_plan.py | `test_result_stopped_counts_canceled` |
| M463 | `state-task.js` · `submittingDetail` | 已守 | 红 · test_ui_contract_plan.py | `test_run_submitting_single_caption_and_cancel_label` |
| M467 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_absolute_deadline_needs_no_anchor` |
| M474 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_anchor_is_stable_across_open` |
| M478 | `state-task.js` · `effectiveRetryDeadline` | 已守 | 红 · test_ui_contract_plan.py | `test_truncation_fallback_and_telemetry` |
| M487 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_refuses_before_sending_anything` |
| M502 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_rejection_branches_show_their_own_exit` |
| M509 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_rejection_branches_show_their_own_exit` |
| M518 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` |
| M527 | `plan.js` · `startPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_start_timeout_enters_reconciliation_without_restarting` |
| M545 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconciliation_failure_leaves_visible_unknown_result` |
| M561 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M578 | `plan.js` · `reconcileStart` | 已守 | 红 · test_ui_plan_flow.py | `test_reconciliation_failure_leaves_visible_unknown_result` |
| M598 | `plan.js` · `adoptPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` |
| M621 | `plan.js` · `closeStopAsk` | 已守 | 红 · test_ui_contract_plan.py | `test_escape_closes_and_returns_focus_to_stop_button` |
| M628 | `plan.js` · `stopAskKey` | 已守 | 红 · test_ui_contract_plan.py | `test_enter_and_search_keys_do_not_reach_background` |
| M634 | `plan.js` · `confirmStopPlan` | 已守 | 红 · test_ui_contract_plan.py | `test_confirm_runs_existing_stop_flow_once` |
| M640 | `plan.js` · `noteStartedFromPhone` | 已守 | 红 · test_ui_main_window_plan.py | `test_phone_started_plan_logs_one_start_line` |
| M649 | `plan.js` · `modifyPlan` | 已守 | 红 · test_ui_main_window_plan.py | `test_modify_plan_logs_the_paused_line_with_the_draft_count` |
| M655 | `plan.js` · `restoreEditedPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_restore_edited_plan_sends_original_selection` |
| M663 | `plan.js` · `doStopPlan` | 已守 | 红 · test_ui_plan_flow.py | `test_stop_rejection_clears_stopping_and_editing` |
| M675 | `plan.js` · `doLogin` | 已守 | 红 · test_ui_plan_flow.py | `test_login_start_reports_failure_and_keeps_previous_session` |
