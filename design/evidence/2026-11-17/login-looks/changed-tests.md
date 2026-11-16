# 按样子改写的旧用例

隔离副本只替换本批允许的样子，输入保持原样。试跑登录相关旧用例时只有下面两条变红，其他旧用例没有变红。

| 用例 | 原来的输入与断言 | 改后的断言 | 依据 |
|---|---|---|---|
| `local/tests/test_login_machine.py` `LoginMachineTests.test_each_phase_keeps_its_visible_appearance` | `autoLogin=true` 期望 `pill is-busy`；`result="unknown", ok=false, present=true` 期望 `pill is-none` | 输入不变；自动登录中期望 `pill is-busy is-spin`；待确认期望 `pill is-warn` | L2 |
| `local/tests/test_login_transitions.py` `LoginTransitionTests.test_rechecking_keeps_green_capsule_and_blocks_start` | `S.login.checking=true` 且有效结论，期望胶囊 `className="pill is-ok"` | 输入与其余断言不变，期望 `className="pill is-ok is-spin"` | L2 |

隔离副本试跑的 `test_ui_login_capsule.py`、登录契约、Shell 契约和可靠性用例均未变红。没有表外旧用例需要改写。
