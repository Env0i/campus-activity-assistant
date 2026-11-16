# 计划栏契约测试清点

分类按测试实际做的事情。`行为对应` 指同一用户结果已经由整页 `run_js` 用例覆盖，`无` 指这条测试守的是页面结构、源码形状、后端命令或另一个功能，不在本批补重复行为。

| 测试 | 守的内容 | 现有方式 | 行为对应 |
|---|---|---|---|
| `test_index_wires_led_and_stop_dialog` | LED 与停止确认弹层的页面接线 | 字面 | `test_stop_success_waits_for_plan_done_before_result` |
| `test_led_js_is_pure_renderer` | LED 渲染器边界 | 字面 | 无 |
| `test_stop_only_after_confirmation` | 停止按钮必须经过确认 | 字面 | `test_stop_success_waits_for_plan_done_before_result` |
| `test_open_puts_focus_on_keep_going` | 弹层初始焦点 | 行为 | 既有行为测试 |
| `test_escape_closes_and_returns_focus_to_stop_button` | Esc 关闭与焦点回收 | 行为 | 既有行为测试 |
| `test_keep_going_closes_without_stopping` | 继续计划不发停止 | 行为 | 既有行为测试 |
| `test_confirm_runs_existing_stop_flow_once` | 确认只发一次停止 | 行为 | 既有行为测试 |
| `test_confirm_after_plan_ended_does_not_call_backend` | 计划结束后不再停止 | 行为 | `test_stop_success_waits_for_plan_done_before_result` |
| `test_tab_cycles_between_the_two_buttons_only` | 弹层 Tab 循环 | 行为 | 既有行为测试 |
| `test_enter_and_search_keys_do_not_reach_background` | 键盘事件不穿透 | 行为 | 既有行为测试 |
| `test_no_plan_means_no_prompt` | 无计划不出停止弹层 | 行为 | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| `test_overlay_styles_follow_prototype` | 弹层样式选择器 | 字面 | 无 |
| `test_app_py_kills_process_tree` | 后端进程树终止 | 字面 | 无，属于后端 |
| `test_grab_retry_window_is_hard_deadline` | worker 重试截止 | 字面 | 无，属于后端 |
| `test_grab_finally_never_returns` | worker finally 行为 | 字面 | 无，属于后端 |
| `test_app_js_stopping_feedback` | 停止反馈文案接线 | 字面 | `test_stop_success_waits_for_plan_done_before_result` |
| `test_index_has_policy_controls` | 重试策略控件 | 字面 | `test_retry_for_accepts_adaptive_choice` |
| `test_app_js_saves_and_sends_policy` | 策略值保存与发送 | 字面 | `test_retry_for_accepts_adaptive_choice` |
| `test_app_js_renders_attempts_and_stop_reason` | 次数和停止原因传递 | 字面 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_plan_failure_keeps_silent_recheck` | 计划失败后的静默复查 | 字面 | 无 |
| `test_backend_contract_strings` | 后端契约字符串 | 字面 | 无，属于接口契约 |
| `test_paint_route_has_no_fake_time_fallbacks` | 路线图不伪造时间 | 字面 | 无 |
| `test_worker_payload_carries_lead` | worker 提前准备参数 | 字面 | 无，属于后端参数 |
| `test_scheduler_prepare_semantics` | 调度提前准备语义 | 字面 | 无，属于后端调度 |
| `test_canceled_task_leaves_batch_count` | 取消场次不改变批次数 | 行为 | `test_result_actions_reselect_only_eligible_tasks` |
| `test_success_leaves_target_on_future_activity` | 成功场次不替换未来目标 | 行为 | `test_result_actions_reselect_only_eligible_tasks` |
| `test_preview_open_label_uses_absolute_time` | 预览开放时间标签 | 行为 | `test_waiting_plan_turns_to_soon_inside_five_seconds` |
| `test_submitting_wins_over_waiting` | 提交阶段优先于等待 | 行为 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_all_terminal_waits_for_plan_done` | 全终态等待计划结束 | 行为 | `test_stop_success_waits_for_plan_done_before_result` |
| `test_snapshot_restore_without_selection_or_list_item` | 快照缺列表项时仍显示任务 | 行为 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_single_failure_does_not_paint_plan` | 单场失败不伪造整计划成功 | 行为 | `test_result_actions_reselect_only_eligible_tasks` |
| `test_anchor_is_stable_across_open` | 重试锚点跨开放时刻稳定 | 行为 | `test_prepared_task_uses_checkpoint_in_visible_detail` |
| `test_truncation_fallback_and_telemetry` | 截止时间截断和 telemetry | 行为 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_absolute_deadline_needs_no_anchor` | 绝对截止不需要启动锚点 | 行为 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_activity_row_tracks_phase_and_open_time` | 任务阶段随开放时间变化 | 行为 | `test_waiting_plan_turns_to_soon_inside_five_seconds` |
| `test_future_prewarm_is_not_reported_as_submitting` | 预热不显示提交中 | 行为 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_missing_attempts_is_not_a_submission` | 缺少次数不算已提交 | 行为 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_retry_for_accepts_adaptive_choice` | 自适应重试选择 | 行为 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_list_rows_disabled_while_terms_locked` | 条款未同意时行禁用 | 行为 | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| `test_quick_pick_blocked_by_terms_gate` | 条款门禁挡住快速选场 | 行为 | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| `test_empty_state_does_not_point_to_disabled_refresh` | 空态不指向禁用刷新 | 行为 | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| `test_draft_one_selected_title_and_checks` | 草稿标题和检查条 | 行为 | `test_empty_board_offers_pick_and_selected_board_offers_start` |
| `test_draft_clock_blocker_resyncs_directly` | 时钟门禁给直接校准动作 | 行为 | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| `test_draft_edit_note_counts_down_inside_300_seconds` | 修改说明倒计时 | 行为 | `test_edit_note_is_visible_only_for_the_editing_draft` |
| `test_run_tag_turns_soon_inside_five_seconds` | 五秒内标签改即将开放 | 字面 | `test_waiting_plan_turns_to_soon_inside_five_seconds` |
| `test_run_submitting_single_caption_and_cancel_label` | 单场提交说明与取消按钮 | 字面 | `test_task_cards_explain_login_wait_and_submission_phase` |
| `test_run_warn_relogin_window_and_too_late` | 登录失效及时/来不及提示 | 字面 | `test_login_failure_warning_and_modify_gate_follow_open_window` |
| `test_busy_pill_shows_expired_but_keeps_unknown` | 登录胶囊与计划运行联动 | 字面 | 无，登录功能已有独立行为测试 |
| `test_result_partial_with_pending_and_no_fallback` | 部分结果与待核对 | 字面 | `test_result_actions_reselect_only_eligible_tasks` |
| `test_result_only_full_has_no_reselect` | 名额已满不可重选 | 字面 | `test_result_actions_reselect_only_eligible_tasks` |
| `test_result_stopped_counts_canceled` | 停止结果计数 | 字面 | `test_stop_success_waits_for_plan_done_before_result` |
| `test_result_all_success_shows_mini_led` | 全成功小 LED | 字面 | `test_result_actions_reselect_only_eligible_tasks` |
| `test_result_not_complete_while_a_task_is_still_waiting` | 仍有等待任务不算完成 | 字面 | `test_waiting_plan_shows_waiting_target_and_cancel_action` |
| `test_stop_ask_closes_when_plan_ends` | 计划结束收起停止弹层 | 行为 | `test_stop_success_waits_for_plan_done_before_result` |
| `test_task_prepared_uses_checkpoint_time` | checkpoint 决定已准备好 | 字面 | `test_prepared_task_uses_checkpoint_in_visible_detail` |

属于静态接线、后端命令或其他功能的条目不再重复补计划栏行为用例。属于计划栏显示与按钮的字面条目，在新增两个行为文件中都有对应的用户结果覆盖。
