# 拆 Api 前的三道守卫：口径、变异证明与对不上清单

- 基线：开工 HEAD `e126e51`（分支 `refactor/step1`）。三份守卫测试、数据目录探针与本 README
  都是该分支上未入库的工作区文件，与产品代码在同一份源码上验证。
- 本文含 2026-11-23 返修：矩阵夹具隔离数据目录、矩阵补「计划进程在跑」一列（14×10）、
  锁序等级表改六级（发布锁移到协调锁之外）、规则一扩到服务类内部、变异补到 18 条。
- 三道守卫各守一件拆分时最容易悄悄坏的事：
  1. **手机动作 ↔ 真实 Api 签名**（`local/tests/test_phone_action_signatures.py`）——
     手机端按动作名反射调 Api，改个参数名别处测试照样绿，手机端静默变 `internal`。
  2. **锁的等级只升不降**（`local/tests/test_lock_order.py`）——ast 只读源码，六级等级表与四条
     规则见该文件；Api 与各服务类内部都适用。挪错锁的先后不会马上红，只会在并发里死锁。
  3. **谁挡谁矩阵**（`local/tests/test_busy_matrix.py` + `local/tests/fixtures/busy_states.py`）——
     14 行 × 10 列逐格钉住忙碌门禁；摆状态只经夹具一个入口，下一批协调对象落地时只改夹具。

## 口径

- 变异证明**全程不碰工作区**：每条变异在系统临时目录建的副本里做，副本只拷 `local/`
  （排除 `data/`、`config.json`、`_site_build.py`、`bin/` 与字节码），外加仓库根的 `VERSION`
  （`app.py` 导入期必读，缺了会以 `SystemExit` 装载失败——那不算守卫变红，所以副本必须带上）。
  四个副本并行，每条变异只跑对应的那份守卫测试，退出码非 0（首红）即算证明成立，跑完删副本。
- **矩阵夹具隔离数据目录（返修 R1）**：`busy_states.build()` 在构造 Api 前把数据根 patch 到
  临时目录（app 模块的 `DATA_DIR` 与按它派生、构造路径实际会读的路径名字一并指过去），用例
  结束删除。验收用审计钩子探针 `scripts/data_dir_probe.py`：修前一份矩阵对真实数据根产生
  2016 次事件（`open` 252 次 `.advanced.lock`、`os.mkdir` 252 次、`os.listdir` 504、
  `os.scandir` 1008——每个 Api 构造两个组件服务，构造期都按真实根刷新组件状态），修后
  **归零**；矩阵单份耗时从共享盘实测的 63 秒级降到 2-3 秒。修前修后记录见 `data-dir-probe.txt`。
- 三份守卫各连跑 3 次全绿（返修后），输出与耗时见 `green-runs.txt` 第二段（签名 ≈1.7 s、
  锁序 ≈0.5 s、矩阵 ≈2.2-3.1 s）。缺 pywebview 的解释器上，导入 `local/app.py` 的用例按仓库
  既有惯例整批 skip，跳过不冒充通过；纯 ast 的锁序守卫在任何解释器上都真跑。

## 复跑命令（都在仓库根，装齐本仓库依赖的解释器）

```bash
# 三道守卫在干净源码上跑绿
PYTHONIOENCODING=utf-8 python -B -m unittest discover -s local/tests -p test_phone_action_signatures.py
PYTHONIOENCODING=utf-8 python -B -m unittest discover -s local/tests -p test_lock_order.py
PYTHONIOENCODING=utf-8 python -B -m unittest discover -s local/tests -p test_busy_matrix.py

# 数据目录探针：真实数据根上的事件次数（零事件退出码 0）
PYTHONIOENCODING=utf-8 python -B design/evidence/2026-11-17/api-guards/scripts/data_dir_probe.py

# 变异证明（18 条，四个副本并行，任一条存活则退出码 1）
PYTHONIOENCODING=utf-8 python -B design/evidence/2026-11-17/api-guards/scripts/mutate.py
```

## 矩阵：14 行 × 10 列（返修 R2 拆列）

`busy.md` 第二节的「计划在跑」一列把两个不同的状态混在一起：协调器**已发布状态**
（`_plan.published_status()` 为 ready/running）与**计划进程表**（`_plan_procs` 里还有活着的
worker）。返修拆成两列：

- `plan`「计划在跑」：只摆 `_plan.published_status()` 为 running（`_plan_procs` 空）；
- `plan_procs`「计划进程在跑」：`_plan` 为 None、`_plan_procs` 里有一个 poll 返回 None 的替身。

新一列（`plan_procs`）的期望由源码逐行定，出处写在 `test_busy_matrix.py` 的 GRID 注释里
（每行注 `local/app.py` 行号）：读它的判断是 G1（`_is_busy_locked` 4297）、G2
（`_cancel_busy_reason_locked` 2399）与自动重登门（`_relogin_blocked_locked` 1890），所以
login / grab / start_plan / cancel_signup / 组件下载 / 组件安装 / 自动重登七行挡，
check / list / 组件移除 / 开关手机访问 / 手工重登 / 更新放行。140 格实测分布：
block 58、pass 79、merge 3。

**与 busy.md 的对照（返修后无「对不上」格）**：拆列后两列各自与 busy.md 原矩阵一致——
上一批记录的那 1 格差异（自动重登 × 计划在跑：busy.md 写挡、实测放行）的来由正是混列：
busy.md 该格的挡对应的是**计划进程在跑**（`_relogin_blocked_locked` 读 `_plan_procs`，拆列后
`plan_procs` 列确实挡），而**已发布状态**那一半确实不读（`plan` 列放行）。原差异不是矩阵
钉错，是 busy.md 列定义混同；建议规划方在下一批协调对象的清点里沿用拆列口径。
（机制性备注同前：「单场报名 × 关闭中」的拒绝实际来自 `_spawn` 自己的 `_closing` 检查，
busy.md 该格写 G1 只是机制标签。）

## 变异表（18 条 = 上批 14 + 返修 4）

每条变异：改了哪一行、预期哪个用例红、实际哪个用例红。完整机器输出见 `mutations-output.md`
（两份内容一致，这里加了机理说明）。

| 编号 | 守卫 | 改了哪一行 | 预期红 | 实际红 | 结论 |
|---|---|---|---|---|---|
| sig-1 | 签名 | `local/app.py` `start_plan` 签名的 `request_id` 改名 | `test_all_actions_bind_to_real_api_signatures`（start_plan 全键）与 `test_start_plan_dispatch_marks_source_phone` | 同左，两个用例都红 | 红 |
| sig-2 | 签名 | `phone_service.dispatch` 把 `save_retry_policy` 的改写目标改成不存在的方法 | `test_save_retry_policy_rewrites_into_prefs` | 该用例红，另有两个派发子用例因 `not_available` 红 | 红 |
| sig-3 | 签名 | `phone_rules.ACTION_PARAMS` 给 `check` 加一个 Api 不接的键 | `test_tables_cover_the_whole_whitelist` | 同左 | 红 |
| sig-4 | 签名 | `local/app.py` `check` 加一个没有默认值的前置参数 | `test_all_actions_bind_to_real_api_signatures`（check 两种派发都 internal） | 同左（全键与最小键两个子用例） | 红 |
| lock-1 | 锁序 | `local/app.py` `check`：持协调锁的块里加一层凭据锁（4→1 降级） | `test_lock_level_only_rises` | 同左 | 红 |
| lock-2 | 锁序 | `local/app.py` `check`：持协调锁时加 `self._relay.cancel()` | `test_coordination_lock_calls_only_published_status` | 同左 | 红 |
| lock-3 | 锁序 | `login_relay_service.cancel`：锁外的 `self._on_finish()` 挪进 with | `test_service_locks_avoid_injected_ports` | 同左 | 红 |
| lock-4 | 锁序 | `local/app.py` `check`：新加一把没定级的 `self._x_lock` 并在 with 里用 | `test_new_locks_must_be_leveled` | 同左 | 红 |
| lock-5 | 锁序 | `local/app.py` `remove_advanced_feature`：3 处重入之一改成不取锁的 `_stop_phone_access()` | `test_reentry_equals_the_frozen_legacy_list`（重入变 2 条 ≠ 冻结 3 条） | 同左 | 红 |
| matrix-1 | 矩阵 | `local/app.py` `_is_busy_locked`：加 `or self._advanced_busy` | `test_row_start_plan` 的「组件事务在途」子用例 | start_plan×组件 红；同走 G1 的 grab×组件、login×组件 也红（同一扇门喂三行，机理一致） | 红 |
| matrix-2 | 矩阵 | `local/app.py` `_start_phone_access`：门里删掉 `self._advanced_busy` | `test_row_start_phone_access` 的「组件事务在途」子用例 | 同左 | 红 |
| matrix-3 | 矩阵 | `local/app.py` `check`：门里删掉 `_cancelling` | `test_row_check` 的「取消报名在途」子用例 | 同左 | 红 |
| matrix-4 | 矩阵 | `local/app.py` `remove_advanced_feature`：移除门也问 `_is_busy_locked()` | `test_row_component_remove` 的「取消在途 / worker / 计划在跑 / 计划进程在跑」子用例 | 同左，四个子用例都红 | 红 |
| matrix-5 | 矩阵 | `local/app.py` `_spawn_relay_worker`：门里删掉 `_checking` | `test_row_manual_relogin` 的「check 在途」子用例 | 同左 | 红 |
| matrix-6 | 矩阵 | `local/app.py` `_is_busy_locked`：`_plan_procs` 那句换成 `return False` | 走 G1 的五行「计划进程在跑」子用例（start_plan / login / grab / 组件下载 / 组件安装） | 同左，五个子用例都红 | 红 |
| matrix-7 | 矩阵 | `local/app.py` `_relogin_blocked_locked`：`_plan_procs` 那句换成 `return False` | `test_row_auto_relogin` 的「计划进程在跑」子用例 | 同左 | 红 |
| lock-6 | 锁序 | `phone_service.revoke_all`：持 `_event_lock`（等级 6）再拿 `_lock`（等级 5） | `test_service_lock_level_only_rises`（服务类内部 6→5 降级） | 同左 | 红 |
| lock-7 | 锁序 | `signup_plan.cancel_task`：`self._publish` 挪进 `with self._lock`（锁内发布） | `test_publish_stays_outside_the_coordinator_lock`（同时 5→3 降级也该红） | 锁外发布断言红 + `test_service_lock_level_only_rises`（5→3 降级）+ `test_service_locks_avoid_injected_ports`（持服务锁调到 emit 端口）都红，机理一致 | 红 |

全部 18 条变异都让预期的用例变红，无存活。

## 锁序六级表与端口裁决（返修 R4/R5）

等级表与逐条理由的唯一真源是 `local/tests/test_lock_order.py`（六级的简表见
`docs/ARCHITECTURE.md`「锁的先后」）：1 凭据锁、2 手机访问锁、3 **发布锁
`PlanCoordinator._emit_lock`**、4 协调锁、5 各服务锁、6 叶子锁。发布锁在协调锁之外，
依据是 `_publish` 持它调 emit 端口，端口接到 `app.py` `_start_plan_inner` 里的闭包，闭包会取
`Api._lock`（app.py:2968、2983）并经 `Api._emit` 碰服务锁与 `_event_lock`——等级必须低于
它们才不成环。

- **服务类内部（R4）**：规则一扩到服务类后，开工源码上实测**零降级**；同级重入恰好 2 条
  （`PlanCoordinator.cancel_task` / `stop` 持 `_lock` 调 `_set_state_locked`，RLock 重入），
  冻结在 `FROZEN_SERVICE_REENTRY`。
- **有序端口表（R5）**：`FROZEN_PORTS` 原 4 条中的 `signup_plan.py _publish → emit` 挪进新表
  `ORDERED_PORTS`——它是发布锁定级的依据（端口实际接到 app.py:2958 闭包，取 Api._lock(4)、
  relay 服务锁(5)、`_event_lock`(6)，全部高于持有的 `_emit_lock`(3)，顺序成立），不是待修存量。
  `FROZEN_PORTS` 剩 3 条（组件 `snapshot` 的 `_status`、手机 `pair`/`authenticate_or_restore`
  的 `_device_store`），白名单 `LEAF_PORTS` 7 条不变。
- **锁外发布（P2-1）**：新增断言 `test_publish_stays_outside_the_coordinator_lock` 钉住
  协调器的五处 `_publish` 调用（start/cancel_task/stop/_run/_set_state）都不在 `_lock` 的
  with 块内——谁把发布挪进锁内，它和降级断言两道都红（见变异 lock-7）。

## 回归（返修后，装齐依赖的解释器）

三份守卫各 3 次全绿（见 `green-runs.txt` 第二段）。其余回归各一次：
`test_api_patch_targets`（4）、`test_code_shape`（15）、`test_layer_boundaries`（19）、
`test_phone_service`（66）、`test_application_services`（162）全部 OK，无环境类失败。
矩阵 15 个用例（140 个 subTest）在装齐依赖的解释器上真跑约 2.2-3.1 秒；缺依赖的解释器上
整批 skip（140 个 subTest），不冒充通过。
