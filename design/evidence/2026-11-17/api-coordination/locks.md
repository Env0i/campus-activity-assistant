# 锁图

- 生成脚本：`scripts/lock_graph.py`（ast 只读源码，不 import 产品代码）
- 命令：`python -B design/evidence/<日期>/api-coordination/scripts/lock_graph.py --head 788b25c`
- 基线：`788b25c`；范围：local/app.py 与 local/application 下 9 个模块；锁 12 把
- 「获取处」是 `with` 出现的次数而非执行次数；间接只追一层；服务自己线程里拿自己锁的路径（HTTP 处理线程等）不经过 Api，只按静态源码计。
- 认不出的 `with`：0 处

## 一览

| 锁 | 种类 | 声明 | 获取处 | 持有方法数 | 功能分布 |
|---|---|---|---|---|---|
| `Api._lock` | Lock（不可重入） | `local/app.py:842` | 96 | 64 | 组件 11、手机访问 3、登录恢复 19、计划 13、活动列表 5、窗口与托盘 3、时钟 2、worker 进程 2、其他 6 |
| `LoginRelayService._lock` | Lock（不可重入） | `local/application/login_relay_service.py:129` | 20 | 14 | 登录恢复 14 |
| `Api._credential_lock` | RLock（可重入） | `local/app.py:843` | 12 | 12 | 组件 8、登录恢复 4 |
| `PhoneAccessService._lock` | Lock（不可重入） | `local/application/phone_service.py:41` | 13 | 11 | 手机访问 11 |
| `AdvancedComponentService._lock` | RLock（可重入） | `local/application/advanced_component_service.py:92` | 18 | 10 | 组件 10 |
| `UpdateService._lock` | Lock（不可重入） | `local/application/update_service.py:45` | 11 | 10 | 更新 10 |
| `Api._phone_access_lock` | RLock（可重入） | `local/app.py:845` | 9 | 9 | 组件 6、手机访问 3 |
| `AutoReloginMonitor._lock` | Lock（不可重入） | `local/application/auto_relogin.py:38` | 14 | 8 | 登录恢复 8 |
| `PhoneAccessService._event_lock` | Condition | `local/application/phone_service.py:43` | 3 | 3 | 手机访问 3 |
| `_LIFECYCLE_LOCK` | Lock（不可重入） | `local/app.py:779` | 1 | 1 | 其他 1 |
| `_PHONE_LOG_LOCK` | Lock（不可重入） | `local/app.py:147` | 1 | 1 | 手机访问 1 |
| `plan_service:run_plan_task:supervise` | Condition | `local/application/plan_service.py:162` | 6 | 1 | 计划 1 |

## 每把锁

### `Api._lock`（Lock（不可重入），`local/app.py:842`）

持有它的方法 64 个、`with` 96 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/app.py` | `Api._after_cancelled` | 计划 | 2 | 2476、2489 |
| `local/app.py` | `Api._anchor_login_success` | 登录恢复 | 1 | 4420 |
| `local/app.py` | `Api._auto_relogin_eligible` | 登录恢复 | 1 | 1850 |
| `local/app.py` | `Api._auto_relogin_paused` | 登录恢复 | 1 | 1876 |
| `local/app.py` | `Api._begin_auto_relogin_once` | 登录恢复 | 2 | 2029、2040 |
| `local/app.py` | `Api._begin_typed_relogin` | 登录恢复 | 1 | 4007 |
| `local/app.py` | `Api._bootstrap_plan_snapshot` | 计划 | 4 | 1225、1228、1234、1239 |
| `local/app.py` | `Api._commit_downloaded_component_group` | 组件 | 1 | 1339 |
| `local/app.py` | `Api._commit_downloaded_ocr_group` | 组件 | 1 | 1397 |
| `local/app.py` | `Api._commit_pending_save` | 登录恢复 | 1 | 3936 |
| `local/app.py` | `Api._component_finished` | 组件 | 1 | 1354 |
| `local/app.py` | `Api._confirm_signed` | 计划 | 1 | 2512 |
| `local/app.py` | `Api._do_check` | 登录恢复 | 2 | 2173、2180 |
| `local/app.py` | `Api._do_list` | 活动列表 | 1 | 2373 |
| `local/app.py` | `Api._do_list_inner` | 活动列表 | 2 | 2542、2608 |
| `local/app.py` | `Api._find_request_id` | 其他 | 1 | 1214 |
| `local/app.py` | `Api._install_downloaded_component` | 组件 | 1 | 1326 |
| `local/app.py` | `Api._install_downloaded_ocr` | 组件 | 1 | 1387 |
| `local/app.py` | `Api._install_selected_feature` | 组件 | 1 | 1708 |
| `local/app.py` | `Api._is_busy` | 其他 | 1 | 4300 |
| `local/app.py` | `Api._note_login_conclusion` | 登录恢复 | 1 | 2202 |
| `local/app.py` | `Api._note_pc_list_error` | 活动列表 | 1 | 2343 |
| `local/app.py` | `Api._once_credentials_staged` | 登录恢复 | 1 | 1864 |
| `local/app.py` | `Api._phone_raw_state` | 手机访问 | 2 | 3514、3534 |
| `local/app.py` | `Api._plan_source_of` | 计划 | 1 | 3338 |
| `local/app.py` | `Api._pump` | 其他 | 1 | 4470 |
| `local/app.py` | `Api._relay_finished` | 登录恢复 | 3 | 4137、4162、4179 |
| `local/app.py` | `Api._relogin_entry_gate` | 登录恢复 | 1 | 3980 |
| `local/app.py` | `Api._relogin_late_answer` | 登录恢复 | 1 | 3957 |
| `local/app.py` | `Api._request_auto_relogin` | 登录恢复 | 1 | 1894 |
| `local/app.py` | `Api._run` | worker 进程 | 2 | 4341、4369 |
| `local/app.py` | `Api._spawn` | worker 进程 | 1 | 4386 |
| `local/app.py` | `Api._spawn_relay_worker` | 登录恢复 | 1 | 4121 |
| `local/app.py` | `Api._start_clock_monitor` | 时钟 | 1 | 1076 |
| `local/app.py` | `Api._start_phone_access` | 手机访问 | 1 | 3687 |
| `local/app.py` | `Api._start_plan_inner` | 计划 | 9 | 2855、2866、2885、2922、2931、2968、2983、3048、3082 |
| `local/app.py` | `Api._terminate_plan_procs` | 计划 | 1 | 3115 |
| `local/app.py` | `Api._wait_component_settled` | 组件 | 1 | 3863 |
| `local/app.py` | `Api._wait_for_list_clock` | 活动列表 | 1 | 1011 |
| `local/app.py` | `Api.bootstrap` | 其他 | 2 | 1159、1190 |
| `local/app.py` | `Api.cancel_signup` | 计划 | 2 | 2425、2438 |
| `local/app.py` | `Api.cancel_start_request` | 计划 | 1 | 2755 |
| `local/app.py` | `Api.cancel_task` | 计划 | 1 | 3094 |
| `local/app.py` | `Api.check` | 登录恢复 | 1 | 2118 |
| `local/app.py` | `Api.clear_relogin_credentials` | 登录恢复 | 1 | 1796 |
| `local/app.py` | `Api.download_advanced_feature` | 组件 | 1 | 1434 |
| `local/app.py` | `Api.emit` | 其他 | 2 | 2968、2983 |
| `local/app.py` | `Api.enable_advanced_feature` | 组件 | 1 | 1466 |
| `local/app.py` | `Api.install_advanced_feature` | 组件 | 2 | 1655、1682 |
| `local/app.py` | `Api.list_activities` | 活动列表 | 1 | 2147 |
| `local/app.py` | `Api.login` | 登录恢复 | 1 | 2627 |
| `local/app.py` | `Api.monitor` | 其他 | 1 | 1076 |
| `local/app.py` | `Api.prepare_phone_relogin` | 登录恢复 | 1 | 3921 |
| `local/app.py` | `Api.remove_advanced_feature` | 组件 | 2 | 1734、1764 |
| `local/app.py` | `Api.restore_phone_access` | 手机访问 | 1 | 3781 |
| `local/app.py` | `Api.save_relogin_credentials` | 登录恢复 | 1 | 1784 |
| `local/app.py` | `Api.shutdown` | 窗口与托盘 | 1 | 3397 |
| `local/app.py` | `Api.start_plan` | 计划 | 5 | 2797、2816、2822、2827、2837 |
| `local/app.py` | `Api.start_request_state` | 计划 | 1 | 2716 |
| `local/app.py` | `Api.stop` | 窗口与托盘 | 3 | 3481、3485、3495 |
| `local/app.py` | `Api.stop_plan` | 计划 | 1 | 3102 |
| `local/app.py` | `Api.sync_clock` | 时钟 | 2 | 1045、1056 |
| `local/app.py` | `Api.window_visibility` | 窗口与托盘 | 1 | 3309 |
| `local/application/plan_service.py` | `run_plan_task` | 计划 | 2 | 117、404 |

- 拿别的锁时又被拿 18 处（这些地方它是内层）：`Api._credential_lock`、`Api._phone_access_lock`
- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `self._is_busy_locked()` | 10 |
| `self._remember_start()` | 9 |
| `_start_requests.get()` | 7 |
| `annotated()` | 4 |
| `_activities.get()` | 3 |
| `_activities.values()` | 3 |
| `_env()` | 3 |
| `_proc.poll()` | 3 |
| `_start_requests.items()` | 3 |
| `next()` | 3 |
| `spawn_owned()` | 3 |
| `_finished_plan_ids.get()` | 2 |

### `LoginRelayService._lock`（Lock（不可重入），`local/application/login_relay_service.py:129`）

持有它的方法 14 个、`with` 20 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/application/login_relay_service.py` | `LoginRelayService._finish` | 登录恢复 | 2 | 521、535 |
| `local/application/login_relay_service.py` | `LoginRelayService._handle_line` | 登录恢复 | 3 | 409、475、484 |
| `local/application/login_relay_service.py` | `LoginRelayService._send` | 登录恢复 | 1 | 337 |
| `local/application/login_relay_service.py` | `LoginRelayService._send_submit` | 登录恢复 | 1 | 349 |
| `local/application/login_relay_service.py` | `LoginRelayService.begin` | 登录恢复 | 3 | 181、230、252 |
| `local/application/login_relay_service.py` | `LoginRelayService.cancel` | 登录恢复 | 1 | 282 |
| `local/application/login_relay_service.py` | `LoginRelayService.clear_staged` | 登录恢复 | 1 | 169 |
| `local/application/login_relay_service.py` | `LoginRelayService.observe_line` | 登录恢复 | 1 | 329 |
| `local/application/login_relay_service.py` | `LoginRelayService.prepare` | 登录恢复 | 2 | 146、149 |
| `local/application/login_relay_service.py` | `LoginRelayService.prepared` | 登录恢复 | 1 | 154 |
| `local/application/login_relay_service.py` | `LoginRelayService.shutdown` | 登录恢复 | 1 | 306 |
| `local/application/login_relay_service.py` | `LoginRelayService.staged_hint` | 登录恢复 | 1 | 163 |
| `local/application/login_relay_service.py` | `LoginRelayService.state` | 登录恢复 | 1 | 315 |
| `local/application/login_relay_service.py` | `LoginRelayService.submit` | 登录恢复 | 1 | 260 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `flow.get()` | 11 |
| `public_state()` | 6 |
| `self._now()` | 5 |
| `_safe()` | 2 |
| `_pump_thread.start()` | 1 |
| `_reader.start()` | 1 |
| `_threads.extend()` | 1 |
| `callable()` | 1 |
| `payload.get()` | 1 |

### `Api._credential_lock`（RLock（可重入），`local/app.py:843`）

持有它的方法 12 个、`with` 12 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/app.py` | `Api._begin_auto_relogin_once` | 登录恢复 | 1 | 2010 |
| `local/app.py` | `Api._commit_downloaded_component_group` | 组件 | 1 | 1338 |
| `local/app.py` | `Api._commit_downloaded_ocr_group` | 组件 | 1 | 1396 |
| `local/app.py` | `Api._commit_pending_save` | 登录恢复 | 1 | 3942 |
| `local/app.py` | `Api._install_downloaded_component` | 组件 | 1 | 1325 |
| `local/app.py` | `Api._install_downloaded_ocr` | 组件 | 1 | 1386 |
| `local/app.py` | `Api._install_selected_feature` | 组件 | 1 | 1707 |
| `local/app.py` | `Api.clear_relogin_credentials` | 登录恢复 | 1 | 1793 |
| `local/app.py` | `Api.enable_advanced_feature` | 组件 | 1 | 1465 |
| `local/app.py` | `Api.install_advanced_feature` | 组件 | 1 | 1662 |
| `local/app.py` | `Api.remove_advanced_feature` | 组件 | 1 | 1733 |
| `local/app.py` | `Api.save_relogin_credentials` | 登录恢复 | 1 | 1782 |

- 持它时直接拿别的锁 17 处：`Api._lock`、`Api._phone_access_lock`
- 间接（经同类或服务方法一层）30 处：`AdvancedComponentService._lock` 经 _component_service.remove()、`Api._lock` 经 self._auto_relogin_eligible()、`Api._lock` 经 self._auto_relogin_paused()、`Api._lock` 经 self._once_credentials_staged()、`Api._phone_access_lock` 经 self.stop_phone_access()、`AutoReloginMonitor._lock` 经 _auto_relogin.reset()、`AutoReloginMonitor._lock` 经 _auto_relogin.snapshot()、`LoginRelayService._lock` 经 _relay.begin()、`LoginRelayService._lock` 经 _relay.cancel()、`LoginRelayService._lock` 经 _relay.clear_staged()、`LoginRelayService._lock` 经 _relay.prepare()
- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `_auto_relogin.reset()` | 8 |
| `_relay.cancel()` | 5 |
| `load_prefs()` | 4 |
| `update_prefs()` | 4 |
| `self.stop_phone_access()` | 3 |
| `_phone.is_running()` | 2 |
| `_phone.shutdown()` | 2 |
| `_relay.clear_staged()` | 2 |
| `self._stop_cloudflare_checked()` | 2 |
| `_auto_relogin.snapshot()` | 1 |
| `_component_service.remove()` | 1 |
| `_relay.begin()` | 1 |

### `PhoneAccessService._lock`（Lock（不可重入），`local/application/phone_service.py:41`）

持有它的方法 11 个、`with` 13 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/application/phone_service.py` | `PhoneAccessService.authenticate` | 手机访问 | 1 | 302 |
| `local/application/phone_service.py` | `PhoneAccessService.authenticate_or_restore` | 手机访问 | 1 | 363 |
| `local/application/phone_service.py` | `PhoneAccessService.has_live_session` | 手机访问 | 1 | 322 |
| `local/application/phone_service.py` | `PhoneAccessService.link_status` | 手机访问 | 1 | 339 |
| `local/application/phone_service.py` | `PhoneAccessService.pair` | 手机访问 | 1 | 238 |
| `local/application/phone_service.py` | `PhoneAccessService.pair_code_status` | 手机访问 | 1 | 93 |
| `local/application/phone_service.py` | `PhoneAccessService.paired_count` | 手机访问 | 1 | 120 |
| `local/application/phone_service.py` | `PhoneAccessService.revoke_all` | 手机访问 | 1 | 475 |
| `local/application/phone_service.py` | `PhoneAccessService.set_public_host` | 手机访问 | 1 | 180 |
| `local/application/phone_service.py` | `PhoneAccessService.start` | 手机访问 | 3 | 138、161、168 |
| `local/application/phone_service.py` | `PhoneAccessService.stop` | 手机访问 | 1 | 204 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `self._log()` | 4 |
| `bool()` | 3 |
| `float()` | 3 |
| `pair_code_fresh()` | 3 |
| `self._note_pair()` | 3 |
| `session_alive()` | 3 |
| `_sessions.clear()` | 2 |
| `_sessions.values()` | 2 |
| `range()` | 2 |
| `self._now()` | 2 |
| `type()` | 2 |
| `_device_store.add_device()` | 1 |

### `AdvancedComponentService._lock`（RLock（可重入），`local/application/advanced_component_service.py:92`）

持有它的方法 10 个、`with` 18 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/application/advanced_component_service.py` | `AdvancedComponentService._cancelled` | 组件 | 1 | 444 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService._fail` | 组件 | 1 | 480 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService._run` | 组件 | 3 | 308、316、337 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService._run_split_assets` | 组件 | 5 | 396、408、421、426、430 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService._set` | 组件 | 1 | 130 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService.cancel` | 组件 | 1 | 197 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService.remove` | 组件 | 3 | 221、232、238 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService.shutdown` | 组件 | 1 | 209 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService.snapshot` | 组件 | 1 | 135 |
| `local/application/advanced_component_service.py` | `AdvancedComponentService.start` | 组件 | 1 | 170 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `self._refresh_idle_state()` | 1 |
| `self._render_text()` | 1 |
| `type()` | 1 |

### `UpdateService._lock`（Lock（不可重入），`local/application/update_service.py:45`）

持有它的方法 10 个、`with` 11 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/application/update_service.py` | `UpdateService._spawn` | 更新 | 1 | 97 |
| `local/application/update_service.py` | `UpdateService.cancel` | 更新 | 1 | 171 |
| `local/application/update_service.py` | `UpdateService.launch` | 更新 | 1 | 184 |
| `local/application/update_service.py` | `UpdateService.publish` | 更新 | 1 | 75 |
| `local/application/update_service.py` | `UpdateService.snapshot` | 更新 | 1 | 61 |
| `local/application/update_service.py` | `UpdateService.start_check` | 更新 | 1 | 105 |
| `local/application/update_service.py` | `UpdateService.start_download` | 更新 | 1 | 127 |
| `local/application/update_service.py` | `run_check` | 更新 | 1 | 271 |
| `local/application/update_service.py` | `run_download` | 更新 | 1 | 335 |
| `local/application/update_service.py` | `run_version_download` | 更新 | 2 | 429、487 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `self._refuse()` | 2 |
| `self.is_closing()` | 2 |
| `state.is_closing()` | 1 |

### `Api._phone_access_lock`（RLock（可重入），`local/app.py:845`）

持有它的方法 9 个、`with` 9 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/app.py` | `Api._commit_downloaded_component_group` | 组件 | 1 | 1338 |
| `local/app.py` | `Api._install_downloaded_component` | 组件 | 1 | 1325 |
| `local/app.py` | `Api._install_selected_feature` | 组件 | 1 | 1707 |
| `local/app.py` | `Api._reconcile_cloudflare_lifecycle` | 手机访问 | 1 | 3616 |
| `local/app.py` | `Api.download_advanced_feature` | 组件 | 1 | 1433 |
| `local/app.py` | `Api.install_advanced_feature` | 组件 | 1 | 1662 |
| `local/app.py` | `Api.remove_advanced_feature` | 组件 | 1 | 1733 |
| `local/app.py` | `Api.start_phone_access` | 手机访问 | 1 | 3672 |
| `local/app.py` | `Api.stop_phone_access` | 手机访问 | 1 | 3877 |

- 持它时直接拿别的锁 6 处：`Api._lock`
- 拿别的锁时又被拿 5 处（这些地方它是内层）：`Api._credential_lock`
- 间接（经同类或服务方法一层）14 处：`AdvancedComponentService._lock` 经 _component_service.remove()、`Api._lock` 经 self._component_finished()、`Api._lock` 经 self._start_phone_access()、`Api._phone_access_lock` 经 self.stop_phone_access()（重入）、`AutoReloginMonitor._lock` 经 _auto_relogin.reset()、`LoginRelayService._lock` 经 _relay.cancel()、`LoginRelayService._lock` 经 _relay.clear_staged()
- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `_phone.is_running()` | 3 |
| `load_prefs()` | 3 |
| `self.stop_phone_access()` | 3 |
| `update_prefs()` | 3 |
| `_auto_relogin.reset()` | 2 |
| `_phone.shutdown()` | 2 |
| `_relay.cancel()` | 2 |
| `self._component_finished()` | 2 |
| `self._stop_cloudflare_checked()` | 2 |
| `self._stop_phone_access()` | 2 |
| `_component_service.remove()` | 1 |
| `_relay.clear_staged()` | 1 |

### `AutoReloginMonitor._lock`（Lock（不可重入），`local/application/auto_relogin.py:38`）

持有它的方法 8 个、`with` 14 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/application/auto_relogin.py` | `AutoReloginMonitor.notify_if_changed` | 登录恢复 | 1 | 99 |
| `local/application/auto_relogin.py` | `AutoReloginMonitor.observe_check` | 登录恢复 | 1 | 112 |
| `local/application/auto_relogin.py` | `AutoReloginMonitor.request_recover` | 登录恢复 | 1 | 121 |
| `local/application/auto_relogin.py` | `AutoReloginMonitor.reset` | 登录恢复 | 1 | 128 |
| `local/application/auto_relogin.py` | `AutoReloginMonitor.snapshot` | 登录恢复 | 1 | 139 |
| `local/application/auto_relogin.py` | `AutoReloginMonitor.start` | 登录恢复 | 1 | 56 |
| `local/application/auto_relogin.py` | `AutoReloginMonitor.tick` | 登录恢复 | 7 | 159、169、200、206、215、238、245 |
| `local/application/auto_relogin.py` | `AutoReloginMonitor.view` | 登录恢复 | 1 | 74 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `self._now()` | 6 |
| `self._failed()` | 4 |
| `_stop.is_set()` | 3 |
| `bool()` | 2 |
| `_thread.start()` | 1 |
| `self._log_event()` | 1 |

### `PhoneAccessService._event_lock`（Condition，`local/application/phone_service.py:43`）

持有它的方法 3 个、`with` 3 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/application/phone_service.py` | `PhoneAccessService._snapshot_events` | 手机访问 | 1 | 443 |
| `local/application/phone_service.py` | `PhoneAccessService.record_event` | 手机访问 | 1 | 434 |
| `local/application/phone_service.py` | `PhoneAccessService.safe_state` | 手机访问 | 1 | 424 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `_event_lock.notify_all()` | 1 |
| `_events.append()` | 1 |
| `select_events()` | 1 |

### `_LIFECYCLE_LOCK`（Lock（不可重入），`local/app.py:779`）

持有它的方法 1 个、`with` 1 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/app.py` | `get_lifecycle` | 其他 | 1 | 785 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `AppLifecycle()` | 1 |

### `_PHONE_LOG_LOCK`（Lock（不可重入），`local/app.py:147`）

持有它的方法 1 个、`with` 1 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/app.py` | `phone_log` | 手机访问 | 1 | 161 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `chr()` | 2 |

### `plan_service:run_plan_task:supervise`（Condition，`local/application/plan_service.py:162`）

持有它的方法 1 个、`with` 6 处：

| 模块 | 方法 | 功能 | 获取处 | 行 |
|---|---|---|---|---|
| `local/application/plan_service.py` | `run_plan_task` | 计划 | 6 | 194、224、239、289、346、385 |

- 持它期间发起的调用（按次数取前 12）：

| 调用 | 次数 |
|---|---|
| `extension_delta()` | 1 |

## 先后表

| 外层 | 内层 | 种类 | 处数 | 出处 |
|---|---|---|---|---|
| `Api._credential_lock` | `AdvancedComponentService._lock` | 间接 | 3 | Api.remove_advanced_feature:1752 经 _component_service.remove()；Api.remove_advanced_feature:1752 经 _component_service.remove()；Api.remove_advanced_feature:1752 经 _component_service.remove() |
| `Api._credential_lock` | `Api._lock` | 直接 | 12 | Api._install_downloaded_component:1326；Api._commit_downloaded_component_group:1339；Api._install_downloaded_ocr:1387… |
| `Api._credential_lock` | `Api._lock` | 间接 | 3 | Api._begin_auto_relogin_once:2011 经 self._auto_relogin_paused()；Api._begin_auto_relogin_once:2013 经 self._auto_relogin_eligible()；Api._begin_auto_relogin_once:2024 经 self._once_credentials_staged() |
| `Api._credential_lock` | `Api._phone_access_lock` | 直接 | 5 | Api._install_downloaded_component:1325；Api._commit_downloaded_component_group:1338；Api.install_advanced_feature:1662… |
| `Api._credential_lock` | `Api._phone_access_lock` | 间接 | 3 | Api.install_advanced_feature:1664 经 self.stop_phone_access()；Api._install_selected_feature:1712 经 self.stop_phone_access()；Api.remove_advanced_feature:1740 经 self.stop_phone_access() |
| `Api._credential_lock` | `AutoReloginMonitor._lock` | 间接 | 9 | Api._install_downloaded_ocr:1391 经 _auto_relogin.reset()；Api._commit_downloaded_ocr_group:1401 经 _auto_relogin.reset()；Api.enable_advanced_feature:1482 经 _auto_relogin.reset()… |
| `Api._credential_lock` | `LoginRelayService._lock` | 间接 | 12 | Api._install_downloaded_ocr:1390 经 _relay.cancel()；Api._commit_downloaded_ocr_group:1400 经 _relay.cancel()；Api._install_selected_feature:1714 经 _relay.cancel()… |
| `Api._phone_access_lock` | `AdvancedComponentService._lock` | 间接 | 3 | Api.remove_advanced_feature:1752 经 _component_service.remove()；Api.remove_advanced_feature:1752 经 _component_service.remove()；Api.remove_advanced_feature:1752 经 _component_service.remove() |
| `Api._phone_access_lock` | `Api._lock` | 直接 | 6 | Api._install_downloaded_component:1326；Api._commit_downloaded_component_group:1339；Api.download_advanced_feature:1434… |
| `Api._phone_access_lock` | `Api._lock` | 间接 | 3 | Api.download_advanced_feature:1441 经 self._component_finished()；Api.download_advanced_feature:1444 经 self._component_finished()；Api.start_phone_access:3673 经 self._start_phone_access() |
| `Api._phone_access_lock` | `Api._phone_access_lock` | 间接·重入 | 3 | Api.install_advanced_feature:1664 经 self.stop_phone_access()（重入）；Api._install_selected_feature:1712 经 self.stop_phone_access()（重入）；Api.remove_advanced_feature:1740 经 self.stop_phone_access()（重入） |
| `Api._phone_access_lock` | `AutoReloginMonitor._lock` | 间接 | 2 | Api._install_selected_feature:1715 经 _auto_relogin.reset()；Api.remove_advanced_feature:1744 经 _auto_relogin.reset() |
| `Api._phone_access_lock` | `LoginRelayService._lock` | 间接 | 3 | Api._install_selected_feature:1714 经 _relay.cancel()；Api.remove_advanced_feature:1742 经 _relay.cancel()；Api.remove_advanced_feature:1743 经 _relay.clear_staged() |

## 互锁与重入

A→B 与 B→A 同时存在（潜在死锁）的组合：无

同一把锁在同一条静态路径上被拿两次（RLock 的必要性就在这些点上）：

| 锁 | 位置 | 行 | 种类 |
|---|---|---|---|
| `Api._phone_access_lock` | `Api.install_advanced_feature` | 1664 | 经 `self.stop_phone_access()（重入）` |
| `Api._phone_access_lock` | `Api._install_selected_feature` | 1712 | 经 `self.stop_phone_access()（重入）` |
| `Api._phone_access_lock` | `Api.remove_advanced_feature` | 1740 | 经 `self.stop_phone_access()（重入）` |

其中落在不可重入 Lock 上的：无

