# 手机页 UI 交接（2026-10-31）

给接手界面的同学：这份文件只讲「现状、改过什么、不能碰什么、怎么验」。
设计口径与决策记录在 `design/decisions/`，本文件不重复。

## 0. 先读这一段：测试通过 ≠ 只改了测试

这轮工作的出发点是「补完 Codex 计划里那四组验收/测试」。结论是**四组自动化全部通过**，
但要交接清楚一件事：**为了让这些测试真的能过，生产代码也改了**，不是只加断言。

一句话版本：

- 组一（Cloudflare 异常退出）、组二（组件信任）、组三（关闭偏好）、组四（既有链路）
  里能自动化的部分，现在有测试锁住；真机上组一/组二/组四已过，组二因「当前没有可报名
  的活动」未测，组三的断网对账仍未真机验证。
- 过程中发现并修掉 **6 个真实缺陷**（D1/D2/D3 + E1/E2 + 验证码分工），每一个都改了
  生产代码，改动清单见第 2 节。
- 全量 `local/tests` 现在 **1370 tests OK（skipped=4）**。
- **没有任何 git 提交**：HEAD 仍是 `3cab0d6`，工作区 62 项改动，提交权在用户手上。

## 1. 当前状态

- 分支工作区脏，`git status --short` 62 项。其中约 40 项是本次会话**入场之前就存在**的
  WIP（`.gitignore`、`VERSION`、`docs/LOGIN.md`、`docs/OPERATIONS.md`、
  `local/business_clock.py`、`local/domain/phone_rules.py`、`local/grab.py`、
  `local/infrastructure/phone_http.py`、`local/login_relay.py`、`local/ui/app.js`、
  `local/ui/styles.css`、`local/ui/views/*.js`、`local/ui/state/clock.js`、`tools/release.py`、
  `server/` 相关等）。
- **不要清理、不要回滚、不要 `git add -A`**：那些文件里混着别人的未完成工作。
- 本次会话真正改过内容的文件列在第 2 节各轮次里，可以照着做 review。

## 2. 这轮到底改了什么（按轮次）

### 轮次 A：返修计划（6 个任务，名义上是「测试夹具 + 文档同步」）

生产代码实际改动：

| 文件 | 改了什么 | 为什么非改不可 |
|---|---|---|
| `local/infrastructure/component_packages.py` | `_manifest()` 要求 `phone_control` **必须**声明 `bin/cloudflared.exe`（版本 + sha256），`relogin_ocr` 不许夹带 | 原来「完全不声明」也算合法，等于组件包里可以没有隧道程序 |
| `local/build/build_advanced.py` | `--cloudflared` 缺失直接 `cloudflared_required` 失败，删掉「回退到 PATH」的分支 | 原来自备一个同名 exe 也能过，版本与哈希无从证明 |
| `local/infrastructure/tunnel_manager.py` | `resolve_cloudflared()` 只返回组件包路径 | 删除 PATH / 解释器目录 / resource_root 三处回退，堵掉同名伪造 |
| `local/application/login_relay_service.py` | 公开投影加 `submit_pending` | 手机靠它判断「这一张已发出、还没结论」，否则网络异常会重发 |
| `local/application/phone_service.py` | 新增 `has_live_session()`（只回布尔） | 隐藏窗口前要确认「还有没有办法叫回来」 |
| `local/app.py` | `hide_window()` 加门禁：托盘或未过期手机会话有其一才允许隐藏，否则 `hide_unavailable` | 否则能把窗口藏成打不开的样子 |
| `local/ui/controllers/window.js` + `local/ui/index.html` | 关窗对话框打开后聚焦「最小化到任务栏」，最小化按钮带 `autofocus` | 四选里默认焦点落在最安全的出口 |
| `local/ui/m/app.js` | 手机页 catch 后先 poll 对账；`verifying` 不再调用 `endReloginControls()` | 提交结果未知时不能当成失败把输入区收掉 |
| `docs/PHONE_ACCESS.md`、`local/README.md`、`local/ui/index.html`、`local/ui/views/phone.js` | 文案改成「cloudflared 随组件包提供、不自动下载升级、不配 PATH」 | 文档与实际能力不一致会直接误导用户 |

### 轮次 B：隐藏缺陷计划（3 个任务）

| 文件 | 改了什么 | 为什么 |
|---|---|---|
| `local/app.py` | 新增 `_cloudflare_status_snapshot()` / `_reconcile_cloudflare_lifecycle()` / `_cloudflare_exit_notice`；`phone_access_state()` 先对账再读；启动 Cloudflare 前重新 `resolve_cloudflared`；`request_window_close()` 改成「先隐藏，成功才记偏好」 | 隧道 `status()` 的 `exited` 只报一次，同一轮第二次读会降级成「可用」，界面会拿旧地址让人扫码；「记住隐藏」原来在门禁之前就把偏好写坏了 |

### 轮次 C：D1/D2/D3（真机验收反馈带出来的三个真缺陷，只动手机页）

| 缺陷 | 现象 | 修法（`local/ui/m/app.js`） |
|---|---|---|
| D1 | 电脑重启程序后手机「能看能刷、点什么都没反应」，日志里全是 `403 bad_csrf` | 写请求**每次**按当前 cookie 重新取 `campus_phone_csrf`，不再用页面打开时读到的旧值 |
| D2 | 断网后请求永久挂起，`poll()` 单飞锁不释放 → 连接文字冻在「已连接」、刷新按钮点了没反应 | 请求加 8 秒 `AbortController` 超时，`finally` 释放锁与计时器 |
| D3 | 电脑认图失败时手机只显示「重登结束：idle」，真正原因被盖掉 | 只有 `failed`/`canceled` 才写「重登结束：…」，`idle` 只收控件 |

### 轮次 D：E1/E2（自查带出来的两个）

| 缺陷 | 修法 |
|---|---|
| E1 除 `poll` 与提交外，写动作都没有 try/catch，断网时变成未处理的 Promise 拒绝、界面静默 | 新增 `postAction()` 把失败折成 `{status:0, error:"network", text:"网络不通，这次操作没有发出去"}`，各按钮沿用原错误分支 |
| E2 `poll()` 把 401 与 403 一起当「需要重新配对」，`bad_csrf` 会把刚配过对的用户踢回配对页 | 401 才回配对页；403 走 `onForbidden()`：重读 cookie、提示「会话令牌已更新」、退避重试 |

### 轮次 E：验证码分工（用户需求，阈值 = 3）

| 文件 | 改了什么 |
|---|---|
| `local/application/login_relay_service.py` | 公开投影加 `origin`（`auto`/`phone`） |
| `local/app.py` | `_MANUAL_RELOGIN_AFTER = 3`；`_relogin_ocr_ready()`、`_manual_relogin_wanted()`、`_phone_relay_view()`；`phone_relogin_begin()` 在电脑自动处理期间不再新开人工场（回 `mode=auto`）；`_anchor_login_success()` 成功后补一次 `check()` |
| `local/ui/m/app.js` | `mode=auto` 时收起验证码区并报「电脑正在自动重登（第 N 次）」；`beginRelogin()` 加 `reloginStarting` 单飞锁 |

判定口径：电脑装了 OCR、且同一场识别失败 < 3、整轮自动重登连续失败 < 3 → 手机看不到验证码；
达阈值或电脑没装 OCR → 整组验证码交给手机人工输入。

### 轮次 F：手机页第二轮（本轮，用户反馈「验证码输入框还在」「断网点什么都没反应」「UI 一坨」）

| 文件 | 改了什么 |
|---|---|
| `local/ui/m/index.html` | 验证码图 + `#code` 输入框 + 三个按钮收进 `#relogin-captcha-group`（默认 `hidden`，`#btn-relogin` 留组外常驻）；新增吸顶的 `#offline-note` 与 `#stale-note`；今天卡按钮整行（`.row.actions` + `button.wide`） |
| `local/ui/m/app.js` | `syncOffline()` 写离线提示与重试次数；刷新按钮只在自己请求在途时禁用并显示「刷新中…」；`refreshControls()` 开头同步两条提示；`poll()` 置 `flying` 后立刻刷新控件；`onPollFail()` 累加 `offlineTries`；`endReloginControls()`/auto 分支/verifying 分支统一控制验证码整组 |
| `local/ui/m/styles.css` | 状态栏吸顶（`position: sticky`）；今天卡高亮为主角；`button.wide`；`#offline-note` 吸顶；`#stale-note` 用 warn 色 |

## 3. 四组验收 ↔ 自动化对应

| 组 | 判据 | 自动化 | 真机 |
|---|---|---|---|
| 一 Cloudflare 异常退出 | 进程被杀后第一次刷新即：旧地址/二维码消失、手机服务停止；重开后是新地址、要重扫 | `test_application_services.PhoneChannelPreferenceTests`（退出对账、提示不降级、启动前重校验）+ `test_tunnel_manager`（exited 只报一次） | 已过（两轮） |
| 二 组件信任 | 运行中移走/替换组件后 Cloudflare 不可用且不启动，Tailscale 不受影响 | `test_component_packages` / `test_component_builder` / `test_tunnel_manager`（只认组件包、版本与哈希） | 已过（真机用真 cloudflared 构建的组件包验证过）；「点 Cloudflare 不可用」这一条当时用脚本验过 |
| 三 关闭偏好 | 隐藏被拒时不写偏好；已记住 minimize 时拒绝后仍是 minimize；成功隐藏才记住 | `test_application_services`（`test_remembered_hide_is_refused_the_same_way`、`test_refused_hide_keeps_the_previous_preference`、`test_hide_succeeds_even_when_the_preference_cannot_be_saved`） | 组四「隐藏唤回」已过；**组三断网对账仍未测** |
| 四 既有链路 | Tailscale 免配对、手机报名/停止/取消、重登对账、托盘或手机唤回 | `test_phone_service`、`test_phone_ui`、`test_application_services`、`test_retry_phone_integration` | 免配对、唤回已过；报名/停止/取消因「当前没有可报名的活动」未测 |

## 4. 界面结构与关键 id

### 手机页 `local/ui/m/index.html`

- `#pair`：`<h1>连接电脑</h1>`、`#pair-code`、`#btn-pair`、`#pair-error`，两处「加书签」提示
- `#app`（配对成功后显示）：
  - `header.bar`：`<h1>这次报名</h1>`（**文案待定，见第 8 节**）、`#conn`（已连接/离线 pill）、`#btn-refresh`
  - `#last-sync` → `#offline-note`（吸顶，断网时写原因与重试次数）→ `#stale-note`（状态过时说明）→ `#banner` → `#login-expired-banner`
  - 今天卡 `#today-items`：`#items`、`#empty`、`.row.actions`（`#btn-start` / `#btn-stop`）、`#plan-line`、`#pending-note`、`#btn-cancel-task`
  - 即将开放卡：`#upcoming-items`、`#upcoming-empty`
  - `details#signed-summary`（已报名 N 场）→ `#bookmark-hint`
  - `details#more-panel`：`#filter-panel`、`#retry-panel`、`#logs-panel`、`#window-panel`（`#btn-show-window`）、`#relogin-panel`
  - `#relogin-panel`：`#relogin-note` → `#relogin-captcha-group`（`#captcha`、`#code`、`#btn-relogin-submit`、`#btn-relogin-refresh`、`#btn-relogin-cancel`）→ `#btn-relogin`
- 样式 token 在 `local/ui/m/styles.css` 顶部 `:root`；触控目标 44px；有 `prefers-reduced-motion` 分支

### 手机页 `local/ui/m/app.js` 的分层

- `PhoneModel`：纯函数（`isStale` 5 秒、`canStart`、`canSubmitRelogin`、`connText`、`nextBackoff`）
- `api()` / `postAction()`：唯一出口（带超时、写请求按当前 cookie 取 CSRF）
- `poll()`：单飞轮询，失败走 `onPollFail()`，401 走 `onNeedPair()`，403 走 `onForbidden()`
- `refreshControls()` / `syncOffline()`：把 model 映射到 DOM（**所有**禁用态与提示都在这里）
- `ingest()` / `ingestRelogin()`：服务端快照 → 界面状态
- 导出：`globalThis.PhoneUI = { model, poll, wire, renderItems, refreshControls, ingest, startPlan, submitRelogin, beginRelogin, cancelRelogin, refreshRelogin, showComputerWindow }`（测试靠它驱动）

### 桌面页

- `local/ui/index.html`：`#dlg-close`（`#btn-close-hide` / `#btn-close-minimize`（`autofocus`）/ `#btn-close-exit` / `#dlg-close-remember` / `#btn-close-cancel`）；帮助→跨设备访问的 `#phone-*` 各展示位
- `local/ui/controllers/window.js`：`openWindowCloseDialog()` 后调 `focusSafestClose()`（缺元素/缺 `showModal` 都安全降级）

## 5. 必须保持的不变量（都是踩过的坑）

1. **写请求每次读 CSRF cookie**（`campus_phone_csrf`，故意非 `HttpOnly`）。只在打开时读一次 → 重启程序后恒 403。
2. **每个 fetch 都要有超时**，失败要释放单飞锁。否则断网一次，刷新按钮永久失效。
3. **401 才回配对页**；403（尤其 `bad_csrf`）不能踢回配对。
4. **验证码整组同进同退**：图、输入框、三个按钮由 `#relogin-captcha-group` 一个开关控制；`#btn-relogin` 永远在组外。
5. **隐藏门禁**：托盘图标或未过期手机会话有其一才允许隐藏，否则 `hide_unavailable` 并保持可见。
6. **cloudflared 只认组件包**（版本 `2026.10.7` + sha256），没有 PATH/resource_root 回退。
7. **Cloudflare 退出提示要暂存**：`status()` 的 `exited` 只报一次。
8. **改含中文的文件用字节写回**：Windows 上 `pathlib.write_text()` 会把 LF 翻成 CRLF；要 `read_bytes`/`write_bytes`。
9. **测试装置的限制**（`local/tests/test_phone_ui.py`）：`setTimeout` 是空实现、没有 `AbortController`；`__fetch` 必须返回 `{status, json: async () => ({...})}`；vm 里未处理的 Promise 拒绝会让 node 退出 → 报「手机 JS 行为测试崩溃」。
10. **`local/README.md` 整文件是 CRLF**：`git diff --check` 会报一串 trailing whitespace 假阳性，判定用 `git -c core.whitespace=cr-at-eol diff --check`；不要为清这个去批量重写行尾。

## 6. 硬约束

- 只服务本人账号：不做多账号、不批量占位、不代他人报名。
- 不改数据模型、登录态机制、学校接口契约（除非任务明确要求）。
- 不引入新依赖。
- 界面可改的范围：`local/ui/**`、`local/tests/**`、必要的 `docs/**`。**不要动** `server/`、`server/data/`、`local/data/`、`.venv/`、`node_modules/`。
- 不改 `@author` 标注；不写临时目录路径与本机绝对路径进文档。
- 提交权在用户：改完停下汇报，不要 `git commit`；也不要 `git add -A`。

## 7. 测试地图与命令

```bash
# 全量（约 2 分钟）
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"

# 手机页行为 + 静态布局（改 UI 主跑这个）
python -X utf8 -m unittest local.tests.test_phone_ui

# 桌面契约（关窗四出口、书签文案、文档与文案同步）
python -X utf8 -m unittest local.tests.test_ui_contract

# 编排与门禁
python -X utf8 -m unittest local.tests.test_application_services local.tests.test_login_relay_service

# 语法与空白
python -X utf8 -m compileall local server
node --check local/ui/m/app.js
git -c core.whitespace=cr-at-eol diff --check
```

改完界面请顺带确认：严格 UTF-8 可解码、无 BOM、行尾与原文件一致、无乱码黑名单字符、无行尾空白。

## 8. 待定项与已知残留

待定：

- `local/ui/m/index.html:32` 的 `<h1>这次报名</h1>` 文案**待定**（不在任何测试断言里，改一行即可，建议连 `<title>校园活动 · 手机</title>` 一起对齐）。候选：手机报名 / 校园活动 / 报名控制台。
- 手机页整体视觉方向（本轮只做了「能看清、点得动」的最小整理，不是重新设计）。

已知残留（记录在案，未改）：

- 8 秒超时对慢链路偏紧：Tailscale 走中继或弱网时，正常的状态拉取也可能超时而多显示一次「离线/未知」。
- 超时只取消客户端等待，服务端可能仍在执行；`start_plan` 靠 `request_id` + `start_request_state` 对账，停止/取消幂等。
- 断网到界面显示「离线/未知」最坏要等满 8 秒超时再加 5 秒判旧。
- `campus_phone_csrf` 故意不加 `HttpOnly`（页面要读它才能回传），设备信任 cookie 仍是 `HttpOnly`，两者权限差别不能合并。
- 首次全量跑出现过 1 次 Windows 临时目录清理 `PermissionError`（`test_session_persistence` 的用例），单独复跑与再次全量均通过，判为环境偶发。

## 9. 给接手人的作业边界

可以改：`local/ui/m/*`（手机页三件套）、`local/ui/*`、`local/ui/views/*`、`local/ui/controllers/*`、`local/tests/**`（同步更新断言）、`docs/**`（文案）。

必须保住：第 5 节十条不变量、第 6 节硬约束、以及 `local/tests/test_phone_ui.py` 里 `LayoutStaticTests` 的静态断言（它们锁的是「验证码整组是一处开关」「离线提示是一等元素」这类结构性事实；改结构就要改断言，不能删）。

完成后按第 7 节跑一遍，把「改了什么 / 验了什么 / 还有什么没验」写清楚交回去。
