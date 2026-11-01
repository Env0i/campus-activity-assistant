# 手机远程访问：执行结果与返修交接（供 Codex 定稿返修计划）

- 交接日期：2026-10-31
- 上一个计划：`docs/superpowers/plans/2026-10-30-phone-access-channel.md`（已执行完毕，guard 已释放）
- 执行记录：`.claude/results/20261031-phone-access-channel-result.yaml`（13 条 plan_amendments，6 条 post_plan_changes，门禁 PASS）
- 问题清单：`docs/superpowers/findings/2026-10-31-ui-findings.md`
- 证据：`design/evidence/2026-10-30/`（链路验收）、`design/evidence/2026-10-31/`（手机页三态截图）
- 当前 HEAD：`3cab0d6dfeb2dccbcd5d7ff86d23b49958b368f5`（本轮**零 git 提交**）

## 一、一句话目标

把「人不在电脑旁时用手机查活动、开报名、处理重登」做成一件成立的事：入口固定、配对一次、失败可自助恢复；本材料汇报**已做到哪一步**、**还需要改什么**。

## 二、已执行完的部分（业务链路已通）

| 任务 | 结果 | 关键产物 |
|---|---|---|
| task-0 Tailscale 探测契约 | success | `tailscale_endpoint()` 四态（missing / not_logged_in / probe_failed / connected），`parse_backend_state()` |
| task-1 DPAPI 设备信任存储 | success | `credential_store.save_document/load_document`、`PhoneSessionStore`（只存 SHA-256、一年、`hmac.compare_digest`） |
| task-2 会话/设备信任/撤销分离 | success | `authenticate_or_restore()`、`campus_phone_device`、`stop(revoke_devices)` / `shutdown(preserve_devices)` |
| task-3 记住通道并自动恢复 | success | `set_phone_access_preferences`、`restore_phone_access`、`schedule_phone_restore`、`CloudflareTunnel.status()` |
| task-4 帮助页通道引导 | success | 四步引导、通道状态行、重新检测、备用地址 + 复制、阻断式关闭确认 |
| task-5 文档同步 | success | `docs/PHONE_ACCESS.md`、`local/README.md` |
| task-6 回归与验收材料 | success | 五模块 138 tests、`design/evidence/2026-10-30/phone-access-acceptance.md` |

真机验收（Tailscale，本机 tailnet）：**15 项全 PASS**。Cloudflare（本机 `local/bin/cloudflared.exe`）：**16 项全 PASS**。
用户真机另确认两条：①Cloudflare 扫码 + 配对码可进入；②同一隧道存活期间**微信二次扫码免配对**。

## 三、计划结束后又改了什么（8 组，已登记 post-001…post-008）

| 触发 | 改动 | 为什么必须改 |
|---|---|---|
| 用户装了 Tailscale 仍报「未安装」 | `resolve_tailscale()` 回退 `Program Files\Tailscale\tailscale.exe` | 官方安装包不写 PATH，只查 PATH 永远 `tailscale_missing` |
| 帮助页承诺的 100.x 备用地址打不开 | `hosts_allowed()`/`origins_allowed()` + 按 scheme 分档 | 服务端只认 MagicDNS 名，备用地址 403 `bad_host`；但 https 隧道时不能让本机 Host 也通过 |
| 用户要求「方便调试复现」 | `local/data/phone.log` 请求级日志 | 之前只有界面提示，配对失败无法归因 |
| 用户报「配对码变了但界面没提示」 | `pair_code_status()`（seq/reason/expires_in）+ 5 秒轮询 + 换码提示 + 二维码按地址缓存 | 原先惰性换码，界面长期显示失效码 |
| 用户报「点开启没反应」 | `pending` 忙碌态：按钮「启动中…」「关闭中…」并禁用，连点只发一次 | Cloudflare 要等隧道出域名，界面无反馈会被当成没点上 |
| Cloudflare 需要可执行文件 | 固定版本下载到 `local/bin/`，`.gitignore` 排除 | 用户批准方案 A |
| 校时不可用时手机面板整块报错（R2） | `pair_code_status()` 捕获 `ClockUnavailable`，降级返回 `reason: "clock_unavailable"` | 校时是外部依赖，面板刷新是高频路径，不该被它整块拖死 |

## 四、需要返修的问题（详见 findings 文件）

### 必修（一行 CSS，风险极低）

**D1**：成功提示显示成红色（"账号信息已准备好。"）。`local/ui/styles.css:361` 的 `.help-status` 基础色是 `var(--bad)`，只给 `[data-tone="warn"]` 覆盖了颜色，`info` 从未定义；补 `.help-status[data-tone="info"] { color: var(--ink-2); }` 即可。建议连带加一条静态断言，防止再漏。

### 必修：校时首轮失败后不自动重试（R1，会复发的真问题）

**现象**：2026-10-31 10:05 启动时三个 NTP 源恰好都不通（网络在切换），顶栏停在「北京时间 未校准」，
活动区「活动暂时没加载」，开始报名的按钮禁用，运行记录只有一行「待校准」；**程序此后不会自己再试**，
必须人工点「重新校时」。当天是把 GUI 重启一次才恢复。

**代码**：`local/business_clock.py:259-265` 校时不可用时 `now()` 直接抛 `ClockUnavailable`，绝不回落到系统时间；
`:316-338` `sync()` 一轮三源各请求一次，失败进 holdover/unavailable。
`local/app.py:667-694` `_start_clock_monitor()` 只在「计划最早准备点前 20 秒」请求重校，**启动阶段没有任何重试**。
`local/app.py:1595`、`:1602`、`:1780` 在校时不可信时按设计拒绝加载活动与开始报名。

**建议方案**（交 Codex 定稿）：

1. 启动后首轮 `sync()` 失败即进入**退避重试**：5s → 15s → 40s → 之后每 60s 一次，直到成功；
   成功后清空退避并恢复正常监控。重试期间顶栏保留「未校准」但**明确写「正在重试」**。
2. 顶栏那条状态做成**可点按钮**（现在只是文字），点一下立刻重校，提示「点这里重试」。
3. 每次失败把「哪个源、什么原因」写进运行记录（现在只有一句笼统的失败）。
4. 测试用**假时钟 + 假源**断言：首轮失败 → 按 5/15/40 触发重试 → 成功后不再重试；
   以及「重试期间 UI 状态文案」。
5. **不做**：后台静默改用系统时间兜底——那会破坏「以北京时间为准」这条既有约定。

### 手机页信息架构（M1–M10）

首屏 40% 被筛选占用、重试设置与日志铺在正文、重登入口在页尾第 3 屏、六卡同权重、原生 checkbox 24px、禁用按钮无原因、配对页无用途说明且大片空白。建议方向已写在 findings 第一节末尾（状态条 → 今天要参加 → 即将开放 → 已报名折叠；其余折进抽屉）。**这是判断题，不是缺陷，等 Codex 定稿。**

### 桌面高级功能（D2–D8）

「填写账号密码 / 保存到本机」语义重叠、缺用途说明、缺最近使用时间、清除无二次确认、两个同级标题实为一件事、凭据保存被 `feature_ready(RELOGIN_OCR)` 挡住（`local/app.py:992`，人工输码的重登其实不需要 ddddocr）、缺「上次是否走了自动识别」回执。

## 五、待 Codex 拍板（不要替用户填默认值）

| # | 待定 | 现状 |
|---|---|---|
| P1 | 「存书签」三处提示的文案与位置 | 未实施，方向已获用户认可 |
| P2 | 手机页信息架构按哪一版落地 | M1–M10 + 建议方向，未定稿 |
| P3 | 账号与登录面板怎么合并 | D2–D8，未定稿 |
| P4 | 组件包与外部二进制的分发方式（谁装、怎么装、是否随包） | 用户明确「交给 Codex 决策」；本轮是我手工下载 |
| P5 | D7 是否解除「保存凭据必须先装 ddddocr」的绑定 | 未定：放开会影响 `feature_required` 的语义 |
| P6 | 点窗口 × 时是否给「最小化 / 退出 / 以后都这样」三选 | 用户已认可方向；方案见 9.1，未实施 |
| P7 | 代理怎么用：分请求类型、还是全局跟随系统代理 | 方案见 9.2，未实施；本轮不改代码 |
| P8 | Cloudflare 是否接受「临时通道」定位（不追固定入口） | 用户已明确不接命名隧道；确认见 9.3 |
| P9 | R1 的退避间隔用 5s/15s/40s/60s 还是别的节奏 | 方向已定（要自动重试），具体节奏交 Codex |

## 六、硬约束（返修计划必须遵守）

- 只服务本人账号；不开局域网入口；配对码不推送、不落日志。
- 不记录配对码、cookie 值、账号、密码、验证码；`phone.log` 只记请求行与 cookie **名**。
- 修改含中文文件后必须严格 UTF-8 解码 + 乱码黑名单检查；文件行尾保持原样（`local/README.md` 是 CRLF，其余目标文件是 LF）。
- 不引入新依赖；`.venv`、`local/data`、`server/data`、`node_modules` 不动。
- 提交需用户授权（本轮全部未提交）。

## 七、验收判据（可机械判断）

1. `python -X utf8 -m unittest local.tests.test_phone_ui local.tests.test_phone_service local.tests.test_phone_http local.tests.test_application_services local.tests.test_tunnel_manager local.tests.test_credential_store local.tests.test_phone_session_store` → 当前 **178 tests OK**，返修后不得下降。
2. `node --check local/ui/app.js`、`node --check local/ui/m/app.js`、`node --check local/ui/views/phone.js` 全部 exit 0。
3. `python -X utf8 -m compileall -q local server` exit 0。
4. `git diff --check` exit 0（允许仅有 `docs/OPERATIONS.md`、`local/requirements.txt` 两条入场既存行尾警告）。
5. 新增 UI 断言至少覆盖：D1 的 `[data-tone="info"]` 静态断言、手机页新结构的关键 id、书签提示文案。
6. 真机复验（用户执行）：Tailscale 通道配对一次后重启程序仍免配对；Cloudflare 通道重新开启会换域名并需要重新配对。
7. R1 的返修必须带测试：假时钟 + 假 NTP 源断言「首轮失败 → 5s/15s/40s 退避重试 → 成功后停止重试」，且顶栏重试入口可点。

## 八、未验证 / 已知不确定

- 手机页只在桌面 Edge 的 iPhone 模拟下渲染过，**没在真实 iPhone Safari 做视觉核对**；真机只验证了配对与恢复链路。
- iOS「相机扫码」与「地址栏手输」是不同存储上下文（实测手输免配对、扫码重复配对），但没验证「扫码后加入书签再打开」这条路径。
- Cloudflare 快速隧道无 SLA、每隧道最多 200 in-flight、不支持 SSE（官方文档）；产品的报名动作是短请求，暂不受影响，但长轮询改 SSE 就不行。
- `ddddocr` 已安装且功能显示「已启用」，但**没有真机跑过一次自动识别重登**；「手机上没出现验证码输入框」只是间接证据。
- 桌面帮助页的真实值来自本机 Tailscale（节点名已掩码），换机器后地址会变。

## 九、讨论已定、尚未实施的方案（细节交 Codex 定稿）

### 9.1 关闭窗口与后台常驻（对应 P6）

**问题**：点右上角 × 就是整个程序收尾——隧道停、手机访问断、正在跑的报名计划中止（2026-10-31 10:10 实测 job 以 exit 0 结束）。

**已核实的平台能力**（pywebview 6.2.1，已装版本源码）：`webview/window.py` 里
`self.events.closing = Event(self, True)`（第二个参数 `True` 表示可取消，处理器返回 `False` 即不关），
另有 `closed` / `minimized` / `maximized` / `shown` / `loaded` 等事件；`pystray` 未安装。
`local/app.py:2554` 的 `webview.start(debug=False)` **返回之后**才 `api.shutdown()`，所以拦住 `closing` 就能让
隧道、手机服务与报名计划继续跑。

**建议方案**：`closing` 里弹三选——「最小化到任务栏」「直接退出」「以后都这样」，
选择落 `ui.json` 键 `window.close_action`（复用现有 prefs 机制）；**报名计划执行中无条件先拦一次**，
默认按钮给「最小化」。最小化用 `window.minimize()`（任务栏图标保留、双击还原）。

**明确不做**：系统托盘（要 `pystray`，新依赖）、`window.hide()` 隐藏窗口（Windows 上任务栏图标消失，
没有托盘就找不回来）、开机自启。

### 9.2 代理与下载（对应 P7）

**现状（已核对代码，本轮未改）**：产品里**没有任何显式代理检测或配置**，但也不是「完全不走代理」——

| 位置 | 网络库 | 事实上是否走系统代理 |
|---|---|---|
| `local/update_check.py:118`（查 GitHub 最新版） | `urllib.request.urlopen` 默认 opener | **走**：Windows 下经 `urllib.request.getproxies()` 读注册表 `ProxyEnable/ProxyServer`，也读 `HTTP(S)_PROXY` |
| `local/updater.py:85`（下载安装器） | 同上 | 同上 |
| `local/grab.py:336/368/404/1050`（**学校接口**） | 同上 | **也走**——报名时序会经过代理，属风险点 |
| 组件包（`cloudflared` / ddddocr） | 产品内无下载逻辑，只有「选 ZIP 导入」 | 不涉及 |
| `tools/release.py:61` | 硬编码 `PROXY = "http://127.0.0.1:7897"` | 开发工具，不该有本机硬编码 |
| NTP 校时（`local/business_clock.py`） | UDP/123 | 不经代理（校时失败与代理无关） |

失败时只报「连接超时，请重试。」/「下载超时，请重试。」，不会提示「可能是代理问题」。

**推测方案（供 Codex 判断，不是定稿）**：

1. **按请求类型分层**：`school`（学校接口、报名提交）**强制直连**——时序敏感，不能引入代理跳数；
   `meta`（查最新版、下载安装器、下载组件包）**允许代理**。
2. **代理来源优先级**：`ui.json` 的 `network.proxy`（用户显式填）> 环境变量 > Windows 系统代理 > 直连。
3. **实现方式**：给 `urllib` 传独立 opener（`build_opener(ProxyHandler(...))`），
   **不要用全局 `install_opener`**，避免一个模块的配置污染另一个模块。
4. **失败可诊断**：日志与提示里写明「本次用代理 `127.0.0.1:7897` / 直连」，
   失败时额外给一个「重试（直连）」入口。
5. 帮助页或运行记录里显示一行网络状态（是否检测到系统代理）。
6. **不做**：自动修改系统代理、自动安装代理软件、把凭据/验证码写进代理配置、
   把 `tools/release.py` 的本机代理当产品配置。

### 9.3 Cloudflare 的生命周期语义（对应 P8，用户已确认）

| 情形 | 手机能否打开 | 是否需要重新配对 |
|---|---|---|
| 程序开着 + 隧道 running | 能 | **不需要**（同一隧道存活期内） |
| 程序关闭（点 × 或退出） | 不能（隧道随进程停止，`local/app.py:1882`、`:2104`） | — |
| 重开程序 + 仍是 Cloudflare | 需**手动**点开启（`restore_phone_access()` 只恢复 Tailscale） | **需要**（域名变、origin 变） |
| 重开程序 + 选 Tailscale | 自动恢复 | 不需要（固定地址 + 一年设备信任） |

结论：「掏出手机就能看」= **程序常驻 + Tailscale**；Cloudflare 定位为临时/应急通道。
让 Cloudflare 变固定入口的唯一路径是命名隧道（`cloudflared tunnel run --token` + 自有域名），用户已明确**不做**。

## 交给 Codex 的开场句

请先核对本材料第三节的代码位置与当前 HEAD 是否一致（`local/infrastructure/tunnel_manager.py` 的 `resolve_tailscale`、`local/infrastructure/phone_http.py` 的 `_allowed_hosts`、`local/application/phone_service.py` 的 `pair_code_status`、`local/ui/views/phone.js` 的 `pending`），再逐条向用户确认第五节 P1–P9（P6/P7/P8 的方案见第九节，属讨论结论、不是定稿），确认后出返修计划（含三道必修：D1 成功提示红色、R1 校时自动重试、以及第七节第 7 条要求的重试测试），出完停下等用户批准，不要直接改代码。
