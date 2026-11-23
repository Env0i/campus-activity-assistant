# 第三组（计划操作）变异结论（补测之后）

- 范围：`local/ui/m/ui-plan.js` 的 13 个顶层函数（`fillRetryOptions` 不含五类节点，其余 12 个函数共 97 条）：甲类（模型及 `pending` 字段写换 `void 0`）28 条、乙类（条件 `C` 换 `!(C)`）31 条、丙类（`.hidden = X` 写换 `void 0`）1 条、丁类（`postAction` 载荷属性换 `undefined`）28 条、戊类（`return true`/`false` 互换）9 条。

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|---|
| M001 | 乙 | `ui-plan.js` | `startPlan` | `if (!canWrite())` | `if (!(!canWrite()))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M002 | 乙 | `ui-plan.js` | `startPlan` | `if (!items.length)` | `if (!(!items.length))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M003 | 乙 | `ui-plan.js` | `startPlan` | `if (model.pending && PhoneModel.startPending(model.pending, Date.now()))` | `if (!(model.pending && PhoneModel.startPending(model.pending, Date.now())))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M004 | 乙 | `ui-plan.js` | `startPlan` | `if (model.pending && !model.pending.done)` | `if (!(model.pending && !model.pending.done))` | 行为守 | `MobileWriteResilienceTests.test_accepted_pending_keeps_the_double_click_window` |
| M005 | 甲 | `ui-plan.js` | `startPlan` | `model.pending = { request_id: requestId, at: Date.now(), done: false };` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M006 | 甲 | `ui-plan.js` | `startPlan` | `model.notice = "";` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_start_plan_payload_and_sync_accept_clears_notice` |
| M007 | 甲 | `ui-plan.js` | `startPlan` | `model.listOpen = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_start_plan_collapses_expanded_list_for_running_plan` |
| M008 | 丁 | `ui-plan.js` | `startPlan` | `action: "start_plan",` | `action: undefined,` | 行为守 | `MobileWriteResilienceTests.test_action_401_returns_to_pairing_without_continuing_poll（超时）` |
| M009 | 丁 | `ui-plan.js` | `startPlan` | `args: { ↵     items, headed: false, ↵     retry_policy: { retry_for_s: Number(model.retry.retry_for_s), ↵                     max_attempts: Number(model.retry.max_attempts \|\| 0) }, ↵     request_id: requestId }` | `args: undefined` | 行为守 | `MobileWriteResilienceTests.test_start_plan_payload_and_sync_accept_clears_notice` |
| M010 | 丁 | `ui-plan.js` | `startPlan` | `items, headed: false,` | `items: undefined, headed: false,` | 行为守 | `MobileWriteResilienceTests.test_start_plan_payload_and_sync_accept_clears_notice` |
| M011 | 丁 | `ui-plan.js` | `startPlan` | `headed: false,` | `headed: undefined,` | 行为守 | `MobileWriteResilienceTests.test_start_plan_payload_and_sync_accept_clears_notice` |
| M012 | 丁 | `ui-plan.js` | `startPlan` | `retry_policy: { retry_for_s: Number(model.retry.retry_for_s), ↵                     max_attempts: Number(model.retry.max_attempts \|\| 0) },` | `retry_policy: undefined,` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M013 | 丁 | `ui-plan.js` | `startPlan` | `retry_for_s: Number(model.retry.retry_for_s),` | `retry_for_s: undefined,` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M014 | 丁 | `ui-plan.js` | `startPlan` | `max_attempts: Number(model.retry.max_attempts \|\| 0)` | `max_attempts: undefined` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M015 | 丁 | `ui-plan.js` | `startPlan` | `request_id: requestId } });` | `request_id: undefined } });` | 行为守 | `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` |
| M016 | 乙 | `ui-plan.js` | `startPlan` | `if (status === 401)` | `if (!(status === 401))` | 行为守 | `MobileWriteResilienceTests.test_action_401_returns_to_pairing_without_continuing_poll` |
| M017 | 乙 | `ui-plan.js` | `startPlan` | `if (body && body.ok && !body.pending)` | `if (!(body && body.ok && !body.pending))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M018 | 甲 | `ui-plan.js` | `startPlan` | `model.pending.done = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_start_plan_payload_and_sync_accept_clears_notice` |
| M019 | 甲 | `ui-plan.js` | `startPlan` | `model.pending.outcome = "accepted";` | `void 0;` | 等价 | — |
| M020 | 乙 | `ui-plan.js` | `startPlan` | `else if (body && body.error)` | `else if (!(body && body.error))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M021 | 乙 | `ui-plan.js` | `reconcile` | `if (model.reconciling)` | `if (!(model.reconciling))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M022 | 乙 | `ui-plan.js` | `reconcile` | `if (!requestId)` | `if (!(!requestId))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M023 | 甲 | `ui-plan.js` | `reconcile` | `model.reconciling = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` |
| M024 | 丁 | `ui-plan.js` | `reconcile` | `action: "start_request_state",` | `action: undefined,` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M025 | 丁 | `ui-plan.js` | `reconcile` | `args: { request_id: requestId }` | `args: undefined` | 行为守 | `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` |
| M026 | 丁 | `ui-plan.js` | `reconcile` | `request_id: requestId` | `request_id: undefined` | 行为守 | `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` |
| M027 | 乙 | `ui-plan.js` | `reconcile` | `if (model.pending !== pending \|\| pending.request_id !== requestId \|\| pending.done \|\| pending.canceling)` | `if (!(model.pending !== pending \|\| pending.request_id !== requestId \|\| pending.done \|\| pending.canceling))` | 行为守 | `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` |
| M028 | 乙 | `ui-plan.js` | `reconcile` | `if (body && (body.state === "accepted" \|\| body.state === "rejected" ↵                \|\| body.state === "canceled"))` | `if (!(body && (body.state === "accepted" \|\| body.state === "rejected" ↵                \|\| body.state === "canceled")))` | 行为守 | `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` |
| M029 | 甲 | `ui-plan.js` | `reconcile` | `pending.done = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M030 | 甲 | `ui-plan.js` | `reconcile` | `pending.outcome = body.state;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M031 | 乙 | `ui-plan.js` | `reconcile` | `if (body.state === "accepted")` | `if (!(body.state === "accepted"))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M032 | 乙 | `ui-plan.js` | `reconcile` | `body.state === "canceled" ↵       ?` | `!(body.state === "canceled") ↵       ?` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M033 | 乙 | `ui-plan.js` | `reconcile` | `body.state === "canceled" ? "info"` | `!(body.state === "canceled") ? "info"` | 行为守 | `MobileWriteResilienceTests.test_reconcile_single_flight_payload_and_canceled_banner_kind` |
| M034 | 乙 | `ui-plan.js` | `reconcile` | `if (body && body.state === "unknown")` | `if (!(body && body.state === "unknown"))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M035 | 甲 | `ui-plan.js` | `reconcile` | `model.reconciling = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M036 | 乙 | `ui-plan.js` | `cancelPendingStart` | `if (!model.pending \|\| model.pending.done \|\| model.cancelingStart)` | `if (!(!model.pending \|\| model.pending.done \|\| model.cancelingStart))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M037 | 戊 | `ui-plan.js` | `cancelPendingStart` | `if (!model.pending \|\| model.pending.done \|\| model.cancelingStart) return false;` | `if (!model.pending \|\| model.pending.done \|\| model.cancelingStart) return true;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M038 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.canceling = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M039 | 甲 | `ui-plan.js` | `cancelPendingStart` | `model.cancelingStart = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M040 | 丁 | `ui-plan.js` | `cancelPendingStart` | `action:"cancel_start_request",` | `action:undefined,` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M041 | 丁 | `ui-plan.js` | `cancelPendingStart` | `args:{request_id:pending.request_id}` | `args:undefined` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M042 | 丁 | `ui-plan.js` | `cancelPendingStart` | `request_id:pending.request_id` | `request_id:undefined` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M043 | 乙 | `ui-plan.js` | `cancelPendingStart` | `if (body && body.ok && body.state === "canceled")` | `if (!(body && body.ok && body.state === "canceled"))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M044 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.done = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M045 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.outcome = "canceled";` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M046 | 戊 | `ui-plan.js` | `cancelPendingStart` | `\|\| "取消结果尚未确认，请刷新核对")); ↵       return false;` | `\|\| "取消结果尚未确认，请刷新核对")); ↵       return true;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M047 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.canceling = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M048 | 甲 | `ui-plan.js` | `cancelPendingStart` | `model.cancelingStart = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M049 | 乙 | `ui-plan.js` | `cancelPendingStart` | `if (model.paired)` | `if (!(model.paired))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M050 | 戊 | `ui-plan.js` | `cancelPendingStart` | `  return true; ↵ }` | `  return false; ↵ }` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M051 | 乙 | `ui-plan.js` | `stopPlan` | `if (!planId)` | `if (!(!planId))` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M052 | 戊 | `ui-plan.js` | `stopPlan` | `if (!planId) return false;` | `if (!planId) return true;` | 行为守 | `SheetsOpsDomTests.test_stop_plan_payload_and_missing_plan_keeps_confirm_open` |
| M053 | 丁 | `ui-plan.js` | `stopPlan` | `action: "stop_plan",` | `action: undefined,` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M054 | 丁 | `ui-plan.js` | `stopPlan` | `args: { plan_id: planId }` | `args: undefined` | 行为守 | `SheetsOpsDomTests.test_stop_plan_payload_and_missing_plan_keeps_confirm_open` |
| M055 | 丁 | `ui-plan.js` | `stopPlan` | `plan_id: planId` | `plan_id: undefined` | 行为守 | `SheetsOpsDomTests.test_stop_plan_payload_and_missing_plan_keeps_confirm_open` |
| M056 | 乙 | `ui-plan.js` | `stopPlan` | `if (body && body.error)` | `if (!(body && body.error))` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M057 | 戊 | `ui-plan.js` | `stopPlan` | `showSheetError("没能停止计划：" + String(body.text \|\| body.error)); ↵     return false;` | `showSheetError("没能停止计划：" + String(body.text \|\| body.error)); ↵     return true;` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M058 | 戊 | `ui-plan.js` | `stopPlan` | `  return true; ↵ }` | `  return false; ↵ }` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M059 | 丁 | `ui-plan.js` | `showComputerWindow` | `action: "show_window",` | `action: undefined,` | 行为守 | `SheetsOpsDomTests.test_show_computer_window_payload_and_logs` |
| M060 | 丁 | `ui-plan.js` | `showComputerWindow` | `args: {}` | `args: undefined` | 行为守 | `SheetsOpsDomTests.test_show_computer_window_payload_and_logs` |
| M061 | 乙 | `ui-plan.js` | `showComputerWindow` | `if (status !== 200 \|\| (body && body.ok === false))` | `if (!(status !== 200 \|\| (body && body.ok === false)))` | 行为守 | `SheetsOpsDomTests.test_show_computer_window_payload_and_logs` |
| M062 | 乙 | `ui-plan.js` | `cancelTask` | `if (!planId \|\| !task)` | `if (!(!planId \|\| !task))` | 行为守 | `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` |
| M063 | 戊 | `ui-plan.js` | `cancelTask` | `if (!planId \|\| !task) return false;` | `if (!planId \|\| !task) return true;` | 行为守 | `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` |
| M064 | 丁 | `ui-plan.js` | `cancelTask` | `action: "cancel_task",` | `action: undefined,` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M065 | 丁 | `ui-plan.js` | `cancelTask` | `args: { plan_id: planId, task_id: task.task_id }` | `args: undefined` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M066 | 丁 | `ui-plan.js` | `cancelTask` | `plan_id: planId,` | `plan_id: undefined,` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M067 | 丁 | `ui-plan.js` | `cancelTask` | `task_id: task.task_id` | `task_id: undefined` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M068 | 乙 | `ui-plan.js` | `cancelTask` | `if (body && body.error)` | `if (!(body && body.error))` | 行为守 | `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` |
| M069 | 戊 | `ui-plan.js` | `cancelTask` | `showSheetError("没能取消这一场：" + String(body.text \|\| body.error)); ↵     return false;` | `showSheetError("没能取消这一场：" + String(body.text \|\| body.error)); ↵     return true;` | 行为守 | `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` |
| M070 | 戊 | `ui-plan.js` | `cancelTask` | `  return true; ↵ }` | `  return false; ↵ }` | 行为守 | `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` |
| M071 | 甲 | `ui-plan.js` | `reselectFailed` | `model.dismissedPlanId = String((model.plan && model.plan.plan_id) \|\| "");` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M072 | 甲 | `ui-plan.js` | `reselectFailed` | `model.plan = null;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M073 | 乙 | `ui-plan.js` | `reselectFailed` | `if (st !== "failed" && st !== "canceled")` | `if (!(st !== "failed" && st !== "canceled"))` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M074 | 乙 | `ui-plan.js` | `reselectFailed` | `if (item && PhoneModel.actionable(item, model.items, PhoneModel.businessNowS(model)))` | `if (!(item && PhoneModel.actionable(item, model.items, PhoneModel.businessNowS(model))))` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M075 | 甲 | `ui-plan.js` | `reselectFailed` | `model.selected = picked;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M076 | 甲 | `ui-plan.js` | `reselectFailed` | `model.listOpen = false;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M077 | 甲 | `ui-plan.js` | `reselectFailed` | `model.notice = "";` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M078 | 乙 | `ui-plan.js` | `reselectFailed` | `if (skipped > 0)` | `if (!(skipped > 0))` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M079 | 甲 | `ui-plan.js` | `finishPlanView` | `model.dismissedPlanId = String((model.plan && model.plan.plan_id) \|\| "");` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M080 | 甲 | `ui-plan.js` | `finishPlanView` | `model.plan = null;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_finish_and_reselect_clear_task_cards_immediately` |
| M081 | 甲 | `ui-plan.js` | `finishPlanView` | `model.selected = [];` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| M082 | 甲 | `ui-plan.js` | `finishPlanView` | `model.listOpen = false;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M083 | 甲 | `ui-plan.js` | `finishPlanView` | `model.notice = "";` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M084 | 丁 | `ui-plan.js` | `saveRetry` | `action: "save_retry_policy",` | `action: undefined,` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M085 | 丁 | `ui-plan.js` | `saveRetry` | `args: { ↵     retry_policy: { ↵       retry_for_s: Number(model.retry.retry_for_s), ↵       max_attempts: Number(model.retry.max_attempts \|\| 0) } }` | `args: undefined` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M086 | 丁 | `ui-plan.js` | `saveRetry` | `retry_policy: { ↵       retry_for_s: Number(model.retry.retry_for_s), ↵       max_attempts: Number(model.retry.max_attempts \|\| 0) }` | `retry_policy: undefined` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M087 | 丁 | `ui-plan.js` | `saveRetry` | `retry_for_s: Number(model.retry.retry_for_s),` | `retry_for_s: undefined,` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M088 | 丁 | `ui-plan.js` | `saveRetry` | `max_attempts: Number(model.retry.max_attempts \|\| 0)` | `max_attempts: undefined` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M089 | 乙 | `ui-plan.js` | `saveRetry` | `if (body && body.error)` | `if (!(body && body.error))` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M090 | 甲 | `ui-plan.js` | `saveRetry` | `model.retryDirty = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M091 | 乙 | `ui-plan.js` | `renderReview` | `if (tk.act)` | `if (!(tk.act))` | 行为守 | `SheetsOpsDomTests.test_review_render_act_line_warns_visibility_and_remove_clears_notice` |
| M092 | 丙 | `ui-plan.js` | `renderReview` | `$("review-warns").hidden = !warns.length;` | `void 0;` | 行为守 | `SheetsOpsDomTests.test_review_render_act_line_warns_visibility_and_remove_clears_notice` |
| M093 | 乙 | `ui-plan.js` | `renderReview` | `warns.length ?` | `!(warns.length) ?` | 行为守 | `WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` |
| M094 | 甲 | `ui-plan.js` | `removeFromReview` | `model.selected = res.selected;` | `void 0;` | 行为守 | `SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty` |
| M095 | 甲 | `ui-plan.js` | `removeFromReview` | `model.notice = "";` | `void 0;` | 行为守 | `SheetsOpsDomTests.test_review_render_act_line_warns_visibility_and_remove_clears_notice` |
| M096 | 乙 | `ui-plan.js` | `removeFromReview` | `if (!model.selected.length)` | `if (!(!model.selected.length))` | 行为守 | `SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty` |
| M097 | 乙 | `ui-plan.js` | `openReview` | `if ($("btn-start").disabled)` | `if (!($("btn-start").disabled))` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |

## 各类合计

- 行为守：96
- 字面守：0
- 无人守：0
- 无效：0
- 等价：1
- 总计：97

## 按变异口径统计

| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| 甲类（模型及 `pending` 字段写换 `void 0`） | 27 | 0 | 0 | 0 | 1 | 28 |
| 乙类（条件 `C` 换 `!(C)`） | 31 | 0 | 0 | 0 | 0 | 31 |
| 丙类（`.hidden = X` 写换 `void 0`） | 1 | 0 | 0 | 0 | 0 | 1 |
| 丁类（`postAction` 载荷属性换 `undefined`） | 28 | 0 | 0 | 0 | 0 | 28 |
| 戊类（`return true`/`false` 互换） | 9 | 0 | 0 | 0 | 0 | 9 |

## 按函数统计

| 函数 | 口径（甲 / 乙 / 丙 / 丁 / 戊） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---|---:|---:|---:|---:|---:|---:|
| `startPlan` | 5 / 7 / 0 / 8 / 0 | 19 | 0 | 0 | 0 | 1 | 20 |
| `reconcile` | 4 / 8 / 0 / 3 / 0 | 15 | 0 | 0 | 0 | 0 | 15 |
| `cancelPendingStart` | 6 / 3 / 0 / 3 / 3 | 15 | 0 | 0 | 0 | 0 | 15 |
| `stopPlan` | 0 / 2 / 0 / 3 / 3 | 8 | 0 | 0 | 0 | 0 | 8 |
| `showComputerWindow` | 0 / 1 / 0 / 2 / 0 | 3 | 0 | 0 | 0 | 0 | 3 |
| `cancelTask` | 0 / 2 / 0 / 4 / 3 | 9 | 0 | 0 | 0 | 0 | 9 |
| `reselectFailed` | 5 / 3 / 0 / 0 / 0 | 8 | 0 | 0 | 0 | 0 | 8 |
| `finishPlanView` | 5 / 0 / 0 / 0 / 0 | 5 | 0 | 0 | 0 | 0 | 5 |
| `saveRetry` | 1 / 1 / 0 / 5 / 0 | 7 | 0 | 0 | 0 | 0 | 7 |
| `fillRetryOptions` | 0 / 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `renderReview` | 0 / 2 / 1 / 0 / 0 | 3 | 0 | 0 | 0 | 0 | 3 |
| `removeFromReview` | 2 / 1 / 0 / 0 / 0 | 3 | 0 | 0 | 0 | 0 | 3 |
| `openReview` | 0 / 1 / 0 / 0 / 0 | 1 | 0 | 0 | 0 | 0 | 1 |

## 等价判定理由与调用方证明

- **M019**（`ui-plan.js:startPlan`）：startPlan 第 21 行新建的 model.pending.outcome 初值为 undefined，第 33 行仅在同步受理且无 pending 标记的分支将其设为 "accepted"；该值只在同作用域存活，全目录 12 份脚本仅有 model.js:250-251（PhoneModel.startPending）读取 pending.outcome，且只判断 === "canceled" || === "rejected"，"accepted" 与 undefined 在所有正常分支返回值完全相同。 调用方证明：全局扫描 local/ui/m/*.js 所有 pending.outcome 与 .outcome 引用：(1) model.js:250-251（PhoneModel.startPending）为唯一读取方，仅检查 pending.outcome === "canceled" || pending.outcome === "rejected"；(2) ui-plan.js:33（写入 "accepted"）、ui-plan.js:52（reconcile 写入 body.state）、ui-plan.js:80（cancelPendingStart 写入 "canceled"）；(3) model-conflict.js:238 为任务卡字段 t.outcome_label，非 pending.outcome；(4) 其余 9 份脚本（index/ui-status/ui-list/ui-sync/ui-session/ui-relogin/ui-shell/model-list/model-run/model-relogin）零读取，DOM、定时器和 postAction 请求均不读取 pending.outcome。
