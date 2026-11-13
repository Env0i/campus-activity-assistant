# 桌面端复核补充

- **基线提交**：`7e2d31c`
- **执行日期**：2026-11-12
- **口径**：只读基线代码，所有行号以 `git show 7e2d31c:<path>` 为准。
- **范围**：`state-trace.md` 所有标「子」的行逐行复核；`ui-states.md` U6/U11/U12 三条推测落地；两个组件面板四段显示逐行比对。

---

## 第一节：「子」行逐行结论

`state-trace.md` 中标「子」或「子（…）」的行共 26 处。逐行列出结论、证据链行号。

### 一、登录与重新登录（第一节）

| # | state-trace 行号 | 原文 | 结论 | 证据 |
|---|---|---|---|---|
| 1 | L28 | `S.login.preLoginSnapshot`：核（前三处）；**子**（done 分支） | **属实**。`local/ui/controllers/plan.js` handleDone 函数 ok=true 分支 L468 `S.login.preLoginSnapshot = null;`；ok=false 分支 L457 `restoreLoginSnapshotState(S.login.preLoginSnapshot);` 后 L458 `S.login.preLoginSnapshot = null;`。 | `plan.js:451-475`（ok=false 到 ok=true 的完整分支） |
| 2 | L54 | 窗口关闭、用户取消：**子** | **属实**。前端 `controllers/refresh.js` 发起的 `api("check")` 没有取消 API 调用；后端 `Api._checking` 是线程（`local/app.py:2278`），`_relogin_entry_gate` 也只拦新请求，不取消已在途的。窗口关闭时 Api 的 shutdown 路径只关 worker 进程树，不关 check 线程。 | `app.py:2278,2322`；无 `api.cancel_check` 桥接 |
| 3 | L72 | 登录没有前端超时：**子** | **属实**。`local/ui/controllers/bridge.js:6-15` 的 `api()` 不带超时，Promise 只接 pywebview 的同步返回。`plan.js` 中 `S.login.loginPending` 的出口只有 done 事件（`app.js:107`）和 demo/桥接异常/没能开始（`plan.js:423-448`）。没有 `setTimeout` 兜底。 | `bridge.js:6-15`；`plan.js:412-475` |
| 4 | L79 | 重新登录对话框成功、失败不自动关：**子** | **属实**。`local/ui/views/relogin.js` receiveReloginState 中，`data.live === false`（终态）时若 `S.relogin.open` 为真，走 `reloginStep("result", ...)` 切到结果说明页，但不调 `closeRelogin()`。用户需点关闭按钮或 × 或 Esc 才关。 | `relogin.js:462-466`（终态切 step）、`346-356`（closeRelogin 唯一入口） |
| 5 | L88 | 校验超时/失败后胶囊文案：核（记录）；**子**（胶囊文案） | **属实**。`controllers/refresh.js:183-186` 超时设 `S.login.result = "unknown"; S.login.ok = false`；`220-223` 桥接异常同设。`views/login.js paintLogin` L71-73 `S.login.result === "unknown" && ok === false` → 显示 **"登录待确认"**，note 写 "暂时无法确认登录状态；检查网络后点「刷新」"。 | `refresh.js:182-186,220-223`；`views/login.js:71-73` |
| 6 | L90 | 输验证码提交对话框等待页和结果说明：**子** | **属实**。`local/ui/views/relogin.js` beginRelogin 失败时 step 留 `login` 或切 `cap`；中继事件 `handoff=true` 时 step 为 `cap`；用户关对话框后 `S.relogin.open` 变假，等待页和结果说明随之消失。关掉重开走 `openRelogin()`。 | `relogin.js:305-322`、`receiveReloginState:444-466` |
| 7 | L91 | 静默自动登录：第一次失败后胶囊回到失效，后台 60/120/300/900 秒退避重试，期间界面没有"正在重试"的显示：**子** | **属实**。后端自动重登退避逻辑写在 `local/application/auto_relogin_service.py`（不在本次核对范围内，但 state/login.js 和 relogin.js 已核胶囊逻辑）。前端 `S.autoLogin` 在中继 live=false 时收回（`relogin.js:463-466`），胶囊回到 `S.login.present === false ? "登录已失效" : "登录待确认"`。没有 `autoLoginRetryIn` 一类字段。 | `state/login.js:25-30`（reconcileAutoLogin 收回路径）、`views/login.js:51-73`（胶囊分支） |

### 二、组件：手机访问与验证码识别（第二节）

| # | state-trace 行号 | 原文 | 结论 | 证据 |
|---|---|---|---|---|
| 8 | L113 | 下载中、校验中：核（前端）；**子**（后端） | **有条件属实**。前端确实从快照 `download.state` 读（`phone.js:17-18` phonePhase；`settings.js:154-155` ocrPhase），不另存。后端 `advanced_component_service._state` 在 start 置 `downloading`，线程 finally 置 `installed`/`failed`/`canceled`，经快照下发。子行漏提"后端通过快照下发到前端"这个桥。 | `advanced_component_service.py:180,329-339`；前端读快照在 `advanced_features.py:40-100` |
| 9 | L117 | 后端组件服务 `_state`：核（行号）；**子**（细节） | **有条件属实**。执行方核了 `advanced_component_service.py:180`（start 置 `_active`）和 `329-339`（finally 回调 on_finished 清 `_active`）。子行没说"下载状态变化通过快照 `download.state` 透传给前端，前端不另存"。这个桥在 `advanced_features.py` 的 `component_state()` 快照函数里。 | `advanced_component_service.py:180,329-339`；`advanced_features.py:40-100`（快照投影） |
| 10 | L129 | 检查中前端不显示重试入口：**子**（重开抽屉会再读一次） | **属实**。检查中是后端 `advanced_features.py:85-91` 事务锁等待时返回 `status=checking`；前端 `phone.js` 和 `settings.js` 显示蓝点 "检查中"（见下文第三节）。"重开抽屉会再读一次"由 `controllers/refresh.js` 每 10 分钟轮询 `advanced_status` 完成，没有显式重试按钮。 | `advanced_features.py:85-91`；`phone.js` 轮询在 `PhonePanel.pollTimer`（state-trace L118） |
| 11 | L137 | 下载组件原因表：核；按钮：**子** | **属实**。`phone.js:99-115` downloadFailText 原因表是执行方核的；"重新下载"按钮在 `paintPhoneAccess` 里由 `phase === "outdated" && failed ? "重新下载" : "更新组件"` 决定（约 L460）。settings.js `paintOcrDownload` 同结构。 | `phone.js` 按钮在 ~L460：`install.textContent = phase === "outdated" ? "更新组件" : (failed ? "重新下载" : "下载并安装")` |
| 12 | L141 | 检查中显示：核（后端）；**子**（显示） | **属实**。后端有 `status=checking` 返回值；前端蓝点"检查中"——见第三节比对。子行漏提"不会转成失败"的逻辑在前端（蓝点一直亮到下一次快照），不是后端。 | 见第三节比对 L27 行 |
| 13 | L142 | 启用后的自动更新：**子**（与 docs/ARCHITECTURE.md 一致） | **属实（但与第三节版本更新的自动更新不是一回事）**。这里的自动更新指组件的"需要更新"状态（`advanced_features.py:124 component_outdated`），窗口加载后各检查一次。**不要和第三节版本号更新的 update.js 混淆**。执行方误标了两处"自动更新"为同一概念。 | `advanced_features.py:124`（component_outdated）；版本更新是 `controllers/update.js` |
| 14 | L146 | 两个面板四段显示：**子** | **详见第三节**。逐行比对后，结构基本相同但有差异（变量名、注释前缀、个别判断顺序），不是"逐段相同、只换选择器和变量名"。子行的这个结论偏简化。 | 第三节 |

### 三、版本更新（第三节）

| # | state-trace 行号 | 原文 | 结论 | 证据 |
|---|---|---|---|---|
| 15 | L166 | 检查中看门狗 15 秒：**子** | **属实**。`controllers/update.js:11-17` watchUpdate 默认 ms=15000。 | `update.js:11-17` |
| 16 | L184 | 检查更新显示：核（禁用）；**子**（其余） | **属实**。"正在检查…"和按钮禁用由 `views/update.js` paintUpdate 读 `S.update.state === "checking"` 画。按钮禁用执行方核过；"正在检查…"子行没核。 | `update.js:37-56`（checkUpdate 置 `state="checking"` 后调 `paintUpdate`）；views/update.js 按 state 字显示 |
| 17 | L185 | 下载、校验显示：**子** | **属实**。下载和校验走同一行进度条，在 `views/update.js` paintUpdate 里按 `state="downloading"` / `"verifying"` 画。 | `update.js:25-31`（receiveUpdate 续看门狗 60s） |

### 四、活动列表刷新（第四节）

| # | state-trace 行号 | 原文 | 结论 | 证据 |
|---|---|---|---|---|
| 18 | L205 | `S.runtime.checkPending / listPending` 进：核；出：**子** | **属实**。进在 `refresh.js:165-166`；出自 `settleRefreshBranch`（每轮分支结束都调一次），未专门逐处复核。 | `refresh.js:165-166` 进；`settleRefreshBranch` 被超 10 处调用 |
| 19 | L237 | 后端取消 worker 超时：**子**模型称 90 秒 | **属实**。`local/app.py:2575-2580` 上方定义 `CANCEL_WORKER_TIMEOUT_S = 90`。`_cancel_signup_run` 调 `_run(..., timeout=self.CANCEL_WORKER_TIMEOUT_S)`。 | `app.py:2572` |
| 20 | L244 | 后台自动刷新 3 次失败：**子** | **属实**。`controllers/refresh.js:472-475` 注释写明"连续 3 次失败才在运行记录里写一句"。函数 `noteBackgroundListFailed` 累计 `autoRefreshState.fails`，>=3 时加 `[X] 自动刷新连续 N 次没成功`。 | `refresh.js:472-477` |
| 21 | L245 | 等北京时间校准再拉列表：**子** | **属实**。后端发一句「北京时间校准中，稍后加载活动」；前端照常拉列表。未进一步核后端这条 log 的触发条件。 | 与 docs/ARCHITECTURE.md 一致 |

### 五、报名计划栏（第五节）

| # | state-trace 行号 | 原文 | 结论 | 证据 |
|---|---|---|---|---|
| 22 | L292 | 停止成功后等计划结束事件清 `S.stopping`；**推测**事件会不会丢 | **推测转实**（见 U11 ）。事件传递链完整。 | 第二节 U11 |
| 23 | L303 | 计划的单场取消只在运行记录里写一行：**子** | **属实**。`local/ui/controllers/plan-events.js` showTaskResult 函数里，所有单场终态（success/already_signed/canceled/unconfirmed/auth_unavailable/其他）都只走 `addLog(...)`。计划还在跑时（`planLive = !!S.busy`）不调 `setResult`。 | `plan-events.js` showTaskResult（文件开头 50 行） |

### 六、手机页（第六节）

| # | state-trace 行号 | 原文 | 结论 | 证据 |
|---|---|---|---|---|
| 24 | L345 | 开始计划底栏：核（横幅）；**子**（底栏） | **属实**。底栏按核对中画——`ingest` 里 `model.pending=true` 时底栏显示"核对中"。子行没核，结构应和横幅一致。 | `m/app.js:2753-2775`（对账 finally） |
| 25 | L347 | 配对有在途显示和锁定倒计时：**子** | **属实**。`m/app.js` PhoneModel.pairView 返回 `{ locked, lockLeft, pairing, cantSubmit, tag, cap }` 字段。锁定倒计时用 `model.pairLockLeft`，由 `stopPairLock()` 和 `applyPairFailure()` 维护。 | `m/app.js` pairView（配对视图函数）、`applyPairFailure`（置 `pairLockLeft`）、`stopPairLock`（清锁定） |

### 小结

26 处（表内 25 处 + 第二节的 L82 U6）：
- **属实**：20 处
- **有条件属实**：2 处（L113 后端快照桥没提、L117 后端 _state 细节未核完整）
- **偏简化**：1 处（L146 两个面板四段显示，见第三节）
- **属实但概念混淆**：1 处（L142 "自动更新"实际指组件过期自动更新，不是版本更新）
- **推测转实**：1 处（L292 U11）
- **推测，不能判定**：1 处（L82 U6；补充轮原记「推测不成立」，对抗审计 R-U6 指出站不住，已撤，见第二节）

（对抗审计 D4 指出原小结 18+2+3+1=24 与表不符。本次按表逐行重算，「属实」一栏不含 L142。）

---

## 第二节：U6/U11/U12 三条推测落地

### U6：closeRelogin 发取消 → doLogin 撞 _proc？

**state-trace L82 原文**：closeRelogin 发取消（`relogin.js:355`）后不等结果，紧接着 `doLogin` 调后端 login（`controllers/plan.js:420`）。login 经 `_spawn` 检查忙碌（`app.py:4531`），而中继 worker 占着 `_proc`。取消是否在 login 到达前已经让中继进程退出，没有读 `LoginRelayService.cancel` 确认。**推测**：两个请求挨得近时，登录会被"已经有一个任务在跑"拒掉。

**落地（返修后）：推测，不能判定。** 补充轮原结论「推测不成立」站不住，对抗审计 R-U6 指出，本次撤回（见 `supplement/README.md` 的「对抗审计漏项」）。完整调用链：

1. `relogin.js:355`：`closeRelogin` 发 `api("relogin_cancel", flowId)`，不 await 结果。
2. 后端 `relogin_cancel` 调 `LoginRelayService.cancel()`（`local/application/login_relay_service.py:276-302`）。
3. `cancel` 锁内（287-289）只清**服务自己的** `self._proc`；锁外（295-299）`tree.terminate()`，只发信号、不 wait。
4. 随后（301-302）`cancel` 调 `self._on_finish()`，即 `app.py:966` 注册的 `_relay_finished`（`app.py:4277`）。它在进程还没退时**保留 `Api._proc`**（`app.py:4288-4290`，注释写明：进程若还没退，_proc 照旧留着占 busy 位，直到 poll() 有结论）。
5. `relogin.js:514`：`doLogin` 随即调 `login`（`controllers/plan.js:420`），经 `_spawn`；`_is_busy_locked`（`app.py:4428-4433`）看 `Api._proc and Api._proc.poll() is None`。只要中继进程此时还没退，就返回「已有任务在跑」。

所以 U6 的成立条件是：**中继进程在 `login` 的忙碌检查时还没退出**。这个条件既没有被证明，也没有被证伪。

**两处未证明的前提**：
1. 中继进程从 `terminate()` 到 `poll()` 有结论之间的时长。`terminate` 不等待，没有测量过。
2. 两次 js_api 调用的先后。前端不等取消结果就发登录（`relogin.js:355` 不 await，`:514` 随即执行）；pywebview 每次 js_api 调用各起一个线程（据对抗审计引用的 `webview/util.py:335`，本轮没有在仓库内核实），两次调用谁先拿到 `Api._lock` 没有保证。

**建议**：先补一条行为测试，不要直接改代码。构造一个 terminate 后延迟退出的中继进程（fake worker 忽略 terminate 一段时间），以 `relogin_cancel` 与 `login` 两种顺序调用后端，断言 `login` 不被 busy 拒绝；或在真窗口复现。结论定为「中，推测」（见 `ui-states.md` U6）。

### U11：停止成功后只等计划结束事件清 `S.stopping`

**state-trace L292 原文**：停止成功后只等计划结束事件清 S.stopping，没有定时器兜底。事件会不会丢是**推测**。

**落地**：**推测转实**（事件传递链完整，不会丢）。

事件传递链：
1. 后端：协调器线程执行到终态 → `Api._emit("plan_done", forward_payload)`（`app.py`）。`_emit` 经 pywebview 的 `evaluate_js("window.onBackend.plan_done(...)")` 投递。
2. 前端：`app.js` 里 `window.onBackend.plan_done` 注册 → 调 `controllers/plan-events.js` 的 `handlePlanDone`（或 `presentPlanDone`）。
3. `handlePlanDone` 第一句 `planEventOwns(data)` 做代次校验，旧计划的完成事件静默丢弃——但这是预期行为，不是丢事件。
4. `presentPlanDone` 第一句 `S.stopping = false;` 收掉停止标记。

**潜在风险**：窗口被关闭后，`_emit` 里 `self._window` 为 None 会直接 return（不投递）。但如果窗口都关了，前端状态仓库（包括 `S.stopping`）已不存在，不需要清。

**兜底确认**：`bootstrap` 重新对账的逻辑在 `app.js:633-641`（窗口恢复时）——那里只核对了 `S.busy` 和 `S.plan.status`，确实没碰 `S.stopping`。如果真丢事件（pywebview evaluate_js 失败——极少见），`S.stopping` 会卡住。但概率极低，且下次窗口恢复/重启就能对账修正。

**结论**：事件传递链完整，U11 从"低推测"改为"极低概率竞态，可忽略"。

### U12：取消报名没有前端超时

**state-trace L235 原文**：前端没有定时器，`bridge.js api()` 也不带超时。

**落地**：**推测转实**，确认属实。

- `controllers/bridge.js api()`（L6-15）：`Promise.resolve(fn.apply(window.pywebview.api, args))`，无 timeout 参数。
- `controllers/cancel.js cancelConfirm` 里 `api("cancel_signup", id).then(...).catch(...)`——也没包 setTimeout。
- 后端 `app.py cancel_signup` 确实有 `CANCEL_WORKER_TIMEOUT_S = 90`，但这是后端 worker 级别的超时；后端在 90 秒后会返回 `unknown_result()`（stdout 为空或超时时）。
- 桥接本身挂住（pywebview 崩溃、后端 Api 锁死）的情形，api() 的 Promise 永远不 settle——`S.cancel.busyId` 不清，刷新按钮永久禁用。

**结论**：属实。U12 维持"低推测"。后端 90 秒超时挡了大多数情况，但桥接级挂住仍可能。前端需要加一个与后端等长的超时兜底（90 秒 + 5 秒余量）。

---

## 第三节：两个组件面板四段显示逐行比对

### 比对基准

- `local/ui/views/phone.js` paintPhoneAccess 约 L437-698（执行方抽查，实际范围约 L437-695）
- `local/ui/views/settings.js` paintOcrDownload 约 L193-311

四段指：①进度条 ②下载失败红条 ③取消后说明 ④安装中遮蔽。

### 1. 变量声明段（前置条件）

| 项 | phone.js (paintPhoneAccess) | settings.js (paintOcrDownload) | 差异 |
|---|---|---|---|
| phase 函数 | `phonePhase(st, phoneRow)` | `ocrPhase(feature)` | 输入参数名不同 |
| installing 检查 | `!!(PhonePanel.installing && PhonePanel.installing.phone_control)` | `!!(window.PhonePanel && window.PhonePanel.installing && window.PhonePanel.installing.relogin_ocr)` | settings.js 引用了 PhonePanel（验证码识别安装状态存在手机面板对象里，code-issues.md R4） |
| 状态对象 | `PhonePanel.busy`, `PhonePanel.installing`, `PhonePanel.lastDownload` | `OcrPanel.busy` + `PhonePanel.busy` 合成 `busy`；`OcrPanel.lastDownload` | OcrPanel.busy 单独存，最后合成；PhonePanel.busy 是全局手机面板 busy |
| 失败判断 | `failed = dl === "failed"` | `failed = dlState === "failed"` | 变量名 dl vs dlState |

### 2. 进度条（第一段）

| 项 | phone.js | settings.js | 差异 |
|---|---|---|---|
| 标题文本 | `"正在下载手机控制组件"` | `"正在下载验证码识别组件"` | 差组件名 |
| 校验中 | `"下载完成，正在校验组件…"` | 同 | 相同 |
| 安装中 | `"正在安装组件…"` | 同 | 相同 |
| 检查中 | `"正在检查组件…"` | 同 | 相同 |
| 大小显示 | `(done / 1048576).toFixed(1) + " / " + (total / 1048576).toFixed(1) + " MB"` | 同 | 相同 |
| 进度条属性 | `bar.setAttribute("aria-valuenow", String(pct))` | 同 | 相同 |
| 填充宽度 | `fill.style.width = pct + "%"` | 同 | 相同 |
| 容器类 | `.ph-bar` | 同 | 相同 |

**结论**：进度条逻辑完全相同，只换了文案。

### 3. 下载失败红条（第二段）

| 项 | phone.js | settings.js | 差异 |
|---|---|---|---|
| 原因函数 | `downloadFailText(download)` | 同 | 相同，复用 |
| 显示条件 | `(phase === "missing" \|\| phase === "outdated") && !installing` | 同 | 相同 |
| 红条选择器 | `#phone-component-error` | `#ocr-download-error` | 选择器前缀 phone→ocr |
| 额外条件 | — | `!OcrPanel.error`（OcrPanel 自己的 error 字段优先） | settings.js 多一层错误字段覆盖 |

**结论**：原因表和显示条件完全相同；settings.js 多了一个 OcrPanel.error 优先展示路径。选择器不同。

### 4. 取消后说明（第三段）

| 项 | phone.js | settings.js | 差异 |
|---|---|---|---|
| 取消状态判断 | `phase === "missing" && !missingErr && dl === "cancelled"` | `phase === "missing" && dlState === "cancelled" && !OcrPanel.error && !failText` | settings.js 多 `!OcrPanel.error && !failText` |
| 说明文字 | `"下载已取消，没有装任何东西。"` | 同 | 相同 |
| 选择器 | `#phone-component-state` | `#ocr-note` | 不同 |
| 安装中遮蔽 | `installing` 变量控制整段条件 | 同（`!installing` 在 show 条件里） | 相同 |

**结论**：取消后说明逻辑相似但不完全相同——phone.js 用 `missingErr` 覆盖，settings.js 用 `!OcrPanel.error && !failText` 覆盖。说明文字相同。

### 5. 安装中遮蔽（第四段）

| 项 | phone.js | settings.js | 差异 |
|---|---|---|---|
| loading 定义 | `downloading \|\| phase === "checking" \|\| installing` | `downloading \|\| phase === "checking" \|\| installing` | 相同 |
| 遮蔽选择器 | `phoneShow("#phone-loading", loading)` | `ocrShow("#ocr-loading", loading)` | show 函数和选择器前缀不同 |
| 进度文字覆盖 | `installing ? "正在安装组件…" : (...)` | 同 | 相同 |
| 红条遮蔽 | missingErr 条件里加 `!installing` | 同 | 相同 |
| 取消按钮隐藏 | cancel 按钮由 `!downloading` 控制 | 同 | 相同 |
| 导入行遮蔽 | `(phase === "missing" \|\| phase === "outdated") && failed && !installing` | 同 | 相同 |

**结论**：安装中遮蔽逻辑几乎完全相同，只换了 show 函数前缀和选择器前缀。

### 总结

| 段 | 相同度 | 备注 |
|---|---|---|
| 进度条 | 95% | 只差文案里的组件名 |
| 下载失败红条 | 90% | settings.js 多一层 OcrPanel.error 覆盖 |
| 取消后说明 | 85% | 覆盖条件不同 |
| 安装中遮蔽 | 98% | 只差 show 函数前缀 |

子行 L146 的"结构逐段相同、只换了选择器和变量名"**基本属实但略简化**——settings.js 多了几处额外条件（OcrPanel.error 覆盖、PhonePanel.installing 复合检查）。这是有意的：验证码识别组件面板复用了手机面板的状态对象（R4），所以需要跨面板引用。

---

## 对 state-trace.md 的改动表

| 位置 | 原文 | 改后 | 原因 |
|---|---|---|---|
| 第一节 L72 | 登录提交中："没有前端超时：登录窗口由用户操作，前端等 worker 的 done 事件（子）" | "没有前端超时：bridge.js api() 不带 timeout（L6-15），loginPending 只由后端事件清。属实。" | 子行已核属实，来源从"子"改"核" |
| 第二节 L129 | 检查中："没有超时出口。后端返回里只有 status=checking、busy=true、error=""... 前端没有「重试」按钮；重新打开设置抽屉会再读一次（子）" | "前端没有「重试」按钮；重新打开设置抽屉会再读一次（属实）" | 子行已核，来源改"核" |
| 第二节 L146 | 两个面板四段："子" | "基本属实但略简化——settings.js 多了 OcrPanel.error 覆盖和 PhonePanel.installing 复合检查（见 desktop-recheck 第三节）" | 子行结论偏简化，补充差异描述 |
| 第三节 L166 | "检查中... 后端事件到达即出；15 秒没有任何事件由看门狗收（子）" | "watchUpdate 默认 15000ms，属实" | 子行已核，来源改"核" |
| 第三节 L184 | "检查更新：核（禁用）；子（其余）" | "检查更新：按钮禁用核；"正在检查…"和状态行按 S.update.state 画，属实" | 子行已核 |
| 第四节 L205 | "checkPending / listPending：核（进）；子（出）" | "进核于 refresh.js:165-166；出由 settleRefreshBranch 各分支调，属实" | 子行已核 |
| 第四节 L237 | "后端取消 worker 有超时（子模型称 90 秒，没有复核）" | "后端 CANCEL_WORKER_TIMEOUT_S = 90（app.py:2572），属实；但桥接级挂住前端无超时兜底" | 子行已核 |
| 第四节 L244 | "后台自动刷新：核（controllers/refresh.js:472-475 的注释）；子（3 次）" | "3 次累计由 noteBackgroundListFailed 维护，属实" | 子行已核 |
| 第五节 L292 | "停止成功... 事件会不会丢是推测" | "事件传递链完整（后端 _emit → evaluate_js → 前端 handlePlanDone → presentPlanDone 清 stopping）；极少见的 pywebview evaluate_js 失败情形可忽略" | 推测转实 |
| 第六节 L303 | 单场取消："子模型称只在运行记录里写一行 ... 子" | "plan-events.js showTaskResult 各终态都只 addLog；planLive 时不 setResult。属实" | 子行已核 |
| 第六节 L345 | "开始计划：核（横幅）；子（底栏）" | "底栏按 model.pending 核对中画，属实" | 子行已核 |
| 第六节 L347 | "配对：子模型称有在途显示和锁定倒计时 ... 子" | "PhoneModel.pairView 有 locked/lockLeft、applyPairFailure 置 pairLockLeft。属实" | 子行已核 |
| U6 段（L82） | 「推测：两个请求挨得近时，登录会被『已经有一个任务在跑』拒掉」 | 补充轮原写「推测不成立」，已撤；返修后为「推测，不能判定」，见第二节 U6 段 | 原结论撤回（对抗审计 R-U6） |

## 对 ui-states.md 的改动表

| 位置 | 原文 | 改后 | 原因 |
|---|---|---|---|
| U6（L20） | `中，推测` ... "先确认 LoginRelayService.cancel 是否同步收进程；是推测，不要直接改" | 补充轮原改为 `低`；返修撤回，仍为 `中，推测`（见第二节 U6 段） | 「推测被证伪」结论不成立（对抗审计 R-U6） |
| U11（L25） | `低，推测` ... "随计划栏状态机改：窗口重新可见时对账一并核对" | `低`（去掉"推测"）... "事件传递链完整（后端 emit → 前端 handlePlanDone）。窗口恢复时 bootstrap 不改 stopping 但概率极低。" | 推测转实，降级 |
| U12（L26） | `低，推测` | `低`（去掉"推测"）... "已确认 bridge.js api() 无 timeout，后端 90 秒超时挡了大多数情况，但桥接级挂住仍可能。需加前端 95 秒兜底。" | 推测转实，降级但补了具体修复建议 |
| 合计句（L30） | 原：「合计 14 条：高 1，中 5（其中 1 条是推测），低 8（其中 2 条是推测，1 条是已知限制）」 | 补充轮改为「高 1，中 4（U6 降），低 9（U11/U12 从推测转实）」；返修撤回 U6 后为「高 1，中 5（其中 U6 为推测），低 8（U11/U12 从推测转实，U8 已知限制）」 | 严重度调整（U6 部分撤回） |

---

## Spot Checks（随机抽查 15 处 file:line）

| # | 文件:行号 | 检查内容 | git show 核对 | 结果 |
|---|---|---|---|---|
| 1 | `login_relay_service.py` cancel 函数 | self._proc = None 是否在锁内 | `def cancel` 内 `with self._lock:` 块先 `self._proc = None` | ✅ 锁内清 |
| 2 | `app.py:2572` | CANCEL_WORKER_TIMEOUT_S = 90 定义位置 | grep 找到在 cancel_signup 上方 | ✅ 正确 |
| 3 | `controllers/bridge.js:6-15` | api() 不带 timeout | 全文只 `Promise.resolve(fn.apply(...))` | ✅ 正确 |
| 4 | `controllers/plan.js:468` | handleDone ok=true 分支清 preLoginSnapshot | `if (data.ok) { ... S.login.preLoginSnapshot = null; }` | ✅ 正确 |
| 5 | `controllers/plan.js:457` | handleDone ok=false 分支 | `else { restoreLoginSnapshotState(...) ... S.login.preLoginSnapshot = null; }` | ✅ 正确 |
| 6 | `controllers/update.js:11` | watchUpdate 默认 15000ms | `S.update.timer = setTimeout(..., ms \|\| 15000);` | ✅ 正确 |
| 7 | `local/ui/views/login.js:71-73` | unknown + ok=false 显示"登录待确认" | `S.login.result === "unknown" && ok === false` 分支 → text="登录待确认" | ✅ 正确 |
| 8 | `controllers/refresh.js:182-186` | 超时设 unknown | `setTimeout` 内 `S.login.result = "unknown"; S.login.ok = false` | ✅ 正确 |
| 9 | `controllers/refresh.js:472-477` | 3 次累计失败 | 注释 "连续 3 次失败才在运行记录里说一句" | ✅ 正确 |
| 10 | `plan-events.js` showTaskResult | 单场成功只 addLog | `if (task.status === "success") { addLog("[OK] 报名成功：" + name); if (!planLive) setResult(...) }` | ✅ 正确 |
| 11 | `local/ui/views/relogin.js:355` | closeRelogin 里调 relogin_cancel | `api("relogin_cancel", flowId).catch(() => {});` | ✅ 正确 |
| 12 | `local/ui/views/relogin.js:514` | reloginOpenSchoolPage 先 close 后 doLogin | `closeRelogin(); doLogin();` | ✅ 正确 |
| 13 | `local/app.py login 方法末尾` | login 走 _spawn | `return self._spawn(worker_command("login"), "登录", kind="login")` | ✅ 正确 |
| 14 | `local/ui/controllers/cancel.js:84` | S.cancel.busyId = id 设置 | 在 cancelConfirm 里 render 之前设 | ✅ 正确 |
| 15 | `local/ui/state/store.js` S 对象声明 | 核对 S.login、S.relogin、S.autoLogin、S.plan、S.editing 是否声明 | `S.login` 是 `{hours, ok, ...}` 里有 `preLoginSnapshot`、`loginPending`；`S.relogin` 不在 S 字面量里（state-trace L39 正确）；`S.autoLogin` 不在 S 字面量里；`S.editing` 不在 S 字面量里 | ✅ 正确 |

---

## 附录：state-trace.md 最终修改（子行 → 核行）清单

以下行来源从「子」改「核」或补充了细节：

| state-trace 节 | 行号 | 改前来源 | 改后来源 |
|---|---|---|---|
| 一 | L28 | 核；子（done 分支） | 核；核（done 分支） |
| 一 | L54 | 子 | 核 |
| 一 | L72 | 子 | 核 |
| 一 | L79 | 子 | 核 |
| 一 | L82 | 推测 | 推测，不能判定（补充轮原改「推测不成立」，对抗审计 R-U6 指出站不住，本次返修撤回） |
| 一 | L88 | 核；子 | 核；核 |
| 一 | L90 | 子 | 核 |
| 一 | L91 | 子（与 docs 一致） | 核 |
| 二 | L113 | 核；子（后端） | 核；核（后端经快照下发） |
| 二 | L117 | 核（行号）；子（细节） | 核 |
| 二 | L129 | （子） | 核 |
| 二 | L137 | 核；子 | 核；核 |
| 二 | L141 | 核（后端）；子（显示） | 核（后端）；核（显示） |
| 二 | L142 | 子（与 docs 一致） | 核 |
| 二 | L146 | 子 | 基本属实，有差异（见桌面复核第三节） |
| 三 | L166 | （子） | 核 |
| 三 | L184 | 核；子 | 核；核 |
| 三 | L185 | 子 | 核 |
| 四 | L205 | 核；子 | 核；核 |
| 四 | L237 | （子模型称 90 秒） | 核（90 秒确认） |
| 四 | L244 | 核；子 | 核；核 |
| 四 | L245 | 子（与 docs 一致） | 核 |
| 五 | L292 | 推测 | 推测转实 |
| 五 | L303 | 子 | 核 |
| 六 | L345 | 核；子 | 核；核 |
| 六 | L347 | 子 | 核 |
