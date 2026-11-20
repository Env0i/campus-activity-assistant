# 报名 worker `cmd_grab` 拆分证据（2026-11-21）

## 1. 范围

本批只搬结构、不改行为：把 `local/grab.py` 里的 1,467 行报名主函数 `cmd_grab` 按准备、执行、终态收尾迁入 `local/application/` 下的六个模块，`grab.cmd_grab` 只留 Playwright 导入、在每次调用时从 `grab` 模块当前全局取 47 个名字组装端口对象，并转发给 `signup_run.run_signup(args, ports)`。

- 开工分支与基线：`refactor/api-coordinator` @ `8583e3a`
- 核心测试文件总数：保持 **39 个**（未新建任何 `test_*.py`，仅扩大三处静态源码契约测试的读取范围并增加非空断言）
- 命令行参数、stdout 文案与先后、`[retry]` / `[clock]` / `[checkpoint]` 结构化行字段与顺序、退出码、报名时序常量、BurstPolicy、签名与传输延迟导入时机、运行时密钥只绑进签名函数 `functools.partial` 的边界均逐字不变。

---

## 2. 六个模块职责与代码形状

| 文件 | 物理行数 | 最长函数（行数） | 职责 |
|---|---:|---|---|
| `local/grab.py` | 2,105（原 3,544） | `cmd_login`（77）；`cmd_grab` 为 **11 行**（原 1,467 行） | 保留原入口名与全部模块级常量/函数；`cmd_grab` 只做 Playwright 导入、调用时取 47 个名字装端口并转发 `signup_run.run_signup` |
| `local/application/signup_run.py` | 276 | `run_signup`（47） | 入口 `run_signup(args, ports)` 与准备阶段：入口业务时钟、冻结起点与重试窗口、预算建立、鉴权与等自动登录、粗校时、查目标、窗口事件、进浏览器前预算检查及最外层三类异常到唯一终态的映射 |
| `local/application/signup_outcome.py` | 155 | `_report_stop_or_failure`（50） | 唯一 `[retry] kind=done` 终态行、各停止原因给人读的结论、飞书通知与退出码、`REPLY_STOP_HINTS`、`SubmitAborted`，以及 `clock_stop` / `budget_stop` 两个收口辅助 |
| `local/application/signup_ledger.py` | 403 | `settle_one`（55） | 同一调度账本：`state` 初值、按回包分类表下结论、页面请求登记与响应/中止结算、直发事件结算、事件泵、在途计数同步、扩窗时重建预算并发 `window_extended` 事件 |
| `local/application/signup_direct.py` | 283 | `precheck_send`（41） | 直发通道：路径选择与 `kind=path` 事件、单向退回点击、版本不兼容与重登后重取密钥、现算签名发一笔、开放前预检（运行时密钥只绑进签名函数的 `functools.partial`） |
| `local/application/signup_browser.py` | 437 | `_make_listeners`（52） | 浏览器阶段：开页、dry-run、已报名前置核对、等待开放、监听注册与解除、主调度循环与点击兜底、finally 资源清理与关浏览器 |
| `local/application/signup_finalize.py` | 218 | `_freeze_and_pump_tail`（44） | 发射闸门 `may_fire`、50ms 短事件泵 `pump_wait`、统一有界收尾（冻结接纳、1 秒尾窗、成功粘性、单次 `getJoinInfo` 最终核对）与收尾异常退路 `fallback_terminal` |

六个新模块均 ≤ 500 行（最大 437 行），所有函数均 ≤ 60 行（最大 55 行），且只 import 标准库、`domain` 与 `application`。

---

## 3. 对照录制方法与结论

脚本位于 `design/evidence/2026-11-21/grab-signup-split/scripts/trace_signup.py`（独立脚本，不被任何测试 import）。

- **方法**：用 `git archive --format=zip` 导出并由 Python `zipfile` 解包到 `tempfile.gettempdir()` 下新建的临时副本目录；在副本里运行 `test_worker_boundaries.py` 与 `test_retry_policy.py` 全部用例（共 281 项测试），对 `grab.cmd_grab` 包装一层，在每次调用前临时包裹 `grab.log`、`grab._post` 与 `sys.stdout`，逐次记录：
  - `case_id`、`call_index`、`exit_code`、`stdout`、`logs`（每一行）、`posts`（每次请求的 `path` 与假时钟时刻 `at`）、`elapsed_s`（调用前后 `grab.time.monotonic()` 之差）。
  - 16 位十六进制运行标识（`os.urandom(8).hex()` 生成的 `<16hex>-<seq>` / `<16hex>-pre<seq>`）统一规范化为 `<RUN_ID>` 后比较。
- **HEAD 自比两遍**：
  - 调用总数：**163 次**（run1 = 163，run2 = 163）
  - 逐字段相等数：**163 / 163**
  - 不确定调用数：**0**
- **搬迁前后比对（HEAD vs 搬迁后副本）**：
  - 调用总数：**163 次**（HEAD = 163，搬迁后 = 163）
  - 逐字段完全相等数：**163 / 163**（`mismatch_count = 0`，`only_in_a = []`，`only_in_b = []`）
  - 证明笔记：初版搬迁曾把 `ctx.finalize_fn` 的赋值放在 `_precheck_before_open` 和 `wait_until(at_ts - POLL_LEAD)` 之后，对照录制立即捕获到 `test_retry_for_zero_keeps_sign_end` 与 `test_backward_jump_does_not_extend` 两处在等待开放期间耗尽预算时走了 `_budget_stop("页面")` 而非原 `cmd_grab` 里的 `_finalize`；将 `ctx.finalize_fn` 移回 `setup_direct_path` 之后、`_precheck_before_open` 之前（与原函数内 `def _finalize` 的声明位置严格一致）后，163 次调用全部逐字段一致。

---

## 4. 十二条定点变异结果表

每一条均在 `tempfile.gettempdir()` 下新建的搬迁后独立副本中单点改坏、运行对应测试文件，跑完即删副本；遇到不红的条目，在开工 HEAD 副本的原位置做同样改动对照。

| 编号 | 变异点 | 修改文件与原句 → 变异句 | 测试文件 | 结果 | 第一条失败的用例名 / HEAD 对照结论 |
|---|---|---|---|---|---|
| V1 | 成功粘性：回包分类为 `success` 时不再置 `resp_ok` | `local/application/signup_ledger.py`：`state["resp_ok"] = True` → `state["resp_ok"] = False` | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.DirectRuntimeKeyTests.test_page_timeout_still_sends_direct` |
| V2 | 结果未确认的退出码从 2 改成 0 | `local/application/signup_outcome.py`：`unconfirmed` 分支 `return 2` → `return 0` | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.ClockLossMidFlowTests.test_clock_loss_with_pending_is_unconfirmed_not_missing` |
| V3 | 扩窗后不再重建预算：去掉结算后的扩窗同步调用 | `local/application/signup_ledger.py`：`sync_budget_window(ctx)` → `pass` | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.UnifiedGateAndFinalizeTests.test_429_triple_extends_window_events` |
| V4 | 收尾尾窗从 1 秒改成 0 | `local/application/signup_finalize.py`：`min(1.0, max(0.0, ctx.budget.remaining_s()))` → `min(0.0, ...)` | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.UnifiedDirectLoopTests.test_direct_late_completed_tail_boundaries` |
| V5 | 收尾不再做单次最终核对 `is_joined` | `local/application/signup_finalize.py`：`if state["attempts"]:` → `if False:` | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.FinalJoinCheckTests.test_expired_budget_still_checks_once_and_counts_join` |
| V6 | 直发时回包为 `no_activity` 不再退回点击 | `local/application/signup_ledger.py`：`downgrade_fn(ctx, "学校查不到活动信息（hd-info 空值），改走点击核实")` → `pass` | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.SignupReplyClassificationTests.test_missing_activity_on_direct_downgrades_to_click` |
| V7 | 确认点击的超时从预算超时改成固定 3000 | `local/application/signup_browser.py`：`timeout=ctx.budget.timeout_ms(3000)` → `timeout=3000` | `test_ui_contracts.py` | **变红** | `test_ui_contracts.StopLifecycleContractTests.test_grab_retry_window_is_hard_deadline` |
| V8 | 浏览器阶段 `finally` 里加一个 `return` | `local/application/signup_browser.py`：`_cleanup_browser_resources(ctx, browser)` 后追加 `return 0` | `test_ui_contracts.py` | **变红** | `test_ui_contracts.StopLifecycleContractTests.test_grab_finally_never_returns` |
| V9 | `done` 行把 `last_reason` 挪到 `pending` 之前 | `local/application/signup_outcome.py`：`"pending=%d streak_404=%d phase=%s last_reason=%s"` → `"last_reason=%s pending=%d streak_404=%d phase=%s"` | `test_retry_policy.py` | **变红** | `test_retry_policy.RetryLineParsingTests.test_parse_done_line_real_shape_tail_fields_independent` |
| V10 | 端口改成在 `grab` 模块 import 时一次绑定 | `local/grab.py`：模块顶层 `_BOUND_SIGNUP_PORTS = {name: globals()[name] for name in _SIGNUP_PORT_NAMES}`，`cmd_grab` 读该字典 | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.AdmissionTests.test_confirm_failure_keeps_zero` |
| V11 | 页面响应回调在直发在途未降级时也入队 | `local/application/signup_browser.py`（及 HEAD `local/grab.py`）：去掉 `on_response` 里的 `if direct["enabled"] and not direct["downgrade"]: return` | `test_worker_boundaries.py` | **既有缺口**（两处均不红） | HEAD 副本在 `local/grab.py` 原位置做同样改动跑 `test_worker_boundaries.py` 同样 `exit_code=0`（不红）。原因：`on_request` 在直发未降级时已拦截了页面自发请求（未登记进 `request_to_bid`），且现有用例未在直发未降级期间构造会改变断言的页面侧 `on_response` 事件，属存量测试未覆盖 `on_response` 单独守卫的既有缺口，非本批引入 |
| V12 | 开放前预检在 `instant` 模式下也发 | `local/application/signup_direct.py`：`if (not direct["enabled"] or direct["downgrade"] or ctx.instant_mode or ctx.at_ts - now_entry < ports.PRECHECK_MIN_LEAD_S):` → `if not direct["enabled"] or direct["downgrade"]:` | `test_worker_boundaries.py` | **变红** | `test_worker_boundaries.FinalizeFallbackTests.test_finalize_exception_with_pending_reports_unconfirmed` |

---

## 5. 全量测试与静态检查对比结论

- **开工 HEAD 基线全量**：`Ran 2738 tests in 203.596s` → `OK (skipped=2)`
- **收尾搬迁后全量**：`Ran 2738 tests in 192.515s` → `OK (skipped=2)`
- **逐用例对比**：开工基线与收尾全量共 2,738 项测试（含 `subTest` 展开），逐条比对状态一致（`status_diffs = []`，`only_in_head = []`，`only_in_closeout = []`），0 项新增失败或报错。
- **静态与结构检查**：
  - `python -B -m ruff check local server tools`：`All checks passed!`
  - `python tools/code_shape/check.py`：通过（文件 >800 行 10 个、501–800 行 11 个；函数 >100 行 23 个、61–100 行 70 个；测试函数 >60 行 19 个；属性超标的类 2 个；其中 `cmd_grab` 及其 5 个超 60 行嵌套闭包已全部降到 60 行以内）
  - `python -m compileall -q local/grab.py local/application`：退出码 0，无任何输出

---

## 6. 复现命令

以下命令在仓库根目录执行（临时目录统一使用 `%TEMP%` 或 `tempfile.gettempdir()`，跑前清掉代理环境变量）：

```powershell
# 清除代理环境变量
$env:http_proxy=$null; $env:HTTP_PROXY=$null; $env:https_proxy=$null; $env:HTTPS_PROXY=$null; $env:all_proxy=$null

# 1. 定向测试与分层/代码形状守卫
python -B -m unittest discover -s local/tests -p test_worker_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_retry_policy.py -v
python -B -m unittest discover -s local/tests -p test_ui_contracts.py -v
python -B -m unittest discover -s local/tests -p test_layer_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_code_shape.py -v
python -B -m unittest discover -s local/tests -p test_worker_logs.py -v
python -B -m unittest discover -s local/tests -p test_signup_plan.py -v

# 2. 代码形状、Ruff 与字节码编译检查
python tools/code_shape/check.py
python -B -m ruff check local server tools
python -m compileall -q local/grab.py local/application

# 3. 在临时副本上运行对照录制自比（使用 tempfile.gettempdir()）
python -B -c "import shutil, subprocess, sys, tempfile, zipfile; from pathlib import Path; tmp = Path(tempfile.mkdtemp(dir=tempfile.gettempdir())); z = tmp / 'repo.zip'; c = tmp / 'copy'; subprocess.run(['git', 'archive', '--format=zip', '-o', str(z), 'HEAD'], check=True); zipfile.ZipFile(z).extractall(c); subprocess.run([sys.executable, '-B', 'design/evidence/2026-11-21/grab-signup-split/scripts/trace_signup.py', '--self-compare-copy', str(c), '--out', str(tmp / 'out')], check=True); shutil.rmtree(tmp, ignore_errors=True)"

# 4. 本机版全量回归
python -B -m unittest discover -s local/tests -p "test_*.py" -v
```

---

## 7. 未验证项

- **真实学校环境**：本批所有测试均在离线替身下执行，未发起真实学校网络请求。
- **真实图形窗口与真实浏览器（Playwright Chromium/Edge）**：`cmd_grab` 的浏览器交互由 `FakePage` / `install_fake_playwright` 替身验证，未拉起真实 pywebview 窗口或真实浏览器。
- **冻结版 worker（`grab-worker.exe`）**：未执行 PyInstaller 打包构建与冻结态子进程验收。

## 8. 审计复核

审计方在独立临时副本（工作区改动叠加在开工提交上）复核，结论与上文一致：

- 定向测试：test_worker_boundaries、test_retry_policy、test_ui_contracts、test_layer_boundaries、test_signup_plan、test_worker_logs、test_cancel_signup 全部通过；test_code_shape 与 tools/code_shape/check.py 在工作区内通过（副本不是 git 仓库，test_code_shape 在副本里会因读不到 git 清单报错，开工提交的副本上同样如此，与本批无关）。
- 对照录制：用本目录脚本重录开工提交与搬迁后各一遍，163/163 次调用逐字段相等；录制内容非空（163 次调用都有日志与 stdout，共 3080 行日志、156 次调用有请求）。
- 另做八条定点变异，三条变红：直发预留不计入次数配额、收尾不解除页面监听、扩窗开关恒关。五条在搬迁后与开工提交的原位置上都不变红，属于既有测试缺口、不是本批引入：事件泵遇 4001 待查或学校明确拒绝时不提前返回；开抢前「是否已报名」查询异常时当成未报名；收尾时忽略 4001 待确认；直发票据序号不计入已预留的笔数；不写事件上下文里的活动 id。连同上文 V11，共六处既有缺口，留给后续补测。
