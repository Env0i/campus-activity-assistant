# 步骤 1 出口变异结论表（补之前）

- 基线提交：`682463d`（D2 行号以 dddc179 为准，脚本逐行核对通过）
- 执行命令（仓库根，临时目录用占位符）：`python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py --phase 补之前 --out <表名>.md`
- 测试集合（D3）：`test_ui_*.py`、`test_prerefactor_fixes.py`、`test_phone_ui.py`（含本计划新建文件）
- 结论口径（D4）：变红用例按 D1 认定；「等价」由人工复判（D6），脚本只出前三类

| 编号 | 状态 | 文件与函数 | 结论 | 变红的用例名 |
|---|---|---|---|---|
| L01 | 登录·校验中 | controllers/refresh.js refresh | 没人守 | （无） |
| L02 | 登录·校验中 | controllers/refresh.js refresh | 行为测试已守 | test_ui_contract_login.StartGateContractTests.test_refresh_catch_failure_leaves_checking_and_sets_unknown |
| L03 | 登录·校验中 | controllers/refresh.js settleSynchronous | 没人守 | （无） |
| L04 | 登录·校验中 | controllers/refresh.js settleSynchronous | 没人守 | （无） |
| L05 | 登录·校验中 | controllers/refresh.js settleSynchronous | 没人守 | （无） |
| L06 | 登录·校验中 | app.js check 事件 | 行为测试已守 | test_ui_contract_list.EmptyPreferenceBehaviorTests.test_check_arrival_updates_empty_state、test_ui_contract_login.LoginSequenceBehaviorTests.test_successful_relogin_clears_old_anchor_then_adopts_new、test_ui_reliability.AutoListRefreshTests.test_a_success_resets_the_failure_count |
| L07 | 登录·浏览器登录窗口开着 | controllers/plan.js doLogin | 没人守 | （无） |
| L08 | 登录·浏览器登录窗口开着 | controllers/plan.js doLogin | 没人守 | （无） |
| L09 | 登录·浏览器登录窗口开着 | controllers/plan.js doLogin | 没人守 | （无） |
| L10 | 登录·浏览器登录窗口开着 | controllers/plan.js handleDone | 行为测试已守 | test_ui_contract_login.LoginSequenceBehaviorTests.test_cancelled_relogin_restores_full_prior_login_state、test_ui_contract_login.LoginSequenceBehaviorTests.test_cancelled_relogin_without_any_session_stays_logged_out、test_ui_contract_login.LoginSequenceBehaviorTests.test_failed_relogin_keeps_countdown_instead_of_invalid |
| L11 | 登录·已转人工 | state/login.js setLogin | 没人守 | （无） |
| L12 | 登录·已转人工 | views/relogin.js receiveReloginState | 没人守 | （无） |
| L13 | 登录·自动登录中 | state/login.js reconcileAutoLogin | 行为测试已守 | test_ui_reliability.SilentReloginResidualTests.test_pill_leaves_auto_login_when_a_valid_check_arrives |
| L14 | 登录·自动登录中 | state/login.js reconcileAutoLogin | 行为测试已守 | test_ui_reliability.SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_check_cannot_reach_the_school、test_ui_reliability.SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_check_times_out、test_ui_reliability.SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_refresh_check_fails_outright |
| L15 | 登录·自动登录中 | views/relogin.js receiveReloginState | 行为测试已守 | test_ui_reliability.SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_relay_finishes_or_hands_off、test_ui_reliability.SilentReloginUiTests.test_handoff_restores_the_reminder_and_asks_for_the_captcha |
| L16 | 登录·重新登录对话框 | views/relogin.js closeRelogin | 行为测试已守 | test_ui_reliability.SilentReloginResidualTests.test_closing_the_dialog_keeps_the_computers_own_auto_login |
| P01 | 计划栏·开始请求 | controllers/plan.js startPlan | 行为测试已守 | test_ui_contract_feedback.ErrorFeedbackRoundtripTests.test_start_plan_component_failure_banner_only、test_ui_contract_list.EmptyPreferenceBehaviorTests.test_start_plan_payload_carries_headed_switch |
| P02 | 计划栏·开始请求 | controllers/plan.js reconcileStart | 行为测试已守 | test_ui_reliability.StartReconcileQueryTests.test_old_generation_reply_is_ignored |
| P03 | 计划栏·开始请求 | controllers/plan.js reconcileStart | 没人守 | （无） |
| P04 | 计划栏·开始请求 | controllers/plan.js adoptPlan | 行为测试已守 | test_ui_reliability.ReconcileTerminalTests.test_finished_plan_restores_terminal_not_busy、test_ui_reliability.StartReconcileTests.test_accepted_reconcile_restores_plan |
| P05 | 计划栏·正在停止 | controllers/plan-events.js presentPlanDone | 没人守 | （无） |
| P06 | 计划栏·正在停止 | controllers/plan-events.js handlePlanDone | 行为测试已守 | test_ui_reliability.StoppingEarlyReturnTests.test_duplicate_done_clears_stopping_flag |
| P07 | 计划栏·正在停止 | controllers/plan.js startPlan | 没人守 | （无） |
| P08 | 计划栏·正在停止 | controllers/plan.js adoptPlan | 没人守 | （无） |
| P09 | 计划栏·正在停止 | controllers/plan.js doStopPlan | 行为测试已守 | test_prerefactor_fixes.PlanEditingExitTests.test_plain_stop_refusal_does_not_invent_the_editing_sentence、test_prerefactor_fixes.PlanEditingExitTests.test_stop_bridge_error_while_editing_returns_to_the_running_plan、test_prerefactor_fixes.PlanEditingExitTests.test_stop_refused_while_editing_returns_to_the_running_plan |
| P10 | 计划栏·修改中 | controllers/plan-events.js presentPlanDone | 行为测试已守 | test_prerefactor_fixes.PlanEditingExitTests.test_plan_ending_by_itself_while_editing_clears_editing、test_prerefactor_fixes.PlanEditingExitTests.test_reselect_after_the_natural_end_is_not_still_editing |
| P11 | 计划栏·修改中 | controllers/plan.js startPlan | 行为测试已守 | test_ui_main_window_plan.DockStatesTests.test_start_plan_clears_editing_even_when_plan_id_stays |
| P12 | 计划栏·修改中 | controllers/plan.js doStopPlan | 行为测试已守 | test_prerefactor_fixes.PlanEditingExitTests.test_stop_bridge_error_while_editing_returns_to_the_running_plan、test_prerefactor_fixes.PlanEditingExitTests.test_stop_refused_while_editing_returns_to_the_running_plan |
| P13 | 计划栏·修改中 | state/filters.js clearSelection | 没人守 | （无） |
| P14 | 计划栏·修改中 | state/plan.js handlePlan | 没人守 | （无） |
| R01 | 列表·加载中 | controllers/refresh.js refresh | 行为测试已守 | test_ui_main_window_list.ListFailureLogTests.test_timeout_logs_one_line |
| R02 | 列表·加载中 | controllers/refresh.js refresh | 行为测试已守 | test_ui_main_window_list.ListFailureLogTests.test_promise_rejection_logs_one_line |
| R03 | 列表·加载中 | controllers/refresh.js settleSynchronous | 没人守 | （无） |
| R04 | 列表·加载中 | controllers/refresh.js settleSynchronous | 没人守 | （无） |
| R05 | 列表·加载中 | controllers/refresh.js settleSynchronous | 没人守 | （无） |
| R06 | 列表·加载中 | controllers/refresh.js applyActivities | 行为测试已守 | test_ui_main_window_list.ListFailureLogTests.test_error_reply_logs_one_line、test_ui_reliability.AutoListRefreshTests.test_manual_refresh_failure_still_clears_the_list |
| R07 | 列表·加载中 | controllers/refresh.js applyActivities | 行为测试已守 | test_prerefactor_fixes.ProgramRefreshTests.test_accepting_terms_with_a_list_refreshes_in_the_background、test_prerefactor_fixes.ProgramRefreshTests.test_browser_login_success_with_a_list_refreshes_in_the_background、test_prerefactor_fixes.ProgramRefreshTests.test_cancel_success_refreshes_in_the_background |
| R08 | 列表·取消报名 | controllers/cancel.js cancelSettle | 行为测试已守 | test_prerefactor_fixes.ProgramRefreshTests.test_cancel_success_refreshes_in_the_background、test_ui_conflict_cancel.CancelFlowTests.test_bridge_failure_is_reported_as_unknown_not_success、test_ui_conflict_cancel.CancelFlowTests.test_confirm_calls_cancel_signup_once_and_marks_busy |
| C01 | 组件·面板请求在途 | views/phone.js enableFeature | 没人守 | （无） |
| C02 | 组件·面板请求在途 | views/phone.js toggleStart | 没人守 | （无） |
| C03 | 组件·面板请求在途 | views/phone.js toggleStop | 没人守 | （无） |
| C04 | 组件·面板请求在途 | views/phone.js downloadComponent | 没人守 | （无） |
| C05 | 组件·面板请求在途 | views/phone.js saveCredentials | 行为测试已守 | test_phone_ui.HelpAdvancedBehaviorTests.test_failed_save_clears_password_and_recovers_buttons |
| C06 | 组件·手机访问开启中或停止中 | views/phone.js toggleStart | 没人守 | （无） |
| C07 | 组件·手机访问开启中或停止中 | views/phone.js toggleStop | 没人守 | （无） |
| C08 | 组件·导入安装中 | views/phone.js installComponent | 行为测试已守 | test_phone_ui.ComponentDownloadUiTests.test_install_shows_installing_until_refresh_returns、test_phone_ui.ComponentDownloadUiTests.test_ocr_install_shows_installing_until_refresh_returns |
| C09 | 组件·验证码识别面板请求在途 | views/settings.js enableOcr | 没人守 | （无） |

汇总：没人守 25、只有字面断言守 0、行为测试已守 22、等价 0（共 47 行）
