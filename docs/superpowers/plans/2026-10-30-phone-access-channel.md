# 手机远程访问通道与持久会话 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让手机远程访问在现有帮助入口内形成清晰的 Tailscale 主通道与 Cloudflare 临时通道；Tailscale 配对后的设备信任可跨程序/电脑重启恢复，Cloudflare 重启后明确要求重新扫码。

**Architecture:** 保留现有三层边界：手机控制是可选功能包，Tailscale/Cloudflare 是外部远程通道，配对与设备信任是会话层。Tailscale 使用 Windows DPAPI 保护的持久设备信任记录，程序重启时只恢复设备信任和 Tailscale 监听；Cloudflare Quick Tunnel 不自动恢复，地址变化时要求重新扫码。帮助页继续使用现有“跨设备访问与高级功能”区域，不新增顶层入口。

**Tech Stack:** Python 3.10+、标准库 HTTP 服务、Windows DPAPI、pywebview API、HTML/CSS/JavaScript、Node `vm` 行为测试、Python `unittest`。

## Global Constraints

- 远程产品入口只允许 Tailscale 与 Cloudflare；不新增普通局域网、公网 IP 或 IPv6 入口。
- 只有 Tailscale 做持久设备信任与自动恢复；Cloudflare Quick Tunnel 每次重启后地址变化，必须重新扫码。
- 持久设备 cookie 只发给 Tailscale 配对；Cloudflare 配对只发当前活动会话 cookie，不能把临时通道变成持久入口。
- Tailscale 默认通道；Cloudflare 与 Tailscale 并列展示，但始终标注“临时地址，重启后需重新扫码”。
- 首次教程固定为帮助页内联四步文字说明，首次打开时保持可见；不新增模态向导、截图或录屏维护链路。
- 通道选择写入现有 prefs；通过专用的手机访问偏好接口更新，不让 UI 直接提交任意 prefs；不新建独立偏好文件，不新增 `guide_url` 等 API 字段。
- Tailscale 同时展示 MagicDNS 名和 `100.x` 原始地址；二维码只使用一个首选公开地址，备用地址仅用于复制和排障，配对后不要在两个地址之间来回切换；配对码不进入 URL、不落日志、不进二维码。
- “复制地址”使用跨浏览器可降级的复制实现；不做无法由普通浏览器可靠控制的“自动加入书签”按钮。
- 关闭手机访问使用现有帮助弹窗内的阻断式确认行；确认后撤销手机设备信任并要求下一次重新配对，取消不调用停止 API。
- 首版不增加 cloudflared 看门狗；必须能检测隧道退出并显示重新开启提示。
- 不自动下载、安装或启动 Tailscale/cloudflared；“重新检测 Tailscale”必须真实调用探测。
- 不修改学校登录协议、业务数据模型或登录态机制；不引入新依赖。
- 不修改 `local/data`、`server/data`、`.venv`、`node_modules`、`server/`；运行时生成的 DPAPI 文件不进入版本库。
- 新增或修改含中文文件后执行严格 UTF-8 解码和乱码黑名单检查。
- 本轮只写计划，不运行构建、测试或发布命令；执行阶段需要单独授权验证命令，Git 提交另需授权。

## Decisions captured from the discussion

- Tailscale 是稳定主通道，配对一次后设备信任跨程序重启、电脑重启和手机网络切换恢复。
- Cloudflare 是 Quick Tunnel 临时降级通道，不承诺固定域名；程序或电脑重启后重新扫码。
- 首次引导直接放在现有帮助区域，避免用户出门后才发现前置条件。
- Tailscale 设备信任与当前 8 小时活动会话分离：设备信任用于重启后恢复，活动会话仍按现有安全边界运行；设备信任默认保存一年，手动关闭或移除手机控制立即撤销。
- 设备信任只存 DPAPI 密文中的 token hash、创建时间和最近使用时间；不把手机 cookie 明文写入文件。
- 账号密码入口继续留在帮助页的“高级功能”区域；手机控制与 ddddocr 独立安装，凭据保存沿用现有本机 DPAPI 入口，不新增顶层菜单。

---

### Task 0: 完成 Tailscale 状态取证并冻结探测契约

**Files:**
- Create: `design/evidence/2026-10-30/tailscale-probe.md`
- Test: `local/tests/test_tunnel_manager.py`

**Interfaces:**
- Consumes: 本机 `tailscale status --json` 与 `tailscale ip -4` 的三种真实状态。
- Produces: `tailscale_endpoint()` 对“未安装、已安装未登录、已连接、探测失败”的稳定字段约定，供后续 UI 和自动恢复使用。

- [ ] **Step 1: 采集未安装/未登录/已连接状态**

  在执行机上取得当前可用状态；未安装或未登录状态可用不含账号、cookie、token 的替身输出补齐，不为取证强行安装或退出 Tailscale：

  ```powershell
  tailscale status --json
  tailscale ip -4
  ```

  记录命令是否存在、`Self.DNSName`、IPv4 列表和 `BackendState` 原始值；不得把完整环境变量、账号信息或日志凭据写入证据。已连接状态必须来自真实命令或用户/DS 提供的脱敏结果，不能由替身冒充。

- [ ] **Step 2: 固定状态映射测试**

  在 `local/tests/test_tunnel_manager.py` 增加替身 JSON，明确断言：

  ```python
  self.assertEqual(result["state"], "connected")
  self.assertEqual(result["error"], "tailscale_not_logged_in")
  self.assertEqual(result["error"], "tailscale_missing")
  ```

  实际枚举值以 Step 1 证据为准；未知值必须归入 `tailscale_probe_failed`，不能假装可用。

- [ ] **Step 3: 运行聚焦探测测试**

  执行阶段运行：

  ```powershell
  python -X utf8 -m unittest local.tests.test_tunnel_manager -v
  ```

  预期：探测状态映射全部通过，未知状态不会返回 `available: true`。

---

### Task 1: 增加 DPAPI 设备信任存储

**Files:**
- Modify: `local/infrastructure/credential_store.py`
- Create: `local/infrastructure/phone_session_store.py`
- Modify: `local/tests/test_credential_store.py`
- Create: `local/tests/test_phone_session_store.py`

**Interfaces:**
- Consumes: 现有 `_protect` / `_unprotect` DPAPI 边界和 `DATA_DIR`。
- Produces:
  - `save_document(path: Path, document: dict) -> None`
  - `load_document(path: Path) -> dict`
  - `PhoneSessionStore.add_device(token: str, now: float) -> None`
  - `PhoneSessionStore.validate_device(token: str, now: float) -> bool`
  - `PhoneSessionStore.revoke_all() -> None`

- [ ] **Step 1: 先写 DPAPI 文档存储测试**

  覆盖以下契约：

  ```python
  credential_store.save_document(path, {"version": 1, "devices": []})
  self.assertEqual(credential_store.load_document(path)["version"], 1)
  self.assertNotIn(b"plain-secret", path.read_bytes())
  ```

  DPAPI 失败时必须不创建明文回退文件；损坏 JSON、错误 base64 和版本不支持必须抛出 `CredentialStoreError`。

- [ ] **Step 2: 实现通用 DPAPI 文档封装**

  让现有账号密码 `save()` / `load()` 复用文档封装，但保持原有外层 JSON 形状和测试契约不变。新增文档函数只接收字典，不接受任意字符串路径内容。

- [ ] **Step 3: 写设备信任存储测试**

  使用临时路径和 fake DPAPI，覆盖：首次加入、重复加入幂等、有效 token、未知 token、设备信任一年后过期、`revoke_all()` 清空、文件中不出现 token 明文。

- [ ] **Step 4: 实现 `PhoneSessionStore`**

  文件内只保存如下密文载荷，token 使用 SHA-256 hash，比较时使用 `hmac.compare_digest`：

  ```python
  {
      "version": 1,
      "devices": [
          {"token_hash": "...", "created_at": 0.0, "last_seen_at": 0.0}
      ]
  }
  ```

  `validate_device()` 在一年未使用后返回 `False` 并清理过期记录；任何读写异常都按“没有持久设备信任”处理，不把异常原文返回 UI。

- [ ] **Step 5: 运行存储测试**

  执行阶段运行：

  ```powershell
  python -X utf8 -m unittest local.tests.test_credential_store local.tests.test_phone_session_store -v
  ```

  预期：所有密文边界、过期、撤销和损坏文件测试通过。

---

### Task 2: 让手机服务区分活动会话、设备信任和手动撤销

**Files:**
- Modify: `local/application/phone_service.py`
- Modify: `local/infrastructure/phone_http.py`
- Modify: `local/domain/phone_rules.py`
- Modify: `local/tests/test_phone_service.py`
- Modify: `local/tests/test_phone_http.py`

**Interfaces:**
- Consumes: `PhoneSessionStore`、现有会话 cookie/CSRF 校验、Origin/Host 校验。
- Produces:
  - `PhoneAccessService(..., device_store=...)`
- `PhoneAccessService.start(..., persistent_device: bool = False) -> dict`
  - `PhoneAccessService.shutdown(preserve_devices: bool = True) -> dict`
  - `PhoneAccessService.stop(revoke_devices: bool = True) -> dict`
  - `PhoneAccessService.authenticate_or_restore(cookie_header, device_cookie_header) -> tuple[dict | None, list[str]]`
  - Tailscale 配对响应设置持久设备 cookie、活动 session cookie 和 CSRF cookie；Cloudflare 配对只设置活动 session cookie 和 CSRF cookie。

- [ ] **Step 1: 写失败测试锁定生命周期**

  增加以下场景：

  ```python
  service.start("100.64.0.2", persistent_device=True)
  first = service.pair(service.current_pair_code(), ip="100.64.0.2")
  service.shutdown(preserve_devices=True)
  restarted = new_service_with_same_store()
  restarted.start("100.64.0.2", persistent_device=True)
  session, headers = restarted.authenticate_or_restore("", first["device_cookie"])
  self.assertIsNotNone(session)
  self.assertTrue(any(name == "Set-Cookie" for name, _ in headers))
  ```

  同时断言：手动 `stop()` 后旧设备 cookie 失效；Cloudflare 不调用自动恢复；一码一次、限速和现有 CSRF 规则不变。

- [ ] **Step 2: 增加设备 cookie 与恢复协议**

  新增独立设备 cookie 名称，例如 `campus_phone_device`，仅在 Tailscale 通道设置 `HttpOnly`、`SameSite=Strict`、`Path=/` 和一年 `Max-Age`；Cloudflare 不写该 cookie。二维码和配对码仍不携带任何 cookie 或参数。

  `pair()` 根据 `persistent_device` 决定是否返回 `device_cookie`；`/api/state` 在活动 session 无效但 Tailscale 设备 cookie 有效时，创建新的活动 session 和 CSRF cookie，并通过响应头回写。Cloudflare 请求永远不进入设备恢复分支；手机端下一次轮询即可恢复 Tailscale 会话，无需再次输入配对码。

- [ ] **Step 3: 区分正常重启与用户关闭**

  `shutdown(preserve_devices=True)` 只停止监听并清理内存活动 session，不清除 DPAPI 设备信任；`stop(revoke_devices=True)` 用于帮助页“关闭手机访问”，清除设备信任并让下一次访问回到配对页。`AppApi.shutdown()` 的正常进程收尾必须调用前者；移除手机控制高级功能也必须走后者。

- [ ] **Step 4: 保持 HTTP 安全边界**

  设备恢复仍必须经过 Host/Origin、Tailscale 绑定地址、CSRF 和动作白名单；设备 cookie 只能恢复会话，不能绕过条款、计划状态、请求体上限或动作白名单。

- [ ] **Step 5: 运行手机服务与 HTTP 回归**

  执行阶段运行：

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_service local.tests.test_phone_http -v
  ```

  预期：手动关闭撤销成功、正常重启恢复成功、旧 session/设备 token 不能跨撤销继续访问。

---

### Task 3: 记住通道并恢复 Tailscale，Cloudflare 保持临时

**Files:**
- Modify: `local/app.py`
- Modify: `local/infrastructure/tunnel_manager.py`
- Modify: `local/tests/test_tunnel_manager.py`
- Modify: `local/tests/test_application_services.py`

**Interfaces:**
- Consumes: `load_prefs()` / `update_prefs()`、`tailscale_endpoint()`、`CloudflareTunnel`。
- Produces:
  - prefs 命名空间 `phone_access.preferred_channel` 与 `phone_access.tailscale_autostart`
  - `AppApi.set_phone_access_preferences(preferred_channel: str) -> dict`
  - `AppApi.restore_phone_access() -> dict`
  - `advanced_features_state()` / `phone_access_state()` 返回通道状态、地址候选和 Cloudflare 临时性说明。

- [ ] **Step 1: 写 prefs 与恢复测试**

  覆盖以下矩阵：

  | 偏好 | 探测 | 预期 |
  |---|---|---|
  | Tailscale + 自动恢复 | connected | 启动手机服务并恢复设备信任 |
  | Tailscale + 自动恢复 | missing/not logged in | 不监听，返回可操作诊断 |
  | Cloudflare 上次使用 | 任意 | 不自动启动隧道，提示重新开启 |
  | 手动关闭后 | connected | `tailscale_autostart=false` 且设备信任已撤销 |

- [ ] **Step 2: 实现通道偏好与自动恢复**

  增加专用 `set_phone_access_preferences(preferred_channel)` API，通道选择变化时只写入 `phone_access.preferred_channel`。成功开启 Tailscale 后写入 `phone_access.tailscale_autostart=true`；帮助页手动关闭时清除自动恢复并撤销设备信任。成功开启 Cloudflare 只记录最近选择，不写自动恢复开关。

  在窗口桥接准备完成且条款已通过后调用 `restore_phone_access()`；失败只返回诊断，不自动安装、不启动 Tailscale 守护进程。

- [ ] **Step 3: 完善通道状态投影**

  `advanced_features_state()` 和 `phone_access_state()` 返回：Tailscale `state/error/text/magicdns/addresses/public_host`，Cloudflare `available/error/text/temporary/restart_requires_pairing`，以及当前通道、首选通道、可复制地址候选和运行状态。不要新增 `guide_url`。

- [ ] **Step 4: 增加 Cloudflare 退出状态但不做看门狗**

  `CloudflareTunnel` 增加只读 `status()` 或等价查询：子进程退出后清空 `public_url` 并返回可识别的失败状态；不自动重启、不保留旧地址宽限。UI 通过“重新开启”恢复。

- [ ] **Step 5: 运行通道测试**

  执行阶段运行：

  ```powershell
  python -X utf8 -m unittest local.tests.test_tunnel_manager local.tests.test_application_services -v
  ```

  预期：Tailscale 自动恢复矩阵、Cloudflare 不自动恢复和隧道退出状态全部通过。

---

### Task 4: 在现有帮助入口完成通道引导和状态 UI

**Files:**
- Modify: `local/ui/index.html`
- Modify: `local/ui/styles.css`
- Modify: `local/ui/views/phone.js`
- Modify: `local/tests/test_phone_ui.py`

**Interfaces:**
- Consumes: `phone_access_state()` 的 `channels`、`preferred_channel`、`address`、`qr`、`pair_code` 和诊断文案。
- Produces: 现有帮助段内的四步引导、通道状态、地址复制、重新检测、Cloudflare 临时警告和关闭确认。

- [ ] **Step 1: 写 UI 结构与状态断言**

  增加静态与行为断言：

  ```python
  self.assertIn("先扫二维码，再输入配对码", html)
  self.assertIn('id="btn-phone-address-copy"', html)
  self.assertIn('id="btn-tailscale-recheck"', html)
  self.assertIn("重启后需重新扫码", html)
  ```

  行为测试覆盖：Tailscale 状态与 Cloudflare 状态独立渲染、MagicDNS/IP 两个地址的显示、复制成功/失败通用提示、重新检测真实调用 API、关闭访问取消时不调用停止 API。

- [ ] **Step 2: 保持现有入口并增加内联四步说明**

  在现有 `help-tools help-advanced` 内加入短说明：

  1. 在电脑和手机上准备同一 Tailscale 网络，或选择 Cloudflare 临时地址。
  2. 点击“开启手机访问”，先扫二维码。
  3. 再输入电脑显示的 6 位配对码。
  4. Tailscale 可跨重启恢复；Cloudflare 重启后需重新扫码。

  配对成功后再显示“复制地址”和“在手机浏览器菜单中加入书签/主屏幕”的提示；不承诺网页自动操作系统书签。不新增顶层菜单、不做模态弹窗、不把配对码拼进地址。

- [ ] **Step 3: 实现通道与地址呈现**

  `PhonePanel.paint()` 按通道独立渲染：

  - Tailscale：显示连接状态、MagicDNS 主地址、`100.x` 备用地址和“重新检测”；二维码只对应主地址，备用地址用于复制和排障。
  - Cloudflare：显示当前临时地址和“重启后需重新扫码”警告。
  - 运行中显示二维码、配对码和“复制地址”；未运行隐藏配对信息。
  - 地址复制优先使用 `navigator.clipboard.writeText()`，失败时使用一次性 textarea + `document.execCommand("copy")`，两条路径都只显示通用结果。

- [ ] **Step 4: 实现选择记忆与关闭确认**

  通道选择变化时调用 `set_phone_access_preferences` 保存 prefs。关闭按钮先在现有帮助弹窗内展开阻断式确认行，明确写出“关闭后手机会失去访问，需要重新扫码”；“取消”只收起确认行，“确认关闭”才调用 `stop_phone_access`，不使用嵌套 dialog 或浏览器原生 `window.confirm`。

- [ ] **Step 5: 运行手机 UI 测试**

  执行阶段运行：

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_ui -v
  node --check local/ui/app.js
  node --check local/ui/m/app.js
  ```

  预期：原有 24 项与新增通道状态/复制/确认断言全部通过，两处语法检查退出码为 0。

---

### Task 5: 同步使用说明和安全边界

**Files:**
- Modify: `docs/PHONE_ACCESS.md`
- Modify: `local/README.md`

**Interfaces:**
- Consumes: Task 3/4 的最终字段、文案和生命周期。
- Produces: 帮助页和文档一致的四步教程、通道差异、重启行为和撤销边界。

- [ ] **Step 1: 更新四步教程**

  文档必须明确写出“先扫二维码，再输入配对码”，并说明配对码不进 URL、不落日志、一码一次。

- [ ] **Step 2: 更新通道差异**

  Tailscale 段写明：默认通道、MagicDNS/IP 地址、配对设备信任跨程序/电脑重启恢复、手机需要加入同一 tailnet。

  Cloudflare 段写明：Quick Tunnel、临时域名、无固定入口、重启后重新扫码；不写下载或自动安装指引。

- [ ] **Step 3: 更新关闭与安全边界**

  写明帮助页确认关闭会撤销设备信任；程序正常重启保留 Tailscale 设备信任，但当前活动 session 会重新建立；移除手机控制高级功能会清除设备信任；Cloudflare 不保存持久设备 cookie；电脑必须保持唤醒。

- [ ] **Step 4: 做文案一致性检查**

  使用静态搜索确认帮助页和两份文档都包含同一套四步核心文案，并且没有“局域网入口”“Cloudflare 固定地址”“自动安装 Tailscale”等过时描述。

---

### Task 6: 完成离线回归与真实设备验收材料

**Files:**
- Create: `design/evidence/2026-10-30/phone-access-acceptance.md`
- Test: `local/tests/test_phone_session_store.py`
- Test: `local/tests/test_phone_service.py`
- Test: `local/tests/test_phone_http.py`
- Test: `local/tests/test_tunnel_manager.py`
- Test: `local/tests/test_phone_ui.py`

**Interfaces:**
- Consumes: Tasks 0–5 的代码、文案和探测证据。
- Produces: 可区分的离线技术验证、Tailscale 真机验收、Cloudflare 临时通道验收和未验证范围。

- [ ] **Step 1: 运行完整本机回归**

  执行阶段运行：

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_session_store local.tests.test_phone_service local.tests.test_phone_http local.tests.test_tunnel_manager local.tests.test_phone_ui -v
  python -X utf8 -m compileall local server
  node --check local/ui/app.js
  node --check local/ui/m/app.js
  git diff --check
  ```

  预期：所有测试通过，compileall 退出码为 0，两处 node 检查退出码为 0，`git diff --check` 无错误输出。

- [ ] **Step 2: 执行 UTF-8 与乱码检查**

  对所有修改的中文文件执行严格 UTF-8 解码，并运行 AGENTS.md 黑名单扫描；预期无非法 UTF-8、无乱码命中。

- [ ] **Step 3: 验收 Tailscale 持久会话**

  在真实设备上记录：

  1. Tailscale 开启 → 扫码 → 输入配对码 → 手机进入主界面。
  2. 关闭手机浏览器后从复制地址/书签重新打开，不重新配对。
  3. 正常重启程序后重新打开，不重新配对。
  4. 重启电脑后重新打开，不重新配对。
  5. 手机 Wi-Fi 与移动数据切换后仍能访问，前提是手机 Tailscale 仍连接同一 tailnet。
  6. 电脑点击“关闭手机访问”并确认后，手机下一次轮询回到配对页；旧 cookie 不能恢复。

- [ ] **Step 4: 验收 Cloudflare 临时通道**

  使用手机移动数据完成一次配对；确认显示临时地址和警告。重启程序后确认旧地址不可作为稳定入口，新地址需要重新扫码和输入配对码。确认 Cloudflare 不会自动启动、不显示为持久通道。

- [ ] **Step 5: 记录验收边界**

  证据只记录时间、通道、状态、是否需要重新配对和截图；不记录账号、密码、验证码、cookie、token、完整请求头或完整 URL 查询参数。

---

## Self-review

- 讨论材料的 9 个未决项已全部给出具体决策，并写入对应任务：入口形态、prefs 落点、Cloudflare 位置、地址展示、教程媒体、看门狗、复制/书签、关闭确认和 `guide_url`。
- Tailscale 与 Cloudflare 的重启语义已拆开，避免把 Quick Tunnel 的随机域名误当成固定入口。
- 当前内存会话与“程序重启免重扫”的冲突已通过独立设备信任层解决；手动关闭仍然撤销，保持用户可控。
- 不新增局域网入口、不自动安装外部程序、不改变学校登录协议和业务数据。
- 真实 Tailscale/Cloudflare/手机验收仍是独立证据，不会被本机测试绿灯替代。
- 本轮只生成计划文件，未修改源码、未运行测试、未提交 Git。
