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
