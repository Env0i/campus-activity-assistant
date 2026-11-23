# 第二组（摄入与渲染）变异结论（补测之后）

- 范围：23 个函数（`ui-status.js` 13 个、`ui-list.js` 5 个、`ui-sync.js` 5 个），甲类（`model.字段` 写换 `void 0`）40 条、乙类（条件 `C` 换 `!(C)`）141 条、丙类（`.hidden = X` 写换 `void 0`）45 条，共 226 条。

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|---|
| M001 | 甲 | `ui-status.js` | `setBanner` | `model.bannerKind = text ? String(kind \|\| "info") : "";` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_reconcile_late_reply_cannot_overwrite_canceled_pending` |
| M002 | 乙 | `ui-status.js` | `setBanner` | `text ?` | `!(text) ?` | 行为守 | `PhoneDomBehaviourTests.test_reconcile_late_reply_cannot_overwrite_canceled_pending` |
| M003 | 丙 | `ui-status.js` | `setBanner` | `el.hidden = !text;` | `void 0;` | 行为守 | `PhoneSyncPolicyTests.test_successful_sync_clears_only_the_stale_banner` |
| M004 | 乙 | `ui-status.js` | `clearStaleBanner` | `if (model.bannerKind === "stale_action")` | `if (!(model.bannerKind === "stale_action"))` | 行为守 | `PhoneSyncPolicyTests.test_successful_sync_clears_only_the_stale_banner` |
| M005 | 乙 | `ui-status.js` | `syncOffline` | `if (!stale)` | `if (!(!stale))` | 行为守 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` |
| M006 | 丙 | `ui-status.js` | `syncOffline` | `  if (!stale) { ↵     note.hidden = true;` | `  if (!stale) { ↵     void 0;` | 行为守 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` |
| M007 | 甲 | `ui-status.js` | `syncOffline` | `model.offlineTries = 0;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_poll_failure_backs_off_and_stale_disables_start` |
| M008 | 乙 | `ui-status.js` | `syncOffline` | `if (PhoneModel.connState(model, false).state !== "off")` | `if (!(PhoneModel.connState(model, false).state !== "off"))` | 行为守 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` |
| M009 | 丙 | `ui-status.js` | `syncOffline` | `  if (PhoneModel.connState(model, false).state !== "off") { ↵     note.hidden = true;` | `  if (PhoneModel.connState(model, false).state !== "off") { ↵     void 0;` | 行为守 | `ExceptionStatesTests.test_silent_stale_hides_red_bar_but_retrying_shows_it` |
| M010 | 乙 | `ui-status.js` | `syncOffline` | `tries > 0 ?` | `!(tries > 0) ?` | 行为守 | `ExceptionStatesTests.test_silent_stale_hides_red_bar_but_retrying_shows_it` |
| M011 | 乙 | `ui-status.js` | `syncOffline` | `model.flying ?` | `!(model.flying) ?` | 行为守 | `ExceptionStatesTests.test_silent_stale_hides_red_bar_but_retrying_shows_it` |
| M012 | 丙 | `ui-status.js` | `syncOffline` | `note.hidden = false;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_silent_stale_hides_red_bar_but_retrying_shows_it` |
| M013 | 丙 | `ui-status.js` | `renderAlerts` | `$("terms-alert").hidden = !(!off && terms);` | `void 0;` | 行为守 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` |
| M014 | 丙 | `ui-status.js` | `renderAlerts` | `$("login-expired-banner").hidden = !(!off && !terms && expired);` | `void 0;` | 行为守 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` |
| M015 | 丙 | `ui-status.js` | `renderAlerts` | `$("pclist-alert").hidden = !(!off && !terms && !expired && pcList);` | `void 0;` | 行为守 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` |
| M016 | 乙 | `ui-status.js` | `renderAlerts` | `if (!$("pclist-alert").hidden)` | `if (!(!$("pclist-alert").hidden))` | 行为守 | `ExceptionStatesTests.test_pc_list_error_alert_hides_bar_until_recovered` |
| M017 | 乙 | `ui-status.js` | `renderAlerts` | `when ↵       ?` | `!(when) ↵       ?` | 行为守 | `ExceptionStatesTests.test_pc_list_error_alert_hides_bar_until_recovered` |
| M018 | 丙 | `ui-status.js` | `renderAlerts` | `$("pcclock-alert").hidden = !(!off && !terms && !expired && !pcList && clockDown);` | `void 0;` | 行为守 | `ExceptionStatesTests.test_alert_priority_chain_follows_prototype` |
| M019 | 丙 | `ui-status.js` | `renderAlerts` | `$("pair-ok-alert").hidden = !(!off && !terms && !expired && !pcList && !clockDown ↵     && model.pairOkPending);` | `void 0;` | 行为守 | `PairStatesDomTests.test_pair_success_shows_dismissable_connected_alert` |
| M020 | 甲 | `ui-status.js` | `canWrite` | `model.nowMs = Date.now();` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_can_write_reads_fresh_clock_after_idle_gap_before_start` |
| M021 | 甲 | `ui-status.js` | `refreshControls` | `model.nowMs = Date.now();` | `void 0;` | 行为守 | `ExceptionStatesTests.test_silent_stale_hides_red_bar_but_retrying_shows_it` |
| M022 | 丙 | `ui-status.js` | `refreshControls` | `$("stale-note").hidden = !stale;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` |
| M023 | 丙 | `ui-status.js` | `refreshControls` | `$("btn-stop").hidden = !model.busy;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` |
| M024 | 乙 | `ui-status.js` | `refreshControls` | `model.reloginSetup ↵         ?` | `!(model.reloginSetup) ↵         ?` | 行为守 | `PhoneReloginRecoveryTests.test_begin_shows_the_computer_took_over` |
| M025 | 乙 | `ui-status.js` | `refreshControls` | `if (account)` | `if (!(account))` | 等价 | — |
| M026 | 丙 | `ui-status.js` | `refreshControls` | `account.hidden = setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true;` | `void 0;` | 等价 | — |
| M027 | 乙 | `ui-status.js` | `refreshControls` | `setup ?` | `!(setup) ?` | 等价 | — |
| M028 | 丙 | `ui-status.js` | `refreshControls` | `$("btn-cancel-start").hidden = !(model.pending && !model.pending.done);` | `void 0;` | 行为守 | `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` |
| M029 | 丙 | `ui-status.js` | `refreshControls` | `$("review-policy").hidden = !hint;` | `void 0;` | 行为守 | `WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` |
| M030 | 乙 | `ui-status.js` | `refreshControls` | `if (model.sheetId)` | `if (!(model.sheetId))` | 行为守 | `SheetShellTests.test_sheet_close_button_hides_only_when_open_sheet_is_busy` |
| M031 | 丙 | `ui-status.js` | `refreshControls` | `$("btn-sheet-close").hidden = sheetBusy();` | `void 0;` | 行为守 | `SheetShellTests.test_sheet_close_button_hides_only_when_open_sheet_is_busy` |
| M032 | 丙 | `ui-status.js` | `renderBar` | `bar.hidden = false;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_alert_hides_bar_until_recovered` |
| M033 | 乙 | `ui-status.js` | `renderBar` | `result ?` | `!(result) ?` | 行为守 | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| M034 | 丙 | `ui-status.js` | `renderBar` | `$("bar-info").hidden = !!result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| M035 | 丙 | `ui-status.js` | `renderBar` | `$("btn-reselect").hidden = !result \|\| !result.canRetry;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M036 | 丙 | `ui-status.js` | `renderBar` | `$("btn-finish").hidden = !result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M037 | 乙 | `ui-status.js` | `renderBar` | `if (result)` | `if (!(result))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M038 | 丙 | `ui-status.js` | `renderBar` | `$("btn-start").hidden = true;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M039 | 丙 | `ui-status.js` | `renderBar` | `$("btn-cancel-start").hidden = true;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M040 | 乙 | `ui-status.js` | `renderBar` | `if (model.busy)` | `if (!(model.busy))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M041 | 乙 | `ui-status.js` | `renderBar` | `model.plan && String(model.plan.source \|\| "") === "phone" ↵       ?` | `!(model.plan && String(model.plan.source \|\| "") === "phone") ↵       ?` | 行为守 | `ExceptionStatesTests.test_stop_stays_tappable_when_offline` |
| M042 | 乙 | `ui-status.js` | `renderBar` | `if (model.pending && !model.pending.done)` | `if (!(model.pending && !model.pending.done))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M043 | 乙 | `ui-status.js` | `renderBar` | `PhoneModel.pendingLong(model.pending, Date.now()) ↵       ?` | `!(PhoneModel.pendingLong(model.pending, Date.now())) ↵       ?` | 行为守 | `RunWaitDomTests.test_pending_bar_title_switches_after_window_and_start_hides_when_busy` |
| M044 | 乙 | `ui-status.js` | `renderBar` | `if (model.pcListError)` | `if (!(model.pcListError))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M045 | 丙 | `ui-status.js` | `renderBar` | `bar.hidden = true;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_alert_hides_bar_until_recovered` |
| M046 | 丙 | `ui-status.js` | `renderBar` | `$("btn-start").hidden = false;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` |
| M047 | 乙 | `ui-status.js` | `renderBar` | `model.termsOk === false ↵       ?` | `!(model.termsOk === false) ↵       ?` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M048 | 乙 | `ui-status.js` | `renderBar` | `recoveringSub ?` | `!(recoveringSub) ?` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M049 | 乙 | `ui-status.js` | `renderBar` | `expiredSub ?` | `!(expiredSub) ?` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M050 | 乙 | `ui-status.js` | `renderBar` | `model.clockState === "unavailable"                   // EX06（Phone:865） ↵                     ?` | `!(model.clockState === "unavailable")                   // EX06（Phone:865） ↵                     ?` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M051 | 乙 | `ui-status.js` | `renderBar` | `PhoneModel.connState(model, model.flying).state === "off"  // UI-F3：离线不冒充「已选 N 场，可开始」 ↵                        ?` | `!(PhoneModel.connState(model, model.flying).state === "off")  // UI-F3：离线不冒充「已选 N 场，可开始」 ↵                        ?` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M052 | 乙 | `ui-status.js` | `renderBar` | `expired && !model.busy ↵     && !(model.pending && !model.pending.done) ?` | `!(expired && !model.busy ↵     && !(model.pending && !model.pending.done)) ?` | 行为守 | `ExceptionStatesTests.test_bar_sub_says_auto_relogin_in_progress_not_relogin` |
| M053 | 丙 | `ui-status.js` | `renderBar` | `$("btn-start").hidden = model.busy;` | `void 0;` | 行为守 | `RunWaitDomTests.test_pending_bar_title_switches_after_window_and_start_hides_when_busy` |
| M054 | 乙 | `ui-status.js` | `renderRail` | `if (!box)` | `if (!(!box))` | 行为守 | `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` |
| M055 | 丙 | `ui-status.js` | `renderRail` | `box.hidden = !steps.length;` | `void 0;` | 行为守 | `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` |
| M056 | 乙 | `ui-status.js` | `renderRail` | `if (step.state)` | `if (!(step.state))` | 行为守 | `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` |
| M057 | 乙 | `ui-status.js` | `renderBoard` | `if (!section)` | `if (!(!section))` | 行为守 | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| M058 | 乙 | `ui-status.js` | `renderBoard` | `if (model.busy)` | `if (!(model.busy))` | 行为守 | `ExceptionStatesTests.test_clock_unavailable_blocks_start_and_shows_pending_calibration` |
| M059 | 乙 | `ui-status.js` | `renderBoard` | `if (pendingNow)` | `if (!(pendingNow))` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M060 | 乙 | `ui-status.js` | `renderBoard` | `    board = PhoneModel.pendingBoard(model.pending, Date.now()); ↵   } else if (result)` | `    board = PhoneModel.pendingBoard(model.pending, Date.now()); ↵   } else if (!(result))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M061 | 乙 | `ui-status.js` | `renderBoard` | `if (model.termsOk === false)` | `if (!(model.termsOk === false))` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M062 | 丙 | `ui-status.js` | `renderBoard` | `section.hidden = !board;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M063 | 乙 | `ui-status.js` | `renderBoard` | `result && result.boardCls ?` | `!(result && result.boardCls) ?` | 行为守 | `ExceptionStatesTests.test_stale_note_and_stop_and_cancel_start_visibility_follow_state` |
| M064 | 乙 | `ui-status.js` | `renderBoard` | `if (!board)` | `if (!(!board))` | 行为守 | `ExceptionStatesTests.test_clock_unavailable_blocks_start_and_shows_pending_calibration` |
| M065 | 乙 | `ui-status.js` | `renderBoard` | `board.tagTone ?` | `!(board.tagTone) ?` | 行为守 | `WorkbenchPhoneTests.test_terms_not_accepted_keeps_the_phone_read_only` |
| M066 | 丙 | `ui-status.js` | `renderBoard` | `nowLine.hidden = false;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M067 | 乙 | `ui-status.js` | `renderBoard` | `nowS !== null ↵     ?` | `!(nowS !== null) ↵     ?` | 行为守 | `ExceptionStatesTests.test_clock_unavailable_blocks_start_and_shows_pending_calibration` |
| M068 | 丙 | `ui-status.js` | `renderBoard` | `$("board-led-wrap").hidden = !!result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| M069 | 丙 | `ui-status.js` | `renderBoard` | `$("board-cap").hidden = !!result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_board_and_stack_bar_follow_prototype` |
| M070 | 丙 | `ui-status.js` | `renderBoard` | `$("board-stats").hidden = !result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M071 | 乙 | `ui-status.js` | `renderBoard` | `  $("board-sub").textContent = board.sub; ↵   if (result)` | `  $("board-sub").textContent = board.sub; ↵   if (!(result))` | 行为守 | `PhoneReloginRecoveryTests.test_snapshot_restores_challenge_without_erasing_typed_code` |
| M072 | 甲 | `ui-status.js` | `renderBoard` | `model.pickId = "";` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_hides_pick_next_and_clears_pick_target` |
| M073 | 丙 | `ui-status.js` | `renderBoard` | `$("btn-pick-next").hidden = true;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_result_hides_pick_next_and_clears_pick_target` |
| M074 | 乙 | `ui-status.js` | `renderBoard` | `if (d.cls)` | `if (!(d.cls))` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M075 | 甲 | `ui-status.js` | `renderBoard` | `model.pickId = board.pickId \|\| "";` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M076 | 丙 | `ui-status.js` | `renderBoard` | `$("btn-pick-next").hidden = !board.pickId;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M077 | 乙 | `ui-status.js` | `renderStats` | `if (n.tone)` | `if (!(n.tone))` | 行为守 | `ResultTermsDomTests.test_result_bar_visibility_stats_tones_and_draft_reset` |
| M078 | 丙 | `ui-status.js` | `renderPlan` | `tip.hidden = !model.busy;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` |
| M079 | 乙 | `ui-status.js` | `renderTasks` | `if (!box)` | `if (!(!box))` | 行为守 | `ResultTermsDomTests.test_finish_and_reselect_clear_task_cards_immediately` |
| M080 | 丙 | `ui-status.js` | `renderTasks` | `box.hidden = !(model.busy \|\| PhoneModel.resultView(model.plan, model.busy)) \|\| !tasks.length;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_finish_and_reselect_clear_task_cards_immediately` |
| M081 | 乙 | `ui-status.js` | `renderTasks` | `if (box.hidden)` | `if (!(box.hidden))` | 行为守 | `ResultTermsDomTests.test_finish_and_reselect_clear_task_cards_immediately` |
| M082 | 乙 | `ui-status.js` | `renderTasks` | `card.tone ?` | `!(card.tone) ?` | 行为守 | `RunWaitDomTests.test_board_rail_visibility_and_step_classes_and_task_card_tone` |
| M083 | 乙 | `ui-status.js` | `renderTasks` | `if (card.canCancel)` | `if (!(card.canCancel))` | 行为守 | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| M084 | 乙 | `ui-list.js` | `buildRow` | `row.cls ?` | `!(row.cls) ?` | 行为守 | `PhoneRowDomTests.test_clash_row_is_disabled_and_tap_toggles_the_reason` |
| M085 | 乙 | `ui-list.js` | `buildRow` | `model.flashId === row.id ?` | `!(model.flashId === row.id) ?` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M086 | 甲 | `ui-list.js` | `buildRow` | `model.selected = res.selected;` | `void 0;` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M087 | 甲 | `ui-list.js` | `buildRow` | `model.notice = res.notice;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` |
| M088 | 乙 | `ui-list.js` | `buildRow` | `if (row.timeCls)` | `if (!(row.timeCls))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M089 | 乙 | `ui-list.js` | `buildRow` | `if (row.hasLeft)` | `if (!(row.hasLeft))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M090 | 乙 | `ui-list.js` | `buildRow` | `if (row.leftCls)` | `if (!(row.leftCls))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M091 | 乙 | `ui-list.js` | `buildRow` | `f.cls ?` | `!(f.cls) ?` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M092 | 乙 | `ui-list.js` | `buildRow` | `  }); ↵   if (row.clash)` | `  }); ↵   if (!(row.clash))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M093 | 乙 | `ui-list.js` | `buildRow` | `if (row.act)` | `if (!(row.act))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M094 | 乙 | `ui-list.js` | `buildRow` | `if (row.hasRf)` | `if (!(row.hasRf))` | 行为守 | `PhoneRowDomTests.test_inline_time_refund_and_note_and_no_buttons_on_signed_rows` |
| M095 | 乙 | `ui-list.js` | `buildRow` | `row.rfNo ?` | `!(row.rfNo) ?` | 行为守 | `PhoneRowDomTests.test_inline_time_refund_and_note_and_no_buttons_on_signed_rows` |
| M096 | 乙 | `ui-list.js` | `buildRow` | `if (row.hasPlace)` | `if (!(row.hasPlace))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M097 | 乙 | `ui-list.js` | `buildRow` | `if (row.rw && row.rw.text)` | `if (!(row.rw && row.rw.text))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M098 | 乙 | `ui-list.js` | `buildRow` | `if (row.hasWarn)` | `if (!(row.hasWarn))` | 行为守 | `PhoneRowDomTests.test_build_row_renders_unknown_time_left_soon_flags_place_reward_and_warn` |
| M099 | 乙 | `ui-list.js` | `buildRow` | `if (row.note)` | `if (!(row.note))` | 行为守 | `PhoneRowDomTests.test_inline_time_refund_and_note_and_no_buttons_on_signed_rows` |
| M100 | 乙 | `ui-list.js` | `buildRow` | `  /* 重叠行：点按这一行展开 / 收起原因，一次只开一条（面板在行内占满整行宽） */ ↵   if (row.clash)` | `  /* 重叠行：点按这一行展开 / 收起原因，一次只开一条（面板在行内占满整行宽） */ ↵   if (!(row.clash))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M101 | 乙 | `ui-list.js` | `buildRow` | `if (event && event.preventDefault)` | `if (!(event && event.preventDefault))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M102 | 乙 | `ui-list.js` | `buildRow` | `if (model.whyId === row.id)` | `if (!(model.whyId === row.id))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M103 | 乙 | `ui-list.js` | `buildWhy` | `if (view.hasGo)` | `if (!(view.hasGo))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M104 | 乙 | `ui-list.js` | `buildWhy` | `if (event && event.stopPropagation)` | `if (!(event && event.stopPropagation))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M105 | 甲 | `ui-list.js` | `goSigned` | `model.whyId = "";` | `void 0;` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M106 | 乙 | `ui-list.js` | `goSigned` | `if (!shown)` | `if (!(!shown))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M107 | 甲 | `ui-list.js` | `goSigned` | `model.filter = { q: "", status: "all", time: "all" };` | `void 0;` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M108 | 乙 | `ui-list.js` | `goSigned` | `if ($("q"))` | `if (!($("q")))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M109 | 乙 | `ui-list.js` | `goSigned` | `if ($("search-q"))` | `if (!($("search-q")))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M110 | 乙 | `ui-list.js` | `goSigned` | `b.dataset.status === "all" ?` | `!(b.dataset.status === "all") ?` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M111 | 乙 | `ui-list.js` | `goSigned` | `b.dataset.time === "all" ?` | `!(b.dataset.time === "all") ?` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M112 | 乙 | `ui-list.js` | `goSigned` | `if ($("signed-summary"))` | `if (!($("signed-summary")))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M113 | 甲 | `ui-list.js` | `goSigned` | `model.flashId = id;` | `void 0;` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M114 | 乙 | `ui-list.js` | `goSigned` | `if (row && row.scrollIntoView)` | `if (!(row && row.scrollIntoView))` | 行为守 | `PhoneRowDomTests.test_clash_row_click_prevents_default_and_go_button_stops_bubbling` |
| M115 | 甲 | `ui-list.js` | `goSigned` | `model.flashId = "";` | `void 0;` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M116 | 乙 | `ui-list.js` | `goSigned` | `if (row && row.classList)` | `if (!(row && row.classList))` | 行为守 | `PhoneRowDomTests.test_go_signed_resets_hidden_filters_scrolls_flashes_and_clears_after_two_seconds` |
| M117 | 甲 | `ui-list.js` | `renderItems` | `model.nowMs = Date.now();` | `void 0;` | 行为守 | `RunWaitDomTests.test_render_items_refreshes_clock_before_offline_board_render` |
| M118 | 乙 | `ui-list.js` | `renderItems` | `if (!box)` | `if (!(!box))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M119 | 乙 | `ui-list.js` | `renderItems` | `if (!inListZone(zone, group.title))` | `if (!(!inListZone(zone, group.title)))` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M120 | 乙 | `ui-list.js` | `renderItems` | `if (group.nowBefore && group.now)` | `if (!(group.nowBefore && group.now))` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M121 | 乙 | `ui-list.js` | `renderItems` | `group.cls ?` | `!(group.cls) ?` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M122 | 乙 | `ui-list.js` | `renderItems` | `if ($("signed-count"))` | `if (!($("signed-count")))` | 行为守 | `ResultTermsDomTests.test_signed_groups_render_in_main_list_and_summary_only_in_result` |
| M123 | 丙 | `ui-list.js` | `renderItems` | `$("fbar").hidden = !showList;` | `void 0;` | 行为守 | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| M124 | 丙 | `ui-list.js` | `renderItems` | `$("search-view").hidden = !showList \|\| !model.searchOpen;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M125 | 丙 | `ui-list.js` | `renderItems` | `toggle.hidden = !(model.busy \|\| result);` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M126 | 乙 | `ui-list.js` | `renderItems` | `  toggle.hidden = !(model.busy \|\| result); ↵   toggle.setAttribute("aria-expanded", model.listOpen ?` | `  toggle.hidden = !(model.busy \|\| result); ↵   toggle.setAttribute("aria-expanded", !(model.listOpen) ?` | 行为守 | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| M127 | 乙 | `ui-list.js` | `renderItems` | `  toggle.setAttribute("aria-expanded", model.listOpen ? "true" : "false"); ↵   toggle.textContent = model.listOpen ?` | `  toggle.setAttribute("aria-expanded", model.listOpen ? "true" : "false"); ↵   toggle.textContent = !(model.listOpen) ?` | 行为守 | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| M128 | 丙 | `ui-list.js` | `renderItems` | `tip.hidden = !showList \|\| !noMatch;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M129 | 丙 | `ui-list.js` | `renderItems` | `$("today-items").hidden = !showList \|\| noMatch;` | `void 0;` | 行为守 | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| M130 | 乙 | `ui-list.js` | `renderItems` | `if ($("upcoming-zone"))` | `if (!($("upcoming-zone")))` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M131 | 丙 | `ui-list.js` | `renderItems` | `$("upcoming-zone").hidden = !showList \|\| noMatch;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_items_group_cls_and_zone_and_toggle_visibility` |
| M132 | 乙 | `ui-list.js` | `renderItems` | `if ($("signed-summary"))` | `if (!($("signed-summary")))` | 行为守 | `ResultTermsDomTests.test_signed_groups_render_in_main_list_and_summary_only_in_result` |
| M133 | 丙 | `ui-list.js` | `renderItems` | `$("signed-summary").hidden = !showList \|\| !result;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_signed_groups_render_in_main_list_and_summary_only_in_result` |
| M134 | 乙 | `ui-list.js` | `renderItems` | `if (result)` | `if (!(result))` | 行为守 | `ResultTermsDomTests.test_signed_summary_items_populate_only_in_result_state` |
| M135 | 丙 | `ui-list.js` | `renderItems` | `$("empty").hidden = !showList \|\| noMatch \|\| nowS === null \|\| zoneCount[0] > 0;` | `void 0;` | 行为守 | `ListDetailModelTests.test_today_chip_shows_real_shape_activity_via_dom` |
| M136 | 乙 | `ui-list.js` | `renderItems` | `if ($("upcoming-empty"))` | `if (!($("upcoming-empty")))` | 行为守 | `ResultTermsDomTests.test_uncalibrated_clock_hides_today_empty_and_calibrated_empty_today_keeps_it` |
| M137 | 丙 | `ui-list.js` | `renderItems` | `$("upcoming-empty").hidden = !showList \|\| noMatch \|\| zoneCount[1] > 0;` | `void 0;` | 行为守 | `ResultTermsDomTests.test_uncalibrated_clock_hides_today_empty_and_calibrated_empty_today_keeps_it` |
| M138 | 丙 | `ui-list.js` | `renderItems` | `notice.hidden = !showList \|\| !model.notice;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` |
| M139 | 甲 | `ui-list.js` | `toggleSearch` | `model.searchOpen = !model.searchOpen;` | `void 0;` | 行为守 | `ListDetailModelTests.test_list_notice_and_search_toggle` |
| M140 | 丙 | `ui-list.js` | `toggleSearch` | `$("search-view").hidden = !model.searchOpen;` | `void 0;` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |
| M141 | 乙 | `ui-list.js` | `toggleSearch` | `model.searchOpen ?` | `!(model.searchOpen) ?` | 行为守 | `ListDetailModelTests.test_list_notice_and_search_toggle` |
| M142 | 甲 | `ui-list.js` | `toggleSearch` | `model.filter.q = "";` | `void 0;` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |
| M143 | 乙 | `ui-list.js` | `toggleSearch` | `if ($("q"))` | `if (!($("q")))` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |
| M144 | 乙 | `ui-list.js` | `toggleSearch` | `if (model.searchOpen && $("search-q").focus)` | `if (!(model.searchOpen && $("search-q").focus))` | 行为守 | `ListDetailModelTests.test_toggle_search_reveals_box_before_focus_and_clears_queries` |
| M145 | 乙 | `ui-sync.js` | `scheduleTick` | `if (model.tickTimer)` | `if (!(model.tickTimer))` | 行为守 | `PhoneSyncPolicyTests.test_poll_success_resets_backoff_and_replaces_old_poll_timer` |
| M146 | 甲 | `ui-sync.js` | `scheduleTick` | `  if (model.tickTimer) clearTimeout(model.tickTimer); ↵   model.tickTimer = null;` | `  if (model.tickTimer) clearTimeout(model.tickTimer); ↵   void 0;` | 等价 | — |
| M147 | 乙 | `ui-sync.js` | `scheduleTick` | `if (typeof document !== "undefined" && document.hidden)` | `if (!(typeof document !== "undefined" && document.hidden))` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M148 | 乙 | `ui-sync.js` | `scheduleTick` | `if (!model.paired)` | `if (!(!model.paired))` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M149 | 甲 | `ui-sync.js` | `scheduleTick` | `model.tickTimer = setTimeout(() => { ↵     model.tickTimer = null; ↵     tickClock(); ↵     scheduleTick(); ↵   }, PhoneModel.nextTickDelay(PhoneModel.businessNowS(model)));` | `void 0;` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M150 | 甲 | `ui-sync.js` | `scheduleTick` | `  model.tickTimer = setTimeout(() => { ↵     model.tickTimer = null;` | `  model.tickTimer = setTimeout(() => { ↵     void 0;` | 等价 | — |
| M151 | 乙 | `ui-sync.js` | `tickClock` | `if (typeof document !== "undefined" && document.hidden)` | `if (!(typeof document !== "undefined" && document.hidden))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M152 | 甲 | `ui-sync.js` | `tickClock` | `model.tickMark = { wall: wallMs, mono: monoMs };` | `void 0;` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M153 | 乙 | `ui-sync.js` | `tickClock` | `if (slept && model.clock)` | `if (!(slept && model.clock))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M154 | 甲 | `ui-sync.js` | `tickClock` | `model.clock = null;` | `void 0;` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M155 | 乙 | `ui-sync.js` | `tickClock` | `if (model.paired)` | `if (!(model.paired))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M156 | 乙 | `ui-sync.js` | `tickClock` | `  const clockText = nowS !== null ↵     ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)) : "待校准"; ↵   const nowEl = $("board-now-text");` | `  const clockText = !(nowS !== null) ↵     ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)) : "待校准"; ↵   const nowEl = $("board-now-text");` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M157 | 乙 | `ui-sync.js` | `tickClock` | `if (nowEl && !$("board-now").hidden && nowEl.textContent !== clockText)` | `if (!(nowEl && !$("board-now").hidden && nowEl.textContent !== clockText))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M158 | 乙 | `ui-sync.js` | `tickClock` | `  const chipText = nowS !== null ↵     ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : ""; ↵   if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {` | `  const chipText = !(nowS !== null) ↵     ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : ""; ↵   if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {` | 行为守 | `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` |
| M159 | 乙 | `ui-sync.js` | `tickClock` | `if (typeof document !== "undefined" && typeof document.querySelectorAll === "function")` | `if (!(typeof document !== "undefined" && typeof document.querySelectorAll === "function"))` | 行为守 | `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` |
| M160 | 乙 | `ui-sync.js` | `tickClock` | `if (chipText && el.textContent !== chipText)` | `if (!(chipText && el.textContent !== chipText))` | 行为守 | `PhoneTickTests.test_second_tick_updates_nowchip_only_when_calibrated` |
| M161 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (!section \|\| section.hidden)` | `if (!(!section \|\| section.hidden))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M162 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (result)` | `if (!(result))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M163 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (model.busy)` | `if (!(model.busy))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M164 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (pendingNow)` | `if (!(pendingNow))` | 行为守 | `PhoneTickTests.test_visible_board_rebuilds_dots_only_when_countdown_changes` |
| M165 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (model.termsOk === false)` | `if (!(model.termsOk === false))` | 行为守 | `PhoneTickTests.test_visible_board_rebuilds_dots_only_when_countdown_changes` |
| M166 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (!board \|\| !board.led)` | `if (!(!board \|\| !board.led))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M167 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (!wrap \|\| wrap.hidden)` | `if (!(!wrap \|\| wrap.hidden))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M168 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (wrap.getAttribute("aria-label") === board.led.aria)` | `if (!(wrap.getAttribute("aria-label") === board.led.aria))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M169 | 乙 | `ui-sync.js` | `tickBoardLed` | `if (d.cls)` | `if (!(d.cls))` | 行为守 | `PhoneTickTests.test_tick_board_led_assigns_lit_dot_classes_when_countdown_changes` |
| M170 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (typeof document === "undefined")` | `if (!(typeof document === "undefined"))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_row_countdown_keeps_ticking_while_review_drawer_is_open` |
| M171 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (!box \|\| typeof box.querySelectorAll !== "function")` | `if (!(!box \|\| typeof box.querySelectorAll !== "function"))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M172 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (el && el.dataset)` | `if (!(el && el.dataset))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_row_countdown_keeps_ticking_while_review_drawer_is_open` |
| M173 | 乙 | `ui-sync.js` | `tickRowLeft` | `el && el.querySelector ?` | `!(el && el.querySelector) ?` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M174 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (!small \|\| !row.hasLeft)` | `if (!(!small \|\| !row.hasLeft))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M175 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (row.st === "open" && small.textContent !== "已开放")` | `if (!(row.st === "open" && small.textContent !== "已开放"))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_row_crossing_open_moment_aligns_text_and_polls_once` |
| M176 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (small.textContent !== row.left)` | `if (!(small.textContent !== row.left))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_row_countdown_keeps_ticking_while_review_drawer_is_open` |
| M177 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (String(small.className \|\| "") !== cls)` | `if (!(String(small.className \|\| "") !== cls))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_tick_row_left_updates_urgent_class_name` |
| M178 | 乙 | `ui-sync.js` | `tickRowLeft` | `if (crossed && model.paired)` | `if (!(crossed && model.paired))` | 行为守 | `PhoneTickSleepAndDrawerTests.test_device_sleep_marks_clock_uncalibrated_and_polls` |
| M179 | 乙 | `ui-sync.js` | `ingest` | `if (payload.reset)` | `if (!(payload.reset))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M180 | 甲 | `ui-sync.js` | `ingest` | `model.seenEventSeq.clear();` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M181 | 甲 | `ui-sync.js` | `ingest` | `model.seq = 0;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` |
| M182 | 乙 | `ui-sync.js` | `ingest` | `if (logs)` | `if (!(logs))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` |
| M183 | 乙 | `ui-sync.js` | `ingest` | `if (state.login_relay && typeof state.login_relay === "object")` | `if (!(state.login_relay && typeof state.login_relay === "object"))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M184 | 乙 | `ui-sync.js` | `ingest` | `if (Array.isArray(state.activities))` | `if (!(Array.isArray(state.activities)))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M185 | 甲 | `ui-sync.js` | `ingest` | `model.items = state.activities;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M186 | 甲 | `ui-sync.js` | `ingest` | `model.selected = before.filter((id) => { ↵       const item = model.items.find((candidate) => candidate && candidate.id === id); ↵       if (!item \|\| !PhoneModel.actionable(item, model.items)) return false; ↵       const status = PhoneModel.stOf(item, businessNow); ↵       return status === "open" \|\| status === "pre"; ↵     });` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` |
| M187 | 乙 | `ui-sync.js` | `ingest` | `if (!item \|\| !PhoneModel.actionable(item, model.items))` | `if (!(!item \|\| !PhoneModel.actionable(item, model.items)))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M188 | 乙 | `ui-sync.js` | `ingest` | `if (model.selected.length !== before.length)` | `if (!(model.selected.length !== before.length))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` |
| M189 | 甲 | `ui-sync.js` | `ingest` | `model.notice = "";` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_notice_when_selection_intact_and_clears_when_pruned` |
| M190 | 乙 | `ui-sync.js` | `ingest` | `if (state.plan && String(state.plan.plan_id \|\| "") !== model.dismissedPlanId)` | `if (!(state.plan && String(state.plan.plan_id \|\| "") !== model.dismissedPlanId))` | 行为守 | `PhoneDomBehaviourTests.test_refresh_restores_busy_plan_and_stop` |
| M191 | 甲 | `ui-sync.js` | `ingest` | `model.plan = state.plan;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_refresh_restores_busy_plan_and_stop` |
| M192 | 乙 | `ui-sync.js` | `ingest` | `if (typeof state.terms_ok === "boolean")` | `if (!(typeof state.terms_ok === "boolean"))` | 行为守 | `WorkbenchPhoneTests.test_terms_not_accepted_keeps_the_phone_read_only` |
| M193 | 甲 | `ui-sync.js` | `ingest` | `model.termsOk = state.terms_ok;` | `void 0;` | 行为守 | `WorkbenchPhoneTests.test_terms_not_accepted_keeps_the_phone_read_only` |
| M194 | 乙 | `ui-sync.js` | `ingest` | `if (state.relogin_setup && typeof state.relogin_setup === "object")` | `if (!(state.relogin_setup && typeof state.relogin_setup === "object"))` | 行为守 | `ReloginSheetTests.test_busy_phrases_and_verifying_sheet_lock` |
| M195 | 甲 | `ui-sync.js` | `ingest` | `model.reloginSetup = state.relogin_setup;` | `void 0;` | 行为守 | `ReloginSheetTests.test_busy_phrases_and_verifying_sheet_lock` |
| M196 | 乙 | `ui-sync.js` | `ingest` | `if (state.business_clock && typeof state.business_clock === "object")` | `if (!(state.business_clock && typeof state.business_clock === "object"))` | 行为守 | `ExceptionStatesTests.test_bar_sub_says_auto_relogin_in_progress_not_relogin` |
| M197 | 甲 | `ui-sync.js` | `ingest` | `model.clockState = String(state.business_clock.state \|\| "");` | `void 0;` | 行为守 | `ExceptionStatesTests.test_clock_unavailable_blocks_start_and_shows_pending_calibration` |
| M198 | 乙 | `ui-sync.js` | `ingest` | `model.clock ?` | `!(model.clock) ?` | 行为守 | `ExceptionStatesTests.test_clock_unavailable_blocks_start_and_shows_pending_calibration` |
| M199 | 甲 | `ui-sync.js` | `ingest` | `model.lastOkText = sampled !== null ↵       ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(sampled)) : "";` | `void 0;` | 行为守 | `ExceptionStatesTests.test_last_ok_text_recorded_from_clock_snapshot` |
| M200 | 乙 | `ui-sync.js` | `ingest` | `sampled !== null ↵       ?` | `!(sampled !== null) ↵       ?` | 行为守 | `ExceptionStatesTests.test_last_ok_text_recorded_from_clock_snapshot` |
| M201 | 甲 | `ui-sync.js` | `ingest` | `model.pcListError = state.pc_list_error \|\| null;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_alert_hides_bar_until_recovered` |
| M202 | 乙 | `ui-sync.js` | `ingest` | `if (typeof state.busy === "boolean")` | `if (!(typeof state.busy === "boolean"))` | 行为守 | `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` |
| M203 | 甲 | `ui-sync.js` | `ingest` | `model.busy = state.busy;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_pc_list_error_bar_readies_start_button_and_run_tip_toggles_with_busy` |
| M204 | 乙 | `ui-sync.js` | `ingest` | `if (state.retry_policy && typeof state.retry_policy === "object" ↵       && !model.retryHydrated && !model.retryDirty)` | `if (!(state.retry_policy && typeof state.retry_policy === "object" ↵       && !model.retryHydrated && !model.retryDirty))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M205 | 甲 | `ui-sync.js` | `ingest` | `model.retry = { ↵       retry_for_s: Number(state.retry_policy.retry_for_s), ↵       max_attempts: Number(state.retry_policy.max_attempts \|\| 0), ↵     };` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M206 | 甲 | `ui-sync.js` | `ingest` | `model.retryHydrated = true;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_keeps_saved_retry_policy_against_stale_poll_snapshot` |
| M207 | 乙 | `ui-sync.js` | `ingest` | `if (state.retry_options && Array.isArray(state.retry_options.choices))` | `if (!(state.retry_options && Array.isArray(state.retry_options.choices)))` | 行为守 | `ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck` |
| M208 | 甲 | `ui-sync.js` | `ingest` | `model.retryOptions = state.retry_options;` | `void 0;` | 等价 | — |
| M209 | 甲 | `ui-sync.js` | `ingest` | `model.seq = Math.max(model.seq, eventSeq);` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` |
| M210 | 乙 | `ui-sync.js` | `ingest` | `if (eventSeq > 0)` | `if (!(eventSeq > 0))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M211 | 乙 | `ui-sync.js` | `ingest` | `if (model.seenEventSeq.has(eventSeq))` | `if (!(model.seenEventSeq.has(eventSeq)))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M212 | 甲 | `ui-sync.js` | `ingest` | `model.seenEventSeq.add(eventSeq);` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M213 | 甲 | `ui-sync.js` | `ingest` | `model.seenEventSeq.delete(Math.min.apply(null, Array.from(model.seenEventSeq)));` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M214 | 乙 | `ui-sync.js` | `ingest` | `if (event.kind === "log")` | `if (!(event.kind === "log"))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M215 | 乙 | `ui-sync.js` | `ingest` | `typeof raw === "string" ?` | `!(typeof raw === "string") ?` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M216 | 乙 | `ui-sync.js` | `ingest` | `if (line)` | `if (!(line))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_deduplicates_event_seq_but_reset_accepts_new_round` |
| M217 | 乙 | `ui-sync.js` | `ingest` | `if (event.kind === "phone_relogin" && !state.login_relay)` | `if (!(event.kind === "phone_relogin" && !state.login_relay))` | 行为守 | `MobileWriteResilienceTests.test_older_event_cannot_overwrite_current_relogin_snapshot` |
| M218 | 乙 | `ui-sync.js` | `ingest` | `if (payload.seq)` | `if (!(payload.seq))` | 行为守 | `PhoneDomBehaviourTests.test_ingest_reset_rewinds_poll_cursor_and_clears_old_logs` |
| M219 | 甲 | `ui-sync.js` | `ingest` | `model.seq = Math.max(model.seq, Number(payload.seq));` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_poll_is_single_flight_and_recovers_on_visibility` |
| M220 | 乙 | `ui-sync.js` | `ingest` | `if (state.login && typeof state.login === "object")` | `if (!(state.login && typeof state.login === "object"))` | 行为守 | `ExceptionStatesTests.test_bar_sub_says_auto_relogin_in_progress_not_relogin` |
| M221 | 甲 | `ui-sync.js` | `ingest` | `model.login = state.login;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_bar_sub_says_auto_relogin_in_progress_not_relogin` |
| M222 | 乙 | `ui-sync.js` | `ingest` | `if (syncLine)` | `if (!(syncLine))` | 行为守 | `PhoneSyncPolicyTests.test_ingest_updates_last_sync_time_and_falls_back_when_uncalibrated` |
| M223 | 乙 | `ui-sync.js` | `ingest` | `syncNow !== null ↵       ?` | `!(syncNow !== null) ↵       ?` | 行为守 | `PhoneSyncPolicyTests.test_ingest_updates_last_sync_time_and_falls_back_when_uncalibrated` |
| M224 | 乙 | `ui-sync.js` | `ingest` | `if (model.sheetId === "review")` | `if (!(model.sheetId === "review"))` | 行为守 | `SheetsOpsDomTests.test_ingest_refreshes_open_review_drawer_and_closes_only_review_when_empty` |
| M225 | 乙 | `ui-sync.js` | `ingest` | `if (!model.selected.length)` | `if (!(!model.selected.length))` | 行为守 | `SheetsOpsDomTests.test_ingest_refreshes_open_review_drawer_and_closes_only_review_when_empty` |
| M226 | 乙 | `ui-sync.js` | `ingest` | `if (model.pending && !model.pending.done)` | `if (!(model.pending && !model.pending.done))` | 行为守 | `MobileWriteResilienceTests.test_reconciled_rejection_reaches_the_banner` |

## 各类合计

- 行为守：220
- 字面守：0
- 无人守：0
- 无效：0
- 等价：6
- 总计：226

## 按变异口径单列统计（含显隐写入）

| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| 甲类（`model.字段` 写换 `void 0`） | 37 | 0 | 0 | 0 | 3 | 40 |
| 乙类（条件 `C` 换 `!(C)`） | 139 | 0 | 0 | 0 | 2 | 141 |
| 丙类（`.hidden = X` 显隐写换 `void 0`） | 44 | 0 | 0 | 0 | 1 | 45 |

## 按文件分布

| 文件 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| `ui-status.js` | 80 | 0 | 0 | 0 | 3 | 83 |
| `ui-list.js` | 61 | 0 | 0 | 0 | 0 | 61 |
| `ui-sync.js` | 79 | 0 | 0 | 0 | 3 | 82 |
| **总计** | **220** | **0** | **0** | **0** | **6** | **226** |

## 等价判定理由

- **M025**（`ui-status.js:refreshControls`）：在 index.html:254 与测试 DOM 桩中 #relogin-account 恒存在；且同一 refreshControls() 函数第 133 行无条件调用 renderRelogin()（ui-relogin.js:32 无条件写入 $("relogin-account").hidden = !view.needAcct），第 118–132 行（renderAlerts、renderBar 等）均不读取 #relogin-account。将第 117 行的 if (account) 反转后仅跳过第 117 行，随后第 133 行仍会写入完全相同的显隐值，任何 DOM、fetch 请求或定时器均不变。
- **M026**（`ui-status.js:refreshControls`）：在 refreshControls()（ui-status.js:117）后，第 118–132 行（renderAlerts、renderBar 等）均不读取 #relogin-account；第 133 行无条件调用 renderRelogin()（ui-relogin.js:32），且 model-relogin.js:107 在 reloginView() 所有 return 分支前已将 view.needAcct 置为 s ? PhoneModel.relNeedAcct(f, s) : false，即 !view.needAcct 与第 117 行的 setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true 完全同义。删掉第 117 行赋值后第 133 行仍立即写回同值（beginRelogin 也先调 refreshControls() 再读 account.hidden），外部结果完全等价。
- **M027**（`ui-status.js:refreshControls`）：在 refreshControls()（ui-status.js:117）紧接着的第 118–132 行没有任何代码读取 #relogin-account.hidden；同一同步调用末尾第 133 行无条件调用 renderRelogin()（ui-relogin.js:32），将 $("relogin-account").hidden 覆写为 !view.needAcct（model-relogin.js:107 保证其恒等于 setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true）。反转第 117 行三元条件只改变被同一同步函数末尾立即覆写的中间 DOM 属性，任何外部可见结果均不变。
- **M146**（`ui-sync.js:scheduleTick`）：model.tickTimer 的全部读写方只有 scheduleTick（ui-sync.js:10,11,14,15）、onNeedPair（ui-session.js:275-276）、visibilitychange 监听（ui-shell.js:254-255）与 pagehide 监听（ui-shell.js:264-265），所有读取方都只执行 if (model.tickTimer) clearTimeout(model.tickTimer)。scheduleTick 第 10 行已调用 clearTimeout 取消旧定时器：若第 12/13 行提前返回，保留已取消的单调 ID 仅使后续清理方再次对其调用空操作 clearTimeout；若继续到第 14 行则立即覆写新定时器 ID。浏览器与测试沙箱（++timerSeq）均不复用已分配的定时器 ID，任何 DOM、fetch 请求或活跃定时器都无法区分变异前后。
- **M150**（`ui-sync.js:scheduleTick`）：model.tickTimer 的全部读写方只有 scheduleTick（ui-sync.js:10,11,14,15）、onNeedPair（ui-session.js:275-276）、visibilitychange 监听（ui-shell.js:254-255）与 pagehide 监听（ui-shell.js:264-265），所有读取方都只执行 if (model.tickTimer) clearTimeout(model.tickTimer)。本条位于 scheduleTick 的 setTimeout 回调内（第 15 行），此时定时器已触发并退出活跃队列：紧接着第 16 行调用的 tickClock() 不读 model.tickTimer（内部若有 poll(false) 也在 await fetch 之后才调度），第 17 行立即调用 scheduleTick() 对该已触发单调 ID 调用空操作 clearTimeout 并由第 11 行置 null 或第 14 行覆写新 ID。任何 DOM、fetch 请求或活跃定时器均不变。
- **M208**（`ui-sync.js:ingest`）：在 local/ui/m/ 全部 12 份脚本中检索 retryOptions，除 ingest() 第 174 行写入 model.retryOptions = state.retry_options 外无任何读取方，ui-session.js 中的 model 初值也未声明该字段；第 175 行直接将参数 state.retry_options 传给 fillRetryOptions(state.retry_options)。去掉这句未读取的属性写入不会影响任何 DOM、fetch 请求或定时器。
