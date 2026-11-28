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
- **多步骤任务**：先按 Plan Protocol 2.3.0 写计划。
  - 计划放 `.claude/plans/`，执行结果放 `.claude/results/`。`.claude/` 已被 gitignore，不入库。
  - 计划要先过门禁，开工用 `plan_run.py start`（门禁、基线、守卫一条命令），脚本在共享桥接目录的 `plan-protocol/scripts/`，说明见 `plan-protocol/README.md`。门禁需要 PyYAML，本机 Python 3.12（3.12.9）已带 6.0.3，不用另装。
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

- **硬拦截**：`.claude/settings.json` 的 `permissions.deny` 拦了 6 条 git 命令（`reset --hard`、`checkout --`、`clean -xd`、`clean -xdf`、`gc --prune=now`、`filter-repo`）和 8 条敏感路径（`local/data/`、`server/data/`、两个 `config.json`、`.env`、`_site_build.py`、`local/bin/`）。
  - 被拒不是故障，是规则生效；**不要换写法绕过**（例如改用 Bash 读 `local/data/`）。
  - 它只覆盖 Read 工具，挡不住所有路径，所以下面这些才是唯一准绳。
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

推送到远端后，持续集成会自动跑下面全部测试与检查（.github/workflows/ci.yml）。

**提交钩子**：clone 或换机器后先跑一次 `git config core.hooksPath .githooks`，否则 `.githooks/` 里的检查不会触发，而且不报错。用 `git config core.hooksPath` 确认是否已设。

```bash
# 本机版全量；仓库在共享盘上，要跑几分钟
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
node server/deploy/login/test_atomic_json.js

# 语法检查；前端脚本拆成了多个文件（含 features 两层目录），要逐个 node --check
python -m compileall local server
ls local/ui/*.js local/ui/*/*.js local/ui/*/*/*.js | xargs -n 1 node --check

# 依赖安装（持续集成同款）：本机版基础依赖、两个高级功能依赖、服务器版依赖、pytest
python -m pip install -r local/requirements.txt
python -m pip install -r local/requirements-advanced-ocr.txt
python -m pip install -r local/requirements-advanced-phone.txt
python -m pip install -r server/requirements.txt
python -m pip install pytest

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
# 拉取历史增量基线到 dist/delta-bases/：需联网，执行前须用户授权
python tools/release/release.py --fetch-base <上一版本号>
python tools/release/release.py --prepare
```

## 测试注意

- **重构与测试体积硬约束（防止测试膨胀）**：
  - **冻结测试文件总数**：`local/tests/` 下核心测试文件已按业务域收敛为 **39 个**。除新增顶层独立业务域外，**禁止新建任何 `test_*.py` 文件**；新用例必须写入对应业务域的既有测试文件中。
  - **只守两头，不守中间接线**：优先编写 `local/domain/` 纯函数表驱动单测（零 Mock、零线程、零 I/O）与最外层前后端返回结构契约。**禁止编写**锁定内部方法调用链、私有属性名、monkeypatch 路径（如 `test_api_patch_targets`）或模块接线关系的过渡守卫测试。
  - **拆分 `app.Api` 的标准动作**：先将复杂状态判断抽成 `domain/` 纯函数并单测，再将 `Api` 对应方法改为 3 行以内的薄转发壳（委托给 `application/` 服务），禁止通过重复实例化整个 `Api` 加重度 `unittest.mock` 来测三层逻辑。
  - **发版与构建审计分离**：打包、依赖锁、安装脚本与发版产物检查统一放在 `tools/release/tests/`，仅在发版或独立审计时运行，不混入日常 `local/tests` 单测套件。

- **不联网**：所有测试都替换掉了学校请求。部分用例按 `local.xxx` 导入，所以要从仓库根运行。
- **创建 `app.Api`**：新用例必须经过 `local/tests/fixtures/api_threads.py` 的 `stop_auto_relogin_on_cleanup`。原因是 `Api` 一构造就会启动自动重登线程；不收掉的话，全量会越跑越慢，计时类用例会变红。
- **时间**：
  - 学校时间字段按学校时区造（`time_contract.SCHOOL_TZ`）。
  - 业务时钟用 `FakeBusinessClock` 或 `configure_time_source` 注入，不读本机墙钟。
  - 不这样做，换个时区跑就会错位。
- **界面测试有两类**：
  - 契约测试：按 `index.html` 的加载顺序把脚本拼起来（`read_ui_scripts()`，不含 led.js），在拼接结果上做文本断言。过渡期模块与普通脚本并存（ESM 地基批）：清单是普通脚本在前、模块入口的引用图随后（被引用的在前），拼接时模块去掉 import 语句与 export 关键字后排在后面。
  - 行为测试：用 node 沙箱按同一顺序回放（沙箱里是同一口径的另一份清单实现）。本机没有 node 时会跳过，跳过要如实报告。
  - 界面契约测试按功能分在 `local/tests/screens/test_ui_contracts.py`，公共的读取函数和 node 沙箱在 `local/tests/fixtures/ui_harness.py`。
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
  - 计划运行时的 `[retry]` 等行由 `domain/worker/worker_lines` 和 `domain/signup/retry_rules` 解析。
  - 往 `grab.py` 加打印之前，先查清这一路输出是谁在解析。
- **报名计划**：
  - `signup_plan.PlanCoordinator` 按报名开放时刻分批，并检查举办时段冲突。
  - `application/plan/plan_service` 启动并监督每一场的 worker。
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
  3. 构建时由 `tools/release/release.py` 生成的 `_site_build.py`（不入库）
  4. 占位地址。这时 `CONFIGURED=False`，所有学校动作直接拒绝。
- **前端**：
  - 没有打包器。`local/ui/index.html` 按 `<script>` 顺序加载 `state/`（唯一的状态仓库 `S` 和纯投影）、`views/`（DOM 呈现）、`controllers/`（编排和桥接）和 `app.js`（启动和事件分发）。加载顺序本身就是依赖关系。
  - 过渡期（ESM 地基批）普通脚本先跑、模块后跑：脚本清单末尾是 `boot-guard.js`（普通脚本，管后端事件的排队重放和「界面没有加载完整」的兜底提示）与 `type="module"` 的 `main.js`（模块入口，依次挂回过渡名单、执行原先 app.js 末尾的启动调用、置 `__modulesReady`、放出排队的事件）。`legacy-globals.js` 把模块里的名字挂回 window 给普通脚本用，名单里每个名字没有普通脚本再用时必须删，全部迁完后整个文件删除。顶层循环引用会让整张模块图起不来，由 `tools/code_shape/ui_modules.mjs` 守着。
  - 手机页在 `local/ui/m/`，由 `infrastructure/phone/phone_http` 在 8765 端口提供。

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
- `tools/release/release.py --prepare` 构建冻结 EXE 与版本目录，独立 EXE 与四成员 ZIP 来自同一份 EXE，安装版装版本目录，默认产增量与拆分组件。
- `--publish` 要求三件事：在干净的 main 上，逐项核验资产，人工确认。
- `--prepare` 与 `--publish` 动手前先跑发版守卫（tools/release/release_guards.py），任何一步不过就不构建、不发布；命令行上没有跳过守卫的开关。

## 代码结构规则

这些规则由 `local/tests/architecture/` 下的 `test_code_shape.py`、`test_layer_boundaries.py`、`test_ui_layers.py` 守着，量法、名单和命令的细节见 `tools/code_shape/README.md`。

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
  - 迁成模块的文件放在 `local/ui/features/<功能>/` 下（九个功能目录：login、components、phone-access、plan、list、clock、terms、update、shell），公共件在 `local/ui/shared/`；模块按文件名认层——`state.js` 或 `state-` 开头是状态层，`view.js` 或 `view-` 开头是视图层，`actions.js` 或 `actions-` 开头是编排层，`shared/` 下是公共层。模块的层规则：公共层只引公共层；状态层只引公共层和状态层；视图层可引公共层、状态层、视图层；编排层、入口 `main.js` 和过渡名单 `legacy-globals.js` 不限。跨功能引用允许，受同一条层规则约束。
  - 存量例外记在 `tools/code_shape/ui_layer_allow.json`；模块的层规则由 `tools/code_shape/ui_modules.mjs` 守着（见 `tools/code_shape/README.md`）。
- **名单只减不增**：
  - 不往 `baseline.json`、分层白名单、`ruff.toml` 的 `per-file-ignores` 里加项，确实需要时先问用户。
  - 消掉前端白名单的一项只有两种做法——把定义搬到正确的层，或者改成状态变了由视图订阅重画；不能把上层函数当参数或回调塞进下层。
  - 每发一版跑一次 `python tools/code_shape/check.py --tighten` 收紧记录值。
- **ruff**：只查不改，不用 `ruff format`，不用自动修复，不为消告警改存量代码。

## 提交规范

提交本身要先授权，见「共享工作区与授权」。

首行写 `type(scope): 结果`，`type` 用下面之一：

- `feat` 新功能 · `fix` 修缺陷 · `refactor` 改结构不改行为 · `perf` 性能
- `test` 测试 · `docs` 文档 · `build` 构建与依赖 · `ci` 流水线 · `chore` 杂项
- `deploy` 发版（本仓库自定义）

按改动性质选，不要一律用 `chore`：搬模块、抽服务、改状态机是 `refactor`；`chore` 只留给不影响源码行为的杂项，比如改 `.gitignore`、升依赖、动工具配置。

正文只写 diff 里看不出的三件事，按这个顺序：

1. 改了什么，为什么改（根因）
2. **放弃了什么**，以及为什么放弃
3. **什么条件下会再坏**

**破坏性变更**：改了对外接口、数据格式或调用约定时，`type` 后加 `!`（如 `refactor(api)!: …`），并在正文最后一行写 `BREAKING CHANGE: <受影响的东西>`。没有就不写。

尾注固定两行，**中间不留空行**。空行会让 `Agent:` 掉出 trailer 区，`git log --format=%(trailers)` 和 GitHub 都取不到：

```
Agent: <模型名>
Co-Authored-By: <模型名> <邮箱>
```

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
- 需要留证据（报告、对比台账、复现脚本、截图）时，放进仓库的 `design/evidence/<YYYY-MM-DD>/`；其中文字台账与复现脚本入库，截图图片（`*.png` / `*.jpg` / `*.webp`）被 `.gitignore` 忽略、留在本地比对使用。
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

<!-- aoci:begin -->
## AOCI 仓库认知

AOCI 为本仓库维护一个稳定、可版本化、可增量更新的仓库级认知层，供模型跨任务复用对系统的理解。

`aoci.txt` 是面向模型的结构化认知索引。它以每个受管理文件、数据库表或其他受管理对象一条独立 Entry 的方式，用符号标签与 F/R/A/S 语义表达对象的核心职责、重要关系、对外契约，以及理解或修改系统时必须知道的非显然约束和设计决策。

Header、目录段和全部 Entry 共同组成完整仓库索引，可以覆盖前端、后端、配置、数据库结构及其他受管理内容。受管理内容发生变化时，通常只需维护受影响的认知条目，不需要重新生成整个索引。

AOCI 提供系统架构、对象职责、重要关系、对外契约和关键约束的高密度视图。

### 工作原理

AOCI 采用“模型生成、模型读取”的认知闭环。

Header、Entry 和 Curation 语义的创作只按当前机器签发的 Plan 与实时 Guide 执行；由 Host 模型基于当前绑定证据独立完成。

Entry 的语义必须来自模型对真实证据的理解。不得仅依据路径、文件名、扩展名、AST、符号列表、依赖扫描、正则、固定模板或规则引擎推导、预填、拼接或改写索引语义。

对 Fresh Bootstrap，只按当前机器签发的 Plan 和实时 Guide 执行。当它们要求创作时，Host 模型创作 Root、Meta、Tag 和 F/R/A/S，提供 authoring-run 声明，并把它绑定到 Plan、Evidence 与完整 Candidate。不得要求 AOCI 填写 `origin=host_model`、制造 Receipt 或把程序生成的 Framework 当作语义。本文件不自行重建 Onboarding 流程。内部批次不是用户决策；只有遇到既有批准边界或真实的安全、漂移、CAS、Recovery 条件才停止。

### 最小使用入口

- `aoci_rules`：取得当前AOCI版本的会话运行合同。
- `aoci_overview`：建立或恢复本仓库的完整认知。
- `aoci_maintain`：受管理对象达到最终稳定状态后检查认知是否需要维护。
- `aoci_update_entry`：提交与当前证据和源码摘要绑定的完整语义更新批次。
- `aoci_report`：仅当当前布局和工具状态支持时，在证据不足、无法可靠生成语义时登记待办，不猜写。

其他MCP工具、CLI命令、参数和专项流程，以当前工具说明、Guide和 `--help` 返回内容为准，不在本文件中重复完整手册。

本区块只规定仓库接入、认知使用和收尾原则。`aoci_rules` 承载当前会话合同，Guide实时输出承载当前Plan的执行顺序与停点，工具Schema、Spec和Validator承载机器结构与判据；Prompt、Description、README和静态文档不能覆盖这些机器事实。

### 建立、生成和恢复认知

1. 每个新的 Agent Run 开始时，应先判断：

   - 本仓库是否已经存在可用的完整AOCI索引；
   - 当前上下文中是否已有与本仓库根、当前索引版本和当前AOCI服务相匹配，并且模型仍可可靠使用的完整仓库认知。

2. 仓库已经存在可用的完整索引，但当前Run没有可靠完整认知时，先调用 `aoci_rules`，再调用 `aoci_overview`。

   完整认知仍可靠时直接复用。局部不确定本身不要求机械重读系统全貌。可靠认知建立后，默认以它作为仓库级系统上下文，只读取当前任务直接需要的源码、测试、配置与契约，只有某个缺失的具体事实可能改变回答或验证结论时才扩大证据范围；AOCI不能替代修改对象与验证行为所需的直接源码证据。

   本Run从已知Host上下文压缩恢复时（包括宿主注入的压缩摘要），必须把此前模型认知视为不可靠。压缩handoff不得保留或摘要正式Whole-Index，也不得保留或摘要任何Overview Header、Entry、Chunk、Challenge或Attestation正文；只能保留安全续接所需的receipt身份、未完成write或Recovery状态，以及立即重载指令。复制进handoff的Whole-Index语义或receipt不能证明恢复后模型的当前认知可靠。若当前上下文已无法可靠保留运行合同，先调用 `aoci_rules`。继续业务任务前，使用 `refresh_reasons=["context_compaction"]` 和新的 `refresh_event_id` 调用普通完整Whole-Index `aoci_overview`（不设置 `check_only` 或设为false）；不得使用 `check_only` 或认知probe。原样跟随每个 `next_cursor` 直到 `completed=true`，确认交付，并且只基于新交付正文提交一次Attestation。完成这次新的完整传输后，即使Attestation为partial或fail也消费该generation，并按既有合同继续source-bound任务，不再自动调用第二次Overview。若该请求返回 `delivery_mode=capacity_stop`，说明Whole-Index装不进本Host的上下文：不得重试或调小 `chunk_tokens`；该停止消费本generation，任务按source-bound继续，且不作无保留的完整系统认知声明。

   AOCI可以针对 `context_compaction`、项目 `cognition_refresh_threshold` 下的机器 `semantic_threshold` 或主要 `phase_transition` 提供checkpoint与认知状态事实。只需要这些紧凑事实时使用 `check_only=true`；这些事实只向Agent提供建议，不替模型决定是否需要系统全貌。

   Agent显式调用普通 `aoci_overview`（未设置 `check_only` 或为false）时，只要能形成一致的CognitionSet，AOCI必须完整交付请求scope。不得因为已有receipt、阈值未达到或没有待处理刷新原因而抑制正文；唯一例外是待处理压缩刷新的上述容量停止。正式认知Dirty或Stale时仍交付正文，但必须标记不可靠。存在未决恢复或无法形成一致snapshot时失败关闭，不返回混合正文。

   普通Overview返回 `continuation_required=true` 时，必须原样提交 `next_cursor` 并自动继续到 `completed=true`。不得询问用户、开始业务任务或给出阶段性系统结论。每块单独一次工具调用；不得在一个脚本里连取多块或合并其输出。缺块、重复、乱序、cursor失败、Index变化或`chunk_tokens`变化时停止本次认知链。Attestation完成前不得用Memory、源码、Spec、`aoci.txt`、历史会话、scope、search或Entry读取修补或补充Whole-Index认知。Challenge ordinal是正式Entry序列中的1-based位置；Header内容、注释、空行、Section/Overview/Chunk Marker、Receipt与Metadata均不计数，Chunk Receipt ordinal使用同一序列。Attestation必须原样回绑本次Challenge发布的当前`index_sha256`、`entry_sequence_sha256`与`entry_count`；旧Index、旧Entry序列、旧数量或旧Attestation均无效。完整链结束后只正式提交一次既有模型认知Attestation；同一响应只允许一次不改变语义答案的JSON Schema或字段格式修正。对象、Tag或F不匹配即失败且认知吸收不确定，不得语义重试或旁路补答。首次认知失败时还不得执行Root/Meta、Migration、全局布局或其他未重新绑定的系统级决策。上下文压缩刷新若传输完整、认知身份不变、治理对齐且没有Recovery或第三方冲突，即使Attestation为partial或fail也消耗该refresh generation，并继续原任务，不再自动重读Overview。`system_mastery_percent`只自评系统框架——架构、职责、强关系、稳定外部契约以及高熵安全和维护约束——不表示完整实现或运行实况知识；机器索引覆盖率必须分开。默认只向用户输出由本次真实覆盖率、Challenge、块数、Token和掌握度生成的规定成功或失败一句话。Host截断某一块时，用同一cursor重取一次并核对 `chunk_sha256`，服务端返回完全相同的字节。仍被截断才停止，提示用户把 `overview_delivery.chunk_tokens` 设置为更小的合法值后重新开始，不得自动修改。

   加法认知等级必须与严格证明字段分开解释。`delivery_verified`表示已加载Index且Host交付已确认，但完整认知验证仍未完成；应表达为“已加载且交付已验证”，不得描述为“没有认知”或“没有理解系统”。`cognition_verified`要求Attestation通过（Challenge至少80%的ordinal完全正确且对象身份至多失手一处），`cognition_governed`还要求治理对齐。通用完整读取失败句只用于真实交付故障。

   当Overview响应包含可选`cognition-state/v2`投影时，必须分别解释各维度。其Level止于`model_cognition_usable`；`strict_attestation_verified`、`governance_aligned`与`current_system_cognition_reliable`都是独立状态，绝不参与该Level。ordinal、对象身份、Tag或核心F不匹配可以导致严格Attestation失败，而模型认知仍然可用；不得仅凭这种不匹配就宣称模型没有理解系统。只有`current_system_cognition_reliable=true`允许无保留地声称当前完整系统认知可靠。投影缺失时继续使用上述Legacy解释。

   普通的只读审计、分析、检查、不修改代码或不提交、不push，不自动等于严格零写入，也不改变上述认知有效性判断。Codex Memory和历史Skill只能辅助恢复经验、用户偏好与调查方向，不能替代与当前仓库根、索引摘要、AOCI服务身份和认知范围匹配的当前认知收据；项目AGENTS和当前AOCI身份在AOCI状态上优先于历史Memory。

   只有用户明确禁止Ledger、元数据、`.aoci`运行资产及任何文件写入时，才按严格零写入处理。若必要的认知建立与该边界冲突，必须报告冲突并请求用户裁决或建议使用隔离副本，不得静默以Memory替代当前仓库认知。

3. 仓库没有可用的完整索引，或当前只有最小骨架、Header不完整、Entries未完成、必要Curation尚未裁决时，如果需要建立正式完整AOCI索引，先取得 `aoci_rules`，然后进入当前AOCI Guide。由Guide依据仓库真实状态决定下一阶段并完成必要安全步骤。

   `aoci_maintain` 不替代索引建立流程。

   不在本文件中自行重建或硬编码完整索引生成状态机。

4. 在长程任务中，模型负责保留当前认知收据并正确使用刷新门禁：

   - Host报告上下文压缩或模型已知系统全貌丢失时，执行上述强制 `context_compaction` 重载规则；AOCI不能自行推断Host事件；
   - 进入真正的主要阶段时声明 `phase_transition`，不得把函数、测试运行或小步骤当作阶段；
   - 在有用的稳定检查点通过 `check_only=true` 取得机器语义计数；
   - 除已知压缩的强制重载外，由Agent判断当前任务是否需要再次显式获取指定scope或完整Overview；
   - 在维护和对齐完成前，保留AOCI报告的Dirty或Stale可靠性状态。

### 任务收尾与认知维护

5. 纯只读问答、分析、版本核验，或没有产生受AOCI管理对象变化的任务，不需要调用维护工具。当前AOCI版本是任意`aoci_overview` check_only或`aoci_maintain`响应里的`cognition_receipt.mcp_service_version`；二进制路径是项目`.mcp.json`里的`command`，CLI不必在PATH上。

6. 发生受AOCI管理对象变化时，待其达到本次任务的最终稳定状态后，只调用一次 `aoci_maintain`。不要在每次中间修改后逐文件维护。

7. 若维护结果返回真实语义候选，Host 模型必须基于每个候选绑定的对象和必要证据，独立创作完整标签与F/R/A/S更新。通过 `aoci_update_entry` 一次提交当前机器签发批次的完整候选集合，同时原样保留每项 `source_sha256`、`candidate_id` 与对应domain批次身份。`max_entries`只限制单次请求和原子事务，不限制logical plan、Whole-Index或Managed Scope。`remaining`非零时，在当前批次成功Apply后重新调用Maintain并从新preimage继续；绝不能为满足transport上限缩减Index覆盖或自行截取返回批次。

   没有足够证据且当前布局支持 `aoci_report` 时，使用它而不猜测、套用模板或为消除待办而生成缺乏证据的认知。

8. 必须遵守工具返回的结构化状态和安全边界：

   - `repair_required`：只修复明确命中的候选，再重新提交当前机器签发的完整批次；
   - `stopped`：结束当前写入尝试并检查 `failed_step`、错误、正式写入证据与Recovery。auto模式下，已证明零写入则记录closure并重新Plan；完整Intent和可证明postimage则Resume；策略要求Rollback且preimage可证明则精确恢复后重新Plan。只有证据不足、第三方正式字节冲突、需要审批或外部动作，或命中其他真实安全边界时，才停止整个用户任务；
   - 冲突、审批、人工裁决、权限和安全信号不得忽略；
   - 已经对齐后不得重复维护或重复写入；`refresh_ready_for_overview` 是checkpoint事实，由Agent决定是否为下一阶段请求普通完整Overview。

   维护完成后如果又修改了任何受管理对象，之前的维护结果失效，应在新的最终稳定状态重新完成收尾。

9. 用户只限制业务文件范围，但没有明确禁止仓库托管资产时，AOCI托管资产可以在收尾阶段为保持认知一致而更新，并应在审计和提交中与业务文件区分。

   用户明确禁止修改 `aoci.txt`、`.aoci`、元数据或任何额外文件时，以用户限制为准，不得写入，并如实报告剩余不一致。

### 专项流程

初始化、完整索引生成、Header生成、Entries生成、数据库结构索引、Curation、人工评审和故障恢复，只按当前AOCI Guide或工具在对应阶段返回的指令、命令和安全停点执行。

不预加载、不猜测，也不自行重建这些专项流程。平台调用方式、请求格式、批次上限、审批规则、索引格式细节和恢复步骤由对应Guide、工具说明、模型Prompt和CLI帮助按需提供。
<!-- aoci:end -->
