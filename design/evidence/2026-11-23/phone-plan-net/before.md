# 第三组（计划操作）变异结论（补测之前）

- 范围：`local/ui/m/ui-plan.js` 的 13 个顶层函数（`fillRetryOptions` 不含五类节点，其余 12 个函数共 97 条）：甲类（模型及 `pending` 字段写换 `void 0`）28 条、乙类（条件 `C` 换 `!(C)`）31 条、丙类（`.hidden = X` 写换 `void 0`）1 条、丁类（`postAction` 载荷属性换 `undefined`）28 条、戊类（`return true`/`false` 互换）9 条。

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|---|
| M001 | 乙 | `ui-plan.js` | `startPlan` | `if (!canWrite())` | `if (!(!canWrite()))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M002 | 乙 | `ui-plan.js` | `startPlan` | `if (!items.length)` | `if (!(!items.length))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M003 | 乙 | `ui-plan.js` | `startPlan` | `if (model.pending && PhoneModel.startPending(model.pending, Date.now()))` | `if (!(model.pending && PhoneModel.startPending(model.pending, Date.now())))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M004 | 乙 | `ui-plan.js` | `startPlan` | `if (model.pending && !model.pending.done)` | `if (!(model.pending && !model.pending.done))` | 行为守 | `MobileWriteResilienceTests.test_accepted_pending_keeps_the_double_click_window` |
| M005 | 甲 | `ui-plan.js` | `startPlan` | `model.pending = { request_id: requestId, at: Date.now(), done: false };` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M006 | 甲 | `ui-plan.js` | `startPlan` | `model.notice = "";` | `void 0;` | 无人守 | — |
| M007 | 甲 | `ui-plan.js` | `startPlan` | `model.listOpen = false;` | `void 0;` | 无人守 | — |
| M008 | 丁 | `ui-plan.js` | `startPlan` | `action: "start_plan",` | `action: undefined,` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M009 | 丁 | `ui-plan.js` | `startPlan` | `args: { ↵     items, headed: false, ↵     retry_policy: { retry_for_s: Number(model.retry.retry_for_s), ↵                     max_attempts: Number(model.retry.max_attempts \|\| 0) }, ↵     request_id: requestId }` | `args: undefined` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M010 | 丁 | `ui-plan.js` | `startPlan` | `items, headed: false,` | `items: undefined, headed: false,` | 无人守 | — |
| M011 | 丁 | `ui-plan.js` | `startPlan` | `headed: false,` | `headed: undefined,` | 无人守 | — |
| M012 | 丁 | `ui-plan.js` | `startPlan` | `retry_policy: { retry_for_s: Number(model.retry.retry_for_s), ↵                     max_attempts: Number(model.retry.max_attempts \|\| 0) },` | `retry_policy: undefined,` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M013 | 丁 | `ui-plan.js` | `startPlan` | `retry_for_s: Number(model.retry.retry_for_s),` | `retry_for_s: undefined,` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M014 | 丁 | `ui-plan.js` | `startPlan` | `max_attempts: Number(model.retry.max_attempts \|\| 0)` | `max_attempts: undefined` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M015 | 丁 | `ui-plan.js` | `startPlan` | `request_id: requestId } });` | `request_id: undefined } });` | 行为守 | `MobileWriteResilienceTests.test_terminal_pending_releases_start_immediately` |
| M016 | 乙 | `ui-plan.js` | `startPlan` | `if (status === 401)` | `if (!(status === 401))` | 行为守 | `MobileWriteResilienceTests.test_action_401_returns_to_pairing_without_continuing_poll` |
| M017 | 乙 | `ui-plan.js` | `startPlan` | `if (body && body.ok && !body.pending)` | `if (!(body && body.ok && !body.pending))` | 行为守 | `MobileWriteResilienceTests.test_write_action_network_failure_is_visible_not_swallowed` |
| M018 | 甲 | `ui-plan.js` | `startPlan` | `model.pending.done = true;` | `void 0;` | 无人守 | — |
| M019 | 甲 | `ui-plan.js` | `startPlan` | `model.pending.outcome = "accepted";` | `void 0;` | 无人守 | — |
| M020 | 乙 | `ui-plan.js` | `startPlan` | `else if (body && body.error)` | `else if (!(body && body.error))` | 行为守 | `MobileWriteResilienceTests.test_write_action_network_failure_is_visible_not_swallowed` |
| M021 | 乙 | `ui-plan.js` | `reconcile` | `if (model.reconciling)` | `if (!(model.reconciling))` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M022 | 乙 | `ui-plan.js` | `reconcile` | `if (!requestId)` | `if (!(!requestId))` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M023 | 甲 | `ui-plan.js` | `reconcile` | `model.reconciling = true;` | `void 0;` | 无人守 | — |
| M024 | 丁 | `ui-plan.js` | `reconcile` | `action: "start_request_state",` | `action: undefined,` | 行为守 | `PhoneDomBehaviourTests.test_reconcile_late_reply_cannot_overwrite_canceled_pending` |
| M025 | 丁 | `ui-plan.js` | `reconcile` | `args: { request_id: requestId }` | `args: undefined` | 无人守 | — |
| M026 | 丁 | `ui-plan.js` | `reconcile` | `request_id: requestId` | `request_id: undefined` | 无人守 | — |
| M027 | 乙 | `ui-plan.js` | `reconcile` | `if (model.pending !== pending \|\| pending.request_id !== requestId \|\| pending.done \|\| pending.canceling)` | `if (!(model.pending !== pending \|\| pending.request_id !== requestId \|\| pending.done \|\| pending.canceling))` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M028 | 乙 | `ui-plan.js` | `reconcile` | `if (body && (body.state === "accepted" \|\| body.state === "rejected" ↵                \|\| body.state === "canceled"))` | `if (!(body && (body.state === "accepted" \|\| body.state === "rejected" ↵                \|\| body.state === "canceled")))` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M029 | 甲 | `ui-plan.js` | `reconcile` | `pending.done = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M030 | 甲 | `ui-plan.js` | `reconcile` | `pending.outcome = body.state;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M031 | 乙 | `ui-plan.js` | `reconcile` | `if (body.state === "accepted")` | `if (!(body.state === "accepted"))` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M032 | 乙 | `ui-plan.js` | `reconcile` | `body.state === "canceled" ↵       ?` | `!(body.state === "canceled") ↵       ?` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M033 | 乙 | `ui-plan.js` | `reconcile` | `body.state === "canceled" ? "info"` | `!(body.state === "canceled") ? "info"` | 无人守 | — |
| M034 | 乙 | `ui-plan.js` | `reconcile` | `if (body && body.state === "unknown")` | `if (!(body && body.state === "unknown"))` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M035 | 甲 | `ui-plan.js` | `reconcile` | `model.reconciling = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |
| M036 | 乙 | `ui-plan.js` | `cancelPendingStart` | `if (!model.pending \|\| model.pending.done \|\| model.cancelingStart)` | `if (!(!model.pending \|\| model.pending.done \|\| model.cancelingStart))` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M037 | 戊 | `ui-plan.js` | `cancelPendingStart` | `if (!model.pending \|\| model.pending.done \|\| model.cancelingStart) return false;` | `if (!model.pending \|\| model.pending.done \|\| model.cancelingStart) return true;` | 无人守 | — |
| M038 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.canceling = true;` | `void 0;` | 无人守 | — |
| M039 | 甲 | `ui-plan.js` | `cancelPendingStart` | `model.cancelingStart = true;` | `void 0;` | 无人守 | — |
| M040 | 丁 | `ui-plan.js` | `cancelPendingStart` | `action:"cancel_start_request",` | `action:undefined,` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M041 | 丁 | `ui-plan.js` | `cancelPendingStart` | `args:{request_id:pending.request_id}` | `args:undefined` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M042 | 丁 | `ui-plan.js` | `cancelPendingStart` | `request_id:pending.request_id` | `request_id:undefined` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M043 | 乙 | `ui-plan.js` | `cancelPendingStart` | `if (body && body.ok && body.state === "canceled")` | `if (!(body && body.ok && body.state === "canceled"))` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M044 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.done = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M045 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.outcome = "canceled";` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_unknown_start_can_be_explicitly_canceled_before_restarting` |
| M046 | 戊 | `ui-plan.js` | `cancelPendingStart` | `\|\| "取消结果尚未确认，请刷新核对")); ↵       return false;` | `\|\| "取消结果尚未确认，请刷新核对")); ↵       return true;` | 无人守 | — |
| M047 | 甲 | `ui-plan.js` | `cancelPendingStart` | `pending.canceling = false;` | `void 0;` | 无人守 | — |
| M048 | 甲 | `ui-plan.js` | `cancelPendingStart` | `model.cancelingStart = false;` | `void 0;` | 无人守 | — |
| M049 | 乙 | `ui-plan.js` | `cancelPendingStart` | `if (model.paired)` | `if (!(model.paired))` | 无人守 | — |
| M050 | 戊 | `ui-plan.js` | `cancelPendingStart` | `  return true; ↵ }` | `  return false; ↵ }` | 无人守 | — |
| M051 | 乙 | `ui-plan.js` | `stopPlan` | `if (!planId)` | `if (!(!planId))` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M052 | 戊 | `ui-plan.js` | `stopPlan` | `if (!planId) return false;` | `if (!planId) return true;` | 无人守 | — |
| M053 | 丁 | `ui-plan.js` | `stopPlan` | `action: "stop_plan",` | `action: undefined,` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M054 | 丁 | `ui-plan.js` | `stopPlan` | `args: { plan_id: planId }` | `args: undefined` | 无人守 | — |
| M055 | 丁 | `ui-plan.js` | `stopPlan` | `plan_id: planId` | `plan_id: undefined` | 无人守 | — |
| M056 | 乙 | `ui-plan.js` | `stopPlan` | `if (body && body.error)` | `if (!(body && body.error))` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M057 | 戊 | `ui-plan.js` | `stopPlan` | `showSheetError("没能停止计划：" + String(body.text \|\| body.error)); ↵     return false;` | `showSheetError("没能停止计划：" + String(body.text \|\| body.error)); ↵     return true;` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M058 | 戊 | `ui-plan.js` | `stopPlan` | `  return true; ↵ }` | `  return false; ↵ }` | 行为守 | `SheetsOpsDomTests.test_confirm_action_failure_keeps_the_sheet_with_red_bar` |
| M059 | 丁 | `ui-plan.js` | `showComputerWindow` | `action: "show_window",` | `action: undefined,` | 无人守 | — |
| M060 | 丁 | `ui-plan.js` | `showComputerWindow` | `args: {}` | `args: undefined` | 无人守 | — |
| M061 | 乙 | `ui-plan.js` | `showComputerWindow` | `if (status !== 200 \|\| (body && body.ok === false))` | `if (!(status !== 200 \|\| (body && body.ok === false)))` | 无人守 | — |
| M062 | 乙 | `ui-plan.js` | `cancelTask` | `if (!planId \|\| !task)` | `if (!(!planId \|\| !task))` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M063 | 戊 | `ui-plan.js` | `cancelTask` | `if (!planId \|\| !task) return false;` | `if (!planId \|\| !task) return true;` | 无人守 | — |
| M064 | 丁 | `ui-plan.js` | `cancelTask` | `action: "cancel_task",` | `action: undefined,` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M065 | 丁 | `ui-plan.js` | `cancelTask` | `args: { plan_id: planId, task_id: task.task_id }` | `args: undefined` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M066 | 丁 | `ui-plan.js` | `cancelTask` | `plan_id: planId,` | `plan_id: undefined,` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M067 | 丁 | `ui-plan.js` | `cancelTask` | `task_id: task.task_id` | `task_id: undefined` | 行为守 | `SheetsOpsDomTests.test_cancel_task_posts_the_tapped_card_task_id` |
| M068 | 乙 | `ui-plan.js` | `cancelTask` | `if (body && body.error)` | `if (!(body && body.error))` | 无人守 | — |
| M069 | 戊 | `ui-plan.js` | `cancelTask` | `showSheetError("没能取消这一场：" + String(body.text \|\| body.error)); ↵     return false;` | `showSheetError("没能取消这一场：" + String(body.text \|\| body.error)); ↵     return true;` | 无人守 | — |
| M070 | 戊 | `ui-plan.js` | `cancelTask` | `  return true; ↵ }` | `  return false; ↵ }` | 无人守 | — |
| M071 | 甲 | `ui-plan.js` | `reselectFailed` | `model.dismissedPlanId = String((model.plan && model.plan.plan_id) \|\| "");` | `void 0;` | 无人守 | — |
| M072 | 甲 | `ui-plan.js` | `reselectFailed` | `model.plan = null;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M073 | 乙 | `ui-plan.js` | `reselectFailed` | `if (st !== "failed" && st !== "canceled")` | `if (!(st !== "failed" && st !== "canceled"))` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M074 | 乙 | `ui-plan.js` | `reselectFailed` | `if (item && PhoneModel.actionable(item, model.items, PhoneModel.businessNowS(model)))` | `if (!(item && PhoneModel.actionable(item, model.items, PhoneModel.businessNowS(model))))` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M075 | 甲 | `ui-plan.js` | `reselectFailed` | `model.selected = picked;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M076 | 甲 | `ui-plan.js` | `reselectFailed` | `model.listOpen = false;` | `void 0;` | 无人守 | — |
| M077 | 甲 | `ui-plan.js` | `reselectFailed` | `model.notice = "";` | `void 0;` | 无人守 | — |
| M078 | 乙 | `ui-plan.js` | `reselectFailed` | `if (skipped > 0)` | `if (!(skipped > 0))` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M079 | 甲 | `ui-plan.js` | `finishPlanView` | `model.dismissedPlanId = String((model.plan && model.plan.plan_id) \|\| "");` | `void 0;` | 无人守 | — |
| M080 | 甲 | `ui-plan.js` | `finishPlanView` | `model.plan = null;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_finish_and_reselect_clear_task_cards_immediately` |
| M081 | 甲 | `ui-plan.js` | `finishPlanView` | `model.selected = [];` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| M082 | 甲 | `ui-plan.js` | `finishPlanView` | `model.listOpen = false;` | `void 0;` | 无人守 | — |
| M083 | 甲 | `ui-plan.js` | `finishPlanView` | `model.notice = "";` | `void 0;` | 无人守 | — |
| M084 | 丁 | `ui-plan.js` | `saveRetry` | `action: "save_retry_policy",` | `action: undefined,` | 无人守 | — |
| M085 | 丁 | `ui-plan.js` | `saveRetry` | `args: { ↵     retry_policy: { ↵       retry_for_s: Number(model.retry.retry_for_s), ↵       max_attempts: Number(model.retry.max_attempts \|\| 0) } }` | `args: undefined` | 无人守 | — |
| M086 | 丁 | `ui-plan.js` | `saveRetry` | `retry_policy: { ↵       retry_for_s: Number(model.retry.retry_for_s), ↵       max_attempts: Number(model.retry.max_attempts \|\| 0) }` | `retry_policy: undefined` | 无人守 | — |
| M087 | 丁 | `ui-plan.js` | `saveRetry` | `retry_for_s: Number(model.retry.retry_for_s),` | `retry_for_s: undefined,` | 无人守 | — |
| M088 | 丁 | `ui-plan.js` | `saveRetry` | `max_attempts: Number(model.retry.max_attempts \|\| 0)` | `max_attempts: undefined` | 无人守 | — |
| M089 | 乙 | `ui-plan.js` | `saveRetry` | `if (body && body.error)` | `if (!(body && body.error))` | 无人守 | — |
| M090 | 甲 | `ui-plan.js` | `saveRetry` | `model.retryDirty = false;` | `void 0;` | 无人守 | — |
| M091 | 乙 | `ui-plan.js` | `renderReview` | `if (tk.act)` | `if (!(tk.act))` | 无人守 | — |
| M092 | 丙 | `ui-plan.js` | `renderReview` | `$("review-warns").hidden = !warns.length;` | `void 0;` | 无人守 | — |
| M093 | 乙 | `ui-plan.js` | `renderReview` | `warns.length ?` | `!(warns.length) ?` | 行为守 | `WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` |
| M094 | 甲 | `ui-plan.js` | `removeFromReview` | `model.selected = res.selected;` | `void 0;` | 行为守 | `SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty` |
| M095 | 甲 | `ui-plan.js` | `removeFromReview` | `model.notice = "";` | `void 0;` | 无人守 | — |
| M096 | 乙 | `ui-plan.js` | `removeFromReview` | `if (!model.selected.length)` | `if (!(!model.selected.length))` | 行为守 | `SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty` |
| M097 | 乙 | `ui-plan.js` | `openReview` | `if ($("btn-start").disabled)` | `if (!($("btn-start").disabled))` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |

## 各类合计

- 行为守：53
- 字面守：0
- 无人守：44
- 无效：0
- 等价：0
- 总计：97

## 按变异口径统计

| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| 甲类（模型及 `pending` 字段写换 `void 0`） | 11 | 0 | 17 | 0 | 0 | 28 |
| 乙类（条件 `C` 换 `!(C)`） | 25 | 0 | 6 | 0 | 0 | 31 |
| 丙类（`.hidden = X` 写换 `void 0`） | 0 | 0 | 1 | 0 | 0 | 1 |
| 丁类（`postAction` 载荷属性换 `undefined`） | 15 | 0 | 13 | 0 | 0 | 28 |
| 戊类（`return true`/`false` 互换） | 2 | 0 | 7 | 0 | 0 | 9 |

## 按函数统计

| 函数 | 口径（甲 / 乙 / 丙 / 丁 / 戊） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---|---:|---:|---:|---:|---:|---:|
| `startPlan` | 5 / 7 / 0 / 8 / 0 | 14 | 0 | 6 | 0 | 0 | 20 |
| `reconcile` | 4 / 8 / 0 / 3 / 0 | 11 | 0 | 4 | 0 | 0 | 15 |
| `cancelPendingStart` | 6 / 3 / 0 / 3 / 3 | 7 | 0 | 8 | 0 | 0 | 15 |
| `stopPlan` | 0 / 2 / 0 / 3 / 3 | 5 | 0 | 3 | 0 | 0 | 8 |
| `showComputerWindow` | 0 / 1 / 0 / 2 / 0 | 0 | 0 | 3 | 0 | 0 | 3 |
| `cancelTask` | 0 / 2 / 0 / 4 / 3 | 5 | 0 | 4 | 0 | 0 | 9 |
| `reselectFailed` | 5 / 3 / 0 / 0 / 0 | 5 | 0 | 3 | 0 | 0 | 8 |
| `finishPlanView` | 5 / 0 / 0 / 0 / 0 | 2 | 0 | 3 | 0 | 0 | 5 |
| `saveRetry` | 1 / 1 / 0 / 5 / 0 | 0 | 0 | 7 | 0 | 0 | 7 |
| `fillRetryOptions` | 0 / 0 / 0 / 0 / 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `renderReview` | 0 / 2 / 1 / 0 / 0 | 1 | 0 | 2 | 0 | 0 | 3 |
| `removeFromReview` | 2 / 1 / 0 / 0 / 0 | 2 | 0 | 1 | 0 | 0 | 3 |
| `openReview` | 0 / 1 / 0 / 0 / 0 | 1 | 0 | 0 | 0 | 0 | 1 |
