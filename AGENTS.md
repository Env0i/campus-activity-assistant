# AGENTS.md

本文件对本仓库内的所有 AI agent（Codex、Claude 和其他）以及人同时生效。Claude 另外还读 `CLAUDE.md`，那里只放 Claude 专用的补充。

## 这是什么

校园活动推送工具，服务目标学校的专升本学生端。它把「今天要参加的」和「即将开放报名的」活动整理成卡片推到飞书，还能在报名开放的时刻自动提交。

两个版本共用同一套接口知识和报名时序，但**不共享运行环境**：

| 目录 | 是什么 | 跑在哪 |
|---|---|---|
| `local/` | 本机图形界面（pywebview），多活动报名计划 | Windows，用户自己的电脑 |
| `server/` | 定时推送、群 @ 查询、私聊预报名、无人值守重登 | Linux + systemd + cron |
| `contracts/` | 学校接口的脱敏样例 | — |
| `docs/` | 架构、运维、登录、自动报名、飞书、配置，是工程真源 | — |
| `design/` | 决策记录（篇数见 `design/decisions/README.md`）、规格、流程、新工作台原型 | — |
| `tools/` | 发版、QA 和代码结构检查脚本 | — |

## 硬边界

- **只服务本人账号**：不做多账号，不批量占位，不代他人报名。任何改动都不得越过这条。
- 除非任务明确要求，不引入新依赖。
- 除非任务明确要求，不改数据模型、登录态机制和学校接口契约。
- 浏览器自动化只能点用户已经明确指定的活动，不能无差别提交。

## 共享工作区与授权

当前工作区是共享目录下的 `share/code/campus-activity-assistant`，同一时间可能有别的协作者或 agent 在改同一份文件。

- **开工前后**：开工前跑 `git log --oneline -5` 和 `git status --short`，收工后再跑一次 `git status --short`。发现不是自己改的文件，不回滚、不清理、不覆盖，只在报告里列出文件名。
- **暂存**：只 `git add` 自己动过的文件，不用 `git add -A`。
- **要先授权的 Git 操作**：
  - 授权来自用户，或者来自 `/plan-execute` 计划里的明确要求。
  - 需要授权的操作有：commit、push（包括 `--force` 和 `--force-with-lease`）、rebase、amend、reset、clean、gc、filter-repo、merge、cherry-pick、大范围回滚，以及删除分支、tag、stash 或其他 refs。
- **永远不跑**：`git reset --hard`、`git checkout --`、`git clean -xdf`、`git gc --prune=now`、`git filter-repo`。这些命令会丢掉别人还没提交的工作，或者改写共享的对象库。
- **构建、测试和外部网络**：没有用户授权、计划里也没要求时，不跑构建和测试，也不做真实的外部网络操作。
- **多步骤任务**：先按 Plan Protocol 2.2.1 写计划。
  - 计划放 `.claude/plans/`，执行结果放 `.claude/results/`。`.claude/` 已被 gitignore，不入库。
  - 计划要先过门禁，门禁是共享桥接目录里的 `plan-validate`。门禁需要 PyYAML，本机测试用的 Python 3.12 没装 PyYAML。
- **需求有歧义时**：只在有歧义时才问。能自己判断的，把判断写进提交正文的「放弃了什么」。
- **收工**：
  - 提醒提交端净化 `.claude/`（对共享工作区可见）。脚本是共享桥接目录里的 `scrub-share.ps1`，写法随 PowerShell 版本不同，两种环境不通用：
    - PowerShell 7：`pwsh -NoProfile -File <bridge 目录>/scrub-share.ps1 -Repo <当前项目路径>`
    - PowerShell 5.1：不能 `-File` 直跑。它按 ANSI 解码无 BOM 的脚本，中文串里的 `}` 会被吞掉，报「Try 语句缺少 Catch 或 Finally」，改用加载器：

      ```powershell
      $B = '<bridge 目录>'
      $T = [IO.File]::ReadAllText("$B\scrub-share.ps1", [Text.Encoding]::UTF8) -replace '(?m)(param\([^)]*\)\r?\n)', ('$1' + "`$PSScriptRoot = '$B'`r`n")
      & ([scriptblock]::Create($T)) -Repo '<当前项目路径>'
      ```

      不写 `-Repo` 就用当前目录；第二行补的是 `$PSScriptRoot`，它在 scriptblock 里是空串，缺了会在 `Split-Path` 上报空路径。
  - 交接用 `git bundle create ../handover.bundle --all`。
- **报告**：完成后只报告五件事：
  1. 改了什么
  2. 验证了什么
  3. 还有什么没验证
  4. 有没有 plan_amendments
  5. 是否需要用户授权 push

## 安全与敏感信息

- **不读、不建、不复制、不提交**：
  - `local/data/`、`server/data/`
  - `local/config.json`、`server/config.json`
  - `.env`、会话、cookie、storage state、token、凭据、私钥
- **不入库**：`dist/` 和 `reports/` 是构建和运行产物。
- **不要动 Git 共享配置**：`.git/config` 和 `.git/hooks` 由同一台机器上的几个工作区共用。
- **真实站点地址**：只从环境变量 `SCHOOL_ORIGIN` 读；没有这个变量就用占位地址，不把真实地址写进仓库。
- **不写进代码、文档、计划、结果、日志、提交信息的内容**：
  - 账号、密码、验证码、token，以及登录文件的内容
  - 学号、真实姓名、邮箱、学校名称
  - 主机路径

## 开工前读什么

- **决策记录**：先读 `design/decisions/` 里和本次改动相关的那篇，索引见那里的 README。
  - 已经拍板的规则不重新设计。
  - 发现规则过时或有错，提出来修订，不要绕过。
- **冲突时**：`docs/` 和 `design/` 冲突时，以 `docs/` 的契约和代码为准，再回 `design/` 改记录。
- **界面原型**：界面工作以 `design/prototype/workbench-2026-11/` 为 1:1 基准（决策 014），代码还没完全跟上原型。
  - 打开方式见那个目录的 README（本机双击 `打开原型.bat`）。
  - 正式窗口是 WebView2，所以断行以 Edge 为准。

## 命令

以下命令都在仓库根执行。本机测试环境是 Python 3.12（Windows 上是 `py -3.12`），README 写的最低版本是 3.10。

```bash
# 本机版全量，约 1700 例；仓库在共享盘上，要跑几分钟
python -m unittest discover -s local/tests -p "test_*.py" -v
# 单个文件；加 -k 按用例名片段过滤
python -m unittest discover -s local/tests -p "test_signup_plan.py" -v
python -m unittest discover -s local/tests -p "test_signup_plan.py" -k <用例名片段> -v

# 服务器版：单独一类，不能冒充本机版验收
python -m pytest server/tests
python -m pytest server/tests/test_watchlist_safety.py -k <用例名片段>

# Node 离线测试：不连网，不读真实配置
node server/bot/test_bot_runtime.js
node server/bot/test_handled_messages.js
node server/deploy/test_atomic_json.js

# 语法检查；前端脚本拆成了多个文件，要逐个 node --check
python -m compileall local server
for f in local/ui/*.js local/ui/*/*.js; do node --check "$f" || break; done

# 代码结构：大小名单只读比对；名单只许变短
python tools/code_shape/check.py
# 开发依赖（ruff），不进安装包
python -m pip install -r requirements-dev.txt
# 只查不改的静态检查
ruff check local server tools

# 不登录，用假活动跑界面
python local/app.py --demo

# 发版：不带参数时只读检查；--prepare 只在本地构建，不打 tag、不上传
# --publish 是对外发布，必须用户授权
python tools/release.py --prepare
```

## 测试注意

- **不联网**：所有测试都替换掉了学校请求。部分用例按 `local.xxx` 导入，所以要从仓库根运行。
- **创建 `app.Api`**：新用例必须经过 `local/tests/fixtures/api_threads.py` 的 `stop_auto_relogin_on_cleanup`。原因是 `Api` 一构造就会启动自动重登线程；不收掉的话，全量会越跑越慢，计时类用例会变红。
- **时间**：
  - 学校时间字段按北京时间造（`time_contract.SCHOOL_TZ`）。
  - 业务时钟用 `FakeBusinessClock` 或 `configure_time_source` 注入，不读本机墙钟。
  - 不这样做，换个时区跑就会错位。
- **界面测试有两类**：
  - 契约测试：按 `index.html` 的加载顺序把脚本拼起来（`read_ui_scripts()`，不含 led.js），在拼接结果上做文本断言。
  - 行为测试：用 node 沙箱按同一顺序回放。本机没有 node 时会跳过，跳过要如实报告。
  - 界面契约测试按功能分在 `local/tests/test_ui_contract_*.py`，公共的读取函数和 node 沙箱在 `local/tests/fixtures/ui_harness.py`。
  - 新测试文件先把测试目录放进 `sys.path` 再 import fixtures，文件尾带 `unittest.main()` 入口。
- **脚本式的 server 测试**：`server/tests/` 里的 `test_dedup.py`、`test_endpoints.py`、`test_notify.py` 没有 `test_` 函数，pytest 收集不到。其中 `test_dedup.py` 会临时改写 `server/data/state.json`，不要跑。
- **临时目录**：一律放在 `tempfile.gettempdir()` 下面；server 测试也可以用环境变量 `CAMPUS_TEST_ROOT` 指定。
  - `<tmp>` 只是文档里的占位符，不是路径。夹具里出现 `<tmp>` 字面量就是缺陷，改成 `tempfile.gettempdir()` 不算「改测试路径凑绿」（用户 2026-11-06 定）。
- **不为变绿改测试**：除上面这种情况外，不改断言、不加 skip、不改测试路径。因为环境原因跳过或报错的用例（例如没装 webview），如实写进报告。

## 架构

### 两个产品，各自一份学校知识

- `local/`（Windows 图形界面）和 `server/`（Linux cron、systemd、飞书机器人）不共享运行时代码，两边各有一份 `site_target.py` 和学校请求代码。改学校接口契约时，两边都要查。
- 脱敏后的接口样例在 `contracts/school-api/`，`test_school_contract` 用它核对。
- 接口清单和 4001 失效的语义见 `docs/ARCHITECTURE.md`。

### 本机版：界面进程加一次性 worker 进程

- **界面进程**：`local/app.py` 是组合根。
  - pywebview 起窗时传入 `js_api=Api`，前端经 `window.pywebview.api` 调 `Api` 的方法。
  - 后端经 `evaluate_js("window.onBackend.<kind>(...)")` 往前端推 log、state、done 事件。
- **worker 进程**：要联网的事（check、list、grab、login）不在界面进程里做，每次都经 `worker_command()` 起一个新的 worker 进程。
  - 源码态是 `python local/grab.py <子命令>`。
  - 冻结态是打进资源根的 `grab-worker.exe`。它是 onefile 打包，每次启动都要先解包。
- **worker 输出就是协议**：
  - `list --json` 的 stdout 由 `app` 解析成 JSON。
  - 计划运行时的 `[retry]` 等行由 `domain/worker_lines` 和 `retry_rules` 解析。
  - 往 `grab.py` 加打印之前，先查清这一路输出是谁在解析。
- **报名计划**：
  - `signup_plan.PlanCoordinator` 按报名开放时刻分批，并检查举办时段冲突。
  - `application/plan_service` 启动并监督每一场的 worker。
  - 单场报名链路见 `docs/ARCHITECTURE.md` 的「报名链路（决策 015）」：以直发签名为主、点击兜底，回包分类，终态核对，登录失效时先复查再交接。
- **分层**：
  - 依赖只能向下：`domain/`（纯函数，不做 IO，不读墙钟）← `application/`（用例，依赖经端口注入）← `infrastructure/`（有副作用的适配器）。
  - 依赖由 `app.py` 注入，`test_layer_boundaries` 守着这条边界。
  - `app.py` 保留了一批旧的模块级名字作再导出，因为测试按 `app.X` 打补丁，重构时不要删。
- **时间**（决策 012）：
  - 业务时刻一律走 `business_clock`：公共 NTP 锚点加单调时钟，不读也不改系统时间。换算走 `time_contract`。
  - 界面进程经 `CAMPUS_CLOCK_SNAPSHOT` / `CAMPUS_CLOCK_OWNER` 把时钟快照交给 worker。
  - 时钟不可用时不能开始报名，登录和活动列表照常可用。
- **数据目录**：由 `runtime_paths` 决定。
  - 源码态在 `local/data/`，冻结态在 `%LOCALAPPDATA%\TianSoftActivityPreRegistration\data`，`CAMPUS_DATA_DIR` 可以覆盖。
  - 登录态只经 `grab.save_session` 写入，它用进程内锁加跨进程文件锁。
- **站点地址**：由 `site_target` 按下面的顺序取，取到即止。
  1. `SCHOOL_ORIGIN`
  2. `config.json` 的 `site.base`
  3. 构建时由 `tools/release.py` 生成的 `_site_build.py`（不入库）
  4. 占位地址。这时 `CONFIGURED=False`，所有学校动作直接拒绝。
- **前端**：
  - 没有打包器。`local/ui/index.html` 按 `<script>` 顺序加载 `state/`（唯一的状态仓库 `S` 和纯投影）、`views/`（DOM 呈现）、`controllers/`（编排和桥接）和 `app.js`（启动和事件分发）。加载顺序本身就是依赖关系。
  - 手机页在 `local/ui/m/`，由 `infrastructure/phone_http` 在 8765 端口提供。

### 服务器版

- **脚本**：`server/scripts/` 是 cron 拉起的一次性脚本。
  - `common.py` 是学校地址、会话读写、原子写、跨进程锁和业务时间的唯一来源。
  - `fetch.py` 拉取活动并做归一化。
- **去重**：用两份状态，互不覆盖。
  - `data/state.json` 的「已推送」只在推送成功后才写：锁内先占位，失败就回滚。
  - `data/activity_watch.json` 首轮只建基线，不发通知。
- **机器人**：`server/bot/bot.js` 只有 `BOT_ROLE=combined` 一个角色，一条长连接按 `chat_type` 分流。
  - 群里只读，只回答问题。
  - owner 私聊才会动手：预报名 → `watchlist.py` → `watchlist_runner.py` → 到点 `systemd-run grab_signup.py`。
- **部署**：`server/deploy/` 放登录守护 `server_refresh.js`、靠验证码识别做无人值守重登的 `auto_login.py`，以及 systemd 单元。部署和运维见 `docs/OPERATIONS.md`。

### 发版

- 版本号的真源是根目录的 `VERSION`。
- `tools/release.py --prepare` 构建一份冻结 EXE，再由同一份 EXE 派生出独立 EXE、四成员 ZIP、安装版和 manifest。
- `--publish` 要求三件事：在干净的 main 上，逐项核验资产，人工确认。

## 代码结构规则

这些规则由 `local/tests/` 的 `test_code_shape.py`、`test_layer_boundaries.py`、`test_ui_layers.py` 守着，量法、名单和命令的细节见 `tools/code_shape/README.md`。

- **大小**：
  - 新文件不超过 500 行，新函数不超过 60 行。
  - 存量超限的记在 `tools/code_shape/baseline.json`，只许变短，变长就红；超过 800 行的文件与超过 100 行的函数在名单里带一句理由。
  - 测试文件不限行数，单个测试函数（`test_` 开头）不超过 60 行。
  - 一个类里在三个及以上方法中赋值的实例属性不超过 5 个。
- **后端分层**：
  - `domain` 只 import 标准库和 domain；`application` 只 import 标准库、domain、application；这两层不 import 第三方包。
  - `infrastructure` 可以 import 标准库、第三方包、domain、infrastructure。
  - 三层都不 import `local/` 根目录下的模块，依赖由 `app.py` 注入。
- **前端分层**：
  - `state/` 不引用 `views/`、`controllers/`、`app.js` 里定义的名字。
  - `views/` 不引用 `controllers/`、`app.js` 里定义的名字，不发桥接请求。
  - 存量例外记在 `tools/code_shape/ui_layer_allow.json`。
- **名单只减不增**：
  - 不往 `baseline.json`、分层白名单、`ruff.toml` 的 `per-file-ignores` 里加项，确实需要时先问用户。
  - 消掉前端白名单的一项只有两种做法——把定义搬到正确的层，或者改成状态变了由视图订阅重画；不能把上层函数当参数或回调塞进下层。
  - 每发一版跑一次 `python tools/code_shape/check.py --tighten` 收紧记录值。
- **ruff**：只查不改，不用 `ruff format`，不用自动修复，不为消告警改存量代码。

## 提交规范

提交本身要先授权，见「共享工作区与授权」。

首行写 `type(scope): 结果`，`type` 用 feat / fix / docs / deploy / chore 之一。

正文只写 diff 里看不出的三件事，按这个顺序：

1. 改了什么，为什么改（根因）
2. **放弃了什么**，以及为什么放弃
3. **什么条件下会再坏**

尾注写一行：`Agent: <模型名>`。

**要短**：

- 首行冒号后不超过 25 个字，只写结果。
- 正文每段一两句，不用列表；不算尾注，全文不超过 200 字。
- 不复述 diff 里看得到的东西，比如改了哪些文件、加了哪些用例、搬了哪些章节。
- 写不短，多半是一次提交做了几件事，应该拆开提交。

## 文档与记录规范

### 不记录会被清理的路径

`<tmp>` 每周清理一次，写进文档的引用必然失效，等于留了一条死链。

- 不在文档、注释、CHANGELOG、决策记录里写 `<tmp>/...`，也不写任何临时目录下的具体文件路径。
- 记录验证过程时，写**日期、结论和复现命令**，不写「报告在哪个文件夹」。
- 需要留证据（截图、报告、对比结果）时，放进仓库的 `design/evidence/<YYYY-MM-DD>/`。
- 临时目录只出现在「怎么跑」的命令里，用 `%TEMP%`（Windows）或 `tempfile.gettempdir()`，**不写死盘符**。

理由不只是链接会失效。agent 会照着文档里的路径去读，读不到就自己编一个解释，再基于错误的前提改代码。

### 不写本机绝对路径

禁止写 `C:/Users/<用户名>/...`、`D:/Env/...` 这类只在某一台机器上成立的路径，改用 `~`、`%LOCALAPPDATA%` 或 `<占位符>`。

### 旧记录不追改

`CHANGELOG.md`、`design/decisions/`、`design/specs/` 里历史上写入的临时路径属于过程记录，不回改，改了就等于伪造记录。这条只约束新增内容。

### `@author` 标注

沿用文件原有的 `@author` 标注，不要改，也不要补。

## 参考

- 设计口径：`design/decisions/`，篇数和索引见 `design/decisions/README.md`。改动前先读对应的那篇。
- 数据流与模块职责：`docs/ARCHITECTURE.md`
- 版本号真源：`VERSION`
