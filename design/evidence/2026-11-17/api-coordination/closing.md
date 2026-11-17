# 关闭标记 `_closing` 与关停顺序

- 口径：行号以开工 HEAD `788b25c` 的 `local/app.py` 为准；读写次数与持锁来自
  `scripts/field_map.py --head 788b25c`（见 `fields.md` 的 `_closing` 一节）。
- 数字：**2 处赋值、28 处读**，读写分布在 9 个功能里（worker 进程、手机访问、更新、活动列表、
  登录恢复、窗口与托盘、组件、计划，加 `__init__`）。

## 一、赋值点

| 位置 | 值 | 持锁 | 说明 |
|---|---|---|---|
| `Api.__init__` 851 | `False` | 无（构造期） | 初值 |
| `Api.shutdown` 3404 | `True` | `Api._lock` | 与「取进程快照」同一临界区：置位与快照不可分 |

只有这两处。没有任何地方把它置回 `False`——`_closing` 一旦为真，这个 `Api` 实例就不再接受新工作，
这与「一个进程只有一次关停」一致。

## 二、读点（按功能）

| 功能 | 读它的方法 | 持锁 | 处数 |
|---|---|---|---|
| 组件 | `download_advanced_feature`、`enable_advanced_feature`、`install_advanced_feature`、`remove_advanced_feature`、`_install_downloaded_component`、`_commit_downloaded_component_group`、`_install_downloaded_ocr`、`_commit_downloaded_ocr_group`、`_install_selected_feature`、`_wait_component_settled` | `Api._lock`、`Api._phone_access_lock`、`Api._credential_lock`（按所在方法定） | 10 方法 / 若干处 |
| 登录恢复 | `check`、`login`、`_do_check`、`_auto_relogin_eligible`、`_relogin_entry_gate`、`_spawn_relay_worker` | `Api._lock` | 6 |
| 窗口与托盘 | `shutdown` 自身（判断是否已有收尾在进行） | `Api._lock` | 1 |
| 计划 | `_start_plan_inner`、`_cancel_busy_reason_locked`(锁外调)、`_run_plan_task`(传 lambda) | `Api._lock`（后者不是） | 3 |
| 手机访问 | `start_phone_access`、`_start_phone_access`、`restore_phone_access` | `Api._lock` | 3 |
| 活动列表 | `list_activities`、`_wait_for_list_clock` | `Api._lock` | 2 |
| worker 进程 | `_run`、`_spawn` | `Api._lock` | 2 |
| 更新 | `_update_is_closing` 2055-2057 | **无锁** | 1 |

### 锁外读的四处（改归属时最容易漏）

| 位置 | 读法 | 为什么在锁外 | 风险 |
|---|---|---|---|
| `Api.__init__` 851 | 赋值 | 构造期无并发 | 无 |
| `Api._update_is_closing` 2057 | `bool(self._closing)` 直接读 | 给 `UpdateService` 当 `is_closing` 端口，服务在自己的锁里调 | 读到的是「某一瞬间」，没有 `_lock` 的 happens-before；实践上 `bool` 读在 CPython 下不会撕裂，但这依赖实现 |
| `Api._cancel_busy_reason_locked` 2393 | 直接读 | 命名带 `_locked`，靠**调用方**持锁的约定 | 约定不在类型里，谁都能在锁外调它 |
| `Api._run_plan_task` 4315 | `is_closing=lambda: self._closing` 传给 `run_plan_task` | plan_service 在自己的 `with lock:` 里调它 | 若将来把 `lock` 参数换成别的锁，这个 lambda 读的就是没保护的值 |

## 三、`shutdown` 的先后（3380-3478）

| 步 | 做什么 | 在锁内还是锁外 | 为什么这个顺序 |
|---|---|---|---|
| 1 | `_stop_tray()` 撤托盘图标 | 锁外 | 先撤图标，免得窗口收完还挂着一个点不出来的图标（3395 注释） |
| 2 | 锁内：首次进入则置 `_closing=True`，并**同锁**取六份快照：`_plan`、`_plan_procs`、`_plan_trees`、`_aux_procs`、`_aux_trees`、`_proc`/`_proc_tree` | `Api._lock` | 关闭屏障：一切 worker 创建/登记也在这把锁里先核 `_closing`，所以快照必然完备（3383-3386 注释） |
| 3 | 若已有收尾在进行：锁外 `_shutdown_done_event.wait()` 后返回 | 锁外 | 后到调用不重复 stop，但要等到真正收完（FB2） |
| 4 | 组件服务 `shutdown()`（两个事务先收，等目录替换提交/回滚完） | 锁外 | 3416-3420：资源根要在主进程退出前释放 |
| 5 | `_auto_relogin.stop()` → `_relay.shutdown()` → `_stop_cloudflare_checked()` → `_phone.shutdown(preserve_devices=True)` | 锁外 | 手机入口先收（有界取消、关 HTTP、撤销会话），再走进程 |
| 6 | `plan.stop()` → 逐棵树 `terminate()` → 没被树收走的按 `_kill_tree(pid)` 兜底 → `aux_trees` 同样处理 → `_proc_tree.terminate()` | 锁外 | 3421-3475；树端口优先，PID 兜底 |
| 7 | `_shutdown_done_event.set()` | 锁外（`finally`） | 3477-3478：提前置位会让后到调用先于真正收尾返回 |

**为什么第 4-6 步都在锁外**：`plan.stop()` 与树终止会回调协调器与任务线程，而那边登记/清理也要
`Api._lock`；在锁内等待会互等（3386-3387 注释）。这条与 `plan_service.run_plan_task` 的
「创建与登记同临界区」是同一套约定的两面。

## 四、容易认错的一个同名

`main()` 里 4699 行有个局部函数 `def _closing() -> bool`，它是 pywebview 窗口 `closing` 事件的处理函数
（返回 `False` 取消关闭），和 `Api._closing` 属性**同名不同物**。搜 `_closing` 时这两者会混在一起，
搬 `_closing` 归属时要连这个函数名一起看，别把它当字段读点（本次清点已排除：它在 `main` 里，不是 `self._closing`）。

## 五、与 2026-11-12 审计的对照

审计（基线 `7e2d31c`）：`_closing` 2 处赋值、30 处读。本次：2 处赋值、28 处读。

实测两个基线的 `self._closing` 出现次数：`7e2d31c` 33 次 → 本次 30 次，少的三处与写法变化如下
（`git show 7e2d31c:local/app.py | grep "self._closing"` 与 `grep local/app.py` 逐条对比）：

| 写法 | 7e2d31c | 本次 | 说明 |
|---|---|---|---|
| `if self._closing:` | 23 | 20 | 少的三处都在更新那一块，随 `check_update`/`update_download` 搬进 `UpdateService` |
| `closing = self._closing`（先取副本再锁外发事件） | 1 | 0 | 原来的 `_publish_update` 里，搬走后由服务自己的 `snapshot()` 取代 |
| `return bool(self._closing)` | 0 | 1 | 新增 `Api._update_is_closing`（2055），变成唯一的对外入口 |

也就是说「一个字段 30 处读」是能收敛的：先给它一个入口函数，读点会跟着少；
但收敛的前提是**读的语义能用一个布尔表达**（这里恰好是「关没关」），
`_is_busy_locked` 这种读四样字段的判断就没这么容易。
