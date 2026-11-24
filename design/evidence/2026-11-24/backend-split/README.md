# 后端大文件与长函数拆分证据（2026-11-24）

## 1. 范围与基线

- **日期**：2026-11-24
- **分支与开工基线**：`refactor/backend-split` @ `99fc221`（与 `main` 一致）
- **目标**：在不改任何外部行为、协议、锁序与测试口径的前提下，先收紧 `tools/code_shape/baseline.json` 过期记录，再拆解 `local/` 后端其余超 800 行文件与超 100 行函数（`local/app.py` 与前端留待发版后另批处理），并保持 `local/tests/` 核心测试文件总数冻结为 **39 个**。

---

## 2. 五组拆分明细与代码形状前后对照

### 2.1 目标文件与长函数前后行数

| 组别 | 文件 / 函数 | 拆前行数 | 拆后行数 | 现存 >60 行函数 |
|---|---|---:|---:|---|
| `components` | `local/infrastructure/components/component_packages.py` | 1,666 | **272** | 无（`_helper` 61→45、`install` 72→26、`install_artifact` 64→40） |
| `components` | `local/application/components/advanced_component_service.py` | 503 | **450** | 无（`_run_split_assets` 101→5、`_run` 92→26） |
| `grab` | `local/grab.py` | 1,307 | **761** | 无（`main` 76→50、`cmd_login` 77→≤60、`run_cancel` 76→≤60） |
| `clock` | `local/infrastructure/clock/business_clock.py` | 875 | **636** | 无（`_accept_cluster` 72→≤60） |
| `plan` | `local/application/plan/plan_service.py` | 423 | **189** | 无（`run_plan_task` 361→38、`feed` 77→≤60） |
| `plan` | `local/signup_plan.py` | 614 | **501** | 无（`validate_plan` 117→19、`PlanCoordinator._run` 66→55） |
| `misc` | `local/infrastructure/phone/phone_http.py` | 400 | **424** | 无（`_make_handler` 261→11） |
| `misc` | `local/application/desktop/update_service.py` | 500 | **453** | 无（`run_version_download` 151→≤60） |
| `misc` | `local/application/login/login_relay_service.py` | 551 | **479** | 无（`_handle_line` 103→≤60、`begin` 85→45） |

### 2.2 各组迁出模块与职责

1. **`components`（组件包与分片资产安装）**
   - `local/infrastructure/components/component_manifest.py`（355 行）：包与资产清单校验、目录与 ZIP 只读自检、旧版识别。
   - `local/infrastructure/components/component_storage.py`（315 行）：数据目录解析、进程内/跨进程事务锁与使用租约、受管 `helper` 管道 I/O、原子 JSON、阶段目录与缓存回收。
   - `local/infrastructure/components/component_transactions.py`（288 行）：换位恢复、旧单体 `status` / `install` / `remove`。
   - `local/infrastructure/components/component_artifacts.py`（460 行）：schema2 资产缓存命中、写入、组指针解析、组提交 `commit_artifact_group`、`feature_status` 与 `invoke`。
   - `local/infrastructure/components/component_cloudflared.py`（248 行）：`cloudflared` 探测、自检、受管安装、缓存查询与移除。
   - `component_packages.py` 留作对外外观与再导出入口，支持正常包导入与发版脚本 `spec_from_file_location` 独立加载（不修改 `sys.path`），内部调用时从 `component_packages` 解析门面属性以保留全部测试替换点。
   - `local/application/components/split_asset_flow.py`（101 行）：`AdvancedComponentService._run_split_assets` 的无锁流程编排（校验、缓存查找、逐资产下载与校验）。

2. **`grab`（worker 剩余职责）**
   - `local/domain/signup/retry_window.py`（151 行）：迁入 `SUBMIT_BACKOFF_*`、`retry_anchor`、`compute_retry_window`、`attempts_allowed`、`next_submit_gap`、`known_policy_start`。
   - `local/domain/signup/signup_reply.py`（151 行）：迁入 `classify_http_response`、`decode_reply_body`、`recognizable_code`、`direct_headers`。
   - `local/domain/worker/worker_lines.py`（108 行）：迁入 `format_ts_text`、`format_retry_event`、`parse_http_date_epoch`。
   - `local/application/signup/signup_policy.py`（445 行）：迁入 `wait_before_next_submit`。
   - `local/application/worker/worker_cancel.py`（166 行）：迁入 `cancel_facts`、`cancel_joined`、`run_cmd_cancel`。
   - `local/application/worker/worker_clock.py`（109 行）：迁入 `configure_business_clock`、`business_now`、`business_bounds`、`clock_meta`、`setup_business_clock`、`wait_until`、`checkpoint_event`、`retry_event`。
   - `local/application/worker/worker_auth.py`（88 行）：迁入 `probe_list`、`fetch_runtime_key`、`probe_token`、`check_token`、`run_check`。
   - `local/application/worker/worker_runtime.py`（137 行）：迁入 `setup_console`、`read_json`、`notify`、`launch_browser`、`new_context`、`run_selftest`、`add_grab_parser`。
   - `local/grab.py` 保留命令行入口、参数解析、模块级常量/再导出，并在每次调用时从 `grab` 当前命名空间装配端口转发。

3. **`clock`（业务时钟报文与快照客户端）**
   - `local/infrastructure/clock/sntp_packet.py`（161 行）：SNTP 请求构造与响应校验（`SNTPPacketError`、`build_client_packet`、`parse_server_packet`、`classify_failure` 及相关常量）。
   - `local/infrastructure/clock/clock_client.py`（175 行）：只读端快照客户端（`ClockClient`、`ClockUnavailable`、`_elapsed_tick` 及漂移/阈值常量），调用时优先解析 `business_clock._elapsed_tick` 以兼容测试替身。
   - `local/infrastructure/clock/business_clock.py`（636 行）：保留 `BusinessClock`、`_SourceSlot`、`retry_delay_s`、`--probe` 入口与全部对外/测试符号再导出，将 `_accept_cluster` 拆出 `_maximal_consistent_groups` 与 `_select_cluster_candidate`。

4. **`plan`（报名计划监督与校验）**
   - `local/application/plan/plan_task_monitor.py`（273 行）：抽出 `TaskMonitorState`、看门狗与扩窗处理、输出行消费 `feed_worker_line`、有界清理 `cleanup_task_monitor` 与终态分类 `classify_monitored_stop`。
   - `local/application/plan/plan_service.py`（189 行）：保留 `plan_done_notice`、`run_plan_task`、两处 `with lock:`（`Api._lock`）临界区与 `_run_monitor_loop`。
   - `local/domain/plan/plan_validation.py`（153 行）：抽出 `signed_occupancy`、活动条目校验与时段冲突计算纯函数（零墙钟依赖）。
   - `local/signup_plan.py`（501 行）：`validate_plan` 委托给 `domain.plan.plan_validation.validate_plan_rows`，`PlanCoordinator._run` 抽出 `_build_done_payload`。

5. **`misc`（其余三个超百行函数）**
   - `local/infrastructure/phone/phone_http.py`（424 行）：将嵌套在 `_make_handler` 内的 HTTP 处理器提为顶层 `_HandlerDeps` 与 `PhoneRequestHandler`，`_make_handler` 仅做薄子类装配（11 行）。
   - `local/application/desktop/update_version_download.py`（105 行）：抽出版本更新包的载荷选择、节流下载与暂存辅助，`with state._lock:` 读写保留在 `update_service.py`（453 行）。
   - `local/application/login/login_relay_protocol.py`（150 行）：抽出中继行解析与事件状态更新纯逻辑，`LoginRelayService._lock` 临界区与 `_now()` 叶子端口调用保留在 `login_relay_service.py`（479 行）。

所有新建模块均 ≤ 500 行（最大 460 行），全仓新建与修改函数均 ≤ 60 行。

---

## 3. `grab` 对照录制结论

在系统临时目录导出开工基线 `99fc221` 副本与叠加本批改动的副本并逐字段比对（跑完已清理临时目录）：

- **`trace_signup.py --compare`**：开工基线 **170 次**调用 vs 搬迁后 **170 次**调用 → `exact_equal = 170`，`only_in_a = []`，`only_in_b = []`，`mismatch_count = 0`。
- **`record_io.py --compare`**：`http_cases = 9`，`clock_cases = 7`，`log_files_rotated = ["grab.log", "grab.log.1", "grab.log.2"]`，`diff_count = 0`。
- **其余命令与辅助函数扩展录制**：覆盖 `retry_anchor`、`compute_retry_window`、`attempts_allowed`、`next_submit_gap`、`wait_before_next_submit`、`_classify_response`、`_decode_body`、`_recognizable_code`、`_ts_text`、`clock_meta`、`business_now`、`business_bounds`、`_checkpoint_event`/`_retry_event`、`cmd_check`、`fetch_runtime_key`、`cmd_cancel` 共 **17 组**，`diff_count = 0`。

---

## 4. 十六条定点变异结果

每条均在系统临时目录下的独立副本中单点改坏后运行对应测试，验证完毕即删除临时副本：

| 组别 | 变异位置与写法 | 测试命令 | 结果与第一条失败用例 |
|---|---|---|---|
| `components` | `component_manifest.py::_outdated_version` 恒返回 `""` | `test_component_packages.py` | **变红**（3 失败）：`test_feature_status_reports_outdated_when_split_is_absent` |
| `components` | `component_transactions.py::_recover_replacement` 跳过 `if backup.exists():` 回滚分支 | `test_component_packages.py` | **变红**（3 失败）：`test_legacy_install_process_exit_recovery_boundaries` |
| `components` | `component_artifacts.py::find_cached_artifact` 跳过 `compatibility_id` 命中返回 | `test_component_packages.py` | **变红**（1 失败、2 报错）：`test_cache_reuses_verified_content_and_does_not_remove_other_stage` |
| `grab` | `retry_window.py::next_submit_gap` 中 `SUBMIT_BACKOFF_FACTOR` 改为 `1.0` | `test_retry_policy.py -k SubmitBackoff` | **变红**：`SubmitBackoffTests.test_backoff_sequence_is_bounded` |
| `grab` | `signup_reply.py::classify_http_response` 中 `status_code == 404` 改为 `999` | `test_worker_boundaries.py -k BurstPolicyV4Tests` | **变红**：`BurstPolicyV4Tests.test_classify_five_way_split` |
| `grab` | `worker_cancel.py::run_cmd_cancel` 退出码改为恒 `0` | `test_cancel_signup.py -k CmdCancelTests` | **变红**：`CmdCancelTests.test_non_cancelled_results_exit_nonzero_with_one_json_line` |
| `clock` | `sntp_packet.py::parse_server_packet` 跳过 `originate` 8 字节比对 | `test_business_clock.py` | **变红**：`test_same_second_different_request_rejected` |
| `clock` | `clock_client.py::ClockClient._load` 跳过 `owner_id` 归属校验 | `test_business_clock.py` | **变红**：`test_client_rejects_bad_snapshots` |
| `clock` | `business_clock.py::BusinessClock._effective_state_locked` 跳过 `age > self._holdover_max_s` 判定 | `test_business_clock.py` | **变红**：`test_holdover_expiry_becomes_unavailable` |
| `plan` | `plan_task_monitor.py::classify_monitored_stop` 置 `attempts_seen = 0; stop = {}` | `test_worker_logs.py -k StampedAttemptLineTests` | **变红**（3 失败）：`StampedAttemptLineTests` |
| `plan` | `signup_plan.py::PlanCoordinator.stop` 跳过 `event.set()` | `test_signup_plan.py -k stop` | **变红**：`'failed' != 'canceled'` |
| `plan` | `plan_validation.py::_validate_activity_item` 篡改 `sign_end_passed` 类型名 | `test_signup_plan.py -k validate_plan` | **变红**：`StopIteration` |
| `misc` | `phone_http.py::PhoneRequestHandler._check_host` 恒返回 `True` | `test_phone_infra.py` | **变红**（3 失败） |
| `misc` | `update_service.py::run_version_download` 跳过 delta 应用失败后的完整包回退 | `test_application_services.py` | **变红**（1 失败） |
| `misc` | `login_relay_service.py::LoginRelayService._handle_line` 跳过 `self._notify_success(flow)` | `test_login_relay.py` | **变红**（4 失败） |
| `guards` | `signup_plan.py::PlanCoordinator.cancel_task` 把 `self._publish("task", payload)` 放进 `with self._lock:` | `test_concurrency_guards.py` | **变红**（3 失败、16 报错）：`LockOrderTests` 捕获 `_lock`→`_emit_lock` 降级与持锁调 `emit` |

---

## 5. 并发守卫与仍超限项

- **`test_concurrency_guards.py` 改动**：**0 处**。五组拆分均把 `Api._lock`（`plan_service.py`）、`UpdateService._lock`（`update_service.py`）、`LoginRelayService._lock`（`login_relay_service.py`）、`AdvancedComponentService._lock`（`advanced_component_service.py`）和 `PlanCoordinator`（`signup_plan.py`）保留在既有的扫描模块内，锁序、重入表、叶子端口与冻结端口完全不变。`test_concurrency_guards.py` 未改动即 37/37 全过。
- **`local/` 后端仍超限项与理由**：
  - `local/app.py`（2,577 行）、`local/app.py::Api.__init__`（139 行）、`local/app.py::Api`（20 个多方法实例属性）：本批按范围不动 `local/app.py`，留待发版后 `Api` 收口批处理。
  - `local/signup_plan.py`（501 行，原 614 行）：仅超出 500 行阈值 1 行，保留 `TaskSpec` 与 `PlanCoordinator`（并发守卫固定扫描该文件）。
  - `local/application/components/advanced_component_service.py::AdvancedComponentService`（8 个属性）、`local/application/login/auto_relogin.py::AutoReloginMonitor`（8 个属性）、`local/infrastructure/clock/business_clock.py`（636 行，原 875 行）、`local/grab.py`（761 行，原 1,307 行）等处于 501–800 行乙档的存量项：均已控制在 ≤ 800 行以内，不再有 `app.py` 之外的 `>800` 行文件或 `>100` 行函数。

---

## 6. 复现命令

```powershell
# 清除代理并统一 UTF-8 输出
$env:http_proxy=$null; $env:HTTP_PROXY=$null; $env:https_proxy=$null; $env:HTTPS_PROXY=$null; $env:all_proxy=$null
$env:PYTHONIOENCODING='utf-8'

# 代码形状、静态检查、分层与并发守卫
python tools/code_shape/check.py
python -B -m ruff check local server tools
python -m compileall -q local
python -B -m unittest discover -s local/tests -p test_code_shape.py -v
python -B -m unittest discover -s local/tests -p test_layer_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_concurrency_guards.py -v

# 本机版全量回归与组件发版测试
python -B -m unittest discover -s local/tests -p "test_*.py" -v
python -B -m unittest tools/release/tests/test_lifecycle_release.py -v
```

---

## 7. 未验证项

- **真实学校网络与登录**：所有学校请求、飞书通知与组件下载均在离线替身下验证，未连真实外网。
- **真实图形窗口与浏览器**：桌面 pywebview 窗口与 Playwright 真实 Chromium/Edge 交互未在本批拉起。
- **PyInstaller 冻结打包与 `server/` 测试**：未执行冻结 EXE 打包构建；未运行 `server/tests`。
