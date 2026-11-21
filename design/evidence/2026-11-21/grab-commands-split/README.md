# 报名 worker 节奏状态机与命令编排拆分证据（2026-11-21）

## 1. 范围

本批只搬结构、不改行为：把 `local/grab.py`（开工时 **2,105** 行）里的提交节奏状态机 `BurstPolicy`（及 13 个节奏常量）与取消报名、查目标、登录三条命令的编排迁入 `local/application/` 下的四个新模块，`local/grab.py` 保留原有全部模块级名字与签名，只作 `BurstPolicy` 子类 / 常量再导出与调用时从 `grab` 模块全局装配端口的薄转发。

- 开工分支与基线：`refactor/api-coordinator` @ `575db6b`（`chore(aoci): 索引同步缺口补测`，开工工作区与暂存区干净）
- 开工基线全量回归（`python -B -m unittest discover -s local/tests -p "test_*.py" -v`）：`Ran 2745 tests in 215.878s` → `OK (skipped=2)`
- 核心测试文件总数保持 **39 个**；除将 `local/tests/test_worker_logs.py` 中的登录文案契约测试读取范围扩至 `local/application/worker_login.py`（并增加扫描非空断言）外，不改动任何测试。

### 开工 AST 名字清点

用 Python `ast` 扫描四块在 `local/grab.py` 内读取的模块级名字（不含函数/类自身定义与局部变量），与各测试替换落点核对一致：

| 搬迁块 | 原位置与物理行数 | 读取的 `grab` 模块级名字 / 外部边界 | 可直接由新模块导入的标准库 |
|---|---|---|---|
| `BurstPolicy` 及 13 个节奏常量 | L1376–1760（385 行） | `log`、`ClockUnavailable` + 13 个节奏常量（`GOLDEN_WINDOW_S`、`GOLDEN_INTERVAL_S`、`GOLDEN_ROUNDS`、`FULL_SPEED_INTERVAL_S`、`BACKOFF_FACTOR`、`BACKOFF_MAX_S`、`ADAPTIVE_WINDOW_S`、`SERVER_ERROR_MIN_GAP_S`、`ADAPTIVE_IN_GOLDEN`、`INFLIGHT_TTL_S`、`NOT_READY_404_LIMIT`、`NOT_READY_SLOWDOWN_AFTER_S`、`NOT_READY_SLOW_GAP_S`） | `math` |
| 取消报名 `run_cancel` | L983–1058（76 行） | `SITE_CONFIGURED`、`probe_token`、`business_now`、`_CLOCK`、`_cancel_joined`、`_cancel_facts`、`_get`、`log`、`CANCEL_PATH`、`CANCEL_PRECHECK_BUDGET_S`、`CANCEL_RECHECK_BUDGET_S`、`ClockUnavailable`、`sanitize_school_message` | `urllib.parse` |
| 查目标（`candidates`、`pick_activity`、`_by_index_or_name`、`_at_or_now`、`resolve_target`） | L1077–1112、L1163–1255（123 行） | `fetch_activities`、`business_now`、`default_now`、`parse_ts`、`still_relevant`、`school_time_text` | — |
| 登录（`page_local_storage`、`session_from_items`、`_cmd_login_relay`、`cmd_login`） | L752–901（150 行） | `ensure_data_dir`、`launch_browser`、`new_context`、`log_event`、`save_verified_files`、`check_token`、`_post`、`BASE`、`LOGIN_HASH`、`time`、`sys`（`Playwright` 与 `login_relay` 延迟导入留在 `grab.py` 调用端并经端口传入） | `datetime`、`json`、`secrets` |

---

## 2. 四个新模块职责与代码形状

| 文件 | 物理行数 | 最长函数（行数） | 职责 |
|---|---:|---|---|
| `local/grab.py` | 1,481（原 2,105） | `main`（76） | 保留全部原有模块级名字与常量；`BurstPolicy` 子类只覆盖 `_clock_error` 与调用时取 `log` 的 `_log` 钩子；`run_cancel`、`candidates`、`pick_activity`、`_by_index_or_name`、`_at_or_now`、`resolve_target`、`page_local_storage`、`session_from_items`、`_cmd_login_relay`、`cmd_login` 在调用时从模块全局装配端口后转发给 `application` |
| `local/application/signup_policy.py` | 435 | `settle`（34） | `BurstPolicy` 状态机实现与 13 个节奏常量唯一来源；告警与业务时钟无效异常经 `_log`、`_clock_error` 钩子延迟解析，不 import `grab` 或 `business_clock` |
| `local/application/worker_cancel.py` | 126 | `_check_join_and_window`（30） | `run_cancel` 编排：拆分站点/鉴权/时钟核对（`_check_auth_and_clock`）、已报与详情窗口核对（`_check_join_and_window`）、单次调取消接口与 `getJoinInfo` 复查（`_send_and_recheck`） |
| `local/application/signup_target.py` | 144 | `resolve_target`（49） | `candidates`、`pick_activity`、`by_index_or_name`、`at_or_now`、`resolve_target` 编排：候选排序、序号/名称匹配、已开放场次替换当前业务时刻与三条查目标路径 |
| `local/application/worker_login.py` | 187 | `run_login`（41） | `page_local_storage`、`session_from_items`、`run_login_relay`（含 `_RelayDeps`）与 `run_login`（拆为 `_wait_for_token` 与 `_persist_and_verify`）；`Playwright` 与 `login_relay` 延迟导入留在 `grab.py` 调用端 |

四个新模块均 ≤ 500 行（最大 435 行），所有新函数与拆出函数均 ≤ 60 行（最大 49 行），且只 import 标准库与 `domain`（`signup_policy.py` 导入 `domain.retry_window.ADAPTIVE_SECONDS`）。

---

## 3. 对照录制结论

直接运行 `design/evidence/2026-11-21/grab-signup-split/scripts/trace_signup.py`，对在 `tempfile.gettempdir()` 下解包的开工 HEAD 副本与叠加本批改动后的副本各录一遍后比对：

- 开工 HEAD 副本调用总数：**170 次**
- 搬迁后副本调用总数：**170 次**
- 逐字段完全相等数：**170 / 170**（`mismatch_count = 0`，`only_in_a = []`，`only_in_b = []`）

---

## 4. 十三条定点变异结果表

每条均在 `tempfile.gettempdir()` 下新建的搬迁后独立副本中单点改坏、运行对应测试文件，跑完即删；搬迁后未变红的条目，同步在开工 HEAD 副本的原位置做等价改动对照：

| 守的行为 | 改坏位置（文件行号）与变异写法 | 测试文件 | 搬迁后结果与第一条失败用例 | HEAD 对照结论 |
|---|---|---|---|---|
| 同一 `request_id` 重复结算被拒绝 | `local/application/signup_policy.py:364`：`if record is None or record["status"] == "settled":` → `if record is None:` | `test_worker_boundaries.py`、`test_retry_policy.py` | **未变红**（`fails=0`） | HEAD 同位置改坏同样 `fails=0`（既有测试缺口，非本批引入：`signup_ledger._settle_direct_completed` 已先拦截，且纯单测未构造同 ID 二次 `settle`） |
| 自适应扩窗不得越过 `sign_end` | `local/application/signup_policy.py:320-321`：删去 `if self.sign_end_ts: target = min(target, self.sign_end_ts)` | `test_worker_boundaries.py` | **变红**（2 处失败）：`test_worker_boundaries.BurstPolicyPureTests.test_404_extension_never_passes_sign_end` | — |
| `BurstPolicy` 告警钩子按调用时取 `grab.log` | `local/grab.py:1134-1136`：`_log` 改为类体定义时绑定 `_bound_log = staticmethod(log)` | `test_worker_boundaries.py`、`test_retry_policy.py` | **未变红**（`fails=0`） | HEAD 同样改坏在两文件同样 `fails=0`（既有测试缺口：两套用例未在替换 `grab.log` 时构造 `attempt_no` 回退场景） |
| `BurstPolicy` 时钟读数无效抛 `ClockUnavailable` | `local/grab.py:1132`：`_clock_error = ClockUnavailable` → `_clock_error = RuntimeError` | `test_worker_boundaries.py` | **变红**（7 处失败）：`test_worker_boundaries.BurstPolicyPureTests.test_wall_now_rejects_invalid_business_reading` | — |
| 取消复查只有明确 `False` 才判 `cancelled` | `local/application/worker_cancel.py:84`：`if after is False:` → `if after is not True:` | `test_cancel_signup.py` | **变红**（2 处失败）：`test_cancel_signup.RunCancelOutcomeTests.test_clock_lost_after_cancel_is_unknown` | — |
| 报名窗口外拒绝取消报名 | `local/application/worker_cancel.py:69-70`：删去 `if not (sign_start <= now <= sign_end): return _refuse(log, "window_closed")` | `test_cancel_signup.py` | **变红**（2 处失败）：`test_cancel_signup.RunCancelPrecheckTests.test_outside_sign_window_does_not_call_cancel` | — |
| 取消接口只调用一次，不重发 | `local/application/worker_cancel.py:81`：连续调用两次 `get(cancel_path + ...)` | `test_cancel_signup.py` | **变红**（8 处失败）：`test_cancel_signup.CmdCancelTests.test_unexpected_exception_after_sending_is_unknown` | — |
| `run_cancel` 每次调用从模块全局取 `probe_token` | `local/grab.py:905`：在 `probe_token` 定义后模块级绑定 `_BOUND_CANCEL_PROBE = probe_token`，`run_cancel` 传 `_BOUND_CANCEL_PROBE` | `test_cancel_signup.py` | **变红**（42 处失败）：`test_cancel_signup.RunCancelOutcomeTests.test_school_message_never_reaches_the_log` | — |
| 已开放场次把开放时刻替换成当前业务时刻 | `local/application/signup_target.py:89`：`if ts is not None and ts <= business_now():` → `if False and ...:` | `test_worker_boundaries.py`、`test_signup_plan.py` | **未变红**（`fails=0`） | HEAD 原 `_at_or_now` 同样改坏在两文件同样 `fails=0`（既有测试缺口：两套用例未喂入已过开放时刻并断言 `at` 改写为现在） |
| 三条查目标路径共用传入预算 | `local/application/signup_target.py:104`：按 ID 无 `--at` 路径改传 `fetch_activities(None)` | `test_worker_boundaries.py` | **变红**（1 处失败）：`test_worker_boundaries.ListEntryTests.test_resolve_target_three_paths_share_the_same_budget` | — |
| 登录态双文件落盘失败不得返回 0 | `local/application/worker_login.py:134`：`session_not_saved` 分支 `return 2` → `return 0` | `test_session_persistence.py` | **变红**（1 处失败）：`test_session_persistence.CmdLoginTransactionTests.test_second_file_failure_keeps_old_pair_and_reports_failure` | — |
| 登录成功文案不得再承诺有效期约 17 小时 | `local/application/worker_login.py:142`：成功提示改成带「有效期约 17 小时」 | `test_worker_logs.py` | **变红**（1 处失败）：`test_worker_logs.PureFormatterTests.test_login_success_message_no_longer_promises_a_lifetime` | — |
| 登录后接口复查失败不得返回 0 | `local/application/worker_login.py:141`：`verify_failed` 分支 `return 2` → `return 0` | `test_session_persistence.py`、`test_login_relogin.py` | **未变红**（`fails=0`） | HEAD 同分支改 `return 0` 在两文件同样 `fails=0`（既有测试缺口：现有 `CmdLoginTransactionTests` 仅覆盖复查成功路径） |

---

## 5. 全量测试与静态检查对比结论

- **开工 HEAD 基线全量**：`Ran 2745 tests in 215.878s` → `OK (skipped=2)`
- **收尾搬迁后全量**：`Ran 2745 tests in 213.470s` → `OK (skipped=2)`
- **逐用例对比**：开工与收尾均为 `exit_code=0`、共 2,745 项测试（其中解析统计的逐项状态 2,727 个 `ok` + 2 个 `skipped`，`only_in_head = []`、`only_in_closeout = []`、`status_diffs = []`），无新增失败或报错。
- **静态与代码形状检查**：
  - `python -B -m ruff check local server tools`：`All checks passed!`
  - `python tools/code_shape/check.py`：通过（文件 >800 行 10 个、501–800 行 11 个；函数 >100 行 23 个、61–100 行 68 个；测试函数 >60 行 19 个；属性超标的类 2 个）
  - `python -m compileall -q local/grab.py local/application`：退出码 0，无任何输出

---

## 6. 复现命令

以下命令在仓库根目录执行（临时目录统一使用 `%TEMP%` 或 `tempfile.gettempdir()`，跑前清掉代理环境变量）：

```powershell
# 清除代理环境变量
$env:http_proxy=$null; $env:HTTP_PROXY=$null; $env:https_proxy=$null; $env:HTTPS_PROXY=$null; $env:all_proxy=$null

# 1. 定向测试与分层/代码形状守卫
python -B -m unittest discover -s local/tests -p test_worker_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_cancel_signup.py -v
python -B -m unittest discover -s local/tests -p test_session_persistence.py -v
python -B -m unittest discover -s local/tests -p test_worker_logs.py -v
python -B -m unittest discover -s local/tests -p test_login_relay.py -v
python -B -m unittest discover -s local/tests -p test_login_relogin.py -v
python -B -m unittest discover -s local/tests -p test_retry_policy.py -v
python -B -m unittest discover -s local/tests -p test_signup_plan.py -v
python -B -m unittest discover -s local/tests -p test_layer_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_code_shape.py -v

# 2. 代码形状、Ruff 与字节码编译检查
python tools/code_shape/check.py
python -B -m ruff check local server tools
python -m compileall -q local/grab.py local/application

# 3. 本机版全量回归
python -B -m unittest discover -s local/tests -p "test_*.py" -v
```

---

## 7. 未验证项

- **真实学校网络与登录**：所有请求（`listActivity`、`getInfo`、`getJoinInfo`、`cancel`、`signUp`）均在离线替身下执行，未连学校站点，未运行真实验证码与 `--relay` 端到端登录。
- **真实图形窗口与浏览器（Playwright Chromium/Edge）**：`cmd_login` 与 `cmd_grab` 浏览器步骤均由替身验证，未拉起真实可见窗口。
- **冻结态 EXE（`grab-worker.exe`）与服务器版测试**：未执行 PyInstaller 打包、冻结子进程与 `server/` 测试。


---

## 8. 审计复核

审计方在独立临时副本（工作区改动叠加在开工提交上）复核，结论与上文一致：

- 定向测试：test_worker_boundaries、test_cancel_signup、test_session_persistence、test_worker_logs、test_login_relay、test_login_relogin、test_retry_policy、test_signup_plan、test_ui_contracts 全部通过。
- 对照录制：用 grab-signup-split 目录的录制脚本重录开工提交与搬迁后各一遍，170/170 次调用逐字段相等。
- BurstPolicy 类体与开工提交逐行比对，只多了告警与时钟异常两个钩子，其余一字未变。
- 复现上文两条既有缺口（已开放场次换成现在、登录后接口复查失败的退出码）：在开工提交原位置同样改坏，确实不红。
- 另做五条定点变异，一条变红：取消前登录态未知也放行。四条在搬迁后与开工提交的原位置上都不变红，属于既有测试缺口、不是本批引入：取消前业务时钟未配置也放行；按名称选活动命中多个时直接取第一个；可见浏览器登录时窗口被关掉仍继续等待；手机重登中继保存登录态时不写盘。连同上文四条，共八处既有缺口，留给后续补测。

---

## 9. 既有缺口补测

针对第 4 节与第 8 节识别出的八处既有测试缺口，在不改动任何产品代码、不新建测试文件的前提下，于既有同主题测试类中各补一条外部可见行为测试（夹具仅在 `test_session_persistence.py` 的 `_FakeCtx.__init__` 增加带默认值的 `page=None` 参数，默认值下所有既有测试全绿）。新用例连跑三遍全部通过；在 `tempfile.gettempdir()` 下解包的独立副本中先确认未改坏时全绿，再逐条施加定点变异，八条变异全部变红且第一条失败用例均为对应新用例：

| 守的行为 | 新用例名 | 变异写法 | 变异下第一条失败用例 | 结论 |
|---|---|---|---|---|
| 同一 `request_id` 第二次结算被拒绝，首次结论不被覆盖 | `test_worker_boundaries.BurstPolicyPureTests.test_duplicate_settle_with_different_kind_is_rejected_and_keeps_first_conclusion` | `local/application/signup_policy.py` 的 `settle` 中 `if record is None or record["status"] == "settled":` → `if record is None:` | `test_worker_boundaries.BurstPolicyPureTests.test_duplicate_settle_with_different_kind_is_rejected_and_keeps_first_conclusion` | 已守 |
| `BurstPolicy` 登记发现 `attempt_no` 未递增时经调用时读取的 `grab.log` 输出告警 | `test_worker_boundaries.BurstPolicyPureTests.test_non_monotonic_attempt_no_logs_warning_via_latest_grab_log` | `local/grab.py` 的 `BurstPolicy._log` 改为类定义时绑定 `_bound_log = staticmethod(log)` | `test_worker_boundaries.BurstPolicyPureTests.test_non_monotonic_attempt_no_logs_warning_via_latest_grab_log` | 已守 |
| 已开放场次把开放时刻替换成当前业务时间并保留原定时刻在 `original_at` | `test_worker_boundaries.ListEntryTests.test_resolve_target_replaces_past_open_time_with_now_and_keeps_original` | `local/application/signup_target.py` 的 `at_or_now` 中 `if ts is not None and ts <= business_now():` → `if False and ...:` | `test_worker_boundaries.ListEntryTests.test_resolve_target_replaces_past_open_time_with_now_and_keeps_original` | 已守 |
| 可见浏览器登录后接口复查失败返回退出码 2 并记 `verify_failed` 事件 | `test_session_persistence.CmdLoginTransactionTests.test_verify_failure_after_save_returns_two_and_logs_verify_failed` | `local/application/worker_login.py` 的 `verify_failed` 分支 `return 2` → `return 0` | `test_session_persistence.CmdLoginTransactionTests.test_verify_failure_after_save_returns_two_and_logs_verify_failed` | 已守 |
| 取消报名前业务时钟未配置（`grab._CLOCK["meta"]` 为空）时拒绝且不调接口 | `test_cancel_signup.RunCancelPrecheckTests.test_missing_clock_meta_refuses_without_calling_get` | `local/grab.py` 的 `run_cancel` 转发中 `has_clock_meta=lambda: _CLOCK.get("meta") is not None` → `has_clock_meta=lambda: True` | `test_cancel_signup.RunCancelPrecheckTests.test_missing_clock_meta_refuses_without_calling_get` | 已守 |
| 按名称关键词选活动命中多场时不选，列出序号提示改用 `--pick` 并返回 `None` | `test_worker_boundaries.ListEntryTests.test_by_index_or_name_refuses_ambiguous_keyword_and_lists_indices` | `local/application/signup_target.py` 的 `by_index_or_name` 中 `if len(hits) > 1:` → `if False and len(hits) > 1:` | `test_worker_boundaries.ListEntryTests.test_by_index_or_name_refuses_ambiguous_keyword_and_lists_indices` | 已守 |
| 可见浏览器登录时用户关掉窗口返回 1、写 `window_closed` 事件、不保存登录态 | `test_session_persistence.CmdLoginTransactionTests.test_closed_browser_window_returns_one_without_saving_session` | `local/application/worker_login.py` 的 `_wait_for_token` 中 `if page.is_closed():` → `if False and page.is_closed():` | `test_session_persistence.CmdLoginTransactionTests.test_closed_browser_window_returns_one_without_saving_session` | 已守 |
| 手机重登中继成功落盘走双文件事务保存并写入非空 `saved_at` | `test_login_relay.VerifiedFilesTests.test_cmd_login_relay_saves_verified_pair_with_fresh_saved_at` | `local/application/worker_login.py` 的 `_RelayDeps.save_verified` 中删去 `self._save_verified_files(state, session)` 调用 | `test_login_relay.VerifiedFilesTests.test_cmd_login_relay_saves_verified_pair_with_fresh_saved_at` | 已守 |

### 补测复现命令

```powershell
# 清除代理环境变量
$env:http_proxy=$null; $env:HTTP_PROXY=$null; $env:https_proxy=$null; $env:HTTPS_PROXY=$null; $env:all_proxy=$null

# 1. 单独运行八条新增缺口守卫用例
python -B -m unittest `
  local.tests.test_worker_boundaries.BurstPolicyPureTests.test_duplicate_settle_with_different_kind_is_rejected_and_keeps_first_conclusion `
  local.tests.test_worker_boundaries.BurstPolicyPureTests.test_non_monotonic_attempt_no_logs_warning_via_latest_grab_log `
  local.tests.test_worker_boundaries.ListEntryTests.test_resolve_target_replaces_past_open_time_with_now_and_keeps_original `
  local.tests.test_worker_boundaries.ListEntryTests.test_by_index_or_name_refuses_ambiguous_keyword_and_lists_indices `
  local.tests.test_cancel_signup.RunCancelPrecheckTests.test_missing_clock_meta_refuses_without_calling_get `
  local.tests.test_session_persistence.CmdLoginTransactionTests.test_verify_failure_after_save_returns_two_and_logs_verify_failed `
  local.tests.test_session_persistence.CmdLoginTransactionTests.test_closed_browser_window_returns_one_without_saving_session `
  local.tests.test_login_relay.VerifiedFilesTests.test_cmd_login_relay_saves_verified_pair_with_fresh_saved_at -v

# 2. 运行涉及的全部测试套件与代码形状守卫（临时目录使用 %TEMP% / tempfile.gettempdir()）
python -B -m unittest discover -s local/tests -p test_worker_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_cancel_signup.py -v
python -B -m unittest discover -s local/tests -p test_session_persistence.py -v
python -B -m unittest discover -s local/tests -p test_login_relay.py -v
python -B -m unittest discover -s local/tests -p test_worker_logs.py -v
python -B -m unittest discover -s local/tests -p test_retry_policy.py -v
python -B -m unittest discover -s local/tests -p test_code_shape.py -v
```
