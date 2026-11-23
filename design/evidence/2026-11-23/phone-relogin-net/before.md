# 第四组（重新登录）变异结论（补测之前）

- 范围：`local/ui/m/ui-relogin.js` 的 8 个顶层函数（共 129 条）：甲类（`model.字段` 写换 `void 0`）28 条、乙类（条件 `C` 换 `!(C)`）35 条、丙类（`.hidden = X` 写换 `void 0`）19 条、丁类（请求载荷属性与 `args.*` 写入变异）15 条、戊类（`return true`/`false` 互换）3 条、己类（`.textContent`/`.value`/`.src`/`removeAttribute` 写换 `void 0`）29 条。

| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---|---|---|---|---|
| M001 | 乙 | `ui-relogin.js` | `renderRelogin` | `if (model.sheetId === "relogin")` | `if (!(model.sheetId === "relogin"))` | 无人守 | — |
| M002 | 己 | `ui-relogin.js` | `renderRelogin` | `$("sheet-title").textContent = PhoneModel.loginCopy( ↵       model.relFirstLogin ? "never" : "expired", false).reloginEntry;` | `void 0;` | 无人守 | — |
| M003 | 乙 | `ui-relogin.js` | `renderRelogin` | `model.relFirstLogin ?` | `!(model.relFirstLogin) ?` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M004 | 己 | `ui-relogin.js` | `renderRelogin` | `$("rel-err").textContent = view.err;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M005 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("rel-err").hidden = !view.err;` | `void 0;` | 无人守 | — |
| M006 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("rel-spin").hidden = !view.spin;` | `void 0;` | 行为守 | `ReloginSheetTests.test_done_while_busy_says_plan_continues` |
| M007 | 己 | `ui-relogin.js` | `renderRelogin` | `$("rel-busy-text").textContent = view.spin;` | `void 0;` | 行为守 | `ReloginSheetTests.test_auto_state_shows_progress_and_background_button` |
| M008 | 己 | `ui-relogin.js` | `renderRelogin` | `$("rel-text").textContent = view.text;` | `void 0;` | 行为守 | `ReloginSheetTests.test_auto_state_shows_progress_and_background_button` |
| M009 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("rel-text").hidden = !view.text;` | `void 0;` | 无人守 | — |
| M010 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("rel-form").hidden = !view.showForm;` | `void 0;` | 行为守 | `ReloginSheetTests.test_auto_state_shows_progress_and_background_button` |
| M011 | 己 | `ui-relogin.js` | `renderRelogin` | `$("rel-lead").textContent = view.lead;` | `void 0;` | 行为守 | `ReloginSheetTests.test_handoff_lead_hides_account_fields` |
| M012 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("rel-lead").hidden = !view.lead;` | `void 0;` | 行为守 | `ReloginSheetTests.test_lead_four_states_and_relbad_red_error` |
| M013 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("relogin-account").hidden = !view.needAcct;` | `void 0;` | 行为守 | `ReloginSheetTests.test_lead_four_states_and_relbad_red_error` |
| M014 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("relogin-captcha-group").hidden = !view.needCap;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_whole_captcha_area` |
| M015 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("rel-auto").hidden = !view.autoCap;` | `void 0;` | 无人守 | — |
| M016 | 己 | `ui-relogin.js` | `renderRelogin` | `$("rel-save-gain").textContent = view.saveLine;` | `void 0;` | 无人守 | — |
| M017 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("btn-relogin-auto").hidden = view.mainKind !== "auto";` | `void 0;` | 无人守 | — |
| M018 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("btn-relogin").hidden = view.mainKind !== "begin";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_whole_captcha_area` |
| M019 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("btn-relogin-submit").hidden = view.mainKind !== "submit";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_captcha_and_reports_progress` |
| M020 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("rel-second-row").hidden = !(view.refresh \|\| view.cancel);` | `void 0;` | 无人守 | — |
| M021 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("btn-relogin-refresh").hidden = !view.refresh;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_snapshot_restores_challenge_without_erasing_typed_code` |
| M022 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("btn-relogin-cancel").hidden = !view.cancel;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_verifying_keeps_controls_and_disables_resubmit` |
| M023 | 丙 | `ui-relogin.js` | `renderRelogin` | `$("btn-relogin-done").hidden = !view.done;` | `void 0;` | 无人守 | — |
| M024 | 己 | `ui-relogin.js` | `renderRelogin` | `$("btn-relogin-done").textContent = view.done;` | `void 0;` | 行为守 | `ReloginSheetTests.test_auto_state_shows_progress_and_background_button` |
| M025 | 乙 | `ui-relogin.js` | `openRelogin` | `if (model.sheetId === "relogin")` | `if (!(model.sheetId === "relogin"))` | 行为守 | `ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin` |
| M026 | 乙 | `ui-relogin.js` | `openRelogin` | `if (model.sheetId) closeSheet(true);` | `if (!(model.sheetId)) closeSheet(true);` | 行为守 | `SheetShellTests.test_relogin_entry_switches_from_an_open_sheet` |
| M027 | 甲 | `ui-relogin.js` | `openRelogin` | `model.relFirstLogin = PhoneModel.loginState(model.login) === "never";` | `void 0;` | 行为守 | `SheetsOpsModelTests.test_dom_first_login_keeps_title_and_done_text_across_valid_snapshot` |
| M028 | 甲 | `ui-relogin.js` | `openRelogin` | `model.relConfirm = !liveFlow && !setup.paused && !!setup.saved && !!setup.ocr_ready;` | `void 0;` | 行为守 | `ReloginSheetTests.test_relconfirm_intercepts_before_begin` |
| M029 | 丙 | `ui-relogin.js` | `endReloginControls` | `$("captcha").hidden = true;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_captcha_and_reports_progress` |
| M030 | 己 | `ui-relogin.js` | `endReloginControls` | `$("captcha").removeAttribute("src");` | `void 0;` | 无人守 | — |
| M031 | 甲 | `ui-relogin.js` | `ingestRelogin` | `model.flow = info;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_older_event_cannot_overwrite_current_relogin_snapshot` |
| M032 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (String(info.mode \|\| "") === "auto" ↵       && relayState !== "success" && relayState !== "failed" && relayState !== "canceled")` | `if (!(String(info.mode \|\| "") === "auto" ↵       && relayState !== "success" && relayState !== "failed" && relayState !== "canceled"))` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_captcha_and_reports_progress` |
| M033 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (info.retrying)` | `if (!(info.retrying))` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_captcha_and_reports_progress` |
| M034 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("relogin-note").textContent = "电脑正在自动登录" + ↵         (rounds > 0 ? "（第 " + (rounds + 1) + " 次）" : "") + "…";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_captcha_and_reports_progress` |
| M035 | 乙 | `ui-relogin.js` | `ingestRelogin` | `rounds > 0 ?` | `!(rounds > 0) ?` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_hides_the_captcha_and_reports_progress` |
| M036 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("relogin-note").textContent = ↵         "电脑会自动识别验证码；连续失败几次之后才会转到这里手动输入";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_auto_mode_idle_explains_who_will_solve_the_captcha` |
| M037 | 甲 | `ui-relogin.js` | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     model.reloginStarting = false;` | `    void 0; ↵     model.reloginSubmitting = false; ↵     model.reloginStarting = false;` | 无人守 | — |
| M038 | 甲 | `ui-relogin.js` | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     model.reloginStarting = false;` | `    model.challenge = null; ↵     void 0; ↵     model.reloginStarting = false;` | 无人守 | — |
| M039 | 甲 | `ui-relogin.js` | `ingestRelogin` | `model.reloginStarting = false;` | `void 0;` | 无人守 | — |
| M040 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (relayState === "waiting_code" && info.challenge_id)` | `if (!(relayState === "waiting_code" && info.challenge_id))` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M041 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (PhoneModel.matchesChallenge(model.challenge, info.flow_id, info.challenge_id))` | `if (!(PhoneModel.matchesChallenge(model.challenge, info.flow_id, info.challenge_id)))` | 行为守 | `PhoneReloginRecoveryTests.test_illegal_image_is_not_rendered` |
| M042 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (!info.submit_pending)` | `if (!(!info.submit_pending))` | 行为守 | `PhoneReloginRecoveryTests.test_reconcile_unlocks_only_without_submit_in_flight` |
| M043 | 甲 | `ui-relogin.js` | `ingestRelogin` | `if (!info.submit_pending) model.reloginSubmitting = false;` | `if (!info.submit_pending) void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_reconcile_unlocks_only_without_submit_in_flight` |
| M044 | 甲 | `ui-relogin.js` | `ingestRelogin` | `model.challenge = { ↵       flow_id: info.flow_id, challenge_id: info.challenge_id, ↵     };` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_illegal_image_is_not_rendered` |
| M045 | 甲 | `ui-relogin.js` | `ingestRelogin` | `    model.reloginSubmitting = false; ↵     const img = $("captcha");` | `    void 0; ↵     const img = $("captcha");` | 行为守 | `PhoneReloginRecoveryTests.test_new_challenge_clears_old_input_and_unlocks` |
| M046 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (String(info.image \|\| "").indexOf("data:image/png;base64,") === 0)` | `if (!(String(info.image \|\| "").indexOf("data:image/png;base64,") === 0))` | 行为守 | `PhoneReloginRecoveryTests.test_illegal_image_is_not_rendered` |
| M047 | 己 | `ui-relogin.js` | `ingestRelogin` | `img.src = info.image;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_manual_takeover_renders_the_captcha_again` |
| M048 | 丙 | `ui-relogin.js` | `ingestRelogin` | `img.hidden = false;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_manual_takeover_after_auto_opens_the_captcha_area_again` |
| M049 | 丙 | `ui-relogin.js` | `ingestRelogin` | `img.hidden = true;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_illegal_image_is_not_rendered` |
| M050 | 己 | `ui-relogin.js` | `ingestRelogin` | `img.removeAttribute("src");` | `void 0;` | 无人守 | — |
| M051 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("code").value = "";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_new_challenge_clears_old_input_and_unlocks` |
| M052 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (relayState === "verifying")` | `if (!(relayState === "verifying"))` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M053 | 甲 | `ui-relogin.js` | `ingestRelogin` | `    model.reloginSubmitting = false; ↵     $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | `    void 0; ↵     $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | 无人守 | — |
| M054 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_verifying_keeps_controls_and_disables_resubmit` |
| M055 | 乙 | `ui-relogin.js` | `ingestRelogin` | `else if (relayState === "starting")` | `else if (!(relayState === "starting"))` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M056 | 甲 | `ui-relogin.js` | `ingestRelogin` | `    model.reloginSubmitting = false; ↵     $("relogin-note").textContent = String(info.mode \|\| "") === "auto"` | `    void 0; ↵     $("relogin-note").textContent = String(info.mode \|\| "") === "auto"` | 无人守 | — |
| M057 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("relogin-note").textContent = String(info.mode \|\| "") === "auto" ↵       ? PhoneModel.RELOGIN_BUSY.prepare : PhoneModel.RELOGIN_BUSY.needCode;` | `void 0;` | 无人守 | — |
| M058 | 乙 | `ui-relogin.js` | `ingestRelogin` | `String(info.mode \|\| "") === "auto" ↵       ?` | `!(String(info.mode \|\| "") === "auto") ↵       ?` | 无人守 | — |
| M059 | 乙 | `ui-relogin.js` | `ingestRelogin` | `else if (relayState === "success")` | `else if (!(relayState === "success"))` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M060 | 甲 | `ui-relogin.js` | `ingestRelogin` | `  } else if (relayState === "success") { ↵     model.challenge = null;` | `  } else if (relayState === "success") { ↵     void 0;` | 无人守 | — |
| M061 | 甲 | `ui-relogin.js` | `ingestRelogin` | `  } else if (relayState === "success") { ↵     model.challenge = null; ↵     model.reloginSubmitting = false;` | `  } else if (relayState === "success") { ↵     model.challenge = null; ↵     void 0;` | 无人守 | — |
| M062 | 乙 | `ui-relogin.js` | `ingestRelogin` | `if (info.live)` | `if (!(info.live))` | 行为守 | `PhoneReloginRecoveryTests.test_the_archived_success_is_not_replayed_as_this_round` |
| M063 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("relogin-note").textContent = PhoneModel.loginDoneText(!!model.relFirstLogin, model.busy);` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_the_archived_success_is_not_replayed_as_this_round` |
| M064 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("relogin-note").textContent = "上次重新登录已完成；需要时点「重新登录」再试";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_the_archived_success_is_not_replayed_as_this_round` |
| M065 | 乙 | `ui-relogin.js` | `ingestRelogin` | `else if (relayState === "failed" \|\| relayState === "canceled")` | `else if (!(relayState === "failed" \|\| relayState === "canceled"))` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M066 | 甲 | `ui-relogin.js` | `ingestRelogin` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     model.challenge = null;` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     void 0;` | 无人守 | — |
| M067 | 甲 | `ui-relogin.js` | `ingestRelogin` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     model.challenge = null; ↵     model.reloginSubmitting = false;` | `  } else if (relayState === "failed" \|\| relayState === "canceled") { ↵     model.challenge = null; ↵     void 0;` | 无人守 | — |
| M068 | 己 | `ui-relogin.js` | `ingestRelogin` | `$("relogin-note").textContent = info.live ↵       ? PhoneModel.reloginFailText(reason) ↵       : PhoneModel.reloginFailText(reason, "上次重新登录未完成：");` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M069 | 乙 | `ui-relogin.js` | `ingestRelogin` | `info.live ↵       ?` | `!(info.live) ↵       ?` | 行为守 | `PhoneReloginRecoveryTests.test_idle_snapshot_does_not_overwrite_the_last_reason` |
| M070 | 乙 | `ui-relogin.js` | `ingestRelogin` | `else if (relayState && relayState !== "waiting_code")` | `else if (!(relayState && relayState !== "waiting_code"))` | 无人守 | — |
| M071 | 甲 | `ui-relogin.js` | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     endReloginControls(); ↵   }` | `    void 0; ↵     model.reloginSubmitting = false; ↵     endReloginControls(); ↵   }` | 无人守 | — |
| M072 | 甲 | `ui-relogin.js` | `ingestRelogin` | `    model.challenge = null; ↵     model.reloginSubmitting = false; ↵     endReloginControls(); ↵   }` | `    model.challenge = null; ↵     void 0; ↵     endReloginControls(); ↵   }` | 无人守 | — |
| M073 | 乙 | `ui-relogin.js` | `beginRelogin` | `if (model.reloginStarting)` | `if (!(model.reloginStarting))` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M074 | 乙 | `ui-relogin.js` | `beginRelogin` | `if (!canWrite())` | `if (!(!canWrite()))` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M075 | 甲 | `ui-relogin.js` | `beginRelogin` | `model.reloginStarting = true;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_double_tap_starts_only_one_relogin` |
| M076 | 甲 | `ui-relogin.js` | `beginRelogin` | `model.relConfirm = false;` | `void 0;` | 无人守 | — |
| M077 | 甲 | `ui-relogin.js` | `beginRelogin` | `model.relEnteredAcct = false;` | `void 0;` | 无人守 | — |
| M078 | 甲 | `ui-relogin.js` | `beginRelogin` | `model.relSavedChoice = false;` | `void 0;` | 无人守 | — |
| M079 | 乙 | `ui-relogin.js` | `beginRelogin` | `if (account && !account.hidden)` | `if (!(account && !account.hidden))` | 行为守 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M080 | 乙 | `ui-relogin.js` | `beginRelogin` | `if (!user \|\| !pass)` | `if (!(!user \|\| !pass))` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M081 | 甲 | `ui-relogin.js` | `beginRelogin` | `      model.reloginStarting = false; ↵       $("relogin-note").textContent = "账号和密码都要填。";` | `      void 0; ↵       $("relogin-note").textContent = "账号和密码都要填。";` | 无人守 | — |
| M082 | 己 | `ui-relogin.js` | `beginRelogin` | `$("relogin-note").textContent = "账号和密码都要填。";` | `void 0;` | 无人守 | — |
| M083 | 丁 | `ui-relogin.js` | `beginRelogin` | `args.username = user;` | `void 0;` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M084 | 丁 | `ui-relogin.js` | `beginRelogin` | `args.password = pass;` | `void 0;` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M085 | 丁 | `ui-relogin.js` | `beginRelogin` | `args.save = !!($("relogin-save") \|\| {}).checked;` | `void 0;` | 行为守 | `ReloginSheetTests.test_done_postscript_both_branches` |
| M086 | 甲 | `ui-relogin.js` | `beginRelogin` | `model.relEnteredAcct = true;` | `void 0;` | 行为守 | `ReloginSheetTests.test_done_postscript_both_branches` |
| M087 | 甲 | `ui-relogin.js` | `beginRelogin` | `model.relSavedChoice = args.save;` | `void 0;` | 行为守 | `ReloginSheetTests.test_done_postscript_both_branches` |
| M088 | 己 | `ui-relogin.js` | `beginRelogin` | `$("relogin-pass").value = "";` | `void 0;` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M089 | 丁 | `ui-relogin.js` | `beginRelogin` | `action: "phone_relogin_begin",` | `action: undefined,` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M090 | 丁 | `ui-relogin.js` | `beginRelogin` | `action: "phone_relogin_begin", args: args` | `action: "phone_relogin_begin", args: undefined` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M091 | 甲 | `ui-relogin.js` | `beginRelogin` | `  model.reloginStarting = false; ↵   if (!body \|\| !body.ok)` | `  void 0; ↵   if (!body \|\| !body.ok)` | 行为守 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M092 | 乙 | `ui-relogin.js` | `beginRelogin` | `if (!body \|\| !body.ok)` | `if (!(!body \|\| !body.ok))` | 行为守 | `PhoneReloginRecoveryTests.test_begin_shows_the_computer_took_over` |
| M093 | 己 | `ui-relogin.js` | `beginRelogin` | `$("relogin-note").textContent = body && body.error === "plan_late" ↵       ? "现在来不及重新登录：" + String(body.text \|\| "有场次正在提交，或者离开放不到 100 秒。") ↵       : "还不能开始：" + String((body && body.text) \|\| (body && body.error) \|\| "请到电脑上准备账号");` | `void 0;` | 无人守 | — |
| M094 | 乙 | `ui-relogin.js` | `beginRelogin` | `body && body.error === "plan_late" ↵       ?` | `!(body && body.error === "plan_late") ↵       ?` | 无人守 | — |
| M095 | 乙 | `ui-relogin.js` | `beginRelogin` | `if (String(body.mode \|\| "") === "auto")` | `if (!(String(body.mode \|\| "") === "auto"))` | 行为守 | `PhoneReloginRecoveryTests.test_begin_shows_the_computer_took_over` |
| M096 | 己 | `ui-relogin.js` | `beginRelogin` | `$("relogin-note").textContent = "电脑正在自动登录，手机上不用再操作";` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_begin_shows_the_computer_took_over` |
| M097 | 己 | `ui-relogin.js` | `beginRelogin` | `$("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.needCode;` | `void 0;` | 无人守 | — |
| M098 | 乙 | `ui-relogin.js` | `submitRelogin` | `if (!model.flow \|\| !model.challenge)` | `if (!(!model.flow \|\| !model.challenge))` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M099 | 乙 | `ui-relogin.js` | `submitRelogin` | `if (!PhoneModel.canSubmitRelogin(model, model.challenge))` | `if (!(!PhoneModel.canSubmitRelogin(model, model.challenge)))` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M100 | 乙 | `ui-relogin.js` | `submitRelogin` | `if (!PhoneModel.relCanSubmit({ needCap: true, code }))` | `if (!(!PhoneModel.relCanSubmit({ needCap: true, code })))` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M101 | 乙 | `ui-relogin.js` | `submitRelogin` | `if (!PhoneModel.matchesChallenge(model.flow, model.challenge.flow_id, ↵                                    model.challenge.challenge_id))` | `if (!(!PhoneModel.matchesChallenge(model.flow, model.challenge.flow_id, ↵                                    model.challenge.challenge_id)))` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M102 | 己 | `ui-relogin.js` | `submitRelogin` | `$("relogin-note").textContent = "验证码已换代，请看新图";` | `void 0;` | 无人守 | — |
| M103 | 己 | `ui-relogin.js` | `submitRelogin` | `    $("relogin-note").textContent = "验证码已换代，请看新图"; ↵     $("code").value = "";` | `    $("relogin-note").textContent = "验证码已换代，请看新图"; ↵     void 0;` | 无人守 | — |
| M104 | 甲 | `ui-relogin.js` | `submitRelogin` | `model.reloginSubmitting = true;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M105 | 丁 | `ui-relogin.js` | `submitRelogin` | `method: "POST",` | `method: undefined,` | 无人守 | — |
| M106 | 丁 | `ui-relogin.js` | `submitRelogin` | `body: { action: "phone_relogin_submit", args: { ↵         flow_id: model.challenge.flow_id, ↵         challenge_id: model.challenge.challenge_id, code } }` | `body: undefined` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M107 | 丁 | `ui-relogin.js` | `submitRelogin` | `action: "phone_relogin_submit",` | `action: undefined,` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M108 | 丁 | `ui-relogin.js` | `submitRelogin` | `args: { ↵         flow_id: model.challenge.flow_id, ↵         challenge_id: model.challenge.challenge_id, code }` | `args: undefined` | 无人守 | — |
| M109 | 丁 | `ui-relogin.js` | `submitRelogin` | `flow_id: model.challenge.flow_id,` | `flow_id: undefined,` | 无人守 | — |
| M110 | 丁 | `ui-relogin.js` | `submitRelogin` | `challenge_id: model.challenge.challenge_id,` | `challenge_id: undefined,` | 无人守 | — |
| M111 | 丁 | `ui-relogin.js` | `submitRelogin` | `code } } });` | `code: undefined } } });` | 无人守 | — |
| M112 | 己 | `ui-relogin.js` | `submitRelogin` | `  } catch (err) { ↵     // 结果未知：既不能当成功也不能当失败。保持禁用，先对账问服务端 ↵     // 这张图到底有没有在途提交，等快照给结论再决定放行还是收口。 ↵     // RL02：旧句「提交结果未知，正在对账…」归并为「正在登录，请等结果」 ↵     $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | `  } catch (err) { ↵     // 结果未知：既不能当成功也不能当失败。保持禁用，先对账问服务端 ↵     // 这张图到底有没有在途提交，等快照给结论再决定放行还是收口。 ↵     // RL02：旧句「提交结果未知，正在对账…」归并为「正在登录，请等结果」 ↵     void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_lost_submit_keeps_locked_and_reconciles` |
| M113 | 乙 | `ui-relogin.js` | `submitRelogin` | `if (!result \|\| result.status !== 200 \|\| !result.body \|\| !result.body.ok)` | `if (!(!result \|\| result.status !== 200 \|\| !result.body \|\| !result.body.ok))` | 无人守 | — |
| M114 | 乙 | `ui-relogin.js` | `submitRelogin` | `if (error === "duplicate_submit")` | `if (!(error === "duplicate_submit"))` | 无人守 | — |
| M115 | 己 | `ui-relogin.js` | `submitRelogin` | `    if (error === "duplicate_submit") { ↵       // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行 ↵       // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」 ↵       $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;` | `    if (error === "duplicate_submit") { ↵       // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行 ↵       // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」 ↵       void 0;` | 无人守 | — |
| M116 | 甲 | `ui-relogin.js` | `submitRelogin` | `model.reloginSubmitting = false;` | `void 0;` | 无人守 | — |
| M117 | 己 | `ui-relogin.js` | `submitRelogin` | `$("relogin-note").textContent = String( ↵       (result && result.body && (result.body.text \|\| result.body.error)) ↵         \|\| "提交没有被接受");` | `void 0;` | 无人守 | — |
| M118 | 己 | `ui-relogin.js` | `submitRelogin` | `  $("code").value = ""; ↵   void poll(true);` | `  void 0; ↵   void poll(true);` | 无人守 | — |
| M119 | 乙 | `ui-relogin.js` | `cancelRelogin` | `if (!flowId \|\| (flow && flow.live === false))` | `if (!(!flowId \|\| (flow && flow.live === false)))` | 行为守 | `MobileWriteResilienceTests.test_failed_cancel_without_error_field_keeps_challenge` |
| M120 | 戊 | `ui-relogin.js` | `cancelRelogin` | `if (!flowId \|\| (flow && flow.live === false)) return true;` | `if (!flowId \|\| (flow && flow.live === false)) return false;` | 行为守 | `SheetShellTests.test_relogin_fields_are_cleared_when_the_sheet_closes` |
| M121 | 丁 | `ui-relogin.js` | `cancelRelogin` | `action: "phone_relogin_cancel",` | `action: undefined,` | 行为守 | `PhoneReloginRecoveryTests.test_refresh_challenge_cancels_then_starts_once` |
| M122 | 丁 | `ui-relogin.js` | `cancelRelogin` | `args: { flow_id: flowId }` | `args: undefined` | 无人守 | — |
| M123 | 丁 | `ui-relogin.js` | `cancelRelogin` | `flow_id: flowId` | `flow_id: undefined` | 无人守 | — |
| M124 | 乙 | `ui-relogin.js` | `cancelRelogin` | `if (body && body.error)` | `if (!(body && body.error))` | 行为守 | `MobileWriteResilienceTests.test_failed_cancel_without_error_field_keeps_challenge` |
| M125 | 戊 | `ui-relogin.js` | `cancelRelogin` | `return false;` | `return true;` | 行为守 | `MobileWriteResilienceTests.test_failed_cancel_without_error_field_keeps_challenge` |
| M126 | 甲 | `ui-relogin.js` | `cancelRelogin` | `model.challenge = null;` | `void 0;` | 无人守 | — |
| M127 | 丙 | `ui-relogin.js` | `cancelRelogin` | `$("captcha").hidden = true;` | `void 0;` | 无人守 | — |
| M128 | 戊 | `ui-relogin.js` | `cancelRelogin` | `  return true; ↵ }` | `  return false; ↵ }` | 行为守 | `PhoneReloginRecoveryTests.test_refresh_challenge_cancels_then_starts_once` |
| M129 | 乙 | `ui-relogin.js` | `refreshRelogin` | `if (canceled === false)` | `if (!(canceled === false))` | 行为守 | `PhoneReloginRecoveryTests.test_refresh_challenge_cancels_then_starts_once` |

## 各类合计

- 行为守：79
- 字面守：0
- 无人守：50
- 无效：0
- 等价：0
- 总计：129

## 按变异口径统计

| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---:|---:|---:|---:|---:|---:|
| 甲类（`model.字段` 写换 `void 0`） | 11 | 0 | 17 | 0 | 0 | 28 |
| 乙类（条件 `C` 换 `!(C)`） | 29 | 0 | 6 | 0 | 0 | 35 |
| 丙类（`.hidden = X` 写换 `void 0`） | 12 | 0 | 7 | 0 | 0 | 19 |
| 丁类（请求载荷属性与 `args.*` 写入变异） | 8 | 0 | 7 | 0 | 0 | 15 |
| 戊类（`return true`/`false` 互换） | 3 | 0 | 0 | 0 | 0 | 3 |
| 己类（`.textContent`/`.value`/`.src`/`removeAttribute` 写换 `void 0`） | 16 | 0 | 13 | 0 | 0 | 29 |

## 按函数统计

| 函数 | 口径（甲 / 乙 / 丙 / 丁 / 戊 / 己） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |
|---|---|---:|---:|---:|---:|---:|---:|
| `renderRelogin` | 0 / 2 / 15 / 0 / 0 / 7 | 15 | 0 | 9 | 0 | 0 | 24 |
| `openRelogin` | 2 / 2 / 0 / 0 / 0 / 0 | 4 | 0 | 0 | 0 | 0 | 4 |
| `endReloginControls` | 0 / 0 / 1 / 0 / 0 / 1 | 1 | 0 | 1 | 0 | 0 | 2 |
| `ingestRelogin` | 15 / 15 / 2 / 0 / 0 / 10 | 27 | 0 | 15 | 0 | 0 | 42 |
| `beginRelogin` | 8 / 7 / 0 / 5 / 0 / 5 | 17 | 0 | 8 | 0 | 0 | 25 |
| `submitRelogin` | 2 / 6 / 0 / 7 / 0 / 6 | 8 | 0 | 13 | 0 | 0 | 21 |
| `cancelRelogin` | 1 / 2 / 1 / 3 / 3 / 0 | 6 | 0 | 4 | 0 | 0 | 10 |
| `refreshRelogin` | 0 / 1 / 0 / 0 / 0 / 0 | 1 | 0 | 0 | 0 | 0 | 1 |
