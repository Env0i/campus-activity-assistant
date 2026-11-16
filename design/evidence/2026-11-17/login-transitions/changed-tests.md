# 旧用例变更清单

一条用例一行。类别只有两种：「期望不变·喂字段」是给载荷补上真实后端在那一刻会带的 `auto_state` 或 `login_auto`，断言与开工 HEAD 相同；「按画板改样子」是用户可见结果按新阶段改了，依据列写明规则。表外旧用例一个字不改。

后端字段的口径：每次 check 载荷都带 `auto_state`（结论不是失效又没有一场在跑时是 `idle`，电脑自己那一场还在进行时是 `running`）；中继结束或转人工后后端一秒内推 `login_auto`（`backoff` 或 `handoff`）。

| 文件与用例 | 开工 HEAD 的输入与断言 | 现在的输入与断言 | 类别 | 依据 |
|---|---|---|---|---|
| `test_ui_reliability.py::SilentReloginUiTests.test_expired_check_stays_silent_until_the_relogin_finishes` | 失效 check 带 `recovering: true`；断言自动登录中…、pending、无失效横幅，有效后不是失效 | 失效 check 改带 `auto_state: "running"`；断言不变 | 期望不变·喂字段 | 后端 `auto_state` 是自动登录态唯一来源 |
| `test_ui_reliability.py::SilentReloginUiTests.test_first_silent_failure_puts_the_reminder_back` | 先 `recovering: true`，再 `recovering: false, recover_block: "retry_pending"`；断言先自动登录中…，后登录已失效、bad、失效横幅、auto 为假 | 先 `auto_state: "running"`，再 `auto_state: "backoff", auto_retry_in_s: 60`；断言不变 | 期望不变·喂字段 | 静默失败后后端给 backoff；稍后重试阶段的字仍是登录已失效、view.state 仍是 bad |
| `test_ui_reliability.py::SilentReloginUiTests.test_handoff_restores_the_reminder_and_asks_for_the_captcha` | `recovering: true` 后中继转人工快照；断言字为登录已失效、bad、横幅含登录已失效，auto 为假，不另开一场 | `auto_state: "running"` 后加 `login_auto` 推 `handoff`，再中继转人工快照；断言字为要你输验证码、bad、横幅含输入验证码，其余不变 | 按画板改样子 | 转人工进新阶段 needs_code（要你输验证码）及其横幅 |
| `test_ui_reliability.py::SilentReloginResidualTests.test_closing_the_dialog_keeps_the_computers_own_auto_login` | 失效 check 带 `recovering: true`；断言关对话框不取消、仍自动登录中… | 改带 `auto_state: "running"`；断言不变 | 期望不变·喂字段 | 同上 |
| `test_ui_reliability.py::SilentReloginResidualTests.test_closing_after_the_auto_flow_handed_off_still_cancels` | 失效 check 带 `recovering: true`；断言转人工后关对话框照旧取消 | 改带 `auto_state: "running"`；断言不变 | 期望不变·喂字段 | 同上 |
| `test_ui_reliability.py::SilentReloginResidualTests.test_pill_leaves_auto_login_when_a_valid_check_arrives` | 失效 check 带 `recovering: true`，再有效 check；断言 auto 为假、已登录、ok | 改带 `auto_state: "running"`；断言不变 | 期望不变·喂字段 | 同上 |
| `test_ui_reliability.py::SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_check_cannot_reach_the_school` | `recovering: true` 后一次 unknown check；断言 auto 为假、字不是自动登录中… | 第一次改带 `auto_state: "running"`，unknown check 加 `auto_state: "idle"`；断言不变 | 期望不变·喂字段 | 后端的 check 载荷总带 `auto_state`，没有一场在跑时是 idle |
| `test_ui_reliability.py::SilentReloginResidualTests.test_a_live_auto_flow_survives_an_unknown_check` | `recovering: true`、电脑那一场在跑，再 unknown check；断言 auto 为真 | 第一次改带 `auto_state: "running"`，unknown check 加 `auto_state: "running"`；断言不变 | 期望不变·喂字段 | 电脑那一场还在进行时后端给 running |
| `test_ui_reliability.py::SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_refresh_check_fails_outright` | `recovering: true` 后刷新里 check 抛错、再被回绝；断言两次都落 unknown、auto 为假、字不是自动登录中… | 第一次改带 `auto_state: "running"`；断言两次都落 unknown、auto 为真、字为自动登录中…；随后加 `login_auto` 推 `idle`，断言 auto 为假、字不是自动登录中…；说明改为前端自判不改后端给的态、后端推 idle 就收回 | 按画板改样子 | 「没带自动登录字段就保持上一次」：抛错和回绝是前端自己判的 unknown，没有后端字段；补了收回断言守住不会一直停着 |
| `test_ui_reliability.py::SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_check_times_out` | `recovering: true` 后 check 超过 100 秒；断言落 unknown、auto 为假、字不是自动登录中… | 第一次改带 `auto_state: "running"`；断言落 unknown、auto 为真、字为自动登录中…；随后加 `login_auto` 推 `idle`，断言 auto 为假、字不是自动登录中…；说明同上 | 按画板改样子 | 同上：超时是前端自己判的 unknown；补了收回断言 |
| `test_ui_reliability.py::SilentReloginResidualTests.test_pill_leaves_auto_login_when_the_relay_finishes_or_hands_off` | `recovering: true` 后中继 failed，再 `recovering: true` 后中继转人工；断言 failed 后 auto 为假、登录已失效，转人工后 auto 为假、登录已失效 | 两处 check 改带 `auto_state: "running"`；failed 后加 `login_auto` 推 `backoff`、`auto_retry_in_s: 60`，断言 auto 为假、登录已失效，新增副句为 1 分钟后再试；转人工后加 `login_auto` 推 `handoff`，断言 auto 为假、字为要你输验证码 | 中继失败一段期望不变·喂字段；转人工一段按画板改样子 | 中继结束或转人工后后端推 `login_auto`；转人工进 needs_code，失败后进 retry_later |
| `test_ui_exit_paths_login.py::LoginHandoffExitTests.test_L11_valid_check_clears_handoff_so_auto_login_can_return` | 有效后再失效 check 带 `recovering: true`；断言 handoff 清掉、自动登录亮回、自动登录中… | 改带 `auto_state: "running"`；断言不变 | 期望不变·喂字段 | 后端 `auto_state` 是自动登录态唯一来源 |
| `test_ui_exit_paths_login.py::LoginHandoffExitTests.test_L12_finished_relay_clears_handoff_so_auto_login_can_return` | 中继 live=false 后失效 check 带 `recovering: true`；断言同上 | 改带 `auto_state: "running"`；断言不变 | 期望不变·喂字段 | 同上 |
| `test_ui_login_capsule.py::LoginCapsuleEdgeTests.test_handoff_retracts_the_auto_login_state` | 置 `S.autoLogin`、handoff 后调 `reconcileAutoLogin()`；断言 auto 为假、字不是自动登录中… | 改为 `login_auto` 推 `handoff`；断言不变 | 期望不变·喂字段 | `reconcileAutoLogin` 已删，收回改由后端推的 handoff 驱动 |
| `test_login_machine.py::LoginMachineTests.test_phase_and_view_state_lists_are_frozen` | 断言阶段清单为 11 项 | 断言阶段清单为 14 项（加 rechecking、needs_code、retry_later），view.state 清单不变 | 按画板改样子 | 登录结论转移表新增三阶段，不增 view.state 取值 |
| `test_login_machine.py::LoginMachineTests.test_every_phase_maps_to_a_listed_view_state` | 11 组事实，断言覆盖 11 阶段及其 view.state 映射 | 加三组事实（确认中、转人工、backoff 有剩余），断言覆盖 14 阶段，新增映射 rechecking→checking、needs_code→bad、retry_later→bad | 按画板改样子 | 同上 |

另外去掉了 `test_ui_exit_paths_login.py` L11、L12 与 `test_ui_reliability.py` 转人工那条在 JS 片段里多出来的行首空格，输入与断言不变。
