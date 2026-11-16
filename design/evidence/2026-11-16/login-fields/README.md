# 登录字段后端补齐证据

## 变更口径

- `local/domain/login_rules.py` 增加冻结的 `AUTO_LOGIN_STATES` 和纯函数 `auto_login_state`。六态顺序先判断用户自己正在进行的中继，再判断电脑发起的转人工或进行中，随后判断有效、不可自动登录、退避和可继续发起。`auto_block` 只在 `blocked` 时出现，`auto_retry_in_s` 只在 `backoff` 时出现。
- `local/application/auto_relogin.py` 的 `view` 在锁内只复制调度字段，锁外读取中继快照和自动登录能力判据。`notify_if_changed` 用退避截止时刻做签名，因此倒计时每秒减少不会重复推送，进入下一轮退避仍会推送。
- `local/app.py` 的 `check`、`bootstrap.login` 带三个新字段。`login_auto` 由调度器只在状态、阻断原因或退避截止时刻变化时推送。原有 `recovering`、`recover_block` 等字段保留。
- `app.py` 仍为 4873 行，构造器参数放在原有末行，两个新增载荷各占一行，并把两段两行注释各压为一行。`tick` 未改。

## 变异结论

脚本在每条变异使用独立临时仓库副本，按文件、函数和目标行文字定位，不修改工作区产品文件。十五条变异均使对应的新用例失败。

| 变异 | 第一条失败用例 |
|---|---|
| manual-priority | `test_manual_live_flow_has_priority_over_expired` |
| handoff-mode-guard | `test_handoff_has_priority_over_inflight` |
| handoff-needs-live | `test_scheduler_handoff_flag_alone_is_backoff_when_relay_not_live` |
| valid-not-idle | `test_idle_when_session_is_valid_even_if_not_ready` |
| blocked-reason | `test_blocked_copies_reason_and_only_exposes_block` |
| backoff-zero | `test_backoff_needs_positive_retry_and_running_when_due` |
| countdown-fixed | `test_view_reports_backoff_and_decrements_remaining_seconds` |
| expired-override | `test_expired_argument_overrides_internal_flag` |
| ready-on-valid | `test_ready_is_only_called_for_expired_view` |
| countdown-signature | `test_notify_changes_once_per_state_not_per_countdown` |
| deadline-signature | `test_second_backoff_deadline_is_a_new_change` |
| run-notify | `test_run_notifies_after_each_tick` |
| check-field | `test_check_exposes_running_fields_and_keeps_legacy_recovering` |
| bootstrap-field | `test_bootstrap_login_exposes_auto_fields` |
| change-callback | `test_monitor_constructor_receives_callbacks_and_event_is_emitted` |

改了 `login_rules.py` 的 handoff 分支以后，「用户自己那一场」（中继在进行且发起方不是 auto）与「转人工」（中继在进行且发起方是 auto）两个分支互不重叠，二者对调成为等价变异。

## 验证记录

- 新规则、调度器、Api 用例通过，分别为 7、30、19 条。单实例回归 32 条通过。
- `tools/code_shape/check.py`、`test_code_shape.py`、`test_layer_boundaries.py`、`ruff check local server tools` 通过。`local/app.py` 行数为 4873。
- 本机版全量运行 2923 条，5 条跳过。现有 `test_release_guards.WorkflowCommandTests.test_syntax_check_command_fails_on_bad_script` 在 Windows 本机因 Node 的非 UTF-8 诊断输出触发测试自身的 `None` 拼接错误，单测独立复跑得到同样结果，未修改该测试。

## 复跑命令

```text
python -B design/evidence/2026-11-16/login-fields/scripts/mutate_fields.py
python -B -m unittest discover -s local/tests -p test_auto_login_rules.py -v
python -B -m unittest discover -s local/tests -p test_auto_relogin.py -v
python -B -m unittest discover -s local/tests -p test_silent_relogin.py -v
python -B -m unittest discover -s local/tests -p test_single_instance.py -v
python -B tools/code_shape/check.py
ruff check local server tools
python -B -m unittest discover -s local/tests -p "test_*.py" -v
```
