# 重构前置清单（supplement）

- **基线提交**：`7e2d31c`。所有行号以它为准。
- **执行日期**：2026-11-12（北京时间）。
- **用途**：`ui-states.md`、`code-issues.md`、`inventory.md` 的补充——把执行重构前必须查清的四项列出来，动手时逐节勾掉。

---

## 第一节：每块动手前要先补的测试

步骤来自 `ui-states.md` 末尾（修 U1/U2/U3/U4/U7/U9、步骤 1A/1B/1C、步骤 2/3）。对照 `git show 7e2d31c:local/tests/` 下七个文件的 `def test_` 方法名，标出已有覆盖和缺口。

| 步骤 | 要补的行为测试 | 已有（测试类/方法名）| 缺 |
|---|---|---|---|
| **修 U1 / 步骤 1C**<br>修改中退出路径 | 停止被后端拒绝：不再显示修改中、运行记录不说"已暂停" | `test_ui_reliability.RunningPlanSnapshotTests.test_stale_plan_events_cannot_hijack_running_plan`<br>`test_ui_reliability.TerminalPlanRestoreTests.test_stopped_plan_keeps_its_own_copy` | 缺"修改中 + 停止被拒绝"组合 |
| | 修改中、计划自然结束后点"重新选择未成功的场次"：回到的不是修改中 | 缺 | 全缺 |
| | "放弃修改"：提交的是原计划的场次，不是当前勾选 | 缺 | 全缺 |
| **修 U2/U3**<br>四处静默刷新 | 窗口重新可见的刷新：不出骨架、失败时列表和勾选不变 | `test_ui_reliability.AutoListRefreshTests.test_background_round_has_no_skeleton_checking_capsule_or_result_box` （覆盖后台刷新不出骨架，但不是"窗口恢复"那一路） | 缺窗口恢复、取消报名成功后、计划结束后、登录成功后这四路各自的行为断言 |
| | 取消报名成功后触发的刷新 | `test_signup_plan.ApiBusyLockTests.test_cancel_waiting_task_does_not_cancel_other_task` （锁层面，不是前端刷新行为） | 缺前端行为 |
| | 计划结束后触发的刷新 | `test_ui_reliability.TerminalPlanRestoreTests.test_running_snapshot_restores_busy_and_progress` （快照恢复，不是结束后自动刷新） | 缺 |
| | 重新登录成功后触发的刷新 | `test_ui_reliability.AutoReloginTests.test_pill_leaves_auto_login_when_a_valid_check_arrives` （check 成功后胶囊收口，不是列表刷新） | 缺列表刷新行为 |
| **修 U4**<br>手机弹层刷新 | 弹层开着时轮询带来新计划状态：弹层内容跟着变 | `test_phone_ui.RunWaitModelTests.test_busy_plan_renders_board_cards_and_collapsed_list` （renderReview 重排，但不是"弹层开着 + 轮询回来"） | 全缺 |
| **修 U7**<br>手机最近同步 | "最近同步"在手机时区和北京时间不同时显示北京时间 | 缺 | 全缺 |
| **修 U9**<br>停止未成功文案 | 停止没成功时，运行记录里不写"计划已暂停" | `test_runtime_bundle.ShutdownAcceptTests.test_stop_kills_tree_cancels_task_and_emits_single_plan_done` （停止成功路径） | 缺停止被拒绝时的文案断言 |
| **步骤 1A 组件** | 检查中超过时限：出现原因和重试入口 | 缺 | 全缺（`test_update_check` 有 check 超时但不是组件检查中） |
| | 读状态失败：有提示 | 缺 | 全缺 |
| | 两个组件同时一个下载、一个安装：各显示各的 | 缺 | 全缺（`test_component_packages` 测的是包层面，不是两个组件并行 UI） |
| **步骤 1B 登录** | 校验结论晚于中继终态到达：胶囊不回亮 | `test_ui_reliability.ReloginHandoffTests.test_handoff_restores_the_reminder_and_asks_for_the_captcha` （handoff 场景，不是"终态先到、结论后到"） | 缺事件顺序竞态 |
| | 验证码页改用浏览器：浏览器登录能开始 | 缺 | 全缺（code-issues L6 标注"没测"） |
| **步骤 2 更新** | 安装程序启动成功后的"已启动"状态（新增状态值） | `test_update_check.UpdateLaunchTests.test_launch_publishes_launching_then_success` （只有 launching → success，没有已启动中间态） | 全缺 |
| **步骤 3 grab.py** | cmd_grab 28 个闭包变量收成显式对象后的逐字对照测试 | `test_runtime_bundle` 有运行记录比对、`test_signup_plan` 有 stdout 解析 | 缺"同样输入得到同样 stdout 行和退出码"的端到端对照 |

**缺口统计**：表内共 17 行要补（原文 22 不成立，对抗审计 C6，已改为 17）。拆分未改：审计给出的「5 条部分覆盖、12 条全缺」与表内「已有」列不符（「已有」列写了测试名的 10 行，写「缺」的 7 行）。这一条只改了总数，拆分停在此处，待指挥会话裁定。

---

## 第二节：Api 五块摘表

按 `code-issues.md` 步骤 2 顺序（更新 → 组件 → 手机访问 → 登录恢复 → 计划），每块列出从 `git show 7e2d31c:local/app.py` 的 def 行号和 `__init__` 属性段（814-980 行）归类出来的事实。

### 块 1：更新（步骤 2 第一刀）

**公开方法（非下划线开头 + app.py def 行号）**

| 方法 | 行号 |
|---|---|
| `check_update(request_id)` | 2057 |
| `update_download(request_id)` | 2117 |
| `update_cancel()` | 2171 |
| `update_launch(request_id)` | 2177 |

（`front_ready`、`bootstrap`、`help` 不属于更新，已挪到第三节「其他：全局入口」，对抗审计 C7。）

**实例属性**

`__init__` 879-889 段：`_updating`、`_update_request_id`、`_update_result`、`_update_installer`、`_update_installer_path`、`_update_staging_path`、`_update_cancelled`。另：`_window`（全局）、`_emit`（全局事件通道，1097 行）。

**涉及的锁**

- `_lock`（67 个方法读，98 处 with）：`check_update` 2088 行、`update_download` 2131 行、`update_cancel` 2174 行、`update_launch` 2240 行都在 with 里。
- 无独立锁。

**L4 外部写入**（update_service.py 从外面给 state=Api 实例赋值）

9 处：`run_check` 写 `_update_result`/`_update_installer`/`_update_installer_path`/`_update_staging_path`/`_update_cancelled`/`_updating`；`run_download` 写 `_update_installer_path`；`fallback_to_installer` 写 `_update_installer_path`；`run_version_download` 写 `_update_staging_path`。

**测试打补丁的 app 模块级名字（X1）**

- `check_latest_release`（6 次，test_update_check.py）
- `version_switch_available`（6 次）
- `worker_command`（24 次，和更新 check 共用 worker_command 的 spawn 路径）

**测试改写的 Api 成员（inventory.md 第三节 C）**

| 名字 | 次数 | 文件数 |
|---|---|---|
| `_update_result` | 11 | 3 |
| `_update_installer` | 9 | 2 |
| `_update_staging_path` | 7 | 3 |
| `_update_request_id` | 3 | 1 |
| `_update_installer_path` | 3 | 1 |
| `_updating` | 4 | 1 |
| `_update_cancelled` | 未列（但 test_update_check.py:705 有 `test_update_cancel_sets_flag_only`）|
| `_closing` | 4 | 3 |
| `_emit` | 36 | 11（全局，更新也走它推 update 事件）|

**手机服务反射调用（X3 / ACTION_PARAMS）**

无。更新相关方法不在 phone_rules.py 的 ACTION_PARAMS 白名单里。

---

### 块 2：组件（步骤 2 第二刀）

**公开方法**

| 方法 | 行号 |
|---|---|
| `download_advanced_feature(key="")` | 1425 |
| `cancel_advanced_feature_download(key="")` | 1452 |
| `enable_advanced_feature(key="")` | 1459 |
| `advanced_component_location(key="")` | 1488 |
| `open_advanced_component_dir(key="")` | 1506 |
| `advanced_features_state()` | 1525 |
| `inspect_advanced_component(key="", path="")` | 1606 |
| `pick_advanced_component(key="")` | 1624 |
| `install_advanced_feature(key="", path="")` | 1644 |
| `remove_advanced_feature(key="")` | 1733 |

**实例属性**

`__init__` 842-845、918-929 段：`_lock`、`_credential_lock`、`_phone_access_lock`、`_advanced_busy`；918 起两个组件服务实例：`_component_service`（phone_control）、`_ocr_component_service`（relogin_ocr）。

**涉及的锁**

- `_lock`：组件下载/安装/移除全在 with _lock 里。
- `_phone_access_lock`：手机访问启动/停止也在这把锁里（共享，所以组件拆完才能拆手机访问）。
- `_credential_lock`：组件不直接用，但 credential_store 被 import 进 app 模块。

**测试打补丁的模块级名字**

- `_advanced_features`（5 次，feature_ready 等）
- `_component_packages`（间接，app.py 里 import 了它）
- `updater.download_installer`（5 次，X4 类"经 app 去补别的模块"）

**测试改写的 Api 成员**

| 名字 | 次数 |
|---|---|
| `_advanced_busy` | 3 |
| `_cloudflare` | 5（共享，手机访问也用）|
| `_phone` | 8（共享）|
| `_component_service` | 1 |
| `_ocr_component_service` | 2 |
| `_ensure_tray` | 10（和组件无关，但 shutdown 里也调它）|

**手机服务反射调用**

无。组件方法不在 ACTION_PARAMS 白名单里（手机访问的 start/stop 才在）。

---

### 块 3：手机访问（步骤 2 第三刀，紧跟组件后因为共用 `_phone_access_lock`）

**公开方法**

| 方法 | 行号 |
|---|---|
| `phone_access_state()` | 3767 |
| `start_phone_access(channel="tailscale")` | 3812 |
| `set_phone_access_preferences(preferred_channel="")` | 3897 |
| `restore_phone_access()` | 3913 |
| `stop_phone_access()` | 4017 |
| `_stop_phone_access()`（私有，`stop_phone_access` 调它，不是重名） | 4024 |

**实例属性**

`__init__` 845、901-917、949-961 段：`_phone_access_lock`、`_phone`（PhoneAccessService 实例）、`_phone_channel`、`_cloudflare`（CloudflareTunnel）、`_cloudflare_exit_notice`、`_cloudflare_starting`。

**涉及的锁**

- `_phone_access_lock`（9 个方法读）：手机访问启停全在这把锁里。
- `_lock`：`_reconcile_cloudflare_lifecycle` 3762 行在 with _lock 里。
- `_credential_lock`：不直接用，但 PhoneAccessService 构造时传了 credential_store。

**测试改写的 Api 成员**

| 名字 | 次数 |
|---|---|
| `_phone_channel` | 1 |
| `_cloudflare` | 5 |
| `_phone` | 8 |
| `stop_phone_access` | 1 |

**手机服务反射调用（X3）**

这是唯一被手机服务反射调用的 Api 块。phone_rules.py ACTION_PARAMS 白名单共 12 个 key（11 个对应 Api 方法，`save_retry_policy` 由 phone_service 特判，见 4.3）：

| ACTION_PARAMS key | 对应 Api 方法 | app.py 行号 |
|---|---|---|
| `list_activities` | `list_activities(request_id)` | 2283 |
| `check` | `check(request_id)` | 2252 |
| `start_plan` | `start_plan(items, headed, ...)` | 2923 |
| `start_request_state` | `start_request_state(request_id)` | 2854 |
| `cancel_start_request` | `cancel_start_request(request_id)` | 2891 |
| `stop_plan` | `stop_plan(plan_id)` | 3242 |
| `cancel_task` | `cancel_task(plan_id, task_id)` | 3234 |
| `save_retry_policy` | 无同名 Api 方法；`phone_service.py:428-431` 在 getattr 之前特判为 `save_prefs`，只放行 `retry_policy` 键 | — |
| `show_window` | `show_window()` | 3427 |
| `phone_relogin_begin` | `phone_relogin_begin(username, password, ...)` | 4211 |
| `phone_relogin_submit` | `phone_relogin_submit(flow_id, challenge_id, code)` | 4244 |
| `phone_relogin_cancel` | `phone_relogin_cancel(flow_id)` | 4248 |

> ⚠️ ACTION_PARAMS 完整清单从 `git show 7e2d31c:local/domain/phone_rules.py` 读到 12 个 key（含 `save_retry_policy`，它不对应 Api 方法，见 4.3）。phone_service.py:438 的 `getattr(self._api, name, None)` 对其中 11 个 key 都要能命中 Api 实例上同名方法（`save_retry_policy` 在它之前已被特判，不经 getattr）。拆 Api 时这 11 个方法必须仍然挂在传给 PhoneAccessService 的那个对象上，否则手机端会收到 `not_available`。

---

### 块 4：登录恢复（步骤 2 第四刀）

**公开方法**

| 方法 | 行号 |
|---|---|
| `save_relogin_credentials(username="", password="")` | 1770 |
| `clear_relogin_credentials()` | 1795 |
| `prepare_phone_relogin(username="", password="", ...)` | 4043 |
| `relogin_begin(username="", password="", save=False)` | 4153 |
| `relogin_submit(flow_id, challenge_id, code)` | 4182 |
| `relogin_cancel(flow_id)` | 4186 |
| `relogin_auto_once()` | 4194 |
| `login()` | 2762 |
| `check(request_id="")` | 2252 |
| `phone_relogin_*` 系列（见上节）| 4211-4248 |

**实例属性**

`__init__` 857-875、935-976 段：`_checking`、`_check_again`、`_last_check`、`_login_wait_pending`、`_auto_relogin_started_at`、`_relay_creds_source`、`_once_creds_rejected`、`_pending_save`、`_last_login_origin`、`_login_seen_valid`、`_expiry_pushed`、`_login_expired_logged`、`_relay`（LoginRelayService）、`_auto_relogin`（AutoReloginMonitor）、`_proc`/`_proc_tree`/`_relay_proc_tree`（共享 worker 进程）。

**涉及的锁**

- `_lock`（大量）：check/list/login/relogin 全在 with _lock 里。
- `_credential_lock`（12 个方法读）：`save_relogin_credentials`/`clear_relogin_credentials`/`prepare_phone_relogin`/`relogin_begin`/`_anchor_login_success`。
- `_phone_access_lock`：不直接用，但 relay 和 phone 共享 `_relay` 实例。

**测试打补丁的模块级名字**

- `PREFS`（30 次，`load_prefs`/`save_prefs` 链路）
- `SESSION_FILE`（15 次）
- `DATA_DIR`（5 次）
- `_credential_store`（1 次）
- `login_state`（2 次）
- `check_latest_release`（6 次，和 update 共用）
- `PlanCoordinator`（30 次，和计划共用）

**测试改写的 Api 成员**

| 名字 | 次数 |
|---|---|
| `_last_check` | 21 |
| `_relay` | 11 |
| `_relay_proc_tree` | 4（间接，在 `_proc_tree` 表里）|
| `_checking` | 4 |
| `_proc` | 7 |
| `_proc_tree` | 2 |
| `_closing` | 4 |
| `_emit` | 36（check 事件也走它推 onBackend.check）|
| `_clock_ready` | 10 |
| `_terms_gate` | 10 |
| `_run` | 8 |
| `_push_login_expired` | 2 |
| `_begin_auto_relogin` | 2 |

---

### 块 5：计划（步骤 2 最后一刀，测试最密）

**公开方法**

| 方法 | 行号 |
|---|---|
| `grab(activity_id, name, at="", ...)` | 2780 |
| `start_request_state(request_id)` | 2854 |
| `cancel_start_request(request_id)` | 2891 |
| `start_plan(items, headed, ...)` | 2923 |
| `cancel_task(plan_id, task_id)` | 3234 |
| `stop_plan(plan_id)` | 3242 |
| `plan_active_for_close()` | 3271 |

**实例属性**

`__init__` 825-900、946-948 段：`_plan`（PlanCoordinator）、`_plan_procs`（dict）、`_plan_trees`（dict）、`_last_plan`、`_start_requests`/`_start_order`、`_canceled_start_ids`、`_plan_generation`、`_latest_plan_id`、`_finished_plan_ids`、`_next_plan_source`、`_plan_sources`、`_cancelling`。

**涉及的锁**

- `_lock`（98 处 with）：start_plan/_start_plan_inner/cancel_task/stop_plan 全在锁里。
- 无独立锁。

**测试打补丁的模块级名字**

- `PlanCoordinator`（30 次，拆计划时 PlanCoordinator 仍在 signup_plan.py，Api 只是转发，所以补 `app.PlanCoordinator` 的路径要留）
- `worker_command`（24 次，grab worker 命令构造）
- `spawn_owned`（16 次，进程树 spawn）
- `spawn_owned_worker`（1 次）
- `validate_plan`（1 次）
- `GRAB`（5 次，worker 路径常量）
- `LIST_CLOCK_WAIT_S`（5 次）
- `LIST_CLOCK_POLL_S`（3 次）

**测试改写的 Api 成员**

| 名字 | 次数 |
|---|---|
| `_plan` | 18 |
| `_activities` | 20 |
| `_proc` | 7 |
| `_plan_procs` | 1 |
| `_start_plan_inner` | 2 |
| `_start_requests` | 2 |
| `_start_order` | 2 |
| `_clock_ready` | 10 |
| `_run` | 8 |
| `_emit` | 36（plan/task/plan_done 事件全走它）|

---

### 其他：全局入口与窗口托盘（归不入五块的）

**全局入口（从块 1 挪入，对抗审计 C7）**

| 公开方法 | 行号 | 说明 |
|---|---|---|
| `bootstrap()` | 1149 | 组装初始快照（登录、列表、计划、更新、条款、手机、偏好） |
| `front_ready()` | 2052 | 界面就绪信号 |
| `help()` | 1245 | 打开帮助 |

**窗口托盘（`show_window` 系列 + 托盘）**

| 公开方法 | 行号 |
|---|---|
| `ask_window_close()` | 3310 |
| `request_window_close(action="")` | 3334 |
| `hide_window()` | 3389 |
| `show_window()` | 3427 |
| `window_visibility()` | 3443 |
| `open_data()` | 4333 |
| `open_latest_release()` | 4344 |
| `get_license_text()` | 4357 |
| `save_prefs(prefs)` | 4376 |
| `accept_terms(document_version="")` | 4383 |
| `withdraw_terms()` | 4409 |

实例属性：`_window`、`_window_hidden`、`_window_minimized`、`_tray`、`_close_approved`、`_closing`、`_shutdown_done_event`。锁：`_lock`。

**worker 进程（check/list/grab/relay 全共用的 spawn 路径）**

私有方法：`_run(args, timeout)` 4475 行、`_spawn(args, label, kind)` 4520 行、`_pump(proc, label, kind)` 4583 行、`_spawn_relay_worker(args)` 4257 行、`_relay_finished()` 4277 行。

共享属性：`_proc`、`_proc_tree`、`_relay_proc_tree`、`_aux_procs`、`_aux_trees`、`_plan_procs`、`_plan_trees`。锁：`_lock`（进程登记/终止全在锁里）。

---

## 第三节：桌面 esc 函数用法上下文

esc 定义：`local/ui/state/time.js:123-125`。正则 `/[&<>\"]/g`——转义 `&`、`<`、`>`、`"` 四个字符，**不含单引号**。

`git grep -c "esc(" 7e2d31c -- local/ui/` 报告 12 个文件共 88 行匹配（一行多个 esc 调用时 grep -c 只算 1 行）。脚本 `string_access.mjs` 精确计数：**11 个文件共 115 次调用**。另有 1 次是 `local/ui/state/time.js:124` 的定义行，全仓 116 次出现（对抗审计 C10 更正：原文把定义行算成调用，并把文件数算成 12）。

| 文件 | grep -c 行数 | 典型上下文（从 git show 抽样）| 包裹引号 | 注入风险评估 |
|---|---|---|---|---|
| `controllers/window.js:88` | 1 | `<b>` + esc(label) + `</b><span>` + esc(text) | 无引号（innerHTML 拼接）| 低：标签本身硬编码，esc 防 label/text 里的 `<>` |
| `state/filters.js` | 6 | 行 54: `<span class="activity-flag ...">" + esc(text) + "</span>"`<br>行 86: `title="' + esc(rw.title) + '">'`<br>行 88-98: `title="' + esc(...) + '"` 多处 | 双引号（title 属性值） | 无：属性值用双引号，esc 已转义 `"`（B1 更正：原判「中」不成立） |
| `views/clock-pop.js` | 12 | 全是 `<div class="...">" + esc(...) + "</div>"` 结构 | 无引号（innerHTML 文本）| 低 |
| `views/conflict-tip.js` | 4 | 行 10: `aria-label="' + esc(model.aria) + '"`<br>行 6-8: `"<dt>" + esc(r.label) + "</dt>"` | 双引号（aria-label） | 无：属性值用双引号，esc 已转义 `"`（B1 更正：原判「中」不成立） |
| `views/help.js` | 1 | 全是 `<li><span class="no">" + esc(step.no) + "</span>...` | 无引号 | 低 |
| `views/list.js` | 22 | 行 190-194: `data-id="' + esc(id) + '"`、`aria-label="' + esc(item.name) + '"`、`title="' + esc(item.place) + '"` 等 | 双引号（data-id、aria-label、title） | 无：生成的属性都是双引号，esc 已转义 `"`；单引号只是 JS 字符串定界符（B1 更正：原判「高」不成立） |
| `views/login.js` | 2 | `<strong>" + esc(result.title) + "</strong><span>" + esc(result.text) + "</span>"` | 无引号 | 低 |
| `views/plan-panel.js` | 27 | 行 215: `title="' + esc("完整地点：" + placeText) + '"`；行 479: `title="' + esc(item.name) + '"`；行 483: `aria-label="' + esc("从计划移除「" + item.name + "」") + '"` | 双引号（title、aria-label） | 无：同 list.js（B1 更正：原判「中高」不成立） |
| `views/selection.js` | 3 | `<strong>" + esc(label) + "</strong><br>" + esc(name)` | 无引号 | 低 |
| `views/status-cards.js` | 1 | `<dt>" + esc(row[0]) + "</dt><dd>" + esc(row[1]) + "</dd>"` | 无引号 | 低 |
| `views/terms.js` | 8 | 多数在 `.replace("现在就看", ...)` 里，esc 先转义再做字符串替换 | 双引号包裹的 JS 字符串（不是 HTML 属性）| 低：不在 HTML 属性值里 |

**结论（对抗审计 B1 更正）**：HTML 属性值一律用双引号，`esc` 已转义 `"`，全仓没有单引号定界的 HTML 属性，因此没有属性闭合注入面。单引号只出现在 JS 字符串定界符里（`app.js:237` 的 CSS 选择器 `[data-act='cx-go']` 不生成 HTML 属性）。原文「共约 30+ 处单引号属性」的说法撤回，**esc 不需要补单引号转义，也不是重构前置动作**。

---

## 第四节：经字符串访问的全局与桥接方法名

### 4.1 `window.onBackend.<kind>` —— 后端 evaluate_js 推事件

定义位置：`local/ui/app.js:90`。后端调用点：`local/app.py:1122`（`self._window.evaluate_js(js)` 拼出 `window.onBackend.<kind>(payload)`）。

11 个 kind：

| kind | app.js 定义行 | 后端触发位置 |
|---|---|---|
| `log` | 91 | `_emit` 1097 行 |
| `window_close_ask` | 93 | `_emit` 1097 行 |
| `check` | 95 | `_emit` 1097 行（check 结果）|
| `activities` | 130 | `_emit` 1097 行（list 结果）|
| `done` | 131 | `_emit` 1097 行 |
| `business_clock` | 132 | `_emit` 1097 行 |
| `plan` | 138 | `_emit` 1097 行（plan 事件）|
| `task` | 139 | `_emit` 1097 行 |
| `plan_done` | 140 | `_emit` 1097 行 |
| `second_open` | 143 | `_emit` 1097 行 |
| `update` | 145 | `_emit` 1097 行 |
| `phone_relogin` | 147 | `_emit` 1097 行（中继快照）|

后端 `_emit(kind, payload)` 把 kind 和 payload 序列化成 JS 代码字符串。**kind 是后端传入的字符串，前端没有白名单校验**——如果后端传了拼错的 kind，前端静默忽略；如果后端 payload 里带可执行代码，evaluate_js 会执行（但 payload 是 dict 序列化，pywebview 的 evaluate_js 一般走 JSON 序列化解包，不是字符串拼接）。

> 📌 **脚本扫出的 emit 差异**：`string_access.mjs` 报告前端定义了 12 个 onBackend kind，但后端 `self._emit("xxx",` 正则只抓到 10 个——**缺 `plan` 和 `task`**。原因：`plan` 和 `task` 不是直接 `self._emit("plan", ...)` 调用，而是走 `_start_plan_inner`（app.py:2994）内部定义的闭包变量 `emit(kind, payload)`，闭包内部才调 `self._emit(kind, forward)`。所以扫描正则没匹配到。实际后端是能 emit 这两个 kind 的，前端的 `plan`/`task` handler 能收到。

### 4.2 `api("xxx")` / `controller.api("xxx")` —— 前端调后端

桥接定义：`local/ui/controllers/bridge.js:6` 的 `function api(name, ...args)`。拼的是 `window.pywebview.api[name](...args)`。

所有 api("...") 字符串参数，从 `git grep -n "api("` 结果整理：

| api("xxx") 调用位置 | 字符串里的 name | 后端实际定义 | 对得上 |
|---|---|---|---|
| `app.js:14` | `"bootstrap"` | Api.bootstrap | ✓ |
| `app.js:81` | `"front_ready"` | Api.front_ready | ✓ |
| `app.js:417` | `"open_data"` | Api.open_data | ✓ |
| `app.js:527` | `"ask_window_close"` | Api.ask_window_close | ✓ |
| `app.js:532` | `"open_latest_release"` | Api.open_latest_release | ✓ |
| `app.js:542` | `"open_data"` | 同上 | ✓ |
| `app.js:637` | `"bootstrap"` | 同上 | ✓ |
| `controllers/bridge.js:6` | （定义） | — | — |
| `controllers/cancel.js:87` | `"cancel_signup"` | Api.cancel_signup | ✓ |
| `controllers/clock.js:16` | `"sync_clock"` | Api.sync_clock | ✓ |
| `controllers/clock.js:44` | `"clock_snapshot"` | Api.clock_snapshot | ✓ |
| `controllers/plan.js:46` | `"start_plan"` | Api.start_plan | ✓ |
| `controllers/plan.js:169` | `"start_request_state"` | Api.start_request_state | ✓ |
| `controllers/plan.js:266` | `"bootstrap"` | 同上 | ✓ |
| `controllers/plan.js:273` | `"cancel_task"` | Api.cancel_task | ✓ |
| `controllers/plan.js:387` | `"stop_plan"` | Api.stop_plan | ✓ |
| `controllers/plan.js:420` | `"login"` | Api.login | ✓ |
| `controllers/prefs.js:7` | `"save_prefs"` | Api.save_prefs | ✓ |
| `controllers/refresh.js:203` | `"check"` | Api.check | ✓ |
| `controllers/refresh.js:225` | `"list_activities"` | Api.list_activities | ✓ |
| `controllers/refresh.js:606` | `"window_visibility"` | Api.window_visibility | ✓ |
| `controllers/terms.js:296` | `"accept_terms"` | Api.accept_terms | ✓ |
| `controllers/terms.js:386` | `"bootstrap"` | 同上 | ✓ |
| `controllers/terms.js:478` | `"get_license_text"` | Api.get_license_text | ✓ |
| `controllers/tick.js:103` | `"check"` | 同上 | ✓ |
| `controllers/update.js:58` | `"check_update"` | Api.check_update | ✓ |
| `controllers/update.js:68` | `"bootstrap"` | 同上 | ✓ |
| `controllers/update.js:103` | `"update_download"` | Api.update_download | ✓ |
| `controllers/update.js:125` | `"update_cancel"` | Api.update_cancel | ✓ |
| `controllers/update.js:135` | `"update_launch"` | Api.update_launch | ✓ |
| `controllers/window.js:201` | `"request_window_close"` | Api.request_window_close | ✓ |
| `views/phone.js` 15 处 | `"phone_access_state"`, `"advanced_component_location"`, `"pick_advanced_component"`, `"inspect_advanced_component"`, `"install_advanced_feature"`, `"enable_advanced_feature"`, `"start_phone_access"`, `"stop_phone_access"`, `"open_advanced_component_dir"`, `"download_advanced_feature"`, `"cancel_advanced_feature_download"`, `"set_phone_access_preferences"`, `"prepare_phone_relogin"`, `"save_relogin_credentials"`, `"clear_relogin_credentials"` | 全部在 Api 上 | ✓ |
| `views/relogin.js` 5 处 | `"relogin_cancel"`, `"relogin_begin"`, `"relogin_auto_once"`, `"relogin_submit"` | 全部在 Api 上 | ✓ |
| `views/settings.js` 4 处 | `"withdraw_terms"`, `"advanced_component_location"`, `"enable_advanced_feature"`, `"open_advanced_component_dir"` | 全部在 Api 上 | ✓ |

**全部对得上**——前端用的每一个 api("xxx") 都在 Api 上有同名公开方法。如果有一个拼错了，pywebview 会直接报 undefined（不是静默忽略），所以生产里不太可能藏着拼错的。拆 Api 时，要保证这些名字仍然在传给 pywebview 的那个对象上（要么 Api 自己持有转发，要么 pywebview.api 换成新的 facade）。

### 4.3 Python getattr(self._api, name) —— 手机服务反射调用

位置：`local/application/phone_service.py:438`。name 来自 `local/domain/phone_rules.py` 的 `normalize_action(action, args)` 白名单校验。

完整 ACTION_PARAMS 白名单（从 `git show 7e2d31c:local/domain/phone_rules.py` + 脚本扫描双重确认，**12 个 key**）：

| key | Api 方法行号 | 对应 4.2 的 api("xxx") 是否出现 |
|---|---|---|
| `list_activities` | 2283 | ✓ 桌面端 refresh.js:225 |
| `check` | 2252 | ✓ refresh.js:203, tick.js:103 |
| `start_plan` | 2923 | ✓ plan.js:46 |
| `start_request_state` | 2854 | ✓ plan.js:169 |
| `cancel_start_request` | 2891 | 只有手机页调（`local/ui/m/app.js:2785`，经 postAction）；桌面端零调用（对抗审计 D3） |
| `stop_plan` | 3242 | ✓ plan.js:387 |
| `cancel_task` | 3234 | ✓ plan.js:273 |
| `save_retry_policy` | — （无同名 Api 方法；`phone_service.py:428-431` 特判为 `save_prefs`，只放行 `retry_policy` 键，对抗审计 B2 更正：不是死路径） | — |
| `show_window` | 3427 | （桌面端窗口恢复可能调，但 grep 没显式；phone.js 里也没看到显式调）|
| `phone_relogin_begin` | 4211 | ✓ phone.js 1103 |
| `phone_relogin_submit` | 4244 | ✓ relogin.js 413 |
| `phone_relogin_cancel` | 4248 | ✓ relogin.js 355 |

> 📌 `save_retry_policy` 不是死路径（对抗审计 B2 更正）：`phone_service.py:428-431` 在 `getattr` 之前把它改写成 `save_prefs`，只放行 `retry_policy` 键，`test_phone_service.py:492-502` 守着这条路径。它不需要 Api 上的同名方法；拆分时保留这段特判即可，不要从白名单删，也不要新增同名方法。

**构造时的 Api 传递链**：app.py:902-903 `self._phone = _phone_service.PhoneAccessService(api=self, ...)` → phone_service 存到 `self._api` → _call() 438 行 `method = getattr(self._api, name, None)`。拆 Api 时，要么把这 11 个方法挪到 PhoneFacade 对象上传给它，要么直接把 PhoneAccessService 改成显式 import 每个方法（消掉反射）。

### 4.4 window[...] 字符串键访问

`git grep -n "window\["` 在 PowerShell 下因为转义没跑通（退出码 1 即零匹配）。只是抽样核对，未全仓扫描（对抗审计 D5 用 grep 复核，`window[` 为 0 处，结论成立）：
- `app.js` 里没有明显的 `window["xxx"]`，都用点号（`window.onBackend`、`window.pywebview`）。
- 手机页 `local/ui/m/app.js` 也没查到（手机页代码没在本次 grep 范围内，但 `git show 7e2d31c:local/ui/m/` 没被 grep 到）。
- 结论：桌面端前端代码 **没有用字符串键访问 window 属性**，全部是点号。这条相对安全。

### 4.5 eval / Function / setTimeout("...") 其他

`git grep -n "eval\|setTimeout(\""` 因为 PowerShell 引号转义失败没跑完。从已读代码片段和 inventory.md 事实：
- pywebview 的 `evaluate_js`（app.py:1122）是唯一向前端执行 JS 的通道，传的是序列化成字符串的代码片段，不是用户输入拼接。
- 前端代码里没看到 `eval(` 或 `new Function` 调用。
- `setTimeout` 在 `app.js` 里出现几次（`clearTimeout(S.round.checkTimer)` 等），参数都是函数引用，不是字符串。
- 结论（抽样判断，未全仓扫描；对抗审计 D5 用 grep 复核，eval、new Function、setTimeout 字符串形式均为 0 处，结论成立）：**没有动态 eval / Function / setTimeout("string") 风险点**。

---

## Spot Checks（写完后随机抽 10 条核对）

1. **第二节块 1 check_update 行号**：声明 2057。`git show 7e2d31c:local/app.py | sed -n '2055,2060p'` → 是 `def check_update(self, request_id: str) -> dict:` ✓
2. **第二节 _lock 被 67 个方法读**：inventory.md 第三节 B 写"读的方法数 67" ✓
3. **第二节 ACTION_PARAMS key 数**：phone_rules.py 完整 dict 从 git show 读到 12 个 key（含 save_retry_policy）✓（原记 11，已更正）
4. **第三节 esc 正则不含单引号**：`/[&<>\"]/g` —— 对，只有 `&<>"\`" 五个字符 ✓
5. **第三节 title 属性定界符**：`git show 7e2d31c:local/ui/views/list.js` 里 `title="'` 是 JS 字符串中的 HTML 双引号属性，生成的属性是双引号（对抗审计 B1 更正：原判为单引号包裹，不成立）✓
6. **第四节 4.1 evaluate_js 位置**：`git show 7e2d31c:local/app.py | Select-String "evaluate_js"` → 1122 行 `self._window.evaluate_js(js)` ✓
7. **第四节 4.2 api("check_update") 调用**：`git grep -n 'api("check_update"' 7e2d31c -- local/ui/` → `controllers/update.js:58` ✓
8. **第四节 4.3 phone_service.py:438**：`git show 7e2d31c:local/application/phone_service.py | Select-Object -Skip 434 -First 15` → 438 行 `method = getattr(self._api, name, None)` ✓
9. **第一节 test_update_check.py 方法数**：grep 到 68 个（`def test_` 共 68，同文件 858 行）。原记 84 为误记，已更正（对抗审计 C9）。
10. **第二节 窗口托盘 ask_window_close 行号**：app.py def 表里 3310 行 ✓

全部 10 条 spot check 原记通过；其中第 3、5、9 条经对抗审计复核后已更正（见上）。
