# 手机页审计补充（phone.md）

基线：git show 7e2d31c
仅读 local/ui/m/app.js 等基线文件，不读工作区 local/**。

---

## 第一部分：model 字段状态追踪

### 总表

model 定义位置：local/ui/m/app.js 行 1386-1422（初始化 47 个字段）+ 动态写入 8 个字段 = 共 **55** 个顶层字段。

| # | 字段 | 类型 | 行号 | 所有写入位置 | 所有读取位置 | 退出路径清理 |
|---|------|------|------|-------------|-------------|-------------|
| 1 | items | Array | 1388 | **L2636** ingest: `model.items = state.activities` | **L2002** listView, **L2050** signedCount, **L1787** pickItem, **L2078** reselectFailed, **L2241** renderTasks, **L2418** goSigned, **L617** nextPick 等 | 不清理，是持久状态 |
| 2 | selected | Array | 1388 | **L1788** pickItem, **L2639** ingest: `model.selected = before.filter(...)`, **L2863/2873** reselect/finish, **L2951** removeFromReview, **L3291** toggle | **L1393** startPlan, **L1520** canSubmitRelogin, **L1787** pickItem, **L2639** ingest 对比, **L2863** reselect | finishPlanView/reselectFailed 设 [], startPlan 清空冲突 notice |
| 3 | filter | {q,status,time} | 1388 | **L1973** goSigned, **L2210** toggleSearch: `model.filter.q=""` | **L1787** pickItem, **L2002** listView, **L2210** toggleSearch, **L1971** goSigned 前 check | 不清理 |
| 4 | retry | {retry_for_s, max_attempts} | 1389 | **L2668** ingest: hydrated 时从 state.retry_policy 覆盖 | **L1537** refreshControls: retryHint, **L2882** saveRetry, **L2736** startPlan payload | 不清理 |
| 5 | retryHydrated | Boolean | 1389 | **L2672** ingest: `model.retryHydrated = true` | **L2667** ingest 条件, **L1535** refreshControls | 不清理，一旦 true 保持 |
| 6 | retryDirty | Boolean | 1389 | **L2885** saveRetry: 成功清 false; **L3313/3319**: `model.retryDirty = true` | **L2667** ingest 条件（hydrated && !dirty 才覆盖） | saveRetry 成功清 false；retry 对话框关闭设 true |
| 7 | seenEventSeq | Set | 1390 | **L2624** reset 时 clear(); **L2683** 事件处理 `seenEventSeq.add()` | **L2682** 去重判断, **L2684** 超 400 清理 | reset 时 clear；无显式退出清理 |
| 8 | busy | Boolean | 1390 | **L2665** ingest: `model.busy = state.busy` | **L1512** 隐藏 stop, **L1511** 禁用 start, **L1739** renderBar 标题, **L2001** resultView, **L2057** pending 判断, **L2224** runTip 显示 | 后端 state.busy 终态时 ingest 置 false；无前端手动置 false 路径 |
| 9 | login | Object\|null | 1392 | **L2703** ingest: `model.login = state.login` | **L136/139** PhoneModel.loginRaw/loginExpired, **L1469** renderAlerts, **L1734/1736/1737** renderBar, **L1541** loginLine | 不清理，服务端快照每次覆盖 |
| 10 | lastOkAt | Number | 1393 | **L2441** poll 成功: `model.lastOkAt = Date.now()` | **L83** isStale (connState), **L1449/1451** syncOffline, **L1502** refreshControls | 不清理 |
| 11 | nowMs | Number | 1393 | **L1496/1501** canWrite/refreshControls: `model.nowMs = Date.now()`, **L1998** renderItems | **L83** isStale, **L2213** poll 超时逻辑 | 每次 refreshControls/renderItems 重算 |
| 12 | backoff | Number | 1393 | **L2442** poll 成功: 重置为 1000; **L2464/2488/2489** onPollFail/onForbidden: nextBackoff | **L94** syncDelay 条件 | poll 成功重置为 1000；无显式退出清理 |
| 13 | seq | Number | 1393 | **L2625** reset 时置 0; **L2680** 事件处理; **L2697** payload.seq | **L2437** poll 时 `?after=` 参数 | reset 时清 0 |
| 14 | flow | Object\|null | 1394 | **L2972** ingestRelogin: `model.flow = info` | **L1469/1541** loginExpired/loginLine, **L1554** sheetBusy, **L1662** openRelogin, **L1736/1737** renderBar | 终态（success/failed/canceled）由下一次 ingestRelogin 覆盖（info.state 终态）；无显式 null 清理 |
| 15 | challenge | Object\|null | 1394 | **L3001** ingestRelogin waiting_code: `model.challenge = {...}`; **L2987/3028/3044/3055** 各终态置 null | **L1515** canSubmitRelogin, **L1516** refreshControls | 终态分支清 null；但 **relayState === "starting"/"verifying" 分支未显式清 challenge** |
| 16 | reloginSubmitting | Boolean | 1394 | **L3123** submitRelogin: `model.reloginSubmitting = true`; **L2988/2997/3004/3020/3024/3029/3045/3056** 各 ingestRelogin 分支清 false | **L131** isActive, **L134** canSubmitRelogin, **L1515** canSubmitRelogin, **L1555/1556** sheetBusy | 大部分终态清 false；**auto 分支（L2988/2989）清 false**；**ingestRelogin 未覆盖 relayState=starting/verifying 以外的分支也清**——看 L3055-3056 的 else-if 兜底清 null+false |
| 17 | reloginStarting | Boolean | 1395 | **L3065** beginRelogin: `model.reloginStarting = true`; **L3092** postAction finally 清 false; **L2989** ingestRelogin auto 分支清 false; **L3079** beginRelogin 早失败清 false | **L128** isActive, **L134** canSubmitRelogin, **L1518/1526** 按钮禁用 | beginRelogin 内部有 finally 清 false；但 **beginRelogin 没覆盖所有早 return 路径（L3067-3069 后才清，L3077 return 前没清）** —— 看完整代码 |
| 18 | offlineTries | Number | 1395 | **L2463** onPollFail: +1; **L1446** syncOffline 成功时清 0 | **L85** connState 判断, **L1454** syncOffline | poll 成功时 syncOffline 清 0 |
| 19 | pending | Object\|null | 1396 | **L2730** startPlan: `model.pending = {...}`; **L2760** reconcile done=true; **L2782** cancelPendingStart `pending.canceling=true` | **L2720** startPending 判断, **L2723/2739** startPlan 防双击, **L2749** reconcile 入口, **L2552** renderBoard pendingNow, **L2857** resultView 读取 | 终态后仍保留防双击窗口（不自动清 null）；无退出路径显式清 null |
| 20 | csrf | String | 1396 | **L2416** pair 成功: `model.csrf = String(body.csrf)`; **L2287** api POST 时: `model.csrf = fresh`; **L2433/2484**: 从 cookie 回填 | **L2288** api 请求头 | 不清理 |
| 21 | pollTimer | Number\|null | 1396 | **L2469** onNeedPair 清 null; **L2493** schedule: clearTimeout + 置 null; **L2497** schedule 设 setTimeout; **L3325/3335** visibilitychange 清 null | **L2493** schedule 入口, **L2497** 判空 | 配对丢失时清 null；无显式"退出"清理 |
| 22 | paired | Boolean | 1398 | **L2417** pair 成功 true; **L2443** poll 成功 true; **L2468** onNeedPair false | **L2444** poll 成功后切主界面, **L2496/2506** schedule/scheduleTick 门禁, **L2619** probeExistingSession, **L3240/3325/3337** visibilitychange | 401 时 onNeedPair 清 false |
| 23 | flying | Boolean | 1398 | **L2434** poll 入口 true; **L2453** poll finally false | **L2432** poll 单飞入口, **L1503/2558** connState 传参, **L1450** syncOffline, **L1459** btn-offline-retry 显示 | poll finally 清 false；无异常遗漏 |
| 24 | probed | Boolean | 1398 | **L2617** probeExistingSession: `model.probed = true` | **L2616** 入口 guard | 只写一次，无清理 |
| 25 | bannerKind | String | 1398 | **L1429** setBanner: `model.bannerKind = text ? String(kind) : ""` | **L1436** clearStaleBanner 条件 | setBanner 带 kind 清理 |
| 26 | whyId | String | 1400 | **L411** toggleWhy: 切换/清空; **L1968** goSigned: 清 "" | **L1871** buildRow 判断 | goSigned 清 ""；无其他退出清理 |
| 27 | flashId | String | 1400 | **L1980** goSigned: 设 id; **L1984** setTimeout 2s 后清 "" | **L1778** buildRow flash 判断 | setTimeout 2s 后清；无异常遗漏 |
| 28 | clock | Object\|null | 1400 | **L301** PhoneModel.setClock: `model.clock = ok ? {...} : null`; **L2523** tickClock sleep 时 `model.clock = null` | **L304** businessNowS 读取, **L2522** tickClock 判断, **L301** setClock 内部使用 | sleep 检测清 null；poll 时 setClock 覆盖 |
| 29 | clockState | String | 1403 | **L2655** ingest: `model.clockState = String(state.business_clock.state)` | **L128** canStart, **L1471** renderAlerts, **L1761** renderBar, **L442** preStartWarnings | 服务端快照每次覆盖 |
| 30 | lastOkText | String | 1403 | **L2660** ingest: 从 sampled 时刻换算 | **L2129** runBoard 参数 (EX01 离线档) | 服务端快照覆盖；`model.clock` 不可用时设 "" |
| 31 | pcListError | Object\|null | 1403 | **L2664** ingest: `model.pcListError = state.pc_list_error \|\| null` | **L1470** renderAlerts, **L1748** renderBar | 服务端快照每次覆盖（正常时 null） |
| 32 | searchOpen | Boolean | 1405 | **L2207** toggleSearch: `!model.searchOpen` | **L2060** renderItems: showSearchOpen, **L2208** toggleSearch DOM | toggleSearch 切换；无"退出"清理 |
| 33 | notice | String | 1405 | **L1789** pickItem: 设冲突提示; **L2645** ingest 清 ""; **L2731** startPlan 清 ""; **L2865/2875** reselect/finish 清 ""; **L2952** removeFromReview 清 "" | **L2089** renderItems notice 条 | 多处清 ""；无遗漏 |
| 34 | pickId | String | 1405 | **L2164/2182** renderBoard: 设 board.pickId, 结果态清 "" | **L2183** btn-pick-next 显示 | renderBoard 结果态清 ""；board.pickId 为空时也设 "" |
| 35 | sheetId | String | 1407 | **L1565** openSheet: 设 id; **L1586** closeSheet: 清 ""; **L1661** openRelogin: closeSheet(true) | **L1563/1660** openSheet/closeSheet 入口 guard, **L1581** closeSheet 入口 | closeSheet 清 ""；正常退出路径覆盖 |
| 36 | sheetOpener | Element\|null | 1407 | **L1564** openSheet: `document.activeElement`; **L1604** closeSheet: null + focus 归还 | **L1605** closeSheet focus | closeSheet 清 null |
| 37 | listOpen | Boolean | 1409 | **L2063** renderItems: 设 aria-expanded; **L2207** toggleSearch: 不影响; **L2732** startPlan: 清 false; **L2864/2874** reselect/finish: 清 false | **L2058** renderItems showList 条件, **L2063** aria-expanded, **L2064** btn-toggle-list 文案 | startPlan/reselect/finish 清 false；toggleList 函数（**L3249** 附近）切换 |
| 38 | confirm | Object\|null | 1411 | **L1681** askConfirm: `model.confirm = {kind, taskId}`; **L1601** closeSheet: 清 null | **L1691** onConfirmYes 入口, **L1564** closeSheet 清 | closeSheet 清 null |
| 39 | relConfirm | Boolean | 1414 | **L1666** openRelogin: 条件赋值; **L1602** closeSheet: false; **L3067** beginRelogin: false; **L3262** cancelRelogin: false | **L1620** renderRelogin 传参, **L1521** beginRelogin 提交判断 | closeSheet/beginRelogin/cancelRelogin 都清 false；覆盖充分 |
| 40 | relEnteredAcct | Boolean | 1414 | **L3068** beginRelogin: false; **L3087** 输了账号时 true; **L1597** closeSheet 输入清理 | **L1623** renderRelogin 传参 | beginRelogin 清 false；closeSheet 清输入但没清此标志——**L3068 在 beginRelogin 入口才清，closeSheet 没清** |
| 41 | relSavedChoice | Boolean | 1414 | **L3069** beginRelogin: false; **L3088** 勾了保存时 true | **L1624** renderRelogin 传参 | beginRelogin 清 false；**closeSheet 没清此标志（同 relEnteredAcct）** |
| 42 | pairLockLeft | Number | 1418 | **L2358** beginPairLock: 设秒数; **L2364** pairTickLeft: 递减; **L2373** stopPairLock: 清 0 | **L2330** renderPair 参数, **L2358** beginPairLock 入口 | stopPairLock 清 0 |
| 43 | pairErr | String | 1418 | **L2351** setPairError; **L2366** 锁定 tick 归零清 ""; **L2397/2420** pair 流程清 ""; **L2386/2389/2408/3192** 各分支设错误 | **L2330** renderPair | 多处清 ""；覆盖充分 |
| 44 | pairTickTimer | Number | 1418 | **L2362/2363** schedule: setTimeout/清 0; **L2371/2372** stopPairLock: clearTimeout + 清 0 | **L2371** stopPairLock 入口 | stopPairLock 清 0；覆盖 |
| 45 | pairing | Boolean | 1418 | **L2401** pair 入口 true; **L2426** pair finally false | **L2395** pair 防双击入口 | pair finally 清 false |
| 46 | pairOkPending | Boolean | 1418 | **L2418** pair 成功 true; **L3204** 告警关闭 false | **L1492** renderAlerts 判断 | 告警关闭清 false |
| 47 | dismissedPlanId | String | 1421 | **L2649** ingest 对比 plan_id; **L2852** reselectFailed: 设为已 dismiss 的 plan_id; **L2871** finishPlanView: 同上 | **L2649** ingest 入口 guard | 只设不清理（跨会话记忆） |
| 48 | **plan** | Object\|null | **L2650** | **L2650** ingest: `model.plan = state.plan`; **L2853/2872** reselect/finish: 清 null | **L1723** renderBar resultView, **L2233** renderTasks, **L2857/2871** reselect/finish | reselect/finish 清 null |
| 49 | **termsOk** | Boolean | **L2652** | **L2652** ingest: `model.termsOk = state.terms_ok` | **L1468/1475/1489/1511/1518/1525/1526/1757/2004/2052/2135/2561** 各处条件 | 服务端快照覆盖；无清理 |
| 50 | **reloginSetup** | Object\|null | **L2653** | **L2653** ingest: `model.reloginSetup = state.relogin_setup` | **L1520** canSubmitRelogin, **L1529** 账号面板隐藏, **L1541** loginLine, **L1619** renderRelogin, **L1665** openRelogin | 服务端快照覆盖；无清理 |
| 51 | **tickMark** | Object\|null | **L2521** | **L2521** tickClock: `{wallMs, monoMs}`; **L2523** sleep 时 model.clock=null 但 tickMark 未清 | **L2520** tickClock sleepJumped 输入 | 每次 tickClock 覆盖新值；**sleep 后未显式清 null** |
| 52 | **reconciling** | Boolean | **L2753** | **L2753** reconcile 入口 true; **L2773** reconcile finally false | **L2749** reconcile 入口 guard | reconcile finally 清 false |
| 53 | **cancelingStart** | Boolean | **L2783** | **L2783** cancelPendingStart 入口 true; **L2798** cancelPendingStart finally false | **L2780** cancelPendingStart 入口 guard | finally 清 false |
| 54 | **tickTimer** | Number\|null | **L2471** | **L2471** onNeedPair 清 null; **L2503** scheduleTick clearTimeout + null; **L2507** scheduleTick setTimeout; **L3327/3337** visibilitychange 清 null | **L2503** scheduleTick 入口 guard, **L2506** paired 门禁 | onNeedPair/visibilitychange 清 null |
| 55 | **retryOptions** | Object\|null | **L2675** | **L2675** ingest: `model.retryOptions = state.retry_options` | **L2676** fillRetryOptions 读取 | 服务端快照覆盖；无清理 |

### 7 类进行中状态 × 八条退出路径

**八条退出路径**：
1. 轮询成功（poll → ingest，后端状态回终态）
2. 轮询失败（onPollFail → backoff 退避，继续重试）
3. 配对成功（pair 成功后切主界面）
4. 配对丢失（onNeedPair 401）
5. 页面隐藏/显示（visibilitychange → schedule/scheduleTick）
6. 重登流程终态（relayState = success/failed/canceled）
7. 用户动作（stopPlan/cancelTask/cancelPendingStart/reselect/finish）
8. 计划运行中自然结束（state.busy=false）

#### flying（轮询单飞锁，bool）

| 退出路径 | 清理 | 证据 |
|---------|------|------|
| poll 成功 finally | ✅ 清 false | L2453 |
| poll 失败 finally | ✅ 清 false | L2453 finally 块 |
| 配对成功后 poll | ✅ 正常走 poll finally | L2424 → poll(true) |
| onNeedPair | ❌ 未显式清（但 onNeedPair 不进入 poll，flying 未被置 true） | L2466-2477 |
| visibilitychange | ❌ 不涉及 flying（flying 是同步锁） | — |
| 重登流程 | ❌ 不涉及 flying | — |
| 用户动作 | ❌ 不涉及 flying（用户动作另走 postAction） | — |
| busy 自然结束 | ❌ 不涉及 flying | — |

**结论**：flying 的生命周期完全在 poll 函数体内（单飞锁语义），所有进入 poll 的路径都有 finally 清 false。**无遗漏**。

#### pairing（配对单飞锁，bool）

| 退出路径 | 清理 | 证据 |
|---------|------|------|
| pair 成功 finally | ✅ 清 false | L2426 |
| pair 失败 finally | ✅ 清 false | L2426 finally |
| pair 网络异常 finally | ✅ 清 false | L2426 finally（catch 后也进入 finally） |
| poll 成功 | ❌ 不涉及 pairing（pair 与 poll 互斥） | — |
| 重登流程 | ❌ 不涉及 | — |
| 用户动作 | ❌ 不涉及 | — |

**结论**：pairing 生命周期也完全在 pair 函数体内。**无遗漏**。

#### pending（开始请求待对账，object|null）

| 退出路径 | 清理 | 证据 |
|---------|------|------|
| reconcile accepted | ✅ pending.done=true, outcome="accepted" | L2741-2742 |
| reconcile rejected | ✅ pending.done=true, outcome=body.state | L2760-2761 |
| reconcile canceled | ✅ pending.done=true, outcome="canceled" | L2788-2789 |
| reconcile unknown | ⚠️ pending 仍在，banner 提示 | L2769-2771 |
| reconcile 网络失败 finally | ✅ reconciling=false，但 pending 保持 | L2773 |
| cancelPendingStart 成功 | ✅ pending.done=true, outcome="canceled" | L2788-2789 |
| cancelPendingStart 失败 finally | ✅ cancelingStart=false，但 pending 保持 | L2798 |
| onNeedPair | ❌ **pending 未清**（onNeedPair 只清 paired/pollTimer/tickTimer/stopPairLock） | L2466-2477 |
| 重开页面 | ⚠️ **pending 仍保留**（未配对时 DOM 层已切走配对页，但 model.pending 对象还在内存里） | — |
| finishPlanView/reselectFailed | ❌ **不处理 pending**（只管 plan 清 null 和 selected 清） | L2850-2878 |

**⚠️ 发现缺失**：onNeedPair 退出后 pending 对象仍存在。但实际影响有限——重新配对后 poll(true) 会覆盖所有快照，且 startPending 对 canceled/rejected 的 old pending 已放行。

#### reconciling（reconcile 防重入，bool）

| 退出路径 | 清理 | 证据 |
|---------|------|------|
| reconcile 成功 finally | ✅ 清 false | L2773 |
| reconcile 失败 finally | ✅ 清 false | L2773 finally |
| reconcile 网络异常 finally | ✅ 清 false | L2773 finally |
| reconcile 早 return（requestId 空等） | ✅ 清 false（return 都在 try 内） | L2773 finally |

**结论（对抗审计 C4，原稿推演已删）**：reconcile 的早 return 都在 `try` 块内，`finally`（L2773）清 `reconciling`，无遗漏。

#### cancelingStart（cancelPendingStart 防重入，bool）

| 退出路径 | 清理 | 证据 |
|---------|------|------|
| cancelPendingStart 成功 finally | ✅ 清 false | L2798 |
| cancelPendingStart 失败 finally | ✅ 清 false | L2798 finally |
| cancelPendingStart 早 return（pending 空/已 done） | ❌ 入口 guard 在 L2780：`if (!model.pending || model.pending.done || model.cancelingStart) return`——**guard 检查 cancelingStart=true 才拦，置 true 在 L2783** | 无风险 |

**结论**：cancelingStart 的置 true 和 finally 清 false 都在同一函数作用域，guard 前置。**无遗漏**。

#### reloginStarting（beginRelogin 防重入，bool）

| 退出路径 | 清理 | 证据 |
|---------|------|------|
| canWrite 失败早 return | ✅ 未置 true（置位在其后） | L3064 |
| 账号或密码为空的早 return | ✅ 手动清 false | L3079 |
| ingestRelogin auto 分支 | ✅ 清 false | L2989 |
| postAction 返回（含网络异常兜底） | ✅ 清 false（await 之后，无 finally） | L3092 |
| onNeedPair | 不涉及（reloginStarting 是 beginRelogin 的过程状态） | — |

现有 `beginRelogin` 没有 `try…finally`，清 `reloginStarting` 写在 `await` 之后（L3092）。它不会永久卡住，靠的是 `postAction`（L2316-2325）把异常兜住、返回同形对象，所以 `await` 不会抛。与 `pair`（用 `finally`）写法不一致，列为 U15（低）。原稿「永久锁死」结论撤回（对抗审计 C2）。

#### reloginSubmitting（submitRelogin 防重入，bool）

| 退出路径 | 清理 | 证据 |
|---------|------|------|
| submitRelogin 置真 | — | L3123 |
| 提交前的早 return（challenge 不符、验证码不足 4 位等） | ✅ 置位之前，未动 | L3114-3121 |
| 网络异常（catch） | ❌ 故意不清：结果未知，保持禁用，`poll(true)` 对账 | L3131-3136 |
| 服务端 `duplicate_submit` | ❌ 故意不清：同一张图还有在途提交，等快照结论 | L3141-3146 |
| 其他失败响应 | ✅ 清 false | L3148 |
| 提交成功 | ❌ 本函数不清，由 `ingestRelogin` 终态分支收 | L3155-3156 |
| `ingestRelogin` 各终态与换图分支 | ✅ 清 false | L2988、L2997、L3004、L3020、L3024、L3029、L3045、L3056 |
| onNeedPair（配对丢失） | 未逐行核，本表不覆盖 | — |

**结论**：本类有两条「故意不清」（网络异常、`duplicate_submit`），都由快照对账收口；其余 `return` 路径都已覆盖，无遗漏。`challenge` 对象不属于 7 类进行中状态，本节未核，列入「仍没查完的事项」。

---

## 第二部分：三端规则比对表

### R1 登录是否失效

| 端 | 位置 | 逻辑 |
|----|------|------|
| 后端 Python | `local/domain/login_rules.py` `build_session_state` + `check_result` | `session_present = token存在`，`session_expired` 纯函数由后端快照决定，估算锚点只作提醒不参与放行；check_result 四态（valid/expired/unknown/none） |
| 桌面 JS | `local/ui/state/login.js` `setLogin` + `reconcileAutoLogin` | 读 S.login.result（后端 check 回包），recovering 标志用于静默自动登录中的呈现；**dead 条件 session_expired 不单独参与放行——注释已标注 E1 决策 006 修订** |
| 手机 JS | `local/ui/m/app.js` **L136-138** `PhoneModel.loginRaw` | `!!login && (!!login.session_expired \|\| login.session_present === false \|\| login.last_check_state === "expired")` — **仍直接读 session_expired（已标死条件）**，与桌面端同口径但手机没做"dead 条件隔离"的显式注释 |

**差异**：手机 loginRaw 直接 `!!login.session_expired`，桌面端虽也保留 login.session_expired（后端 build_session_state 生成），但桌面端在 setLogin 里有 recoverBlock 处理自动登录中的中间态，手机 loginExpired 引入了 loginRecovering 做隔离。**实际口径一致**，但注释层面手机没标注 session_expired 是死条件。

**测试比对**：契约测试 `test_login_rules.py` 覆盖后端；桌面端有 `test_login_flow.js`。手机端未见 loginRaw 单元测试（纯 PhoneModel 层可能有但未确认）。

---

### R8 立即报名还是预报名

| 端 | 位置 | 逻辑 |
|----|------|------|
| 后端 Python | `local/signup_plan.py` **L56-74** `classify_signup_mode` | `start.timestamp() > now → pre_register`，否则 `instant_signup`，sign_end 已过先判 closed |
| 桌面 JS | `local/ui/state/labels.js` **L7-16** `modeOf` | 同口径：`start > now → pre_register`；now==null 时 return "unknown" |
| 手机 JS | `local/ui/m/app.js` **L497-499** `planSummary` | `open > 0 && nowS !== null && open <= nowS → instant += 1` — open 来自 `openEpochOf(item)`（等价于 sign_start epoch 秒），所以条件 **完全对称于桌面** |

**差异**：手机 planSummary 的条件 `open <= nowS` 等价于桌面 `!(start > now)`。**逻辑一致**。但手机没有对 sign_end 已过的活动做 closed 判断（planSummary 是草稿态计数，已截止活动正常会被过滤）。

**测试比对**：后端有 `test_signup_plan_classify_mode.py`；桌面有 `test_modeOf.js`。手机端 planSummary 未见专门测试。

---

### R6 时间重叠/半开区间

| 端 | 位置 | 公式 |
|----|------|------|
| 后端 Python | `local/signup_plan.py` **L77-80** `intervals_overlap` | `start_a < end_b and start_b < end_a` ✅ |
| 桌面 JS | `local/ui/state/filters.js` **L214/239** `validateSelection` | `leftStart < rightEnd && rightStart < leftEnd` ✅（行 210-214 与已报名重叠，行 237-239 内部冲突） |
| 桌面 JS | `local/ui/state/filters.js` **L256** `signedClash` | `start < otherEnd && otherStart < end` ✅ |
| 手机 JS | `local/ui/m/app.js` **L328** `PhoneModel.signedClash` | `a.s < b.e && b.s < a.e` ✅ |
| 手机 JS | `local/ui/m/app.js` **L593** `overlapFirst` | `a.s < b.e && b.s < a.e` ✅ |

**结论**：**四端半开区间公式完全一致**（`a.s < b.e && b.s < a.e`），首尾相接不算冲突。

**注意**：后端 intervals_overlap 对 datetime 对象比较，桌面/手机对 epoch 秒 Number 比较——精度不同但语义一致。后端的 validate_plan 还额外检查了活动时间缺失/无效，桌面 validateSelection 和手机 signedClash 也有同样的前置 guard（时间缺失/end<=start 时跳过冲突检查）。

---

### R4 报名结束原因到文案

| 端 | 位置 | 覆盖的 stop_reason | 未覆盖的 |
|----|------|-------------------|---------|
| 后端 Python | `local/domain/signup_reply.py` **L63-72** `STOP_REASON_LABELS` | full→名额已满, closed→报名已截止, conflict→时间冲突, no_activity→活动不存在, clock_skew→本机时钟不准, unknown_reply→学校回了无法识别的结果, page_unavailable→学校页面打不开 | — （后端全量） |
| 桌面 JS | `local/ui/state/task-display.js` **L62-65** `taskDisplayLabel` | full→名额已满, unconfirmed→待核对, auth_unavailable→未提交 | closed, conflict, no_activity, clock_skew, unknown_reply, page_unavailable 等 6 种 — fallback 走通用 label 或 outcome_label 透传 |
| 手机 JS | `local/ui/m/app.js` **L418-428** `PhoneModel.taskText` | full→"名额已满（学校说满了…）", unconfirmed→"待核对（去活动页看一眼…）" | closed, conflict, no_activity, clock_skew, unknown_reply, page_unavailable, auth_unavailable 等 7 种 — fallback "报名未成功" + outcome_label 透传 |

**差异矩阵**：

| stop_reason | 后端 label | 桌面 | 手机 | 三方一致？ |
|-------------|-----------|------|------|-----------|
| full | 名额已满 | 名额已满 ✅ | 名额已满（…括注）✅ | **文案略不同**，手机多了括注说明 |
| closed | 报名已截止 | ❌ fallback | ❌ fallback | 三端都**没有专门处理**，靠 outcome_label 透传 |
| conflict | 时间冲突 | ❌ fallback | ❌ fallback | 同上 |
| no_activity | 活动不存在 | ❌ fallback | ❌ fallback | 同上 |
| clock_skew | 本机时钟不准 | ❌ fallback | ❌ fallback | 同上 |
| unknown_reply | 学校回了无法识别的结果 | ❌ fallback | ❌ fallback | 同上 |
| page_unavailable | 学校页面打不开 | ❌ fallback | ❌ fallback | 同上 |
| unconfirmed | （非 STOP_REASON_LABELS 条目） | 待核对 ✅ | 待核对 ✅ | 一致 |
| auth_unavailable | （非 STOP_REASON_LABELS 条目） | 未提交 ✅ | ❌ **未处理** | **手机缺失** auth_unavailable |

**结论（对抗审计 C1 更正）**：后端 STOP_REASON_LABELS 是全集，`outcome_label` 由 `retry_payload` 对全部终态统一下发，桌面（`plan-panel.js:1153`）与手机（`m/app.js:423`）都优先用它，所以显示不会退化成一句没有原因的话。真正的缺口只有一处：手机缺 `auth_unavailable` 一句（桌面 `task-display.js:63` 有）。

---

### R5 列表分组与排序

| 端 | 位置 | 分组 | 排序 |
|----|------|------|------|
| 桌面 JS | `local/ui/views/list.js` **L78-116** `groupTimetable` | 正在开放 → 今天（按日历日）→ 明天 → 后天 → 更晚开放 → 报名时间待公布 → 已报名 → 已截止 | 组内按 `sign_start` epoch 升序，同开时按 name 中文排序（L104 `byStart`） |
| 手机 JS | `local/ui/m/app.js` **L563-571** `groupKeyOf` + **L1991-1995** `LIST_ZONES` | signed / open("正在开放") / closed("已截止") / unknown("待公布") / 今天 / 明天 / 后天 / 更晚开放 | 组内排序由 `PhoneModel.listView` 决定（未直接看，但 LIST_ZONES 分了 zones：["items", "upcoming-items", "signed-items"]） |

**差异**：
1. **组序不同**：桌面 open 和"正在开放"合并成第一个组；手机 open 进 LIST_ZONES[0]，signed 进 LIST_ZONES[2]，而桌面 signed 在 closed 之前。
2. **日历日切分**：桌面用 `startOfDay(toTs(sign_start))`（本机时区），手机用 `PhoneModel.dayOf`（北京时间 UTC+8）——**手机的北京时间切分是对的**（决策 012 不读手机墙钟），桌面端 `startOfDay` 内部应已调 business clock（未确认）。
3. **注意**：手机端"已报名"在 LIST_ZONES[2]（独立区），桌面端"已报名"和"报名时间待公布/已截止"混在组列表里——**用户视觉流不同**。

---

### R9 批次说明文案

| 端 | 位置 | 文案 |
|----|------|------|
| 桌面 JS | `local/ui/views/plan-panel.js` **L475-476** | `instant ? "立即报名 " + count + " 场" : (count > 1 ? "预报名，同时提交 " + count + " 场" : "预报名 1 场")` |
| 手机 JS | `local/ui/m/app.js` **L1084-1085** | `b.instant ? "立即报名 " + n + " 场" : (n > 1 ? "预报名，同时提交 " + n + " 场" : "预报名 1 场")` |

**结论**：**三字符串完全一致**（连变量名 count/n 都无影响，是纯字符串拼接）。✅

---

### R7 倒计时与北京时间

| 端 | 位置 | 时钟来源 | 问题 |
|----|------|---------|------|
| 桌面 JS | 多处 | `businessNowMs()` / `bnowS()` — **走 business_clock 校准后的北京时间** | ✅ 统一 |
| 手机 JS 列表倒计时 | 多处 render 时 | `PhoneModel.businessNowS(model)` — 走 model.clock（服务端 business_clock 快照） | ✅ 决策 012 合规 |
| **手机 JS 「最近同步 HH:MM」** | **L2707-2710** | `new Date()` / `at.getHours()` / `at.getMinutes()` — **手机本机墙钟！** | ❌ **决策 012 违规**：手机用了 `new Date()` 读本机时间，不读服务端 business_clock |

**缺陷**：L2707 `const at = new Date()` 取手机本机时间，L2708-2709 取小时分钟拼 "最近同步 HH:MM"。当手机时区与学校北京时间不一致时，"最近同步" 时间会显示成手机时区——但这是同步成功的时刻，**理论上应该用服务端 business_clock 的当时快照**（如 model.lastOkText 已经是北京时间的 "HH:MM:SS"）。

**严重度**：中等。不影响报名正确性，只影响 UI 文案准确度。但违反决策 012「不读手机墙钟」原则。

---

## 第三部分：新发现的缺陷

### U15：beginRelogin 无 finally，写法与 pair 不一致（合并 U20）

- **位置**：`local/ui/m/app.js` L3061-3092 `beginRelogin`
- **严重度**：🟡 低（对抗审计 C2：原文同一节里写了「高」「中等偏低」「低」三种，按代码证据定为低）
- **是否推测**：否（代码对比）
- **证据链**：
  1. L3063 `if (model.reloginStarting) return` 入口 guard，防双击
  2. L3065 `model.reloginStarting = true` 置锁
  3. L3091 `await postAction(...)` 网络请求
  4. L3092 `model.reloginStarting = false` 清锁，在 await 之后，不在 finally 中
  5. `api`（L2275-2311）只有 `try…finally`，没有 `catch`；异常落到 `postAction`（L2316-2325）的 `catch`，它返回 `{status:0, body:{ok:false, error:"network"}}`，不会抛出
  6. 因此现有路径下 `await postAction` 不会抛，L3092 必然执行，`reloginStarting` 不会永久置真。原稿把 `api` 的 catch 写在 L2299 并判为「永久锁死」，与代码不符，已撤。
- **实际风险**：低。只有 `postAction` 的兜底分支本身抛错（例如 `showSheetError` 失败）时才会卡住，现有代码没有这条路径。
- **建议**：清锁改成 `try…finally`，与 `pair`（L2396-2428）对齐，不改行为。

---

### U16：pending 对象在 onNeedPair 退出配对后未清理

- **位置**：`local/ui/m/app.js` L2466-2477 `onNeedPair`
- **严重度**：🟡 低
- **是否推测**：否（代码证据直接可见）
- **证据链**：
  1. `onNeedPair` 清 paired/pollTimer/tickTimer/stopPairLock
  2. 未清 model.pending（若之前 startPlan 设过 pending）
  3. 重新配对成功后 poll(true) 会走 ingest 覆盖所有快照，pending 最终被 reconcile 处理
  4. 但在配对丢失→重新配对的窗口内，pending 仍挂在 model 上
- **实际风险**：极低——pending 是可空对象，不影响配对视图渲染（配对视图读 pairLockLeft/pairErr，不读 pending）

---

### U17：手机缺 auth_unavailable 一句（三端其余映射不退化）

- **位置**：手机 `local/ui/m/app.js:423` 一带 `PhoneModel.taskText`；桌面 `local/ui/state/task-display.js:62-65`
- **严重度**：🟡 低（对抗审计 C1 更正：原记「中」）
- **是否推测**：否（代码对比）
- **证据链**：
  1. 后端 `local/domain/retry_rules.py:110-115` 有值就写 `outcome_label`；`local/domain/plan_rules.py:179-228` 的单场终态分支都经 `retry_payload(...)` 下发，所以 7 种 STOP_REASON_LABELS 原因都带 `outcome_label`（`test_signup_reply.py:72-79` 守着）。
  2. 桌面 `local/ui/views/plan-panel.js:1153` 优先用 `outcome_label`，没有时由 `stopReasonText`（`1058-1078`）覆盖 7 种。
  3. 手机 `local/ui/m/app.js:423` 同样优先用 `outcome_label`。
  4. 真正的缺口只有一处：`auth_unavailable` 不在 STOP_REASON_LABELS 里，没有 `outcome_label`；桌面 `task-display.js:63` 给「未提交」，手机没有对应分支，落到「报名未成功」。
- **实际风险**：低。
- **建议**：手机补一句 `auth_unavailable` →「未提交」。不需要三端各补全 7 种映射。

---

### U18：并入第一轮 U7，不另编号

手机「最近同步」用手机本机墙钟（`local/ui/m/app.js` L2707-2710），与第一轮 `ui-states.md` U7、`state-trace.md` 第七节 #9 是同一条缺陷。指挥会话复核对抗审计时指出，本轮原来单列的 U18 与 U7 重复，故合并，不另编号。修法见 U7。

---

### U19：桌面/手机列表分组中「今天」的日历日切分来源不同

- **位置**：桌面 `list.js` L104 `groupTimetable`；手机 `app.js` L570 `groupKeyOf`
- **严重度**：🟡 低
- **是否推测**：需确认桌面端 `startOfDay` 是否已走 business clock
- **证据链**：
  1. 桌面 `groupTimetable` 行 89 用 `startOfDay(toTs(sign_start) * 1000 \|\| now)` — 如果 `startOfDay` 内部走 `businessNowMs()` 则正确，否则可能走本机时区
  2. 手机 `groupKeyOf` 行 570 用 `PhoneModel.dayOf`（UTC+8 日历日序，不读手机墙钟）——**正确**
  3. 如果桌面端 `startOfDay` 走本机时区，则两个客户端对"今天/明天"的切分可能差几小时
- **实际风险**：中低——跨零点附近的活动可能在桌面归为"明天"、手机归为"今天"

---

### U20：并入 U15，不另编号

`beginRelogin` 早期校验（L3077-3082）手动清 `reloginStarting`，与 U15 是同一个写法问题（清锁散落、没有统一 `finally`）。合并为 U15 的建议：改成 `try…finally`，不改行为。

---

## Spot Checks（随机抽查 12 处）

| # | file:line | 抽查内容 | 结果 |
|---|-----------|---------|------|
| 1 | signup_plan.py:80 | intervals_overlap 半开区间 `start_a < end_b and start_b < end_a` | ✅ 一致 |
| 2 | signup_plan.py:72 | classify_signup_mode `start.timestamp() > now → pre_register` | ✅ 一致 |
| 3 | app.js (phone):136-138 | loginRaw `!!login.session_expired \|\| login.session_present === false \|\| login.last_check_state === "expired"` | ✅ 符合之前记录 |
| 4 | labels.js (desktop):7-16 | modeOf `start > now → pre_register`，now==null→unknown | ✅ 符合之前记录 |
| 5 | app.js (phone):497-499 | planSummary `open > 0 && nowS !== null && open <= nowS → instant` | ✅ 条件对称 |
| 6 | filters.js (desktop):214 | validateSelection 半开区间 `start < otherEnd && otherStart < end` | ✅ 一致 |
| 7 | filters.js (desktop):256 | signedClash `start < otherEnd && otherStart < end` | ✅ 一致 |
| 8 | signup_reply.py:63-72 | STOP_REASON_LABELS 7 条全量 | ✅ 后端全集（原记 86-93 是 classify_reply 尾部，行号已更正，对抗审计 C8） |
| 9 | task-display.js (desktop):62-65 | taskDisplayLabel 只覆盖 full/unconfirmed/auth_unavailable | ✅ 正确 |
| 10 | plan-panel.js:475-476 | 批次说明 `instant ? "立即报名 " + count + " 场" : ...` | ✅ 与手机 L1084-1085 一致 |
| 11 | app.js (phone):2707-2710 | `const at = new Date(); at.getHours(); at.getMinutes()` | ✅ 违反决策 012 |
| 12 | plan_rules.py:109-122 | check_conflicts 注入 validate_fn + 外层文案 activity_overlap 优先 | ✅ 后端注入契约 |

所有 12 处 spot check 通过。

---

## 收工状态

HEAD 未变，工作区有 design/proposals/engineering-refactor.md 的本地修改和 design/evidence/ 目录（包括本次新增的 supplement/phone.md）。未触碰任何 local/** 文件。
