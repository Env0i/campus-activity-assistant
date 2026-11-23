# 整理后安全网复跑对照（72 条变异）

- 原版对照：`design/evidence/2026-11-22/phone-net/after.md`
- 总结论：**完全一致（0 条偏差）**（行为守 66、等价 6、字面守 0、无人守 0、定位不到 0，共 72 条）

| 编号 | 类 | 文件 | 新函数 | 定位方式 | 本次结论 | 原结论 | 对照 | 第一条失败用例 |
|---|---|---|---|---|---|---|---|---|
| M01 | 乙 | `local/ui/m/ui-session.js` | `readCookie` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M02 | 乙 | `local/ui/m/ui-session.js` | `readCookie` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M03 | 乙 | `local/ui/m/ui-session.js` | `readCookie` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M04 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M05 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M06 | 乙 | `local/ui/m/ui-session.js` | `adoptCookieCsrf` | 重定位 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M07 | 甲 | `local/ui/m/ui-session.js` | `adoptCookieCsrf` | 重定位 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M08 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M09 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M10 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M11 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M12 | 乙 | `local/ui/m/ui-session.js` | `api` | 重定位 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_action_401_clears_active_poll_and_tick_timers` |
| M13 | 乙 | `local/ui/m/ui-session.js` | `api` | 重定位 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_terminal_pending_releases_start_immediately` |
| M14 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M15 | 乙 | `local/ui/m/ui-session.js` | `api` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_api_clears_abort_timeout_after_request_settles` |
| M16 | 乙 | `local/ui/m/ui-session.js` | `renderPair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_locked_state_disables_input_and_counts_down` |
| M17 | 乙 | `local/ui/m/ui-session.js` | `renderPair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_pair_led_renders_lit_dots_and_clears_old_error_on_submit` |
| M18 | 乙 | `local/ui/m/ui-session.js` | `renderPair` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_pair_failure_says_the_network_is_down` |
| M19 | 甲 | `local/ui/m/ui-session.js` | `setPairError` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_pair_failure_says_the_network_is_down` |
| M20 | 甲 | `local/ui/m/ui-session.js` | `beginPairLock` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M21 | 乙 | `local/ui/m/ui-session.js` | `beginPairLock` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M22 | 甲 | `local/ui/m/ui-session.js` | `schedulePairTick` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M23 | 甲 | `local/ui/m/ui-session.js` | `schedulePairTick` | 原样 | 等价 | 等价 | 一致 | — |
| M24 | 甲 | `local/ui/m/ui-session.js` | `schedulePairTick` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M25 | 乙 | `local/ui/m/ui-session.js` | `schedulePairTick` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M26 | 甲 | `local/ui/m/ui-session.js` | `schedulePairTick` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M27 | 乙 | `local/ui/m/ui-session.js` | `stopPairLock` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_stopping_pair_lock_cancels_pending_countdown_timer` |
| M28 | 甲 | `local/ui/m/ui-session.js` | `stopPairLock` | 原样 | 等价 | 等价 | 一致 | — |
| M29 | 甲 | `local/ui/m/ui-session.js` | `stopPairLock` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_need_pair_repaints_the_pair_screen` |
| M30 | 乙 | `local/ui/m/ui-session.js` | `applyPairFailure` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M31 | 乙 | `local/ui/m/ui-session.js` | `applyPairFailure` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_wrong_code_shows_remaining_attempts_and_red_led` |
| M32 | 乙 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M33 | 甲 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_pair_led_renders_lit_dots_and_clears_old_error_on_submit` |
| M34 | 乙 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M35 | 甲 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_pair_is_single_flight` |
| M36 | 乙 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_locked_state_disables_input_and_counts_down` |
| M37 | 甲 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M38 | 甲 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_pair_success_sends_csrf_and_keeps_retry_if_first_poll_fails` |
| M39 | 甲 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_pair_success_shows_dismissable_connected_alert` |
| M40 | 甲 | `local/ui/m/ui-session.js` | `pair` | 原样 | 等价 | 等价 | 一致 | — |
| M41 | 甲 | `local/ui/m/ui-session.js` | `pair` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_pair_is_single_flight` |
| M42 | 乙 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M43 | 乙 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M44 | 甲 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `PhoneReloginRecoveryTests.test_poll_preserves_in_memory_csrf_and_caches_cookie_csrf` |
| M45 | 甲 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `PhoneSyncPolicyTests.test_manual_refresh_keeps_one_request_and_one_timer` |
| M46 | 乙 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M47 | 乙 | `local/ui/m/ui-session.js` | `poll` | 重定位 | 行为守 | 行为守 | 一致 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M48 | 乙 | `local/ui/m/ui-session.js` | `poll` | 重定位 | 行为守 | 行为守 | 一致 | `ListDetailModelTests.test_today_chip_shows_real_shape_activity_via_dom` |
| M49 | 乙 | `local/ui/m/ui-session.js` | `poll` | 重定位 | 行为守 | 行为守 | 一致 | `ListDetailModelTests.test_today_chip_shows_real_shape_activity_via_dom` |
| M50 | 甲 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M51 | 甲 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M52 | 甲 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_action_401_clears_active_poll_and_tick_timers` |
| M53 | 甲 | `local/ui/m/ui-session.js` | `poll` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M54 | 甲 | `local/ui/m/ui-session.js` | `onPollFail` | 原样 | 行为守 | 行为守 | 一致 | `PhoneReloginRecoveryTests.test_offline_says_why_and_keeps_refresh_tappable` |
| M55 | 甲 | `local/ui/m/ui-session.js` | `onPollFail` | 原样 | 行为守 | 行为守 | 一致 | `PairStatesDomTests.test_pair_success_sends_csrf_and_keeps_retry_if_first_poll_fails` |
| M56 | 甲 | `local/ui/m/ui-session.js` | `onNeedPair` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_action_401_returns_to_pairing_without_continuing_poll` |
| M57 | 乙 | `local/ui/m/ui-session.js` | `onNeedPair` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_action_401_clears_active_poll_and_tick_timers` |
| M58 | 甲 | `local/ui/m/ui-session.js` | `onNeedPair` | 原样 | 等价 | 等价 | 一致 | — |
| M59 | 乙 | `local/ui/m/ui-session.js` | `onNeedPair` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_action_401_clears_active_poll_and_tick_timers` |
| M60 | 甲 | `local/ui/m/ui-session.js` | `onNeedPair` | 原样 | 等价 | 等价 | 一致 | — |
| M61 | 乙 | `local/ui/m/ui-session.js` | `adoptCookieCsrf` | 重定位 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M62 | 甲 | `local/ui/m/ui-session.js` | `adoptCookieCsrf` | 重定位 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M63 | 乙 | `local/ui/m/ui-session.js` | `onForbidden` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_forbidden_csrf_keeps_the_app_open` |
| M64 | 甲 | `local/ui/m/ui-session.js` | `onForbidden` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M65 | 乙 | `local/ui/m/ui-session.js` | `schedule` | 原样 | 行为守 | 行为守 | 一致 | `PhoneSyncPolicyTests.test_poll_success_resets_backoff_and_replaces_old_poll_timer` |
| M66 | 甲 | `local/ui/m/ui-session.js` | `schedule` | 原样 | 等价 | 等价 | 一致 | — |
| M67 | 乙 | `local/ui/m/ui-session.js` | `schedule` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M68 | 乙 | `local/ui/m/ui-session.js` | `schedule` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M69 | 甲 | `local/ui/m/ui-session.js` | `schedule` | 原样 | 行为守 | 行为守 | 一致 | `MobileWriteResilienceTests.test_403_without_cookie_keeps_csrf_caches_new_cookie_and_backs_off` |
| M70 | 乙 | `local/ui/m/ui-session.js` | `probeExistingSession` | 原样 | 行为守 | 行为守 | 一致 | `PhoneReloginRecoveryTests.test_initial_wire_probes_cookie_session_once_without_repeating` |
| M71 | 甲 | `local/ui/m/ui-session.js` | `probeExistingSession` | 原样 | 行为守 | 行为守 | 一致 | `PhoneReloginRecoveryTests.test_initial_wire_probes_cookie_session_once_without_repeating` |
| M72 | 乙 | `local/ui/m/ui-session.js` | `probeExistingSession` | 原样 | 行为守 | 行为守 | 一致 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |

## 定位不到的条目

- 无（72 条全部唯一命中并通过 `node --check`）。
