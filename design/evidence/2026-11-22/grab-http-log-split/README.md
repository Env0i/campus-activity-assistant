# 报名 worker 学校请求层与日志层拆分证据（2026-11-22）

## 1. 范围

本批只搬结构、不改行为：把 `local/grab.py`（开工时 **1,481** 行）最底层的学校请求（直连 opener、网关签名、nonce、POST/GET、HTTP Date 粗校时）与日志（文件锁、轮转、stderr 出口、stdout 改道、写一行日志）迁入 `local/infrastructure/` 下的两个新模块（`school_http.py`、`worker_log.py`），`local/grab.py` 保留原有全部模块级名字与签名，只作调用时从 `grab` 模块全局装配端口的薄转发。

- 开工分支与基线：`refactor/api-coordinator` @ `94dc3cd`（`chore(aoci): 索引同步八处缺口补测`；开工前 `git status --short` 为空，暂存区为空，`.aoci/lock` 不存在）
- 开工基线全量回归（`python -B -m unittest discover -s local/tests -p "test_*.py" -v`）：`Ran 2753 tests in 188.961s` → `OK (skipped=2)`（逐用例解析 2,753 条：2,751 `ok` + 2 `skipped`）
- 核心测试文件总数保持 **39 个**；除将 `local/tests/test_network_policy.py` 中 `test_installing_global_opener_is_not_used` 的源码读取范围扩至 `local/infrastructure/school_http.py`（并增加 `ProxyHandler` 非空扫描断言）外，不改动任何测试。

### 开工 AST 名字清点

用 Python `ast` 扫描 `local/grab.py` 内两层全部函数（不含函数自身定义与局部变量）读取的模块级名字，并与端口设计核对：

| 搬迁块 | 原位置与物理行数 | 读取的 `grab` 模块级名字 | 处理方式 |
|---|---|---|---|
| `_school_open` | L184–L198（15 行） | `urllib` | 调用时传 `grab.urllib` |
| `_hmac_sha256_hex` | L400–L401（2 行） | `hashlib`、`hmac` | 新模块直接导入标准库 |
| `_xor_base64` | L404–L408（5 行） | `base64` | 新模块直接导入标准库 |
| `_encode_x_token` | L411–L417（7 行） | `REQUEST_SECURITY_CLIENT_KEY`、`_hmac_sha256_hex`、`_xor_base64`、`base64` | 密钥与同层函数经参数传入，`base64` 直接导入 |
| `sign_request_headers` | L422–L444（23 行） | `REQUEST_SECURITY_CLIENT_KEY`、`REQUEST_SECURITY_RAW_KEY`、`_encode_x_token`、`_hmac_sha256_hex`、`hashlib` | 两个密钥常量留 `grab` 并与同层函数经参数传入，`hashlib` 直接导入 |
| `_request_nonce` | L447–L450（4 行） | `hashlib`、`secrets`、`time` | 调用时传 `grab.time`，`hashlib`/`secrets` 直接导入 |
| `_post` | L489–L537（49 行） | `API`、`BudgetExhausted`、`REFERER`、`UA`、`_remember_school_date`、`_request_nonce`、`_school_open`、`json`、`sign_request_headers`、`time`、`token`、`urllib` | `json` 直接导入，其余全部（含常量、类、`time`、`urllib` 与回调）在调用时从 `grab` 装配传入；`_remember_school_date` 与 `_SCHOOL_DATE` 留 `grab` |
| `_get` | L540–L559（20 行） | `API`、`REFERER`、`UA`、`_school_open`、`json`、`token`、`urllib` | `json` 直接导入，其余在调用时从 `grab` 装配传入 |
| `clock_sample` | L562–L622（61 行） | `BASE`、`UA`、`_school_open`、`time`、`urllib` | 全部在调用时从 `grab` 装配传入；拆出判定辅助以控制在 60 行以内 |
| `clock_skew` | L625–L628（4 行） | `clock_sample` | 调用时取 `grab.clock_sample` |
| `_log_file_lock` | L208–L233（26 行） | `LOG_LOCK_FILE`、`LOG_LOCK_TIMEOUT_S`、`Path`、`PrefsLockTimeout`、`_LOG_THREAD_LOCK`、`acquire_file_lock`、`contextlib`、`release_file_lock`、`time` | 新模块导入 `pathlib`/`contextlib` 与 `infrastructure.prefs_store` 的锁原语；`_LOG_THREAD_LOCK` 单实例；`timeout_s` 默认值沿用定义时绑定 `LOG_LOCK_TIMEOUT_S` 的存量语义；`LOG_LOCK_FILE` 与 `time` 调用时传入 |
| `rotate_log_file` | L236–L258（23 行） | `LOG_KEEP`、`LOG_MAX_BYTES`、`Path`、`os` | `Path`/`os` 直接导入；`LOG_MAX_BYTES`、`LOG_KEEP` 调用时作为默认上限传入 |
| `_stderr_note` | L261–L269（9 行） | `sys` | 新模块直接导入 `sys` |
| `_stdout_to_stderr` | L273–L290（18 行） | `contextlib`、`os`、`sys` | 新模块直接导入标准库 |
| `log` | L293–L316（24 行） | `LOG_FILE`、`PrefsLockTimeout`、`_append_log_line_unlocked`、`_log_file_lock`、`_stderr_note`、`business_now`、`datetime`、`ensure_data_dir`、`rotate_log_file`、`school_time_text` | `datetime` 与 `PrefsLockTimeout` 新模块直接导入；其余端口（含 `ensure_data_dir`、`business_now`、`school_time_text`、`_log_file_lock`、`rotate_log_file`、`LOG_FILE`、`_append_log_line_unlocked`、`_stderr_note`）全部在调用时从 `grab` 传入 |
| `_append_log_line_unlocked` | L319–L324（6 行） | `LOG_FILE`、`_stderr_note` | 均在调用时从 `grab` 传入 |

---

## 2. 两个新模块职责与代码形状

| 文件 | 物理行数 | 最长函数（行数） | 职责 |
|---|---:|---|---|
| `local/grab.py` | 1,304（原 1,481） | `main`（76） | 保留全部原有模块级名字、签名字典常量与 `_SCHOOL_DATE` 状态；请求层与日志层入口改为调用时从 `grab` 全局读取 `urllib`、`time`、`token`、路径/上限常量与回调的薄转发 |
| `local/infrastructure/school_http.py` | 262 | `clock_sample`（39） | 学校 HTTP 直连 opener（`school_open`）、网关四头签名（`hmac_sha256_hex`、`xor_base64`、`encode_x_token`、`sign_request_headers`）、`request_nonce`、`school_post`（拆 `_build_post_request` 与 `_decode_http_error`）、`school_get` 与 HTTP Date 粗校时（`clock_sample` 拆 `_evaluate_http_date_offset`，及 `clock_skew`）；不导入 `urllib`、`time` 或根目录模块 |
| `local/infrastructure/worker_log.py` | 150 | `log_file_lock`（27） | 唯一进程内日志线程锁 `_LOG_THREAD_LOCK`、跨进程文件锁 `log_file_lock`、轮转 `rotate_log_file`、stderr 出口 `stderr_note`、stdout 改道 `stdout_to_stderr`、`append_log_line_unlocked` 与 `write_log`；不导入 `urllib`、`time` 或根目录模块 |

两个新模块均 ≤ 500 行（262 行、150 行），所有新函数与拆出函数均 ≤ 60 行（最大 39 行）；`clock_sample` 从 61 行拆为 39 行 + 26 行后，全仓 61–100 行存量函数由 68 个降至 67 个。

### 存量怪癖保留记录

- `_log_file_lock(timeout_s=LOG_LOCK_TIMEOUT_S)` 的默认超时在 `local/grab.py` 函数定义时取一次 `LOG_LOCK_TIMEOUT_S`（2.0 秒），`log()` 调用 `_log_file_lock()` 时不传参，因此测试替换 `grab.LOG_LOCK_TIMEOUT_S` 实际并不缩短 `log()` 的拿锁超时。本批按「只搬结构、不改行为」原样保留该定义时默认绑定，未顺手改成调用时取。

---

## 3. 两份对照录制结论

### 3.1 学校请求与日志对照录制（`scripts/record_io.py`）

在 `tempfile.gettempdir()` 下分别解包开工 HEAD 副本（`94dc3cd`）与叠加本批改动后的副本，由独立子进程执行固定输入录制（9 组 `_post`/`_get` 请求字节/请求头/超时/正常回包/Date 侧带/`HTTPError` JSON 与非 JSON/异常/`BudgetExhausted`、7 组 `clock_sample`、日志轮转/`rotate_log_file` 抛错/写失败/`_stdout_to_stderr`）：

- 开工 HEAD 副本自比两遍：`http_cases=9`，`clock_cases=7`，`log_files_rotated=["grab.log", "grab.log.1", "grab.log.2"]`，`diff_count = 0`（`diffs = []`）
- 开工 HEAD 副本 vs 搬迁后副本：`diff_count = 0`（`diffs = []`），逐字段完全相等。

### 3.2 `cmd_grab` 对照录制（`grab-signup-split/scripts/trace_signup.py`）

直接运行 `design/evidence/2026-11-21/grab-signup-split/scripts/trace_signup.py`，在 `tempfile.gettempdir()` 下分别对开工 HEAD 副本与搬迁后副本各录一遍后比对：

- 开工 HEAD 副本调用总数：**170 次**
- 搬迁后副本调用总数：**170 次**
- 逐字段完全相等数：**170 / 170**（`exact_equal = 170`，`mismatch_count = 0`，`only_in_a = []`，`only_in_b = []`）

---

## 4. 十二条定点变异结果表

每条均在 `tempfile.gettempdir()` 下解包的搬迁后独立副本中单点改坏并恢复、运行对应测试文件，跑完即删副本；未变红的条目同步在开工 HEAD 副本原位置做等价改动对照：

| 守的行为 | 改坏位置（文件行号）与变异写法 | 测试文件 | 搬迁后结果与第一条失败用例 | HEAD 对照结论 |
|---|---|---|---|---|
| 网关签名 canonical 方法写死为 POST | `local/infrastructure/school_http.py:70`：`"POST"` → `"GET"` | `test_login_relay.py` | **变红**（1 处失败）：`test_login_relay.PureRuleTests.test_school_request_signature_matches_public_bundle_vector` | — |
| 学校请求 opener 必须显式传入空代理表 `{}` | `local/infrastructure/school_http.py:34`：`build_opener(handler({})).open(...)` → `build_opener().open(...)` | `test_network_policy.py` | **变红**（1 处报错）：`test_network_policy.DirectOpenerShapeTests.test_school_open_builds_a_direct_opener` | — |
| POST 回包的 HTTP `Date` 响应头侧带记录 | `local/infrastructure/school_http.py:154`：跳过 `remember_date_fn(headers.get("Date"))` | `test_list_signed.py`（另运行 `test_worker_boundaries.py` 为 `ok`） | **变红**（1 处失败）：`test_list_signed.ClockFallbackDateTests.test_clock_unavailable_filters_by_school_date_and_enriches_only_visible` | — |
| POST 不得吞掉 `BudgetExhausted` | `local/infrastructure/school_http.py:159`：`except budget_exhausted_cls:` → `except LookupError:`（落入外层 `except Exception`） | `test_worker_boundaries.py` | **未变红**（`rc=0`，现有 `cmd_grab` 用例均替换了 `grab._post`） | HEAD 原 `grab.py` 的 `except BudgetExhausted:` 同改亦 `rc=0`（既有测试缺口，非本批引入；`record_io.py` 已在录制层核对 `_post` 原样抛出） |
| HTTP Date 粗校时不确定区间包含整秒截断 1 秒 | `local/infrastructure/school_http.py:199`：`uncertainty = rtt / 2.0 + 1.0` → `uncertainty = rtt / 2.0` | `test_business_clock.py` | **变红**（2 处失败）：`test_business_clock.ClockQualityTests.test_threshold_straddle_is_unknown` | — |
| `_school_open` 转发在调用时读取 `grab.urllib` | `local/grab.py:184,189`：改为模块导入时绑定 `_BOUND_URLLIB = urllib` | `test_network_policy.py` | **变红**（2 处报错）：`test_network_policy.DirectOpenerShapeTests.test_school_open_builds_a_direct_opener` | — |
| `clock_sample` 转发在调用时读取 `grab.time` | `local/grab.py:437,444`：改为模块导入时绑定 `_BOUND_CLOCK_TIME = time` | `test_business_clock.py` | **变红**（4 处失败）：`test_business_clock.ClockQualityTests.test_slow_response_is_unknown_not_definite` | — |
| 日志轮转按配置份数保留（不提前丢最老一份） | `local/infrastructure/worker_log.py:68`：`count = max(1, (default_keep if keep is None else keep) - 1)` | `test_worker_logs.py` | **变红**（1 处失败）：`test_worker_logs.RotationTests.test_rotation_keeps_at_most_five_copies_newest_first` | — |
| 拿不到日志跨进程锁时不得无锁追加写盘 | `local/infrastructure/worker_log.py:148`：`except PrefsLockTimeout:` 分支先调 `append_fn(line)` 再打降级提示 | `test_worker_logs.py` | **变红**（1 处失败）：`test_worker_logs.LogLockTests.test_lock_timeout_does_not_append_without_the_lock` | — |
| `log` 转发在调用时读取 `grab.rotate_log_file` | `local/grab.py:234,242`：改为模块导入时绑定 `_BOUND_ROTATE = rotate_log_file` | `test_worker_logs.py` | **变红**（1 处失败）：`test_worker_logs.RotationTests.test_rotation_failure_does_not_lose_the_line` | — |
| `--json` 输出期间把 `stdout` 改道到 `stderr` | `local/infrastructure/worker_log.py:101`：`if not enabled:` → `if True or not enabled:` | `test_worker_boundaries.py`、`test_cancel_signup.py` | **均变红**：`test_worker_boundaries.ListEntryTests.test_cmd_list_json_stdout_stays_pure_when_helpers_log`（1 处报错）；`test_cancel_signup.CmdCancelTests.test_non_cancelled_results_exit_nonzero_with_one_json_line`（1 处失败、3 处报错） | — |
| 日志写文件失败时必须经 `stderr` 输出诊断与未落盘行 | `local/infrastructure/worker_log.py:122`：写失败异常处理改为 `pass`，不调用 `note_fn` | `test_worker_logs.py` | **变红**（1 处失败）：`test_worker_logs.WriteFailureTests.test_unwritable_log_goes_to_stderr_and_does_not_raise` | — |

---

## 5. 全量测试与静态检查对比结论

- **开工 HEAD 基线全量**：`Ran 2753 tests in 188.961s` → `OK (skipped=2)`（2,751 `ok` + 2 `skipped`）
- **收尾搬迁后全量**：`Ran 2753 tests in 199.824s` → `OK (skipped=2)`（2,751 `ok` + 2 `skipped`）
- **逐用例对比**：开工与收尾均解析 2,753 项用例，返回码均为 0，`only_in_head = []`、`only_in_closeout = []`、`status_diffs = []`，零新增失败或报错。
- **静态与代码形状检查**：
  - `python -B -m ruff check local server tools`：`All checks passed!`
  - `python tools/code_shape/check.py`：通过（文件 >800 行 10 个、501–800 行 11 个；函数 >100 行 23 个、61–100 行 67 个；测试函数 >60 行 19 个；属性超标的类 2 个）
  - `python -m compileall -q local/grab.py local/infrastructure`：退出码 0，无报错。

---

## 6. 复现命令

以下命令在仓库根目录执行（临时目录统一使用 `%TEMP%` 或 `tempfile.gettempdir()`，跑前清掉代理环境变量）：

```powershell
# 清除代理环境变量
$env:http_proxy=$null; $env:HTTP_PROXY=$null; $env:https_proxy=$null; $env:HTTPS_PROXY=$null; $env:all_proxy=$null

# 1. 定向测试与分层/代码形状守卫
python -B -m unittest discover -s local/tests -p test_network_policy.py -v
python -B -m unittest discover -s local/tests -p test_business_clock.py -v
python -B -m unittest discover -s local/tests -p test_worker_logs.py -v
python -B -m unittest discover -s local/tests -p test_login_relay.py -v
python -B -m unittest discover -s local/tests -p test_session_persistence.py -v
python -B -m unittest discover -s local/tests -p test_worker_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_cancel_signup.py -v
python -B -m unittest discover -s local/tests -p test_list_signed.py -v
python -B -m unittest discover -s local/tests -p test_layer_boundaries.py -v
python -B -m unittest discover -s local/tests -p test_code_shape.py -v

# 2. 代码形状、Ruff 与字节码编译检查
python tools/code_shape/check.py
python -B -m ruff check local server tools
python -m compileall -q local/grab.py local/infrastructure

# 3. 本机版全量回归
python -B -m unittest discover -s local/tests -p "test_*.py" -v
```

---

## 7. 未验证项

- **真实学校网络与登录**：所有学校请求（`listActivity`、`getInfo`、`getJoinInfo`、`cancel`、`signUp` 与 `HEAD /stu/` 粗校时）均在离线替身下执行，未连接真实学校站点或发送真实网络包。
- **真实图形窗口与浏览器**：`cmd_login`、`cmd_grab` 及桌面主窗口均由离线替身验证，未拉起真实可见窗口。
- **冻结态 EXE（`grab-worker.exe`）与服务器版测试**：未执行 PyInstaller 打包、冻结子进程启动与 `server/` 测试套件。

---

## 8. 审计复核

审计方在独立临时副本（工作区改动叠加在开工提交上）复核，结论与上文一致：

- 定向测试：test_network_policy、test_business_clock、test_worker_logs、test_login_relay、test_session_persistence、test_worker_boundaries、test_cancel_signup、test_list_signed、test_school_contract 全部通过。
- 请求与日志录制：用本目录脚本比对开工提交与搬迁后副本，9 组请求用例、7 组校时用例与日志输出逐字段相等；报名主流程对照录制 170/170 次调用逐字段相等。
- 两个新模块与原实现逐段比对：判断顺序、try 层次与返回形状不变；日志线程锁只有一把，锁超时默认值仍在定义时取。细微差别——日志追加与锁文件现在用模块自己的内置 open，不再经 grab.open，现有用例不受影响。
- 「POST 不得吞掉 BudgetExhausted」那条不红的变异属于等价变异：预算换算超时在 try 之外完成，请求通道本身不会抛 BudgetExhausted，那句重抛是走不到的防御代码；录制脚本已核对预算耗尽时原样抛出。
- 另做四条请求层定点变异，在搬迁后与开工提交的原位置上都不变红，属于既有测试缺口、不是本批引入：GET 请求不带 token 头；POST 在 token 为空时也加 token 头；HTTPError 回包不再解析学校的 JSON；请求随机串从 32 位截成 16 位。这四处都是学校接口契约的细节，本目录的录制脚本能发现，但测试套件没有守，留给后续补测。

---

## 9. 请求层契约补测

针对第 8 节识别的四处学校请求层既有测试缺口，在 `local/tests/test_network_policy.py` 的 `SchoolRequestContractTests` 中各补 1 条只断言替身收到的请求对象与返回值的外部可见行为单测（不改动任何产品代码或测试夹具，测试文件总数保持 39 个）。

在 `tempfile.gettempdir()` 下使用 `git archive --format=zip` 导出并叠加测试改动的独立临时副本中，先确认未变异副本跑 `test_network_policy.py`（11 条）与 `test_school_contract.py`（21 条）全绿，随后逐条在独立副本中执行单点变异（每次仅跑 `test_network_policy.py` 与 `test_school_contract.py`，跑完即删副本）：

| 守的行为 | 新用例名 | 变异写法 | 变异下第一条失败用例 | 结论 |
|---|---|---|---|---|
| GET 请求携带显式或已保存的登录 token 头 | `test_network_policy.SchoolRequestContractTests.test_get_request_attaches_explicit_or_saved_token_header` | `local/infrastructure/school_http.py` 的 `school_get` 中将 `req.add_header("token", tok if tok is not None else get_token())` 改为 `pass` | `test_network_policy.SchoolRequestContractTests.test_get_request_attaches_explicit_or_saved_token_header` | 已守 |
| POST 请求在 token 为空时不加空 token 头 | `test_network_policy.SchoolRequestContractTests.test_post_request_omits_token_header_when_token_is_empty` | `local/infrastructure/school_http.py` 的 `_build_post_request` 中将 `if tok_value:` 改为 `if True:` | `test_network_policy.SchoolRequestContractTests.test_post_request_omits_token_header_when_token_is_empty` | 已守 |
| HTTP 错误状态回包照常解析 JSON 体并在非 JSON 时退回 `HTTPError` | `test_network_policy.SchoolRequestContractTests.test_post_request_decodes_json_body_on_http_error_and_falls_back_on_non_json` | `local/infrastructure/school_http.py` 的 `_decode_http_error` 中将 `payload = json.loads(raw)` 改为 `payload = None` | `test_network_policy.SchoolRequestContractTests.test_post_request_decodes_json_body_on_http_error_and_falls_back_on_non_json` | 已守 |
| POST 请求每次生成不同的 32 位小写十六进制 `X-Nonce` 头 | `test_network_policy.SchoolRequestContractTests.test_post_request_generates_distinct_32_char_lower_hex_nonce_headers` | `local/infrastructure/school_http.py` 的 `request_nonce` 中将 `hexdigest()[:32]` 改为 `hexdigest()[:16]` | `test_network_policy.SchoolRequestContractTests.test_post_request_generates_distinct_32_char_lower_hex_nonce_headers` | 已守 |

### 复现命令

在仓库根目录执行（临时目录统一使用 `%TEMP%` 或 `tempfile.gettempdir()`，跑前清掉代理环境变量）：

```powershell
$env:http_proxy=$null; $env:HTTP_PROXY=$null; $env:https_proxy=$null; $env:HTTPS_PROXY=$null; $env:all_proxy=$null

# 1. 新用例与所在测试文件及学校接口契约测试
python -B -m unittest local.tests.test_network_policy.SchoolRequestContractTests -v
python -B -m unittest discover -s local/tests -p test_network_policy.py -v
python -B -m unittest discover -s local/tests -p test_school_contract.py -v
```
