# 画板转移与当前实现（返工点名版）

以下每行都写出当前实现的行为守护。没有能准确点名的行标为「一致但没人守」，不把源码或画板一致当成验收。

| 画板转移 | 当前实现 | 守护用例 |
|---|---|---|
| 草稿空 → 草稿已选 | 选场后显示已选数量，开始按钮从禁用变可点 | `test_ui_plan_board.PlanBoardBehaviorTests.test_empty_board_offers_pick_and_selected_board_offers_start` |
| 等开放 → 即将开放 | 五秒内标签变即将开放 | `test_ui_plan_board.PlanBoardBehaviorTests.test_waiting_plan_turns_to_soon_inside_five_seconds` |
| 等开放任务卡 | 标题等开放，任务卡给取消 | `test_ui_plan_board.PlanBoardBehaviorTests.test_waiting_plan_shows_waiting_target_and_cancel_action` |
| 提交开始请求 → 没回话 | 先提交中，再进入正在确认，按钮保持禁用 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_start_timeout_enters_reconciliation_without_restarting` |
| 确认中 → 查不到 | 结果未确认并给重新确认 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_reconciliation_failure_leaves_visible_unknown_result` |
| 等开放 → 停止成功 | 正在停止，收到结束事件后打开结果页 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_stop_success_waits_for_plan_done_before_result` |
| 停止被拒绝 | 清掉停止和修改态，记录计划仍运行 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_stop_rejection_clears_stopping_and_editing` |
| 修改中 → 重新开始 | 恢复进入修改前的原计划场次再发起请求 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_restore_edited_plan_sends_original_selection` |
| 修改中 → 计划自然结束 | 修改作废、结果页打开、旧场次不放回 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_natural_end_cancels_editing_and_opens_result` |
| 结果 → 完成 | 清空选择和任务卡，回到草稿 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_finish_result_returns_to_empty_draft` |
| 结果 → 重新选择 | 只放回可重报失败场次 | `test_ui_plan_board.PlanBoardBehaviorTests.test_result_actions_reselect_only_eligible_tasks` |
| 运行中登录失效 | 来得及可重新登录，进入一百秒窗口后禁用修改 | `test_ui_plan_board.PlanBoardBehaviorTests.test_login_failure_warning_and_modify_gate_follow_open_window` |
| 任务卡自动登录等待 | 写电脑正在自动登录的说明 | `test_ui_plan_board.PlanBoardBehaviorTests.test_task_cards_explain_login_wait_and_submission_phase` |
| 任务卡 checkpoint | 写已准备好而不是继续等待 | `test_ui_plan_board.PlanBoardBehaviorTests.test_prepared_task_uses_checkpoint_in_visible_detail` |
| 终态后同计划迟到事件 | 不复活忙态和运行按钮 | `test_ui_plan_flow.PlanFlowBehaviorTests.test_late_same_plan_events_do_not_revive_terminal_plan` |
| 停止中窗口恢复且没有结束事件 | 当前没有独立兜底出口，仍可能停在正在停止 | 一致但没人守，留给后续状态机计划 |
| 停止被拒绝的画板专用「照常进行」标签 | 当前只在运行记录和运行提示中说明 | 现状不同，无期望测试 |
| 结果部分完成、全成功、名额已满、待核对 | 现有契约测试覆盖多种结果排序 | `test_ui_contract_plan.PlanPanelPrototypeTests.test_result_partial_with_pending_and_no_fallback`、`test_result_all_success_shows_mini_led`、`test_result_only_full_has_no_reselect` |
| 预报名预热 | 不把提前打开页面说成提交中 | `test_ui_contract_plan.DisplayPhaseBoundaryTests.test_future_prewarm_is_not_reported_as_submitting` |
| 任务次数阶段 | 有真实提交次数才显示提交中 | `test_ui_contract_plan.DisplayPhaseBoundaryTests.test_activity_row_tracks_phase_and_open_time` |
| 条款未同意 | 行和快速选场受门禁控制 | `test_ui_contract_plan.AcceptanceDefectRegressionTests.test_list_rows_disabled_while_terms_locked`、`test_quick_pick_blocked_by_terms_gate` |
| 停止确认弹层 | 计划结束后不再发停止请求 | `test_ui_contract_plan.StopAskBehaviorTests.test_confirm_after_plan_ended_does_not_call_backend` |

本表仍有两处明确缺口：停止事件丢失后的恢复兜底没有实现，停止被拒绝的专用画板标签没有实现。它们记录为现状，不用错误期望钉死当前代码。
