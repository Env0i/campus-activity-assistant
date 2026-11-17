# 「现在能不能做某件事」的判断

- 口径：逐个函数读源码整理，行号以开工 HEAD `788b25c` 的 `local/app.py` 为准；锁的归属来自
  `scripts/lock_graph.py --head 788b25c`（见 `locks.md`），字段读写次数来自 `scripts/field_map.py`（见 `fields.md`）。
- 「持锁」列写的是**调用方必须已经持有的锁**或**函数自己拿的锁**；写「无」表示判断本身在锁外进行。
- 判断编号 G1–G14 在下面的「谁挡谁」矩阵里直接引用。

## 一、全部判断

| 编号 | 判断 | 位置 | 读了什么 | 持锁 | 谁在调 |
|---|---|---|---|---|---|
| G1 | `_is_busy_locked`（忙碌） | `Api._is_busy_locked` 4287-4297 | `_cancelling`、`_proc.poll()`、`_plan.published_status()`、`_plan_procs` 的 poll | 调用方持 `_lock` | `_is_busy` 4299、`_start_plan_inner` 2884/3057、`_spawn` 4391、`_bootstrap_plan_snapshot` 1229/1238/1240、`download_advanced_feature` 1435、`enable_advanced_feature` 1656、`_phone_raw_state` 3518 |
| G2 | `_cancel_busy_reason_locked`（取消能不能开始） | 2391-2405 | 依次 `_closing`、`_cancelling`、`_plan.published_status()`、`_plan_procs`、`_proc`、`_checking`/`_listing`/`_advanced_busy` | 调用方持 `_lock` | `cancel_signup` 2431 附近 |
| G3 | 自动重登的两个门 | `_auto_relogin_eligible` 1849-1856、`_relogin_blocked_locked` 1880-1890 | 前者：`_closing`/`_advanced_busy`/`_checking`/`_listing`/`_cancelling`/`_relogin_blocked_locked`，再锁外问 `_silent_relogin_ready()`；后者：`_login_wait_pending`/`_proc`/`_plan_procs` | 前者前半段持 `_lock`，后半段锁外；后者调用方持 `_lock` | `AutoReloginMonitor(eligible=...)` 构造于 `__init__` 973 附近 |
| G4 | `check` 自己的门 | `check` 2110-2140 | 条款门禁（G13）、`_closing`、`_cancelling`、`_checking`（在途则合并并置 `_check_again`） | `_lock`（条款门禁在锁外） | 前端、手机动作 `check` |
| G5 | `list_activities` 自己的门 | 2142-2171 | 条款门禁、`_closing`、`_cancelling`、`_listing` | `_lock` | 前端、手机动作 `list_activities` |
| G6 | 开始计划的全部前置 | `_start_plan_inner` 2862/2867/3052/3057/2878-2895 | `_clock_ready()`（两次：入参后与最终接纳前）、`_closing`、`_is_busy_locked`（G1）、`worker_problem()`、`_checking`、`_last_check["result"]`（只认 `valid`）、`_start_requests` 的 `canceled` | `_lock` | `start_plan` |
| G7 | 组件事务（下载/安装/移除） | 1435-1437、1656-1658、1735-1737 | `_closing`、`_advanced_busy`；下载与安装还看 `_is_busy_locked`（G1），**移除只看前两个** | 下载：外层 `_phone_access_lock` + `_lock`；安装：`_lock`；移除：外层 `_credential_lock` + `_phone_access_lock` + `_lock` | `download_advanced_feature`、`enable_advanced_feature`/`install_advanced_feature`、`remove_advanced_feature` |
| G8 | 开手机访问 | `start_phone_access` 3688-3697 | `_closing`、`_advanced_busy`；`_phone.is_running()` 与 `_phone_channel`（换通道要先关）；`_cloudflare_starting` | 前两项在 `_lock` 内，后两项锁外 | 前端、手机动作、`restore_phone_access` |
| G9 | 重登入口 | `_relogin_entry_gate` 3973-3984 | DEMO、条款（G13）、`_closing`，再 `_relogin_late_answer()`（100 秒窗口） | `_lock`（只包 `_closing`） | `relogin_begin`/`relogin_submit`/`phone_relogin_*` 4020/4055/4076 |
| G10 | 中继 worker 的起进程门 | `_spawn_relay_worker` 4118-4135 | `worker_problem()`、`_closing`、`_proc`、`_checking`、`_listing`、`_cancelling`；**不看 `_plan`**（注释：计划在跑时能不能登录由调用方先判） | `_lock`（创建与登记同临界区） | `LoginRelayService(spawn=...)` |
| G11 | 登录入口 | `login` 2622-2636 | DEMO、`_closing`、`_plan.published_status()`，条款（G13） | `_lock`（条款门禁在锁外） | 前端、手机动作 |
| G12 | 更新单飞 | `UpdateService.start_check`/`start_download`（`local/application/update_service.py`） | 自己的 `_updating`/`_update_request_id`；关闭看 `is_closing()` → `Api._update_is_closing` 2055 | `UpdateService._lock` | `check_update`/`update_download` 转发 |
| G13 | 条款门禁 | `_terms_gate` 1124-1141 | `load_prefs()` 的 `terms_version`/`terms_accepted_at`；DEMO 直接放行 | 无（读文件，不持锁） | `check`、`list_activities`、`login`、`grab`、`start_plan`、`cancel_signup`、`relogin_*`、`bootstrap.terms_ok` |
| G14 | 计划里起 worker 的关闭门 | `local/application/plan_service.py` 117-124 | `is_closing()`（`Api._run_plan_task` 4315 传的是 `lambda: self._closing`） | 参数 `lock` = `Api._lock` | `PlanCoordinator` 的 runner |

## 二、谁挡谁

行是「要做的事」，列是「正在进行的事」。格子写挡住它的判断编号；`—` 是不挡（读过源码确认），
`合并` 是不拒绝而是合并成一次在途。

| 要做的事 \ 正在进行 | 关闭中 | 取消报名在途 | check 在途 | list 在途 | 单 worker 在跑 | 计划在跑 | 组件事务在途 | 隧道启动中 | 更新在途 |
|---|---|---|---|---|---|---|---|---|---|
| 检查登录 `check` | G4 | G4 | G4（合并） | — | — | — | — | — | — |
| 拉活动列表 `list_activities` | G5 | G5 | — | G5（合并） | — | — | — | — | — |
| 登录 `login` | G11 | G1 | — | — | G1 | G11 | — | — | — |
| 单场报名 `grab` | G1 | G1 | — | — | G1 | G1 | — | — | — |
| 开始计划 `start_plan` | G6 | G1 | G6 | — | G1 | G1 | — | — | — |
| 取消报名 `cancel_signup` | G2 | G2 | G2 | G2 | G2 | G2 | G2 | — | — |
| 组件下载 | G7 | G1 | — | — | G1 | G1 | G7 | — | — |
| 组件安装 | G7 | G1 | — | — | G1 | G1 | G7 | — | — |
| 组件移除 | G7 | — | — | — | — | — | G7 | — | — |
| 开启手机访问 | G8 | — | — | — | — | — | G8 | G8 | — |
| 停止手机访问 | — | — | — | — | — | — | — | — | — |
| 自动重登 | G3 | G3 | G3 | G3 | G3 | G3（`login_wait` 时放行） | G3 | — | — |
| 手工／手机重登 | G9、G10 | G10 | G10 | G10 | G10 | —（设计如此） | — | — | — |
| 更新检查与下载 | G12 | — | — | — | — | — | — | — | G12（同一次只跑一个） |

## 三、从矩阵里读出来的事（判断，不是数出来的）

1. **`_advanced_busy` 不在 `_is_busy_locked` 里**（4287-4297 只读 `_cancelling`/`_proc`/`_plan`/`_plan_procs`）。
   结果是：组件事务进行中还能开始计划（`_start_plan_inner` 只问 G1 + G6），也能单场报名。
   反向是挡的：组件下载/安装会问 G1。所以「组件 ↔ 报名」这条边是单向的。
2. **组件移除只问 `_closing` 与 `_advanced_busy`**（1735），不看 `_is_busy_locked`：
   计划在跑、单 worker 在跑时都能删组件。与下载/安装不对称。
3. **`check`/`list` 不看 G1**：单 worker 在跑、计划在跑时都能刷登录态与列表（只挡关闭与取消）。
   这对「计划跑着、界面还想刷新」是必要的，但也意味着这两个动作与报名共用 worker 之外的资源没有互斥。
4. **`_cancelling` 被六个判断读**（G1/G2/G3/G4/G5/G10），它是「取消报名」伸进所有别的动作的那只手；
   它自己只在一处置真（2434）、一处置假（2439，`finally`）。
5. **计划在跑对 `_spawn_relay_worker` 不算忙**（4118-4124 的注释写明），手工重登与计划可以并行；
   自动重登则要看 `_relogin_blocked_locked`（1880）：报了 `login_wait` 才放行。
6. **条款门禁是唯一一处「与锁无关」的全局前置**（1124，读文件），除更新与关停外每个学校动作都过它；
   它同时是 `bootstrap.terms_ok` 的来源（3565）。
7. **同一件事有两次检查的地方**：开始计划（2884 首检、3057 最终接纳前重检）、自动重登（1849 与 1880 两层）、
   手机访问（3688 与 `_start_phone_access` 里再核）。重检点都是「锁内最后一道」，说明作者已经在处理
   「检查与执行之间的窗口」；拆服务时这些重检点不能合并成一次。
