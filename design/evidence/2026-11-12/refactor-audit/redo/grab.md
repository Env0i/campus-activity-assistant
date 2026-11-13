# T4 grab.py 输出协议（盲做）

- **基线提交**：`7e2d31c`；文件 `local/grab.py`，共 4077 行。事实放在 `grab.cites.jsonl`，本文只写 `[[条目id]]`。
- **清点方法**：`scripts/grab_outputs.py` 用 `ast` 列出全部输出调用、各函数自己的 `return`、`sys.exit`、环境变量和写文件调用，并按子命令归属（口径写在脚本头）。**不复用补充轮的同名脚本**。解析方用全仓搜索（`local`、`server`、`tools`、测试、前端），按前缀、子串、正则、`json.loads` 读 stdout 的地方都找。
- **脚本数字**（从仓库根复跑 `grab_outputs.py`）：脚本列出的输出点共 187 处，口径分两层：**输出函数本身 148 处**（`log(...)` 62、直接 `print` 到 stdout 84、写 stderr 的 `print` 1、`sys.stderr.write` 1）；**调用封装函数的点 39 处**（`terminal(...)` 22、`_stderr_note` 6、`_rollback_note` 2、`pick_activity` 等 3 个各 1、`log_event` 6），封装本身不另输出新行，但 `log_event` 与 `log` 一样会把带时间戳的整行 print 到 stdout（[[GRB-301]]），`_stderr_note` 才写 stderr（[[GRB-003]]）。下面「归属」是静态可达归属，同一处输出可属多个子命令，所以各项相加（223）大于 187。归属：grab 130、login 30、list 23、cancel 16、check 14、selftest 6、`main` 2、无静态可达 2（一处 `register_request` 的日志、一处写登录文件的失败日志）。`cmd_*` 里嵌套函数里的 `return` 共 109 个，不算子命令退出码。
- **两条贯穿全表的事实**
  1. `log(msg)` 往 stdout 打印的是**带时间戳的整行**（[[GRB-001]]、[[GRB-002]]），行首是北京时间 `YYYY-MM-DD HH:MM:SS`；直接 `print` 的行没有时间戳。`_stderr_note` 才写 stderr（[[GRB-003]]）。
  2. `list --json` 的 stdout 要给主程序 `json.loads`，所以这个子命令执行期间 stdout 被整体改道到 stderr（[[GRB-014]]），只有最后的 JSON 才写到真正的 stdout。

## 一、输出行种类与解析方

「解析方」只算**按文本内容解读**这些行的代码；只是把整行转发给界面显示的不算。标「无人解析」的，表示全仓搜索没有命中任何按该前缀、子串或正则读取它的地方。

| # | 种类（前缀与格式） | 产生处（子命令） | 解析方 | 说明 |
|---|---|---|---|---|
| 1 | `[retry] kind=… attempts=… stop_reason=… …`（进度型与终态型两种；字段以空格分隔，值内空格换成不换行空格） | 进度行 [[GRB-004]]，终态行 [[GRB-005]]；均经 `log`（grab） | 解析函数 [[GRB-101]]（要求行以前缀开头）；计划服务读终态行 [[GRB-102]]、读进度行 [[GRB-103]]；单场报名结论 [[GRB-104]] 读尾部做子串判断；QA 脚本用子串 [[GRB-105]] | **见下面的 W6**：解析函数要求行首就是前缀，而产生处走 `log`，行首带时间戳。进度行共 8 种 kind，加终态 `done`：`login_wait` [[GRB-310]]、`login_resumed` [[GRB-311]]、`window` [[GRB-312]]、`path` [[GRB-313]]、`window_extended` [[GRB-314]]、`submit` [[GRB-315]]、`not_ready` [[GRB-316]]、`throttled` [[GRB-317]]、`server_error` [[GRB-318]]（含终态共 10 种取值）。按 kind 读取的只有 `path`、`login_wait`、`login_resumed` [[GRB-319]]（`progress_event_status`）和计划服务里的 `window_extended`、`login_wait` [[GRB-320]]；其余 kind 只靠 `retry_deadline`、`attempts`、`phase` 字段被读 [[GRB-321]] |
| 2 | `[i] 第 N 次提交：…`（每次发起提交一行） | `_settle_one` 等多处，均经 `log`（grab） | 正则 [[GRB-106]]（行首锚定），计划服务 [[GRB-107]] 用它计提交次数 | 同上，行首锚定 |
| 3 | `[checkpoint] {"kind":…,"at":…}`（JSON） | [[GRB-006]]（grab） | [[GRB-108]]（按子串找，不要求行首）；计划服务 [[GRB-109]] | 能读到带时间戳的行 |
| 4 | `[clock] {…}`（JSON，粗校时结论） | check [[GRB-007]]，grab 入口 | [[GRB-110]]（按子串找，取最后一条）；check 的来源行提取会过滤它 [[GRB-111]] | 能读到带时间戳的行 |
| 5 | `[timing] list token_s=… pages=… …` | list，写 **stderr** [[GRB-008]] | 主程序只认 stderr 里以该前缀开头的行 [[GRB-112]] | 走 `_stderr_note`，没有时间戳，行首对得上 |
| 6 | 活动列表 JSON（一行，数组） | list `--json` [[GRB-009]]；空列表 `[]` [[GRB-010]] | 主程序对 stdout 做 `json.loads` [[GRB-113]] | stdout 此前被改道，不含日志行 |
| 7 | 取消结果 JSON（stdout 最后一行） | cancel [[GRB-011]] | [[GRB-114]]：只认最后一个非空行 | 前面可以有任意日志行 |
| 8 | `[login] {…}`（JSON 安全行，手机重登中继协议） | 不在 `grab.py`，在 `login_relay.py` [[GRB-013]]，经 `login --relay` 调用 | 泵线程按行首前缀识别 [[GRB-115]] 并转交中继 [[GRB-116]] | 用 `print`，无时间戳，行首对得上 |
| 9 | `[X] …` 失败行（登录失效、没报上、未确认等；`print` 的版本行首无时间戳，`log` 的版本带时间戳） | login、check、list、grab、selftest | check：取第一条以 `[X] ` 开头的行为原因 [[GRB-117]]；done 事件：取尾部最后一条以 `[X] ` 开头的行为失败原因 [[GRB-118]]；桌面运行记录按前缀着色 [[GRB-119]] | 计划模式的失败原因另有一处解析：倒序取第一条以 `[X] ` 开头的行 [[GRB-302]]，用于 `classify_task_stop`；登录失效另按子串 `登录失效` 判 [[GRB-303]]（子串，对带时间戳行成立）。`print` 的 `[X]` 行（如 [[GRB-308]]）行首无时间戳，能被认出；`log` 的 `[X]` 行（如 [[GRB-309]]）带时间戳，认不出。所以计划模式的失败原因取决于该行是哪种输出 |
| 10 | `[OK] …` 成功行 | login、check、grab | 单场结论按子串判断 [[GRB-120]]；done 事件读「报名成功」子串 [[GRB-121]]；着色同上 | 子串，能读到 |
| 11 | `[i]`、`[!]`、`[?]` 说明行 | 全部子命令 | 着色（前缀）；无按内容读取的代码 | 其中 `[i] 第 N 次提交` 见第 2 行 |
| 12 | `[cancel] …` 过程行 | cancel（`run_cancel` 及其内嵌函数） | **无人解析**（全仓搜 `[cancel]` 只有 grab 自己的产生处） | 取消只认最后一行 JSON |
| 13 | 自检与交互提示（`selftest` 的结果、`pick_activity` 的序号表、`resolve_target` 的确认文字、`grab` 的「后台等待中」） | selftest、grab、list（交互版） | **无人解析** | 给人看的 |
| 13b | `[log] …` 诊断行（数据目录不可用、日志轮转失败、没拿到日志文件锁、写日志文件失败） | `log` 与 `_append_log_line_unlocked` 内部，写 **stderr** [[GRB-330]]、[[GRB-331]]（共 5 个调用点） | 读取方未核 | 与 `[timing]` 同走 `_stderr_note` |
| 13c | `list --json` 的旧界面读取 | `local/gui.py` 里取输出最后一行做 `json.loads` [[GRB-332]] | 是否仍被使用未核 | 推测，见该条缺的一环 |
| 14 | 站点未配置：`[X] …` 后返回 2 | `main` [[GRB-015]] | 不在 `cancel` 时 stdout 走上面第 9 行；`cancel` 自己回一行 JSON 拒绝 | `main` 注释写明原因 |

**W6（代码层事实；端到端表现单列为需测试定）**：

1. 产生：`log()` 为每行拼上北京时间戳再整行 print 到 stdout（[[GRB-001]]、[[GRB-002]]），仓库里没有关闭它的开关（`grab.py` 直接读的环境变量只有时钟快照路径，[[GRB-019]]）。`[retry]` 终态行、进度行与「第 N 次提交」行都经 `log`（[[GRB-005]]、[[GRB-004]]、[[GRB-306]]）。
2. 传递：计划服务的读线程只去掉行尾换行（[[GRB-123]]），`feed` 把原始行交给各解析函数（[[GRB-122]]、[[GRB-103]]）。
3. 解析：`parse_retry_line` 要求行以 `[retry] ` 开头（[[GRB-101]]，它先只去首尾空白，[[GRB-130]] 所在行），`ATTEMPT_RE` 用行首锚定（[[GRB-106]]）；`[checkpoint]`、`[clock]` 用子串查找（[[GRB-108]]、[[GRB-110]]），不受影响。计划模式失败原因按「以 `[X] ` 开头」取（[[GRB-302]]），对 `log` 版本的 `[X]` 行同样不成立；登录失效子串（[[GRB-303]]）、`[OK] 报名成功` 子串（[[GRB-104]]）不受影响。纯函数验证：给 `parse_retry_line` 传带时间戳的 `[retry] kind=done …` 返回 `None`，不带时间戳时返回字典；`ATTEMPT_RE` 同理。
4. 所以，**计划模式下带时间戳的 `[retry]` 行、「第 N 次提交」行、`log` 版本的 `[X]` 原因行认不出，是代码层事实**。现有测试没有红，是因为输入形状与生产不同：除了 `test_retry_events` 的单元样例，`test_retry_policy` 的 fake worker 也用 `print` 直接输出不带时间戳的 `[retry]` 与「第 N 次提交」行（[[GRB-340]]、[[GRB-341]]）。

**需测试定（只剩端到端表现）**：认不出之后，计划结果页最终显示什么原因（是落到 `process_error`，还是靠退出码与子串落到别的值）、`supervised` 路径的 `unconfirmed` 会不会因为次数观察不到而变化，没有运行带时间戳输出的计划服务观察过。要补的测试：把 `test_retry_policy` 的 fake worker 输出改成与 `log()` 同形（带时间戳），断言 `stop_reason` 为 `full` 或 `unconfirmed`；另起最小进程调用 `grab.log("[retry] kind=done attempts=1 stop_reason=full")`（数据目录指向临时目录），把 stdout 一行交给解析函数。

## 二、退出码（按子命令逐个写）

脚本给的是各 `cmd_*` 函数自己的 `return`；嵌套函数里的 `return`（109 个）不算子命令退出码。进程退出码 = `main()` 的返回值经 `sys.exit(main())`（[[GRB-018]]）。`main` 自己还有：站点未配置返回 2（[[GRB-016]]，`cancel` 例外）、被 Ctrl+C 中断返回 130（[[GRB-017]]）。

| 子命令 | 退出码与含义（脚本列出的 `cmd_*` 自身 return） | 读取方 |
|---|---|---|
| login | 0 登录成功并已保存（[[GRB-308b]]）；1 两处：窗口被关（[[GRB-350]]）、等超时（[[GRB-351]]）；2 三处：打不开登录页（[[GRB-349]]）、登录态没能写入（[[GRB-352]]）、接口校验失败（[[GRB-353]]）；`--relay` 时返回中继函数的返回值 | 桌面只看是否为 0 [[GRB-124]] |
| check | 0 登录态有效；2 无效或检查失败 | 主程序读退出码与全部输出 [[GRB-125]]，再按来源行分类 [[GRB-126]]（退出码为 0 直接认有效） |
| list | 0 成功（含空列表）；2 三处失败：检查登录态失败、`PermissionError`（登录态失效）、拉取活动异常（站点未配置由 `main` 返回 2，不属于 list） | 主程序：非 0 就当失败并把输出原样显示 [[GRB-127]] |
| cancel | 0 取消成功；2 其余 | 读取方**不看退出码**，只看 stdout 最后一行 JSON [[GRB-114]]；超时（-1）与读不出一律「结果未知」 |
| grab | 0、2、3 和一批「由内嵌函数算出再返回」的值（`terminal(...)`、`_finalize(...)`、`_clock_stop()`、`_budget_stop(...)`）；另有两处直接 `return 0` 容易漏：目标解析不出时（`resolve_target` 返回空，其中包括「找不到报名开始时间」这条 `[X]` 失败和「已取消」）[[GRB-322]]，以及 dry-run 完成 [[GRB-323]] | 单场结论 [[GRB-104]]（退出码加尾部子串）；done 事件 [[GRB-121]] |
| selftest | 0 通过；2 失败 | 无人读取退出码（只由安装批处理直接运行 [[GRB-128]]，看控制台） |

### grab 子命令的退出码：`terminal(stop_reason)` 的映射

`cmd_grab` 的绝大部分 `return` 最终来自内嵌函数 `terminal(stop_reason)`（脚本把这类返回值列为「由内嵌函数算出」）。它先写唯一一条结构化终态行 `[retry] kind=done …`（[[GRB-005]]），再按终态给人读结论和退出码；重复调用直接返回 2（[[GRB-211]]）。逐个终态：

| 终态 `stop_reason` | 退出码 | 依据 |
|---|---|---|
| `success` | 0 | [[GRB-201]] |
| `already_signed` | 0 | [[GRB-202]] |
| `login_invalid` | 3 | [[GRB-203]] |
| `auth_unavailable` | 3 | [[GRB-204]] |
| `clock_unavailable` | 3 | [[GRB-207]] |
| `max_attempts` | 2 | [[GRB-205]] |
| `unconfirmed` | 2 | [[GRB-206]] |
| 回包类 7 个（`full`、`closed`、`conflict`、`no_activity`、`clock_skew`、`unknown_reply`、`page_unavailable`） | 2 | [[GRB-208]]，七个键在 [[GRB-212]] |
| `process_error` | 2 | [[GRB-209]] |
| 其余（`sign_end`、`retry_duration` 及任何未知值） | 2 | [[GRB-210]] |

合计 15 个有显式取值的终态（2 个返回 0：`success`、`already_signed`；3 个返回 3：`login_invalid`、`auth_unavailable`、`clock_unavailable`；10 个返回 2：`max_attempts`、`unconfirmed`、回包类 7 个、`process_error`）加一个兜底。要补的对照测试：每个终态各录一条「输入回包序列 → 终态行与退出码」，现有夹具见第四节。

「grab 的退出码」不能只看脚本列出的常量：`cmd_grab` 大部分 `return` 的是内嵌函数的返回值，这些函数的返回值又来自 `terminal`、`_finalize` 里的映射。要补的对照测试：逐个终态（成功、已报名、登录失效、登录状态无法确认、最大次数、未确认、时钟不可用、截止、进程异常）各录一条「输入回包序列 → 退出码」。

## 三、环境变量与写文件

| 类 | 内容 | 依据 |
|---|---|---|
| 读环境变量 | `grab.py` 本文件里直接读的只有 `CAMPUS_CLOCK_SNAPSHOT`（时钟快照路径） | [[GRB-019]] |
| 父进程传入 | 主程序启动 worker 时设置 `CAMPUS_DATA_DIR`、`CAMPUS_CLOCK_SNAPSHOT`、`CAMPUS_CLOCK_OWNER`，以及 `PYTHONIOENCODING`、`PYTHONUTF8` | [[GRB-020]]、[[GRB-021]]；`CAMPUS_DATA_DIR`、`CAMPUS_CLOCK_OWNER` 由 `grab.py` 引入的别的模块读取，不在本脚本范围 |
| 写文件 | 运行日志 `grab.log`（追加，加跨进程锁，超过上限轮转） | [[GRB-022]]，轮转用 `os.replace`（脚本明细列出 3 处） |
| 写文件 | 登录态两个文件（会话与浏览器状态）：临时文件加 `os.replace`，失败回滚 | 脚本明细列出 `_save_verified_files_locked`、`_restore_original` 的写操作 |
| 写文件 | 通用原子 JSON 写入 `write_json_atomic`（临时文件加替换） | 脚本明细 |
| 写文件 | 空设备（无控制台形态下 stdout 改道） | [[GRB-014]] |

## 四、对照测试草案（每个子命令一组）

「可用夹具」指仓库里已有、可直接复用的替身；「缺夹具」指现在没有。输入回包序列指替换掉学校请求边界后喂给 `grab` 函数的序列。

| 子命令 | 对照什么 | 可用夹具 | 缺夹具的分支 |
|---|---|---|---|
| list | 同样的回包序列，`--json` 的 stdout 一行 JSON 与退出码不变；stderr 里的 `[timing]` 行字段不变 | `test_list_signed` 的网络边界替身和业务时钟注入；`test_worker_boundaries` 的 F01 一组；`test_business_clock_wiring` 的 `cmd_list` 调用 | 空列表输出 `[]`；登录态失效、站点未配置、拉取失败三个退出码 2 分支各一条 |
| check | 有效、无效、网络错误三种回包的输出行与退出码 | `check_token` 的替身（`test_login_probe`、`test_session_persistence` 一带） | `[clock]` 行的带时间戳形态；时钟偏差告警行 |
| cancel | 四类结果 JSON 与退出码 | `test_cancel_signup` 里的 `cmd_cancel` 调用（网络边界替身） | 异常兜底分支的两种 `kind`（已调与未调接口） |
| login | 成功、窗口被关、超时、接口校验失败的输出行与退出码；`--relay` 的 `[login]` 行 | `test_login_relay_service`、`test_session_writer` | 浏览器启动失败；保存登录态失败回滚（1 的两个出口） |
| grab | 每个终态的输出行序列、`[retry]` 终态行、退出码 | `test_worker_boundaries` 的 `FakePage`、`FakeBrowser`、`FakeClock`；`test_business_clock_wiring`；`test_signup_plan` | 带时间戳的真实输出行经计划服务解析（见 W6）；`terminal` 各分支与退出码的完整映射 |
| selftest | 通过与失败的输出行 | 缺夹具 | 全部（没有任何测试经过 `cmd_selftest`） |

## 五、新问题

- **W6**（需测试定）：见第一节。
- **W7（推测）**：`selftest` 子命令看起来没有测试和解析方，退出码没有读取方；它在安装批处理里直接运行（[[GRB-128]]）。这是全仓缺席结论，缺的一环见 [[GRB-131]]。
