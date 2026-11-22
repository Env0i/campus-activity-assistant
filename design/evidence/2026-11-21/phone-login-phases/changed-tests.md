# 手机页登录四态改动涉及的测试记录

## 一、放行修改的旧断言

修改原因统一为：**决策 006 规定未确认不得写成有效；后端 `local/app.py` 的 `_last_check_fields` 恒带 `last_check_state`（仅取 `valid` / `expired` / `unknown`），缺字段仅在旧测试载荷里出现。** 除以下两条用例中明确列出的断言外，其余既有断言未改动、未删除、未加 skip。

### 1. `SheetsOpsModelTests.test_login_line_four_states_follow_prototype`（`local/tests/test_phone_ui.py`）

- **四条 `setup` 组合与 `paused` 用例输入**（原 `{session_present: true}`，5 处）：
  - 改前：`mk({session_present: true}, ...)`
  - 改后：`mk({session_present: true, last_check_state: "valid"}, ...)`
  - 期望文本不变（这五条测的是后半句与 `paused` 组合，不是前半句的未校验态）。
- **`bare` 断言（`mk(null, null)`）**：
  - 改前：`self.assertEqual(bare, "电脑上的登录有效。电脑上没保存账号，重新登录要输账号、密码和验证码。", "快照没到手：按未失效、未保存呈现，不猜")`
  - 改后：`self.assertEqual(bare, "电脑上的登录状态还没确认。电脑上没保存账号，重新登录要输账号、密码和验证码。", "快照没到手：按待确认、未保存呈现，不写成有效")`
- 同用例内的 `expired` 断言保持不动。

### 2. `SheetsOpsModelTests.test_login_line_follows_the_computers_last_school_check`（`local/tests/test_phone_ui.py`）

- **`unknown` 断言**：
  - 改前：`self.assertEqual(unknown, "电脑上的登录有效。失效时电脑会自己重新登录。", "没确认（unknown）不当成失效")`
  - 改后：`self.assertEqual(unknown, "电脑上的登录状态还没确认。失效时电脑会自己重新登录。", "没确认（unknown）不写成有效")`
- **`bare` 断言（`{session_present: true, session_expired: false}` 缺 `last_check_state`）**：
  - 改前：`self.assertEqual(bare, valid, "老载荷没带 last_check_state：保持原口径")`
  - 改后：`self.assertEqual(bare, unknown, "缺 last_check_state 时按待确认呈现，不写成有效")`
- 同用例内的 `expired`、`valid`、`pred_expired`、`pred_valid` 断言保持不动。

## 二、新增用例清单（均位于 `local/tests/test_phone_ui.py`）

1. `SheetsOpsModelTests.test_login_state_classifies_four_states_and_precedence`：表驱动覆盖 `PhoneModel.loginState` 的非对象/缺字段/四态判定与「无会话先于失效」顺序。
2. `SheetsOpsModelTests.test_login_copy_covers_all_fields_across_four_states`：表驱动逐字校验 `PhoneModel.loginCopy` 四态全部 8 个文案字段。
3. `SheetsOpsModelTests.test_login_line_four_states_by_setup_and_recovering`：表驱动覆盖 `PhoneModel.loginLine` 四态 × 4 种 `relogin_setup`，以及 `never` 与 `expired` 各自的自动恢复文案。
4. `SheetsOpsModelTests.test_login_done_text_switches_by_first_login_and_busy`：表驱动覆盖 `PhoneModel.loginDoneText` 两个布尔参数组合（首次登录 vs 重新登录 × 闲时 vs 计划运行中）。
5. `SheetsOpsModelTests.test_dom_never_uses_login_copy_and_unknown_hides_expired_banner`（位于 `SheetsOpsDomTests`）：校验 `unknown` 时失效横幅隐藏且登录行写「还没确认」；`never` 时横幅、底栏、更多面板入口按钮与打开重登面板标题均为「登录」口径。
6. `SheetsOpsModelTests.test_dom_first_login_keeps_title_and_done_text_across_valid_snapshot`（位于 `SheetsOpsDomTests`）：校验在 `never` 下打开重登面板后，即使轮询带来 `login=valid` 与 `login_relay.state="success"` 快照并多次 `refreshControls`，面板标题仍为「在手机上登录」且完成文案以「登录成功」开头；关掉后在 `valid` 下重开才切回「在手机上重新登录」。
