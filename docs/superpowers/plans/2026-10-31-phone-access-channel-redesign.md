# 手机访问通道与组件分发 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把手机控制组件和 Tailscale/Cloudflare 两条远程通道改成可理解、可安装、可恢复、可真机验收的用户流程。

**Architecture:** 保留现有 `help-advanced` 手机访问入口，将“手机控制能力”“远程通道”“手机会话”拆成三个独立状态。`phone_control` 作为独立 Release 组件包，用户主动确认后通过项目现有 HTTPS/Release 下载与 SHA-256 校验流程安装；Tailscale 为默认长期通道，Cloudflare Quick Tunnel 为手动开启的临时通道。

**Tech Stack:** Python 3.10+、pywebview/WebView2、HTML/CSS/原生 JavaScript、现有 `update_check.py`/`updater.py` 下载校验链路、Python unittest。

## Global Constraints

- 只服务本人账号；不增加多账号、批量报名或代他人报名能力。
- 不增加局域网通道，不改变学校接口、登录态机制或数据模型。
- Tailscale 是默认长期通道；Cloudflare Quick Tunnel 是用户明确开启的临时/应急通道。
- 电脑重启后仅保证用户登录 Windows 且程序恢复运行后免重新扫码；不实现未登录 Windows 时的后台访问。
- 同一时间只运行一条远程通道；不自动从 Tailscale 故障切换到 Cloudflare。
- `phone_control` 组件包必须携带匹配版本的 `bin/cloudflared.exe` 和 manifest；禁止 PATH、程序目录或任意同名程序回退。
- 组件安装、下载、升级和移除均须由用户主动触发；不后台安装、不自动升级。
- 组件下载可使用系统/环境代理；学校接口请求必须直连；不增加代理编辑界面。
- 普通首次安装流程不显示路径输入框、裸 `cloudflared.exe` 选择器或“自检”二级按钮；本机导入完整组件包只保留在高级维护入口。
- 继续使用现有 UI 变量、字体、按钮和状态提示体系；不引入新依赖、渐变或新的顶级导航。
- 计划不自动提交，`plan.git.auto_commit=false`；提交权在用户手上。

---

### Task 1: 发布独立的 phone_control 组件资产

**Files:**
- Modify: `local/build_advanced.py`
- Modify: `tools/release.py`
- Modify: `local/update_check.py`
- Test: `local/tests/test_component_builder.py`
- Test: `local/tests/test_update_check.py`
- Test: `local/tests/test_lifecycle_release.py`

**Interfaces:**
- `local/build_advanced.py` 继续以 `phone_control` 为功能键，输出可安装 ZIP；其 manifest 必须声明 `feature=phone_control`、`target=win-x64`、组件版本、应用兼容版本、`bin/cloudflared.exe`、cloudflared 版本和文件 SHA-256。
- `local/update_check.py` 新增 `phone_control_asset_name(version: str) -> str`，命名为 `campus-activity-watch-phone-control-v{version}-win-x64.zip`。
- `select_release_assets(payload, version)` 返回 `phone_control` 资产的 `name/url/bytes`；只接受本仓库 GitHub Release 的 HTTPS 资产 URL。
- Release 资产校验必须沿用现有 manifest 版本、大小和 SHA-256 规则，不能接受任意外部下载地址。

- [ ] **Step 1: 写 Release 资产命名和 manifest 失败用例**

在 `local/tests/test_update_check.py` 增加断言：

```python
def test_phone_control_asset_name_is_stable():
    self.assertEqual(
        update_check.phone_control_asset_name("1.2.3"),
        "campus-activity-watch-phone-control-v1.2.3-win-x64.zip",
    )

def test_release_selection_rejects_phone_asset_outside_repository():
    payload = {"assets": [{
        "name": "campus-activity-watch-phone-control-v1.2.3-win-x64.zip",
        "browser_download_url": "https://example.com/component.zip",
        "size": 10,
    }]}
    picked = update_check.select_release_assets(payload, "1.2.3")
    self.assertIsNone(picked["phone_control"])
```

- [ ] **Step 2: 运行定向测试确认新增断言先失败**

运行：

```text
python -X utf8 -m unittest local.tests.test_update_check
```

预期：新增测试因资产命名函数或选择结果字段尚不存在而失败；不得修改测试来绕过失败。

- [ ] **Step 3: 实现组件资产命名、Release 选择和 manifest 校验**

在 `local/update_check.py` 中：

1. 增加 `phone_control_asset_name`。
2. 在 `select_release_assets` 的返回值中增加 `phone_control=None` 默认字段。
3. 只接受 `https://github.com/ShenTingBai/campus-activity-watch/releases/download/<tag>/<asset>` 形态的 URL。
4. 将组件资产的大小限制设为与现有安装器相同的上限，并复用现有版本解析和 manifest 校验。
5. 缺少组件资产、版本不符、manifest 不符时返回明确的 `no_component`/`manifest_invalid`，不回退到手动下载页。

在 `local/build_advanced.py` 中：

1. 保持 `phone_control` 没有 `--cloudflared` 时直接失败。
2. 生成的 ZIP 内必须有 `bin/cloudflared.exe` 和 manifest。
3. manifest 记录应用兼容版本、目标架构、cloudflared 版本和文件哈希。

在 `tools/release.py` 中：

1. `--prepare` 额外生成独立 phone_control ZIP。
2. `verify_release_assets`、`asset_digest`、`publish` 将该 ZIP 纳入 Release 资产和总 manifest。
3. 主程序 ZIP/EXE/安装器不自动安装该组件；组件作为独立可选资产发布。

- [ ] **Step 4: 运行定向测试确认 Release 资产契约通过**

运行：

```text
python -X utf8 -m unittest local.tests.test_update_check local.tests.test_component_builder local.tests.test_lifecycle_release
```

预期：exit 0；覆盖合法资产、外部 URL、缺失 manifest、错误版本、错误大小和错误哈希。

---

### Task 2: 增加用户主动触发的组件下载与安装事务

**Files:**
- Create: `local/application/advanced_component_service.py`
- Modify: `local/app.py`
- Modify: `local/infrastructure/advanced_features.py`
- Modify: `local/infrastructure/component_packages.py`
- Test: `local/tests/test_application_services.py`
- Test: `local/tests/test_component_packages.py`
- Test: `local/tests/test_updater.py`

**Interfaces:**
- 新服务只负责 phone_control 组件的“元数据读取、用户确认后的下载、取消、校验后安装、失败恢复”；低层字节下载复用 `updater.download_installer`，不复制其 HTTPS、`.part`、大小和 SHA-256 逻辑。
- `Api.advanced_features_state()` 增加 `phone_control.download`，至少包含 `state/request_id/text/downloaded/total_bytes/error_code/version`。
- 新增 `Api.download_advanced_feature(key="phone_control") -> dict`：只有 `phone_control` 且用户明确调用时开始下载；调用时若已有下载必须返回 `busy`，不得启动第二条。
- 新增 `Api.cancel_advanced_feature_download(key="phone_control") -> dict`：取消后删除临时文件并回到可再次安装状态。
- `Api.install_advanced_feature` 保留给高级维护导入；普通 UI 不再调用裸 `cloudflared.exe` 安装路径。

- [ ] **Step 1: 写组件下载状态机测试**

覆盖以下状态迁移：

```text
available -> confirm -> downloading -> verifying -> installed
available -> confirm -> cancelled
available -> confirm -> downloading -> failed
installed -> removing -> missing
```

断言：同一功能单飞；取消删除 `.part`；哈希失败保留旧安装；下载失败不写 `advanced_features=true`；安装成功后才写偏好。

- [ ] **Step 2: 运行定向测试确认状态机测试先失败**

运行：

```text
python -X utf8 -m unittest local.tests.test_application_services local.tests.test_updater local.tests.test_component_packages
```

预期：新增接口和状态尚不存在导致失败。

- [ ] **Step 3: 实现下载事务**

在 `local/application/advanced_component_service.py` 中：

1. 读取 `update_check` 返回的本仓库 Release 资产元数据。
2. 只有在 API 明确收到用户动作后才调用 `updater.download_installer`。
3. 使用现有系统/环境代理能力，不新增代理配置。
4. 下载期间发布 `downloading` 进度，每 1 MiB 至少发布一次，不能每个 64 KiB 片段都刷新 UI。
5. 下载完成后进入 `verifying`，调用 `component_packages.inspect_archive` 检查 feature、目标架构、manifest、cloudflared 版本和哈希。
6. 在临时目录完成验证后，调用现有 `component_packages.install` 做原子安装。
7. 安装失败时删除暂存目录、保留旧组件并返回可读错误。
8. 组件替换前停止手机访问；替换失败不能把旧组件标记为缺失。
9. 组件下载或安装期间禁用重复点击和移除按钮。

在 `local/app.py` 中：

1. 增加下载状态锁、request_id 和取消标记，不能复用更新安装器的 UI 状态字段。
2. `advanced_features_state()` 始终返回 phone_control 的安装状态和下载状态，即使组件未安装也不能隐藏入口。
3. `remove_advanced_feature("phone_control")` 先停止手机访问，再清理组件和手机会话；Tailscale 检测结果保持可用。

- [ ] **Step 4: 运行定向测试确认下载事务通过**

运行：

```text
python -X utf8 -m unittest local.tests.test_application_services local.tests.test_updater local.tests.test_component_packages
```

预期：exit 0；至少覆盖取消、断网、HTTP 错误、大小不符、哈希不符、旧组件保留、重复点击和移除。

---

### Task 3: 固化两条通道的生命周期和会话语义

**Files:**
- Modify: `local/app.py`
- Modify: `local/infrastructure/tunnel_manager.py`
- Modify: `local/application/phone_service.py`
- Modify: `local/ui/views/phone.js`
- Test: `local/tests/test_phone_service.py`
- Test: `local/tests/test_tunnel_manager.py`
- Test: `local/tests/test_phone_http.py`
- Test: `local/tests/test_application_services.py`

**Interfaces:**
- `Api.phone_access_state()` 必须同时返回 `features.phone_control`、`channels.tailscale`、`channels.cloudflare` 和 `active_channel`，前端不能用单个 `ready` 推导全部状态。
- `Api.start_phone_access(channel)` 必须显式拒绝缺少 verified phone_control 组件、Cloudflare 正在启动、另一条通道正在运行或通道不满足条件的请求。
- Cloudflare 退出归因为 `tunnel_exited` 时，状态读取必须一次性清除运行地址、QR 和临时会话，不得被第二次 `status()` 降级为 available。

- [ ] **Step 1: 写通道状态和旧地址清理测试**

覆盖：

1. Cloudflare 缺组件时不能启动。
2. PATH、程序目录和其他组件目录中的同名 `cloudflared.exe` 不能被使用。
3. Cloudflare 异常退出后首次 `phone_access_state()` 返回 `exited`，地址/QR 为空，第二次仍不是 `available`。
4. Tailscale 可用时 Cloudflare 失败不改变 Tailscale 状态。
5. Tailscale 重新启动后 `restart_requires_pairing=false`；Cloudflare 重新启动后必须生成新地址并重新配对。
6. 不能自动从 Tailscale 切换到 Cloudflare。

- [ ] **Step 2: 运行定向测试确认生命周期缺陷能被捕获**

运行：

```text
python -X utf8 -m unittest local.tests.test_phone_service local.tests.test_tunnel_manager local.tests.test_phone_http local.tests.test_application_services
```

预期：新增测试先覆盖当前错误状态或接口缺口。

- [ ] **Step 3: 实现后端生命周期语义**

1. 保留当前 Cloudflare 进程由程序拥有和回收的边界。
2. 启动前再次验证受管组件 manifest、文件哈希和 `--version`。
3. 只在 tunnel manager 返回新地址后写入 `phone_access_state`。
4. 退出时清理旧地址、QR、pairing URL 和 Cloudflare 会话；Tailscale 设备信任不清除。
5. 所有写请求继续读取当前 CSRF Cookie；不得因为本次通道设计改动登录或学校接口。

- [ ] **Step 4: 运行定向测试确认生命周期通过**

运行：

```text
python -X utf8 -m unittest local.tests.test_phone_service local.tests.test_tunnel_manager local.tests.test_phone_http local.tests.test_application_services
```

预期：exit 0。

---

### Task 4: 按现有桌面风格重做手机访问首次安装 UI

**Files:**
- Modify: `local/ui/index.html`
- Modify: `local/ui/views/phone.js`
- Modify: `local/ui/styles.css`
- Test: `local/tests/test_phone_ui.py`
- Test: `local/tests/test_ui_contract.py`

**Interfaces:**
- 继续使用现有 `help-advanced`、`phone-access-detail`、`help-status`、`dlg-components` 结构；不新增顶级导航。
- `#btn-phone-feature-install` 在 `missing/available/failed` 状态始终可见；按钮文案由状态派生。
- 新增的状态元素至少包括 `#phone-component-state`、`#phone-component-progress`、`#phone-component-error`、`#btn-phone-component-install` 和 `#btn-phone-component-cancel`；元素缺失时 JS 必须安全降级。
- `phone.js` 只通过 `PhonePanel` 管理组件下载、通道状态和手机会话，不能把 Cloudflare 状态串到 ddddocr 状态。

- [ ] **Step 1: 写 UI 状态断言**

断言以下用户可见行为：

1. phone_control 未安装时安装入口显示。
2. Cloudflare 缺组件时显示“安装组件”，不显示“没有找到 cloudflared”加空白区域。
3. 下载中显示进度并禁用重复安装/开启按钮；取消后可再次安装。
4. Tailscale 显示“长期”，Cloudflare 显示“临时”。
5. Cloudflare 运行中显示临时地址说明；退出后地址、QR 和配对码清空。
6. Tailscale 运行中显示稳定地址和免重新扫码说明。
7. 不出现路径输入框、裸 `cloudflared.exe` 选择器或普通用户可见的“自检”按钮。
8. 不自动切换通道，不自动开启 Cloudflare。
9. 保留统一书签提示，并追加 Cloudflare 换地址说明。

- [ ] **Step 2: 运行手机 UI 测试确认断言先失败**

运行：

```text
python -X utf8 -m unittest local.tests.test_phone_ui local.tests.test_ui_contract
```

预期：新增 UI 契约因元素或文案尚不存在而失败。

- [ ] **Step 3: 实现 UI**

1. 保留现有帮助弹窗位置和视觉变量：`--hall`、`--paper`、`--paper-2`、`--ink`、`--ink-2`、`--ink-3`、`--line`、`--blue`。
2. 将手机访问区改成“能力状态 + 通道选择 + 通道动作 + 地址/QR/配对”的单一纵向流程。
3. 首次组件安装使用一个轻量确认/进度区域；下载成功后回到“开启手机访问”，不自动公开通道。
4. 组件维护对话框只显示版本、校验状态、移除和折叠的完整组件包导入；保留 ddddocr 的独立入口。
5. 为状态变化保留键盘焦点、`aria-live` 和可读的下一步提示；不使用新的视觉装饰来代替状态文本。
6. Cloudflare 的临时/换地址语义在通道选择、地址区、停止结果和二维码说明中保持一致。

- [ ] **Step 4: 运行 UI 定向测试和语法检查**

运行：

```text
python -X utf8 -m unittest local.tests.test_phone_ui local.tests.test_ui_contract
node --check local/ui/app.js
node --check local/ui/m/app.js
node --check local/ui/views/phone.js
```

预期：测试和三个语法检查全部 exit 0。

---

### Task 5: 同步产品文档和真实验收清单

**Files:**
- Modify: `docs/PHONE_ACCESS.md`
- Modify: `local/README.md`
- Modify: `design/evidence/2026-10-31/mobile-ui-real-device-acceptance.md`
- Create: `design/evidence/2026-10-31/phone-access-channel-redesign-acceptance.md`

- [ ] **Step 1: 写文档断言清单**

文档必须明确：

1. Tailscale 是默认长期通道。
2. Cloudflare 是临时/应急通道，重启后不自动开启，每次重新开启需要新地址和新扫码。
3. 手机控制组件是可选功能；普通用户点击安装即可，不需要选择文件或配置 PATH。
4. 电脑重启后的验收前提是用户登录 Windows 并启动程序；不承诺未登录 Windows 时可访问。
5. Cloudflare 旧地址、QR、配对会话在退出后失效。
6. 下载使用系统/环境代理，学校接口直连。

- [ ] **Step 2: 写真实验收步骤**

在新证据文档中加入以下可逐项记录的步骤：

**Tailscale 首次和重启：**

1. 确认手机控制组件未隐藏，组件状态可见。
2. 选择 Tailscale，确认未安装/未登录时提示明确。
3. Tailscale 就绪后开启手机访问，记录地址、二维码和配对码。
4. 手机扫码并输入配对码，验证查看活动、打开报名计划和重登入口。
5. 关闭并重新启动程序；登录 Windows 后再次打开同一地址，确认不要求重新扫码。

**Cloudflare 首次、异常退出和重开：**

1. 选择 Cloudflare，确认入口显示“临时”且组件缺失时有“安装组件”。
2. 点击安装，确认只有确认、进度、校验和结果步骤，不要求选路径。
3. 安装成功后手动开启 Cloudflare，确认出现新地址、二维码和配对码。
4. 手机上扫码并输入配对码，验证手机控制台可用。
5. 停止 Cloudflare，确认旧地址和旧二维码不再显示且旧地址不能访问。
6. 强制结束 `cloudflared`，刷新桌面状态，确认显示“临时通道已失效”，不是“可用”。
7. 重新开启 Cloudflare，确认地址改变，手机必须重新扫码和输入配对码。
8. 关闭程序并重新启动，确认 Cloudflare 不会自动开启。

**安全与边界：**

1. 将同名 `cloudflared.exe` 放入 PATH、程序目录或其他组件目录，确认不会被执行。
2. 替换组件文件或修改 manifest，确认启动被拒绝。
3. Cloudflare 失败时确认 Tailscale 状态不被破坏，也不会自动公开通道。

- [ ] **Step 3: 运行文档/文案契约测试**

运行：

```text
python -X utf8 -m unittest local.tests.test_ui_contract local.tests.test_component_packages
```

预期：文档和 UI 文案与已拍板通道语义一致。

---

### Task 6: 回归验证与用户验收门禁

**Files:**
- Modify: `design/evidence/2026-10-31/phone-access-channel-redesign-acceptance.md`

- [ ] **Step 1: 运行本机全量验证**

只有获得本轮测试授权后运行：

```text
python -X utf8 -m unittest discover -s local/tests -p "test_*.py"
python -X utf8 -m compileall local server
node --check local/ui/app.js
node --check local/ui/m/app.js
node --check local/ui/views/phone.js
git -c core.whitespace=cr-at-eol diff --check
```

预期：所有命令 exit 0；乱码检查无命中；不修改已有 CRLF 文件以“消除”假阳性。

- [ ] **Step 2: 审核改动范围**

确认只修改本计划列出的文件和本轮新增证据文档；不执行 `git add -A`，不清理入场脏改动，不提交。

- [ ] **Step 3: 停在用户真机验收**

把自动化验证与用户验收分开记录。只有用户完成 Tailscale 和 Cloudflare 两组真实步骤后，才能把 `acceptance_status` 从 `pending_user_review` 改为通过。

## Plan Self-Review

- 组件分发、下载事务、通道生命周期、桌面 UI、文档和真机验收分别有独立任务。
- 计划没有把 Cloudflare 的临时地址当成长期地址，也没有引入自动故障转移。
- 计划没有改变学校接口、登录态、活动数据模型或 ddddocr 业务规则。
- 计划没有承诺 Windows 未登录时远程访问。
- 计划保留当前项目的下载校验、状态机、代理、临时文件和 UI 视觉约束。

## Execution Notes

执行前必须确认当前工作区仍有其他 agent 的脏改动；只修改本计划列出的目标文件。验证命令由执行器按项目授权规则运行，计划本身不自动提交。
