# 手机页（local/ui/m）移动前事实清点

- 数据来源：`local/ui/m/app.js`、`local/ui/m/index.html`、`local/infrastructure/phone_http.py`、`local/tests/test_phone_ui.py`。
- 口径：函数范围与词法借 `tools/code_shape/jsscan.mjs`、`jslex.mjs`；`model.字段` 读写只计直接访问（赋值、复合赋值、自增自减与 `add`/`delete`/`clear`/`push` 等原地修改及嵌套属性赋值计写，其余计读）；字符常量与注释不计。

## 表一 DOM 层函数

| 函数名 | 起止行 | 行数 | 所属组 | 读的 model 字段 | 写的 model 字段 | 调用的其他 DOM 函数 | 被哪些 DOM 函数调用 | 挂在 PhoneUI | test_phone_ui.py 调用次数 |
|---|---|---:|---|---|---|---|---|---|---:|
| `readCookie` | 1373–1385 | 13 | 请求与配对会话 | — | — | — | `api`、`onForbidden`、`poll`、`probeExistingSession` | 否 | 0 |
| `setBanner` | 1427–1433 | 7 | 摄入与渲染 | `bannerKind` | `bannerKind` | — | `beginRelogin`、`cancelPendingStart`、`clearStaleBanner`、`onForbidden`、`reconcile`(3)、`startPlan`(3) | 否 | 0 |
| `clearStaleBanner` | 1435–1437 | 3 | 摄入与渲染 | `bannerKind` | — | `setBanner` | `poll` | 否 | 0 |
| `syncOffline` | 1442–1461 | 20 | 摄入与渲染 | `flying`、`offlineTries` | `offlineTries` | — | `renderAlerts` | 否 | 0 |
| `renderAlerts` | 1465–1494 | 30 | 摄入与渲染 | `clockState`、`flow`、`login`、`pairOkPending`、`pcListError`(2)、`termsOk` | — | `syncOffline` | `refreshControls`、`wire` | 否 | 0 |
| `canWrite` | 1495–1498 | 4 | 摄入与渲染 | `lastOkAt`、`nowMs` | `nowMs` | — | `beginRelogin`、`startPlan` | 否 | 0 |
| `refreshControls` | 1500–1547 | 48 | 摄入与渲染 | `busy`、`challenge`(2)、`flow`(3)、`flying`(2)、`items`、`lastOkAt`、`login`、`nowMs`、`pending`(2)、`reloginSetup`(4)、`reloginStarting`(2)、`retry`、`selected`、`sheetId`、`termsOk`(4) | `nowMs` | `renderAlerts`、`renderBar`、`renderRelogin`、`sheetBusy` | `beginRelogin`(5)、`cancelPendingStart`、`ingestRelogin`(4)、`poll`(2)、`reconcile`、`renderItems`、`startPlan`(2)、`submitRelogin`(2)、`wire`(3) | 是 | 34 |
| `sheetBusy` | 1553–1557 | 5 | 外壳与接线 | `flow`、`reloginSubmitting`(2) | — | — | `closeSheet`、`openSheet`、`refreshControls` | 否 | 0 |
| `openSheet` | 1561–1578 | 18 | 外壳与接线 | `sheetId` | `sheetId`、`sheetOpener` | `sheetBusy` | `askConfirm`、`openRelogin`、`openReview`、`wire` | 是 | 14 |
| `closeSheet` | 1579–1606 | 28 | 外壳与接线 | `sheetId`、`sheetOpener` | `confirm`、`relConfirm`、`sheetId`、`sheetOpener` | `sheetBusy` | `ingest`、`onConfirmYes`(2)、`openRelogin`、`removeFromReview`、`wire`(8) | 是 | 11 |
| `showSheetError` | 1608–1613 | 6 | 外壳与接线 | `sheetId` | — | — | `cancelPendingStart`、`cancelTask`、`postAction`、`stopPlan` | 否 | 0 |
| `renderRelogin` | 1618–1649 | 32 | 重新登录 | `busy`、`flow`、`relConfirm`、`relEnteredAcct`、`relSavedChoice`、`reloginSetup`、`reloginStarting`、`reloginSubmitting` | — | — | `openRelogin`、`refreshControls` | 是 | 0 |
| `openRelogin` | 1656–1669 | 14 | 重新登录 | `flow`、`reloginSetup`、`sheetId`(2) | `relConfirm` | `closeSheet`、`openSheet`、`renderRelogin` | `wire`(3) | 是 | 4 |
| `askConfirm` | 1678–1689 | 12 | 外壳与接线 | `sheetId` | `confirm` | `openSheet` | `renderTasks`、`wire`(2) | 是 | 4 |
| `onConfirmYes` | 1690–1704 | 15 | 外壳与接线 | `confirm` | — | `cancelPendingStart`、`cancelTask`、`closeSheet`(2)、`stopPlan` | `wire` | 否 | 0 |
| `renderBar` | 1719–1771 | 53 | 摄入与渲染 | `busy`(4)、`clockState`、`flow`(2)、`flying`、`items`、`login`(4)、`pcListError`、`pending`(5)、`plan`(3)、`selected`(2)、`termsOk` | — | — | `refreshControls` | 否 | 0 |
| `buildRow` | 1775–1876 | 102 | 摄入与渲染 | `flashId`、`items`、`selected`、`whyId` | `notice`、`selected` | `buildWhy`、`renderItems`(2) | `renderItems`(2) | 否 | 0 |
| `buildWhy` | 1879–1963 | 85 | 摄入与渲染 | — | — | `goSigned` | `buildRow` | 否 | 0 |
| `goSigned` | 1967–1985 | 19 | 摄入与渲染 | `filter`、`items` | `filter`、`flashId`(2)、`whyId` | `renderItems` | `buildWhy` | 否 | 0 |
| `renderItems` | 1997–2093 | 97 | 摄入与渲染 | `busy`(5)、`filter`、`items`(4)、`listOpen`(3)、`notice`(2)、`nowMs`、`pending`(2)、`plan`、`searchOpen`、`selected`、`termsOk`(2) | `nowMs` | `buildRow`(2)、`refreshControls`、`renderBoard` | `buildRow`(2)、`finishPlanView`、`goSigned`、`poll`、`removeFromReview`、`reselectFailed`、`toggleSearch`、`wire`(6) | 是 | 8 |
| `renderRail` | 2098–2114 | 17 | 摄入与渲染 | — | — | — | `renderBoard`(2) | 否 | 0 |
| `renderBoard` | 2120–2184 | 65 | 摄入与渲染 | `busy`(2)、`flying`、`lastOkText`、`pending`(3)、`plan`(2)、`termsOk` | `pickId`(2) | `renderRail`(2)、`renderStats` | `renderItems` | 是 | 0 |
| `renderStats` | 2188–2202 | 15 | 摄入与渲染 | — | — | — | `renderBoard` | 否 | 0 |
| `toggleSearch` | 2206–2215 | 10 | 摄入与渲染 | `searchOpen`(4) | `filter`、`searchOpen` | `renderItems` | `wire` | 是 | 0 |
| `renderPlan` | 2220–2225 | 6 | 摄入与渲染 | `busy` | — | `renderTasks` | `finishPlanView`、`poll`、`reselectFailed` | 否 | 0 |
| `renderTasks` | 2230–2265 | 36 | 摄入与渲染 | `busy`(2)、`plan`(3) | — | `askConfirm` | `renderPlan` | 否 | 0 |
| `addLog` | 2267–2272 | 6 | 摄入与渲染 | — | — | — | `cancelRelogin`、`ingest`、`reselectFailed`、`saveRetry`、`showComputerWindow`(2) | 否 | 0 |
| `api` | 2275–2311 | 37 | 请求与配对会话 | `csrf`(2) | `csrf` | `onForbidden`、`onNeedPair`、`readCookie` | `pair`、`poll`、`postAction`、`submitRelogin` | 否 | 0 |
| `postAction` | 2316–2325 | 10 | 请求与配对会话 | — | — | `api`、`showSheetError` | `beginRelogin`、`cancelPendingStart`、`cancelRelogin`、`cancelTask`、`reconcile`、`saveRetry`、`showComputerWindow`、`startPlan`、`stopPlan` | 否 | 0 |
| `renderPair` | 2328–2349 | 22 | 请求与配对会话 | `pairErr`、`pairLockLeft` | — | — | `onNeedPair`、`pair`(2)、`schedulePairTick`、`setPairError`、`wire`(2) | 是 | 1 |
| `setPairError` | 2350–2353 | 4 | 请求与配对会话 | — | `pairErr` | `renderPair` | `applyPairFailure`(3)、`pair`(2) | 否 | 0 |
| `beginPairLock` | 2356–2360 | 5 | 请求与配对会话 | `pairLockLeft` | `pairLockLeft` | `schedulePairTick`、`stopPairLock` | `applyPairFailure` | 是 | 2 |
| `schedulePairTick` | 2361–2369 | 9 | 请求与配对会话 | `pairLockLeft`(2) | `pairErr`、`pairLockLeft`、`pairTickTimer`(2) | `renderPair` | `beginPairLock` | 否 | 0 |
| `stopPairLock` | 2370–2374 | 5 | 请求与配对会话 | `pairTickTimer`(2) | `pairLockLeft`、`pairTickTimer` | — | `beginPairLock`、`onNeedPair`、`pair`(2) | 否 | 0 |
| `applyPairFailure` | 2377–2390 | 14 | 请求与配对会话 | — | — | `beginPairLock`、`setPairError`(3) | `pair` | 否 | 0 |
| `pair` | 2392–2428 | 37 | 请求与配对会话 | `pairing` | `csrf`、`pairErr`(2)、`pairOkPending`、`paired`、`pairing`(2) | `api`、`applyPairFailure`、`poll`、`renderPair`(2)、`setPairError`(2)、`stopPairLock`(2) | `wire`(2) | 是 | 2 |
| `poll` | 2431–2460 | 30 | 请求与配对会话 | `csrf`、`flying`、`seq` | `backoff`、`csrf`、`flying`(2)、`lastOkAt`、`paired` | `api`、`clearStaleBanner`、`ingest`、`onForbidden`、`onNeedPair`、`onPollFail`(2)、`readCookie`、`refreshControls`(2)、`renderItems`、`renderPlan`、`schedule`、`scheduleTick` | `beginRelogin`(2)、`cancelPendingStart`、`cancelRelogin`、`cancelTask`、`ingestRelogin`、`pair`、`probeExistingSession`、`schedule`、`startPlan`、`stopPlan`、`submitRelogin`(3)、`tickClock`、`tickRowLeft`、`wire`(4) | 是 | 39 |
| `onPollFail` | 2461–2465 | 5 | 请求与配对会话 | `backoff`、`offlineTries` | `backoff`、`offlineTries` | — | `poll`(2) | 否 | 0 |
| `onNeedPair` | 2466–2477 | 12 | 请求与配对会话 | `pollTimer`(2)、`tickTimer`(2) | `paired`、`pollTimer`、`tickTimer` | `renderPair`、`stopPairLock` | `api`、`poll` | 否 | 0 |
| `onForbidden` | 2481–2489 | 9 | 请求与配对会话 | `backoff` | `backoff`、`csrf` | `readCookie`、`setBanner` | `api`、`poll` | 否 | 0 |
| `schedule` | 2492–2498 | 7 | 请求与配对会话 | `flying`、`paired`、`pollTimer`(2) | `pollTimer`(2) | `poll` | `poll` | 否 | 0 |
| `scheduleTick` | 2502–2512 | 11 | 摄入与渲染 | `paired`、`tickTimer`(2) | `tickTimer`(3) | `tickClock` | `poll` | 是 | 0 |
| `tickClock` | 2513–2547 | 35 | 摄入与渲染 | `busy`、`clock`、`filter`、`items`、`paired`、`selected`、`termsOk`、`tickMark` | `clock`、`tickMark` | `poll`、`tickBoardLed`、`tickRowLeft` | `scheduleTick` | 是 | 8 |
| `tickBoardLed` | 2549–2582 | 34 | 摄入与渲染 | `busy`(2)、`flying`、`lastOkText`、`pending`(3)、`plan`(2)、`termsOk` | — | — | `tickClock` | 否 | 0 |
| `tickRowLeft` | 2584–2612 | 29 | 摄入与渲染 | `paired` | — | `poll` | `tickClock` | 否 | 0 |
| `probeExistingSession` | 2615–2620 | 6 | 请求与配对会话 | `probed` | `probed` | `poll`、`readCookie` | `wire` | 否 | 0 |
| `ingest` | 2621–2721 | 101 | 摄入与渲染 | `clock`(2)、`dismissedPlanId`、`items`(2)、`pending`(2)、`retryDirty`、`retryHydrated`、`seenEventSeq`(3)、`selected`(3)、`seq`(2)、`sheetId` | `busy`、`clockState`、`items`、`lastOkText`、`login`、`notice`、`pcListError`、`plan`、`reloginSetup`、`retry`、`retryHydrated`、`retryOptions`、`seenEventSeq`(3)、`selected`、`seq`(3)、`termsOk` | `addLog`、`closeSheet`、`fillRetryOptions`、`ingestRelogin`(2)、`reconcile`、`renderReview` | `poll` | 是 | 65 |
| `startPlan` | 2724–2755 | 32 | 计划操作 | `pending`(4)、`retry`(2)、`selected` | `listOpen`、`notice`、`pending`(3) | `canWrite`、`poll`、`postAction`、`refreshControls`(2)、`setBanner`(3) | `wire` | 是 | 10 |
| `reconcile` | 2756–2784 | 29 | 计划操作 | `pending`(2)、`reconciling` | `reconciling`(2) | `postAction`、`refreshControls`、`setBanner`(3) | `ingest` | 是 | 1 |
| `cancelPendingStart` | 2785–2811 | 27 | 计划操作 | `cancelingStart`、`paired`、`pending`(3) | `cancelingStart`(2) | `poll`、`postAction`、`refreshControls`、`setBanner`、`showSheetError` | `onConfirmYes` | 是 | 2 |
| `stopPlan` | 2812–2824 | 13 | 计划操作 | `plan`(2) | — | `poll`、`postAction`、`showSheetError` | `onConfirmYes` | 否 | 0 |
| `showComputerWindow` | 2826–2833 | 8 | 计划操作 | — | — | `addLog`(2)、`postAction` | `wire` | 是 | 0 |
| `cancelTask` | 2839–2852 | 14 | 计划操作 | `plan`(4) | — | `poll`、`postAction`、`showSheetError` | `onConfirmYes` | 否 | 0 |
| `reselectFailed` | 2858–2877 | 20 | 计划操作 | `items`(2)、`plan`(4) | `dismissedPlanId`、`listOpen`、`notice`、`plan`、`selected` | `addLog`、`renderItems`、`renderPlan` | `wire` | 否 | 0 |
| `finishPlanView` | 2878–2886 | 9 | 计划操作 | `plan`(2) | `dismissedPlanId`、`listOpen`、`notice`、`plan`、`selected` | `renderItems`、`renderPlan` | `wire` | 否 | 0 |
| `saveRetry` | 2887–2894 | 8 | 计划操作 | `retry`(2) | `retryDirty` | `addLog`、`postAction` | `wire`(2) | 否 | 0 |
| `fillRetryOptions` | 2895–2905 | 11 | 计划操作 | `retry` | — | — | `ingest` | 否 | 0 |
| `renderReview` | 2911–2953 | 43 | 计划操作 | `items`、`selected` | — | — | `ingest`、`openReview`、`removeFromReview` | 是 | 0 |
| `removeFromReview` | 2957–2964 | 8 | 计划操作 | `items`、`selected`(2) | `notice`、`selected` | `closeSheet`、`renderItems`、`renderReview` | `wire` | 否 | 0 |
| `openReview` | 2965–2969 | 5 | 计划操作 | — | — | `openSheet`、`renderReview` | `wire` | 否 | 0 |
| `endReloginControls` | 2975–2978 | 4 | 重新登录 | — | — | — | `ingestRelogin`(4) | 否 | 0 |
| `ingestRelogin` | 2979–3068 | 90 | 重新登录 | `busy`、`challenge` | `challenge`(5)、`flow`、`reloginStarting`、`reloginSubmitting`(8) | `endReloginControls`(4)、`poll`、`refreshControls`(4) | `ingest`(2) | 否 | 0 |
| `beginRelogin` | 3069–3119 | 51 | 重新登录 | `reloginStarting` | `relConfirm`、`relEnteredAcct`(2)、`relSavedChoice`(2)、`reloginStarting`(3) | `canWrite`、`poll`(2)、`postAction`、`refreshControls`(5)、`setBanner` | `refreshRelogin`、`wire`(2) | 是 | 11 |
| `submitRelogin` | 3120–3165 | 46 | 重新登录 | `challenge`(6)、`flow`(2) | `reloginSubmitting`(2) | `api`、`poll`(3)、`refreshControls`(2) | `wire` | 是 | 1 |
| `cancelRelogin` | 3166–3183 | 18 | 重新登录 | `flow` | `challenge` | `addLog`、`poll`、`postAction` | `refreshRelogin`、`wire` | 是 | 1 |
| `refreshRelogin` | 3185–3190 | 6 | 重新登录 | — | — | `beginRelogin`、`cancelRelogin` | `wire` | 是 | 1 |
| `wire` | 3192–3354 | 163 | 外壳与接线 | `busy`、`items`、`lastOkAt`、`listOpen`、`login`、`nowMs`、`paired`(2)、`pending`(2)、`pickId`(2)、`pollTimer`(4)、`selected`、`tickTimer`(4) | `filter`(4)、`listOpen`、`notice`、`pairErr`、`pairOkPending`、`pollTimer`(2)、`relConfirm`、`retry`(2)、`retryDirty`(2)、`selected`、`tickTimer`(2) | `askConfirm`(2)、`beginRelogin`(2)、`cancelRelogin`、`closeSheet`(8)、`finishPlanView`、`onConfirmYes`、`openRelogin`(3)、`openReview`、`openSheet`、`pair`(2)、`poll`(4)、`probeExistingSession`、`refreshControls`(3)、`refreshRelogin`、`removeFromReview`、`renderAlerts`、`renderItems`(6)、`renderPair`(2)、`reselectFailed`、`saveRetry`(2)、`showComputerWindow`、`startPlan`、`submitRelogin`、`toggleSearch` | — | 是 | 0 |
| **合计** | **67 个函数** | **1793** | **5 组** | **167 关系 / 270 次** | **106 关系 / 146 次** | — | — | **26 个** | **219 次** |

## 表二 model 字段

| 字段名 | 声明行 | 写它的函数及所属组 | 读它的函数及所属组 | 被两个及以上组写 |
|---|---:|---|---|---|
| `backoff` | 1393 | `onForbidden`[请求与配对会话]、`onPollFail`[请求与配对会话]、`poll`[请求与配对会话] | `onForbidden`[请求与配对会话]、`onPollFail`[请求与配对会话] | 否 |
| `bannerKind` | 1398 | `setBanner`[摄入与渲染] | `clearStaleBanner`[摄入与渲染]、`setBanner`[摄入与渲染] | 否 |
| `busy` | 1390 | `ingest`[摄入与渲染] | `ingestRelogin`[重新登录]、`refreshControls`[摄入与渲染]、`renderBar`[摄入与渲染]×4、`renderBoard`[摄入与渲染]×2、`renderItems`[摄入与渲染]×5、`renderPlan`[摄入与渲染]、`renderRelogin`[重新登录]、`renderTasks`[摄入与渲染]×2、`tickBoardLed`[摄入与渲染]×2、`tickClock`[摄入与渲染]、`wire`[外壳与接线] | 否 |
| `cancelingStart` | 未声明（动态） | `cancelPendingStart`[计划操作]×2 | `cancelPendingStart`[计划操作] | 否 |
| `challenge` | 1394 | `cancelRelogin`[重新登录]、`ingestRelogin`[重新登录]×5 | `ingestRelogin`[重新登录]、`refreshControls`[摄入与渲染]×2、`submitRelogin`[重新登录]×6 | 否 |
| `clock` | 1400 | `tickClock`[摄入与渲染] | `ingest`[摄入与渲染]×2、`tickClock`[摄入与渲染] | 否 |
| `clockState` | 1403 | `ingest`[摄入与渲染] | `renderAlerts`[摄入与渲染]、`renderBar`[摄入与渲染] | 否 |
| `confirm` | 1411 | `askConfirm`[外壳与接线]、`closeSheet`[外壳与接线] | `onConfirmYes`[外壳与接线] | 否 |
| `csrf` | 1396 | `api`[请求与配对会话]、`onForbidden`[请求与配对会话]、`pair`[请求与配对会话]、`poll`[请求与配对会话] | `api`[请求与配对会话]×2、`poll`[请求与配对会话] | 否 |
| `dismissedPlanId` | 1421 | `finishPlanView`[计划操作]、`reselectFailed`[计划操作] | `ingest`[摄入与渲染] | 否 |
| `filter` | 1388 | `goSigned`[摄入与渲染]、`toggleSearch`[摄入与渲染]、`wire`[外壳与接线]×4 | `goSigned`[摄入与渲染]、`renderItems`[摄入与渲染]、`tickClock`[摄入与渲染] | 是 |
| `flashId` | 1400 | `goSigned`[摄入与渲染]×2 | `buildRow`[摄入与渲染] | 否 |
| `flow` | 1394 | `ingestRelogin`[重新登录] | `cancelRelogin`[重新登录]、`openRelogin`[重新登录]、`refreshControls`[摄入与渲染]×3、`renderAlerts`[摄入与渲染]、`renderBar`[摄入与渲染]×2、`renderRelogin`[重新登录]、`sheetBusy`[外壳与接线]、`submitRelogin`[重新登录]×2 | 否 |
| `flying` | 1398 | `poll`[请求与配对会话]×2 | `poll`[请求与配对会话]、`refreshControls`[摄入与渲染]×2、`renderBar`[摄入与渲染]、`renderBoard`[摄入与渲染]、`schedule`[请求与配对会话]、`syncOffline`[摄入与渲染]、`tickBoardLed`[摄入与渲染] | 否 |
| `items` | 1388 | `ingest`[摄入与渲染] | `buildRow`[摄入与渲染]、`goSigned`[摄入与渲染]、`ingest`[摄入与渲染]×2、`refreshControls`[摄入与渲染]、`removeFromReview`[计划操作]、`renderBar`[摄入与渲染]、`renderItems`[摄入与渲染]×4、`renderReview`[计划操作]、`reselectFailed`[计划操作]×2、`tickClock`[摄入与渲染]、`wire`[外壳与接线] | 否 |
| `lastOkAt` | 1393 | `poll`[请求与配对会话] | `canWrite`[摄入与渲染]、`refreshControls`[摄入与渲染]、`wire`[外壳与接线] | 否 |
| `lastOkText` | 1403 | `ingest`[摄入与渲染] | `renderBoard`[摄入与渲染]、`tickBoardLed`[摄入与渲染] | 否 |
| `listOpen` | 1409 | `finishPlanView`[计划操作]、`reselectFailed`[计划操作]、`startPlan`[计划操作]、`wire`[外壳与接线] | `renderItems`[摄入与渲染]×3、`wire`[外壳与接线] | 是 |
| `login` | 1392 | `ingest`[摄入与渲染] | `refreshControls`[摄入与渲染]、`renderAlerts`[摄入与渲染]、`renderBar`[摄入与渲染]×4、`wire`[外壳与接线] | 否 |
| `notice` | 1405 | `buildRow`[摄入与渲染]、`finishPlanView`[计划操作]、`ingest`[摄入与渲染]、`removeFromReview`[计划操作]、`reselectFailed`[计划操作]、`startPlan`[计划操作]、`wire`[外壳与接线] | `renderItems`[摄入与渲染]×2 | 是 |
| `nowMs` | 1393 | `canWrite`[摄入与渲染]、`refreshControls`[摄入与渲染]、`renderItems`[摄入与渲染] | `canWrite`[摄入与渲染]、`refreshControls`[摄入与渲染]、`renderItems`[摄入与渲染]、`wire`[外壳与接线] | 否 |
| `offlineTries` | 1395 | `onPollFail`[请求与配对会话]、`syncOffline`[摄入与渲染] | `onPollFail`[请求与配对会话]、`syncOffline`[摄入与渲染] | 是 |
| `pairErr` | 1418 | `pair`[请求与配对会话]×2、`schedulePairTick`[请求与配对会话]、`setPairError`[请求与配对会话]、`wire`[外壳与接线] | `renderPair`[请求与配对会话] | 是 |
| `pairLockLeft` | 1418 | `beginPairLock`[请求与配对会话]、`schedulePairTick`[请求与配对会话]、`stopPairLock`[请求与配对会话] | `beginPairLock`[请求与配对会话]、`renderPair`[请求与配对会话]、`schedulePairTick`[请求与配对会话]×2 | 否 |
| `pairOkPending` | 1418 | `pair`[请求与配对会话]、`wire`[外壳与接线] | `renderAlerts`[摄入与渲染] | 是 |
| `pairTickTimer` | 1418 | `schedulePairTick`[请求与配对会话]×2、`stopPairLock`[请求与配对会话] | `stopPairLock`[请求与配对会话]×2 | 否 |
| `paired` | 1398 | `onNeedPair`[请求与配对会话]、`pair`[请求与配对会话]、`poll`[请求与配对会话] | `cancelPendingStart`[计划操作]、`schedule`[请求与配对会话]、`scheduleTick`[摄入与渲染]、`tickClock`[摄入与渲染]、`tickRowLeft`[摄入与渲染]、`wire`[外壳与接线]×2 | 否 |
| `pairing` | 1418 | `pair`[请求与配对会话]×2 | `pair`[请求与配对会话] | 否 |
| `pcListError` | 1403 | `ingest`[摄入与渲染] | `renderAlerts`[摄入与渲染]×2、`renderBar`[摄入与渲染] | 否 |
| `pending` | 1396 | `startPlan`[计划操作]×3 | `cancelPendingStart`[计划操作]×3、`ingest`[摄入与渲染]×2、`reconcile`[计划操作]×2、`refreshControls`[摄入与渲染]×2、`renderBar`[摄入与渲染]×5、`renderBoard`[摄入与渲染]×3、`renderItems`[摄入与渲染]×2、`startPlan`[计划操作]×4、`tickBoardLed`[摄入与渲染]×3、`wire`[外壳与接线]×2 | 否 |
| `pickId` | 1405 | `renderBoard`[摄入与渲染]×2 | `wire`[外壳与接线]×2 | 否 |
| `plan` | 未声明（动态） | `finishPlanView`[计划操作]、`ingest`[摄入与渲染]、`reselectFailed`[计划操作] | `cancelTask`[计划操作]×4、`finishPlanView`[计划操作]×2、`renderBar`[摄入与渲染]×3、`renderBoard`[摄入与渲染]×2、`renderItems`[摄入与渲染]、`renderTasks`[摄入与渲染]×3、`reselectFailed`[计划操作]×4、`stopPlan`[计划操作]×2、`tickBoardLed`[摄入与渲染]×2 | 是 |
| `pollTimer` | 1396 | `onNeedPair`[请求与配对会话]、`schedule`[请求与配对会话]×2、`wire`[外壳与接线]×2 | `onNeedPair`[请求与配对会话]×2、`schedule`[请求与配对会话]×2、`wire`[外壳与接线]×4 | 是 |
| `probed` | 1398 | `probeExistingSession`[请求与配对会话] | `probeExistingSession`[请求与配对会话] | 否 |
| `reconciling` | 未声明（动态） | `reconcile`[计划操作]×2 | `reconcile`[计划操作] | 否 |
| `relConfirm` | 1414 | `beginRelogin`[重新登录]、`closeSheet`[外壳与接线]、`openRelogin`[重新登录]、`wire`[外壳与接线] | `renderRelogin`[重新登录] | 是 |
| `relEnteredAcct` | 1414 | `beginRelogin`[重新登录]×2 | `renderRelogin`[重新登录] | 否 |
| `relSavedChoice` | 1414 | `beginRelogin`[重新登录]×2 | `renderRelogin`[重新登录] | 否 |
| `reloginSetup` | 未声明（动态） | `ingest`[摄入与渲染] | `openRelogin`[重新登录]、`refreshControls`[摄入与渲染]×4、`renderRelogin`[重新登录] | 否 |
| `reloginStarting` | 1395 | `beginRelogin`[重新登录]×3、`ingestRelogin`[重新登录] | `beginRelogin`[重新登录]、`refreshControls`[摄入与渲染]×2、`renderRelogin`[重新登录] | 否 |
| `reloginSubmitting` | 1394 | `ingestRelogin`[重新登录]×8、`submitRelogin`[重新登录]×2 | `renderRelogin`[重新登录]、`sheetBusy`[外壳与接线]×2 | 否 |
| `retry` | 1389 | `ingest`[摄入与渲染]、`wire`[外壳与接线]×2 | `fillRetryOptions`[计划操作]、`refreshControls`[摄入与渲染]、`saveRetry`[计划操作]×2、`startPlan`[计划操作]×2 | 是 |
| `retryDirty` | 1389 | `saveRetry`[计划操作]、`wire`[外壳与接线]×2 | `ingest`[摄入与渲染] | 是 |
| `retryHydrated` | 1389 | `ingest`[摄入与渲染] | `ingest`[摄入与渲染] | 否 |
| `retryOptions` | 未声明（动态） | `ingest`[摄入与渲染] | — | 否 |
| `searchOpen` | 1405 | `toggleSearch`[摄入与渲染] | `renderItems`[摄入与渲染]、`toggleSearch`[摄入与渲染]×4 | 否 |
| `seenEventSeq` | 1390 | `ingest`[摄入与渲染]×3 | `ingest`[摄入与渲染]×3 | 否 |
| `selected` | 1388 | `buildRow`[摄入与渲染]、`finishPlanView`[计划操作]、`ingest`[摄入与渲染]、`removeFromReview`[计划操作]、`reselectFailed`[计划操作]、`wire`[外壳与接线] | `buildRow`[摄入与渲染]、`ingest`[摄入与渲染]×3、`refreshControls`[摄入与渲染]、`removeFromReview`[计划操作]×2、`renderBar`[摄入与渲染]×2、`renderItems`[摄入与渲染]、`renderReview`[计划操作]、`startPlan`[计划操作]、`tickClock`[摄入与渲染]、`wire`[外壳与接线] | 是 |
| `seq` | 1393 | `ingest`[摄入与渲染]×3 | `ingest`[摄入与渲染]×2、`poll`[请求与配对会话] | 否 |
| `sheetId` | 1407 | `closeSheet`[外壳与接线]、`openSheet`[外壳与接线] | `askConfirm`[外壳与接线]、`closeSheet`[外壳与接线]、`ingest`[摄入与渲染]、`openRelogin`[重新登录]×2、`openSheet`[外壳与接线]、`refreshControls`[摄入与渲染]、`showSheetError`[外壳与接线] | 否 |
| `sheetOpener` | 1407 | `closeSheet`[外壳与接线]、`openSheet`[外壳与接线] | `closeSheet`[外壳与接线] | 否 |
| `termsOk` | 未声明（动态） | `ingest`[摄入与渲染] | `refreshControls`[摄入与渲染]×4、`renderAlerts`[摄入与渲染]、`renderBar`[摄入与渲染]、`renderBoard`[摄入与渲染]、`renderItems`[摄入与渲染]×2、`tickBoardLed`[摄入与渲染]、`tickClock`[摄入与渲染] | 否 |
| `tickMark` | 未声明（动态） | `tickClock`[摄入与渲染] | `tickClock`[摄入与渲染] | 否 |
| `tickTimer` | 未声明（动态） | `onNeedPair`[请求与配对会话]、`scheduleTick`[摄入与渲染]×3、`wire`[外壳与接线]×2 | `onNeedPair`[请求与配对会话]×2、`scheduleTick`[摄入与渲染]×2、`wire`[外壳与接线]×4 | 是 |
| `whyId` | 1400 | `goSigned`[摄入与渲染] | `buildRow`[摄入与渲染] | 否 |
| **合计** | **55 个字段** | **106 关系 / 146 次** | **167 关系 / 270 次** | **13 个** |

> 注：P1 口径只计 `model.<字段>` 直接访问；另有两个经 `PhoneModel` 传入 `model` 引用的间接写：`ingest` 调 `PhoneModel.setClock(model, ...)` 写 `model.clock`、`buildRow` 调 `PhoneModel.toggleWhy(model, ...)` 写 `model.whyId`。

## 表三 组间调用

| 调用方组 | 被调方组 | 函数对 | 次数 |
|---|---|---|---:|
| 外壳与接线 | 摄入与渲染 | `wire` → `refreshControls` | 3 |
| 外壳与接线 | 摄入与渲染 | `wire` → `renderAlerts` | 1 |
| 外壳与接线 | 摄入与渲染 | `wire` → `renderItems` | 6 |
| 外壳与接线 | 摄入与渲染 | `wire` → `toggleSearch` | 1 |
| 外壳与接线 | 计划操作 | `onConfirmYes` → `cancelPendingStart` | 1 |
| 外壳与接线 | 计划操作 | `onConfirmYes` → `cancelTask` | 1 |
| 外壳与接线 | 计划操作 | `onConfirmYes` → `stopPlan` | 1 |
| 外壳与接线 | 计划操作 | `wire` → `finishPlanView` | 1 |
| 外壳与接线 | 计划操作 | `wire` → `openReview` | 1 |
| 外壳与接线 | 计划操作 | `wire` → `removeFromReview` | 1 |
| 外壳与接线 | 计划操作 | `wire` → `reselectFailed` | 1 |
| 外壳与接线 | 计划操作 | `wire` → `saveRetry` | 2 |
| 外壳与接线 | 计划操作 | `wire` → `showComputerWindow` | 1 |
| 外壳与接线 | 计划操作 | `wire` → `startPlan` | 1 |
| 外壳与接线 | 请求与配对会话 | `wire` → `pair` | 2 |
| 外壳与接线 | 请求与配对会话 | `wire` → `poll` | 4 |
| 外壳与接线 | 请求与配对会话 | `wire` → `probeExistingSession` | 1 |
| 外壳与接线 | 请求与配对会话 | `wire` → `renderPair` | 2 |
| 外壳与接线 | 重新登录 | `wire` → `beginRelogin` | 2 |
| 外壳与接线 | 重新登录 | `wire` → `cancelRelogin` | 1 |
| 外壳与接线 | 重新登录 | `wire` → `openRelogin` | 3 |
| 外壳与接线 | 重新登录 | `wire` → `refreshRelogin` | 1 |
| 外壳与接线 | 重新登录 | `wire` → `submitRelogin` | 1 |
| 摄入与渲染 | 外壳与接线 | `ingest` → `closeSheet` | 1 |
| 摄入与渲染 | 外壳与接线 | `refreshControls` → `sheetBusy` | 1 |
| 摄入与渲染 | 外壳与接线 | `renderTasks` → `askConfirm` | 1 |
| 摄入与渲染 | 计划操作 | `ingest` → `fillRetryOptions` | 1 |
| 摄入与渲染 | 计划操作 | `ingest` → `reconcile` | 1 |
| 摄入与渲染 | 计划操作 | `ingest` → `renderReview` | 1 |
| 摄入与渲染 | 请求与配对会话 | `tickClock` → `poll` | 1 |
| 摄入与渲染 | 请求与配对会话 | `tickRowLeft` → `poll` | 1 |
| 摄入与渲染 | 重新登录 | `ingest` → `ingestRelogin` | 2 |
| 摄入与渲染 | 重新登录 | `refreshControls` → `renderRelogin` | 1 |
| 计划操作 | 外壳与接线 | `cancelPendingStart` → `showSheetError` | 1 |
| 计划操作 | 外壳与接线 | `cancelTask` → `showSheetError` | 1 |
| 计划操作 | 外壳与接线 | `openReview` → `openSheet` | 1 |
| 计划操作 | 外壳与接线 | `removeFromReview` → `closeSheet` | 1 |
| 计划操作 | 外壳与接线 | `stopPlan` → `showSheetError` | 1 |
| 计划操作 | 摄入与渲染 | `cancelPendingStart` → `refreshControls` | 1 |
| 计划操作 | 摄入与渲染 | `cancelPendingStart` → `setBanner` | 1 |
| 计划操作 | 摄入与渲染 | `finishPlanView` → `renderItems` | 1 |
| 计划操作 | 摄入与渲染 | `finishPlanView` → `renderPlan` | 1 |
| 计划操作 | 摄入与渲染 | `reconcile` → `refreshControls` | 1 |
| 计划操作 | 摄入与渲染 | `reconcile` → `setBanner` | 3 |
| 计划操作 | 摄入与渲染 | `removeFromReview` → `renderItems` | 1 |
| 计划操作 | 摄入与渲染 | `reselectFailed` → `addLog` | 1 |
| 计划操作 | 摄入与渲染 | `reselectFailed` → `renderItems` | 1 |
| 计划操作 | 摄入与渲染 | `reselectFailed` → `renderPlan` | 1 |
| 计划操作 | 摄入与渲染 | `saveRetry` → `addLog` | 1 |
| 计划操作 | 摄入与渲染 | `showComputerWindow` → `addLog` | 2 |
| 计划操作 | 摄入与渲染 | `startPlan` → `canWrite` | 1 |
| 计划操作 | 摄入与渲染 | `startPlan` → `refreshControls` | 2 |
| 计划操作 | 摄入与渲染 | `startPlan` → `setBanner` | 3 |
| 计划操作 | 请求与配对会话 | `cancelPendingStart` → `poll` | 1 |
| 计划操作 | 请求与配对会话 | `cancelPendingStart` → `postAction` | 1 |
| 计划操作 | 请求与配对会话 | `cancelTask` → `poll` | 1 |
| 计划操作 | 请求与配对会话 | `cancelTask` → `postAction` | 1 |
| 计划操作 | 请求与配对会话 | `reconcile` → `postAction` | 1 |
| 计划操作 | 请求与配对会话 | `saveRetry` → `postAction` | 1 |
| 计划操作 | 请求与配对会话 | `showComputerWindow` → `postAction` | 1 |
| 计划操作 | 请求与配对会话 | `startPlan` → `poll` | 1 |
| 计划操作 | 请求与配对会话 | `startPlan` → `postAction` | 1 |
| 计划操作 | 请求与配对会话 | `stopPlan` → `poll` | 1 |
| 计划操作 | 请求与配对会话 | `stopPlan` → `postAction` | 1 |
| 请求与配对会话 | 外壳与接线 | `postAction` → `showSheetError` | 1 |
| 请求与配对会话 | 摄入与渲染 | `onForbidden` → `setBanner` | 1 |
| 请求与配对会话 | 摄入与渲染 | `poll` → `clearStaleBanner` | 1 |
| 请求与配对会话 | 摄入与渲染 | `poll` → `ingest` | 1 |
| 请求与配对会话 | 摄入与渲染 | `poll` → `refreshControls` | 2 |
| 请求与配对会话 | 摄入与渲染 | `poll` → `renderItems` | 1 |
| 请求与配对会话 | 摄入与渲染 | `poll` → `renderPlan` | 1 |
| 请求与配对会话 | 摄入与渲染 | `poll` → `scheduleTick` | 1 |
| 重新登录 | 外壳与接线 | `openRelogin` → `closeSheet` | 1 |
| 重新登录 | 外壳与接线 | `openRelogin` → `openSheet` | 1 |
| 重新登录 | 摄入与渲染 | `beginRelogin` → `canWrite` | 1 |
| 重新登录 | 摄入与渲染 | `beginRelogin` → `refreshControls` | 5 |
| 重新登录 | 摄入与渲染 | `beginRelogin` → `setBanner` | 1 |
| 重新登录 | 摄入与渲染 | `cancelRelogin` → `addLog` | 1 |
| 重新登录 | 摄入与渲染 | `ingestRelogin` → `refreshControls` | 4 |
| 重新登录 | 摄入与渲染 | `submitRelogin` → `refreshControls` | 2 |
| 重新登录 | 请求与配对会话 | `beginRelogin` → `poll` | 2 |
| 重新登录 | 请求与配对会话 | `beginRelogin` → `postAction` | 1 |
| 重新登录 | 请求与配对会话 | `cancelRelogin` → `poll` | 1 |
| 重新登录 | 请求与配对会话 | `cancelRelogin` → `postAction` | 1 |
| 重新登录 | 请求与配对会话 | `ingestRelogin` → `poll` | 1 |
| 重新登录 | 请求与配对会话 | `submitRelogin` → `api` | 1 |
| 重新登录 | 请求与配对会话 | `submitRelogin` → `poll` | 3 |
| **合计** | **87 对跨组函数对** | — | **122 次** |

## 表四 PhoneModel 成员

| 名字 | 起止行 | 行数 | 被哪些组的 DOM 函数用 | test_phone_ui.py 出现次数 |
|---|---:|---:|---|---:|
| `newRequestId` | 9–15 | 7 | 计划操作 | 1 |
| `filterItems` | 18–39 | 22 | — | 5 |
| `openEpochOf` | 43–53 | 11 | — | 1 |
| `bucketOf` | 57–66 | 10 | — | 4 |
| `nextBackoff` | 69–72 | 4 | 请求与配对会话 | 1 |
| `staleAfterMs` | 77–77 | 1 | — | 3 |
| `isStale` | 78–81 | 4 | 外壳与接线、摄入与渲染 | 3 |
| `IDLE_SYNC_MS` | 85–85 | 1 | — | 0 |
| `ACTIVE_SYNC_MS` | 86–86 | 1 | — | 0 |
| `reloginBusy` | 89–94 | 6 | 外壳与接线 | 0 |
| `isActive` | 96–102 | 7 | — | 0 |
| `syncDelay` | 104–109 | 6 | 请求与配对会话 | 0 |
| `nextTickDelay` | 113–118 | 6 | 摄入与渲染 | 5 |
| `canStart` | 125–132 | 8 | 摄入与渲染 | 10 |
| `loginRaw` | 136–139 | 4 | 摄入与渲染 | 0 |
| `loginRecovering` | 143–148 | 6 | 摄入与渲染 | 0 |
| `loginExpired` | 151–154 | 4 | 外壳与接线、摄入与渲染 | 9 |
| `canSubmitRelogin` | 155–163 | 9 | 摄入与渲染、重新登录 | 6 |
| `challengeExpired` | 166–168 | 3 | — | 2 |
| `matchesChallenge` | 169–172 | 4 | 重新登录 | 3 |
| `RETRY_FALLBACK_S` | 175–175 | 1 | — | 0 |
| `taskDeadline` | 176–189 | 14 | — | 6 |
| `retryHint` | 193–197 | 5 | 摄入与渲染 | 3 |
| `startPending` | 202–208 | 7 | 计划操作 | 6 |
| `itemTitle` | 211–213 | 3 | — | 1 |
| `itemMeta` | 214–220 | 7 | — | 1 |
| `actionable` | 222–228 | 7 | 摄入与渲染、计划操作 | 7 |
| `WJ` | 233–233 | 1 | — | 0 |
| `glue` | 234–234 | 1 | — | 0 |
| `schoolSec` | 236–245 | 10 | — | 0 |
| `pad2` | 246–246 | 1 | — | 0 |
| `absWhen` | 248–252 | 5 | — | 0 |
| `dayOf` | 253–253 | 1 | — | 0 |
| `endsAtMidnight` | 255–255 | 1 | — | 0 |
| `lastDayOf` | 256–258 | 3 | — | 0 |
| `actRange` | 260–264 | 5 | — | 0 |
| `spanDays` | 265–268 | 4 | — | 2 |
| `actSpan` | 270–280 | 11 | — | 5 |
| `mono` | 282–285 | 4 | 摄入与渲染 | 0 |
| `SLEEP_JUMP_MS` | 288–288 | 1 | — | 0 |
| `sleepJumped` | 289–293 | 5 | 摄入与渲染 | 0 |
| `setClock` | 294–303 | 10 | 摄入与渲染 | 5 |
| `businessNowS` | 304–310 | 7 | 摄入与渲染、计划操作 | 8 |
| `cancelWindowOpen` | 312–318 | 7 | — | 0 |
| `signedClash` | 321–330 | 10 | — | 2 |
| `refundFlag` | 332–337 | 6 | — | 5 |
| `rewardText` | 340–356 | 17 | — | 0 |
| `cancelNote` | 358–362 | 5 | — | 7 |
| `clashWay` | 364–378 | 15 | — | 0 |
| `whyView` | 380–408 | 29 | 摄入与渲染 | 3 |
| `toggleWhy` | 410–413 | 4 | 摄入与渲染 | 4 |
| `taskText` | 415–429 | 15 | — | 6 |
| `escape` | 430–433 | 4 | 计划操作 | 0 |
| `preStartWarnings` | 440–477 | 38 | 计划操作 | 3 |
| `connState` | 481–490 | 10 | 摄入与渲染 | 0 |
| `planSummary` | 494–504 | 11 | 摄入与渲染 | 0 |
| `hhmmss` | 514–519 | 6 | 摄入与渲染 | 0 |
| `beijingSecOf` | 521–523 | 3 | 摄入与渲染 | 0 |
| `hms` | 524–528 | 5 | — | 0 |
| `hmsAt` | 530–534 | 5 | — | 0 |
| `leftCn` | 536–543 | 8 | — | 6 |
| `stOf` | 548–558 | 11 | 摄入与渲染 | 0 |
| `groupKeyOf` | 562–573 | 12 | — | 0 |
| `visibleItems` | 576–585 | 10 | 摄入与渲染 | 0 |
| `overlapFirst` | 587–595 | 9 | — | 0 |
| `conflictNotice` | 597–600 | 4 | — | 0 |
| `pickItem` | 602–611 | 10 | 外壳与接线、摄入与渲染、计划操作 | 4 |
| `nextPick` | 614–624 | 11 | — | 0 |
| `rowView` | 627–679 | 53 | 摄入与渲染 | 0 |
| `draftBoard` | 683–725 | 43 | — | 5 |
| `listView` | 728–771 | 44 | 摄入与渲染 | 6 |
| `PENDING_WINDOW_MS` | 779–779 | 1 | — | 1 |
| `pendingLong` | 780–783 | 4 | 摄入与渲染 | 2 |
| `pendingBoard` | 786–796 | 11 | 摄入与渲染 | 2 |
| `taskOpenOf` | 799–801 | 3 | — | 0 |
| `taskRail` | 805–821 | 17 | — | 0 |
| `runBoard` | 829–870 | 42 | 摄入与渲染 | 12 |
| `taskCard` | 878–936 | 59 | 摄入与渲染 | 16 |
| `confirmView` | 940–957 | 18 | 外壳与接线 | 4 |
| `planFinished` | 966–972 | 7 | — | 0 |
| `resultView` | 977–1034 | 58 | 摄入与渲染 | 12 |
| `termsBoard` | 1037–1044 | 8 | 摄入与渲染 | 1 |
| `reviewBatches` | 1055–1088 | 34 | 计划操作 | 3 |
| `loginLine` | 1094–1106 | 13 | 摄入与渲染 | 3 |
| `RELOGIN_BUSY` | 1118–1122 | 5 | 重新登录 | 1 |
| `relSaveGain` | 1125–1127 | 3 | — | 0 |
| `REL_HANDOFF_AFTER` | 1132–1132 | 1 | — | 0 |
| `relHandoff` | 1133–1137 | 5 | — | 0 |
| `relNeedAcct` | 1141–1145 | 5 | 摄入与渲染 | 0 |
| `relLead` | 1148–1158 | 11 | — | 5 |
| `relCanSubmit` | 1162–1167 | 6 | 摄入与渲染、重新登录 | 6 |
| `RELBAD_TEXT` | 1170–1170 | 1 | — | 0 |
| `RELOGIN_BAD_PASSWORD_TEXT` | 1176–1177 | 2 | — | 0 |
| `reloginFailText` | 1178–1182 | 5 | 重新登录 | 0 |
| `reloginView` | 1187–1274 | 88 | 重新登录 | 0 |
| `glyphs` | 1278–1295 | 18 | — | 0 |
| `ledOf` | 1298–1318 | 21 | — | 0 |
| `pairView` | 1322–1342 | 21 | 请求与配对会话 | 5 |
| `pairTickLeft` | 1344–1347 | 4 | 请求与配对会话 | 3 |
| `pairWrongText` | 1352–1356 | 5 | 请求与配对会话 | 3 |
| `pairLockedText` | 1358–1360 | 3 | 请求与配对会话 | 1 |
| **合计** | **101 个成员** | **1122** | **50 个被 DOM 使用** | **228 次** |

## 表五 未归组的顶层名字

| 名字 | 形态 | 定义行 | 说明 |
|---|---|---:|---|
| `$` | const | 1368 | DOM 选择器快捷箭头函数 `document.getElementById(id)` |
| `REQUEST_TIMEOUT_MS` | const | 1371 | 请求超时常量 `8000` |
| `model` | const | 1386 | DOM 层闭包状态对象 |
| `SHEET_TITLES` | const | 1559 | sheet 标题映射常量 |
| `LIST_ZONES` | const | 1991 | 列表三区映射常量 |
| **合计** | **5 项** | — | — |

## 表六 页面加载现状

### index.html 的 script 标签原文

| 序号 | 标签原文 |
|---:|---|
| 1 | `<script src="app.js"></script>` |

### PHONE_STATIC 全部条目

| 路径 | 文件名 | Content-Type |
|---|---|---|
| `/` | `index.html` | `text/html; charset=utf-8` |
| `/index.html` | `index.html` | `text/html; charset=utf-8` |
| `/styles.css` | `styles.css` | `text/css; charset=utf-8` |
| `/app.js` | `app.js` | `text/javascript; charset=utf-8` |
| `/favicon.ico` | `favicon.ico` | `image/x-icon` |
| `/apple-touch-icon.png` | `apple-touch-icon.png` | `image/png` |
| **合计** | **1 条 script / 6 条静态路径** | — |
