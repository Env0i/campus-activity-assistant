# T2 手机页状态追踪（基线 7e2d31c）

- **基线提交**：`7e2d31c`（v1.2.2）。全部行号以它为准；产品代码只按基线读（`git show 7e2d31c:<路径>`），未读工作区现行文件。
- **执行日期**：2026-11-13。只读审计；引用条目共 123 条（id 前缀 `p-`），与本文件和 `phone.cites.jsonl` 对应。
- **清点脚本**（node，标准库，只读，从仓库根复跑）：

  ```bash
  node design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/phone_model_fields.mjs
  ```

  脚本内部用 `child_process` 执行 `git show 7e2d31c:local/ui/m/app.js` 取基线内容，静态解析出 `model`（基线 1386-1422 行字面量）每个字段的全部写入点与读取点（行号 + 所在函数名），输出 JSON 到 stdout。本文「字段总表」的写入/读取行号清单与脚本输出一致；「哪种情况下执行」为人工读码补注，每处挂引用。

## 口径说明

- **字段**：只数 `model` 的顶层字段。基线字面量声明 47 个；另 8 个是运行中动态加上的（`plan`、`termsOk`、`reloginSetup`、`retryOptions`、`reconciling`、`cancelingStart`、`tickTimer`、`tickMark`，都不在 1386-1422 行的字面量里），合计 55。
- **写入点计数**：`model.X = …`（含条件赋值、子字段 `model.X.y = …`、复合赋值）与原地变更方法（`model.X.clear()/add()/delete()`）各记一处；同一行的读+写分别记。脚本数出 **148 处**（145 处赋值 + 3 处原地变更）；另有 **6 处经局部别名**（`reconcile`/`cancelPendingStart` 里 `const pending = model.pending` 后写 `pending.done` 等，行 2760、2761、2782、2788、2789、2797），在 `model.X` 词形之外，脚本数不到，本文在 `pending` 行人工补注。合计 **154 处**。第一轮 redo 参照的分组 136+3+9+6 分组法不同，但总数同为 154；本表以本脚本口径为准。
- **读取点**：脚本数出 **296 处**表达式引用；另有 **45 处裸 `model` 引用**（作实参传给 `PhoneModel` 纯函数、`PhoneUI` 导出等），单独在脚本输出的 `bareModelRefs` 里，不计入读写。`PhoneModel.setClock` 与 `toggleWhy` 经名为 `model` 的形参写字段（301、411 行），脚本按形参名归到页面 `model`，已计入写入点。
- **脚本边界（解析不到的形态，见脚本头注）**：①局部别名写入（上面 6 处）；②计算成员 `model[expr]`（基线没有，脚本数出 0 处）；③模板字符串 `${…}` 内的引用按整段字符串不数（基线没有模板字符串）；④字符串下标访问（基线没有）；⑤解构写入 `[model.a] = …`（基线没有，脚本不识别，出现会漏数）。`Object.assign(model…)` 基线为 0 处。
- **七种出口**：按任务书口径——进入、成功、失败、取消、超时、页面隐藏、配对失效。第一轮 README「C4」列的八条退出路径在本表按此归并：C4 的「异常」并入失败，「窗口关闭/隐藏」并入页面隐藏，「后端先结束」「迟到/重放事件」在手机页主要表现为 401 配对失效与快照接管，逐操作注明。读代码定不了的标「需测试定」并写 missing。
- **等待操作清单以代码为准**：轮询同步、配对（含锁定倒计时）、开始计划、对账、取消等待、停止计划、取消一场、重新登录开始、提交验证码、取消重登/换图、保存重试设置、显示电脑窗口，共 12 个。前三轮范围外的一律不列。

---

## ① 字段总表

写入点格式：`行 函数｜执行条件`，后跟形如 p-001 的双方括号引用条目；子字段写入用 `[子字段]` 注明。读取点格式：`行 函数`，同一行多次引用合并计数（×n）。函数名后是所在函数的声明行（脚本输出 `函数名@行`，此处省略行号，行号看写入/读取行）。

| 字段（声明） | 写入点（行 函数｜执行条件） | 读取点（行 函数） |
|---|---|---|
| `items`（1388） | 2636 ingest@2621｜快照带 activities 数组时整表替换 [[p-001]] | 1535 refreshControls；1754 renderBar；1787 addEventListener›回调；1970 goSigned；2002 renderItems；2050 renderItems；2078 renderItems；2080 forEach›回调；2541 tickClock；2640 filter›回调；2641 filter›回调；2859 forEach›回调；2860 forEach›回调；2904 renderReview；2950 removeFromReview；3290 addEventListener›回调 |
| `selected`（1388） | 1788 addEventListener›回调｜行内勾选 change，用 pickItem 结果写回（撞已选场保留原选择）[[p-002]]<br>2639 ingest｜新活动表到达，按 actionable 与开放状态过滤旧勾选 [[p-001]]<br>2863 reselectFailed｜结果态「重新选择」把 failed/canceled 场放回 [[p-003]]<br>2873 finishPlanView｜结果态「完成」清空 [[p-004]]<br>2951 removeFromReview｜核对弹层移除条目 [[p-005]]<br>3291 addEventListener›回调｜「选这一场」 [[p-006]] | 131 canStart；1536 refreshControls；1755 renderBar；1756 renderBar；1787 addEventListener›回调；2004 renderItems；2543 tickClock；2637 ingest；2645 ingest；2718 startPlan；2904 renderReview；2950 removeFromReview；2954 removeFromReview；3290 addEventListener›回调 |
| `filter`（1388） | 1973 goSigned｜目标行当前筛选下不可见时重置为全部 [[p-007]]<br>2210 toggleSearch[q]｜开合搜索时清关键词 [[p-008]]<br>3276 addEventListener›回调[q]｜折叠内 #q 输入 [[p-009]]<br>3283 addEventListener›回调[q]｜整页搜索框输入 [[p-010]]<br>3297 addEventListener›回调[status]｜段钮点击 [[p-011]]<br>3305 addEventListener›回调[time]｜时间档钮点击 [[p-012]] | 1970 goSigned；2002 renderItems；2541 tickClock |
| `retry`（1389） | 2668 ingest｜首次快照带 retry_policy 且未 hydrate 未 dirty [[p-013]]<br>3312 addEventListener›回调[retry_for_s]｜#retry-for change [[p-014]]<br>3318 addEventListener›回调[max_attempts]｜#max-attempts change [[p-015]] | 446 preStartWarnings×2；1537 refreshControls；2736 startPlan；2737 startPlan；2882 saveRetry；2883 saveRetry；2896 fillRetryOptions |
| `retryHydrated`（1389） | 2672 ingest｜retry_policy 落地后置真，挡住后续快照覆盖 [[p-013]] | 2667 ingest |
| `retryDirty`（1389） | 2885 saveRetry｜保存成功才清；失败保持真（挡快照覆盖用户输入）[[p-016]]<br>3313 addEventListener›回调｜#retry-for change 置真 [[p-014]]<br>3319 addEventListener›回调｜#max-attempts change 置真 [[p-015]] | 2667 ingest |
| `seenEventSeq`（1390，Set） | 2624 ingest[clear]｜payload.reset 开新事件周期 [[p-017]]<br>2683 forEach›回调[add]｜每个 seq>0 事件登记去重 [[p-018]]<br>2685 forEach›回调[delete]｜集合超 400 裁最老 [[p-018]] | 2682 forEach›回调；2684 forEach›回调；2685 forEach›回调 |
| `busy`（1390） | 2665 ingest｜快照 busy 是布尔才写（电脑上计划在跑）[[p-020]] | 98 isActive；127 canStart；1512 refreshControls；1625 renderRelogin；1723 renderBar；1739 renderBar；1768 renderBar；1770 renderBar；2001 renderItems；2004 renderItems；2058 renderItems；2062 renderItems；2080 forEach›回调；2124 renderBoard；2126 renderBoard；2224 renderPlan；2236 renderTasks×2；2543 tickClock；2553 tickBoardLed；2556 tickBoardLed；3034 ingestRelogin；3222 addEventListener›回调 |
| `login`（1392） | 2703 ingest｜快照 state.login 是对象时整份替换 [[p-021]] | 1469 renderAlerts；1541 refreshControls；1734 renderBar；1736 renderBar；1737 renderBar；1738 renderBar；3222 addEventListener›回调 |
| `lastOkAt`（1393） | 2441 poll｜/api/state 回 200（同步成功）[[p-023]] | 126 canStart；156 canSubmitRelogin；483 connState；486 connState；1497 canWrite；1502 refreshControls；3205 addEventListener›回调 |
| `nowMs`（1393） | 1496 canWrite｜每次判「能不能写」前取手机墙钟 [[p-025]]<br>1501 refreshControls｜每次重画控件前 [[p-026]]<br>1998 renderItems｜每次重画列表前 [[p-027]] | 126 canStart；156 canSubmitRelogin；483 connState；1497 canWrite；1502 refreshControls；2003 renderItems；3205 addEventListener›回调 |
| `backoff`（1393） | 2442 poll｜同步成功归 1000 [[p-023]]<br>2464 onPollFail｜轮询失败按指数退避拉长 [[p-028]]<br>2488 onForbidden｜403 后退避 [[p-029]] | 105 syncDelay；2464 onPollFail；2488 onForbidden |
| `seq`（1393） | 2625 ingest｜payload.reset 归 0 [[p-017]]<br>2680 forEach›回调｜事件游标取 max [[p-018]]<br>2697 ingest｜payload.seq 取 max [[p-019]] | 2437 poll；2680 forEach›回调；2697 ingest |
| `flow`（1394） | 2972 ingestRelogin｜每次中继快照/事件整份替换 [[p-030]] | 101 isActive；160 canSubmitRelogin；1469 renderAlerts；1521 refreshControls；1531 refreshControls；1541 refreshControls；1554 sheetBusy；1619 renderRelogin；1662 openRelogin；1736 renderBar；1738 renderBar；3114 submitRelogin；3117 submitRelogin；3159 cancelRelogin |
| `challenge`（1394） | 2987 ingestRelogin｜auto 在途清（手机不看图）[[p-032]]<br>3001 ingestRelogin｜waiting_code 新图到达（flow_id+challenge_id）[[p-033]]<br>3028 ingestRelogin｜success 清 [[p-035]]<br>3044 ingestRelogin｜failed/canceled 清 [[p-036]]<br>3055 ingestRelogin｜其余态（含 idle）清 [[p-037]]<br>3171 cancelRelogin｜取消成功清 [[p-113]] | 1515 refreshControls；1516 refreshControls；2995 ingestRelogin；3114 submitRelogin；3115 submitRelogin；3117 submitRelogin；3118 submitRelogin；3129 submitRelogin；3130 submitRelogin |
| `reloginSubmitting`（1394） | 2988 ingestRelogin｜auto 在途收 [[p-032]]<br>2997 ingestRelogin｜同图对账且服务端无在途提交才收 [[p-033]]<br>3004 ingestRelogin｜新图到达收 [[p-033]]<br>3020 ingestRelogin｜verifying 收 [[p-034]]<br>3024 ingestRelogin｜starting 收 [[p-034]]<br>3029 ingestRelogin｜success 收 [[p-035]]<br>3045 ingestRelogin｜failed/canceled 收 [[p-036]]<br>3056 ingestRelogin｜其余非 waiting_code 态收 [[p-037]]<br>3123 submitRelogin｜发送前置真（锁 sheet）[[p-038]]<br>3148 submitRelogin｜回包失败且非 duplicate_submit 收 [[p-039]] | 99 isActive；158 canSubmitRelogin；1555 sheetBusy；1556 sheetBusy；1622 renderRelogin |
| `reloginStarting`（1395） | 2989 ingestRelogin｜快照显示 auto 在途（mode=auto 且非终态）时收 [[p-031]][[p-032]]<br>3065 beginRelogin｜发起前置真（单飞）[[p-040]]<br>3079 beginRelogin｜缺账号密码保险丝收 [[p-041]]<br>3092 beginRelogin｜POST 返回后收 [[p-042]] | 99 isActive；1518 refreshControls；1526 refreshControls；1621 renderRelogin；3063 beginRelogin |
| `offlineTries`（1395） | 1446 syncOffline｜判定不 stale 时归零 [[p-045]]<br>2463 onPollFail｜每次失败加一 [[p-028]] | 486 connState；1454 syncOffline；2463 onPollFail |
| `pending`（1396） | 2730 startPlan｜发新开始，`{request_id, at, done:false}` [[p-047]]<br>2741 startPlan[done]｜后端当场受理 [[p-048]]<br>2742 startPlan[outcome]｜记 accepted（保留防双击窗）[[p-048]]<br>2760 reconcile[done，别名]｜对账查到终态（经局部别名 pending 写，脚本边界外）[[p-085]]<br>2761 reconcile[outcome，别名]｜同上 [[p-085]]<br>2782 cancelPendingStart[canceling，别名]｜取消动作开始 [[p-088]]<br>2788 cancelPendingStart[done，别名]｜取消回包 canceled [[p-089]]<br>2789 cancelPendingStart[outcome，别名]｜同上 [[p-089]]<br>2797 cancelPendingStart[canceling，别名]｜finally 复位 [[p-090]] | 100 isActive；1532 refreshControls×2；1744 renderBar×2；1745 renderBar；1769 renderBar×2；2057 renderItems×2；2123 renderBoard×2；2131 renderBoard；2552 tickBoardLed×2；2560 tickBoardLed；2712 ingest×2；2720 startPlan×2；2723 startPlan×2；2750 reconcile；2757 reconcile；2780 cancelPendingStart×2；2781 cancelPendingStart；3223 addEventListener›回调×2 |
| `csrf`（1396） | 2287 api｜每次写请求前重读 cookie，有新的就换 [[p-049]]<br>2416 pair｜配对成功从回包取 [[p-052]]<br>2433 poll｜无 csrf 时从 cookie 补 [[p-022]]<br>2484 onForbidden｜403 后重读 [[p-029]] | 2288 api×2；2433 poll |
| `pollTimer`（1396） | 2470 onNeedPair｜401 清表停轮询 [[p-054]]<br>2494 schedule｜先清旧 [[p-055]]<br>2497 schedule｜按 syncDelay 排下一次 [[p-055]]<br>3325 addEventListener›回调｜进后台清 [[p-056]]<br>3335 addEventListener›回调｜pagehide 清 [[p-057]] | 2469 onNeedPair×2；2493 schedule×2；3324 addEventListener›回调×2；3334 addEventListener›回调×2 |
| `paired`（1398） | 2417 pair｜配对成功 [[p-052]]<br>2443 poll｜状态读得到即会话还在 [[p-023]]<br>2468 onNeedPair｜401 置假 [[p-054]] | 2496 schedule；2506 scheduleTick；2524 tickClock；2611 tickRowLeft；2801 cancelPendingStart；3328 addEventListener›回调；3340 addEventListener›回调 |
| `flying`（1398） | 2434 poll｜发请求前置真 [[p-022]]<br>2453 poll｜finally 收（成功/失败/401/403 都走）[[p-024]] | 1459 syncOffline；1503 refreshControls；1509 refreshControls；1763 renderBar；2128 renderBoard；2432 poll；2496 schedule；2558 tickBoardLed |
| `probed`（1398） | 2617 probeExistingSession｜首屏一次性探测置真 [[p-060]] | 2616 probeExistingSession |
| `bannerKind`（1398） | 1429 setBanner｜每次设横幅连 kind 一起写，清空记 "" [[p-061]] | 1432 setBanner；1436 clearStaleBanner |
| `whyId`（1400） | 411 PhoneModel.toggleWhy｜点冲突行切换（经参数 model 写入）[[p-062]]<br>1968 goSigned｜跳转前清 [[p-007]] | 411 toggleWhy；412 toggleWhy；1871 buildRow |
| `flashId`（1400） | 1980 goSigned｜置目标行高亮 [[p-063]]<br>1984 setTimeout›回调｜2 秒后清 [[p-063]] | 1778 buildRow |
| `clock`（1400） | 301 PhoneModel.setClock｜快照时刻齐且 ready/holdover 才记锚，否则 null（经参数 model 写入）[[p-064]]<br>2523 tickClock｜检出睡眠跳变丢锚 [[p-059]] | 305 businessNowS；2522 tickClock；2659 ingest×2 |
| `clockState`（1403） | 2655 ingest｜快照 business_clock 是对象时记档位 [[p-065]] | 128 canStart；129 canStart×2；442 preStartWarnings；1471 renderAlerts；1761 renderBar |
| `lastOkText`（1403） | 2660 ingest｜同上分支：钟可用记采样时刻的北京时间 HH:MM:SS，不可用记空 [[p-065]] | 2129 renderBoard；2558 tickBoardLed |
| `pcListError`（1403） | 2664 ingest｜无条件取 pc_list_error‖null [[p-066]] | 1470 renderAlerts；1481 renderAlerts；1748 renderBar |
| `searchOpen`（1405） | 2207 toggleSearch｜点搜索钮取反 [[p-008]] | 2060 renderItems；2207 toggleSearch；2208 toggleSearch；2209 toggleSearch；2213 toggleSearch |
| `notice`（1405） | 1789 addEventListener›回调｜勾选撞已选场写提示，选成/取消都清 [[p-002]]<br>2645 ingest｜勾选数变少时清 [[p-001]]<br>2731 startPlan｜计划已发出，勾选提示不再适用 [[p-047]]<br>2865 reselectFailed｜重选清 [[p-003]]<br>2875 finishPlanView｜完成清 [[p-004]]<br>2952 removeFromReview｜移除条目清 [[p-005]]<br>3292 addEventListener›回调｜「选这一场」写 [[p-006]] | 2089 renderItems；2090 renderItems |
| `pickId`（1405） | 2164 renderBoard｜结果态清 [[p-067]]<br>2182 renderBoard｜非结果板取 board.pickId [[p-068]] | 3289 addEventListener›回调；3290 addEventListener›回调 |
| `sheetId`（1407） | 1565 openSheet｜开弹层记 id（一次只开一张）[[p-069]]<br>1586 closeSheet｜关弹层写空（忙态拦下不关）[[p-070]] | 1543 refreshControls；1563 openSheet；1581 closeSheet；1609 showSheetError；1660 openRelogin；1661 openRelogin；1680 askConfirm |
| `sheetOpener`（1407） | 1564 openSheet｜记打开前焦点元素 [[p-069]]<br>1604 closeSheet｜关后清并归还焦点 [[p-071]] | 1603 closeSheet |
| `listOpen`（1409） | 2732 startPlan｜计划发出即收列表 [[p-047]]<br>2864 reselectFailed｜重选收 [[p-003]]<br>2874 finishPlanView｜完成收 [[p-004]]<br>3249 addEventListener›回调｜「查看活动列表」切换 [[p-079]] | 2058 renderItems；2063 renderItems；2064 renderItems；3249 addEventListener›回调 |
| `confirm`（1411） | 1681 askConfirm｜确认槽写入 kind+taskId [[p-072]]<br>1601 closeSheet｜随 sheet 收起清 [[p-071]] | 1691 onConfirmYes |
| `relConfirm`（1414） | 1602 closeSheet｜随 sheet 收起清 [[p-071]]<br>1666 openRelogin｜按 relogin_setup 决定是否进 RL06 确认层 [[p-073]]<br>3067 beginRelogin｜确认层用完即收 [[p-040]]<br>3262 addEventListener›回调｜取消钮先清 [[p-111]] | 1620 renderRelogin |
| `relEnteredAcct`（1414） | 3068 beginRelogin｜开始前清上一轮 [[p-040]]<br>3087 beginRelogin｜这一轮输过账号置真 [[p-042]] | 1623 renderRelogin |
| `relSavedChoice`（1414） | 3069 beginRelogin｜开始前清 [[p-040]]<br>3088 beginRelogin｜记「保存到这台电脑」勾选 [[p-042]] | 1624 renderRelogin |
| `pairLockLeft`（1418） | 2358 beginPairLock｜按服务端 retry_after_s 置权威呈现值 [[p-074]]<br>2364 setTimeout›回调｜每秒呈现递减一步 [[p-075]]<br>2373 stopPairLock｜清零 [[p-076]] | 2330 renderPair；2359 beginPairLock；2364 setTimeout›回调；2365 setTimeout›回调 |
| `pairErr`（1418） | 2351 setPairError｜写错误句 [[p-077]]<br>2366 setTimeout›回调｜倒计时归零收回旧错误条 [[p-075]]<br>2397 pair｜新尝试开始清 [[p-050]]<br>2420 pair｜配对成功清 [[p-052]]<br>3192 addEventListener›回调｜输入即清 [[p-078]] | 2330 renderPair |
| `pairTickTimer`（1418） | 2362 schedulePairTick｜排 1 秒 tick [[p-075]]<br>2363 setTimeout›回调｜tick 开头先记 0 [[p-075]]<br>2372 stopPairLock｜清 [[p-076]] | 2371 stopPairLock×2 |
| `pairing`（1418） | 2401 pair｜发请求前置真（单飞防双发）[[p-050]]<br>2426 pair｜finally 收（成功/失败/超时都走）[[p-052]] | 2395 pair |
| `pairOkPending`（1418） | 2418 pair｜配对成功置真 [[p-052]]<br>3204 addEventListener›回调｜点「知道了」置假，本会话不再出现 [[p-123]] | 1493 renderAlerts |
| `dismissedPlanId`（1421） | 2852 reselectFailed｜按 plan_id 记已收起 [[p-003]]<br>2871 finishPlanView｜同上 [[p-004]] | 2649 ingest |
| `plan`（动态） | 2650 ingest｜plan_id ≠ dismissedPlanId 才接纳（结果态收起后不回头）[[p-080]]<br>2853 reselectFailed｜重选清 [[p-003]]<br>2872 finishPlanView｜完成清 [[p-004]] | 1723 renderBar；1740 renderBar×2；2001 renderItems；2124 renderBoard；2127 renderBoard；2233 renderTasks×2；2236 renderTasks；2553 tickBoardLed；2557 tickBoardLed；2807 stopPlan×2；2832 cancelTask×2；2833 cancelTask×2；2851 reselectFailed×2；2852 reselectFailed×2；2871 finishPlanView×2 |
| `termsOk`（动态） | 2652 ingest｜快照 terms_ok 是布尔才写 [[p-081]] | 1468 renderAlerts；1511 refreshControls；1518 refreshControls；1525 refreshControls；1526 refreshControls；1757 renderBar；2004 renderItems；2081 forEach›回调；2135 renderBoard；2543 tickClock；2561 tickBoardLed |
| `reloginSetup`（动态） | 2653 ingest｜快照 relogin_setup 是对象才整份替换 [[p-082]] | 443 preStartWarnings；1520 refreshControls；1521 refreshControls；1529 refreshControls；1541 refreshControls；1619 renderRelogin；1665 openRelogin |
| `retryOptions`（动态） | 2675 ingest｜快照 retry_options.choices 是数组才写；**全文件无读取点**（脚本数出读取点为空）[[p-083]] | （无读取点） |
| `reconciling`（动态） | 2753 reconcile｜对账前置真（单飞守卫）[[p-084]]<br>2773 reconcile｜finally 收 [[p-087]] | 2749 reconcile |
| `cancelingStart`（动态） | 2783 cancelPendingStart｜取消动作前置真 [[p-088]]<br>2798 cancelPendingStart｜finally 收 [[p-090]] | 2780 cancelPendingStart |
| `tickTimer`（动态） | 2472 onNeedPair｜401 清秒针 [[p-054]]<br>2504 scheduleTick｜先清旧 [[p-058]]<br>2507 scheduleTick｜续排 [[p-058]]<br>2508 setTimeout›回调｜到点先记 0 [[p-058]]<br>3327 addEventListener›回调｜进后台清 [[p-056]]<br>3337 addEventListener›回调｜pagehide 清 [[p-057]] | 2471 onNeedPair×2；2503 scheduleTick×2；3326 addEventListener›回调×2；3336 addEventListener›回调×2 |
| `tickMark`（动态） | 2521 tickClock｜每次 tick 记 (wall,mono) 对，供睡眠检测比对 [[p-059]] | 2520 tickClock |

字段合计 55（脚本输出 `counts.fields = 55`）；写入点合计 148（脚本）+ 6（别名补注）= 154；读取点合计 296；裸 `model` 引用 45（`PhoneUI` 导出、传参，未列入本表）。

---

## ② 等待操作七出口

每个等待操作列七种出口。没有的出口写「无」，并给出代码依据；读代码定不了的标「需测试定」。请求层共同事实先行：所有请求 8 秒超时（AbortController abort）[[p-091]][[p-092]]；`postAction` 把网络异常接住返回同形失败回包 [[p-093]]；`api` 对 `/api/action` 的 401 调 `onNeedPair`、403 调 `onForbidden` [[p-094]]；401＝会话失效，`onNeedPair` 停表清定时器切回配对页 [[p-054]]；弹层容器 `#sheet-root` 在 `#app` 内，`#app` 隐藏时弹层一并不可见 [[p-118]][[p-119]]。

### 1. 轮询同步（poll / schedule / scheduleTick）

- **进入**：`schedule` 到点、右上刷新钮、离线红条「重试」钮、回前台 `visibilitychange`、`pageshow`、首屏探测、各动作成功后的 `poll(true)`；`flying=true` 在发请求前 [[p-022]]。单飞：在途直接返回 [[p-022]]。
- **成功**：200 后记 `lastOkAt`、退避归位、置 `paired`、ingest 快照 [[p-023]]；`finally` 清 `flying` 并重排 [[p-024]]。同步周期按活动态自适应：忙 2 秒、闲 15 秒，失败退避优先 [[p-116]]；过时门禁是 30 秒无新快照 [[p-117]]。
- **失败**：401/403/其他非 200 分流 [[p-108]]；fetch 抛错走 catch；两条路都进 `onPollFail` 计数+退避 [[p-028]]，红条与「同步中」pill 呈现 [[p-045]]。
- **取消**：无用户取消入口；重复刷新被单飞守卫拦成空操作 [[p-022]]。
- **超时**：8 秒 abort 使 fetch reject，进 catch 按失败处理 [[p-091]][[p-092]][[p-093]]。
- **页面隐藏**：进后台清轮询与秒针定时器 [[p-056]]，`schedule`/`scheduleTick` 有 `document.hidden` 门不排新 [[p-055]][[p-058]]；在途请求照常跑完（代码无中断；后台页回调实际时序**需测试定**，missing：未在真机后台验证定时器节流与回调完成顺序）；回前台立刻补一次按游标的 poll [[p-056]]；pagehide/pageshow 同 [[p-057]]。
- **配对失效**：401 → `onNeedPair`：`paired=false`、清两个定时器、收锁定倒计时、切回配对页 [[p-054]]；`flying` 由 finally 收 [[p-024]]。

### 2. 配对（pair，含锁定倒计时）

- **进入**：输入 6 位后点「配对」或 Enter；清旧错误条与锁定后 `pairing=true` [[p-050]]。
- **成功**：记 csrf、置 `paired`、排成功告警 [[p-123]]、收锁定与错误条、切主界面、立即 `poll(true)`；finally 收 `pairing` [[p-052]]。
- **失败**：非 200/!ok 走 `applyPairFailure`：locked 起锁定倒计时、bad_code 带剩余次数、其他通用句，并清空输入 [[p-053]]；网络异常写专属错误条 [[p-051]]。失败显示为 #pair-error 红条。
- **取消**：无取消动作（配对页代码里没有取消入口）；配错等锁定归零或重输即可再试 [[p-053]]。
- **超时**：8 秒 abort → catch → 错误条「配对失败：网络不通…」[[p-091]][[p-051]]。
- **页面隐藏**：无专门处理；请求回调照常执行（**需测试定**，missing：未验证后台页 fetch 回调与 DOM 更新的实际表现）。
- **配对失效**：本操作即配对；已配会话再失效走 `onNeedPair`（见轮询）。
- **子项·锁定倒计时**：进入 `beginPairLock`（权威值 retry_after_s）[[p-074]]；成功/新尝试/onNeedPair 都会 `stopPairLock` [[p-076]][[p-050]][[p-052]][[p-054]]；归零自停并清旧错误条 [[p-075]]；该定时器是三个定时器里唯一没有 `document.hidden` 门的（见 V5）；权威值只在进入时取一次，无按服务端重算机制 [[p-074]]。

### 3. 开始计划（startPlan，model.pending）

- **进入**：过时拦（stale_action 横幅）、空选拦、未决拦（accepted 防双击静默拦）[[p-046]]；通过后写 `pending={request_id, done:false}` 并清提示、收列表 [[p-047]]。
- **成功**：后端当场受理记 `done+accepted`（保留 15 秒防双击窗）[[p-048]]；或对账查到 accepted 后清提示 [[p-085]][[p-086]]；随后快照 `busy=true` 接管呈现 [[p-020]]。
- **失败**：后端回 error 只亮 banner、**pending 不落地** [[p-048]]；此后每次成功轮询触发对账 [[p-104]]；对账给 rejected/canceled 才落终态 [[p-085]]，给 unknown 则不落——后端对没有记录的 request_id 恒回 unknown [[p-105]]，这时唯一出口是「取消等待」[[p-086]]。
- **取消**：确认 sheet → `cancelPendingStart` [[p-088]]；回包 canceled 经别名落 done/outcome 并亮横幅 [[p-089]]；已被接纳的开始后端拒绝取消（回 ok=false 带 plan_id 让改用停止）[[p-107]]；失败红条回 false，sheet 不收 [[p-089]]。
- **超时**：pending 本身无定时器，超时只改呈现（15 秒对账窗后「还没有查到结果」）[[p-102]][[p-103]]，**超时不清 pending** [[p-103]]；请求层 8 秒超时走 postAction 伪响应进错误分支 [[p-091]][[p-093]]。
- **页面隐藏**：轮询停排，回前台补 poll 触发对账 [[p-056]][[p-104]]；pending 与横幅跨隐藏保留（代码不清）。
- **配对失效**：401 直接 return，pending 留着，等重配后下一次成功轮询再对账 [[p-048]][[p-103]]；onNeedPair 切回配对页 [[p-054]]。

### 4. 对账（reconcile）

- **进入**：ingest 末尾对未决 pending 触发 [[p-104]]；单飞守卫后置 `reconciling` [[p-084]]。
- **成功/失败**：accepted/rejected/canceled 终态经别名落 pending 并按档亮横幅 [[p-085]][[p-086]]。
- **取消**：无（单飞守卫使重复触发为空操作 [[p-084]]）。
- **超时**：8 秒 abort → postAction 伪响应（无 state 字段）→ 无终态动作，finally 收 `reconciling` [[p-093]][[p-087]]。
- **页面隐藏**：随轮询节奏（只在轮询成功后触发），无专门处理 [[p-104]]。
- **配对失效**：401 时伪响应进不了终态分支；onNeedPair 已切配对页 [[p-094]][[p-054]]。

### 5. 取消等待（cancelPendingStart）

- **进入**：确认 sheet「取消等待」；守卫（无未决/已终态/已在途）后置别名 canceling 与 `cancelingStart` [[p-088]]。
- **成功**：回包 canceled 落终态、亮横幅、补 poll、回 true 收 sheet [[p-089]][[p-090]][[p-100]]。
- **失败**：回包错误或 state 不符 → sheet 红条、回 false，finally 复位两个标志 [[p-089]][[p-090]]。
- **取消**：—（本操作即取消）。
- **超时**：8 秒 abort → 伪响应走失败分支 [[p-091]][[p-093]]；pending 仍未决，可再点（守卫已复位）[[p-090]]。
- **页面隐藏**：无处理；sheet 的关闭钮在在途时仍可用（confirm 档不受 sheetBusy 锁，见 V2）。
- **配对失效**：401 → 伪响应失败分支 + onNeedPair 切页 [[p-094]][[p-054]]；重配后可重试。

### 6. 停止计划（stopPlan）

- **进入**：确认 sheet「停止计划」；无独立在途字段，防重发靠确认层禁双钮 [[p-120]][[p-100]]。
- **成功**：回包无 error → 补 poll、回 true → 收 sheet [[p-120]][[p-100]]。
- **失败**：回包 error → sheet 红条「没能停止计划：…」、回 false、双钮重开 [[p-120]][[p-100]][[p-101]]。
- **取消**：「继续计划」钮/Esc/点遮罩收 sheet；请求仍在途（结果未知），失败说明会因 sheet 已关而丢失（见 V2）[[p-099]][[p-101]]。
- **超时**：8 秒 abort → 伪响应 ok=false → 红条 [[p-091]][[p-093]][[p-120]]。
- **页面隐藏**：无处理；回包到达后 `closeSheet(true)` 对已关 sheet 是空操作 [[p-070]]。
- **配对失效**：401 → 伪响应失败分支 + onNeedPair 切页；sheet 随 #app 隐藏、重配后原样回来（见 V4）[[p-094]][[p-054]]。

### 7. 取消一场（cancelTask）

- **进入**：任务卡「取消这一场」→ 确认槽带上这一场的 task_id [[p-121]][[p-072]]。
- **成功**：回包无 error → 补 poll、回 true、收 sheet [[p-121]][[p-100]]。
- **失败**：回包 error → sheet 红条「没能取消这一场：…」、回 false [[p-121]]。
- **取消**：—（本操作即取消）；发请求前的「先不取消」/Esc/点遮罩只是收 sheet，请求尚未发出 [[p-099]][[p-072]]；动作在途时失败说明可能丢失（见 V2）[[p-100]]。
- **超时**：8 秒 abort → 伪响应 ok=false → 红条 [[p-091]][[p-093]][[p-121]]。
- **页面隐藏**：无处理；回包到达后 `closeSheet(true)` 对已关 sheet 是空操作 [[p-070]]。
- **配对失效**：401 → 伪响应失败分支 + onNeedPair 切页；sheet 随 #app 隐藏、重配后原样回来（见 V4）[[p-094]][[p-054]]。

### 8. 重新登录开始（beginRelogin）

- **进入**：更多面板入口/底栏主钮/告警条按钮 → `openRelogin`（先收旧 sheet、按 setup 决定确认层）[[p-073]]；主钮单飞守卫后置 `reloginStarting` 并清三个附言字段 [[p-110]][[p-040]]。
- **成功**：回包 ok → auto 模式「电脑正在自动登录，手机上不用再操作」、manual「正在向电脑要验证码」，两种都补一次 poll；此后由中继快照接管 [[p-044]][[p-030]]。
- **失败**：回包不 ok → plan_late 专属句或「还不能开始：…」[[p-043]]；缺账号/密码走保险丝收标志 [[p-041]]。
- **取消**：取消钮 → 先清确认层，`cancelRelogin` 成立（或本无在途流程）才收 sheet [[p-111]][[p-112]]；有在途流程发 cancel POST，失败留 sheet 与旧图重试 [[p-113]]。
- **超时**：8 秒 abort → postAction 伪响应 → 按「还不能开始」分支收 `reloginStarting` [[p-091]][[p-093]][[p-042]]。
- **页面隐藏**：无处理；快照接管要等回前台后的轮询 [[p-056]]。
- **配对失效**：401 → 伪响应失败分支（标志已在 3092 收）+ onNeedPair 切页 [[p-094]][[p-054]]。

### 9. 提交验证码（submitRelogin）

- **进入**：四道门（flow/challenge 存在、canSubmitRelogin、4 位、同图校验）通过后置 `reloginSubmitting` 并重画锁 sheet [[p-038]]。
- **成功**：200+ok → 清输入、补 poll；在途标志由快照收：verifying [[p-034]]、同图无在途提交 [[p-033]]、success [[p-035]]、failed/canceled [[p-036]]、其余态 [[p-037]]、auto 接管 [[p-032]]（「正在进行」的判定口径见 [[p-115]]）。
- **失败**：非 200/非 ok：duplicate_submit 不解锁只等对账；其余收标志写原因 [[p-039]]。
- **取消**：提交在途期间 sheet 全锁——关闭钮隐藏 [[p-096]]、closeSheet 拦 [[p-070]]、呈现层只有 spin 无取消钮 [[p-097]][[p-098]]、Esc/遮罩也被拦 [[p-099]]。**代码中无取消出口**（见 V1）。
- **超时**：8 秒 abort → catch：故意不清在途标志（结果未知），提示「正在登录，请等结果」并立即 poll [[p-109]][[p-091]]；恢复只依赖下一次成功轮询的快照，断网持续则一直锁（见 V1）。
- **页面隐藏**：catch 里直接调用的 `poll(true)` 不受 hidden 门限制；无其他处理 [[p-109]]。
- **配对失效**：401 → 伪响应走失败分支收标志；onNeedPair 切页（sheet 随 #app 消失）[[p-094]][[p-054]]。

### 10. 取消重登 / 换一张图（cancelRelogin / refreshRelogin）

- **进入**：取消钮或「换一张」钮 [[p-111]][[p-114]]。
- **成功**：无在途流程直接收起不发请求 [[p-112]]；有在途流程 cancel 成功 → 清 challenge、收图、补 poll [[p-113]]；换图 = cancel + begin [[p-114]]。
- **失败**：cancel 回 error → 只写运行记录、留图、回 false（sheet 不收，可重试）[[p-113]]；旧场没撤掉宁可不换图 [[p-114]]。
- **取消**：—（本操作即取消）。
- **超时**：8 秒 abort → postAction 伪响应 → error 分支（留图重试）[[p-091]][[p-093]][[p-113]]。
- **页面隐藏/配对失效**：无专门处理；同「重新登录开始」的 401 路径 [[p-094]]。

### 11. 保存重试设置（saveRetry，change 自动触发）

- **进入**：#retry-for / #max-attempts change 即自动发 [[p-014]][[p-015]]。
- **成功**：清 `retryDirty` [[p-016]]。
- **失败**：只写运行记录「没能保存重试设置：…」，`retryDirty` 保持真，挡住快照覆盖 [[p-016]]。
- **取消/超时/页面隐藏/配对失效**：无取消；超时同失败 [[p-091]][[p-093]]；页面隐藏与配对失效无专门处理。

### 12. 显示电脑窗口（showComputerWindow）

- **进入**：#btn-show-window 点击；无在途标志 [[p-122]]。
- **成功/失败**：都只写一行运行记录，不改任何报名状态 [[p-122]]。
- **取消**：无。**超时**：8 秒 abort → postAction 伪响应 → 按失败写记录 [[p-091]][[p-093]]。
- **页面隐藏/配对失效**：无专门处理。

---

## ③ 新发现的界面缺陷（V1 起）

以下为本轮追踪中新发现、第一轮六节与 C5 对账未收录的手机页缺陷；每条给完整代码路径行号。严重度仅作参考标注。

- **V1（高）提交验证码遇网络异常后，重登 sheet 无任何人工出口，只能等网络恢复。** 链条：submitRelogin 的 catch 故意不清 `reloginSubmitting`（结果未知，先对账）[[p-109]]；此后 `sheetBusy` 为真 [[p-095]]，`closeSheet` 拒绝关闭并顺手藏关闭钮 [[p-070]]，关闭钮显隐也随忙态隐藏 [[p-096]]；呈现层在提交在途时只有 spin，不给取消/换图/完成钮 [[p-097]][[p-098]]；Esc 与点遮罩也走 `closeSheet` 被拦 [[p-099]]。解锁只发生在下一次**成功**轮询的快照里（同图对账 [[p-033]]、verifying [[p-034]]、终态 [[p-035]][[p-036]][[p-037]]）。代码中没有超时或强制解锁路径；断网持续多久锁多久。恢复动作（轮询）本身也依赖网络，形成「必须等网络，无法自救」的闭环。
- **V2（中）确认 sheet 的动作在途时，Esc/点遮罩仍可关掉 sheet，失败反馈丢失。** 链条：`onConfirmYes` 在途只禁双钮 [[p-100]]，`sheetBusy` 只看重登忙态、不看 confirm 在途 [[p-095]]；Esc/遮罩/closeSheet 三条路径此时都能把 confirm sheet 关掉 [[p-099]][[p-070]]；随后回包失败时 `showSheetError` 因 `model.sheetId` 已空直接静默返回 [[p-101]]，失败分支只剩重新放开两个已不可见的钮 [[p-100]]。注释声明 UI-F5「动作失败不静默收场」[[p-072]]，该保证在「用户提前关 sheet」路径上不成立；适用于停止计划、取消一场、取消等待三个动作。
- **V3（中）开始请求被后端拒绝时 pending 不落地，若对账恒回 unknown，开始被持续拦住，唯一出口是「取消等待」，且错误横幅不会自动清。** 链条：startPlan 后端回 error 只亮 banner，pending 保持 `done:false` [[p-048]]；此后对账只在轮询成功后触发 [[p-104]]；请求没被服务端记录（断网没发出、电脑端重启过）时后端恒回 unknown [[p-105]]，前端对 unknown 只给横幅、不落终态 [[p-086]]；`startPending` 对未 done 的 pending 恒拦新开始、超时也不清 [[p-103]]。banner 的 kind 是 error，`clearStaleBanner` 只清 stale_action，同步成功也不清它 [[p-061]]。取消等待对未知 ID 在后端会登记取消并回 canceled，可落终态 [[p-106]][[p-089]]。
- **V4（低）401 配对失效不清理确认层状态，重配后旧确认 sheet 原样回来。** 链条：`onNeedPair` 只清 `paired`、定时器与锁定倒计时，不动 `model.sheetId`/`model.confirm`，也不关 sheet [[p-054]]；`#sheet-root` 在 `#app` 内，`#app` 隐藏时弹层只是不可见 [[p-118]][[p-119]]；重新配对成功后 `#app` 重新显示 [[p-052]]，旧确认 sheet（含此前在途时被禁用的双钮 [[p-100]]）原样出现，等迟到的回包才恢复。
- **V5（低，需测试定）配对锁定倒计时定时器无 document.hidden 门，后台可能走时失真。** `schedulePairTick` 每 1 秒呈现递减一步 [[p-075]]，与 `schedule`/`scheduleTick` 的 hidden 门 [[p-055]][[p-058]] 不同；权威值 `retry_after_s` 只在 `beginPairLock` 进入时取一次，之后无按服务端重算机制 [[p-074]]。页面在后台被浏览器节流时呈现倒计时可能落后于服务端锁窗。missing：未在真机后台实测节流下的实际偏差与解锁时刻差。

---

## ④ spot_checks

随机抽 12 条重读基线核对（语义与行号都核对过；对 12、错 0）：

1. `p-`（poll_enter）——重读 2432-2435：`if (model.flying) return`、无 csrf 补 cookie、`model.flying = true`、先 `refreshControls()` 再发请求，与「先画同步中再发请求」一致。
2. poll_fin——重读 2450-2459：catch 调 `onPollFail`，finally 四件事（清 flying、schedule、scheduleTick、三连重画）属实。
3. pendack——重读 2739-2744：401 直接 return；`body.ok && !body.pending` 记 done+accepted；error 分支只 setBanner，pending 未动。V3 的关键前提成立。
4. rec_term——重读 2757-2761：守卫含 `pending.canceling`；`pending.done = true` 写在别名上，证实脚本别名边界外的 6 处补注必要。
5. irnew——重读 2994-3005：同图先对账、`!info.submit_pending` 才解锁；新图才写 `model.challenge` 并清 `#code`。V1 的解锁条件属实。
6. sheetbusy/closesh——重读 1553-1557、1580-1585：auto 模式只看提交在途；`closeSheet` 忙态直接 return。V1/V2 依据属实。
7. reqto/abort——重读 1371、2293-2294：`REQUEST_TIMEOUT_MS = 8000`、`setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)`。
8. apyunk/apycancel——重读 app.py 2867-2869、2904-2907：无记录回 unknown；未知 ID 登记取消回 canceled。V3 的后端两端成立。
9. twhy/setclk——重读 410-412、294-302：两处经形参 `model` 写字段，脚本按形参名归并的假设成立（抽查脚本正确性）。
10. ropt——重读 2674-2677 并全文件检索 `retryOptions`：仅 2675 一处出现，无读取点（脚本与人工一致）。
11. vis/ph——重读 3322-3341：hidden 清两表、回前台 `poll(false)`；pagehide 清两表、pageshow 补拉。
12. startpending/pendinglong——重读 202-208、780-783：未 done 恒未决、accepted 保留防双击窗、15 秒只改呈现。与②.3 的「超时不清 pending」一致。

追加抽查（第二次，随机种子 20261113，抽 12 条，对 12、错 0）：p-023、p-003、p-107、p-017、p-047、p-118、p-082、p-117、p-002、p-059、p-009、p-066，逐条把摘录与 `git show 7e2d31c` 原文比对一致，claim 与代码语义一致（含 app.py 一条、index.html 一条）。

另核对：phone.cites.jsonl 每条摘录在其基线文件中唯一（构建器逐条 `count==1` 校验通过）；md 引用的 id 全部存在于 jsonl，jsonl 中无未被引用的条目（构建器双向核对通过）。

---

## ⑤ 未尽事项

- 本表只覆盖 `local/ui/m/app.js` 的 `model` 对象。`PhoneModel` 纯函数自己的缓存键（`PhoneModel._glyphs`）与 DOM 上的临时状态（`dataset`、输入框值）未纳入字段表；后者在七出口里只在影响等待呈现处提到。
- 脚本对「写入」的判定是词法级的：`model.X = …` 一律算写入，不做数据流分析。`model.pairLockLeft = PhoneModel.pairTickLeft(model.pairLockLeft)` 这类「读旧写新」按一写一读计（2364 行），与人工核对一致。
- `retryOptions` 是只写字段（写于 2675，无读取点）：`fillRetryOptions` 用的是函数入参而非这个字段。这是状态追踪发现，不是界面缺陷，未编号 V。
- 第一轮 state-trace 第六节「手机页」的三项对账结论（C5 #7 已修、#8 未修、#9 未修）与本轮一致：#8（核对弹层不随轮询更新，`renderReview` 只在打开与移除时调用）、#9（「最近同步」用手机本机时钟，2707-2710 行）在本轮七出口与字段表中都能看到对应代码路径，未重复编号为缺陷。
- 未验证项：所有「需测试定」条目（后台定时器节流、页面隐藏时在途回调时序、锁定倒计时后台偏差）未做真机运行验证；本审计不跑测试与构建，遵守只读边界。
- 引用条数 123 与参照重做（约 292 条）不同的原因：本表以「每个写入点/每条出口链路一证」为准，读取点清单以脚本输出为源、不在 md 里逐条挂引用，故条数更少；字段数 55、写入 154、读取 296 与参照一致。
