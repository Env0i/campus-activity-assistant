# T5 重构前置清点（盲做）

- **基线提交**：`7e2d31c`。事实放在 `prereq.cites.jsonl`，本文只写 `[[条目id]]`。
- **四项**：①第一轮 `ui-states.md` 末节每条「要补的行为测试」在 `local/tests` 里有没有；②`Api` 公开方法归块，并列出每块的实例字段、锁、测试打补丁的名字；③桌面 `esc` 全部调用点按落点分类并给结论；④经字符串访问的全局与桥接方法名与定义逐个比对。
- **脚本**（都在 `scripts/`，从仓库根复跑）：`api_methods.py`（②）、`esc_sites.mjs`（③）、`string_names.py`（④）。公开方法清单由脚本从基线 `app.py` 的 `ast` 取，不手抄。
- **找测试的办法**：按函数名、选择器名、状态名在 `local/tests` 里搜；搜到名字相近的，只在表里写「名字相近，需读测试体确认」并记为推测，因为本轮没有逐个读测试体；搜不到写「缺」并列出搜过的关键词。

## 一、`ui-states.md` 末节「要补的行为测试」逐条对照

第一轮末节共 7 行（步骤），拆成下面 13 条具体断言。「已有」只用于测试名与断言内容明显对应的；其余写缺或推测。

| 编号 | 要补的断言（出自第一轮） | 现有测试 | 结论 |
|---|---|---|---|
| 1 | 修改中、停止被后端拒绝：不再显示修改中，运行记录不说「已暂停」 | 搜 `S.editing`、`modifyPlan`：只有「修改计划写已暂停运行记录」[[PRE-167]] 和「开始被接纳时清修改中」[[PRE-168]]，都是现状的正向断言，没有停止被拒这一条 | 缺 |
| 2 | 修改中、计划自然结束后点「重新选择未成功的场次」：回到的不是修改中 | 搜 `reselectFailed`：只有「名额已满单列且不重选」一条（与本断言无关） | 缺 |
| 3 | 「放弃修改」提交的是原计划场次，不是当前勾选 | 搜 `btn-edit-restore`、`restartStoppedPlan`：无命中 | 缺 |
| 4 | 窗口重新可见、取消成功后、计划结束后、重新登录成功后四处刷新：不出骨架；失败时列表和勾选不变 | 后台轮的一组（不出骨架 [[PRE-159]]、失败保留列表 [[PRE-158]]、隐藏不刷新回来补刷 [[PRE-160]]）只覆盖「后台标志」这一条路；现状反例「手动刷新失败仍清空列表」[[PRE-157]] 反而固化了四处程序发起刷新的当前行为 | 缺（四处程序发起的刷新没有测试；现有反例会在修复时变红，要同步改） |
| 5 | 手机核对弹层开着时轮询带来新计划状态：弹层内容跟着变 | 搜 `renderReview`：无命中；只有批次的静态内容 [[PRE-171]] | 缺 |
| 6 | 「最近同步」在手机时区与北京时间不同时显示北京时间 | 搜 `最近同步`、`last-sync`：只有两条静态版面用例，不断言时区 | 缺 |
| 7 | 组件「检查中」超过时限出现原因和重试；读状态失败有提示 | 搜 `checking`、`读状态`：无命中（功能本身还没做） | 缺 |
| 8 | 两个组件同时一个在下载、一个在安装：各显示各的 | 两条各自的「安装中显示到刷新返回」[[PRE-165]]、[[PRE-166]]，名字对应单个组件，是否覆盖「同时」需读测试体 | 部分（推测） |
| 9 | 校验结论晚于中继终态到达：胶囊不回亮 | 校验结论为有效时中继重放不回亮 [[PRE-161]]、未知校验不收掉进行中的自动登录 [[PRE-162]]；第一轮说的是「结论为失效且恢复中」的晚到序列，没有对应用例 | 部分 |
| 10 | 验证码页改用浏览器：浏览器登录能开始 | 搜 `btn-rl-browser`：无命中；关对话框相关的两条 [[PRE-163]]、[[PRE-164]] 只管取消的发或不发 | 缺 |
| 11 | 停止成功但结束事件没到：窗口重新可见后「正在停止」能收掉 | 搜 `S.stopping` 的用例都是正向流程；手机侧「回前台按游标补事件」[[PRE-172]] 与桌面无关 | 缺 |
| 12 | 更新：安装程序启动成功后的状态（按用户定的做法） | 现状正向用例：按钮变成关闭本工具 [[PRE-169]]、显示后端文案 [[PRE-170]]；用户还没定做法 | 待定 |
| 13 | 现有样板 `SilentReloginResidualTests`（每条用例一条退出路径） | 该类共 10 条用例，上面第 9 条引用了其中 2 条 | 样板存在 |

**计数**：上表 13 行里，标「缺」的 9 行（1、2、3、4、5、6、7、10、11），「部分」2 行（8、9），「待定」1 行（12），「样板」1 行（13）。

## 二、`Api` 公开方法归块

### 2.1 公开方法清单（脚本数出来的）

`class Api` 共 153 个方法，其中公开（名字不以下划线开头）60 个。五块：更新、组件、手机访问、登录恢复、计划；其余归「跨块」。归块是人工定的：按方法名和它写的字段判断，不确定的写在表后。数量：更新 5，组件 11，手机访问 6，登录恢复 11，计划 7，跨块 20，合计 60，没有未归类的。

| 公开方法 | 归块 | 定义 | 写入的实例字段 | 用到的锁 |
|---|---|---|---|---|
| `clock_snapshot` | 跨块 | [[PRE-001]] | 无 | 无 |
| `sync_clock` | 跨块 | [[PRE-002]] | _clock_syncing | _lock |
| `bootstrap` | 跨块 | [[PRE-003]] | 无 | _lock |
| `help` | 跨块 | [[PRE-004]] | 无 | 无 |
| `download_advanced_feature` | 组件 | [[PRE-005]] | _advanced_busy | _lock、_phone_access_lock |
| `cancel_advanced_feature_download` | 组件 | [[PRE-006]] | 无 | 无 |
| `enable_advanced_feature` | 组件 | [[PRE-007]] | 无 | _credential_lock、_lock |
| `advanced_component_location` | 组件 | [[PRE-008]] | 无 | 无 |
| `open_advanced_component_dir` | 组件 | [[PRE-009]] | 无 | 无 |
| `advanced_features_state` | 组件 | [[PRE-010]] | 无 | 无 |
| `inspect_advanced_component` | 组件 | [[PRE-011]] | 无 | 无 |
| `pick_advanced_component` | 组件 | [[PRE-012]] | 无 | 无 |
| `install_advanced_feature` | 组件 | [[PRE-013]] | _advanced_busy | _credential_lock、_lock、_phone_access_lock |
| `remove_advanced_feature` | 组件 | [[PRE-014]] | _advanced_busy、_component_service（容器内改） | _credential_lock、_lock、_phone_access_lock |
| `save_relogin_credentials` | 登录恢复 | [[PRE-015]] | _once_creds_rejected | _credential_lock、_lock |
| `clear_relogin_credentials` | 登录恢复 | [[PRE-016]] | _once_creds_rejected | _credential_lock、_lock |
| `front_ready` | 跨块 | [[PRE-017]] | 无 | 无 |
| `check_update` | 更新 | [[PRE-018]] | _update_request_id、_update_staging_path、_updating | _lock |
| `update_download` | 更新 | [[PRE-019]] | _update_cancelled、_update_request_id、_updating | _lock |
| `update_cancel` | 更新 | [[PRE-020]] | _update_cancelled | _lock |
| `update_launch` | 更新 | [[PRE-021]] | 无 | _lock |
| `check` | 跨块 | [[PRE-022]] | _check_again、_check_request_id、_checking | _lock |
| `list_activities` | 跨块 | [[PRE-023]] | _list_request_id、_listing | _lock |
| `cancel_signup` | 跨块 | [[PRE-024]] | _cancelling | _lock |
| `login` | 登录恢复 | [[PRE-025]] | 无 | _lock |
| `grab` | 计划 | [[PRE-026]] | 无 | 无 |
| `start_request_state` | 计划 | [[PRE-027]] | 无 | _lock |
| `cancel_start_request` | 计划 | [[PRE-028]] | __dict__（容器内改） | _lock |
| `start_plan` | 计划 | [[PRE-029]] | _next_plan_source | _lock |
| `cancel_task` | 计划 | [[PRE-030]] | 无 | _lock |
| `stop_plan` | 计划 | [[PRE-031]] | 无 | _lock |
| `plan_active_for_close` | 计划 | [[PRE-032]] | 无 | 无 |
| `ask_window_close` | 跨块 | [[PRE-033]] | 无 | 无 |
| `request_window_close` | 跨块 | [[PRE-034]] | _close_approved、_window_minimized | 无 |
| `hide_window` | 跨块 | [[PRE-035]] | _window_hidden | 无 |
| `show_window` | 跨块 | [[PRE-036]] | _window_hidden、_window_minimized | 无 |
| `window_visibility` | 跨块 | [[PRE-037]] | 无 | _lock |
| `shutdown` | 跨块 | [[PRE-038]] | _closing、_phone_channel | _lock |
| `stop` | 跨块 | [[PRE-039]] | _proc、_proc_tree、_relay_proc_tree | _lock |
| `phone_access_state` | 手机访问 | [[PRE-040]] | 无 | 无 |
| `start_phone_access` | 手机访问 | [[PRE-041]] | 无 | _phone_access_lock |
| `set_phone_access_preferences` | 手机访问 | [[PRE-042]] | 无 | 无 |
| `restore_phone_access` | 手机访问 | [[PRE-043]] | 无 | _lock |
| `schedule_phone_restore` | 手机访问 | [[PRE-044]] | 无 | 无 |
| `schedule_component_auto_update` | 组件 | [[PRE-045]] | 无 | 无 |
| `stop_phone_access` | 手机访问 | [[PRE-046]] | _cloudflare_exit_notice | _phone_access_lock |
| `prepare_phone_relogin` | 登录恢复 | [[PRE-047]] | _once_creds_rejected、_pending_save、_relay_creds_source | _lock |
| `relogin_begin` | 登录恢复 | [[PRE-048]] | 无 | 无 |
| `relogin_submit` | 登录恢复 | [[PRE-049]] | 无 | 无 |
| `relogin_cancel` | 登录恢复 | [[PRE-050]] | 无 | 无 |
| `relogin_auto_once` | 登录恢复 | [[PRE-051]] | 无 | 无 |
| `phone_relogin_begin` | 登录恢复 | [[PRE-052]] | 无 | 无 |
| `phone_relogin_submit` | 登录恢复 | [[PRE-053]] | 无 | 无 |
| `phone_relogin_cancel` | 登录恢复 | [[PRE-054]] | 无 | 无 |
| `open_data` | 跨块 | [[PRE-055]] | 无 | 无 |
| `open_latest_release` | 更新 | [[PRE-056]] | 无 | 无 |
| `get_license_text` | 跨块 | [[PRE-057]] | 无 | 无 |
| `save_prefs` | 跨块 | [[PRE-058]] | 无 | 无 |
| `accept_terms` | 跨块 | [[PRE-059]] | 无 | 无 |
| `withdraw_terms` | 跨块 | [[PRE-060]] | 无 | 无 |

归块时的几处判断：
- `login`（打开浏览器登录）和 `check`（校验登录态）：`login` 归登录恢复；`check` 同时被自动登录调度和界面刷新用，归跨块。
- `cancel_signup`（取消一场已报名）、`list_activities`：学校动作，不属于五块，归跨块。
- `stop`、`shutdown`、窗口三个方法：生命周期，跨块。
- `save_prefs`、`accept_terms`、`withdraw_terms`：偏好与条款，跨块。
- `grab`：旧的单场报名入口，与计划同一路径的 worker，归计划。

### 2.2 每块的实例字段、锁

字段列表是我按字段名挑出的每块种子字段（不含只被读的）；「写入它的方法数」由脚本数，含下划线方法。锁的数字是 `with self.<锁>` 出现在多少个方法里（脚本数）。全类里 `_lock` 用在 66 个方法里，`_credential_lock` 12 个，`_phone_access_lock` 9 个。

**更新**

| 实例字段 | 写入它的方法数（含下划线方法，脚本数） | 其中公开方法 | 第一处赋值 |
|---|---|---|---|
| `_updating` | 4 | check_update、update_download | [[PRE-061]] |
| `_update_request_id` | 3 | check_update、update_download | [[PRE-062]] |
| `_update_cancelled` | 3 | update_download、update_cancel | [[PRE-063]] |
| `_update_result` | 2 | 无 | [[PRE-064]] |
| `_update_installer` | 1 | 无 | （不是 self.字段 = 形式） |
| `_update_installer_path` | 1 | 无 | [[PRE-065]] |
| `_update_staging_path` | 2 | check_update | [[PRE-066]] |

公开方法用到的锁：`_lock`（4 个公开方法）。

**组件**

| 实例字段 | 写入它的方法数（含下划线方法，脚本数） | 其中公开方法 | 第一处赋值 |
|---|---|---|---|
| `_advanced_busy` | 5 | download_advanced_feature、install_advanced_feature、remove_advanced_feature | [[PRE-067]] |
| `_component_service` | 2 | remove_advanced_feature | [[PRE-068]] |
| `_ocr_component_service` | 1 | 无 | [[PRE-069]] |

公开方法用到的锁：`_credential_lock`（3 个公开方法）、`_lock`（4 个公开方法）、`_phone_access_lock`（3 个公开方法）。

**手机访问**

| 实例字段 | 写入它的方法数（含下划线方法，脚本数） | 其中公开方法 | 第一处赋值 |
|---|---|---|---|
| `_phone_channel` | 7 | shutdown | [[PRE-070]] |
| `_cloudflare` | 1 | 无 | [[PRE-071]] |
| `_cloudflare_exit_notice` | 4 | stop_phone_access | [[PRE-072]] |
| `_cloudflare_starting` | 2 | 无 | [[PRE-073]] |
| `_phone` | 1 | 无 | [[PRE-074]] |

公开方法用到的锁：`_lock`（1 个公开方法）、`_phone_access_lock`（2 个公开方法）。

**登录恢复**

| 实例字段 | 写入它的方法数（含下划线方法，脚本数） | 其中公开方法 | 第一处赋值 |
|---|---|---|---|
| `_pending_save` | 6 | prepare_phone_relogin | [[PRE-075]] |
| `_once_creds_rejected` | 5 | save_relogin_credentials、clear_relogin_credentials、prepare_phone_relogin | [[PRE-076]] |
| `_relay_creds_source` | 3 | prepare_phone_relogin | [[PRE-077]] |
| `_relay` | 1 | 无 | [[PRE-078]] |
| `_relay_proc_tree` | 4 | stop | [[PRE-079]] |
| `_auto_relogin` | 1 | 无 | [[PRE-080]] |
| `_auto_relogin_started_at` | 2 | 无 | [[PRE-081]] |

公开方法用到的锁：`_credential_lock`（2 个公开方法）、`_lock`（4 个公开方法）。

**计划**

| 实例字段 | 写入它的方法数（含下划线方法，脚本数） | 其中公开方法 | 第一处赋值 |
|---|---|---|---|
| `_plan` | 2 | 无 | [[PRE-082]] |
| `_plan_generation` | 2 | 无 | [[PRE-083]] |
| `_plan_procs` | 1 | 无 | （不是 self.字段 = 形式） |
| `_plan_trees` | 1 | 无 | （不是 self.字段 = 形式） |
| `_last_plan` | 2 | 无 | [[PRE-084]] |
| `_start_requests` | 2 | 无 | （不是 self.字段 = 形式） |
| `_latest_plan_id` | 2 | 无 | [[PRE-085]] |
| `_finished_plan_ids` | 3 | 无 | （不是 self.字段 = 形式） |
| `_next_plan_source` | 3 | start_plan | [[PRE-086]] |

公开方法用到的锁：`_lock`（5 个公开方法）。

### 2.3 测试打补丁的名字与被改写的成员

统计口径见 `api_methods.py --tests` 文件头：模块级名字 = `patch.object(app, "X")`、`patch("app.X")`、`setattr(app, "X")`、`app.X = …`；Api 成员 = 对叫 `api` 或以 `api` 结尾的变量的 `patch.object`、`setattr`、`api._X = …`。**与第一轮的数字（42 个名字、66 个成员）对不上**：按这个口径脚本数得模块级名字 37 个、Api 成员 34 个。第一轮的口径细则没有保留，本文不判断谁对，只给出本口径的完整清单。其中 `TimeoutError`、`sync_playwright` 是变量名恰好以 `api` 结尾造成的误判，不是 Api 成员。

| 被补丁的 app 模块级名字 | 归块 | 涉及的测试文件数 | 一处位置 |
|---|---|---|---|
| `Api` | 跨块 | 1 | [[PRE-087]] |
| `BusinessClock` | 跨块 | 1 | [[PRE-088]] |
| `CREDENTIAL_FILE` | 登录恢复 | 1 | [[PRE-089]] |
| `DATA_DIR` | 跨块 | 2 | [[PRE-090]] |
| `DEMO` | 跨块 | 6 | [[PRE-091]] |
| `DEVICE_FILE` | 手机访问 | 1 | [[PRE-092]] |
| `GRAB` | 跨块 | 1 | [[PRE-093]] |
| `LOG_FILE` | 跨块 | 1 | [[PRE-094]] |
| `PREFS` | 跨块 | 8 | [[PRE-095]] |
| `PlanCoordinator` | 计划 | 2 | [[PRE-096]] |
| `SESSION_FILE` | 登录恢复 | 2 | [[PRE-097]] |
| `SUPERVISE_GRACE_S` | 计划 | 2 | [[PRE-098]] |
| `_CREDENTIAL_STORE_OK` | 登录恢复 | 1 | [[PRE-099]] |
| `_PREFS_SAVE_TIMEOUT_S` | 跨块 | 1 | [[PRE-100]] |
| `_credential_store` | 登录恢复 | 1 | [[PRE-101]] |
| `_kill_tree` | 跨块 | 1 | [[PRE-102]] |
| `_prefs_transaction` | 跨块 | 1 | [[PRE-103]] |
| `_screen_size` | 跨块 | 1 | [[PRE-104]] |
| `check_latest_release` | 更新 | 1 | [[PRE-105]] |
| `configure_time_source` | 跨块 | 1 | [[PRE-106]] |
| `defer_close_action` | 跨块 | 1 | （脚本只给出文件名，没有找到直接改写的那一行） |
| `ensure_data_dir` | 跨块 | 2 | [[PRE-107]] |
| `get_lifecycle` | 跨块 | 3 | [[PRE-108]] |
| `load_prefs` | 跨块 | 2 | [[PRE-109]] |
| `login_state` | 登录恢复 | 2 | [[PRE-110]] |
| `migration_record` | 跨块 | 1 | [[PRE-111]] |
| `phone_log` | 手机访问 | 1 | [[PRE-112]] |
| `resolve_update_launcher_path` | 更新 | 2 | [[PRE-113]] |
| `save_session_timing_anchor` | 登录恢复 | 1 | [[PRE-114]] |
| `spawn_owned` | 跨块 | 1 | [[PRE-115]] |
| `spawn_owned_worker` | 跨块 | 1 | [[PRE-116]] |
| `update_prefs` | 跨块 | 1 | [[PRE-117]] |
| `update_version_paths` | 更新 | 2 | [[PRE-118]] |
| `validate_plan` | 计划 | 1 | [[PRE-119]] |
| `version_switch_available` | 更新 | 3 | [[PRE-120]] |
| `worker_command` | 跨块 | 5 | [[PRE-121]] |
| `worker_problem` | 跨块 | 2 | [[PRE-122]] |

| 被测试改写的 Api 成员 | 归块 | 涉及的测试文件数 | 一处位置 |
|---|---|---|---|
| `TimeoutError` | (脚本误判，不是 Api 成员) | 2 | [[PRE-123]] |
| `_activities` | 跨块 | 6 | [[PRE-124]] |
| `_advanced_busy` | 组件 | 1 | [[PRE-125]] |
| `_auto_relogin_paused` | 登录恢复 | 1 | [[PRE-126]] |
| `_aux_procs` | 跨块 | 1 | [[PRE-127]] |
| `_aux_trees` | 跨块 | 1 | [[PRE-128]] |
| `_checking` | 跨块 | 2 | [[PRE-129]] |
| `_clock_now` | 跨块 | 1 | [[PRE-130]] |
| `_clock_ready` | 跨块 | 1 | [[PRE-131]] |
| `_close_approved` | 跨块 | 1 | [[PRE-132]] |
| `_closing` | 跨块 | 1 | [[PRE-133]] |
| `_emit` | 跨块 | 8 | [[PRE-134]] |
| `_last_check` | 跨块 | 4 | [[PRE-135]] |
| `_once_credentials_staged` | 登录恢复 | 1 | [[PRE-136]] |
| `_plan` | 计划 | 3 | [[PRE-137]] |
| `_plan_procs` | 计划 | 1 | [[PRE-138]] |
| `_proc` | 跨块 | 2 | [[PRE-139]] |
| `_push_login_expired` | 登录恢复 | 1 | [[PRE-140]] |
| `_relogin_blocked_locked` | 登录恢复 | 1 | [[PRE-141]] |
| `_run` | 跨块 | 2 | [[PRE-142]] |
| `_silent_relogin_ready` | 登录恢复 | 1 | [[PRE-143]] |
| `_start_plan_inner` | 计划 | 1 | [[PRE-144]] |
| `_terms_gate` | 跨块 | 2 | [[PRE-145]] |
| `_update_installer` | 更新 | 1 | [[PRE-146]] |
| `_update_result` | 更新 | 2 | [[PRE-147]] |
| `_update_staging_path` | 更新 | 2 | [[PRE-148]] |
| `_window` | 跨块 | 1 | [[PRE-149]] |
| `_window_hidden` | 跨块 | 1 | [[PRE-150]] |
| `_window_minimized` | 跨块 | 1 | [[PRE-151]] |
| `accept_terms` | 跨块 | 1 | [[PRE-152]] |
| `plan_active_for_close` | 计划 | 1 | [[PRE-153]] |
| `request_window_close` | 跨块 | 1 | [[PRE-154]] |
| `sync_playwright` | (脚本误判，不是 Api 成员) | 2 | [[PRE-155]] |
| `withdraw_terms` | 跨块 | 1 | [[PRE-156]] |

归块只是名字推断：模块级名字里 37 个中没有归到五块的都标「跨块」。拆 `Api` 时，凡是被测试补丁的模块级名字（不论归哪块）都必须继续留在 `app.py` 的模块级，否则按名字打补丁会悄悄落空。

## 三、桌面 `esc` 全部调用点与注入风险

- **清点**（`esc_sites.mjs`）：桌面前端 39 个脚本，`esc(` 调用点共 115 处，分布在 11 个文件，与第一轮的数字一致。`esc` 本身只转义 `&`、`<`、`>`、`"` 四个字符（[[PRE-901]]），不转义单引号。
- **落点分类**（脚本启发式，再人工确认）：文本节点 83，双引号属性 22，其他 8（人工确认后全是文本节点），标签内其他 2（`list.js` 里的两处，人工看过：都是双引号属性值内的拼接，一处 `data-id`，一处 `aria-label`），**单引号属性 0，事件处理器字符串 0，URL 0，无引号属性 0**。
- **人工确认的代表点**：双引号属性：奖励提示的 `title` [[PRE-902]]、[[PRE-910]]，行的 `data-id` 与 `aria-label` [[PRE-903]]，计划票据的 `title` [[PRE-904]]；文本节点：[[PRE-906]] 的结果最终落在 [[PRE-905]]（文本），[[PRE-907]]、[[PRE-908]]、[[PRE-909]]。
- **结论**：目前没有实际注入风险。`esc` 把 `"` 转成 `&quot;`，而全部 22 个属性落点都是双引号包裹的；没有任何落点是单引号属性、事件处理器字符串或 URL。**补充轮曾把 R10「`esc` 不转义单引号」判成已确认的注入风险，这个判断读代码得不到**。
- **脆弱点（判断，不是缺陷）**：`esc` 的安全依赖「所有属性都用双引号」这条约定，没有测试守着；以后有人写单引号属性、或把 `esc` 的结果放进 `href` 或事件处理器，就会出问题。建议在 `esc` 旁加一条测试：扫描桌面脚本，断言 `esc(` 的结果不落在单引号属性、事件处理器或 URL 里；或让 `esc` 同时转义 `'`。
- **缺席结论的依据**：「单引号属性为 0」是缺席结论，靠脚本分类和全文搜索 `='` 一类写法得到，脚本对跨语句拼接可能漏判，见 [[PRE-911]]（推测）。桌面一共有 43 处 `innerHTML =` 赋值，本项只查了经过 `esc` 的 115 个点，没有检查「没有经过 `esc` 的拼接」是否带用户数据，那是另一项检查。

## 四、经字符串访问的全局与桥接方法名

`string_names.py` 的输出（从仓库根复跑）：

1. **桌面桥接方法名**：前端 `api("名字")` 的字面量共 44 个，全部是 `Api` 的公开方法，没有不存在的名字（桥接入口 [[PRE-930]]、[[PRE-931]]：名字不存在时前端得到「本机程序不支持」的拒绝）。`api(name, …)` 第一个实参不是字面量的只有桥接定义这一处。公开方法里桌面前端静态看不到引用的有 16 个：`advanced_features_state`、`cancel_start_request`、`grab`、`help`、`hide_window`、`phone_relogin_begin`、`phone_relogin_cancel`、`phone_relogin_submit`、`plan_active_for_close`、`remove_advanced_feature`、`restore_phone_access`、`schedule_component_auto_update`、`schedule_phone_restore`、`show_window`、`shutdown`、`stop`。其中一部分被手机白名单或窗口回调使用（见第 3 条），`advanced_features_state`、`remove_advanced_feature`、`grab`、`help` 在前端和白名单里都看不到调用方，**是否还有别的调用方，没有逐个查，记推测**（缺的一环：全仓搜索它们的调用点）。
2. **后端推给前端的事件**：后端 `_emit` 的字面量事件名 10 个，经 `window.onBackend.<kind>(…)` 拼出调用（[[PRE-922]]）；前端 `window.onBackend` 有 12 个键（[[PRE-921]]）。多出的 `plan`、`task` 来自 `_emit(kind, …)` 这种 kind 是变量的调用（[[PRE-923]]，在计划事件转发里）。后端有而前端没有的：无。拆 `Api` 时，这 12 个名字是前后端之间的字符串契约。
3. **手机动作白名单**：`ACTION_PARAMS` 共 12 个动作（[[PRE-924]]）。11 个与 `Api` 方法同名，直接 `getattr` 反射调用（[[PRE-927]]）；`save_retry_policy` 在 `Api` 里没有同名方法，`dispatch` 特判成调用 `save_prefs`（[[PRE-925]]、[[PRE-929]]），所以**不是死路径**；`start_plan` 特判补 `source="phone"`（[[PRE-926]]），`Api.start_plan` 的签名接受 `source`（[[PRE-928]]）。拆 `Api` 时，这 11 个同名方法不能改名或搬出，否则 `getattr` 返回空，动作变成 `not_available`。另：白名单里 `phone_relogin_*` 三项上方的注释仍写「白名单先占位，未实现时明确报错」（[[PRE-932]]），但这三个方法在 `Api` 里已有实现（[[PRE-933]]），注释已过时，拆 `Api` 时容易被误读。
4. **`window[…]` 形式的全局访问**：桌面与手机页全文无命中。


