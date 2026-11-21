# 第一组（请求与配对会话）变异结论（补测之前）

- 范围：16 个函数，甲类（`model.字段` 写换 `void 0`）32 条，乙类（条件 `C` 换 `!(C)`）40 条，共 72 条。

| 编号 | 类 | 函数 | 第几次 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |
|---|---|---|---:|---|---|---|---|
| M01 | 乙 | `readCookie` | 1 | `typeof document.cookie === "string" ?` | `!(typeof document.cookie === "string") ?` | 行为守 | `MobileWriteResilienceTests.test_forbidden_csrf_keeps_the_app_open` |
| M02 | 乙 | `readCookie` | 1 | `if (at < 0)` | `if (!(at < 0))` | 行为守 | `MobileWriteResilienceTests.test_forbidden_csrf_keeps_the_app_open` |
| M03 | 乙 | `readCookie` | 1 | `if (part.slice(0, at).trim() !== name)` | `if (!(part.slice(0, at).trim() !== name))` | 行为守 | `MobileWriteResilienceTests.test_forbidden_csrf_keeps_the_app_open` |
| M04 | 乙 | `api` | 1 | `if (opts.body && typeof opts.body !== "string")` | `if (!(opts.body && typeof opts.body !== "string"))` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M05 | 乙 | `api` | 1 | `if (opts.method === "POST")` | `if (!(opts.method === "POST"))` | 行为守 | `PhoneReloginRecoveryTests.test_existing_session_restores_app_and_csrf_without_pairing_again` |
| M06 | 乙 | `api` | 1 | `if (fresh) model.csrf = fresh;` | `if (!(fresh)) model.csrf = fresh;` | 行为守 | `PhoneReloginRecoveryTests.test_write_requests_use_the_current_csrf_cookie` |
| M07 | 甲 | `api` | 1 | `if (fresh) model.csrf = fresh;` | `if (fresh) void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_write_requests_use_the_current_csrf_cookie` |
| M08 | 乙 | `api` | 1 | `if (model.csrf) opts.headers` | `if (!(model.csrf)) opts.headers` | 行为守 | `PhoneReloginRecoveryTests.test_existing_session_restores_app_and_csrf_without_pairing_again` |
| M09 | 乙 | `api` | 1 | `typeof AbortController === "function" ?` | `!(typeof AbortController === "function") ?` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M10 | 乙 | `api` | 1 | `if (controller) {` | `if (!(controller)) {` | 行为守 | `WorkbenchPhoneTests.test_account_password_is_used_once_unless_save_is_ticked` |
| M11 | 乙 | `api` | 1 | `if (path === "/api/action")` | `if (!(path === "/api/action"))` | 行为守 | `MobileWriteResilienceTests.test_action_401_returns_to_pairing_without_continuing_poll` |
| M12 | 乙 | `api` | 1 | `if (resp.status === 401)` | `if (!(resp.status === 401))` | 行为守 | `MobileWriteResilienceTests.test_action_401_returns_to_pairing_without_continuing_poll` |
| M13 | 乙 | `api` | 1 | `if (resp.status === 403)` | `if (!(resp.status === 403))` | 行为守 | `MobileWriteResilienceTests.test_terminal_pending_releases_start_immediately` |
| M14 | 乙 | `api` | 1 | `if (resp.status !== 200 \|\| body.ok === false)` | `if (!(resp.status !== 200 \|\| body.ok === false))` | 行为守 | `MobileWriteResilienceTests.test_failed_cancel_without_error_field_keeps_challenge` |
| M15 | 乙 | `api` | 1 | `if (controller) clearTimeout(timer);` | `if (!(controller)) clearTimeout(timer);` | 无人守 | — |
| M16 | 乙 | `renderPair` | 1 | `view.tagTone ?` | `!(view.tagTone) ?` | 行为守 | `PairStatesDomTests.test_locked_state_disables_input_and_counts_down` |
| M17 | 乙 | `renderPair` | 1 | `if (d.cls)` | `if (!(d.cls))` | 无人守 | — |
| M18 | 乙 | `renderPair` | 1 | `view.hasErr ?` | `!(view.hasErr) ?` | 行为守 | `MobileWriteResilienceTests.test_pair_failure_says_the_network_is_down` |
| M19 | 甲 | `setPairError` | 1 | `model.pairErr = String(text \|\| "");` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_pair_failure_says_the_network_is_down` |
| M20 | 甲 | `beginPairLock` | 1 | `model.pairLockLeft = Math.max(0, Math.floor(Number(seconds) \|\| 0));` | `void 0;` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M21 | 乙 | `beginPairLock` | 1 | `if (model.pairLockLeft > 0)` | `if (!(model.pairLockLeft > 0))` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M22 | 甲 | `schedulePairTick` | 1 | `model.pairTickTimer = setTimeout(() => { ↵       model.pairTickTimer = 0; ↵       model.pairLockLeft = PhoneModel.pairTickLeft(model.pairLockLeft); ↵       if (model.pairLockLeft > 0) schedulePairTick(); ↵       else model.pairErr = "";   // UI-F6（原型 lockLeft 归零清 pairErr）：解锁即收回旧错误条 ↵       renderPair(); ↵     }, 1000);` | `void 0;` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M23 | 甲 | `schedulePairTick` | 1 | `model.pairTickTimer = 0;` | `void 0;` | 等价 | — |
| M24 | 甲 | `schedulePairTick` | 1 | `model.pairLockLeft = PhoneModel.pairTickLeft(model.pairLockLeft);` | `void 0;` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M25 | 乙 | `schedulePairTick` | 1 | `if (model.pairLockLeft > 0)` | `if (!(model.pairLockLeft > 0))` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M26 | 甲 | `schedulePairTick` | 1 | `else model.pairErr = "";` | `else void 0;` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M27 | 乙 | `stopPairLock` | 1 | `if (model.pairTickTimer)` | `if (!(model.pairTickTimer))` | 无人守 | — |
| M28 | 甲 | `stopPairLock` | 1 | `model.pairTickTimer = 0;` | `void 0;` | 等价 | — |
| M29 | 甲 | `stopPairLock` | 1 | `model.pairLockLeft = 0;` | `void 0;` | 行为守 | `PairStatesDomTests.test_need_pair_repaints_the_pair_screen` |
| M30 | 乙 | `applyPairFailure` | 1 | `if (error === "locked")` | `if (!(error === "locked"))` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M31 | 乙 | `applyPairFailure` | 1 | `if (error === "bad_code")` | `if (!(error === "bad_code"))` | 行为守 | `PairStatesDomTests.test_wrong_code_shows_remaining_attempts_and_red_led` |
| M32 | 乙 | `pair` | 1 | `if (model.pairing)` | `if (!(model.pairing))` | 行为守 | `MobileWriteResilienceTests.test_pair_failure_says_the_network_is_down` |
| M33 | 甲 | `pair` | 1 | `^    model.pairErr = "";` | `    void 0;` | 无人守 | — |
| M34 | 乙 | `pair` | 1 | `if (!code)` | `if (!(!code))` | 行为守 | `MobileWriteResilienceTests.test_pair_failure_says_the_network_is_down` |
| M35 | 甲 | `pair` | 1 | `model.pairing = true;` | `void 0;` | 行为守 | `PairStatesDomTests.test_pair_is_single_flight` |
| M36 | 乙 | `pair` | 1 | `if (status !== 200 \|\| !body.ok)` | `if (!(status !== 200 \|\| !body.ok))` | 行为守 | `PairStatesDomTests.test_countdown_end_releases_input_for_the_next_try` |
| M37 | 甲 | `pair` | 1 | `model.csrf = String(body.csrf \|\| "");` | `void 0;` | 无人守 | — |
| M38 | 甲 | `pair` | 1 | `model.paired = true;` | `void 0;` | 无人守 | — |
| M39 | 甲 | `pair` | 1 | `model.pairOkPending = true;` | `void 0;` | 行为守 | `PairStatesDomTests.test_pair_success_shows_dismissable_connected_alert` |
| M40 | 甲 | `pair` | 2 | `^      model.pairErr = "";` | `      void 0;` | 等价 | — |
| M41 | 甲 | `pair` | 1 | `model.pairing = false;` | `void 0;` | 行为守 | `PairStatesDomTests.test_pair_is_single_flight` |
| M42 | 乙 | `poll` | 1 | `if (model.flying)` | `if (!(model.flying))` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M43 | 乙 | `poll` | 1 | `if (!model.csrf)` | `if (!(!model.csrf))` | 无人守 | — |
| M44 | 甲 | `poll` | 1 | `if (!model.csrf) model.csrf = readCookie("campus_phone_csrf");` | `if (!model.csrf) void 0;` | 无人守 | — |
| M45 | 甲 | `poll` | 1 | `model.flying = true;` | `void 0;` | 行为守 | `PhoneSyncPolicyTests.test_manual_refresh_keeps_one_request_and_one_timer` |
| M46 | 乙 | `poll` | 1 | `force ?` | `!(force) ?` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M47 | 乙 | `poll` | 1 | `if (status === 401)` | `if (!(status === 401))` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M48 | 乙 | `poll` | 1 | `if (status === 403)` | `if (!(status === 403))` | 行为守 | `MobileWriteResilienceTests.test_forbidden_csrf_keeps_the_app_open` |
| M49 | 乙 | `poll` | 1 | `if (status !== 200)` | `if (!(status !== 200))` | 行为守 | `PairStatesDomTests.test_pair_success_shows_dismissable_connected_alert` |
| M50 | 甲 | `poll` | 1 | `model.lastOkAt = Date.now();` | `void 0;` | 行为守 | `PairStatesDomTests.test_pair_success_shows_dismissable_connected_alert` |
| M51 | 甲 | `poll` | 1 | `model.backoff = 1000;` | `void 0;` | 无人守 | — |
| M52 | 甲 | `poll` | 1 | `model.paired = true;` | `void 0;` | 无人守 | — |
| M53 | 甲 | `poll` | 1 | `model.flying = false;` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_background_recovery_backfills_by_event_cursor_only` |
| M54 | 甲 | `onPollFail` | 1 | `model.offlineTries = Number(model.offlineTries \|\| 0) + 1;` | `void 0;` | 行为守 | `PhoneReloginRecoveryTests.test_offline_says_why_and_keeps_refresh_tappable` |
| M55 | 甲 | `onPollFail` | 1 | `model.backoff = PhoneModel.nextBackoff(model.backoff);` | `void 0;` | 行为守 | `PhoneDomBehaviourTests.test_poll_failure_backs_off_and_stale_disables_start` |
| M56 | 甲 | `onNeedPair` | 1 | `model.paired = false;` | `void 0;` | 行为守 | `MobileWriteResilienceTests.test_action_401_returns_to_pairing_without_continuing_poll` |
| M57 | 乙 | `onNeedPair` | 1 | `if (model.pollTimer)` | `if (!(model.pollTimer))` | 无人守 | — |
| M58 | 甲 | `onNeedPair` | 1 | `model.pollTimer = null;` | `void 0;` | 等价 | — |
| M59 | 乙 | `onNeedPair` | 1 | `if (model.tickTimer)` | `if (!(model.tickTimer))` | 无人守 | — |
| M60 | 甲 | `onNeedPair` | 1 | `model.tickTimer = null;` | `void 0;` | 等价 | — |
| M61 | 乙 | `onForbidden` | 1 | `if (fresh) model.csrf = fresh;` | `if (!(fresh)) model.csrf = fresh;` | 无人守 | — |
| M62 | 甲 | `onForbidden` | 1 | `if (fresh) model.csrf = fresh;` | `if (fresh) void 0;` | 无人守 | — |
| M63 | 乙 | `onForbidden` | 1 | `code === "bad_csrf"` | `!(code === "bad_csrf")` | 行为守 | `MobileWriteResilienceTests.test_forbidden_csrf_keeps_the_app_open` |
| M64 | 甲 | `onForbidden` | 1 | `model.backoff = PhoneModel.nextBackoff(model.backoff);` | `void 0;` | 无人守 | — |
| M65 | 乙 | `schedule` | 1 | `if (model.pollTimer)` | `if (!(model.pollTimer))` | 无人守 | — |
| M66 | 甲 | `schedule` | 1 | `model.pollTimer = null;` | `void 0;` | 等价 | — |
| M67 | 乙 | `schedule` | 1 | `if (typeof document !== "undefined" && document.hidden)` | `if (!(typeof document !== "undefined" && document.hidden))` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M68 | 乙 | `schedule` | 1 | `if (!model.paired \|\| model.flying)` | `if (!(!model.paired \|\| model.flying))` | 行为守 | `PhoneSyncPolicyTests.test_401_stops_the_automatic_sync` |
| M69 | 甲 | `schedule` | 1 | `model.pollTimer = setTimeout(() => poll(false), PhoneModel.syncDelay(model));` | `void 0;` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |
| M70 | 乙 | `probeExistingSession` | 1 | `if (model.probed)` | `if (!(model.probed))` | 无人守 | — |
| M71 | 甲 | `probeExistingSession` | 1 | `model.probed = true;` | `void 0;` | 无人守 | — |
| M72 | 乙 | `probeExistingSession` | 1 | `if (!readCookie("campus_phone_csrf"))` | `if (!(!readCookie("campus_phone_csrf")))` | 行为守 | `PhoneSyncPolicyTests.test_busy_plan_syncs_every_two_seconds` |

## 各类合计

- 行为守：48
- 字面守：0
- 无人守：18
- 无效：0
- 等价：6
- 总计：72

## 等价判定理由

- **M23**（`schedulePairTick`）：model.pairTickTimer 的全部读取/写入方只有 schedulePairTick（app.js:2362-2363）与 stopPairLock（app.js:2371-2372）。本条位于 setTimeout 回调内（定时器已触发并退出活跃队列）：若 pairLockLeft > 0，下一行（2365）立即调用 schedulePairTick() 覆写新定时器 ID；若 pairLockLeft <= 0，之后唯一读取方 stopPairLock 只执行 if (model.pairTickTimer) clearTimeout(model.pairTickTimer)。由于浏览器与测试沙箱（++timerSeq）都不会复用已分配的定时器 ID，对已触发 ID 再次调用 clearTimeout 为空操作，任何 DOM、fetch 请求或活跃定时器都分不出变异前后。
- **M28**（`stopPairLock`）：model.pairTickTimer 的全部读取/写入方只有 schedulePairTick（app.js:2362-2363）与 stopPairLock（app.js:2371-2372）。stopPairLock 上一行（2371）已对当前 model.pairTickTimer 调用过 clearTimeout，且定时器 ID 单调递增不复用；保留旧 ID 仅使后续 stopPairLock 再次对已取消 ID 调用 clearTimeout（空操作），下次 beginPairLock 会覆写新 ID，任何 DOM、fetch 请求或活跃定时器都分不出变异前后。
- **M40**（`pair`）：model.pairErr 的全部写入方只有 setPairError（app.js:2351，由 applyPairFailure 和 pair 调用）、schedulePairTick（app.js:2366，仅清空）、pair（app.js:2397, 2420）与 wire（app.js:3200，input 事件仅清空）。进入 pair() 时有 model.pairing 并发锁（2395）阻拦重入，2397 行已将 model.pairErr 置为 ""，2398 行已调用 stopPairLock() 停止倒计时；在 await api("/pair") 挂起期间没有任何可达写入方能把 pairErr 设为非空串，因此到 2420 行时 model.pairErr 必已为 ""（且 2422 行紧接着隐藏 #pair），任何外部可见结果都不变。
- **M58**（`onNeedPair`）：model.pollTimer 的全部读取方只有 onNeedPair（app.js:2469）、schedule（app.js:2493）与 wire 的 visibilitychange/pagehide 监听（app.js:3332, 3342），每一处都只执行 if (model.pollTimer) clearTimeout(model.pollTimer)。onNeedPair 上一行（2469）已调用 clearTimeout 取消该定时器，保留已取消的单调 ID 仅使后续清理方再次对其调用空操作 clearTimeout，任何 DOM、fetch 请求或活跃定时器都分不出变异前后。
- **M60**（`onNeedPair`）：model.tickTimer 的全部读取方只有 onNeedPair（app.js:2471）、scheduleTick（app.js:2503）与 wire 的 visibilitychange/pagehide 监听（app.js:3334, 3344），每一处都只执行 if (model.tickTimer) clearTimeout(model.tickTimer)。onNeedPair 上一行（2471）已调用 clearTimeout 取消该定时器，保留已取消的单调 ID 仅使后续清理方再次对其调用空操作 clearTimeout，任何 DOM、fetch 请求或活跃定时器都分不出变异前后。
- **M66**（`schedule`）：model.pollTimer 的全部读取方只有 onNeedPair（app.js:2469）、schedule（app.js:2493）与 wire 的 visibilitychange/pagehide 监听（app.js:3332, 3342），每一处都只执行 if (model.pollTimer) clearTimeout(model.pollTimer)。schedule 上一行（2493）已调用 clearTimeout 取消旧定时器：若在 2495/2496 行提前返回，保留已取消的单调 ID 仅使后续清理方再次对其调用空操作 clearTimeout；若继续到 2497 行则立即覆写新定时器 ID，任何 DOM、fetch 请求或活跃定时器都分不出变异前后。
