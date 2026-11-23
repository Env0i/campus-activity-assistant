# 第五组（外壳与接线）变异结论（补测之前）

- 范围：`local/ui/m/ui-shell.js` 的 7 个顶层函数（共 141 条）：甲类（`model.字段` 写换 `void 0`）25 条、乙类（条件 `C` 换 `!(C)`）38 条、丙类（`.hidden = X` 写换 `void 0`）19 条、戊类（`return true`/`false` 互换）0 条、己类（`.textContent`/`.value`/`.disabled` 写换 `void 0`）17 条、庚类（`addEventListener` 绑定整条换 `void 0`）42 条。

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|---|
| M001 | 乙 | `ui-shell.js` | `sheetBusy` | `if (flow && String(flow.mode \|\| "") === "auto")` | `if (!(flow && String(flow.mode \|\| "") === "auto"))` | 行为守 | `PhoneReloginRecoveryTests.test_auto_snapshot_clears_challenge_submitting_and_starting_locks` |
| M002 | 乙 | `ui-shell.js` | `openSheet` | `if (!root \|\| !SHEET_TITLES[id] \|\| model.sheetId)` | `if (!(!root \|\| !SHEET_TITLES[id] \|\| model.sheetId))` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M003 | 甲 | `ui-shell.js` | `openSheet` | `model.sheetOpener = document.activeElement \|\| null;` | `void 0;` | 无人守 | — |
| M004 | 甲 | `ui-shell.js` | `openSheet` | `model.sheetId = id;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M005 | 丙 | `ui-shell.js` | `openSheet` | `$("sheet-err").hidden = true;` | `void 0;` | 无人守 | — |
| M006 | 丙 | `ui-shell.js` | `openSheet` | `$("more-panel").hidden = id !== "more";` | `void 0;` | 无人守 | — |
| M007 | 丙 | `ui-shell.js` | `openSheet` | `$("review-panel").hidden = id !== "review";` | `void 0;` | 行为守 | `SheetShellTests.test_open_close_switch_and_busy_lock` |
| M008 | 丙 | `ui-shell.js` | `openSheet` | `$("confirm-panel").hidden = id !== "confirm";` | `void 0;` | 无人守 | — |
| M009 | 丙 | `ui-shell.js` | `openSheet` | `$("relogin-panel").hidden = id !== "relogin";` | `void 0;` | 行为守 | `SheetShellTests.test_relogin_entry_switches_from_an_open_sheet` |
| M010 | 丙 | `ui-shell.js` | `openSheet` | `$("review-foot").hidden = id !== "review";` | `void 0;` | 无人守 | — |
| M011 | 丙 | `ui-shell.js` | `openSheet` | `$("relogin-foot").hidden = id !== "relogin";` | `void 0;` | 行为守 | `SheetShellTests.test_relogin_entry_switches_from_an_open_sheet` |
| M012 | 己 | `ui-shell.js` | `openSheet` | `$("sheet-title").textContent = id === "relogin" ↵     ? PhoneModel.loginCopy(model.relFirstLogin ? "never" : "expired", false).reloginEntry ↵     : SHEET_TITLES[id];` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M013 | 乙 | `ui-shell.js` | `openSheet` | `id === "relogin" ↵     ?` | `!(id === "relogin") ↵     ?` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M014 | 乙 | `ui-shell.js` | `openSheet` | `model.relFirstLogin ?` | `!(model.relFirstLogin) ?` | 无人守 | — |
| M015 | 乙 | `ui-shell.js` | `openSheet` | `if (id === "more")` | `if (!(id === "more"))` | 无人守 | — |
| M016 | 己 | `ui-shell.js` | `openSheet` | `$("btn-relogin-open").textContent = PhoneModel.loginCopy(PhoneModel.loginState(model.login), false).reloginEntry;` | `void 0;` | 无人守 | — |
| M017 | 丙 | `ui-shell.js` | `openSheet` | `$("btn-sheet-close").hidden = sheetBusy();` | `void 0;` | 无人守 | — |
| M018 | 丙 | `ui-shell.js` | `openSheet` | `root.hidden = false;` | `void 0;` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M019 | 乙 | `ui-shell.js` | `closeSheet` | `if (!root \|\| !model.sheetId)` | `if (!(!root \|\| !model.sheetId))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M020 | 乙 | `ui-shell.js` | `closeSheet` | `if (!force && sheetBusy())` | `if (!(!force && sheetBusy()))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M021 | 丙 | `ui-shell.js` | `closeSheet` | `$("btn-sheet-close").hidden = true;` | `void 0;` | 行为守 | `SheetShellTests.test_open_close_switch_and_busy_lock` |
| M022 | 甲 | `ui-shell.js` | `closeSheet` | `model.sheetId = "";` | `void 0;` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M023 | 丙 | `ui-shell.js` | `closeSheet` | `root.hidden = true;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M024 | 丙 | `ui-shell.js` | `closeSheet` | `$("more-panel").hidden = true;` | `void 0;` | 行为守 | `SheetShellTests.test_open_close_switch_and_busy_lock` |
| M025 | 丙 | `ui-shell.js` | `closeSheet` | `$("review-panel").hidden = true;` | `void 0;` | 行为守 | `WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` |
| M026 | 丙 | `ui-shell.js` | `closeSheet` | `$("confirm-panel").hidden = true;` | `void 0;` | 无人守 | — |
| M027 | 丙 | `ui-shell.js` | `closeSheet` | `$("relogin-panel").hidden = true;` | `void 0;` | 无人守 | — |
| M028 | 丙 | `ui-shell.js` | `closeSheet` | `$("review-foot").hidden = true;` | `void 0;` | 无人守 | — |
| M029 | 丙 | `ui-shell.js` | `closeSheet` | `$("relogin-foot").hidden = true;` | `void 0;` | 无人守 | — |
| M030 | 丙 | `ui-shell.js` | `closeSheet` | `$("sheet-err").hidden = true;` | `void 0;` | 无人守 | — |
| M031 | 乙 | `ui-shell.js` | `closeSheet` | `if (el) el.value = "";` | `if (!(el)) el.value = "";` | 行为守 | `SheetShellTests.test_relogin_fields_are_cleared_when_the_sheet_closes` |
| M032 | 己 | `ui-shell.js` | `closeSheet` | `if (el) el.value = "";` | `if (el) void 0;` | 行为守 | `SheetShellTests.test_relogin_fields_are_cleared_when_the_sheet_closes` |
| M033 | 甲 | `ui-shell.js` | `closeSheet` | `model.confirm = null;` | `void 0;` | 行为守 | `SheetsOpsDomTests.test_stop_and_cancel_task_confirm_sheets_follow_prototype` |
| M034 | 甲 | `ui-shell.js` | `closeSheet` | `model.relConfirm = false;` | `void 0;` | 无人守 | — |
| M035 | 甲 | `ui-shell.js` | `closeSheet` | `model.sheetOpener = null;` | `void 0;` | 无人守 | — |
| M036 | 乙 | `ui-shell.js` | `closeSheet` | `if (opener && typeof opener.focus === "function")` | `if (!(opener && typeof opener.focus === "function"))` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M037 | 乙 | `ui-shell.js` | `showSheetError` | `if (!model.sheetId)` | `if (!(!model.sheetId))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M038 | 己 | `ui-shell.js` | `showSheetError` | `el.textContent = String(text \|\| "");` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M039 | 丙 | `ui-shell.js` | `showSheetError` | `el.hidden = !text;` | `void 0;` | 行为守 | `SheetShellTests.test_network_failure_shows_red_bar_in_sheet` |
| M040 | 乙 | `ui-shell.js` | `askConfirm` | `if (!view \|\| model.sheetId)` | `if (!(!view \|\| model.sheetId))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M041 | 甲 | `ui-shell.js` | `askConfirm` | `model.confirm = { kind: kind, taskId: taskId };` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M042 | 己 | `ui-shell.js` | `askConfirm` | `$("sheet-title").textContent = view.title;` | `void 0;` | 行为守 | `RunWaitDomTests.test_cancel_start_asks_in_a_sheet_before_posting` |
| M043 | 己 | `ui-shell.js` | `askConfirm` | `$("confirm-text").textContent = view.text;` | `void 0;` | 行为守 | `RunWaitDomTests.test_cancel_start_asks_in_a_sheet_before_posting` |
| M044 | 己 | `ui-shell.js` | `askConfirm` | `$("btn-confirm-no").textContent = view.no;` | `void 0;` | 行为守 | `RunWaitDomTests.test_cancel_start_asks_in_a_sheet_before_posting` |
| M045 | 己 | `ui-shell.js` | `askConfirm` | `$("btn-confirm-yes").textContent = view.yes;` | `void 0;` | 行为守 | `RunWaitDomTests.test_cancel_start_asks_in_a_sheet_before_posting` |
| M046 | 己 | `ui-shell.js` | `askConfirm` | `$("btn-confirm-no").disabled = false;` | `void 0;` | 无人守 | — |
| M047 | 己 | `ui-shell.js` | `askConfirm` | `$("btn-confirm-yes").disabled = false;` | `void 0;` | 无人守 | — |
| M048 | 乙 | `ui-shell.js` | `onConfirmYes` | `kind === "cancelstart" ?` | `!(kind === "cancelstart") ?` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M049 | 乙 | `ui-shell.js` | `onConfirmYes` | `kind === "stop" ?` | `!(kind === "stop") ?` | 行为守 | `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` |
| M050 | 乙 | `ui-shell.js` | `onConfirmYes` | `kind === "cancelTask" ?` | `!(kind === "cancelTask") ?` | 行为守 | `SheetsOpsDomTests.test_cancel_task_failure_success_and_missing_task_keeps_confirm_open` |
| M051 | 乙 | `ui-shell.js` | `onConfirmYes` | `if (!run)` | `if (!(!run))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M052 | 己 | `ui-shell.js` | `onConfirmYes` | `$("btn-confirm-yes").disabled = true;` | `void 0;` | 无人守 | — |
| M053 | 己 | `ui-shell.js` | `onConfirmYes` | `$("btn-confirm-no").disabled = true;` | `void 0;` | 无人守 | — |
| M054 | 乙 | `ui-shell.js` | `onConfirmYes` | `if (ok !== false)` | `if (!(ok !== false))` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M055 | 己 | `ui-shell.js` | `onConfirmYes` | `$("btn-confirm-yes").disabled = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_post_failure_reconcile_and_done_guard` |
| M056 | 己 | `ui-shell.js` | `onConfirmYes` | `$("btn-confirm-no").disabled = false;` | `void 0;` | 无人守 | — |
| M057 | 庚 | `ui-shell.js` | `wire` | `$("btn-pair").addEventListener("click", () => void pair());` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_pair_failure_says_the_network_is_down` |
| M058 | 庚 | `ui-shell.js` | `wire` | `$("pair-code").addEventListener("input", () => { ↵     const el = $("pair-code"); ↵     const digits = String(el.value \|\| "").replace(/\D/g, "").slice(0, 6); ↵     if (el.value !== digits) el.value = digits; ↵     model.pairErr = ""; ↵     renderPair(); ↵   });` | `void 0;` | 无人守 | — |
| M059 | 乙 | `ui-shell.js` | `wire` | `if (el.value !== digits) el.value = digits;` | `if (!(el.value !== digits)) el.value = digits;` | 无人守 | — |
| M060 | 己 | `ui-shell.js` | `wire` | `if (el.value !== digits) el.value = digits;` | `if (el.value !== digits) void 0;` | 无人守 | — |
| M061 | 甲 | `ui-shell.js` | `wire` | `model.pairErr = "";` | `void 0;` | 无人守 | — |
| M062 | 庚 | `ui-shell.js` | `wire` | `$("pair-code").addEventListener("keydown", (event) => { ↵     if (event && event.key === "Enter") void pair(); ↵   });` | `void 0;` | 无人守 | — |
| M063 | 乙 | `ui-shell.js` | `wire` | `if (event && event.key === "Enter")` | `if (!(event && event.key === "Enter"))` | 无人守 | — |
| M064 | 庚 | `ui-shell.js` | `wire` | `$("btn-refresh").addEventListener("click", () => void poll(true));` | `void 0;` | 无人守 | — |
| M065 | 庚 | `ui-shell.js` | `wire` | `$("btn-offline-retry").addEventListener("click", () => void poll(true));` | `void 0;` | 行为守 | `ExceptionStatesTests.test_silent_stale_hides_red_bar_but_retrying_shows_it` |
| M066 | 庚 | `ui-shell.js` | `wire` | `$("btn-pair-ok").addEventListener("click", () => { ↵     model.pairOkPending = false; ↵     renderAlerts(PhoneModel.isStale(model.lastOkAt, model.nowMs)); ↵   });` | `void 0;` | 行为守 | `PairStatesDomTests.test_pair_success_shows_dismissable_connected_alert` |
| M067 | 甲 | `ui-shell.js` | `wire` | `model.pairOkPending = false;` | `void 0;` | 行为守 | `PairStatesDomTests.test_pair_success_shows_dismissable_connected_alert` |
| M068 | 庚 | `ui-shell.js` | `wire` | `$("btn-more").addEventListener("click", () => openSheet("more"));` | `void 0;` | 行为守 | `ReloginSheetTests.test_render_relogin_sheet_title_err_text_auto_save_and_footer_buttons` |
| M069 | 庚 | `ui-shell.js` | `wire` | `$("btn-sheet-close").addEventListener("click", () => closeSheet());` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_clears_captcha_and_locks_unlike_waiting_without_id` |
| M070 | 庚 | `ui-shell.js` | `wire` | `$("sheet-root").addEventListener("click", (event) => { ↵     if (event && event.target === event.currentTarget) closeSheet(); ↵   });` | `void 0;` | 无人守 | — |
| M071 | 乙 | `ui-shell.js` | `wire` | `if (event && event.target === event.currentTarget)` | `if (!(event && event.target === event.currentTarget))` | 无人守 | — |
| M072 | 庚 | `ui-shell.js` | `wire` | `document.addEventListener("keydown", (event) => { ↵     if (event && event.key === "Escape") closeSheet(); ↵   });` | `void 0;` | 无人守 | — |
| M073 | 乙 | `ui-shell.js` | `wire` | `if (event && event.key === "Escape")` | `if (!(event && event.key === "Escape"))` | 无人守 | — |
| M074 | 庚 | `ui-shell.js` | `wire` | `$("btn-start").addEventListener("click", () => { ↵     if (PhoneModel.loginExpired(model.login) && !model.busy ↵         && !(model.pending && !model.pending.done)) openRelogin(); ↵     else openReview(); ↵   });` | `void 0;` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M075 | 乙 | `ui-shell.js` | `wire` | `if (PhoneModel.loginExpired(model.login) && !model.busy ↵         && !(model.pending && !model.pending.done))` | `if (!(PhoneModel.loginExpired(model.login) && !model.busy ↵         && !(model.pending && !model.pending.done)))` | 行为守 | `ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom` |
| M076 | 庚 | `ui-shell.js` | `wire` | `$("btn-banner-relogin").addEventListener("click", () => openRelogin());` | `void 0;` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M077 | 庚 | `ui-shell.js` | `wire` | `$("btn-review-start").addEventListener("click", () => { closeSheet(true); void startPlan(); });` | `void 0;` | 无人守 | — |
| M078 | 庚 | `ui-shell.js` | `wire` | `$("btn-review-back").addEventListener("click", () => closeSheet());` | `void 0;` | 行为守 | `WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders` |
| M079 | 庚 | `ui-shell.js` | `wire` | `$("review-items").addEventListener("click", (event) => { ↵     const id = event && event.target && event.target.dataset ↵       ? String(event.target.dataset.id \|\| "") : ""; ↵     if (id) removeFromReview(id); ↵   });` | `void 0;` | 行为守 | `SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty` |
| M080 | 乙 | `ui-shell.js` | `wire` | `event && event.target && event.target.dataset ↵       ?` | `!(event && event.target && event.target.dataset) ↵       ?` | 行为守 | `SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty` |
| M081 | 乙 | `ui-shell.js` | `wire` | `if (id) removeFromReview(id);` | `if (!(id)) removeFromReview(id);` | 行为守 | `SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty` |
| M082 | 庚 | `ui-shell.js` | `wire` | `$("btn-stop").addEventListener("click", () => askConfirm("stop"));` | `void 0;` | 无人守 | — |
| M083 | 庚 | `ui-shell.js` | `wire` | `$("btn-cancel-start").addEventListener("click", () => askConfirm("cancelstart"));` | `void 0;` | 行为守 | `RunWaitDomTests.test_cancel_start_asks_in_a_sheet_before_posting` |
| M084 | 庚 | `ui-shell.js` | `wire` | `$("btn-confirm-no").addEventListener("click", () => closeSheet());` | `void 0;` | 行为守 | `RunWaitDomTests.test_cancel_start_asks_in_a_sheet_before_posting` |
| M085 | 庚 | `ui-shell.js` | `wire` | `$("btn-confirm-yes").addEventListener("click", () => onConfirmYes());` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_cancel_pending_start_race_and_failure_recovery` |
| M086 | 庚 | `ui-shell.js` | `wire` | `$("btn-reselect").addEventListener("click", () => reselectFailed());` | `void 0;` | 行为守 | `ResultTermsDomTests.test_reselect_and_finish_dismiss_plan_collapse_list_and_clear_notice` |
| M087 | 庚 | `ui-shell.js` | `wire` | `$("btn-finish").addEventListener("click", () => finishPlanView());` | `void 0;` | 行为守 | `ResultTermsDomTests.test_finish_and_reselect_clear_task_cards_immediately` |
| M088 | 庚 | `ui-shell.js` | `wire` | `$("btn-toggle-list").addEventListener("click", () => { ↵     model.listOpen = !model.listOpen; ↵     renderItems(); ↵   });` | `void 0;` | 行为守 | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| M089 | 甲 | `ui-shell.js` | `wire` | `model.listOpen = !model.listOpen;` | `void 0;` | 行为守 | `RunWaitDomTests.test_busy_plan_renders_board_cards_and_collapsed_list` |
| M090 | 乙 | `ui-shell.js` | `wire` | `if ($("btn-show-window"))` | `if (!($("btn-show-window")))` | 行为守 | `SheetsOpsDomTests.test_show_computer_window_payload_and_logs` |
| M091 | 庚 | `ui-shell.js` | `wire` | `$("btn-show-window").addEventListener("click", () => void showComputerWindow());` | `void 0;` | 行为守 | `SheetsOpsDomTests.test_show_computer_window_payload_and_logs` |
| M092 | 庚 | `ui-shell.js` | `wire` | `$("btn-relogin-open").addEventListener("click", () => openRelogin());` | `void 0;` | 行为守 | `SheetShellTests.test_relogin_entry_switches_from_an_open_sheet` |
| M093 | 庚 | `ui-shell.js` | `wire` | `$("btn-relogin").addEventListener("click", () => void beginRelogin());` | `void 0;` | 无人守 | — |
| M094 | 庚 | `ui-shell.js` | `wire` | `$("btn-relogin-auto").addEventListener("click", () => void beginRelogin());` | `void 0;` | 行为守 | `ReloginSheetTests.test_begin_relogin_clears_confirm_and_previous_account_postscript` |
| M095 | 庚 | `ui-shell.js` | `wire` | `$("btn-relogin-submit").addEventListener("click", () => void submitRelogin());` | `void 0;` | 无人守 | — |
| M096 | 庚 | `ui-shell.js` | `wire` | `$("btn-relogin-cancel").addEventListener("click", async () => { ↵     model.relConfirm = false; ↵     /* 取消成立（或本来就没有在途流程）才收 sheet；撤不掉就留着重试 */ ↵     const ok = await cancelRelogin(); ↵     if (ok !== false) closeSheet(true); ↵   });` | `void 0;` | 行为守 | `SheetShellTests.test_relogin_fields_are_cleared_when_the_sheet_closes` |
| M097 | 甲 | `ui-shell.js` | `wire` | `model.relConfirm = false;` | `void 0;` | 无人守 | — |
| M098 | 乙 | `ui-shell.js` | `wire` | `if (ok !== false) closeSheet(true);` | `if (!(ok !== false)) closeSheet(true);` | 行为守 | `SheetShellTests.test_relogin_fields_are_cleared_when_the_sheet_closes` |
| M099 | 庚 | `ui-shell.js` | `wire` | `$("btn-relogin-refresh").addEventListener("click", () => void refreshRelogin());` | `void 0;` | 无人守 | — |
| M100 | 庚 | `ui-shell.js` | `wire` | `$("btn-relogin-done").addEventListener("click", () => closeSheet());` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_snapshot_clears_challenge_submitting_and_starting_locks` |
| M101 | 庚 | `ui-shell.js` | `wire` | `$(id).addEventListener("input", () => refreshControls());` | `void 0;` | 无人守 | — |
| M102 | 庚 | `ui-shell.js` | `wire` | `$("q").addEventListener("input", () => { ↵     model.filter.q = $("q").value; ↵     if ($("search-q")) $("search-q").value = $("q").value; ↵     renderItems(); ↵   });` | `void 0;` | 无人守 | — |
| M103 | 甲 | `ui-shell.js` | `wire` | `model.filter.q = $("q").value;` | `void 0;` | 无人守 | — |
| M104 | 乙 | `ui-shell.js` | `wire` | `if ($("search-q")) $("search-q").value = $("q").value;` | `if (!($("search-q"))) $("search-q").value = $("q").value;` | 无人守 | — |
| M105 | 己 | `ui-shell.js` | `wire` | `if ($("search-q")) $("search-q").value = $("q").value;` | `if ($("search-q")) void 0;` | 无人守 | — |
| M106 | 庚 | `ui-shell.js` | `wire` | `$("btn-search").addEventListener("click", () => toggleSearch());` | `void 0;` | 行为守 | `ListDetailModelTests.test_list_notice_and_search_toggle` |
| M107 | 庚 | `ui-shell.js` | `wire` | `$("search-q").addEventListener("input", () => { ↵     model.filter.q = $("search-q").value; ↵     if ($("q")) $("q").value = $("search-q").value; ↵     renderItems(); ↵   });` | `void 0;` | 行为守 | `ListDetailModelTests.test_list_notice_and_search_toggle` |
| M108 | 甲 | `ui-shell.js` | `wire` | `model.filter.q = $("search-q").value;` | `void 0;` | 行为守 | `ListDetailModelTests.test_list_notice_and_search_toggle` |
| M109 | 乙 | `ui-shell.js` | `wire` | `if ($("q")) $("q").value = $("search-q").value;` | `if (!($("q"))) $("q").value = $("search-q").value;` | 行为守 | `ListDetailModelTests.test_list_notice_and_search_toggle` |
| M110 | 己 | `ui-shell.js` | `wire` | `if ($("q")) $("q").value = $("search-q").value;` | `if ($("q")) void 0;` | 行为守 | `ListDetailModelTests.test_list_notice_and_search_toggle` |
| M111 | 庚 | `ui-shell.js` | `wire` | `$("btn-pick-next").addEventListener("click", () => { ↵     if (!model.pickId) return; ↵     const res = PhoneModel.pickItem(model.selected, model.items, model.pickId, true); ↵     model.selected = res.selected; ↵     model.notice = res.notice; ↵     renderItems(); ↵   });` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M112 | 乙 | `ui-shell.js` | `wire` | `if (!model.pickId) return;` | `if (!(!model.pickId)) return;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M113 | 甲 | `ui-shell.js` | `wire` | `model.selected = res.selected;` | `void 0;` | 行为守 | `ListDetailModelTests.test_render_board_visibility_led_dots_and_pick_next_selection` |
| M114 | 甲 | `ui-shell.js` | `wire` | `model.notice = res.notice;` | `void 0;` | 无人守 | — |
| M115 | 庚 | `ui-shell.js` | `wire` | `btn.addEventListener("click", () => { ↵       model.filter.status = btn.dataset.status; ↵       document.querySelectorAll("[data-status]").forEach((other) => ↵         other.setAttribute("aria-pressed", other === btn ? "true" : "false")); ↵       renderItems(); ↵     });` | `void 0;` | 无人守 | — |
| M116 | 甲 | `ui-shell.js` | `wire` | `model.filter.status = btn.dataset.status;` | `void 0;` | 无人守 | — |
| M117 | 乙 | `ui-shell.js` | `wire` | `document.querySelectorAll("[data-status]").forEach((other) => ↵         other.setAttribute("aria-pressed", other === btn ? "true" : "false"));` | `document.querySelectorAll("[data-status]").forEach((other) => ↵         other.setAttribute("aria-pressed", !(other === btn) ? "true" : "false"));` | 无人守 | — |
| M118 | 庚 | `ui-shell.js` | `wire` | `btn.addEventListener("click", () => { ↵       model.filter.time = btn.dataset.time; ↵       document.querySelectorAll("[data-time]").forEach((other) => ↵         other.setAttribute("aria-pressed", other === btn ? "true" : "false")); ↵       renderItems(); ↵     });` | `void 0;` | 行为守 | `ListDetailModelTests.test_today_chip_shows_real_shape_activity_via_dom` |
| M119 | 甲 | `ui-shell.js` | `wire` | `model.filter.time = btn.dataset.time;` | `void 0;` | 无人守 | — |
| M120 | 乙 | `ui-shell.js` | `wire` | `document.querySelectorAll("[data-time]").forEach((other) => ↵         other.setAttribute("aria-pressed", other === btn ? "true" : "false"));` | `document.querySelectorAll("[data-time]").forEach((other) => ↵         other.setAttribute("aria-pressed", !(other === btn) ? "true" : "false"));` | 无人守 | — |
| M121 | 庚 | `ui-shell.js` | `wire` | `$("retry-for").addEventListener("change", () => { ↵     model.retry.retry_for_s = Number($("retry-for").value); ↵     model.retryDirty = true; ↵     void saveRetry(); ↵     refreshControls(); ↵   });` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M122 | 甲 | `ui-shell.js` | `wire` | `model.retry.retry_for_s = Number($("retry-for").value);` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M123 | 甲 | `ui-shell.js` | `wire` | `    model.retry.retry_for_s = Number($("retry-for").value); ↵     model.retryDirty = true;` | `    model.retry.retry_for_s = Number($("retry-for").value); ↵     void 0;` | 无人守 | — |
| M124 | 庚 | `ui-shell.js` | `wire` | `$("max-attempts").addEventListener("change", () => { ↵     model.retry.max_attempts = Number($("max-attempts").value \|\| 0); ↵     model.retryDirty = true; ↵     void saveRetry(); ↵   });` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M125 | 甲 | `ui-shell.js` | `wire` | `model.retry.max_attempts = Number($("max-attempts").value \|\| 0);` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_save_retry_payload_failure_log_and_clears_dirty_before_hydration` |
| M126 | 甲 | `ui-shell.js` | `wire` | `    model.retry.max_attempts = Number($("max-attempts").value \|\| 0); ↵     model.retryDirty = true;` | `    model.retry.max_attempts = Number($("max-attempts").value \|\| 0); ↵     void 0;` | 无人守 | — |
| M127 | 庚 | `ui-shell.js` | `wire` | `document.addEventListener("visibilitychange", () => { ↵     if (document.hidden) { ↵       if (model.pollTimer) clearTimeout(model.pollTimer); ↵       model.pollTimer = null; ↵       if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表 ↵       model.tickTimer = null; ↵     } else if (model.paired) { ↵       void poll(false);       // 回前台立刻补一次，仍按事件游标补齐 ↵     } ↵   });` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M128 | 乙 | `ui-shell.js` | `wire` | `if (document.hidden)` | `if (!(document.hidden))` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M129 | 乙 | `ui-shell.js` | `wire` | `  document.addEventListener("visibilitychange", () => { ↵     if (document.hidden) { ↵       if (model.pollTimer) clearTimeout(model.pollTimer);` | `  document.addEventListener("visibilitychange", () => { ↵     if (document.hidden) { ↵       if (!(model.pollTimer)) clearTimeout(model.pollTimer);` | 行为守 | `PhoneTickTests.test_back_to_foreground_reschedules_and_syncs_once` |
| M130 | 甲 | `ui-shell.js` | `wire` | `      if (model.pollTimer) clearTimeout(model.pollTimer); ↵       model.pollTimer = null; ↵       if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表` | `      if (model.pollTimer) clearTimeout(model.pollTimer); ↵       void 0; ↵       if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表` | 无人守 | — |
| M131 | 乙 | `ui-shell.js` | `wire` | `if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表` | `if (!(model.tickTimer)) clearTimeout(model.tickTimer);   // P1：后台停表` | 行为守 | `PhoneTickTests.test_back_to_foreground_reschedules_and_syncs_once` |
| M132 | 甲 | `ui-shell.js` | `wire` | `      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表 ↵       model.tickTimer = null;` | `      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表 ↵       void 0;` | 无人守 | — |
| M133 | 乙 | `ui-shell.js` | `wire` | `else if (model.paired)` | `else if (!(model.paired))` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M134 | 乙 | `ui-shell.js` | `wire` | `if (typeof window !== "undefined" && typeof window.addEventListener === "function")` | `if (!(typeof window !== "undefined" && typeof window.addEventListener === "function"))` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M135 | 庚 | `ui-shell.js` | `wire` | `window.addEventListener("pagehide", () => { ↵       if (model.pollTimer) clearTimeout(model.pollTimer); ↵       model.pollTimer = null; ↵       if (model.tickTimer) clearTimeout(model.tickTimer); ↵       model.tickTimer = null; ↵     });` | `void 0;` | 无人守 | — |
| M136 | 乙 | `ui-shell.js` | `wire` | `    window.addEventListener("pagehide", () => { ↵       if (model.pollTimer) clearTimeout(model.pollTimer);` | `    window.addEventListener("pagehide", () => { ↵       if (!(model.pollTimer)) clearTimeout(model.pollTimer);` | 无人守 | — |
| M137 | 甲 | `ui-shell.js` | `wire` | `    window.addEventListener("pagehide", () => { ↵       if (model.pollTimer) clearTimeout(model.pollTimer); ↵       model.pollTimer = null;` | `    window.addEventListener("pagehide", () => { ↵       if (model.pollTimer) clearTimeout(model.pollTimer); ↵       void 0;` | 无人守 | — |
| M138 | 乙 | `ui-shell.js` | `wire` | `      if (model.tickTimer) clearTimeout(model.tickTimer); ↵       model.tickTimer = null; ↵     });` | `      if (!(model.tickTimer)) clearTimeout(model.tickTimer); ↵       model.tickTimer = null; ↵     });` | 无人守 | — |
| M139 | 甲 | `ui-shell.js` | `wire` | `      if (model.tickTimer) clearTimeout(model.tickTimer); ↵       model.tickTimer = null; ↵     });` | `      if (model.tickTimer) clearTimeout(model.tickTimer); ↵       void 0; ↵     });` | 无人守 | — |
| M140 | 庚 | `ui-shell.js` | `wire` | `window.addEventListener("pageshow", () => { ↵       if (!document.hidden && model.paired) void poll(false); // bfcache 恢复后按游标补齐 ↵     });` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M141 | 乙 | `ui-shell.js` | `wire` | `if (!document.hidden && model.paired)` | `if (!(!document.hidden && model.paired))` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |

## 各类合计

- 行为守：83
- 字面守：0
- 无人守：58
- 无效：0
- 等价：0
- 总计：141

## 按变异口径统计

| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| 甲类（`model.字段` 写换 `void 0`） | 10 | 0 | 15 | 0 | 0 | 25 |
| 乙类（条件 `C` 换 `!(C)`） | 27 | 0 | 11 | 0 | 0 | 38 |
| 丙类（`.hidden = X` 写换 `void 0`） | 9 | 0 | 10 | 0 | 0 | 19 |
| 戊类（`return true`/`false` 互换） | 0 | 0 | 0 | 0 | 0 | 0 |
| 己类（`.textContent`/`.value`/`.disabled` 写换 `void 0`） | 9 | 0 | 8 | 0 | 0 | 17 |
| 庚类（`addEventListener` 绑定整条换 `void 0`） | 28 | 0 | 14 | 0 | 0 | 42 |

## 按函数统计

| 函数 | 口径（甲 / 乙 / 丙 / 戊 / 己 / 庚） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---|---:|---:|---:|---:|---:|---:|
| `sheetBusy` | 0 / 1 / 0 / 0 / 0 / 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| `openSheet` | 2 / 4 / 9 / 0 / 2 / 0 | 8 | 0 | 9 | 0 | 0 | 17 |
| `closeSheet` | 4 / 4 / 9 / 0 / 1 / 0 | 11 | 0 | 7 | 0 | 0 | 18 |
| `showSheetError` | 0 / 1 / 1 / 0 / 1 / 0 | 3 | 0 | 0 | 0 | 0 | 3 |
| `askConfirm` | 1 / 1 / 0 / 0 / 6 / 0 | 6 | 0 | 2 | 0 | 0 | 8 |
| `onConfirmYes` | 0 / 5 / 0 / 0 / 4 / 0 | 6 | 0 | 3 | 0 | 0 | 9 |
| `wire` | 18 / 22 / 0 / 0 / 3 / 42 | 48 | 0 | 37 | 0 | 0 | 85 |
