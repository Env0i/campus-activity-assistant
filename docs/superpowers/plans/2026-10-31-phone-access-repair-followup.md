# 手机访问返修与验收收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收口 `20261031-phone-access-repair` 的计划越界与计划外改动，并修复 Cloudflare 组件信任、手机重登异常恢复、后台隐藏唤回和关窗默认焦点，使自动化结果与真实产品行为一致。

**Architecture:** 保留现有 `local/ui → local/app.py → application/domain/infrastructure` 分层。手机仍只是电脑的远程控制台，学校请求、报名计划和重登状态由电脑端裁决。本计划只修补已经实现的路径，不重做手机控制台的信息架构，不改变学校接口、登录态文件形状或通道生命周期决策。

**Tech Stack:** Python 3.10+、标准库 `unittest`、pywebview/WebView2、HTML/CSS/JavaScript、Node vm 行为测试、现有组件 ZIP/manifest 校验、Windows WinForms 托盘适配。

## Global Constraints

- 只服务当前用户本人账号；不增加多账号、批量占位或未明确指定活动的报名能力。
- 手机发出的仍是电脑动作；手机不直接访问学校接口，不新增手机侧业务模型。
- 远程入口只有 Tailscale 与 Cloudflare Quick Tunnel；不增加普通局域网、公网 IP 或 IPv6 入口。
- Tailscale 设备信任可跨程序/电脑重启恢复；Cloudflare 每次重新开启都要重新扫码和配对。
- `phone_control` 与 `relogin_ocr` 继续独立按需安装、校验、移除；不自动下载、升级或安装组件。
- 手机验证码没有倒计时和提交次数上限；同一挑战的提交仍由后端 singleflight 防重复，错误由学校响应触发换图。
- `TOTAL_BUDGET_S = 600` 是整个 relay worker 的安全运行上限，不等于验证码倒计时或提交次数上限；本计划保留它，不在没有新证据和用户决定时移除。
- 不放宽生产 PNG 校验；测试夹具必须使用合法 PNG。
- 不把账号、密码、验证码、配对码、cookie 值、token、原始异常或 IP 写入日志、文档、提交信息或 UI 快照。
- 不引入新依赖；不修改 `local/data`、`server/data`、`.venv`、`node_modules`、服务器版代码或学校接口契约。
- 修改含中文文件后做严格 UTF-8 解码和乱码黑名单检查；保持原文件行尾，不做全文件格式化。
- 本计划默认不提交 Git；执行、自动化验证、真机验收和提交状态必须分开记录。

## 审计结论与返修目标

1. **amendment-003 是真实范围越界。** `local/build_advanced.py` 是 task-6 的必要实现文件，不能只留在结果说明里；返修计划把它正式纳入 allowed paths，并补上缺失的构建门禁。
2. **amendment-005 是测试夹具错误，不是生产逻辑错误。** `local/domain/phone_rules.py` 已正确拒绝没有 PNG 魔数的图片；把 `data:image/png;base64,AAAA` 换成合法的一像素 PNG，不能为了让旧断言变绿而放宽生产校验。
3. **Cloudflare 组件仍有信任边界缺口。** `build_advanced.py` 允许 `phone_control` 不带 `cloudflared`，`resolve_cloudflared()` 还会回退到 PATH 或未经过 manifest/hash/probe 的文件。返修后只有通过组件 manifest、文件哈希和版本探测的二进制才能作为 Cloudflare 执行文件。
4. **手机重登有两个状态缺陷。** 网络异常只显示“提交结果未知”却不主动对账，可能把提交按钮永久禁用；`verifying` 状态又被当前 UI 当作终态，可能过早隐藏验证码和重新开始入口。返修用显式 `submit_pending` 状态和状态驱动的 UI 收口，既防重复提交，也给丢包后可恢复的重试机会。
5. **隐藏到后台有安全性缺口。** 托盘创建失败、手机访问也没有可用会话时，当前代码仍会把窗口藏起来，用户没有可靠唤回入口。返修要求没有唤回路径时拒绝隐藏并给出可操作提示。
6. **关窗“默认最小化”没有落到焦点行为。** 对话框虽然已经改成竖排，但没有真正把“最小化到任务栏”设为默认焦点。返修只补焦点和行为测试，保留现有桌面视觉风格与四个出口。
7. **计划外隐藏/托盘/对话框改动本身方向正确。** `ApplicationContext()` 已消除托盘白框，后台隐藏也没有改变报名计划线程；返修只把它们纳入正式范围并补安全门禁，不重新设计整套托盘。

## UI design lock（返修只做收口，不另起视觉语言）

- 继续使用桌面现有色板和字体：`--paper`、`--line`、`--blue`、`--bad`、Microsoft YaHei UI。
- 关窗对话框保持白纸、细边线、竖排选择行；危险的“直接退出”继续使用现有 `--bad`，焦点环使用现有 `--blue`。
- 默认焦点落在“最小化到任务栏”，因为它保留任务栏唤回且不会停止手机访问；“隐藏到后台运行”只有在存在托盘或已配对手机会话时才可执行。
- 手机重登状态只增加“正在验证…”和“提交状态未知，正在核对…”这类状态文案，不增加新的卡片层级、渐变、图标字体或动画。

示意结构：

```text
┌ 要关闭这个窗口吗？ ─────────────────┐
│ 选择会影响手机访问和报名计划的去向。   │
│                                      │
│   隐藏到后台运行  （有唤回入口才可用） │
│ ● 最小化到任务栏  （默认焦点）         │
│   直接退出        （危险）             │
│                                      │
│ □ 以后都这样                 先不关    │
└──────────────────────────────────────┘
```

### Task 1: 固化 phone_control 与 cloudflared 的组件边界

**Files:**
- Modify: `local/build_advanced.py`
- Modify: `local/infrastructure/component_packages.py`
- Modify: `local/infrastructure/tunnel_manager.py`
- Test: `local/tests/test_component_builder.py`
- Test: `local/tests/test_component_packages.py`
- Test: `local/tests/test_tunnel_manager.py`

**Root cause:** 构建脚本的 `--cloudflared` 是可选参数；manifest 允许 `phone_control` 没有 `bin/cloudflared.exe`。运行期 `resolve_cloudflared()` 又会从 `resource_root/bin`、解释器目录和 PATH 找任意同名文件，绕过组件的完整性边界。

**Target behavior:**

- `phone_control` 构建没有 `--cloudflared` 时立即失败，错误码/文案明确为 `cloudflared_required`；不生成半可用 ZIP。
- `phone_control` manifest 必须同时声明 `cloudflared.version`、`cloudflared.sha256` 和 `bin/cloudflared.exe`，且版本固定为当前已批准的 `2026.10.7`。
- `relogin_ocr` 不得携带 cloudflared 文件或字段。
- `component_packages.cloudflared()` 继续执行 manifest、文件哈希和 `--version` probe；`tunnel_manager.resolve_cloudflared()` 只返回该函数通过校验的路径，删除 PATH 和未校验目录回退。
- Tailscale 不依赖 cloudflared；缺少 Cloudflare 组件时只禁用 Cloudflare 通道，不把手机控制整体标成不可用。

**Implementation steps:**

- [ ] 先在 `test_component_builder.py` 增加“phone_control 缺 `--cloudflared` 必须失败”和“版本不匹配必须失败”的测试。
- [ ] 在 `build()` 的 phone_control 分支加入等价逻辑：

```python
if feature == "phone_control" and not cloudflared:
    raise ValueError("cloudflared_required")
```

保留现有 `--version`、复制文件、SHA256 和 manifest 生成流程。
- [ ] 在 `_manifest()` 中把“phone_control 必须有 cloudflared 元数据和文件”写成硬门禁；不能通过省略字段规避。
- [ ] 在 `test_component_packages.py` 增加缺文件、缺 metadata、哈希错误、版本错误、probe 失败和独立移除测试；确认旧组件在新包验证失败时仍保留。
- [ ] 删除 `resolve_cloudflared()` 对 `shutil.which()`、`resource_root/bin` 和解释器目录的无条件回退；保留函数参数兼容性时，参数只用于测试/调用兼容，不得改变信任来源。
- [ ] 在 `test_tunnel_manager.py` 把原来的 PATH 回退断言改成“PATH 中有 cloudflared 也返回空串”，并增加“合法组件路径才返回”的测试。

**Verification:**

```powershell
python -X utf8 -m unittest local.tests.test_component_builder local.tests.test_component_packages local.tests.test_tunnel_manager -v
```

### Task 2: 修复合法 PNG 测试夹具并保持生产校验严格

**Files:**
- Modify: `local/tests/test_retry_phone_integration.py`
- Modify: `local/tests/test_login_relay_service.py`
- Modify: `local/tests/test_phone_ui.py`
- Test: `local/tests/test_retry_phone_integration.py`
- Test: `local/tests/test_login_relay_service.py`
- Test: `local/tests/test_phone_ui.py`

**Root cause:** 工作区里的 `phone_rules.project_text()` 已按设计拒绝没有 PNG 魔数的图片，但多处测试把 `data:image/png;base64,AAAA` 当成合法图片；因此全量测试出现 1 条失败，且其它测试继续掩盖了不真实的 worker 事件。

**Implementation steps:**

- [ ] 在每个需要图片的测试文件中使用同一个合法一像素 PNG 数据 URI：

```text
data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==
```

- [ ] 只替换测试输入，不改 `local/login_relay.py`、`local/domain/phone_rules.py` 的 PNG 魔数、base64 严格解码和大小限制。
- [ ] 增加一条反向测试：非 PNG 魔数仍会被投影为空，确保这次修夹具没有放宽生产边界。

**Verification:**

```powershell
python -X utf8 -m unittest local.tests.test_retry_phone_integration local.tests.test_login_relay_service local.tests.test_phone_ui -v
```

### Task 3: 修复手机重登网络异常与 verifying 状态

**Files:**
- Modify: `local/application/login_relay_service.py`
- Modify: `local/ui/m/app.js`
- Test: `local/tests/test_login_relay_service.py`
- Test: `local/tests/test_phone_ui.py`

**Root cause:** `submitRelogin()` 的网络异常分支只写提示，不触发状态对账；而 `ingestRelogin()` 把除了 `waiting_code` 和 `success` 以外的状态都当成终态，`verifying` 会被过早收口。

**Target behavior:**

- 后端公开状态新增无敏感信息的 `submit_pending` 布尔字段；终态始终为 `false`。
- 网络异常后不立即发第二次提交：先保留禁用态并调用一次 `poll(true)` 对账。
- 对账发现同一验证码仍为 `waiting_code` 且 `submit_pending=false` 时，恢复提交按钮；如果 `submit_pending=true` 或状态为 `verifying`，继续禁用，等待明确结论。
- `verifying` 显示“正在验证验证码…”，保持当前挑战的上下文，不显示“重登结束”，不重新显示“开始重登”。
- `success/failed/canceled/idle` 才调用 `endReloginControls()`；新挑战自动清除旧提交状态。

**Implementation steps:**

- [ ] 在 `public_state()` 增加 `submit_pending`；`flow is None`、终态和无当前提交时均为 `false`。
- [ ] 在 `ingestRelogin()` 的同挑战分支按 `submit_pending` 更新 `model.reloginSubmitting`，不要因为一次轮询就盲目解禁。
- [ ] 单独处理 `info.state === "verifying"`：写“正在验证验证码…”，保留取消入口，提交按钮由 `reloginSubmitting=true` 禁用。
- [ ] 在 `submitRelogin()` 的 `catch` 分支保留当前提交锁、写“提交结果未知，正在核对…”并 `void poll(true)`；不能直接把锁清掉造成重复提交竞态。
- [ ] 只有后端明确回到 `waiting_code + submit_pending=false` 或返回拒绝/新挑战时才解除提交锁；后端永远保留 `_send_submit()` 的 duplicate guard。
- [ ] 用行为测试覆盖：网络异常不立即发第二个 POST；`submit_pending=true` 不解禁；`verifying` 不被当成终态；明确拒绝后可以提交下一张验证码。

**Verification:**

```powershell
python -X utf8 -m unittest local.tests.test_login_relay_service local.tests.test_phone_ui -v
node --check local/ui/m/app.js
```

### Task 4: 给后台隐藏增加唤回门禁，并落实默认最小化焦点

**Files:**
- Modify: `local/application/phone_service.py`
- Modify: `local/app.py`
- Modify: `local/infrastructure/tray_icon.py`（只在测试需要暴露生命周期时最小修改）
- Modify: `local/ui/controllers/window.js`
- Modify: `local/ui/index.html`
- Modify: `local/ui/styles.css`（只补必要的 disabled/focus 状态）
- Test: `local/tests/test_application_services.py`
- Test: `local/tests/test_phone_service.py`
- Test: `local/tests/test_ui_contract.py`

**Root cause:** `hide_window()` 在托盘创建失败时仍继续隐藏；手机服务是否运行也不能证明已有可用的手机会话。这样用户可能点了隐藏后既没有任务栏按钮、又没有托盘、也没有手机唤回入口。关窗对话框虽然竖排，但没有设置“最小化”为真实默认焦点。

**Target behavior:**

- `PhoneAccessService` 提供只读的 `has_live_session()`（按现有 8 小时 session TTL 判断，不返回 cookie/token）。
- `hide_window()` 只有在“托盘成功”或“至少一个已配对手机会话仍有效”时才允许执行；两者都没有时返回 `hide_unavailable`，窗口保持可见，提示“请先配对手机或选择最小化”。
- `ApplicationContext()`、无白框托盘和手机 `show_window` 入口继续保留；不引入 `pystray` 或开机自启。
- 打开关窗 dialog 后，`btn-close-minimize` 具有 `autofocus`，并在 `showModal()` 后用现有焦点 API 再确认一次；浏览器不支持 dialog 时也不抛异常。
- 现有竖排选择行、危险色和 44px 以上可操作区域不变。

**Implementation steps:**

- [ ] 在 `PhoneAccessService` 增加 `has_live_session()`，锁内调用现有 `session_alive()`，过期会话不算唤回路径。
- [ ] 在 `hide_window()` 中先尝试 `_ensure_tray()`，再检查 live session；没有任何路径时返回结构化失败，不调用 `window.hide()`。
- [ ] 在 `test_application_services.py` 覆盖：托盘成功可隐藏、托盘失败但有 live session 可隐藏、两者都没有必须拒绝隐藏、拒绝后窗口状态不变。
- [ ] 在 `local/ui/index.html` 给最小化选项加 `autofocus`；在 `openWindowCloseDialog()` 中 `showModal()` 后调用 `minimize.focus()`，调用前判空。
- [ ] 在 `test_ui_contract.py` 增加默认焦点和 `ApplicationContext()` 静态守护；保留“不得回到 `Application.Run(form)`”的断言。
- [ ] 在 `test_phone_service.py` 覆盖 live session 过期/有效两种情况，不输出敏感 cookie 值。

**Verification:**

```powershell
python -X utf8 -m unittest local.tests.test_application_services local.tests.test_phone_service local.tests.test_ui_contract -v
node --check local/ui/controllers/window.js
```

### Task 5: 同步用户文档与帮助文案，消除旧分发口径

**Files:**
- Modify: `docs/PHONE_ACCESS.md`
- Modify: `local/README.md`
- Modify: `local/ui/index.html`
- Modify: `local/ui/views/phone.js`（只有现有状态文案仍把 PATH 当成产品入口时才改）
- Test: `local/tests/test_ui_contract.py`

**Required copy changes:**

- Cloudflare 使用的 `cloudflared` 随匹配版本的 `phone_control` 组件包提供；不再写“用户自行放 PATH/安装包 bin”。用户必须明确导入组件 ZIP，程序不自动下载或升级。
- Tailscale 仍是长期通道；Cloudflare 仍是临时 Quick Tunnel，重启或重新开启后地址改变并重新配对。
- “隐藏到后台运行”需要托盘或已配对手机唤回；没有唤回路径时建议“最小化到任务栏”。
- 帮助页仍保留三处统一书签文案：`打开后建议加入手机书签，方便下次访问。`；Cloudflare 旁边紧邻临时地址警告。
- 不把历史验收报告改写成已验收；产品文档只写当前行为和可复现步骤。

**Verification:**

```powershell
python -X utf8 -m unittest local.tests.test_ui_contract -v
```

### Task 6: 统一回归、编码门禁与用户验收暂停点

**Files:**
- Test: all affected `local/tests/`
- Modify: `design/evidence/2026-10-31/phone-access-repair-acceptance.md` only when DS/user produces new evidence
- Modify: `.claude/results/` only by the plan executor

**Automated verification (execution phase):**

- [ ] `python -X utf8 -m unittest discover -s local/tests -p "test_*.py" -v`：预期不再有 amendment-005 的 PNG 失败。
- [ ] `python -X utf8 -m compileall local server`：退出码 0。
- [ ] `node --check local/ui/app.js`、`local/ui/m/app.js`、`local/ui/controllers/window.js`、`local/ui/views/phone.js`、`local/ui/state/clock.js`：全部退出码 0。
- [ ] `git diff --check`：无本轮新增空白错误；既有行尾警告单独记录。
- [ ] 对所有本轮改动中文文件做严格 UTF-8 解码和乱码黑名单检查。
- [ ] 结果文件区分 `execution_status`、`verification_status`、`acceptance_status`、`publication_status`；不得把自动化 PASS 写成用户已验收。

**真实验收交给 DS/用户：**

1. Tailscale：手机首次扫码+配对后，关闭并重启程序，固定地址仍可打开且不要求重新配对。
2. Cloudflare：关闭后重新开启，地址改变；旧书签失效，必须重新扫码和输入配对码。
3. 手机控制台：手机选择明确活动，电脑端出现同一计划；停止/取消只产生一次对应动作，结果回到手机。
4. 手机重登：网络短暂断开后页面能回到可操作状态；`verifying` 期间不显示“重登结束”；验证码错误换图，密码错误不自动重试。
5. 关窗：无托盘且无手机会话时“隐藏到后台”被拒绝；有唤回路径时可隐藏；对话框打开时默认焦点是“最小化到任务栏”。
6. Cloudflare 组件：没有匹配组件时 Cloudflare 不可用但 Tailscale 仍可用；PATH 中另放的同名文件不会被执行。

## 明确不在本次返修中改变的内容

- 不移除整体 `TOTAL_BUDGET_S=600`；它与“验证码无倒计时、无提交次数上限”是不同层级的安全预算。
- 不重做手机控制台三块结构、配对流程、二维码入口和 Tailscale/Cloudflare 产品定位。
- 不重新引入普通局域网入口，不增加系统托盘依赖，不自动下载或升级任何组件。
- 不清理入场工作区的其它脏改动，不回滚此前已完成的功能。

## Self-review

- amendment-003：通过 Task 1 正式纳入 `local/build_advanced.py`。
- amendment-005：通过 Task 2 修合法 PNG 夹具，保留生产严格校验。
- post-plan 隐藏/托盘/对话框：通过 Task 4 正式纳入范围，并修复无唤回路径与默认焦点。
- Cloudflare 信任缺口：通过 Task 1、Task 5 同时修代码和用户口径。
- 重登异常恢复：通过 Task 3 覆盖网络异常、singleflight、verifying 和终态。
- 未决的整体 relay 预算：显式保留并记录，不在本次计划中猜测性修改。
