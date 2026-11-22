# 六条变异反证记录

说明：每条变异仅在系统临时目录复制的 `local/` 副本中施加，运行 6 条新增用例并确认变红，原工作区未做变异留痕。

| 序号 | 变异位置与改法 | 运行结果 | 首个失败用例 |
|---|---|---|---|
| 1 | `local/ui/m/model.js` `loginState`：把 `session_present === false` 判 `never` 与 `session_expired \|\| last_check_state === "expired"` 判 `expired` 两条分支对调 | FAIL（exit=1） | `test_phone_ui.SheetsOpsModelTests.test_login_state_classifies_four_states_and_precedence` |
| 2 | `local/ui/m/model.js` `loginState`：把末尾兜底返回值由 `"unknown"` 改成 `"valid"` | FAIL（exit=1） | `test_phone_ui.SheetsOpsDomTests.test_dom_never_uses_login_copy_and_unknown_hides_expired_banner` |
| 3 | `local/ui/m/model.js` `loginCopy`：把 `never.bannerTitle` 换回 `"电脑上的登录已失效"` | FAIL（exit=1） | `test_phone_ui.SheetsOpsDomTests.test_dom_never_uses_login_copy_and_unknown_hides_expired_banner` |
| 4 | `local/ui/m/model-run.js` `loginLine`：把 `st === "never"` 的后半句分支短路回 `expired` 那一套「失效时/重新登录」文案 | FAIL（exit=1） | `test_phone_ui.SheetsOpsModelTests.test_login_line_four_states_by_setup_and_recovering` |
| 5 | `local/ui/m/model-relogin.js` `loginDoneText`：去掉 `if (firstLogin)` 分支，统一返回「重新登录成功…」 | FAIL（exit=1） | `test_phone_ui.SheetsOpsDomTests.test_dom_first_login_keeps_title_and_done_text_across_valid_snapshot` |
| 6 | `local/ui/m/ui-relogin.js` `renderRelogin`：把面板标题 `loginCopy(...)` 参数从 `model.relFirstLogin ? "never" : "expired"` 改回按当前 `PhoneModel.loginState(model.login)` 取值 | FAIL（exit=1） | `test_phone_ui.SheetsOpsDomTests.test_dom_first_login_keeps_title_and_done_text_across_valid_snapshot` |
