# 桌面两处小缺陷变更用例清单

## 一、改过的旧断言

没有改动任何既有旧断言（`test_ui_main_window.py`、`test_ui_reliability.py`、`test_ui_contracts.py`、`test_ui_plan.py` 与本机全量套件在修改后均无既有断言失败）。

## 二、新增用例

### 1. 列表截止边界（`local/tests/test_ui_main_window.py`）

- `test_ui_main_window.RefundAndUntilTests.test_state_of_closes_at_exact_sign_end_second`
  - 业务时钟恰好等于 `sign_end` 时，`stateOf` 与 `modeOf` 均返回 `"closed"`；早 1 秒时，`stateOf` 返回 `"open"`、`modeOf` 返回 `"instant_signup"`。

### 2. 转人工原因只显示一次（`local/tests/test_ui_reliability.py`）

- `test_ui_reliability.SilentReloginUiTests.test_handoff_reason_shown_once_and_user_retries_keep_tries_only`
  - 识别结果不合规转人工（`attempts: 1`）时，对话框显示「电脑没认出这张验证码，请输入验证码。」与「已经试过 1 次，换了一张新图。」；随后用户输错两次产生 `attempts: 2`、`attempts: 3` 的新验证码（`handoff` 仍为真）时，`#rl-err` 为空且隐藏，不再显示任何转人工原因，只更新已试次数；运行记录只保留一条转人工提示。
- `test_ui_reliability.SilentReloginUiTests.test_handoff_at_three_attempts_and_reopen_uses_recorded_count`
  - 转人工在 `attempts: 1` 发生、直到 `attempts: 3` 才打开对话框时，对话框仍按 `receiveReloginState` 记下的次数处理，不按当前 `attempts: 3` 重新推断出「自动识别 3 次没认对」；新一场认满 3 次转人工（`attempts: 3`）时，对话框显示「自动识别 3 次没认对，请输入验证码。」，运行记录对应记一条 3 次提示。
