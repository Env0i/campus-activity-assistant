# 手机帮助页与重登恢复失败修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复当前手机 UI 定向测试暴露的 6 个问题，让高级功能状态、账号保存失败、已有会话恢复、验证码恢复和“换一张图”都与当前产品契约一致。

**Architecture:** 保留现有 `PhonePanel`（桌面帮助弹窗）与 `PhoneUI`（手机页面）边界。桌面帮助只负责呈现两个独立高级功能的状态并安全处理失败；手机页面从 cookie 恢复 CSRF、从状态快照恢复重登挑战，并把刷新验证码实现为“取消旧场 + 开始新场”。测试 harness 只补齐它承诺提供的 DOM 辅助函数，不改变业务断言。

**Tech Stack:** HTML/CSS/JavaScript、Node `vm` 行为测试、Python `unittest`、pywebview API。

## Global Constraints

- 不引入新依赖；不修改 `local/data`、`server/data`、`.venv`、`node_modules`。
- 手机远程入口仍只允许 Tailscale 与 Cloudflare；不新增局域网入口。
- 手机控制与 ddddocr 保持两个独立高级功能；未安装 ddddocr 时保留人工验证码路径。
- 账号密码失败时清空输入框，不把异常原文展示给用户。
- 修改含中文文件后执行 UTF-8 严格解码与乱码黑名单检查。
- 本轮不提交 Git；完成后报告改动、验证和未验证的真实设备范围。

---

### Task 1: 修复桌面帮助页高级功能状态与失败处理

**Files:**
- Modify: `local/ui/index.html:227-257`
- Modify: `local/ui/views/phone.js:7-170`
- Test: `local/tests/test_phone_ui.py:33-141,378-419`

**Interfaces:**
- Consumes `phone_access_state.advanced.features.phone_control` 与 `relogin_ocr` 的 `available/enabled/ready/status/install_mode` 字段。
- Produces independent status labels and safe button labels; `PhonePanel.install()` resolves canceled results without showing success feedback; `PhonePanel.saveCredentials()` catches API failures and always clears inputs.

- [ ] **Step 1: Write failing behavior coverage**

  Assert these projections for `PhonePanel.paint()`:

  ```javascript
  PhonePanel.state.advanced = {features: {
    phone_control: {available: true, enabled: false, ready: false, status: "ready"},
    relogin_ocr: {available: false, enabled: false, ready: false, status: "failed", install_mode: "import"}
  }};
  PhonePanel.paint();
  // phone: 已停用 + 启用手机控制; OCR: 加载失败 + 重新导入组件包
  ```

  Add DOM IDs `ocr-feature-status` and `phone-control-status` only where they are needed by the existing help contract; preserve the current section layout.

- [ ] **Step 2: Run the focused tests and observe the current failures**

  Run:

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_ui.HelpAdvancedBehaviorTests -v
  ```

  Expected before implementation: current labels remain `未安装`/`安装 ddddocr`, and thrown credential-save errors escape the UI handler.

- [ ] **Step 3: Implement the smallest UI state projection**

  In `PhonePanel.paint()`, derive each feature independently:

  ```javascript
  function featureCopy(row, fallback) {
    if (row && row.status === "failed") return {status: "加载失败", action: "重新导入组件包"};
    if (row && row.ready) return {status: "已启用", action: ""};
    if (row && row.available) return {status: "已停用", action: "启用" + fallback};
    return {status: "未安装", action: "安装" + fallback};
  }
  ```

  Keep `phone-access-detail.hidden = !phone.ready`; do not let OCR state control the phone panel. Guard `channel.options` before reading `namedItem`.

- [ ] **Step 4: Make busy and failure paths observable but safe**

  `PhonePanel.install()` must set `busy`, call `paint()`, and in `finally` clear `busy`; a result with `canceled: true` must not call `helpStatus()`.

  `PhonePanel.saveCredentials()` must use `try/catch/finally`, clear both fields in `finally`, convert thrown errors to `{ok:false,text:"账号信息没有保存。"}`, and call `refresh()` after releasing `busy`. Never include the caught error message in UI text.

- [ ] **Step 5: Run the focused tests**

  Run:

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_ui.HelpAdvancedBehaviorTests -v
  ```

  Expected: all help-page behavior tests pass.

---

### Task 2: 修复手机页面现有会话恢复与重登 UI 状态

**Files:**
- Modify: `local/ui/m/app.js:131-537`
- Modify: `local/tests/test_phone_ui.py:34-141,422-463`

**Interfaces:**
- `PhoneUI.ingest(payload)` accepts both event updates and `payload.state.login_relay` snapshots.
- `PhoneUI.refreshRelogin()` performs one cancel request followed by one begin request.
- `PhoneUI` restores `campus_phone_csrf` from `document.cookie` before POST requests.

- [ ] **Step 1: Add failing recovery assertions**

  Cover the following exact outcomes:

  ```javascript
  document.cookie = "campus_phone_csrf=fixture-csrf";
  await PhoneUI.poll(true);
  // a POST carries X-Campus-Csrf: fixture-csrf

  PhoneUI.ingest({state: {login_relay: {
    state: "waiting_code", flow_id: "f1", challenge_id: "c1",
    image: "data:image/png;base64,AAAA"
  }}});
  // challenge is rendered; a second identical snapshot keeps typed code

  await PhoneUI.refreshRelogin();
  // actions are exactly phone_relogin_cancel, phone_relogin_begin
  ```

- [ ] **Step 2: Run the focused recovery tests and observe the current failures**

  Run:

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_ui.PhoneReloginRecoveryTests -v
  ```

  Expected before implementation: `$` is unavailable in the harness, direct snapshots are ignored, and `refreshRelogin` is missing.

- [ ] **Step 3: Implement cookie and snapshot restoration**

  Add a small `readCookie(name)` helper that parses `document.cookie`; in `poll()` initialize `model.csrf` from `campus_phone_csrf` when it is empty. In `ingest()`, call `ingestRelogin(state.login_relay)` before processing events when that snapshot exists.

- [ ] **Step 4: Implement refresh and terminal control rendering**

  Add:

  ```javascript
  async function refreshRelogin() {
    await cancelRelogin();
    await beginRelogin();
  }
  ```

  Export it on `globalThis.PhoneUI` and wire `btn-relogin-refresh` to it. When a flow succeeds or ends, show the `btn-relogin` button and hide submit/refresh/cancel/captcha; when a challenge arrives, apply the inverse. Identical challenge snapshots must return without clearing the typed code.

- [ ] **Step 5: Run focused recovery tests**

  Run:

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_ui.PhoneReloginRecoveryTests -v
  ```

  Expected: all recovery tests pass.

---

### Task 3: 修复测试 harness 契约并完成回归验证

**Files:**
- Modify: `local/tests/test_phone_ui.py:65-105`
- Test: `local/tests/test_phone_ui.py`

**Interfaces:**
- The Node VM harness exposes `$`, `api`, cookie storage, and the minimal DOM functions used by snippets, without changing production code behavior.

- [ ] **Step 1: Expose the documented DOM helpers in every harness mode**

  Define `sandbox.$ = (selector) => el2(selector)` before loading either `app.js` or view files. Keep the existing `api` shim for view-only runs and add a simple `document.cookie` string property.

- [ ] **Step 2: Run the complete phone UI test file**

  Run:

  ```powershell
  python -X utf8 -m unittest local.tests.test_phone_ui -v
  ```

  Expected: all 24 tests pass.

- [ ] **Step 3: Run broader verification**

  Run:

  ```powershell
  python -X utf8 -m unittest local.tests.test_login_relay local.tests.test_login_relay_service local.tests.test_phone_ui -v
  python -X utf8 -m compileall local server
  node --check local/ui/app.js
  node --check local/ui/m/app.js
  git diff --check
  ```

  Expected: all targeted tests pass, both syntax checks exit 0, compileall completes, and `git diff --check` has no error output.

- [ ] **Step 4: Run UTF-8 and mojibake checks**

  Strictly decode every modified UTF-8 file with `[Text.UTF8Encoding]::new($false,$true)` and scan the AGENTS.md blacklist. Expected: no invalid UTF-8 and no blacklist hit.

---

## Self-review

- The six reported failures are covered: three advanced-help behavior failures, two direct-recovery failures caused by missing snapshot/API behavior, and one existing-session CSRF recovery failure.
- No task changes the school login protocol, remote channel choices, credentials storage boundary, or captcha policy.
- The plan uses the current file names and exact exported functions (`PhonePanel.paint`, `PhonePanel.install`, `PhonePanel.saveCredentials`, `PhoneUI.ingest`, `PhoneUI.refreshRelogin`).
- Real phone/Tailscale/Cloudflare acceptance remains outside this offline repair and must be reported separately.
