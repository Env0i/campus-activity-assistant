变异证明：共 18 条，四个副本并行，每条首红即停

[红了] sig-1（signatures）—— local/app.py start_plan 签名：request_id 改名成 request_id2
[红了] sig-2（signatures）—— phone_service.dispatch：save_retry_policy 的改写目标改成不存在的方法
[红了] sig-3（signatures）—— phone_rules.ACTION_PARAMS：给 check 加一个 Api.check 不接的键
[红了] sig-4（signatures）—— local/app.py check 签名：加一个没有默认值的前置参数
[红了] lock-1（lock-order）—— local/app.py check：持协调锁的块里加一层凭据锁（3→1 降级）
[红了] lock-2（lock-order）—— local/app.py check：持协调锁时加一句 self._relay.cancel()
[红了] lock-3（lock-order）—— login_relay_service.cancel：锁外的 self._on_finish() 挪进 with（服务持锁调端口）
[红了] lock-4（lock-order）—— local/app.py check：新加一把没定级的 self._x_lock 并在 with 里用
[红了] lock-5（lock-order）—— local/app.py remove_advanced_feature：3 处重入之一改成不取锁的 _stop_phone_access()
[红了] matrix-1（busy-matrix）—— local/app.py _is_busy_locked：加 or self._advanced_busy
[红了] matrix-2（busy-matrix）—— local/app.py _start_phone_access：门里删掉 self._advanced_busy
[红了] matrix-3（busy-matrix）—— local/app.py check：门里删掉 _cancelling
[红了] matrix-4（busy-matrix）—— local/app.py remove_advanced_feature：移除门也问 _is_busy_locked()
[红了] matrix-5（busy-matrix）—— local/app.py _spawn_relay_worker：门里删掉 _checking
[红了] matrix-6（busy-matrix）—— local/app.py _is_busy_locked：_plan_procs 那句换成 return False
[红了] matrix-7（busy-matrix）—— local/app.py _relogin_blocked_locked：_plan_procs 那句换成 return False
[红了] lock-6（lock-order）—— phone_service.revoke_all：持 _event_lock（等级 6）再拿 _lock（等级 5）
[红了] lock-7（lock-order）—— signup_plan.cancel_task：self._publish 挪进 with self._lock（锁内发布）

## 变异表

| 编号 | 守卫 | 改了哪一行 | 预期红的用例 | 实际红的用例 | 结论 |
|---|---|---|---|---|---|
| sig-1 | signatures | local/app.py start_plan 签名：request_id 改名成 request_id2 | test_all_actions_bind_to_real_api_signatures（start_plan 全键派发） 与 test_start_plan_dispatch_marks_source_phone | test_all_actions_bind_to_real_api_signatures (test_phone_action_signatures.PhoneActionSignatureTests.test_all_actions_bind_to_real_api_signatures) (action='start_plan', variant='all-keys')<br>test_start_plan_dispatch_marks_source_phone (test_phone_action_signatures.PhoneActionSignatureTests.test_start_plan_dispatch_marks_source_phone) | 红 |
| sig-2 | signatures | phone_service.dispatch：save_retry_policy 的改写目标改成不存在的方法 | test_save_retry_policy_rewrites_into_prefs（落到 not_available） | test_all_actions_bind_to_real_api_signatures (test_phone_action_signatures.PhoneActionSignatureTests.test_all_actions_bind_to_real_api_signatures) (action='save_retry_policy', variant='all-keys')<br>test_all_actions_bind_to_real_api_signatures (test_phone_action_signatures.PhoneActionSignatureTests.test_all_actions_bind_to_real_api_signatures) (action='save_retry_policy', variant='minimal')<br>test_save_retry_policy_rewrites_into_prefs (test_phone_action_signatures.PhoneActionSignatureTests.test_save_retry_policy_rewrites_into_prefs) | 红 |
| sig-3 | signatures | phone_rules.ACTION_PARAMS：给 check 加一个 Api.check 不接的键 | test_tables_cover_the_whole_whitelist（全键表没盖住新键） | test_tables_cover_the_whole_whitelist (test_phone_action_signatures.PhoneActionSignatureTests.test_tables_cover_the_whole_whitelist) | 红 |
| sig-4 | signatures | local/app.py check 签名：加一个没有默认值的前置参数 | test_all_actions_bind_to_real_api_signatures（check 两种派发都 internal） | test_all_actions_bind_to_real_api_signatures (test_phone_action_signatures.PhoneActionSignatureTests.test_all_actions_bind_to_real_api_signatures) (action='check', variant='all-keys')<br>test_all_actions_bind_to_real_api_signatures (test_phone_action_signatures.PhoneActionSignatureTests.test_all_actions_bind_to_real_api_signatures) (action='check', variant='minimal') | 红 |
| lock-1 | lock-order | local/app.py check：持协调锁的块里加一层凭据锁（3→1 降级） | test_lock_level_only_rises | test_lock_level_only_rises (test_lock_order.LockOrderTests.test_lock_level_only_rises) | 红 |
| lock-2 | lock-order | local/app.py check：持协调锁时加一句 self._relay.cancel() | test_coordination_lock_calls_only_published_status | test_coordination_lock_calls_only_published_status (test_lock_order.LockOrderTests.test_coordination_lock_calls_only_published_status) | 红 |
| lock-3 | lock-order | login_relay_service.cancel：锁外的 self._on_finish() 挪进 with（服务持锁调端口） | test_service_locks_avoid_injected_ports（_on_finish 不在白名单与冻结表） | test_service_locks_avoid_injected_ports (test_lock_order.LockOrderTests.test_service_locks_avoid_injected_ports) | 红 |
| lock-4 | lock-order | local/app.py check：新加一把没定级的 self._x_lock 并在 with 里用 | test_new_locks_must_be_leveled | test_new_locks_must_be_leveled (test_lock_order.LockOrderTests.test_new_locks_must_be_leveled) | 红 |
| lock-5 | lock-order | local/app.py remove_advanced_feature：3 处重入之一改成不取锁的 _stop_phone_access() | test_reentry_equals_the_frozen_legacy_list（重入变 2 条，不等于冻结的 3 条） | test_reentry_equals_the_frozen_legacy_list (test_lock_order.LockOrderTests.test_reentry_equals_the_frozen_legacy_list) | 红 |
| matrix-1 | busy-matrix | local/app.py _is_busy_locked：加 or self._advanced_busy | test_row_start_plan 的「组件事务在途」子用例（放行变拒绝） | test_row_grab (test_busy_matrix.BusyMatrixTests.test_row_grab) (row='grab', column='advanced')<br>test_row_login (test_busy_matrix.BusyMatrixTests.test_row_login) (row='login', column='advanced')<br>test_row_start_plan (test_busy_matrix.BusyMatrixTests.test_row_start_plan) (row='start_plan', column='advanced') | 红 |
| matrix-2 | busy-matrix | local/app.py _start_phone_access：门里删掉 self._advanced_busy | test_row_start_phone_access 的「组件事务在途」子用例（拒绝变放行） | test_row_start_phone_access (test_busy_matrix.BusyMatrixTests.test_row_start_phone_access) (row='start_phone_access', column='advanced') | 红 |
| matrix-3 | busy-matrix | local/app.py check：门里删掉 _cancelling | test_row_check 的「取消报名在途」子用例（拒绝变放行） | test_row_check (test_busy_matrix.BusyMatrixTests.test_row_check) (row='check', column='cancelling') | 红 |
| matrix-4 | busy-matrix | local/app.py remove_advanced_feature：移除门也问 _is_busy_locked() | test_row_component_remove 的「取消报名在途 / 单 worker 在跑 / 计划在跑」子用例 | test_row_component_remove (test_busy_matrix.BusyMatrixTests.test_row_component_remove) (row='component_remove', column='cancelling')<br>test_row_component_remove (test_busy_matrix.BusyMatrixTests.test_row_component_remove) (row='component_remove', column='worker')<br>test_row_component_remove (test_busy_matrix.BusyMatrixTests.test_row_component_remove) (row='component_remove', column='plan')<br>test_row_component_remove (test_busy_matrix.BusyMatrixTests.test_row_component_remove) (row='component_remove', column='plan_procs') | 红 |
| matrix-5 | busy-matrix | local/app.py _spawn_relay_worker：门里删掉 _checking | test_row_manual_relogin 的「check 在途」子用例（拒绝变放行） | test_row_manual_relogin (test_busy_matrix.BusyMatrixTests.test_row_manual_relogin) (row='manual_relogin', column='checking') | 红 |
| matrix-6 | busy-matrix | local/app.py _is_busy_locked：_plan_procs 那句换成 return False | test_row_start_plan / login / grab / component_download / component_install 的「计划进程在跑」子用例（拒绝变放行） | test_row_component_download (test_busy_matrix.BusyMatrixTests.test_row_component_download) (row='component_download', column='plan_procs')<br>test_row_component_install (test_busy_matrix.BusyMatrixTests.test_row_component_install) (row='component_install', column='plan_procs')<br>test_row_grab (test_busy_matrix.BusyMatrixTests.test_row_grab) (row='grab', column='plan_procs')<br>test_row_login (test_busy_matrix.BusyMatrixTests.test_row_login) (row='login', column='plan_procs')<br>test_row_start_plan (test_busy_matrix.BusyMatrixTests.test_row_start_plan) (row='start_plan', column='plan_procs') | 红 |
| matrix-7 | busy-matrix | local/app.py _relogin_blocked_locked：_plan_procs 那句换成 return False | test_row_auto_relogin 的「计划进程在跑」子用例（拒绝变放行） | test_row_auto_relogin (test_busy_matrix.BusyMatrixTests.test_row_auto_relogin) (row='auto_relogin', column='plan_procs') | 红 |
| lock-6 | lock-order | phone_service.revoke_all：持 _event_lock（等级 6）再拿 _lock（等级 5） | test_service_lock_level_only_rises（服务类内部 6→5 降级） | test_service_lock_level_only_rises (test_lock_order.LockOrderTests.test_service_lock_level_only_rises) | 红 |
| lock-7 | lock-order | signup_plan.cancel_task：self._publish 挪进 with self._lock（锁内发布） | test_publish_stays_outside_the_coordinator_lock（同时 5→3 降级也让 test_service_lock_level_only_rises 红） | test_publish_stays_outside_the_coordinator_lock (test_lock_order.LockOrderTests.test_publish_stays_outside_the_coordinator_lock)<br>test_service_lock_level_only_rises (test_lock_order.LockOrderTests.test_service_lock_level_only_rises)<br>test_service_locks_avoid_injected_ports (test_lock_order.LockOrderTests.test_service_locks_avoid_injected_ports) | 红 |

全部 18 条变异都让预期的守卫变红。
