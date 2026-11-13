# T4：local/grab.py 输出协议（只读审计）

- 基线：提交 `7e2d31c`（fix(component): 导入装好后收掉旧的下载失败）。产品代码一律按该基线读，未看工作区现行文件。
- 引用条目：`grab.cites.jsonl` 共 118 条（g-001..g-118），verify_cites.py 0 失败；md 内引用 id 无缺失。
- 审计脚本：`scripts/grab_outputs.py`（python 标准库、只读、自写不复用仓库脚本）。
  复跑命令（仓库根）：
  `python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/grab_outputs.py`
- 脚本输出摘要（对基线 `local/grab.py`，共 4076 行）：
  - 输出调用 159 处：print 85、log() 61、log_event 6、_stderr_note 6、sys.stderr.write 1、sys.stdout.write 0、logging 0。print/log_event/log() 最终都落 stdout；_stderr_note 与 sys.stderr.write 落 stderr。log()/log_event() 同时写 grab.log（见④）。
  - argparse 子命令 6 个：login / check / list / cancel / grab / selftest（经 `sub.add_parser` + `set_defaults(func=cmd_x)` 注册，`main()` 以 `args.func(args)` 顶层分发）。
  - 退出码 return 条目 60（字面常量 + 动态表达式分列）；嵌套函数 return 条目 79（明确标注「非子命令退出码」）；辅助函数返回 int 常量 0 条；sys.exit 调用 1 处（`sys.exit(main())`）。
  - 计数口径说明：任务书给的参考口径「输出调用 187 处」与本脚本 159 处不同，是计数口径差异（本脚本按调用点计，并把 grab 自有日志出口单列），不是矛盾。
- 结构总览：grab.py 的 docstring 只示例五个子命令 [[g-001]]，cancel 只在 main() 注册 [[g-037]]（login/check/list 的注册见 [[g-036]]）；全部输出经 `setup_console` 强制 UTF-8 [[g-002]]。

## ① 输出种类与解析方

约定：凡写「无人解析」，指全仓 `git grep`（按前缀、正则、子串、json.loads 读 stdout 各方式）找不到解析方，属否定性结论，已用推测条目挂住（见未尽事项）。log()/log_event() 产生的行同时上 stdout 和 grab.log，下表归入「log() 复合通道」。

### A. stdout（worker 协议流）

| # | 输出行（前缀/格式） | 产生处 | 解析方 |
|---|---|---|---|
| A1 | `list --json`：stdout 恰一个 JSON 数组（单行 `json.dumps`；空列表为 `[]`），每条活动字段固定（index/id/sign_start/act_*/三态/points/wage/state 等）；辅助日志必须改道的契约注释 | [[g-015]] [[g-014]] [[g-013]] [[g-003]] | app.Api._do_list_inner：先要求退出码 0，再 `json.loads(stdout)`，stderr 不参与 [[g-061]] [[g-062]] [[g-060]]；契约测试同口径 [[g-094]] |
| A2 | `cancel`：stdout 恰好一行 JSON `{ok, kind, reason?, message?}`，kind 白名单 cancelled/refused/unknown/precheck_failed | [[g-017]] [[g-065]] | app.Api._cancel_signup_run → domain.cancel_rules.normalize_worker_result：只认最后一个非空行 JSON，读不出一律 unknown，ok 由 kind 推出 [[g-064]] [[g-066]] [[g-067]] |
| A3 | `check`：`[OK] 登录态有效。` / `[!] 学校 HTTP Date …偏差` / `[X] <原因>` + 重登指引 | [[g-009]] [[g-010]] | app 调 build_check_event：归因只信第一条 `[X] ` 来源行、四态结论按退出码+文本、clock 取 `[clock]` 行 [[g-069]] [[g-070]] [[g-071]] [[g-072]] |
| A4 | `login`（交互）：三行横幅；`[OK] 登录成功…` / `[X] …` | [[g-008]] [[g-111]] | 无人逐行解析：done 结论只看退出码 [[g-068]]；行经 app._pump 只转发 UI 日志 [[g-085]]，前端按前缀着色 [[g-090]] |
| A5 | `login --relay`：stdout 只有 `[login] ` 前缀的 JSON 行（kind=challenge/failed/success…，带 flow_id） | [[g-087]] [[g-088]] [[g-089]] | app._pump 识别前缀后交 relay flow [[g-085]]；application.login_relay_service._handle_line 解析 JSON 并按 flow_id 对账 [[g-086]] |
| A6 | `grab`：`[i] 目标/报名开始/立即报名…`、`[i] 已选择…`（交互）；找不到报名开始时间的 `[X] …请显式传 --at` | [[g-028]] [[g-039]] [[g-038]] [[g-040]] | 人读；计划监督不解析这几行（只转发日志）[[g-082]] |
| A7 | `grab`：`第 N 次提交：…`（可带 `[i] ` 前缀）与 `第 N 次提交：已发起` | [[g-030]] | domain.retry_rules.ATTEMPT_RE 按行匹配计次（刷新/查询行不会撞上）[[g-077]]；plan_service 主循环用最大值归并 [[g-081]] |
| A8 | `grab` 终态人读行：`[OK] 报名成功：…` / `[i] 你已经报过这个活动了。` / `[X] 登录失效…` / `[X] 登录状态暂时无法确认…` / `[X] 已提交 N 次仍没成功…` / `[?] 结果未确认…` / `[X] 暂时无法获取可信北京时间…` / `[X] 没报上：<短结论>` / `[X] 本机流程异常结束…` / `[X] 没抢到：…` | [[g-021]] [[g-022]] [[g-023]] [[g-024]] [[g-025]] | 单场（非计划）：login_service.done_result 要求退出码 0 且 tail 见过「报名成功」 [[g-068]]；计划：domain.plan_rules.classify_task_stop 认 `stop_reason=success` 或 tail 有 `[OK] 报名成功`（成功不要求退出码 0）、`你已经报过这个活动`、倒序第一条 `[X] ` [[g-083]] [[g-084]] |
| A9 | `grab --dry-run`：只打 joined/buttons 日志行，不提交 | [[g-031]] | 无人解析（诊断输出，人读） |
| A10 | `selftest`：`[i] 自检…` / `[OK] 打开成功…` / 页面片段 / `[!]` / `[X] 自检失败…` | [[g-032]] [[g-033]] | 无人解析（推测）[[g-104]] |
| A11 | `list`（文本）：表头 `%3s %s %s %s` + 行 + 提示语 | [[g-016]] | 无人解析（推测）[[g-102]] |
| A12 | `grab` 交互选择：候选表 + `请输入序号（回车选 1，q 退出）` + `确认到点自动报名？[y/N]` | [[g-039]] | 无人解析（stdin 属于人；推测）[[g-103]] |
| A13 | 顶层门禁：站点未配置时除 cancel 外一律 `[X] <CONFIG_MESSAGE>`；cancel 由它自己回一行 JSON 拒绝 | [[g-034]] | 同 A1/A2 各自口径 |

### B. log() 复合通道（stdout + grab.log 同一行）

| # | 输出行 | 产生处 | 解析方 |
|---|---|---|---|
| B1 | 通用日志行：`<北京时间> <消息>`（log() 每条 print + 写文件） | [[g-004]] [[g-042]] | 前端日志视图解析时间戳前缀、按 `[X]/[!]/[OK]/▶` 前缀着色（原话不改）[[g-090]]；check 归因时 `[clock]`/`[checkpoint]` 结构行被剔除不算人话 [[g-070]] |
| B2 | `[checkpoint] {"kind":…,"at":…(,"clock":…)}`：worker_started / page_opened / watch_started | [[g-026]] | domain.worker_lines.parse_checkpoint_line：kind 三值白名单、坏 JSON/未知 kind/at<=0 返回 None [[g-073]] [[g-074]]；plan_service 据此写 run_started_at/page_opened_at/watch_started_at [[g-080]] |
| B3 | `[clock] {json}`（source=http_date，state ok/warn/unknown）：check 与 grab 各一处 | [[g-009]] | worker_lines.parse_clock_line：取最后一条且只认 source=http_date [[g-075]] [[g-076]]；login_service.build_check_event 消费进 check 事件 [[g-069]] |
| B4 | `[retry] k=v …` 进度行：kind=submit / window / window_extended / not_ready / throttled / server_error / path / login_wait / login_resumed（值内空格→NBSP） | [[g-027]] [[g-029]] [[g-030]] | retry_rules.parse_retry_line：`[retry] ` 前缀、空格切 k=v、last_reason 恒最后 [[g-078]]；progress_event_status 转 path/login_wait/login_resumed 快照并还原 NBSP [[g-079]]；plan_service：终态置 stop_seen、window_extended 才扩窗、login_wait 通知界面自动登录 [[g-081]] |
| B5 | `[retry] kind=done attempts=N stop_reason=X retry_deadline=<epoch> sign_end=<epoch> pending=N streak_404=N phase=… last_reason=…`：唯一结构化终态，恰一条 | [[g-020]] | 同 B4 解析器；plan_service 只认带 stop_reason 的那条为策略信息第一来源 [[g-082]]；docs/UI_SPEC.md 声明它是 telemetry 唯一来源并列全字段 [[g-093]]；QA 脚本按它收终态断言 [[g-101]]；架构文档把该解析职责记在 domain.retry_rules [[g-091]] |
| B6 | `[cancel] 前置核对…/复查…` 等过程日志（run_cancel 内 log()） | [[g-018]] | 无专门解析方：作为 B1 通用日志行进 grab.log 与 UI 日志 |
| B7 | `[login] ` JSON 行在 relay 模式经 stdout 输出（见 A5）；非 relay 的登录过程行走 B1 | [[g-087]] | 见 A5 |

### C. stderr

| # | 输出行 | 产生处 | 解析方 |
|---|---|---|---|
| C1 | `[timing] list token_s=… pages=… pages_s=… details=… details_s=… total_s=… filter_time_source=clock/school_date/none`：仅 --json 模式，经 _stderr_note 恰一行（_emit_list_timing 是嵌套函数，无返回值参与退出码） | [[g-011]] | app._do_list_inner 从 stderr 找 `startswith("[timing] list ")` 恰一行，按空格切 k=v 组装「活动列表用时」运行记录 [[g-063]] [[g-092]]；测试镜像同口径 [[g-095]] [[g-097]] [[g-096]]，test_list_signed 夹具方法按同一前缀逐字段解析 [[g-098]] |
| C2 | `[log] …` 降级诊断行（写 grab.log 自身失败/没拿到日志锁）与 `[X] 登录态回滚没成功…`：sys.stderr.write / _stderr_note | [[g-005]] [[g-044]] | 无人解析（诊断输出） |

### D. 其他出站

| # | 输出 | 产生处 | 解析方 |
|---|---|---|---|
| D1 | 飞书群机器人 webhook 卡片（notify，config.json 配了才发）+ 发送结论 log 行 | [[g-050]] | 无本地解析方（外部系统） |

## ② 退出码表（按子命令）

归属依据来自基线源码 + 脚本 AST 清单（`scripts/grab_outputs.py` 的 exit_code_returns / nested_returns 两节）。脚本口径：子命令函数体自身的 return 常量 = 子命令退出码；嵌套函数里的 return 单列「非退出码」列——它们的值经宿主函数 return 间接生效（如 cmd_grab.terminal）。进程退出码唯一出口是 `sys.exit(main())` [[g-035]]；main() 顶层的 return 经它变进程退出码 [[g-034]]。

| 子命令 | 退出码 | 含义与产生处 | 归属依据 | 嵌套函数返回值（非退出码） |
|---|---|---|---|---|
| login | 0 | 登录成功并保存校验通过 | [[g-111]] | 无 |
| login | 1 | 等待中窗口被用户关掉；超时未检测到登录 | [[g-108]] [[g-109]] | 无 |
| login | 2 | 打不开登录页；登录态保存失败；保存后接口校验失败 | [[g-107]] [[g-110]] | 无 |
| login（--relay） | 动态 | 返回 login_relay.run_http_relay 的值：0 成功；1 等不到凭据(eof)；3 token 未验证；4 持久化失败 | [[g-118]] [[g-088]] [[g-089]] | 无（Playwright 兜底 run_relay 的 1/2 未逐条引证，见未尽事项） |
| check | 0 | 登录态有效（另输出 [clock] JSON 行） | [[g-009]] | 无 |
| check | 2 | 登录态失效/未登录/接口异常 | [[g-010]] | 无 |
| list | 0 | 正常（JSON 或文本）；空列表也是 0 | [[g-015]] [[g-016]] [[g-013]] | rank() 返回 0/1/2 排序键——非退出码 [[g-116]]；_emit_list_timing 无返回 |
| list | 2 | 未登录；拉取失败（登录失效/接口异常） | [[g-012]] [[g-112]] | 同上 |
| cancel | 动态 | 条件表达式：kind==cancelled → 0，否则 2（无字面常量） | [[g-017]] | 无（run_cancel 只返回结果 dict [[g-018]]） |
| grab | 0 | 报名成功/已报名/dry-run/查不到目标（CLI 参数与注册见 [[g-038]]） | terminal(success) [[g-021]]；already_signed [[g-021]]；dry-run [[g-031]]；查不到目标 [[g-114]] | terminal 返回 0/2/3——非直接退出码 [[g-020]] [[g-021]] [[g-022]] [[g-023]] [[g-024]] [[g-025]] |
| grab | 2 | 时间格式不对；max_attempts；unconfirmed；学校明确拒绝（REPLY_STOP_HINTS）；process_error；sign_end/retry_duration 到点 | [[g-113]] [[g-115]] [[g-022]] [[g-023]] [[g-024]] [[g-025]] | _clock_stop（pending>0 → unconfirmed，否则 clock_unavailable）[[g-117]]；_budget_stop/_finalize 动态返回（脚本 nested_returns 清单） |
| grab | 3 | 无可信北京时间不启动；本机无登录态；login_invalid；auth_unavailable；clock_unavailable | [[g-019]] [[g-041]] [[g-022]] [[g-023]] | 同上 |
| selftest | 0 / 2 | 浏览器与站点自检通过；页面可疑或异常 | [[g-032]] [[g-033]] | 无 |
| main（顶层） | 2 | 站点未配置（cancel 除外，由 cancel 自己回 JSON） | [[g-034]] | — |
| main（顶层） | 130 | KeyboardInterrupt（打 `[i] 已手动中断。`） | [[g-034]] | — |
| main（顶层） | 动态 | `return args.func(args)` 分发子命令返回值 | [[g-034]] [[g-035]] | — |

退出码消费方（谁在读）：

| 子命令 | 消费方与口径 |
|---|---|
| list | app._do_list_inner：code!=0 直接按失败呈现，stdout 不进 json.loads [[g-061]] |
| cancel | 界面不读退出码：只取 stdout 末行 JSON，超时（code -1、stdout 空）与读不出一律 unknown（需测试定 [[g-105]]）[[g-064]] |
| check | app 把 code 交 build_check_event：code 0 → valid，无会话 → none，网络词 → unknown，登录词 → expired [[g-069]] [[g-071]] [[g-072]] |
| login（单场） | done_result：ok = returncode == 0 [[g-068]] |
| grab（单场） | done_result：ok = returncode == 0 且 tail 见过「报名成功」 [[g-068]] |
| grab（计划） | classify_task_stop：code==3 且 tail 含「登录失效」才归 login_invalid，否则 process_error；成功不要求退出码 0 [[g-084]] [[g-083]] |
| selftest | 无人解析（给人看/快捷方式用） |
| 全部 | worker 由 worker_command 拉起（源码态 python grab.py，冻结态 grab-worker.exe）[[g-059]]；_run 把 returncode 原样带回并拆 stdout/stderr [[g-060]] |

## ③ 环境变量表（grab.py 会读到的）

grab.py 自己只直接读 CAMPUS_CLOCK_SNAPSHOT；其余经它导入的 runtime_paths / business_clock / site_target 在导入与构造时读取（事实，引用指向实际读取处）。父进程（app）注入见 [[g-058]]。

| 环境变量 | 用途 | 读取处 |
|---|---|---|
| CAMPUS_CLOCK_SNAPSHOT | worker 模式判据与 ClockClient 快照路径：有它就只读父进程时钟快照，不自行校时；不可用则报名拒绝启动（[[g-019]]） | grab.py 直接判断 [[g-007]]；business_clock.ClockClient [[g-054]]；app 注入 [[g-058]] |
| CAMPUS_CLOCK_OWNER | 时钟快照归属校验（同实例跨进程允许，不允许跨会话复活） | business_clock.ClockClient [[g-054]]；app 注入 [[g-058]] |
| CAMPUS_DATA_DIR | 数据根覆盖（相对路径先 resolve；测试与迁移用） | runtime_paths [[g-053]]；app 注入 [[g-058]] |
| LOCALAPPDATA | 冻结态数据根基目录（缺失回退 home） | runtime_paths [[g-053]] |
| CAMPUS_CLOCK_DEBUG | 开时钟调试回溯输出 | business_clock [[g-055]] |
| TEMP | 时钟快照临时目录基路径 | business_clock [[g-057]] |
| SCHOOL_ORIGIN | 真实站点根第一候选（经 site_target 导入为 BASE/CONFIGURED；缺失走 config.json → 构建生成 → 占位，占位时 CONFIGURED=False 全部学校动作拒绝） | site_target [[g-056]]；门禁行为 [[g-034]] |

## ④ 写文件表（grab.py 会写哪些文件、触发条件）

数据根路径由 runtime_paths 决定（源码态 local/data，冻结态 %LOCALAPPDATA%/TianSoftActivityPreRegistration/data，CAMPUS_DATA_DIR 可覆盖）[[g-053]]。

| 文件 | 触发条件 | 写入方式与依据 |
|---|---|---|
| grab.log | 每次 log()/log_event()（所有子命令的过程与结构化行） | 追加写（utf-8，a 模式）[[g-042]]；log_event 经 log() [[g-006]] |
| grab.log.1 … grab.log.5 | 每次 log() 前检查：超过 5MB 轮转，依次后移，更老的丢掉 | os.replace 链 [[g-043]] |
| grab.log.lock | log() 轮转与追加的跨进程锁（a+b 打开，锁不到降级 stderr） | [[g-044]] [[g-004]] |
| session.json + session.json.tmp | login 成功保存；--relay 成功保存；任何走 save_session 的路径（登录态唯一写入口，超时放弃不抛） | 原子写 .tmp → os.replace [[g-045]] [[g-046]] |
| storage_state.json + .tmp | 同上（浏览器 cookie 文件，与 session 共用同一把写锁） | [[g-047]] |
| session.json.lock | 登录态写锁（state 与 session 共用一把，成对落位不被插队） | [[g-048]] |
| state/session 双文件事务 | login 成功路径 save_verified_files：两份先写 .tmp 再依次替换，第二份失败回滚到保存前状态 | [[g-049]] |
| 数据根目录本身 | 每个子命令入口 ensure_data_dir()（main 统一初始化 [[g-034]]） | mkdir(parents=True, exist_ok=True) [[g-051]] |
| 迁移写入（session/storage_state/ui.json/grab.log 补缺） | 仅冻结态首次使用新数据根：把旧 EXE 旁 data 只补缺失搬过来，绝不覆盖目标 | [[g-051]] [[g-052]] |
| config.json | 只读不写（notify 读 feishu_webhook） | [[g-050]] |

不在清单里的：grab.py 不写 ui.json 本体（迁移只搬运）、不写任何 plans/results、不写运行记录——运行记录与 UI 偏好都在界面进程侧。

## ⑤ 对照测试草案（输出协议）

现有夹具（基线 local/tests/fixtures/ 实际存在的四个文件）：
- `api_threads.py`：`stop_auto_relogin_on_cleanup`，凡构造 app.Api 的测试必须在 cleanup 停自动重登线程 [[g-099]]；
- `business_clock.py`：`FakeBusinessClock`（显式锚点/经过时长，可驱动 holdover 与过期）[[g-100]]；
- `update_check_v121.py`、`runtime_bridge.js`：与 grab 输出协议无关。
凡草案只用纯函数或打桩 cmd_* 的，不额外需要夹具；需要子进程/浏览器替身的标「缺夹具」。

| # | 测什么 | 断什么 | 夹具 |
|---|---|---|---|
| T1 | `list --json` stdout 纯度 | check_token 内 log() 打印后 stdout 仍恰一个可 json.loads 的 JSON 数组；stderr 恰一行 `[timing] list ` 且含 token_s/pages/pages_s/details/details_s/total_s/filter_time_source 六字段 [[g-094]] [[g-095]] [[g-063]] | 无需新夹具（io.redirect_stdout + 打桩 _post/check_token/log，照 test_worker_boundaries 既有模式）；时钟用 `fixtures/business_clock.py` 的 FakeBusinessClock [[g-100]] |
| T2 | `list --json` 空列表 | rows 为空时 stdout == `[]`、退出码 0 [[g-013]] | 同 T1 |
| T3 | `list` 文本模式 | stderr 无 `[timing]`、stdout 有表头与行 [[g-096]] [[g-016]]；退出码 0 [[g-016]] | 同 T1 |
| T4 | `cancel` 单行 JSON 与退出码 | run_cancel 打桩返回四种 kind：stdout 恰一行可解析 JSON、kind ∈ 白名单 [[g-017]] [[g-065]]；cancelled → 0，其余 → 2（动态条件表达式 [[g-017]]） | 直接调 cmd_cancel（redirect stdout）即可，无需夹具；Api 全链路则必须 `fixtures/api_threads.py` [[g-099]]；子进程级「stderr 无输出、stdout 恰一行」缺夹具（[[g-106]] 需测试定） |
| T5 | cancel stdout 末行优先 | stdout 尾部混日志行时 normalize_worker_result 只认最后一个非空行；读不出一律 unknown、ok 由 kind 推出 [[g-066]] [[g-067]] | 纯函数测试，无需夹具 |
| T6 | `[retry]` 行解析契约 | parse_retry_line：前缀判定、k=v 空格切分、last_reason 恒最后一个字段、解析失败返回 None [[g-078]]；progress_event_status 还原 NBSP [[g-079]]；ATTEMPT_RE 与结构化行次数两路按最大值归并 [[g-077]] | 纯函数测试，无需夹具 |
| T7 | `[checkpoint]` 白名单 | 未知 kind/坏 JSON/at<=0 返回 None；三个合法 kind 通过 [[g-073]] [[g-074]]；plan_service 只按源事件时间写节点 [[g-080]] | at 值用 `fixtures/business_clock.py` 的 FakeBusinessClock 造 [[g-100]] |
| T8 | `[clock]` 取最后一条 | 两行 `[clock]` 时取后者；只认 source=http_date [[g-075]] [[g-076]]；build_check_event 把它带进 check 事件 [[g-069]] | 纯函数测试，无需夹具 |
| T9 | grab 退出码矩阵 | 无可信北京时间 → 3 且零网络 [[g-019]]；token none → 3 [[g-041]]；--at/--sign-end 格式错 → 2 [[g-113]]；already_signed → 0、login_invalid/auth_unavailable → 3、max_attempts/unconfirmed/REPLY_STOP_HINTS 终态 → 2 [[g-021]] [[g-022]] [[g-023]] [[g-024]]；kind=done 恰一条 [[g-020]] | 缺夹具：页面替身（FakePage/FakeResponse）在 test_worker_boundaries.py 模块内，未沉淀到 fixtures/；时钟部分可用 FakeBusinessClock [[g-100]] |
| T10 | `login --relay` stdout 纯度 | relay 模式下 stdout 只有 `[login] ` JSON 行 [[g-087]]；_handle_line 对 flow_id 不匹配的行丢弃 [[g-086]]；eof → kind=failed 且退出码 1 [[g-088]] | 缺夹具：需 stdin/stdout 假管道 + deps 替身（test_login_relay.py 模块内有现成替身模式，未沉淀到 fixtures/） |
| T11 | cancel 退出码被忽略（子进程级） | worker 退出码 2 + stdout 合法 cancelled JSON → 界面仍按 cancelled 收（现在代码只读 stdout [[g-064]]，属 [[g-105]] 需测试定） | 缺夹具（需子进程 worker 或可打桩的 _run 全链路 + api_threads） |
| T12 | grab.log 并发追加与轮转 | 两个写者同写 grab.log：轮转不挪走对方刚写的行、拿不到锁的行只降级 stderr 不丢协议行 [[g-042]] [[g-043]] [[g-044]] [[g-004]] | 缺夹具（缺跨进程测试夹具；可用 tempfile.gettempdir() 下的 CAMPUS_DATA_DIR 覆盖 [[g-053]]） |

## spot_checks

方法：2026-11-12，对下列条目在基线 7e2d31c 重读声明的行区间，与 excerpt 逐字比对并核对语义与 claim 一致；脚本另有行号落位校验（verify_cites.py 0 失败）。

- g-003（grab.py 256..260）：逐字一致；_stdout_to_stderr 契约注释与 claim 相符。
- g-017（grab.py 1592..1605）：逐字一致；cmd_cancel docstring「stdout 恰好一行 JSON」、print(json.dumps) 与条件退出码都在区间内。
- g-020（grab.py 2553..2563）：逐字一致；terminal 是嵌套函数、恰一条 kind=done 的 docstring 原话成立。
- g-026（grab.py 2369..2379）：逐字一致；[checkpoint] payload 只有 kind/at/clock，时钟不可用提前 return 不写。
- g-034（grab.py 4059..4072）：逐字一致；站点门禁、check/list/cancel 建时钟、Ctrl+C 130 全部在区间。
- g-044（grab.py 201..205）：逐字一致；LOG_LOCK_FILE a+b 打开属实。
- g-055（business_clock.py 502..504）：逐字一致；CAMPUS_CLOCK_DEBUG 只控制 traceback 打印。
- g-061（app.py 2691..2697）：逐字一致；code!=0 时 stdout 确实不进 json.loads。
- g-069（login_service.py 25..38）：逐字一致；build_check_event 用 check_reason_line/check_result/parse_clock_line。
- g-075（worker_lines.py 42..50）：逐字一致；「取输出里最后一条 [clock]」docstring 原话成立。
- g-081（plan_service.py 286..296）：逐字一致；stop_seen/window_extended/login_wait 三分支与 claim 相符。
- g-086（login_relay_service.py 393..401）：逐字一致；[login] 前缀 + json.loads + flow_id 对账。
- g-088（login_relay.py 553..560）：逐字一致；eof → kind=failed error=eof → return 1。
- g-092（docs/ARCHITECTURE.md 328..328）：逐字一致；filter_time_source 三值口径原话成立。
- g-107（grab.py 1255..1261）：逐字一致；打不开登录页 [X] + return 2。
- g-109（grab.py 1281..1286）：逐字一致；超时 [X] + return 1。
- g-112（grab.py 1371..1376）：逐字一致；两条失败路径都 return 2。
- g-116（grab.py 1403..1412）：逐字一致；rank 返回 0/1/2 排序键，非退出码。

## 未尽事项

- login_relay.run_relay（Playwright 兜底路径）内部 return 1/2/3 未逐条引证：--relay 退出码只引了 HTTP 主路径（g-088/g-089），兜底属间接路径，如需可补。
- server/ 侧 `server/deploy/grab_signup.py` 有一套同形的 `[retry]`/`[OK] 报名成功` 输出，但那是服务器版自己的实现，不属于 local/grab.py 协议，本篇未展开。
- 所有「无人解析」结论是全仓 `git grep`（前缀/正则/子串/json.loads 各方式，含 local/tests、server/、tools/）的否定性结论，只能证明基线代码层无人解析，不排除仓库外的人工流程或脚本依赖（g-102/g-103/g-104 已按推测挂条目）。
- 输出调用计数 159 是本脚本口径（调用点计数、自有日志出口单列）；参考口径 187 处的统计方式未知，未强行对齐。
- 冻结态 grab-worker.exe 的 onefile 解包、启动耗时对 stdout 时序的影响不在本篇范围。
- test_worker_boundaries.py 内的 FakePage/FakeResponse 等替身沉淀在测试模块内而非 fixtures/，T9/T10 标「缺夹具」即指此事；补夹具属代码改动，超出本次只读审计。
- `[timing]` 行只有 list 子命令会产生；`[clock]` 行在 check 与 grab 两处产生，均经 log() 复合通道。
- 本篇所有行号与摘录都针对基线 7e2d31c；工作区现行代码如有演进，以基线为准（本次为只读审计）。

## 主执行方复核抽查（2026-11-12，基线 7e2d31c）

随机抽样 12 条（种子 20261112，10.2%），逐条重读基线核对原文与语义：12/12 成立。明细存 plan/verify/grab-spot.txt；verify_cites.py 复跑 118 条 0 失败存 plan/verify/grab.txt；grab_outputs.py 复跑输出存 plan/verify/grab-script.txt。


## 补记：terminal() 的 stop_reason 总数（T6 对账 C5，2026-11-12）

terminal() 处理 **17** 个 stop_reason 值：success、already_signed、login_invalid、auth_unavailable、max_attempts、unconfirmed、REPLY_STOP_HINTS 七键（full/closed/conflict/no_activity/clock_skew/unknown_reply/page_unavailable）、process_error，兜底 sign_end/retry_duration [[g-020]] [[g-021]] [[g-022]] [[g-023]] [[g-024]] [[g-025]]。现有 fake worker 覆盖其中 5 种（含 already_signed）；T9 对照测试草案按 17 种写全。


## 补记：输出调用计数的两种口径（T7 对 AA2 的处置，2026-11-12）

脚本口径 159 = print 85 + sys.stderr.write 1 + log 61（64 处匹配扣 log_event/notify 内部转发 3）+ log_event 6 + _stderr_note 6，指「stdout/stderr 协议行」的产出调用；`notify` 4 处（grab.py:2569、2598、2612、2624 调用，定义 1646）是外部推送通道，不产 stdout/stderr 行，故不计入 159。AA2 口径把 notify 计入输出种类（159+4=163，log 不扣转发则 166）。两口径各自成立：解析方表只关心协议行，输出种类总表若要穷举调用点应含 notify——参照口径 187 无法从基线复算，本表不采纳也不推翻，待人裁决是否统一口径。

## 补记：login --relay 退出码 3/4 补核（T7 对 AA2 意见 7 的处置，2026-11-12）

主执行方补核：3/4 两档成立——login_relay.py:421-445 的 `_settle_success` 返回 3（token_unverified 三路，427/432/435）、4（保存会话失败 internal，443）、0（成功，445）；1（凭据 EOF）在 265。265-381 区间另有 return 1/2 若干处，其函数归属未逐一追（可能属 relay 面也可能属辅助函数）——完整返回面逐函数归属列为后续复核项，本表 0/1/3/4 的结论不变。
