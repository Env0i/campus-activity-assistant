# 服务器直发签名报名验证记录（2026-11-24）

- **分支**：`feat/server-direct-signup`
- **基准提交**：Proposal `0cce738`，第一步拆分提交 `4428b8b` + `c97f74b`
- **日期**：2026-11-24

## 1. 两步改动与行数变化

### 第一步：仅拆结构（零行为改动）

| 模块 | 改动前行数 | 改动后行数 | 关键函数行数 | 职责 |
|---|---|---|---|---|
| `server/deploy/signup/grab_signup.py` | 819 | 198 | `main`: 21（原 66） | 入口参数解析、同目录模块引导、符号再导出与转发 |
| `server/deploy/signup/signup_policy.py` | — | 237 | `settle`: 32 | 黄金风暴 / 全速 / 404 自适应常量、`BurstPolicy`、`classify_response` |
| `server/deploy/signup/signup_io.py` | — | 131 | `send_owner_notify`: 41 | 日志、token 读写与重登、`post_json`、`check_joined`、飞书通知 |
| `server/deploy/signup/signup_loop.py` | — | 409 | `run_submit_loop`: 56（原 343） | 点击事件循环、归属结算、终态收口 |

### 第二步：直发签名、登录恢复与主动换新避让

- 新增 `server/deploy/signup/signup_signing.py`（`cryptography` AES-128-ECB + PKCS7，`SignerUnavailable`，`parse_runtime_key`）。
- 新增 `server/deploy/signup/signup_reply.py`（回包分类、`STOP_REASON_LABELS`、`direct_headers`）。
- 新增 `server/deploy/signup/signup_transport.py`（守护线程 `DirectTransport`，物理并发 ≤ 2，禁重定向）。
- 新增 `server/deploy/signup/signup_direct.py`（`runtime/profile` 取密钥、三种退回点击、直发提交主控、只读 `--rehearse`）。
- 新增 `server/deploy/signup/signup_relogin.py`（等开放 1.5s 复查 + 提交中 60s 限时单次重登 + 锁忙等待 token 变化）。
- 新增 `server/deploy/login/preempt_guard.py`（运行中 `GRAB_UNIT_PREFIX` 单元 / 20 分钟内排队场次 / 损坏清单跳过主动换新）。
- 修改 `server/deploy/login/auto_login.py`（824 → 811 行，`main` 123 → 117 行：增加 `AUTO_LOGIN_MAX_ATTEMPTS` 与 `--preempt` 避让，不阻断被动重登与 `--force`）。
- 修改 `server/requirements.txt`（增加 `cryptography>=41.0` 及用途注释）。

## 2. 对照录制与对拍结果

- **第一步对照录制**（脚本见 `design/evidence/2026-11-24/server-direct-signup/scripts/trace_submit_loop.py`）：
  - 复现命令：
    ```bash
    python design/evidence/2026-11-24/server-direct-signup/scripts/trace_submit_loop.py --repo <head_copy> --out %TEMP%/trace-head.json
    python design/evidence/2026-11-24/server-direct-signup/scripts/trace_submit_loop.py --repo <split_copy> --out %TEMP%/trace-split.json
    python design/evidence/2026-11-24/server-direct-signup/scripts/trace_submit_loop.py --compare %TEMP%/trace-head.json %TEMP%/trace-split.json
    ```
  - 结论：`TRACE MATCH: total_calls=12 matched=12`（`activity_id`、`stop_reason`、`state`、`logs`、`notify` 逐字段全等；`server/tests/test_grab_signup_retry.py` 零改动，原样通过）。
- **第二步签名对拍与标准向量**（环境：`cryptography==50.0.1`）：
  - 假密钥 `Abcdefgh12345678` + `test-activity-1` + `1767225600000` → `e32414cb4f3634022e6adfbb42f1e32ea6b79ae9d39d650ec973ab4ef9753413`（逐字节一致）。
  - 假密钥 `Abcdefgh12345678` + 40 个 `a` + `1767225600123` → 128 位十六进制散列与本机 CNG 逐字节一致。
  - FIPS-197 AES-128 标准向量 `encrypt_aes_ecb(3243f6a8885a308d313198a2e0370734, 2b7e151628aed2a6abf7158809cf4f3c)` → `3925841d02dc09fbdc118597196a0b32` 通过。

- **新增用例清单（`server/tests/test_grab_direct.py`，共 24 项，按 D2–D7 分组）**
- **最终文件行数（收尾实测）**：
  - `grab_signup.py`：`819 → 198（第一步）→ 262` 行（`main` `66 → 28` 行）
  - `signup_loop.py`：`437` 行（`run_submit_loop` `343 → 56` 行）、`signup_policy.py`：`237` 行、`signup_io.py`：`131` 行
  - `signup_signing.py`：`76` 行、`signup_reply.py`：`106` 行、`signup_transport.py`：`143` 行、`signup_direct.py`：`374` 行、`signup_relogin.py`：`115` 行
  - `preempt_guard.py`：`97` 行、`auto_login.py`：`824 → 811` 行（`main` `123 → 117` 行）

## 3. 新增用例清单（`server/tests/test_grab_direct.py`，按 D2–D7 分组）

- **D2（`SigningTests`，5 项）**：`test_two_cng_parity_vectors`、`test_fips_197_aes128_vector`、`test_parse_runtime_key_valid_and_invalid`、`test_signer_unavailable_when_backend_missing_or_fails`、`test_build_signup_hash_input_validation`。
- **D3 / D4（`DirectSignupTests`，8 项）**：`test_direct_success_and_path_line_in_card`、`test_full_stops_immediately_without_burning_attempts`、`test_downgrade_missing_key_and_signer_unavailable`、`test_downgrade_version_rekey_once_then_click`、`test_downgrade_three_consecutive_unknown_and_shared_budget`、`test_physical_concurrency_max_two_and_no_redirect`、`test_per_request_token_read_across_attempts`、`test_rehearse_fetches_key_signs_without_signup_or_notify`。
- **D5（`ReloginTests`，5 项）**：`test_pre_open_4001_recovers_after_1_5s_without_relogin`、`test_pre_open_4001_relogins_and_rekeys_when_recheck_fails`、`test_in_submit_4001_relogins_rekeys_and_continues_to_success`、`test_in_submit_4001_timeout_or_second_failure_ends_login_invalid`、`test_lock_busy_waits_for_token_change_without_spawning`。
- **D6（`PreemptGuardTests`，4 项）**：`test_active_grab_unit_skips_preempt_with_custom_prefix`、`test_watchlist_20min_boundaries_and_statuses`、`test_corrupt_or_missing_watchlist_behavior`、`test_passive_relogin_and_force_bypass_preempt_guard_and_max_attempts_env`。
- **D7（`CrossSideParityTests`，2 项）**：`test_reply_classification_parity_with_local`、`test_burst_policy_constants_parity_with_local`。

## 4. 临时副本单点变异结论（全部变红）

- **`split`（3 项）**：记账加倍（`7 failed`）、去掉 404 自适应扩窗（`3 failed`）、跳过收尾 `is_joined` 复查（`1 failed`）。
- **`signing`（3 项）**：错误 PKCS7 填充（`1 failed`）、错误加密模式 CBC（`1 failed`）、放宽密钥 `isalnum` 校验（`1 failed`）。
- **`direct`（3 项）**：放宽未知回包 3 次退回（`1 failed`）、物理并发上限改 3（`1 failed`）、演练误发 `signUp`（`1 failed`）。
- **`relogin`（3 项）**：去掉等开放 1.5s 复查延迟（`2 failed`）、放开提交中重登多次（`1 failed`）、重登后不重取密钥（`1 failed`）。
- **`preempt`（3 项）**：避让窗口改 0（`1 failed`）、忽略运行中报名单元（`1 failed`）、损坏清单照常换新（`1 failed`）。
- **`parity`（1 项）**：改动服务器端 `full` 回包文案（`1 failed`）。

## 5. 复现命令（离线）

```bash
python -m pytest server/tests -q
node server/bot/test_bot_runtime.js
node server/bot/test_handled_messages.js
node server/deploy/login/test_atomic_json.js
python tools/code_shape/check.py
python -m ruff check server
```

## 6. 返修记录（2026-11-24）

### 五处返修改动

- **R1 页面打不开也走直发**（`server/deploy/signup/grab_signup.py`）：`--dry-run` 仍要求页面加载；正式报名时详情页加载失败仅记日志，照样走直发；直发触发退回点击且页面未打开时，直接以「页面没打开，没法点击兜底」结束并写进私聊结果卡，不调用点击循环。
- **R2 重登只试一次，超时结束整个进程组**（`server/deploy/signup/signup_relogin.py`）：限时重登最大尝试改为 `1` 次；子进程以 `start_new_session=True` 独立进程组拉起，超过 60 秒用 `_kill_process_group` 结束整个进程组（含拉起的浏览器）并按失败收口；锁被占用时等 token 变化逻辑不变。
- **R3 已报名查询带网关签名，网络异常不算失效**（`server/deploy/signup/grab_signup.py`、`signup_io.py`、`signup_direct.py`）：开抢前 `is_joined`、等开放 4001 后复查、冲突回包核对、收尾核对四处 `getJoinInfo` 全部切到 `school_detail.get_join_info`；4001 复查（`recheck_not_4001`）只认明确 `code=4001` 为仍失效，网络/HTTP/解码异常不重登并继续；`--rehearse` 增打一行带签名查询回包 `code`（不打 `data`），顺便修复 `max_attempts`/截止停循环时直发跳过收尾 `is_joined_fn` 的漏洞。
- **R4 找回登录实测事实**（`docs/LOGIN.md`、`server/deploy/login/auto_login.py`）：将上一批删除的 6 步流程、20 样本 OCR 实测（95%/80%/70%、三源 20/20）、5 次/30 秒降质窗口、30 分钟冷却、仅写双文件、600 权限凭据、17.5h / 2026-10-22 10h40m 与 8h 换新、`2026-10-30 07:00` 偶发 4001 实测整理进 `docs/LOGIN.md`，`auto_login.py` 保持 `811` 行不变（`main` `117` 行）。
- **R5 补整块填充对拍样例**（`server/tests/test_grab_direct.py`）：新增 32 字节（两整块）明文 `abcdefghijklmnopqr,1767225600000` 对拍样例。

### 返修新增用例（`server/tests/test_grab_direct.py`，+10 项，共 34 项）

- **R1（`PageOpenFallbackTests`，3 项）**：`test_page_goto_timeout_still_runs_direct_and_succeeds`、`test_page_not_open_when_downgrade_needed_ends_with_reason_without_click_loop`、`test_page_open_normally_still_falls_back_to_click_loop`。
- **R2（`ReloginProcessGroupTests`，2 项）**：`test_relogin_passes_max_attempts_one_and_new_session`、`test_relogin_timeout_kills_process_group_and_returns_false`。
- **R3（`SignedJoinInfoTests`，4 项）**：`test_all_four_join_info_call_sites_send_gateway_sign_headers`、`test_recheck_only_explicit_4001_triggers_relogin_network_and_http_continue`、`test_is_joined_semantics_unchanged`、`test_rehearse_logs_signed_join_info_code_without_data`。
- **R5（`SigningTests`，1 项）**：`test_full_block_32_byte_cng_parity_vector`。

### 返修临时副本回退试验（6 项全部变红）

- `R1_revert_page_open_fail_aborts`：页面失败重新抛出 → `2 failed`（`test_page_goto_timeout_still_runs_direct_and_succeeds`、`test_page_not_open_when_downgrade_needed_ends_with_reason_without_click_loop`）。
- `R2a_revert_attempts_to_two`：限时重登尝试改回 2 次 → `1 failed`（`test_relogin_passes_max_attempts_one_and_new_session`）。
- `R2b_kill_only_child_not_pg`：超时仅 `proc.kill()` 不杀进程组 → `1 failed`（`test_relogin_timeout_kills_process_group_and_returns_false`）。
- `R3a_revert_is_joined_unsigned`：`is_joined` 改回不带签名 `_post` → `1 failed`（`test_all_four_join_info_call_sites_send_gateway_sign_headers`）。
- `R3b_recheck_treats_network_error_as_invalid`：复查网络异常返 `False` 当仍失效 → `1 failed`（`test_recheck_only_explicit_4001_triggers_relogin_network_and_http_continue`）。
- `R5_skip_padding_on_exact_block`：整块时 PKCS7 少补一块 → `1 failed`（`test_full_block_32_byte_cng_parity_vector`）。

### 返修回归结论

- `2026-11-24`：本机离线全量回归通过（`server/tests` `208 passed`、Node `46+8+6`、`code_shape`、`ruff` 零告警、`compileall` 通过、`test_grab_signup_retry.py` 未改）。
