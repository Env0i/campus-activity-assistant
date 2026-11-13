# T5 重构前置清点（prereq）

- 基线：`7e2d31c`（fix(component): 导入装好后收掉旧的下载失败）。产品代码与 docs 只按该提交读取，禁止读工作区现行文件。
- 引用条目：**92 条**（`q-001` 至 `q-092`），见同目录 `prereq.cites.jsonl`；全部摘录由构建脚本从 `git show 7e2d31c:<path>` 逐字提取，并预校验「落在 start..end 行内、至少 12 字符、在文件内唯一」。
- 脚本复跑（在仓库根执行）：

```bash
python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/api_methods.py
node design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/esc_sites.mjs
python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/verify_cites.py design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/prereq.cites.jsonl design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/prereq.md
```

- 口径与边界：只读审计，未运行任何测试或构建；行为测试的「已有/缺」结论来自对基线 `local/tests` 的检索（用例名、关键词、用例正文阅读），不是全量运行结果。`scripts/api_methods.py` 与 `scripts/esc_sites.mjs` 是本报告的清点工具，内容以脚本输出为准。

## 一、行为测试缺口

清单来源：第一轮 `design/evidence/2026-11-12/refactor-audit/ui-states.md` 末节「每一块动手前要先补的测试」表格（该文件是工作区审计产物、不在基线 7e2d31c 内，条目原文照录、引用位一律不空置）。逐条在基线 `local/tests` 检索后的结论如下；「缺」表示基线没有覆盖该行为的用例，检索命令与关键词在正文随条说明。

### 1. 修 U1（或步骤 1C）

| 清单条目 | 结论 | 依据 |
|---|---|---|
| 修改中、停止被后端拒绝：不再显示修改中，运行记录不说「已暂停」 | **缺** | 既有用例只断言暂停句文案与勾选计数 [[q-001]]；该用例把 stop_plan 桩成永不 resolve，暂停句照样断言已写出 [[q-002]]；基线在入口函数 modifyPlan 里同步写「计划已暂停：N 场放回草稿修改」、随后才调 doStopPlan 发 stop_plan [[q-003]]。即「拒绝后退出修改态、日志挪到停止成功之后」的行为基线既未实现也未测。检索词：修改中、已暂停、stop_plan、放弃 |
| 修改中、计划自然结束后点「重新选择未成功的场次」：回到的不是修改中 | **缺** | 基线存在对应行为分支：修改中收到 stopped 终态会把未提交场次放回选择集、清计划并关结果页 [[q-008]]；「重新选择」只有放回规则用例（名额满不放回等）[[q-007]]；修改态清理只有「重新开始被接纳」一条路径有测 [[q-004]]。两者之间（自然结束后点重新选择）无用例。检索词：reselectFailed、reselectableIds、S.editing |
| 「放弃修改」：提交的是原计划的场次，不是当前勾选 | **缺** | 按钮「放弃修改，按原计划继续」在基线桌面页存在 [[q-005]]，点击直接绑定 startPlan [[q-006]]；基线没有任何测试触到 btn-edit-restore，也没有用例区分「原计划场次」与「当前勾选」。检索词：btn-edit-restore、editRestore、放弃修改 |

### 2. 修 U2、U3（或列表一块）

清单把四处刷新合并为一条要求：这四处的刷新「不出骨架；失败时列表和勾选不变」。逐处结论：

| 触发点 | 结论 | 依据 |
|---|---|---|
| 窗口重新可见 | **缺** | 行为存在：visibilitychange 里 bootstrap、必要时 refresh(true)、补一次 autoRefreshTick [[q-011]]；但既有覆盖只是源码文本断言（检查监听器里写了 autoRefreshTick），不是行为用例 [[q-012]]。检索词：visibilitychange、window_visibility、骨架 |
| 取消报名成功后 | **缺** | 取消成功后基线直接 refresh(true) [[q-009]]；无任何用例断言该次刷新「不出骨架、失败时列表和勾选不变」。检索词：cancelSettle、cancel_signup、refresh(true)、骨架 |
| 计划结束后 | **缺** | scheduleSignedRefresh 有界刷新存在 [[q-010]]；`git grep scheduleSignedRefresh 7e2d31c -- local/tests` 无命中，测试对它零引用。 |
| 重新登录成功后 | **部分已有** | 触发与去重已有行为用例（N1）：登录成功走一次 check+list、同 flow 重放不重刷、计划运行中不刷 [[q-013]] [[q-014]]；但该用例断言的是「调用次数」，没有断言「不出骨架」与「失败时列表和勾选不变」，这部分仍缺。 |

### 3. 修 U4、U7（或手机页一块）

| 清单条目 | 结论 | 依据 |
|---|---|---|
| 弹层开着时轮询带来新计划状态：弹层内容跟着变 | **缺** | 基线手机页 renderReview 只在移除条目与打开核对面板两处被调 [[q-016]]；轮询事件入库只特殊处理 log 与 phone_relogin 两种 kind [[q-017]]——U4 描述的「弹层开着时轮询新状态不重画」在基线仍未修，目标行为无用例。检索词：renderReview、ingest、sheet |
| 「最近同步」在手机时区和北京时间不同时显示北京时间 | **缺** | 基线手机页「最近同步」用 new Date() 取手机本地时钟 [[q-015]]——U7 同样未修；现有 last-sync 用例只钉位置与显隐，不断言时区口径。检索词：last-sync、最近同步、beijingSecOf、时区 |

### 4. 步骤 1A 组件

| 清单条目 | 结论 | 依据 |
|---|---|---|
| 检查中超过时限：出现原因和重试 | **缺** | 组件「检查中」态基线只测到「忙且无缓存时标 checking、不标 failed」[[q-024]]；无超时出口、原因下发与重试入口的用例（对应第一轮 U5：提案已定下一版做、需后端配合）。检索词：checking、超时、timeout、重试 |
| 读状态失败：有提示 | **缺** | FB4-R1 已有的组件横幅用例针对 check/list 阶段的组件失败 [[q-025]]；「读组件状态失败时界面提示」（第一轮 U10）无用例。检索词：读状态、runtime_error、横幅 |
| 两个组件同时一个在下载、一个在安装：各显示各的 | **缺** | 组件下载是单飞设计（同时只允许一个下载任务）[[q-023]]；基线无用例覆盖「下载与安装并行时两个状态各自独立显示」。检索词：download_advanced_feature、install_advanced_feature、_advanced_busy |

### 5. 步骤 1B 登录

| 清单条目 | 结论 | 依据 |
|---|---|---|
| 校验结论晚于中继终态到达：胶囊不回亮 | **缺** | 基线对迟到校验结论只有 request_id 一层守卫：后端 _emit 给 check/activities 补本轮 request_id [[q-027]]，前端 check 处理器按 id 丢弃旧轮 [[q-028]]；「中继终态已落、迟到的校验结论不得把胶囊点亮回已登录」没有专门用例。Api.login 的忙碌门禁（关闭中、计划运行中拒绝）见 [[q-026]]。检索词：request_id、迟到、胶囊、setLogin |
| 验证码页改用浏览器：浏览器登录能开始 | **缺** | 无任何用例覆盖「relogin_cancel 与 login 两个桥接调用以任意顺序到达时 login 不被忙碌检查拒绝」（第一轮 U6 标注为推测、未证实，建议先补行为测试）；基线登录门禁见 [[q-026]]。检索词：relogin_cancel、login、busy、浏览器 |

### 6. 步骤 1C 计划栏

| 清单条目 | 结论 | 依据 |
|---|---|---|
| 停止成功但结束事件没到：窗口重新可见后「正在停止」能收掉 | **缺** | 机制存在：doStopPlan 立即置 S.stopping [[q-018]]，stop 失败/异常自收 [[q-019]]，重复终态早返回自清 [[q-020]]，bootstrap 终态快照走 presentPlanDone 同一入口 [[q-021]]；但基线唯一相关行为用例覆盖的是「重复 plan_done 到达」路径 [[q-022]]，「结束事件没到、靠窗口重新可见的 bootstrap 收掉」无用例。检索词：S.stopping、plan_done、ingestBootstrapPlan |

### 7. 步骤 2 更新

| 清单条目 | 结论 | 依据 |
|---|---|---|
| 安装程序启动成功后的状态（按用户定的做法） | **已有** | 后端：启动成功发布 launching 事件并安排退出 [[q-029]]，拉起失败不安排退出 [[q-032]]；前端：launching 二段文案 [[q-030]]、按钮从「启动中…」变「关闭本工具…」[[q-031]]。检索词：update_launch、launching、关闭本工具 |

小结：16 条检查项，**缺 14 条**、**部分已有 1 条**（重新登录成功后的刷新）、**已有 1 条**（安装程序启动成功后的状态）。第一轮点名的样板写法（每条用例一条退出路径）见第一轮文件所引 `SilentReloginResidualTests`；基线里与「正在停止」相邻的 `StoppingEarlyReturnTests` 也是这种写法 [[q-022]]。

## 二、Api 公开方法清点与归块

清点脚本：`scripts/api_methods.py`（python 标准库 ast，内部 `git show 7e2d31c:local/app.py` 取基线内容，不手抄；只读、无第三方依赖）。

- **方法总数 153，公开 60，私有 93**。口径：`class Api`（local/app.py:813 起 [[q-033]]）的直接子节点函数定义，公开 = 名字不以下划线开头；不含嵌套函数与模块级函数。与任务书给的参考口径（153/60）一致。
- 归块口径：按「这一步重构会动到它的实现」归入 更新 / 组件 / 手机访问 / 登录恢复 / 计划 五块之一；同时服务多块或属于窗口/生命周期/静态信息的归「跨块」。依据写在每行。

### 2.1 各块方法清单与依据

**更新（4 个）**

| 方法 | 行号 | 归属依据 |
|---|---|---|
| check_update | 2057 | 只登记轻量后台查询新版本，不在桥接线程等网络 [[q-039]] |
| update_download | 2117 | 用户确认后启动安装器下载：单飞后台流式下载并校验 |
| update_cancel | 2171 | 只置取消标记，下载线程在下一块之间停下 |
| update_launch | 2177 | 启动前先回推 launching，成功后安排退出本程序 [[q-040]] |

**组件（11 个）**

| 方法 | 行号 | 归属依据 |
|---|---|---|
| download_advanced_feature | 1425 | 组件包下载单飞入口 [[q-023]] |
| cancel_advanced_feature_download | 1452 | 取消在进行的组件下载 |
| enable_advanced_feature | 1459 | 启用已装好但未开启的组件（settings-gap B2） |
| advanced_component_location | 1488 | 组件安装位置（B3，电脑端设置抽屉用） |
| open_advanced_component_dir | 1506 | 资源管理器打开组件文件夹（B3，电脑端） |
| advanced_features_state | 1525 | 帮助弹窗的高级功能快照；不返回密码、密文、安装路径 |
| inspect_advanced_component | 1606 | 只读自检所选文件是不是要装的东西 |
| pick_advanced_component | 1624 | 系统文件选择框，选中路径交回对话框 |
| install_advanced_feature | 1644 | 只响应帮助弹窗明确点击的固定组件，不接受任意 pip 包名 |
| remove_advanced_feature | 1733 | 定义存在 [[q-045]]，但全仓检索无任何调用点（见 4.4 对不上的项） |
| schedule_component_auto_update | 3963 | 窗口加载完后把「只差版本」的组件补上，每次启动只走一遍 |

**手机访问（6 个）**

| 方法 | 行号 | 归属依据 |
|---|---|---|
| phone_access_state | 3767 | 监听状态、远程通道、地址、二维码与一次性配对码 [[q-042]] |
| start_phone_access | 3812 | 启动手机访问监听（Tailscale/Cloudflare 通道） |
| stop_phone_access | 4017 | 停止监听并记录 Cloudflare 退出通知 |
| set_phone_access_preferences | 3897 | 记住通道选择，只影响下次启动是否自动恢复 |
| restore_phone_access | 3913 | 窗口就绪后恢复入口：只恢复 Tailscale，绝不自动恢复 Cloudflare |
| schedule_phone_restore | 3937 | 窗口加载完再恢复手机入口（内部转调 restore_phone_access） |

**登录恢复（10 个）**

| 方法 | 行号 | 归属依据 |
|---|---|---|
| prepare_phone_relogin | 4043 | 桌面「准备手机重登」：账号密码只进当前进程内存 [[q-043]] |
| save_relogin_credentials | 1770 | 保存续登录账号密码（DPAPI 加密落盘） |
| clear_relogin_credentials | 1795 | 清掉已保存的续登录凭据 |
| relogin_begin | 4153 | 电脑上点「重新登录」的四种情况 [[q-044]] |
| relogin_submit | 4182 | 电脑上输的验证码 |
| relogin_cancel | 4186 | 取消电脑上发起或接手的这一场登录 |
| relogin_auto_once | 4194 | 有保存账号又装了识别组件时，确认后让电脑自动登录一次 |
| phone_relogin_begin | 4211 | 手机发起的重登开始 |
| phone_relogin_submit | 4244 | 手机提交验证码 |
| phone_relogin_cancel | 4248 | 手机取消这一场重登 |

**计划（5 个）**

| 方法 | 行号 | 归属依据 |
|---|---|---|
| start_request_state | 2854 | 只读对账：开始请求是 pending/accepted/rejected/canceled |
| cancel_start_request | 2891 | 放弃待确认的开始；未知 ID 先登记取消，拦住迟到原请求 |
| start_plan | 2923 | 校验并启动计划，按 request_id 幂等 [[q-041]] |
| cancel_task | 3234 | 取消计划中单场 |
| stop_plan | 3242 | 停止整个计划并终止 worker 进程树 |

**跨块（24 个）**

| 方法 | 行号 | 归属依据 |
|---|---|---|
| clock_snapshot | 1036 | 业务时钟快照，所有块都读（决策 012） |
| sync_clock | 1046 | 重新校时，完成后推 business_clock 事件 |
| bootstrap | 1149 | 聚合时钟、登录、计划、更新等全量快照 [[q-038]] |
| help | 1245 | 帮助弹窗静态内容 |
| front_ready | 2052 | 窗口就绪钩子：触发手机恢复与组件补装 |
| check | 2252 | 登录态校验（学校动作），桌面与手机白名单共用 |
| list_activities | 2283 | 活动列表拉取（学校动作），桌面与手机白名单共用 |
| cancel_signup | 2555 | 取消已报名场次（学校动作、自带 worker 与互斥字段） |
| login | 2762 | 打开学校登录页的 worker（登录基础动作，忙碌门禁见 [[q-026]]） |
| grab | 2780 | 旧的单场直抢入口（学校动作） |
| plan_active_for_close | 3271 | 计划在跑或已就绪时关窗必须先问——计划×关窗共用 |
| ask_window_close | 3310 | 把关窗四选推给界面 |
| request_window_close | 3334 | 界面四选结果：hide/minimize/exit/不关 |
| hide_window | 3389 | 藏窗口到托盘，手机访问与计划继续跑 |
| show_window | 3427 | 托盘菜单与手机页共用的唤回入口 |
| window_visibility | 3443 | 界面自动刷新前问窗口是否藏在托盘 |
| shutdown | 3521 | 进程收尾：关闭屏障、停协调器、终止本 Api 登记的 worker |
| stop | 3621 | 停当前 worker 与计划（收尾入口） |
| open_data | 4333 | 打开数据目录并回真实路径 |
| open_latest_release | 4344 | 浏览器打开 releases/latest 固定页 |
| get_license_text | 4357 | 随包 LICENSE 原文 |
| save_prefs | 4376 | 偏好原子事务（手机端 save_retry_policy 特判最终落到这里） |
| accept_terms | 4383 | 同意条款：核验版本后经 ui.json 原子偏好落盘 |
| withdraw_terms | 4409 | 撤回条款同意，学校动作回到条款门后 |

### 2.2 各块的实例字段、锁、补丁目标与被改写成员

口径说明：
- 「实例字段」只列 Api 在 `__init__` 里赋值的数据成员（共 67 个，脚本 [fields] 节可复算）中、被本块公开方法本体读或写的；方法调用（如 `_emit`、`_terms_gate`）不算字段。
- 「锁」含实例锁与模块级锁。
- 「补丁目标」= 测试里 `patch.object(app.X)` / `patch("app.X")` 的目标；「被改写成员」= 测试对 Api 实例属性或方法的直接赋值替换（`git grep -nE "(self\.api|api)\.[A-Za-z_0-9]+ ?=" 7e2d31c -- local/tests`）。

**更新（4 个）**
- 实例字段：`_update_cancelled`、`_update_installer`、`_update_installer_path`、`_update_request_id`、`_update_result`、`_update_staging_path`、`_updating`、`_closing`（读）
- 锁：`_lock`（实例）
- 补丁目标：`app.sys`（frozen 判定，[[q-051]]）、`app.subprocess`（启动器 Popen，[[q-052]]）
- 被改写成员：`_update_result`（11 处）、`_update_installer`（9）、`_update_staging_path`（7）、`_updating`（4）、`_update_request_id`（3）、方法 `request_window_close`（1，[[q-059]]）

**组件（11 个）**
- 实例字段：`_advanced_busy`、`_auto_relogin`、`_closing`、`_cloudflare`、`_component_service`、`_credential_lock`、`_last_login_origin`、`_lock`、`_phone`、`_phone_access_lock`、`_relay`、`_window`（pick 选框）
- 锁：`_lock`、`_credential_lock`、`_phone_access_lock`（三把实例锁定义见 [[q-034]]）
- 补丁目标：`app.sys`
- 被改写成员：`_advanced_busy`（3）、`_component_service`（1）、`_ocr_component_service`（2）、方法 `stop_phone_access`（1，装组件前替身停隧道，[[q-057]]）

**手机访问（6 个）**
- 实例字段：`_cloudflare`、`_cloudflare_exit_notice`、`_closing`、`_lock`、`_phone`、`_phone_access_lock`、`_phone_channel`
- 锁：`_phone_access_lock`、`_lock`
- 补丁目标：无直接 patch（测试经替身 PhoneService 走）
- 被改写成员：`_phone`（8，改写实样 [[q-054]]）、`_cloudflare`（5）、`_phone_channel`（1）、`_phone_access_lock`（1）、方法 `stop_phone_access`（1）

**登录恢复（10 个）**
- 实例字段：`_auto_relogin`、`_credential_lock`、`_lock`、`_once_creds_rejected`、`_pending_save`、`_relay`、`_relay_creds_source`
- 锁：`_credential_lock`、`_lock`
- 补丁目标：无直接 patch（中继经替身进程/管道）
- 被改写成员：`_relay`（11）、`_auto_relogin`（7）、方法 `_begin_auto_relogin`（2）、`_push_login_expired`（2）、`_credential_lock`（1）、`_silent_relogin_ready`（1）、`_relogin_blocked_locked`（1）、`_once_credentials_staged`（1）、`_auto_relogin_paused`（1）、`_auto_relogin_started_at`（1）

**计划（5 个）**
- 实例字段：`_latest_plan_id`、`_lock`、`_next_plan_source`、`_plan`、`_plan_generation`、`_start_requests`
- 锁：`_lock`
- 补丁目标：`app.Api._run_plan_task`（[[q-050]]）、`app.subprocess`
- 被改写成员：`_plan`（16）、`_start_requests`（2）、`_canceled_start_ids`（1）、`_proc`（6）、`_proc_tree`（2）、`_plan_procs`（1）、`_aux_procs`（1）、`_aux_trees`（1）

**跨块（24 个）**
- 实例字段：`_activities`、`_aux_procs`、`_aux_trees`、`_cancelling`、`_check_again`、`_check_last`、`_check_request_id`、`_checking`、`_clock`、`_clock_syncing`、`_close_approved`、`_closing`、`_last_check`、`_list_last`、`_list_request_id`、`_listing`、`_lock`、`_phone`（hide/show 提示）、`_plan`、`_proc`、`_proc_tree`、`_relay_proc_tree`、`_shutdown_done_event`、`_tray`、`_update_installer_path`、`_update_request_id`、`_update_result`、`_updating`、`_window`、`_window_hidden`、`_window_minimized`
- 锁：`_lock`、`_shutdown_done_event`（Event，[[q-035]]）；模块级 `_PHONE_LOG_LOCK` [[q-036]]（手机日志投递）与 `_LIFECYCLE_LOCK` [[q-037]]（生命周期存取，bootstrap 读）
- 补丁目标：`app.Api._run` [[q-046]] [[q-048]]、`app.Api._spawn` [[q-047]] [[q-049]]、`app.subprocess`、`app.AppLifecycle` [[q-053]]
- 被改写成员：`_emit`（36，[[q-055]]）、`_last_check`（21）、`_activities`（20）、`_window`（16）、方法 `_ensure_tray`（10）、方法 `_terms_gate`（7）、`_closing`（4）、`_window_hidden`（4）、`_checking`（3）、`_tray`（3）、方法 `list_activities`（3）、`_clock_now`（2）、方法 `check` 与 `_do_check_inner`（[[q-056]]）、方法 `accept_terms`、`withdraw_terms`、`plan_active_for_close`（[[q-058]]）、`_endpoint`（1）、`_is_busy_locked`（1）、`_lock`（1）、`_list_last`（1）、`_close_approved`（1）、`_window_minimized`（1）、方法 `cancel_signup`（1）、`_cancelling`（setattr，test_cancel_signup.py）

### 2.3 与参考口径的核对

任务书给的参考口径「Api 153 个方法、公开 60 个」与脚本输出一致；「他人 prereq.md 194 条引用」仅作完备性参照，本报告按事实需要落了 92 条。

## 三、esc 调用点（桌面前端，local/ui 除 m/）

清点脚本：`scripts/esc_sites.mjs`（node 标准库，内部 `git ls-tree`/`git show 7e2d31c:local/ui/...` 取基线内容；逐字符扫描，处理注释、字符串、模板字面量与正则字面量；从仓库根复跑）。

- 扫描范围：`local/ui/` 下 40 个 .js/.html 文件（`local/ui/m/` 整目录排除；`index.html` 无内联 esc 调用，一并扫过为零）。`styles.css` 与图标不扫。
- **esc 定义 1 处**：local/ui/state/time.js:123 [[q-060]]——只转义 `&`、`<`、`>`、`"`，**不转义单引号 `'`**；同文件的 `cssEscape` 只处理双引号与反斜杠，是选择器专用 [[q-061]]。
- **esc( 调用点共 115 处**（grep 按行计数 88 行，多行拼接上一行多处调用，脚本按调用次数计数）；另有 esc 标识符的 3 处非调用引用，全是 local/ui/views/terms.js:46/82/85 里 `const esc = dialog.querySelector(".help-esc")` 的同名局部变量（遮蔽全局转义函数）[[q-067]]。
- 按文件分布：plan-panel.js 38、list.js 28、clock-pop.js 12、terms.js 8、filters.js 7、conflict-tip.js 6、selection.js 6、help.js 3、login.js 3、status-cards.js 2、controllers/window.js 2。其余 29 个文件零调用（含 app.js、全部 controllers、state/store.js、views/phone.js、views/relogin.js、views/settings.js、views/update.js、views/tour.js、views/log.js、views/clock.js）。

### 3.1 落点粗分类计数

| 落点 | 脚本自动 | 人工复核后 |
|---|---|---|
| 文本节点 | 77 | **91** |
| 双引号属性 | 24 | **24** |
| 单引号属性 | 0 | **0** |
| 事件处理器字符串 | 0 | **0** |
| URL | 0 | **0** |
| 其他 | 14 | **0** |

人工复核说明：脚本对「esc 前导字符串不是直接拼接操作数」的 14 处标了「其他」，逐一读代码后全部归「文本节点」——它们是先把 esc 结果存进局部变量再拼接（plan-panel.js:210/211，落点在 214/216 的 span 文本 [[q-069]]）、或前导字面量是纯文字没有标签字符（plan-panel.js:735 三处、1087、1413；selection.js:74/79/80 两处；terms.js:268，其落点在 286 的 innerHTML 文本位）。这 14 处的 file:line 清单以脚本输出的 cat=其他 行为准，复核后无一落在属性或处理器上下文。

### 3.2 注入风险结论

- **文本节点（91 处）：由 esc 的转义集覆盖。** esc 转义 `<`、`>`、`&`，值里出现标签无法逃出文本位 [[q-060]]；样例见组头文本 [[q-064]] 与时钟弹层 dd 文本 [[q-065]]。单引号不转义在文本位无害。
- **双引号属性（24 处）：由 esc 的转义集覆盖。** 属性值以 `"` 包裹（如 title=、data-id、aria-label、data-rx、data-cancel 等 [[q-062]] [[q-063]] [[q-068]]），esc 转义 `"` 使值无法中途断出；值里出现 `'` 无害。
- **单引号属性、事件处理器字符串、URL：0 处。** 全部 115 处人工复核未见 `attr='...'` 形态、未见 on* 处理器内嵌 esc、未见 href/src 拼 esc。因此「esc 不转义单引号」在基线桌面端**当前不构成注入路径**。
- **结构性缺口（需测试定）**：以上结论依赖「落点形态恰好只有文本节点与双引号属性」这一现状，没有自动化测试守护。任何后续把落点改成单引号属性、内联事件处理器或 href 的改动都会立即绕过 esc（`'` 不转义）。本项标**需测试定**：missing=没有针对 esc 落点形态的契约测试，改动后只能靠人工重扫。
- **两处特例**：
  1. terms.js:347-350：esc(text) 之后 `.replace` 把固定子串换成固定按钮再落 span 文本位 [[q-066]]——esc 先行、替换内容是写死按钮，不引入新注入面；但「esc 后再加工」是唯一一处，重构时值得单独看。
  2. terms.js:46：applyTermsFooter 内 `const esc` 局部遮蔽全局转义函数 [[q-067]]，该函数内 82/85 两行用的是局部元素。在该函数作用域里若再按全局语义调 esc(x) 会拿到 DOM 元素——重构改名时注意。
- **需测试定（另一条）**：esc 是否转义 `'` 与单引号属性的组合风险在手机页（m/）未审计——本节只覆盖桌面端；手机页有独立的转义实现，属第一轮手机页审计范围，本次未核对。

## 四、字符串访问的全局与桥接名

把「按字符串取属性/按字符串调方法」的五个形态全部列出，与实际定义逐一比对。

### 4.1 window[...] 动态取属性

- **桌面前端生产代码：0 处**。`git grep -F "window[" 7e2d31c -- local/ui` 无命中。桌面端真正按字符串取方法的是 `window.pywebview.api[name]`（bridge.js 的 api(name) 端口 [[q-070]]），见 4.2。
- **app.py 里的 `window["close_action"]`**（app.py:3385）：这是偏好字典 `window` 段的键，不是浏览器 window 对象 [[q-086]]——与前端 window 全局同名但无关，重构搜索时容易误伤。
- **测试沙箱：local/tests/test_ui_contract.py:2383-2385** 用 `window[name]` 或 eval 动态替换全局函数 [[q-092]]，属测试基建；改全局函数名时这两行会跟着失效。

### 4.2 api("…") 形式的字符串调用（前端到后端）

- 端口定义：bridge.js `function api(name, ...args)` 经 `window.pywebview.api[name]` 动态取方法 [[q-070]]；名字不存在时回「本机程序不支持：name」。
- 桌面前端共 **44 个不同方法名的字符串调用**（54 处（AA2 复核：44 个不同名、54 处调用；原 42 处漏计 controllers/ 与 app.js） `api("…")` 字面量去重，双引号形态；无单引号形态、无变量名形态）。逐一比对基线 Api 60 个公开方法：**44 个全部存在，无对不上的桥接名**。
- 反向：60 个公开方法中有 16 个从未被桌面 `api("…")` 调用：advanced_features_state、cancel_start_request、grab、help、hide_window、phone_relogin_begin、phone_relogin_cancel、phone_relogin_submit、plan_active_for_close、remove_advanced_feature、restore_phone_access、schedule_component_auto_update、schedule_phone_restore、show_window、shutdown、stop。其中多数是内部转调目标（bootstrap 调 help/advanced_features_state、request_window_close 调 hide_window、schedule_phone_restore 调 restore_phone_access 等）或手机白名单动作（cancel_start_request、phone_relogin_* 、show_window）；**remove_advanced_feature 是唯一全仓无调用点的公开方法** [[q-045]]，见 4.4。

### 4.3 evaluate_js 拼出的 window.onBackend.<kind>

- 后端唯一注入点：`_emit` 拼 `window.onBackend && window.onBackend.<kind>(<json>)` 后 `evaluate_js` [[q-072]]；kind 取值共 **12 个**。
- 直发 10 个：log、activities、check、window_close_ask、update、second_open、plan_done、phone_relogin、done、business_clock（`_emit("…")` 直调）；经事件闭包再发 2 个：plan、task——start_plan 内定义 emit 闭包转发 [[q-073]]，plan_done 由闭包转发 [[q-074]]，kind 源头在报名协调器 [[q-075]] [[q-076]]。
- 前端处理器表：window.onBackend 定义 12 个键 [[q-071]]（log、window_close_ask、check、activities、business_clock、done、plan、task、plan_done、phone_relogin、second_open、update）。
- **比对结论：12 个 kind 与 12 个键一一对应，无多无少。** 注意两点：前端 refresh.js 另有两处直接调 `window.onBackend.check(…)`（缓存重放），键名与后端一致；`phone_relogin` 事件在进手机事件缓冲时换成投影视图 [[q-088]]，桌面端收到的是原始载荷。

### 4.4 手机 ACTION_PARAMS 的键

白名单定义在 local/domain/phone_rules.py:155 起 [[q-077]] [[q-078]]，`normalize_action` 对未知动作与多余键一律拒绝 [[q-079]]。12 个键与定义的比对：

| 白名单动作 | 暴露到的 Api 成员 | 对得上？ |
|---|---|---|
| list_activities | Api.list_activities（app.py:2283） | 是 |
| check | Api.check（app.py:2252） | 是 |
| start_plan | Api.start_plan（app.py:2923），服务端注入 source=phone [[q-080]] | 是 |
| start_request_state | Api.start_request_state（app.py:2854） | 是 |
| cancel_start_request | Api.cancel_start_request（app.py:2891） | 是 |
| stop_plan | Api.stop_plan（app.py:3242） | 是 |
| cancel_task | Api.cancel_task（app.py:3234） | 是 |
| save_retry_policy | **不是 Api 方法**：dispatch 特判映射到 Api.save_prefs 且只带 retry_policy 键 [[q-080]] | 是（经特判） |
| show_window | Api.show_window（app.py:3427） | 是 |
| phone_relogin_begin | Api.phone_relogin_begin（app.py:4211） | 是 |
| phone_relogin_submit | Api.phone_relogin_submit（app.py:4244） | 是 |
| phone_relogin_cancel | Api.phone_relogin_cancel（app.py:4248） | 是 |

实际调用方核对：手机页 m/app.js 共发起 10 个动作字面量（stop_plan、start_request_state、start_plan、show_window、save_retry_policy、phone_relogin_submit、phone_relogin_cancel、phone_relogin_begin、cancel_task、cancel_start_request，样例 [[q-089]]）；`list_activities` 与 `check` 在白名单内但手机页按快照取数、未作为动作发起（白名单比页面用法宽，属冗余不算错）。派发终点 `getattr(self._api, name)` [[q-081]] 按字符串取 Api 属性——白名单里有而 Api 上没有的名字只有 save_retry_policy，且它在 getattr 之前被特判改道，不会真正 getattr。

### 4.5 phone_service 对手机页的特判路径

- **静态文件固定映射**：PHONE_STATIC 只放行 `/`、`/index.html`、`/styles.css`、`/app.js` 四个名字 [[q-082]]，来源目录默认 `local/ui/m` [[q-083]]；映射之外的文件一律取不到。
- **HTTP 路由白名单**：GET 只放 `/api/state` 与静态白名单 [[q-084]]；POST 只放 `/pair` 与 `/api/action`，且先查 Host、Origin、Content-Type [[q-085]]。手机页的调用方核对：`/api/state?after=<seq>` 增量轮询 [[q-090]]、POST /pair 配对 [[q-091]]、动作都走 `/api/action`——页面用到的端点与路由表一一对应，无页面请求落在路由之外。
- **动作派发特判**：save_retry_policy 改道 save_prefs（只带 retry_policy）、start_plan 注入 source=phone [[q-080]]。
- **事件缓冲特判**：手机事件缓冲只收投影后的事件，log 事件额外隐去网址与本机路径，其余 kind 原名透传 [[q-087]]；phone_relogin 事件在 _emit 里换成手机投影视图 [[q-088]]。
- **对不上的明确标出**：
  1. `remove_advanced_feature`（app.py:1733）是 js_api 暴露面的一部分但全仓零调用——既不在桌面 api() 调用里、不在手机白名单里、也没有测试触达。属于「暴露但没人用」，重构组件块时按死代码处理或补调用方，需测试定（missing=无使用方证据，删除/保留由重构计划拍板）。
  2. `window["close_action"]`（app.py:3385）与前端 window 全局同名，是偏好字典不是浏览器对象 [[q-086]]——按 4.1 的口径列在这里防止检索误判。
  3. 手机白名单里的 `save_retry_policy` 不是 Api 成员名，靠特判映射（[[q-080]]）；若重构把特判挪走而白名单没同步，会变成「白名单放行一个不存在的动作」，当前不算对不上。

## spot_checks

随机抽取 12 条重读基线原文核对语义（2026-11-13，全部与条目摘录和 claim 一致）：

1. q-002/q-003：重读 test_ui_main_window_plan.py:393 与 plan.js:353-355——stop_plan 桩永不 resolve、暂停句同步写入，claim 部分成立（T7 修正：「同一函数」应为 modifyPlan 写句、doStopPlan 发调用）。
2. q-008：重读 plan-events.js:18-25——修改中收到 stopped 把未提交场次放回选择集并清计划，claim 成立。
3. q-010：重读 refresh.js:451-459——scheduleSignedRefresh 800ms 有界刷新、busy/starting/demo 跳过，claim 成立。
4. q-012：重读 test_ui_reliability.py:2199-2204——确实是 read_text 后 assertIn 源码文本，非行为用例，claim 成立。
5. q-014：重读 test_ui_contract.py:8661-8672——断言 once/replay/busy 三组调用计数，claim 成立。
6. q-015：重读 m/app.js:2706-2711——new Date().getHours/getMinutes 拼进「最近同步」，claim 成立。
7. q-016：重读 m/app.js:2951-2960——renderReview 仅 removeFromReview 与 openReview 调用，claim 成立。
8. q-022：重读 test_ui_reliability.py:1365-1370——StoppingEarlyReturnTests 场景是重复 plan_done 到达，claim 成立。
9. q-029：重读 test_application_services.py:2598-2606——launching 事件 + 安排退出，claim 成立。
10. q-060：重读 state/time.js:123-124——转义集正则 `[&<>"]`，无单引号，claim 成立。
11. q-080：重读 phone_service.py:422-435——save_retry_policy 特判到 save_prefs、start_plan 注入 source，claim 成立。
12. q-083：重读 phone_http.py:71——ui_dir 默认 `parents[1] / "ui" / "m"`，claim 成立。

补充抽查 8 条（同日，覆盖补丁目标与成员改写类条目）：

13. q-046/q-047：重读 app.py:4475-4477 与 4520-4522——_run 文档串自述「同步跑一个短命 worker（check/list）」、_spawn 起一次性 worker，claim 成立。
14. q-048 至 q-053：重读 test_runtime_bundle.py:397-398/443/1029/1863-1864/988 与 test_session_persistence.py:1333——六个 patch.object 目标（_run、_spawn、_run_plan_task、app.sys.frozen、app.subprocess.Popen、app.AppLifecycle.INTERVAL_S）逐字在行，claim 成立。
15. q-054：重读 test_application_services.py:283-289——`self.api._phone = FakePhoneService()` 与 `_endpoint` 字典替换，claim 成立。
16. q-055/q-056：重读 test_application_services.py:469-470 与 1475、1489——_emit 换 lambda、check 方法与 _do_check_inner 整体替换，claim 成立。
17. q-057：重读 test_release_audit.py:104——`self.api.stop_phone_access = mock.Mock()`，claim 成立。
18. q-058：重读 test_terms_consent.py:436-438——plan_active_for_close 换 lambda、withdraw_terms/accept_terms 换 MethodType，claim 成立。
19. q-059：重读 test_application_services.py:2607——update_launch 用例替换 request_window_close，claim 成立。
20. q-045：重读 app.py:1733-1735 并全仓 `git grep remove_advanced_feature 7e2d31c -- local/`——仅命中定义行，claim（零调用点）成立。

## 未尽事项

1. 行为测试「已有/缺」结论基于静态检索与用例正文阅读，未运行测试套件；「缺」以本报告列出的检索词在基线 local/tests 无命中为准。
2. esc 审计只覆盖桌面端（local/ui 除 m/）；手机页（m/app.js）有独立转义实现，本次未核对，属第一轮手机页审计范围。
3. 落点分类是粗分类：文本节点与双引号属性按「紧邻前导字符串/模板字面量」判定，未追踪运行期 DOM 写入路径（innerHTML 与 textContent 的最终归属未逐一验证），结论以 esc 转义集与落点形态的匹配为准。
4. `remove_advanced_feature` 的处置（删除或补调用方）与 esc 落点契约测试的引入，需重构计划拍板，本报告只标记。
5. Api 私有方法（93 个）未逐个归块，只在各块字段/补丁口径里顺带列出被测试改写的私有成员；若重构需要私有方法清点，可扩展 scripts/api_methods.py。
6. 第一轮 ui-states.md 不在基线 7e2d31c 内，其清单条目无法设条目引用，正文以照录方式给出。

## 主执行方复核抽查（2026-11-12，基线 7e2d31c）

随机抽样 10 条（种子 20261112，10.9%），逐条重读基线核对原文与语义：10/10 成立；其中 q-015 的 claim 含「目标行为尚未实现」的推断成分，代码事实（用 new Date() 取手机本地时钟）成立，推断部分按有条件属实记录。明细存 plan/verify/prereq-spot.txt；verify_cites.py 复跑 92 条 0 失败存 plan/verify/prereq.txt；esc_sites.mjs、api_methods.py 复跑输出存 plan/verify/esc-script.txt、api-script.txt。

> 计数勘误（T7）：桌面 api("…") 调用 42→54 处（44 个不同名不变）；PHONE_STATIC 四名→六条路径（q-082 已重写，区间 24-32）；q-015 改标「推测」并补 missing。

> 补记（T7 依 AA3-16）：§2.2 六张「被改写成员」表漏两个真实 Api 字段——_start_order [[q-093]]（开始请求 FIFO 序，app.py:890 起）与 _cloudflare_starting [[q-094]]（隧道启动单飞位，app.py:960 起）；迁移底稿按其消费方法归块（开始/计划 × 手机访问），补丁面清点应含这两处。
