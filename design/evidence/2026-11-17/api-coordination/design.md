# 拆 Api 前的协调设计稿

- 状态：**proposed**，供指挥会话裁决；每条决定后面括号里写依据（表名 + 条目），备选写代价，推荐写理由。
- 基线：开工 HEAD `788b25c`；引用的行号都来自本次清点（`locks.md`、`fields.md`、`busy.md`、`closing.md`、`demo.md`、`reflection.md`、`tests.md`），不是 2026-11-12 审计的旧行号。
- 本稿不改任何代码；「拆分先后」一节的每一块都要另立计划再动手。

## 一、协调对象：叫什么、放哪层、持有什么

**建议**：`local/application/coordination.py` 里的 `Coordinator`（application 层，与 update_service 同级；它编排的是应用层状态，不碰 domain 规则也不碰 infrastructure）。

**持有**（来源：fields.md 跨功能表 23 个字段里挑「职责就是全局互斥」的那批）：

| 状态 | 现在在 | 为什么归协调 | 依据 |
|---|---|---|---|
| `_closing` | Api | 9 个功能读它是为了同一件事：不再接新工作 | closing.md 读点按功能分布 9 行 |
| `_cancelling` | Api | 被六个判断读（G1/G2/G3/G4/G5/G10），是「取消报名」伸进所有动作的那只手 | busy.md 第三节第 4 条 |
| `_checking`、`_listing` | Api | 「在途」槽位，check/list/计划/组件判定都读 | fields.md：`_checking` 4 写 5 读、`_listing` 3 写 4 读，均跨 3–4 个功能 |
| `_advanced_busy` | Api | 组件单飞位，但登录恢复、手机访问、计划的判定都读 | fields.md `_advanced_busy`：5 个功能、7 写 7 读 |
| `_proc`/`_proc_tree`、`_plan_procs`、`_aux_procs`/`_aux_trees` | Api | G1/G2 与 shutdown 第 2 步的快照都要同时看四张进程表 | busy.md G1/G2；closing.md shutdown 第 2 步 |
| `_shutdown_done_event` | Api | 关停幂等与「后到调用等收完」 | closing.md shutdown 第 3/7 步 |

**不持有**（容易滑进去的）：`_activities`、`_last_check`、`_plan`、`_auto_relogin`、`_relay`、`_phone` 这类业务缓存与服务对象——它们跨功能是因为「别人要看它的快照」，不是因为互斥，应该留在所属服务、由协调对象经端口问（fields.md 各字段一节：`_plan` 的读方法 16 个里大多数是快照渲染，不是判定）。

**对外方法**（对应现有判断，语义不改）：

- `closing()`（替 28 处直读；closing.md 锁外读 4 处的教训：先有入口，读点才收得拢）
- `is_busy()`（= G1 `_is_busy_locked` 的四个来源）
- `cancel_busy_reason()`（= G2）
- `begin(kind)` / `end(kind)`，kind ∈ {checking, listing, cancelling, advanced}——占不上返回拒绝理由，替 G4/G5/G7/G8 里各自手写的 `_x = True` + `finally` 恢复
- `register_proc(...)` / `forget_proc(...)`（worker 创建与登记同临界区，替 `_spawn`/`_run` 的登记；closing.md 第 52–54 行的约定两面）
- `prepare_shutdown()`（锁内置 `_closing` 并取六份快照；`finish_shutdown()` 置 done 事件）

**锁**：一把 `Lock`（不可重入），就是现在的 `Api._lock` 挪过去。理由：a) 现在所有重入需求都集中在 `_phone_access_lock` 的 3 处（locks.md 互锁与重入节），`_lock` 从不需要重入；b) 置位 `_closing` 与取快照必须同临界区（closing.md 第 2 步），拆成两把就要在两把锁之间再找一致性。

**备选与代价**：
- 协调对象只持 `_closing` 加四个槽位，进程表留在 worker 服务——shutdown 快照与 G1 就要「先问 A 再问 B」两段锁，第 2 步的「快照必然完备」保证做不回来（closing.md 3383–3386 注释的意思）。
- 协调对象大而全、把 23 个跨功能字段都收进去——变成第二个 God object，`_activities` 这类缓存的锁语义（谁写谁清）会被稀释；不推荐。

## 二、各服务带走什么、锁的先后规则

**字段分配**（单功能的直接走，fields.md 第一节只有 `_canceled_start_ids`、`_clock_monitor_started` 两个；其余按跨功能表逐个定）：

| 服务 | 带走的字段 | 备注 |
|---|---|---|
| 更新 | `_updates` | 已拆完（服务自持锁与状态），不动 |
| 组件 | `_component_service`、`_ocr_component_service` | `_advanced_busy` 留协调对象；组件服务自己的 RLock 见第三节 |
| 手机访问 | `_phone`、`_cloudflare`、`_cloudflare_starting`、`_cloudflare_exit_notice`、`_phone_channel` | `_phone_channel` 被 7 个方法写（fields.md），换通道的互斥并进协调对象的槽位语义 |
| 登录恢复 | `_auto_relogin`、`_relay`、`_pending_save`、`_once_creds_rejected`、`_relay_creds_source`、`_relay_proc_tree`、`_login_expired_logged`、`_login_seen_valid`、`_login_wait_pending`、`_expiry_pushed`、`_check_again`、`_check_last`、`_check_request_id`、`_auto_relogin_started_at` | check 是登录态检查，归这里；`_checking` 槽位留协调对象 |
| 计划 | `_plan`、`_plan_generation`、`_plan_sources`、`_start_requests`、`_start_order`、`_finished_plan_ids`、`_next_plan_source`、`_last_plan`、`_latest_plan_id` | G1 要问 `_plan.published_status()`，经端口回调，不搬 `_plan` 本身 |
| 活动列表 | `_activities`、`_pc_list_error`、`_pc_list_ok_at`、`_list_request_id`、`_list_last`、`_last_check` | `_listing` 槽位留协调对象 |
| 窗口与托盘 | `_window`、`_tray`、`_window_hidden`、`_window_minimized`、`_close_approved` | |
| 时钟 | `_clock`、`_clock_syncing`、`_clock_monitor_started` | `_clock` 12 处锁外访问（fields.md）是拆它时最先要补测试的地方 |
| worker | （无自有字段，进程表在协调对象） | |

**锁先后规则**（写进守卫测试的一句话）：

> 服务不得在持有自己的锁时调用协调对象；协调对象不得在持锁时调用任何服务。

现在的代码已经满足前半句：locks.md 先后表 14 条边里，做外层的只有 `Api._credential_lock` 与 `Api._phone_access_lock`，服务自己的锁（LoginRelayService、AdvancedComponentService、AutoReloginMonitor、PhoneAccessService）**从未做过外层**去包 `Api._lock`；反方向（持 Api 锁时调服务）大量存在且安全，因为 `_lock` 不可重入、服务锁在最内层。选「服务锁在内」而不是反过来，理由：a) 与现状一致，拆分是搬代码不是改协议；b) 协调对象若调服务，`prepare_shutdown` 的快照就可能在持锁时触发服务回调，重演 closing.md 第 52–54 行专门避开的互等。

**两处现存「持 Api 锁调服务」的高频点要留心**：`Api._lock` 持有期间 `self._is_busy_locked()` 10 次、`self._remember_start()` 9 次（locks.md `Api._lock` 节）——前者挪进协调对象后消失，后者是计划服务的登记回调，拆计划时要么改到锁外调，要么把登记做进协调对象。

## 三、两把 RLock 的归宿与去重入

**`_credential_lock`（12 方法：组件 8、登录恢复 4）**：静态清点**没有发现它的重入点**（locks.md 重入表只列 `_phone_access_lock` 的 3 处）。它今天实际扮演的角色是「改凭据与装/删组件的全局互斥」，且从先后表看它与 `_phone_access_lock` 在组件路径上总是先后一起拿（直接 5 处 + 间接 3 处）。

建议：**随登录恢复服务走、降为 `Lock`**，组件路径的互斥改由协调对象槽位表达。降级前提：跑全量测试 + 用锁图脚本复核重入点仍为 0。备选：把它并进协调对象——代价是登录恢复的凭据写入要经过协调对象，字段表里 `_pending_save`、`_once_creds_rejected` 这些纯登录恢复状态也会被吸进去，边界变糊；不推荐。

**`_phone_access_lock`（9 方法：组件 6、手机访问 3）**：3 处重入全部是「持它调 `self.stop_phone_access()`」（locks.md 重入表：`install_advanced_feature:1664`、`_install_selected_feature:1712`、`remove_advanced_feature:1740`）。

建议：**归手机访问服务，先消重入再降 `Lock`**。消法：装/删组件的入口改成两段式——锁外先调 `stop_phone_access()`，再进锁做安装/移除；这符合 G7 的语义（busy.md：组件事务在途本来就互斥，先停手机访问不影响判定）。重入消零后降 `Lock`，两把 RLock 都退出。备选：保留 RLock 不动——代价是守卫测试写不出「不可重入」的约定，后来者还会在持锁时加调用；既然 3 处都有现成的等价改写，不值得留。

## 四、DEMO 怎么传

事实底座：22 个函数读、31 处（demo.md 读点表）；测试打补丁 27 处、伪模块注入 2 处（demo.md 对照节）；读点按将来归属分布：登录恢复 6、其他 8、计划 2、时钟 3、更新 1、手机访问 1、活动列表 1。

**建议：构造参数**。`main()` 仍负责判定演示模式（`main` 的 3 处读点是启动行为，留在原地），算出后传 `Api(demo=...)`，`Api` 把它作为只读端口传给各服务与 `_terms_gate`（G13 里 DEMO 直接放行那条，busy.md G13）。理由：a) 与已拆的 UpdateService 同一风格（构造注入，`local/app.py:899-908` 现在就是这么给 PhoneAccessService 传端口的）；b) 31 处读点里没有「运行中途翻转」的用法——测试全部是构造前 patch，运行中没人改它，构造成员化不丢语义。

**代价（要写进后续计划的测试预算）**：27 处 `mock.patch.object(local_app, "DEMO", ...)` 要改成 patch Api 实例属性或构造参数（tests.md「其他」一节 `DEMO`×27）；`test_terms_consent.py` 的伪模块注入 2 处改命名空间键。**备选**：留模块级、只收拢成一个 `is_demo()` 函数——改动小，但测试补丁面（27 处）一点不会少，且「模块级可变全局」正是审计点名的问题，等于没修。

## 五、phone_service 的反射改成什么

事实底座：`PhoneAccessService(api=self)` 拿着整个 Api（reflection.md 第一节注入点）；12 个动作反射到 12 个 Api 方法，`dispatch` 里两处改写（`save_retry_policy`→`save_prefs`、`start_plan` 补 `source="phone"`）；**没有守卫盯着「白名单动作 ↔ 真实方法签名」**（reflection.md 守卫现状）。

**建议**：显式动作表由 composition root 构造时注入——`PhoneAccessService(actions={...}, ...)`，每个值是绑定方法（或 lambda），参数校验白名单留在 `domain/phone_rules.py` 不动。这样：

- phone_service 不再持有 Api，只持 12 个 callable（依赖面从「任意属性」缩到「12 个函数」）；
- 两处改写变成表里的 lambda（`"save_retry_policy": lambda prefs: api.save_prefs(...)` 一类），「动作名 ≠ 方法名」从隐式约定变成看得见的代码；
- 拆各服务时改的是表右侧的取值，dispatch 不动。

**配套守卫（先补，属于「拆之前要补的测试」）**：新测试用 `inspect.signature` 比对动作表每个值的参数与 `ACTION_PARAMS` 的键集，多键少键都红——这条现在不存在，Api 方法改签名只会让手机端静默变 `internal`（reflection.md `_call` 的行为）。

**备选**：动作表硬编码在 phone_service 模块里——省一个构造参数，但拆服务时每挪一个方法都要回来改 phone_service，依赖方向反了；不推荐。

## 六、组件、手机访问、登录恢复、worker、计划的拆分先后

| 序 | 块 | 范围 | 前置 | 测试预算（tests.md） |
|---|---|---|---|---|
| 0 | 守卫先行 | ①反射签名守卫（第五节）；②锁先后守卫：静态断言「服务锁不做外层包协调锁」；③busy 矩阵守卫：把 busy.md 的 14×9 矩阵逐格写成判定测试 | 无 | 小（新增，不动存量） |
| 1 | 协调对象 | 第一节的全部状态与方法；Api 持 `Coordinator` 并转发，`_is_busy_locked` 等 6 个判断函数搬进去 | 0②③ | 跨功能 417 处是上限，实际按「字段读写点」逐格改 |
| 2 | 组件 | `_advanced_busy` 的读写改走协调槽位；消 L1 越层（reflection.md 第二节的 11 个用法点：9 个默认端口 + ARTIFACTS + CLOUDFLARED_VERSION，全部改成 app.py 显式传）；`_phone_access_lock` 消重入（第三节） | 1 | 组件 44 处 |
| 3 | 手机访问 | `_phone`/`_cloudflare`/`_phone_channel` 收进服务；`start_phone_access` 的判定改问协调对象（G8） | 1、2（通道互斥依赖组件降级后的锁形） | 手机访问 58 处 |
| 4 | 登录恢复 | `_auto_relogin`、`_relay`、check 家族、`_credential_lock` 降级；`_lock` 上 19 个方法的最重一块 | 1 | 登录恢复 82 处 |
| 5 | 计划 | `_start_requests` 等登记改走协调对象；`run_plan_task` 的 `is_closing` 端口换成协调对象方法（closing.md 锁外读第 4 处正好一起收） | 1 | 计划 128 处 |
| 6 | 活动列表、窗口与托盘、时钟、worker | 收尾：`_activities` 家族、窗口三态、时钟（先补 `_clock` 的 12 处锁外访问测试） | 1 | 28、49、28 处 |

**排序理由**：组件排最前是因为它是唯一「持两把 Api 锁 + 一把自己的 RLock」的块（locks.md `_credential_lock`/`_phone_access_lock` 的功能分布都是组件占大头），把它先降级，后面每块的锁形都更简单；登录恢复排在中后，是因为它 19 个方法持 `_lock`（locks.md 功能分布），依赖协调对象与组件降级都就位才动得了；计划放第五，是因为它的判定（G1/G2）最依赖协调对象，但 `plan_service.run_plan_task` 已经是端口化最好的模块（G14 的 `lock` 参数），风险反而小。

## 七、决定 ↔ 事实对照

| 决定 | 依据 |
|---|---|
| 协调对象持 `_closing` + 四槽位 + 四张进程表 | busy.md G1/G2 读取清单；closing.md shutdown 第 2 步、锁外读 4 处 |
| 协调对象一把不可重入锁 | locks.md 一览（`Api._lock` 96 处 / 64 方法）；重入表空 |
| 锁规则「服务锁在内」 | locks.md 先后表（14 条边全是 Api 锁在外层）；互锁为无 |
| `_credential_lock` 降 Lock、随登录恢复 | locks.md 重入表无它；先后表它与 `_phone_access_lock` 总成对 |
| `_phone_access_lock` 消重入后降 Lock | locks.md 重入表 3 处；busy.md G7 组件事务互斥语义 |
| DEMO 构造参数 | demo.md 读点 22 函数 / 31 处、补丁 27 处；busy.md G13 |
| 反射改显式动作表 + 签名守卫 | reflection.md 第一节表与「守卫现状」 |
| 组件先拆 | locks.md 两把 RLock 的功能分布；reflection.md 第二节 11 个用法点 |
| 测试预算 | tests.md 汇总表（1259 处 / 21 文件，各功能分档） |

## 八、本稿没有回答、要指挥会话拍的

1. `_last_check` 归活动列表还是登录恢复——两边都读（fields.md），语义是「最近一次登录检查的结论」，本稿按「活动列表拿缓存、登录恢复写结论」暂归活动列表，需要确认。
2. `begin(kind)/end(kind)` 的 kind 集合要不要把「更新」也算进去——UpdateService 现在完全自管（G12），并进来会让已拆好的块回卷，本稿倾向不并。
3. 协调对象的方法名与文件名（`coordination.py` / `Coordinator` 只是本稿的建议名）。
