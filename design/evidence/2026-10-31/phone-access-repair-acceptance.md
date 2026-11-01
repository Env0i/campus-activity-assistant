# 手机访问返修（2026-10-31）验收证据

本文件只记录可复现的命令与结论，不写账号、密码、验证码、cookie、token 与真实域名。

## 一、离线技术验证

| 检查 | 命令 | 结果 |
|---|---|---|
| 本机全量测试 | `python -X utf8 -m unittest discover -s local/tests -p "test_*.py"` | 1294 tests，1 failure（见第三节），4 skipped |
| 语法 | `python -X utf8 -m compileall local server` | exit 0 |
| 前端语法 | `node --check` × 7（`local/ui/app.js`、`m/app.js`、`views/phone.js`、`state/clock.js`、`views/clock.js`、`views/clock-pop.js`、`controllers/window.js`） | 全部 exit 0 |
| 空白/行尾 | `git diff --check` | exit 0（仅既存的 `docs/OPERATIONS.md`、`local/requirements.txt` 行尾提示） |
| 编码 | 严格 UTF-8 解码 + 乱码黑名单扫描 27 个改动文件 | BAD=0 |

分组结果（本轮改动直接相关的模块）：

- `test_business_clock` + `test_business_clock_wiring`：失败退避 5/10/20/30 秒、成功清零、门禁未到不发新一轮 —— 通过。
- `test_ui_contract`：校时四态文案、「点这里重试」、退避字段、关窗三选、书签文案同源 —— 通过。
- `test_phone_ui`：电脑续登录卡（未装 ddddocr 仍可保存凭据、清除要确认）、手机页三桶顺序与 44px 触摸 —— 通过。
- `test_login_relay_service`：完成方标签 auto→`auto_ocr`、phone→`phone_manual`、零参回调仍只触发一次 —— 通过。
- `test_auto_relogin`：最近使用只记时间与方法，不含账号/验证码/凭据 —— 通过。
- `test_component_packages`：manifest 声明 `bin/cloudflared.exe` 与 2026.10.7 版本、哈希、probe 四道门禁 —— 通过。
- `test_application_services`：`resolve_close_action`、记住选择、退出前先置放行标记 —— 通过。
- `test_network_policy`：学校请求现建「空 ProxyHandler」opener、替身退回 urlopen、`install_opener` 未使用、`tools/release.py` 不再写死本机代理 —— 通过。

## 二、真机（本机 tailnet）复核

沿用上一轮的 Tailscale 真机脚本（`tailscale_endpoint()` → 绑定 `100.x:8765` → MagicDNS 地址 + 配对码），本轮只复核两点：

1. **设备信任仍是 Tailscale 专属**：配对响应带 `campus_phone_device`；Cloudflare（https）通道不签发。
2. **关窗三选不破坏链路**：选「最小化到任务栏」后隧道与手机服务仍在运行（`phone.log` 继续有新请求）。

未执行：物理手机上的独立复核（需用户本人操作），以及 Cloudflare 通道的本轮复测。

## 三、已知失败（与本轮改动无关）

`local.tests.test_retry_phone_integration.FullChainTests.test_pair_read_start_extend_stop_relogin_chain`

```
AssertionError: False is not true
  self.assertTrue(relay["image"].startswith("data:image/png;base64,"))
```

原因：`local/domain/phone_rules.py` 的 `project_text()` 现在要求验证码图「前缀 + 严格 base64 + PNG 魔数」，而该用例喂的假图是 `data:image/png;base64,AAAA`（解码后不是 PNG），于是被整体丢成空串。这是**入场既有的工作区改动**（`git show HEAD:local/domain/phone_rules.py` 里还没有 `_PNG_MAGIC`），不是本轮引入；修法是让用例喂一张合法 PNG 的一像素图。

## 四、未验证范围

- 物理 iPhone 上的扫码/书签/重登全流程（本轮只有桌面端与本机 HTTP 客户端证据）。
- 真实学校链路的登录失败场景轮次。
- Windows 任务栏最小化后的长时间驻留（超过一次报名窗口）。

## 五、返修轮回归（同一日期，晚于上文）

上面一至四节记的是上一轮（含那 1 个失败）。本轮按
`.claude/plans/20261031-phone-access-repair-followup.yaml` 收口了四件事，
结论与复现命令如下。**这里只有自动化回归，没有用户真机验收，不构成验收结论。**

| 检查 | 命令 | 结果 |
|---|---|---|
| 本机全量测试 | `python -X utf8 -m unittest discover -s local/tests -p "test_*.py"` | 1330 tests，OK（skipped=4），exit 0 |
| 语法 | `python -X utf8 -m compileall local server` | exit 0 |
| 前端语法 | `node --check` 全部 `git ls-files 'local/ui/*.js' 'local/ui/**/*.js'`（34 个文件） | 全部 exit 0 |
| 空白/行尾 | `git -c core.whitespace=cr-at-eol diff --check` | exit 0 |
| 编码 | 严格 UTF-8 解码 + 乱码黑名单扫描本轮 22 个改动文件 | BAD=0（无 BOM、无混合行尾、无真实行尾空白） |

本轮修掉的问题（都可单独复现）：

1. **第三节那个失败已消失**：`test_pair_read_start_extend_stop_relogin_chain`
   现在喂的是一张真实的一像素 PNG（`CAPTCHA_PNG`），`domain/phone_rules.py`
   的「前缀 + 严格 base64 + PNG 魔数」判定一行未改。同一次改动里保留了反向断言
   `test_illegal_image_is_not_rendered`：非法图仍然必须被投影成空串。
2. **cloudflared 只从组件包来**：`build_advanced.py` 缺 `--cloudflared` 直接
   `cloudflared_required` 失败；`component_packages._manifest()` 要求
   `phone_control` 必须声明 `bin/cloudflared.exe`（版本 2026.10.7 + 匹配 SHA-256），
   `relogin_ocr` 夹带即拒；`tunnel_manager.resolve_cloudflared()` 不再回退
   `resource_root` / 解释器目录 / `PATH`。
3. **重登的「结果未知」不再当场收口**：`public_state()` 投影出 `submit_pending`，
   网络异常后手机页先 poll 对账，`verifying` 与 `submit_pending=true` 期间保持禁用，
   不自动发第二个 POST。
4. **隐藏到后台要有唤回路**：`PhoneAccessService.has_live_session()` + `app.py`
   的 `hide_window()` 门禁——托盘或未过期手机会话二者有其一才允许隐藏，否则
   `hide_unavailable` 并保持窗口可见；关窗对话框打开时焦点落在「最小化」。

一处必须说明的 `git diff --check` 例外：`local/README.md` 整文件是 CRLF（HEAD
里的 blob 也是 CRLF），本轮编辑后新增行被默认 whitespace 规则按「行尾 CR」判成
trailing whitespace，共 22 行报警。逐字节核对：该文件无任何真实行尾空白，
加 `-c core.whitespace=cr-at-eol` 后 `git diff --check` 为 exit 0。按仓库规范
不为清这条告警批量改行尾，故保留原样。

## 六、隐藏缺陷返修（同一日期，晚于第五节）

按 `.claude/plans/20261031-phone-access-hidden-defects.yaml` 收口两类隐藏缺陷：
Cloudflare 隧道异常退出后没有收口、关闭偏好会在隐藏失败时被写坏。
**这一节同样只有自动化证据，没有真机验收，不构成验收结论。**

### 6.1 修掉的两件事

1. **隧道异常退出必须立刻收口，且退出提示不能被降级**
   - `CloudflareTunnel.status()` 只在读到退出那一刻报一次 `state=exited`，
     第二次读就是 `stopped`。原先 `phone_access_state()` 先取 `address()`
     再由 `advanced_features_state()` 读一次状态，同一轮里第二次读就把
     「已退出」翻成了「可用」，界面继续显示旧地址和旧二维码。
   - 现在 `app.py` 用 `_cloudflare_status_snapshot()` 把 exited 存进
     `_cloudflare_exit_notice`，`phone_access_state()` 先跑
     `_reconcile_cloudflare_lifecycle()`：停手机服务、撤销当前会话、
     清 `_phone_channel`、清旧地址，同一次响应返回 `running=false`、
     `address=''`、`qr=''`，`advanced.channels.cloudflare` 报
     `state=exited` / `error=tunnel_exited` 且带可读文案。提示保留到用户手动
     `stop_phone_access()` 或下一次成功 `start_phone_access('cloudflare')`。
   - 对账幂等：通道已经不是 cloudflare 时直接返回，不重复停服务。
   - 不自动重启、不复用旧地址（Cloudflare 仍是临时通道）。

2. **每次真正启动 Cloudflare 前重新校验组件，失败绝不先起手机服务**
   - `_start_phone_access('cloudflare')` 在 `phone.start()` 之前调用
     `resolve_cloudflared(resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR)`；
     返回空就把 `self._cloudflare.executable` 清空再返回
     `cloudflared_missing`，不启动手机服务、不启动隧道（组件可能在程序启动后
     被替换或删除，初始化时缓存的路径不能直接拿去执行）。

3. **关闭偏好改成「先做再记」的事务**
   - `request_window_close()` 里 `hide` 分支先执行 `hide_window()`，通过门禁
     （托盘或未过期手机会话）后才写 `window.close_action`；门禁失败原样返回
     `hide_unavailable` / `no_window`，用户原有偏好一个字不动。
   - 已经藏起来但偏好写失败时保持隐藏，返回 `hidden=true`、`remembered=false`
     与提示，不把窗口再翻回来。
   - `minimize` / `exit` 行为不变；计划运行中强制询问的逻辑不变。

### 6.2 自动化证据

| 检查 | 命令 | 结果 |
|---|---|---|
| task-1 定向 | `python -X utf8 -m unittest local.tests.test_application_services local.tests.test_tunnel_manager` | 77 tests，OK，exit 0 |
| task-2 定向 | `python -X utf8 -m unittest local.tests.test_application_services` | 37 tests，OK，exit 0 |
| 本机全量测试 | `python -X utf8 -m unittest discover -s local/tests -p "test_*.py"` | 1339 tests，OK（skipped=4），exit 0 |
| 语法 | `python -X utf8 -m compileall local server` | exit 0 |
| 前端语法 | `node --check local/ui/app.js`、`local/ui/m/app.js`、`local/ui/views/phone.js` | 三条均 exit 0 |
| 空白/行尾 | `git diff --check` | exit 2，仅 `local/README.md` 的既有 CRLF 行被判 trailing whitespace（见 6.3） |
| 空白/行尾 | `git -c core.whitespace=cr-at-eol diff --check` | exit 0 |
| 编码 | 严格 UTF-8 解码 + 乱码黑名单扫描本轮改动文件（`local/app.py`、`local/tests/test_application_services.py`、`local/tests/test_tunnel_manager.py`） | BAD=0（无 BOM、无混合行尾、无真实行尾空白） |

新增/改写的用例（都能单独跑，用来复现这三个缺陷）：

- `PhoneChannelPreferenceTests.test_cloudflare_exit_is_reconciled_on_the_first_state_read`
  —— 隧道 exited 时第一次刷新就要 running=false、address/qr 为空、手机服务已停且撤销会话。
- `...test_the_exit_notice_is_not_downgraded_to_available`
  —— 连读两次仍是 exited；手动关闭后才回到 available。
- `...test_cloudflare_start_is_refused_without_a_verified_component`
  —— 组件校验空：清空旧路径、不调 `phone.start`、不调隧道 start。
- `...test_cloudflare_start_uses_the_freshly_verified_path`
  —— 启动用的是刚校验过的路径。
- `...test_a_successful_cloudflare_start_clears_the_exit_notice`
  —— 成功开启后旧提示被清掉。
- `...test_remembered_hide_is_refused_the_same_way`（扩展）
  —— 隐藏被拒时偏好文件里不会出现 hide。
- `...test_refused_hide_keeps_the_previous_preference`
  —— 原有 minimize 偏好在被拒后保持不变。
- `...test_hide_succeeds_even_when_the_preference_cannot_be_saved`
  —— 已隐藏 + 偏好写失败 → `hidden=true`、`remembered=false`、有提示。
- `CloudflareTunnelTests.test_exited_status_is_reported_once_then_stopped`
- `CloudflareTunnelTests.test_stop_after_exit_clears_the_address_and_reports_stopped`

### 6.3 仍然保留的 `git diff --check` 例外

与第五节同因：`local/README.md` 整文件 CRLF（HEAD 里的 blob 也是 CRLF），默认
`core.whitespace` 不含 `cr-at-eol`，于是这些行的行尾 CR 被当成 trailing
whitespace，报 `local/README.md:270-294` 共二十余行。逐字节核对无真实行尾空白，
加 `-c core.whitespace=cr-at-eol` 后 exit 0。按仓库规范不为清这条告警批量改行尾、
也不改 `.git/config`，故保留原样，此处如实记录默认命令与修正命令两种结果。

### 6.4 未验证范围（本轮新增）

以下必须在真机/真实链路验证，自动化只能证明代码路径：

- Cloudflare 隧道进程被外部杀掉（或网络断开导致退出）后，界面第一次刷新就
  不再显示旧地址与旧二维码，重新开启能生成新地址并重新配对。
- 程序运行中删除或替换 `phone_control` 组件包的 `bin/cloudflared.exe` 后，
  再点 Cloudflare 必须报不可用且不启动手机服务；Tailscale 通道不受影响。
- 勾选「以后都这样」再点「隐藏到后台」、且当次隐藏被门禁拒绝后，下次点 X
  仍然弹出关闭对话框（偏好没有被污染）。
- 既有链路回归：Tailscale 重启免配对、手机端报名/停止/取消、重登网络异常后
  的对账与手动恢复、托盘或手机页唤回窗口。
## 七、四组验收（2026-10-31 晚，晚于第六节）

这一轮用的是真二进制、真组件包、真子进程，不是夹具；但仍然没有手机、没有真实
学校的链路，所以只覆盖到「程序这一侧确实做到了」，不构成最终验收结论。

### 7.1 环境与做法

- `cloudflared` 用仓库外的一份本地下载（版本 `2026.10.7`，与
  `component_packages.CLOUDFLARED_VERSION` 一致）；该目录不入库，文档不记路径。
- 组件包用 `local/build_advanced.py --feature phone_control --cloudflared <cloudflared>`
  现场构建，再用 `component_packages.install(zip, "phone_control", root=...)` 装入，
  与打包版「导入组件包」走同一条代码路径。
- 驱动方式：源码版 `import app` 直接驱动 `Api`，`DATA_DIR` / `PREFS` / `DEVICE_FILE`
  全部指向临时目录，`local/data` 未改动。
- 源码环境没有业务时钟，`PhoneAccessService.start()` 会抛 `ClockUnavailable`，
  验收时用演示时钟驱动（既有设计，不是本轮改动）。

### 7.2 组 1：隧道异常退出与重新开启（真 cloudflared）

| 判据 | 结果 |
|---|---|
| 第一次开启 | 拿到 `https://*.trycloudflare.com` 临时地址 + 新配对码，`persistent_device=false` |
| 外部结束 `cloudflared` 后**第一次**读状态 | `running=false`、`address=''`、`qr=''`、`channel=''`、手机服务已停 |
| 通道状态 | `state=exited`、`error=tunnel_exited`、有可读提示 |
| 第二次读状态 | 仍 `exited`（没有被降级成 available） |
| 手动关闭通道后 | 回到 `available` |
| 重新开启 | 拿到**与第一次不同**的新地址 + 新配对码，旧退出提示被清除 |

具体域名与配对码都是一次性临时值，且配对码属凭据类信息，不写入本文件。

### 7.3 组 2：运行中移走组件二进制

在组件已安装、程序已缓存路径的前提下，把
`advanced/phone_control/bin/cloudflared.exe` 移走，再点开启：

- `start_phone_access('cloudflare')` 返回 `cloudflared_missing`；
- 缓存路径被清空，手机服务与隧道都没有启动；
- 文件放回后 `resolve_cloudflared` 立刻恢复。

另用构造的组件包（manifest 与哈希正确、二进制被移走）复验：`feature_ready()`
同步为假，`resolve_cloudflared()` 返回空。

### 7.4 组 3：关闭偏好的事务性

无 GUI 环境下直接调 `Api`，验证的是偏好不被污染，不是界面按钮：

- 无托盘、无手机会话时点「记住并隐藏」→ `hide_unavailable`，偏好里不落 `hide`；
- 拒绝之后下次点 X 仍然走 `ask_window_close`（对话框会再弹）；
- 已有 `minimize` 偏好时被拒，原值保留；
- 已记住 `hide` 但当时没有任何唤回入口 → 仍然拒绝，`window.hide()` 一次都没调用；
- 托盘可用时隐藏成功，`remembered=true`，偏好写入 `hide`。

### 7.5 仍未验收（必须在真机上做）

- 界面上的关窗四选：按钮点击、默认焦点落在「最小化」、勾选「以后都这样」的交互；
- Tailscale 重启免配对；
- 手机端报名 / 停止 / 取消；
- 重登网络异常后的对账与手动恢复（不重复提交、按结果收口）；
- 托盘图标或手机页「显示电脑窗口」真的把界面叫回来。

### 7.6 复现方式

临时目录统一用 `%TEMP%`，不留绝对路径：

1. 准备与 `CLOUDFLARED_VERSION` 同版本的 `cloudflared.exe`，`cloudflared --version`
   确认版本号；
2. 构建组件包：
   `python -X utf8 local/build_advanced.py --feature phone_control --output-dir %TEMP%\phone-control-build --cloudflared <cloudflared.exe>`
3. 把 `DATA_DIR` / `PREFS` / `DEVICE_FILE` 指向临时目录后构造 `Api`，用
   `component_packages.install(<zip>, "phone_control", root=<临时 DATA_DIR>)` 装入；
4. 调 `start_phone_access("cloudflare")`，记录地址与配对码；
5. 从外部结束 `cloudflared` 进程，再调一次 `phone_access_state()`；
6. 再调一次 `start_phone_access("cloudflare")`，比对两次地址与配对码。

验收脚本本身是一次性的，不入库；结论与判据以上面各节为准。

## 八、真机验收结果与随后修掉的三个缺陷（2026-10-31 晚，晚于第七节）

第七节只做到自动化；这一节是用户在真机上按四组逐项操作后的结果。

### 8.1 四组结果

| 组 | 内容 | 结果 |
|---|---|---|
| 一 | Cloudflare 异常退出收口、重新开启换新地址 | **通过**（第一轮、第二轮都过） |
| 二 | 手机端报名 / 停止 / 取消 | **未做**：当时没有可报名的活动 |
| 三 | 重登网络异常后的对账 | **未通过**：请求根本没到业务代码，见 D1 |
| 四 | 隐藏唤回（四选、默认焦点、门禁、记住偏好） | **通过**；唯「显示电脑窗口」失败，同因 D1 |

### 8.2 三个缺陷

**D1 重启后手机端的 CSRF 令牌停在上一个进程的值（功能缺陷，必修）**

现象：退出程序再重开后，手机页能读状态、显示「已连接」，但所有写操作都没反应
（重登点不动、显示电脑窗口失败），提示里只看得到 `bad_csrf`。

证据：手机访问日志 2026-10-31 16:31 有一条 `POST /api/action 200`（配对后正常），
而重开后的 18:18 起连续多条 `POST /api/action 403 bad_csrf`，同一时段的
`GET /api/state` 全部 200——读能过、写全挂，说明问题在令牌而不在通道。

根因：重开后旧会话随进程消失，手机靠设备信任自动恢复一条新会话，
`PhoneAccessService.authenticate_or_restore()` 会换发新的 CSRF 并下发新的
`Set-Cookie`；但手机页只在打开时读一次 cookie（`if (!model.csrf) model.csrf = readCookie(...)`），
之后永不更新，于是请求头里的旧令牌和 cookie 里的新令牌对不上，双提交校验恒失败。

修法：写请求每次都按当前 cookie 取令牌，统一放在 `api()` 里，所有动作共享一处。

**D2 断网时页面会冻住（功能缺陷，必修）**

现象：断网后连接文字一直显示「已连接」，点按钮提示「状态已过时，先刷新」，
而点「刷新」毫无反应。

根因：`api()` 的 `fetch` 没有超时；断网时连接被黑洞吞掉、请求永久悬挂，
`poll()` 的单飞标志 `model.flying` 永远不释放，之后每次 `poll()`（含刷新按钮）
在第一行就返回，界面刷新逻辑再也不跑。

修法：给请求加 8 秒超时（有 `AbortController` 时用它，没有就不加），
`finally` 里清计时器；请求失败即回到可重试状态。

**D3 `idle` 把真实原因盖成一句空话（体验缺陷，必修）**

现象：重登没启动起来，界面最后显示「重登结束：idle」，看不出真正的原因。

根因：`ingestRelogin()` 把任何非 `waiting_code` 的状态都写成「重登结束：…」，
而 `idle` 只是「当前没有在进行的重登」，不是一次结束。

修法：只有 `failed` / `canceled` 才写「重登结束：<原因>」；`idle` 等状态只收控件、
不动提示文字，让上一次的真实原因留在界面上。

### 8.3 改动与验证

改动只在手机页与其测试：`local/ui/m/app.js`、`local/tests/test_phone_ui.py`。
新增三个用例分别锁住三件事：

- 写请求必须使用当前 cookie 里的令牌（`test_write_requests_use_the_current_csrf_cookie`）；
- `idle` 不写「重登结束」、不覆盖上一次的原因
  （`test_idle_snapshot_does_not_overwrite_the_last_reason`）；
- 请求失败后单飞锁必须释放，刷新还能再发
  （`test_hung_request_cannot_latch_the_refresh_button`）。

结果：`local.tests.test_phone_ui` 47 tests OK；全量 `discover` 1342 tests OK
（skipped=4）；`node --check local/ui/m/app.js` 通过；两个文件严格 UTF-8、
无 BOM、全 LF、无行尾空白。

复现命令（仓库根执行）：

```
node --check local/ui/m/app.js
python -X utf8 -m unittest local.tests.test_phone_ui -v
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"
```

### 8.4 仍需真机复验

- 组三：D1 修好后重跑一次断网对账（提交只发一次、按钮保持禁用、按结果收口）；
- 组四：手机页「显示电脑窗口」把隐藏的窗口叫回来；
- 组二：等有可报名活动时补测报名 / 停止 / 取消。

这三项仍然只有真机能证明，自动化通过不等于验收通过。

### 8.5 同日二轮自查：修复本身带出来的两处

给 `api()` 加超时之后，重新看了一遍调用链，发现两处需要一起补：

**E1 超时把「静默失败」变成了「未处理的异常」**

`poll` 与「提交验证码」本来有 try/catch，其余写动作（开始 / 停止 / 取消 /
换图 / 重登开始 / 取消重登 / 显示电脑窗口 / 保存重试 / 配对）没有。请求一旦
超时或断网，页面不会给出任何提示，只在控制台留一条未处理的 Promise 拒绝——
用户看到的就是「按钮点了没反应」。

修法：新增 `postAction()` 把写请求的失败统一折成
`{status: 0, body: {ok: false, error: "network", text: "网络不通，这次操作没有发出去"}}`，
各按钮沿用原来的错误分支即可显示；`pair()` 单独 try/catch，把失败写进配对卡片；
「取消重登」失败时不再假装已取消（保留旧图，让用户重试）。

**E2 403 被当成「没配对」**

`poll()` 原来把 401 和 403 一起处理成「回配对界面」。而 `bad_csrf` 也是 403：
两个手机页同时开着、后开的那个换了 cookie，前一个就会被莫名其妙踢回配对页。

修法：只有 401（`need_pair`）才回配对界面；403 走 `onForbidden()`——重新读取
cookie 里的令牌，提示「会话令牌已更新，正在重新同步」或「请求被拒绝，请刷新」，
留在主界面并退避重试。

**测试与变异检查**

`MobileWriteResilienceTests` 四条：写动作断网要留下能读的话、403 不踢回配对、
401 仍然回配对（老行为不能一起改掉）、配对断网要写进配对卡片。另做变异检查：
把上面两处分别改回旧写法，各有且仅有 1 条变红（`test_forbidden_csrf_keeps_the_app_open`、
`test_write_action_network_failure_is_visible_not_swallowed`），还原后文件字节一致。

**与公开经验的对照**

- [OWASP CSRF Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)：
  双提交模式要求服务端只认请求头/参数、令牌按会话绑定，且不宜每次请求轮换。
  本项目正是「会话绑定的令牌 + 只认请求头」，客户端每次按当前 cookie 取值，
  与这份口径一致。
- [MDN `AbortSignal.timeout()`](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static)：
  超时要和普通网络错误区分开。这里选择手动 `AbortController`（老浏览器没有
  `AbortSignal.timeout`，且本项目还要复用它给单飞锁放开），失败原因在界面上
  统一按「网络不通」呈现，不细分。
- [airwaves-os-control#42](https://github.com/airframesio/airwaves-os-control/issues/42)：
  一个真实缺陷报告，症状与我们 D2 完全同型——轮询没有在途取消、没有单请求超时，
  失败后再也不刷新。说明「给每个请求加超时 + 失败后释放单飞锁」是这类页面的
  标准做法。

### 8.6 已知残留（本轮不改，记录在案）

- 8 秒超时对慢链路偏紧：Tailscale 走中继或弱网时，正常的 `state` 拉取也可能
  超过 8 秒，会多显示一次「离线/未知」。真要调就改 `REQUEST_TIMEOUT_MS` 一处。
- 超时只取消客户端等待，服务端可能仍在执行：`start_plan` 靠 `request_id` +
  `start_request_state` 对账，停止/取消是幂等的，提交验证码走「结果未知 → 对账」。
- 断网到界面显示「离线/未知」最坏要等满一次超时（8 秒）再加 5 秒判旧。
- `campus_phone_csrf` 故意不加 `HttpOnly`（页面要读它才能回传），设备信任
  cookie 仍是 `HttpOnly`——两个 cookie 的权限差别不能合并。

## 九、手机与电脑的验证码分工（2026-10-31 晚，晚于第八节）

### 9.1 起因

真机验收组三暴露出一个设计问题：电脑装了 ddddocr 时整条链路本来就是「电脑自己
识别、自己提交」，但同一张图仍然会被完整推给手机，手机页照旧显示验证码和提交键。
两个人（两台设备）抢同一张图只会互相顶掉：手机提交必然撞上已经消费掉的挑战号，
而手机上看到的那张图对电脑来说早就过期了。

### 9.2 现在的分工

- 电脑装了「无人值守重登」且同一场识别失败次数 < 3、整轮自动重登连续失败次数 < 3：
  手机只看到「电脑正在自动重登（第 N 次）…」，**验证码图与挑战号不下发**。
- 电脑没装 OCR，或上述任一失败计数达到 3：验证码推到手机，按原来的手工流程走。
- 阈值只有一个常量 `_MANUAL_RELOGIN_AFTER`（`local/app.py`），改一个数字即可调整。
- 手机点「在手机上重登」时，若电脑正在自动处理，服务端**不会再起第二个 worker**，
  直接回 `mode=auto`；手机端另有 `reloginStarting` 单飞锁，连点两下只发一次请求。
- 电脑侧自动重登成功后触发一次正常的登录检查，顶栏状态与活动列表跟着刷新，
  不会再停在「登录已过期」。

### 9.3 改了什么

- `local/application/login_relay_service.py`：公开投影增加 `origin`（`auto`/`phone`），
  让手机能分辨这一场是谁发起的；仍不含任何凭据。
- `local/app.py`：新增 `_MANUAL_RELOGIN_AFTER`、`_relogin_ocr_ready()`、
  `_manual_relogin_wanted()`、`_phone_relay_view()`；手机状态改用投影；
  `phone_relogin_begin()` 在电脑自动处理期间不再新开人工场；
  `_anchor_login_success()` 成功后补一次登录检查。
- `local/ui/m/app.js`：`mode=auto` 时收起验证码区、显示「重试中」与尝试次数；
  `beginRelogin()` 增加单飞锁与 `mode=auto` 回执处理。
- 测试：`local/tests/test_login_relay_service.py`（来源标签）、
  `local/tests/test_application_services.py`（`PhoneReloginTakeoverTests` 9 条）、
  `local/tests/test_phone_ui.py`（5 条：自动态隐藏验证码、idle 说明、人工接管恢复、
  电脑接手回执、连点只发一次）。

### 9.4 判据与复现

- `python -X utf8 -m unittest local.tests.test_login_relay_service local.tests.test_application_services local.tests.test_phone_ui`
- `node --check local/ui/m/app.js`
- 变异检查：把投影里的抹图两行改成 `pass`、把手机端单飞锁删掉，对应用例分别变红，
  还原后字节一致。
- 本轮没有真机验证：「电脑自动识别成功后手机不再显示图」「连续失败 3 次转到手机」
  两条要在真机上走一遍才算验收。

### 9.5 仍未验收

- 组三的断网对账（用户尚未测）。
- 手机接管后的手工提交在真机上是否顺畅（本轮只做了自动化）。

### 9.6 手机页第二轮返修（验证码整组、断网可见性、界面整理）

真机反馈三条，逐条对应到具体元素：

1. **自动态连输入框一起收起。** 原来只藏了图和三个按钮，`#code` 输入框还露在外面，
   看起来像「让你输一个不存在的验证码」。现在验证码区整体收进
   `#relogin-captcha-group`：`mode=auto` 时整组隐藏，`mode=manual` 时整组出现，
   电脑认图失败转人工的那一次也会把整组重新打开。
2. **断网不再「点了没反应」。** `#offline-note` 在状态栏下吸顶，写清「连不上电脑
   （已重试 N 次）」以及该检查什么；`#stale-note` 说明为什么开始按钮是灰的；
   刷新按钮只在自己这次请求在途时禁用，并显示「刷新中…」，其余时间永远可点。
   成功拿到一次状态后两个提示都会自动消失，失败计数清零。
3. **界面整理。** 状态栏吸顶（断网时刷新仍在拇指边），今天卡单独高亮为主角，
   开始/停止按钮整行显示，验证码整组与「在手机上重登」分成两级。

判据：

- `python -X utf8 -m unittest local.tests.test_phone_ui`：64 tests OK
- `python -X utf8 -m unittest local.tests.test_ui_contract local.tests.test_application_services local.tests.test_login_relay_service`：301 tests OK
- 全量 `python -X utf8 -m unittest discover -s local/tests -p "test_*.py"`：1370 tests OK（skipped=4）
- 变异检查：删掉失败计数、把刷新按钮改成恒禁用、把验证码整组的两处收起同时拆掉，
  对应用例都变红；验证码组在 `auto` 分支与收口函数里各有一处兜底，只拆一处仍安全，
  这一点已如实记录而不是当成「测试抓不到」。
- 首次全量跑出现 1 个与该改动无关的 Windows 临时目录清理 `PermissionError`
  （`test_session_persistence` 的用例），单独复跑与再次全量均通过，判为环境性偶发。

## 十、后续真实验收清单

本文件前面的各轮记录包含了不同时间点的“未验证”项。为避免遗漏，所有尚未由用户在真实手机、真实桌面程序或真实学校活动条件下完成的项目，已合并到：

`mobile-ui-real-device-acceptance.md`

清单按 A–H 分组，包含前置条件、操作步骤、通过判据、无法观察时的记录口径和结果表。当前建议先做 A1–A4、B1–B4；真实活动出现后再做 D1–D5。
