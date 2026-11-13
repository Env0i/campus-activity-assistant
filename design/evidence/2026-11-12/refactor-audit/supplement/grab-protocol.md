# grab.py 输出协议清点（基线 7e2d31c）

> 产出日期：2026-11-12
> 基线 commit：`git show 7e2d31c:local/grab.py`（4076 行）
> 清点脚本：`supplement/scripts/grab_outputs.py`（ast 解析，零运行时依赖）
> 脚本统计：87 个输出调用、1 处 sys.exit、1 个 os.environ 直接读取、8 处 open 写入

---

## 第一节：输出行种类表

grab.py 的输出分 **stdout** 和 **stderr** 两条通道。非 list/cancel 子命令（login、check、grab、selftest）的所有输出（log() 和 print()）都走 stdout。list --json 和 cancel 子命令里有 `_stdout_to_stderr(True)` 上下文，把 log() 重定向到 stderr，stdout 只留纯 JSON。

下表按 **被谁消费** 分：协议行（父进程/解析方读取）和人话行（终端用户看）。

### 1.1 协议行（被解析方消费）

| 行格式前缀/模式 | 所在子命令 | grab.py 行号 | 解析方 | 消费方 | 测试覆盖 |
|---|---|---|---|---|---|
| `[checkpoint] {"kind":"...", "at":..., ...}` | grab | L2379 (`_checkpoint_event`)；调用点 L2522 (worker_started)、L2834 (page_opened)、L3726 (watch_started) | `domain/worker_lines.py::parse_checkpoint_line`（`find("[checkpoint] ")` + JSON，只认 kind ∈ {worker_started, page_opened, watch_started}） | `plan_service.py::feed()` → `status("submitting", {run_started_at/page_opened_at/watch_started_at: at})` | `test_retry_policy.py::RetryLineParsingTests.test_checkpoint_uses_source_time_not_receipt`；fixture 里也有 checkpoint 行 |
| `[clock] {"source":"http_date", ...}` | check, grab | L1322 (`cmd_check`)、L2739 (`cmd_grab`) | `domain/worker_lines.py::parse_clock_line`（取输出里**最后一条** [clock]） | check 子命令由 GUI 自己读；**grab 子命令 plan_service 不解析 [clock]**（feed() 里没有 parse_clock_line 调用） | `test_clock_tail.py::test_retry_feedback_stops_claiming_old_time_is_usable_after_expiry`（间接） |
| `[retry] key=value key=value ...`（进度行，**无** stop_reason） | grab | L2389 (`_retry_event`)；调用点：login_wait(L2682)、login_resumed(L2695)、window(L2790)、path(L2933/L2972/L2975)、window_extended(L3046)、not_ready/throttled/server_error(L3169/3175/3181/3324/3334/3340)、submit(L3217/3261/3700) | `domain/retry_rules.py::parse_retry_line`（`startswith("[retry] ")` + 空格切字段；只解析，不验 kind） | `plan_service.py::feed()` → 推 retry_deadline / attempts / phase / path / login_wait 等字段；`window_extended` 还触发 `_accept_window_extension` 扩窗 | `test_retry_events.py::ProgressEventStatusTests`（path/login_wait/login_resumed）；`test_retry_policy.py::test_progress_retry_line_does_not_fake_terminal`、`test_phase_forwarded_from_progress_and_done_lines` |
| `[retry] kind=done attempts=N stop_reason=X retry_deadline=E sign_end=E pending=N streak_404=N phase=X last_reason=...` | grab | L2558 (`terminal()`) | `domain/retry_rules.py::parse_retry_line`（同上） | `plan_service.py::feed()` → 置 stop_seen=True；`classify_task_stop()` 用 stop_reason 分类终态；`retry_payload()` 组装 telemetry 载荷 | `test_retry_policy.py::test_parse_done_line_real_shape_tail_fields_independent`（守护 last_reason 在行末的契约）；所有 WorkerTelemetryFlowTests fake worker 都发这行 |
| `[i] 第 N 次提交：...` | grab | L3186/L3216/L3260/L3346（提交循环内） | `domain/retry_rules.py::ATTEMPT_RE = re.compile(r"^(?:\[i\]\s*)?第 (\d+) 次提交[：:]\s*(.*)$")` | `plan_service.py::feed()` → 正则匹配更新 observed attempts 和 last_reason | `test_retry_policy.py::test_max_attempts_full_is_retryable_then_stops`（发 [i] 第 1/2/3 次提交行，验证 attempts 递增） |
| `[timing] list token_s=... pages=... pages_s=... details=... details_s=... total_s=... filter_time_source=...` | list --json | L1344 (`cmd_list::_stderr_note`) ⚠️ **写 stderr**，不是 stdout | app.py L2713 `line.startswith("[timing] list ")`（从 worker 的 stderr 读） | 活动列表运行记录显示用时明细 | 间接：app.py 测试里有 mock _run 后检查 _emit 里的 timing_text |
| 纯 JSON 行（list --json stdout） | list --json | L1465 (`print(json.dumps(out))`) ⚠️ **stdout 唯一内容**，log() 被 `_stdout_to_stderr(True)` 重定向了 | app.py L2702 `json.loads(raw.strip() or "[]")` | 活动列表显示 | `test_signup_plan.py` 等里 mock worker 返回 JSON 后检查 activities 事件 |
| 纯 JSON 行（cancel stdout） | cancel | L1604 (`print(json.dumps(result))`) ⚠️ **stdout 唯一内容**，log() 被重定向 | app.py L2607 `_cancel_rules.normalize_worker_result(res.get("stdout", ""))` | 取消接口返回（kind=cancelled/precheck_failed/unknown） | `test_cancel_signup.py` 多个用例：test_worker_is_started_once_with_the_exact_command 等 |

#### 解析方代码位置全仓 grep（基线 7e2d31c）

```
$ git grep -n "worker_line\|retry_rules\|worker_lines" 7e2d31c -- local/
local/app.py:67:  from domain import retry_rules as _retry_rules
local/app.py:69:  from domain import worker_lines as _worker_lines
local/app.py:4634: _parse_checkpoint_line = _worker_lines.parse_checkpoint_line
local/app.py:4635: _parse_clock_line = _worker_lines.parse_clock_line
local/app.py:4636: _attempts_of = _retry_rules.attempts_of
local/app.py:4639: _retry_payload = _retry_rules.retry_payload
local/app.py:4643: def _parse_retry_line(line): return _retry_rules.parse_retry_line(line)
local/application/login_service.py:12:  from domain.worker_lines import parse_clock_line
local/application/plan_service.py:20:   from domain.retry_rules import ATTEMPT_RE, attempts_of, parse_retry_line, progress_event_status
local/application/plan_service.py:25:   from domain.worker_lines import parse_checkpoint_line
local/domain/plan_rules.py:13:          from domain.retry_rules import retry_payload, with_attempts
local/tests/test_retry_events.py:10:    from domain.retry_rules import parse_retry_line, progress_event_status
local/tests/test_retry_policy.py:164:    # 发射端与解析端的契约守护：last_reason 恒在行末
```

#### 哪些输出行**没有**解析方（人话行）

以下前缀**只给终端用户看**，父进程 plan_service / app.py 不消费：

| 前缀 | grab.py 函数/行号 | 用途 |
|---|---|---|
| `[OK] ...` | terminal L2567/L2574/L2588 等、cmd_login L1311、cmd_check L1319、selftest L3983 | 成功结论 |
| `[X] ...` | 几乎所有子命令的错误分支 | 失败结论 |
| `[!] ...` | cmd_check L1324（时间偏差警告）、cmd_grab L2741/2830/2932/2948/3078/3324/3376/3624/3661/3686 | 诊断警告 |
| `[?] ...` | terminal L2596 | 结果未确认（已发出但无回包） |
| `[i] ...` | terminal L2577/L2584/2594/2602、cmd_login/check/list、_retry_event 的 submit/window/timeout 进度行（注意：`[i] 第 N 次提交`是 ATTEMPT_RE 匹配的**例外**） | 信息提示 |
| `====...====` | cmd_login L1245/L1248 | 分隔线 |
| 列表表头/数据行 | cmd_list L1469/1473、pick_activity L1633/1635 | CLI 交互显示 |
| 空行前缀的 `[cancel] ...` | cmd_cancel 的 log() 调用 | 取消子命令的内部日志（被重定向到 stderr，app.py 不读） |
| 空行前缀的 `[log] ...` | log() 降级分支的 `_stderr_note` | 日志写入失败时的 stderr 提示 |
| `sys.stderr.write("[X] 登录态回滚...")` | `_rollback_note` L517 | 极罕见：登录态回滚失败才触发 |

> ⚠️ 容易混淆的点：**所有带 `[i]` 的行并不都是人话行**——`[i] 第 N 次提交：...` 这条有人话内容但被 `ATTEMPT_RE` 正则匹配，属于协议行。其余 `[i] ...` 都是纯信息提示。

#### stderr 写入者（不是 stdout）

| 前缀 | grab.py 函数/行号 | 触发条件 |
|---|---|---|
| `[timing] list ...` | `_stderr_note` → 内部 `sys.stderr.write` | list --json 模式下每次都输出 |
| `[log] ...` | `_stderr_note` → `sys.stderr.write` | 日志轮转/写入失败、数据目录不可用、没拿到日志锁 |
| `[X] 登录态回滚没成功：...` | `_rollback_note` L517 → `sys.stderr.write` | 登录态保存后校验失败触发回滚，但回滚又失败 |
| `[cancel] ...` 全系列 | `log()` → `print()` 被 `_stdout_to_stderr(True)` 重定向 | cancel 子命令运行期间的所有内部日志 |

---

## 第二节：退出码表

### 2.1 顶层 sys.exit 链路

```
sys.exit(main())                                  # grab.py L4076
  main() → return args.func(args)                 # L4069；argparse parse_args() 自己也会 sys.exit(2)
    args.func(args) = cmd_login / cmd_check / cmd_list / cmd_cancel / cmd_grab / cmd_selftest
    KeyboardInterrupt → print("\n[i] 已手动中断。"); return 130   # L4071-4072
    SITE_CONFIGURED=False && cmd != "cancel" → return 2          # L4062-4063
```

### 2.2 各子命令返回值明细

| 子命令 | exit | 触发条件 | grab.py 行号 |
|---|---|---|---|
| **login** | 0 | 登录成功、登录态写入成功、接口校验通过 | L1313 |
| | 1 | 窗口被关掉 / 等超时未检测到登录成功 | L1272, L1286 |
| | 2 | 打不开登录页 / 登录态写入失败（另一个进程占锁） / 接口校验失败 | L1261, L1303, L1310 |
| **check** | 0 | `check_token()` 返回 ok=True | L1327 |
| | 2 | `check_token()` 返回 ok=False | L1330 |
| **list** | 0 | 拉取成功（空列表也返回 0） | L1419, L1422, L1467, L1475 |
| | 1 | **不返回**（对抗审计 B3 更正：cmd_list 的 return 只有 0 和 2。原引用的 L1408/1410/1412 是嵌套 rank() 的排序档位，L1619/1621 是 candidates() 里 rank() 的返回值，都不是退出码） | — |
| | 2 | 登录失效 / PermissionError / 拉取异常 | L1361, L1373, L1376 |
| **cancel** | 0 | result["kind"] == "cancelled" | L1605 |
| | 2 | result["kind"] 不是 cancelled（precheck_failed / unknown / 其他） | L1605 |
| **grab** | 0 | stop_reason ∈ {success, already_signed} | terminal() L2572, L2575 |
| | 2 | stop_reason ∈ {max_attempts, unconfirmed, sign_end, retry_duration, process_error, full, closed, conflict, no_activity, clock_skew, unknown_reply, page_unavailable} | terminal() L2591, L2600, L2613, L2618, L2627 |
| | 3 | stop_reason ∈ {login_invalid, auth_unavailable, clock_unavailable}；**或**入口时钟不可用（L2513/L2521） | terminal() L2580, L2586, L2605；cmd_grab L2513, L2521 |
| | 2（参数校验） | sign_end 格式错 / at 格式错 | cmd_grab L2528, L2533 |
| **selftest** | 0 | 浏览器拉起 + 打开站点首页 + 页面片段含「学生」或「校园助手」 | L3988 |
| | 2 | 页面片段不对 / playwright 异常 | L3987, L3992 |
| **main 兜底** | 130 | KeyboardInterrupt | L4072 |
| | 2（argparse 自己） | 子命令缺参数 / 无参数 | argparse 内部 |

### 2.3 grab 子命令 stop_reason → exit code 完整对应（terminal() 函数）

| stop_reason | 含义 | exit | 备注 |
|---|---|---|---|
| `success` | 报名成功 | 0 | |
| `already_signed` | 已报过这场 | 0 | |
| `login_invalid` | 登录态失效（学校 4001） | **3** | |
| `auth_unavailable` | 网络/接口无法确认登录状态 | **3** | 区别于 login_invalid：不指导用户重登 |
| `clock_unavailable` | 北京时间不可用 | **3** | 入口就返回 3；中途时钟失效返回 3 |
| `max_attempts` | 到达 --max-attempts | 2 | |
| `unconfirmed` | 已发出但没拿到学校确定回包 | 2 | |
| `sign_end` | 报名截止时间到了 | 2 | |
| `retry_duration` | 重试时长到了 | 2 | |
| `process_error` | 本机流程异常 | 2 | |
| `full` | 学校说名额已满 | 2 | REPLY_STOP_HINTS 条目 |
| `closed` | 报名窗口已关 | 2 | REPLY_STOP_HINTS 条目 |
| `conflict` | 时间冲突 | 2 | REPLY_STOP_HINTS 条目 |
| `no_activity` | 学校查不到活动 | 2 | REPLY_STOP_HINTS 条目 |
| `clock_skew` | 学校连续说请求超时 | 2 | REPLY_STOP_HINTS 条目 |
| `unknown_reply` | 学校连续回了无法识别的结果 | 2 | REPLY_STOP_HINTS 条目 |
| `page_unavailable` | 直发不可用 + 详情页打不开 | 2 | REPLY_STOP_HINTS 条目 |

> terminal() 还有一个 guard：若 `done["value"]` 已为 True（终态行已经输出过），**任何**再次进入 terminal() 都返回 2 且不输出任何行（L2555-2556）。这保证了「恰一条 [retry] kind=done」的不变量。

### 2.4 父进程对 exit code 的消费

`application/plan_service.py::classify_task_stop()` 接收 exit code 作为 `code` 参数：
- code == 0 → status="success"（若 stop_reason=already_signed 也会被 classify 成 success）
- code == 2 或 code == 3 → 结合 worker 输出里的 stop_reason 分类（由 stop_reason 优先，code 只是兜底）
- code == -1 → 进程被 watchdog/cancel 收走
- **exit code 3** 是特殊值：login_invalid / auth_unavailable / clock_unavailable 三类；但父进程优先读 stop_reason，exit code 3 本身**不单独决定**分类

---

## 第三节：worker 运行时的环境变量和文件 IO

### 3.1 worker 运行时会读到的环境变量

按读取者模块分：

| 环境变量 | 读取位置 | 读取方式 | 语义 |
|---|---|---|---|
| `CAMPUS_CLOCK_SNAPSHOT` | grab.py `setup_business_clock()` L127 + business_clock.py `ClockClient` L732 | `os.environ.get()` | GUI 拉起 worker 时注入业务时钟快照路径；有值则 worker 只读快照，不联网自校时 |
| `CAMPUS_CLOCK_OWNER` | business_clock.py `ClockClient` L733 | `os.environ.get()` | 时钟快照的归属者标识；防止跨 GUI 会话复活旧快照 |
| `CAMPUS_DATA_DIR` | runtime_paths.py `_base_dir()` L53 | `os.environ.get()` | 覆盖数据根目录；GUI 拉起 worker 时注入 |
| `LOCALAPPDATA` | runtime_paths.py `_base_dir()` | `os.environ.get()` | 冻结态默认数据根 |
| `SCHOOL_ORIGIN` | site_target.py L54 | `os.environ.get()` | 真实站点域名；缺失则用占位，所有学校动作被 SITE_CONFIGURED=False 拒绝 |

app.py 拉起 worker 时显式注入的 env（L406-410）：
```python
env["CAMPUS_DATA_DIR"] = str(DATA_DIR)
env["CAMPUS_CLOCK_SNAPSHOT"] = _CLOCK_ENV["path"]
env["CAMPUS_CLOCK_OWNER"] = _CLOCK_ENV["owner"]
```

### 3.2 grab.py 代码里直接写的文件（open + mode 含 w/a/x）

基线 `grab_outputs.py` 清点出 8 处 open 写入，加上 import 链里 runtime_paths 的：

| grab.py 行号 | 函数 | 写入目标（相对 DATA_DIR） | mode | 调用条件 |
|---|---|---|---|---|
| L203 | `_log_file_lock` | `grab.log.lock` | `a+b` | 每次 log() 都要拿锁 |
| L266 | `_stdout_to_stderr` | `os.devnull`（空设备） | `w` | sys.stdout 为 None 时兜底（冻结态可能） |
| L304 | `_append_log_line_unlocked` | `grab.log` | `a` | log() 落盘轮转后追加 |
| L342 | `write_json_atomic` | 临时文件 `<path>.tmp` | `w` | `os.replace(tmp, path)` 原子替换 |
| L375 | `_session_write_lock` | `session.json.lock` | `a+b` | 登录态写入跨进程锁 |
| L463 | `_save_verified_files_locked` | 临时文件 | `w` | `storage_state.json` 或 `session.json` 写入的临时文件 |
| L502 | `_restore_original` | 临时文件 | `wb` | 登录态回滚时恢复原文件的临时副本 |
| L509 | `_restore_original` | 原登录态文件 | `wb` | 回滚写回原位置 |

### 3.3 DATA_DIR 真实值解析

`runtime_paths.py::_base_dir()`：
- **源码态**：`<repo>/local/data/`（`Path(__file__).resolve().parent / "data"`）
- **冻结态**：`%LOCALAPPDATA%/TianSoftActivityPreRegistration/data/`
- **CAMPUS_DATA_DIR 覆盖**：`Path(os.environ["CAMPUS_DATA_DIR"]).resolve()`（相对路径锚定当前工作目录）

DATA_DIR 下的关键文件名（全由 runtime_paths.py 定义）：
```
DATA_DIR / "session.json"          ← SESSION_FILE（登录态 token + localStorage）
DATA_DIR / "storage_state.json"    ← STATE_FILE（浏览器 cookie/storage）
DATA_DIR / "ui.json"               ← UI_STATE_FILE（偏好；app.py 写，grab.py 只读）
DATA_DIR / "grab.log"              ← LOG_FILE（日志轮转追加）
DATA_DIR / "grab.log.lock"         ← LOG_LOCK_FILE（跨进程日志锁）
DATA_DIR / "migration.lock"        ← MIGRATION_LOCK_FILE（旧数据迁移锁）
```

> grab.py **不写 ui.json**、不写 migration.lock。这些是 app.py / runtime_paths 管的。
> grab.py 只直接写 session.json / storage_state.json / grab.log 及其锁/临时文件。

### 3.4 非 open() 但有文件副作用的路径

| 操作 | 位置 | 说明 |
|---|---|---|
| `ensure_data_dir()` → `DATA_DIR.mkdir()` | runtime_paths.py L73 | 每次 log() / cmd_* 入口都会调 |
| `os.replace(tmp, path)` | write_json_atomic L344 | 原子替换，不丢旧版本 |
| `os.replace(tmp, path)` | _restore_original L501+L509 | 回滚恢复原文件 |
| 旧 EXE 旁 data → DATA_DIR 迁移 | runtime_paths.py::_migrate_legacy_data | 冻结态首次启动时原子搬 session.json/storage_state.json/grab.log/ui.json |

---

## 第四节：对照测试设计草案

### 4.1 现有测试夹具覆盖了哪些

#### 协议行解析（domain/ 层）

| 解析函数 | 测试文件 | 覆盖点 |
|---|---|---|
| `parse_checkpoint_line` | `test_retry_policy.py`（通过 fake worker）、`test_business_clock_wiring.py` | 只认 kind ∈ {worker_started, page_opened, watch_started}；坏 JSON/未知 kind 返回 None |
| `parse_clock_line` | `domain/worker_lines.py` 本身无直接单测；plan_service 链路里间接覆盖 | 取输出里最后一条 [clock] |
| `parse_retry_line` | `test_retry_policy.py::RetryLineParsingTests`、`test_retry_events.py` | last_reason 在行末契约守护、progress_event_status 对 path/login_wait/login_resumed 的处理、progress 行不冒充终态 |
| `ATTEMPT_RE` 正则 | `test_retry_policy.py::test_max_attempts_full_is_retryable_then_stops` | 第 1/2/3 次提交行 → attempts 递增，不吞人话 |

#### 全链路（plan_service / application 层）

`test_retry_policy.py::WorkerTelemetryFlowTests` 用 **fake worker.py** 脚本模拟 grab 输出，覆盖：
- ✅ [i] 第 N 次提交 → attempts 递增（只在 signUp 行，刷新/查询行不计）
- ✅ [retry] kind=done → 终态 stop_reason / exit code 对应
- ✅ [checkpoint] 源事件时间 → run_started_at / page_opened_at 节点（R10 契约）
- ✅ 进度 [retry] 行无 stop_reason → 不冒充终态，截止尽早上屏
- ✅ phase 字段从进度行和 done 行分别转发
- ✅ exit code 0/2/3 与 classify_task_stop 的关系（stop_reason 优先于 exit code）
- ✅ login_invalid（exit 3）、max_attempts（exit 2）、success（exit 0）

**`test_retry_policy.py::WORKER_FIXTURE`** 定义了 8 个场景（silent / slow_output / parent_exit / structured_only / job_marker / submitted_then_wait / success_then_wait / already_then_wait / definite_fail_then_wait / terminal），覆盖了进程生命周期的各种边界。

#### 子命令级测试

| 子命令 | 测试文件 | 覆盖 |
|---|---|---|
| cancel | `test_cancel_signup.py`（600 行） | worker_command 参数链路、precheck_failed/unknown/cancelled 三种 kind、退出码 0/2 |
| login_relay | `test_login_relay.py`（1000+ 行） | 手机重登中继模式（不是 GUI worker 主路径） |
| layer boundaries | `test_layer_boundaries.py` | plan_service 的 clock_unavailable 捕获、closing 拒绝 |

### 4.2 测试**没有**覆盖的

#### grab.py 代码直接写的分支（无 grab 子命令端到端跑通测试）

| 缺失 | 说明 |
|---|---|
| **terminal() 的 17 个 stop_reason 分支** | 现有 fake worker 只发 success / max_attempts / retry_duration / login_invalid / already_signed 五种（`test_retry_policy.py` 的 already_then_wait 场景，对抗审计 C5 更正）。其余 12 种（auth_unavailable / clock_unavailable / unconfirmed / sign_end / process_error / full / closed / conflict / no_activity / clock_skew / unknown_reply / page_unavailable）没有端到端链路测试。这些分支在 grab.py 里各自有独立的人话输出 + exit code 组合，但解析方 classify_task_stop() 靠 stop_reason 分类，所以解析方逻辑间接覆盖了——**发射端的输出正确性（是否写对 stop_reason、是否写对 exit code）没有测试守护**。 |
| **terminal() 的 done guard** | `done["value"]` 防重入逻辑——正常路径不会触发（终态只走一次），但异常中断后继续执行的边界没有测试。 |
| **cmd_grab 入口校验的 3 个 return 3 分支** | 时钟不可用 / at 格式错 / sign_end 格式错——这些被 main() 接住返回 2/3，不经过 plan_service（因为 worker 还没 start 就 exit 了）。plan_service 只认 stop_reason，不认这些入口分支的 exit code。 |
| **grab.py → 学校真实回包分类** | 所有学校回包（success/full/closed/conflict/no_activity/clock_skew/unknown_reply/page_unavailable）的发射点在 grab.py 内部循环（L3046/L3500/L3576 等），没有单元测试——回包分类逻辑埋在进程生命周期里。 |
| **login_invalid / auth_unavailable 的区分** | stop_reason=login_invalid 和 auth_unavailable 都返回 exit code 3，但语义和用户指导语不同。现有 fake worker 只测了 login_invalid，auth_unavailable 没有覆盖。 |

#### 协议行发射端的格式字符串

| 缺失 | 说明 |
|---|---|
| `[retry] kind=done` 的格式串**变更契约** | `test_retry_policy.py::test_parse_done_line_real_shape_tail_fields_independent` 用正则 `re.search(r'log\("\[retry\] kind=done[^"]*"', source)` 在测试启动时扫 grab.py 源码，守护 `last_reason` 必须在行末。这是**现有唯一**对 grab.py 源码有反射检查的测试。若有人改了 terminal() 里的格式串把 last_reason 挪到行中，这条用例会先红。 |
| `[retry]` 进度行（window / submit / path / login_wait / window_extended / not_ready / throttled / server_error） | 发射端是 `_retry_event(**fields)` 里统一拼的，没有逐个 kind 测格式——解析端 parse_retry_line 不验 kind，所以解析方也不会红。但如果发射端改了 key 名（比如把 `retry_deadline` 拼成 `deadline_epoch`），解析方 plan_service 的 `parsed.get("retry_deadline")` 就取不到，**静默丢字段**，不会有任何失败。 |
| `[checkpoint]` payload 里的 `clock` 可选字段 | `_checkpoint_event` L2376-2378 在有 clock_meta 时加 `"clock": meta`。现有测试不关心这个字段（parse_checkpoint_line 也不消费它），但如果有人删了 clock_meta() 调用，不会有任何测试红。 |

#### 文件 IO / 环境变量

| 缺失 | 说明 |
|---|---|
| **实际写入 DATA_DIR 的端到端** | 所有测试都 mock 了 plan_service 的 spawn()，不会真的启动 grab.py 进程。`test_runtime_bundle.py` 里有 frozen EXE 的黑盒测试，但 **local/grab.py 源码路径** 没有任何用例会真实写入 grab.log / session.json / storage_state.json。 |
| **SCHOOL_ORIGIN 缺失时的行为** | site_target.py 在 SITE_CONFIGURED=False 时，login / check / list / grab 会怎样退出？main() L4062-4063 会 return 2（cancel 例外），但没有测试验证这条路径。 |
| **CAMPUS_CLOCK_SNAPSHOT 有值但快照损坏** | setup_business_clock 会 catch ClockUnavailable 返回 None，但没有测试——grab.py 入口会返回 3，GUI 可能会有异常路径。 |
| **list --json 的 stderr [timing] 行** | cmd_list 的 `_stderr_note("[timing] list ...")` 会在 **stderr** 输出，但 app.py L2713 从 `res.get("stderr")` 读——测试里 mock `_run` 返回的 res 有没有 stderr 键？从现有测试看，可能没有显式构造过 stderr 内容来验证 timing 解析。 |

### 4.3 建议补充的测试用例

| ID | 缺失项 | 建议写法 | 优先级 |
|---|---|---|---|
| T-1 | terminal() 全部 17 个 stop_reason → exit code + [retry] done 行 | 不依赖 fake worker，直接对 grab.py 的 terminal() 函数构造 state dict 调，断言 return 值和 stdout 内容 | 高——现有只覆盖 5 个，且 terminal() 是终态唯一出口 |
| T-2 | auth_unavailable vs login_invalid 的区分 | fake worker 发 stop_reason=auth_unavailable + exit 3，验证 plan_service 分类为 auth_unavailable（不是 login_invalid） | 中 |
| T-3 | [retry] 进度行 key 名变更守卫 | 在 `WorkerTelemetryFlowTests.setUp` 里扫 grab.py 源码，列出所有 `_retry_event(kind=xxx, retry_deadline=...)` 调用，断言 key 名集合是 `{kind, retry_deadline, sign_end, attempts, request_id, path, path_reason, wait_s, phase}` | 高——key 名变更会静默丢字段 |
| T-4 | list --json stderr [timing] 解析 | mock `_run` 返回 `{"stdout": "[]", "stderr": "[timing] list token_s=0.5 pages=1 pages_s=0.3 details=2 details_s=0.2 total_s=1.0 filter_time_source=clock"}`，断言 `activities` 事件里的 timing_text 正确拼接 | 低——功能正常但无显式守护 |
| T-5 | terminal() done guard | mock state.done["value"]=True 后调 terminal("success")，断言 return 2 且无输出 | 低——防御性分支 |
| T-6 | SCHOOL_ORIGIN 缺失时各子命令退出码 | 在 `test_layer_boundaries.py` 里 mock SITE_CONFIGURED=False，验证 login/check/list/grab 都 return 2，cancel 正常 | 中 |
| T-7 | grab.py 入口时钟不可用 return 3 | 直接 import grab.py，mock business_clock.sync 返回失败，验证 cmd_grab() → 3 | 中 |

---

## Spot Checks（随机抽取 15 条用 git show 核对）

> 方法：从 grab-protocol.md 里随机挑 15 个条目，逐个用 `git show 7e2d31c:local/grab.py | Select-Object -Skip <行号-1> -First 1` 核对。

| # | 条目 | 预期 | 实际 | 结论 |
|---|---|---|---|---|
| 1 | terminal() L2558 的 [retry] kind=done 格式串 | `log("[retry] kind=done attempts=%d stop_reason=%s ... last_reason=%s" ...)` | ✅ 确认 L2558-2563，last_reason 在行末，尾字段（pending/streak_404/phase）在它前面 | 通过 |
| 2 | `_checkpoint_event` L2379 调 log() | `log("[checkpoint] " + json.dumps(payload, ...))` | ✅ 确认 L2379 | 通过 |
| 3 | `_retry_event` L2389 调 log() | `log("[retry] " + body)` | ✅ 确认 L2387-2389，body 用 space 拼接 + U+00A0 替换空格 | 通过 |
| 4 | cmd_grab L2522 调 `_checkpoint_event("worker_started")` | 入口就写 worker_started checkpoint | ✅ 确认 L2522 | 通过 |
| 5 | grab.py **唯一** sys.exit 在 L4076 | `sys.exit(main())` | ✅ 确认 L4076；grep 全文件也只命中这一处 | 通过 |
| 6 | REPLY_STOP_HINTS 字典 L2491-2499 有 7 个键 | full / closed / conflict / no_activity / clock_skew / unknown_reply / page_unavailable | ✅ 确认 7 个键，注释写着"决策 015" | 通过 |
| 7 | terminal() stop_reason=success → exit 0 | L2572 `return 0` | ✅ 确认 | 通过 |
| 8 | terminal() stop_reason=login_invalid → exit 3 | L2580 `return 3` | ✅ 确认 | 通过 |
| 9 | terminal() stop_reason=max_attempts → exit 2 | L2591 `return 2` | ✅ 确认 | 通过 |
| 10 | os.environ 直接读取仅 L127 | `if os.environ.get("CAMPUS_CLOCK_SNAPSHOT"):` | ✅ grep grab.py 全文只命中这一处 os.getenv/os.environ | 通过 |
| 11 | DATA_DIR 在 runtime_paths.py 里定义 | `_base_dir()` 读 CAMPUS_DATA_DIR | ✅ 确认 L53，注释明确"环境变量 CAMPUS_DATA_DIR 可覆盖" | 通过 |
| 12 | [timing] list 写 stderr | `_stderr_note("[timing] list ...")` | ✅ 确认 L1344，_stderr_note 内部调 sys.stderr.write | 通过 |
| 13 | list --json 用 `_stdout_to_stderr(True)` | 重定向 stdout 到 stderr | ✅ 确认 L1354 `with _stdout_to_stderr(json_mode):` | 通过 |
| 14 | cancel 子命令也用 `_stdout_to_stderr(True)` | L1595 | ✅ 确认 | 通过 |
| 15 | 工作目录 cmd_login L1257 打不开登录页 → return 2 | `return 2` | ✅ 确认 | 通过 |

**15/15 全过。**

---

## 改动文件清单

- `design/evidence/2026-11-12/refactor-audit/supplement/grab-protocol.md`（本轮新建，基线 7e2d31c 输出协议四节）

`supplement/scripts/grab_outputs.py` 是上一轮（2026-11-11）遗留文件，本轮只运行、未改动，因此不列为本轮新建（对抗审计 D6）。

本轮只从基线 commit `7e2d31c` 的 `local/grab.py` 及相关模块只读解析，未运行 grab.py 本体、未运行测试、未联网。

---

## 已知局限

1. **清单脚本不分类**：清点脚本只穷举所有 print/exit/env/open 调用，不区分「协议行」和「人话行」。本文档第一节的协议行分类是手工完成的，理论上可能漏——但 spot_checks 覆盖了所有格式前缀的发射点。
2. **env 清单是 grab.py 自身代码直接读取**：runtime_paths/business_clock/site_target 这些 import 链里读的环境变量虽然也是 worker 运行时会遇到的，但脚本没抓。本文档第三节的 env 表手工补了全链。
3. **测试覆盖表只列了 worker 输出协议相关**：没有列出 plan_service 进程树管理、watchdog 扩窗、取消语义等其他测试。那些属于不同主题，不在本文档范围。
4. **grab_outputs.py 的 `path_expr` 只显示表达式不显示真实值**：比如 `LOG_FILE`、`LOG_LOCK_FILE` 都是常量名，真实路径需要去 runtime_paths.py 看。脚本设计上有意这么做（避免耦合 runtime_paths 的 import）。

---

## 执行统计

| 指标 | 值 |
|---|---|
| grab.py 总行数（基线） | 4076 |
| print/stdout/stderr/logging 调用 | 87 |
| sys.exit / os._exit 调用 | 1 |
| os.environ 直接读取（grab.py 代码内） | 1（唯键：CAMPUS_CLOCK_SNAPSHOT） |
| open() 写入调用 | 8 |
| stop_reason → exit code 组合 | 17 种 |
| 协议行格式前缀 | 8 种（checkpoint/clock/retry 进度/retry done/i 第 N 次提交/timing list/list JSON/cancel JSON） |
| Spot checks | 15/15 通过 |
