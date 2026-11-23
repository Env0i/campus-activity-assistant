# 变异反证记录

在 `%TEMP%` 下的独立副本先确认无变异基线通过（`test_state_of_closes_at_exact_sign_end_second` 1 项 OK，`test_handoff_` 4 项 OK），随后依次注入以下三处单点变异并运行对应测试文件，三条变异均触发对应新用例失败（`exit=1`）：

1. **变异一：`stateOf` 截止判断改回 `end < bn`**
   - 位置：`local/ui/state/labels.js` `stateOf`
   - 改法：将 `end <= bn` 改回 `end < bn`
   - 首个失败用例：`test_ui_main_window.RefundAndUntilTests.test_state_of_closes_at_exact_sign_end_second`（`exit=1`，`AssertionError: {'state': 'open', 'mode': 'closed'} != {'state': 'closed', 'mode': 'closed'}`）

2. **变异二：对话框改回按当前 `attempts` 选句**
   - 位置：`local/ui/features/login/view-relogin.js` `reloginShowChallenge`
   - 改法：恢复为直接按 `payload.handoff` 与当前 `Number(payload.attempts) || 0` 选句（`times >= 3` 说「自动识别 3 次没认对，请输入验证码。」，否则说「电脑没认出这张验证码，请输入验证码。」）
   - 首个失败用例：`test_ui_reliability.SilentReloginUiTests.test_handoff_at_three_attempts_and_reopen_uses_recorded_count`（`exit=1`，`AssertionError: '自动识别 3 次没认对，请输入验证码。' != ''`；同轮亦触发 `test_handoff_reason_shown_once_and_user_retries_keep_tries_only` 失败）

3. **变异三：对话框去掉「只在转人工那一张显示」的条件**
   - 位置：`local/ui/features/login/view-relogin.js` `reloginShowChallenge`
   - 改法：保留 `handoff_attempts` 选句与非空检查，只去掉 `Number(payload.attempts || 0) === handoffAt` 条件
   - 首个失败用例：`test_ui_reliability.SilentReloginUiTests.test_handoff_at_three_attempts_and_reopen_uses_recorded_count`（`exit=1`，`AssertionError: '电脑没认出这张验证码，请输入验证码。' != ''`；同轮亦触发 `test_handoff_reason_shown_once_and_user_retries_keep_tries_only` 失败）
