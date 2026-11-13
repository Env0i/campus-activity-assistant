# AA2 对抗审计（漏项审计）——独立清单与差异意见

- 基线：提交 `7e2d31c`（fix(component): 导入装好后收掉旧的下载失败）。产品代码只按该提交读，行号均为基线行号。
- 方法声明：本审计严格执行「先独立、后比对」。第一部分的八项清单全部由审计员在**打开被审材料之前**从基线代码独立清点得出（git grep + 只读 AST/正则脚本，脚本在系统临时目录，未写入仓库）；写完第一部分后才打开 `redo/zcode/plan/` 下的五份被审材料。第二部分是逐条比对意见。
- 审计员：AA2（漏项审计）。日期：2026-11-13。

## 第一部分：八项独立清单（与被审材料无关，纯基线产物）

### 1. local/ui/m/app.js —— model 全部字段与读写点

model 字面量在 `local/ui/m/app.js:1386-1422`，**初始化字段 47 个**：

items, selected, filter, retry, retryHydrated, retryDirty, seenEventSeq, busy, login, lastOkAt, nowMs, backoff, seq, flow, challenge, reloginSubmitting, reloginStarting, offlineTries, pending, csrf, pollTimer, paired, flying, probed, bannerKind, whyId, flashId, clock, clockState, lastOkText, pcListError, searchOpen, notice, pickId, sheetId, sheetOpener, listOpen, confirm, relConfirm, relEnteredAcct, relSavedChoice, pairLockLeft, pairErr, pairTickTimer, pairing, pairOkPending, dismissedPlanId

**动态新增字段 8 个**（字面量里没有、运行时才赋值，首次使用前是 undefined）：plan（2650，另 2853/2872 置 null）、termsOk（2652）、reloginSetup（2653）、retryOptions（2675）、reconciling（2753/2773）、tickMark（2521）、tickTimer（2472/2504/2508/3327/3337）、cancelingStart（2783/2798）。

**合计 55 个不同的 model.X 字段**。读写点全表（refs=全部引用，assign=`model.X =` 赋值次数，sub=子字段赋值 `model.X.y =`，reads=refs−assign）：

| 字段 | refs | assign | sub | reads | 关键写入点 |
|---|---|---|---|---|---|
| pending | 32 | 1 | 2 | 31 | 2730 置对象；2741/2761/2789 子字段 done/outcome |
| busy | 24 | 1 | 0 | 23 | 2665（ingest） |
| plan | 26 | 3 | 0 | 23 | 2650/2853/2872 |
| selected | 20 | 6 | 0 | 14 | 1788/2639/2863/2873/2951/3291 |
| tickTimer | 14 | 6 | 0 | 8 | 2472/2504/2507/2508/3327/3337 |
| reloginSubmitting | 15 | 10 | 0 | 5 | 2988/2997/3004/3020/3024/3029/3045/3056/3123/3148 |
| challenge | 15 | 6 | 0 | 9 | 2987/3001/3028/3044/3055/3171 |
| flow | 15 | 1 | 0 | 14 | 2972（ingestRelogin） |
| items | 17 | 1 | 0 | 16 | 2636 |
| pollTimer | 13 | 5 | 0 | 8 | 2470/2494/2497/3325/3335 |
| termsOk | 12 | 1 | 0 | 11 | 2652 |
| retry | 11 | 1 | 2 | 10 | 2668；3312/3318 子字段 |
| reloginStarting | 9 | 4 | 0 | 5 | 2989/3065/3079/3092 |
| sheetId | 9 | 2 | 0 | 7 | 1565/1586 |
| notice | 9 | 7 | 0 | 2 | 1789/2645/2731/2865/2875/2952/3292 |
| filter | 9 | 1 | 5 | 8 | 1973；2210/3276/3283/3297/3305 子字段 |
| csrf | 7 | 4 | 0 | 3 | 2287/2416/2433/2484 |
| clockState | 7 | 1 | 0 | 6 | 2655 |
| lastOkAt | 8 | 1 | 0 | 7 | 2441 |
| login | 8 | 1 | 0 | 7 | 2703 |
| reloginSetup | 8 | 1 | 0 | 7 | 2653 |
| listOpen | 8 | 4 | 0 | 4 | 2732/2864/2874/3249 |
| flying | 10 | 2 | 0 | 8 | 2434/2453 |
| paired | 10 | 3 | 0 | 7 | 2417/2443/2468 |
| nowMs | 10 | 3 | 0 | 7 | 1496/1501/1998 |
| pairLockLeft | 7 | 3 | 0 | 4 | 2358/2364/2373 |
| pairErr | 6 | 5 | 0 | 1 | 2351/2366/2397/2420/3192 |
| backoff | 6 | 3 | 0 | 3 | 2442/2464/2488 |
| seq | 6 | 3 | 0 | 3 | 2625/2680/2697 |
| searchOpen | 6 | 1 | 0 | 5 | 2207 |
| seenEventSeq | 6 | 0 | 0 | 6 | 原地 clear/add/delete（2624/2682-2685） |
| clock | 6 | 2 | 0 | 4 | 301（setClock 内）/2523 |
| whyId | 5 | 2 | 0 | 3 | 411（toggleWhy 内）/1968 |
| offlineTries | 5 | 2 | 0 | 3 | 1446/2463 |
| pairTickTimer | 5 | 3 | 0 | 2 | 2362/2363/2372 |
| relConfirm | 5 | 4 | 0 | 1 | 1602/1666/3067/3262 |
| bannerKind | 3 | 1 | 0 | 2 | 1429 |
| flashId | 3 | 2 | 0 | 1 | 1980/1984 |
| lastOkText | 3 | 1 | 0 | 2 | 2660 |
| pcListError | 4 | 1 | 0 | 3 | 2664 |
| pickId | 4 | 2 | 0 | 2 | 2164/2182 |
| sheetOpener | 3 | 2 | 0 | 1 | 1564/1604 |
| confirm | 3 | 2 | 0 | 1 | 1601/1681 |
| relEnteredAcct | 3 | 2 | 0 | 1 | 3068/3087 |
| relSavedChoice | 3 | 2 | 0 | 1 | 3069/3088 |
| pairOkPending | 3 | 2 | 0 | 1 | 2418/3204 |
| pairing | 3 | 2 | 0 | 1 | 2401/2426 |
| cancelingStart | 3 | 2 | 0 | 1 | 2783/2798 |
| reconciling | 3 | 2 | 0 | 1 | 2753/2773 |
| dismissedPlanId | 3 | 2 | 0 | 1 | 2852/2871 |
| retryHydrated | 2 | 1 | 0 | 1 | 2672 |
| retryDirty | 4 | 3 | 0 | 1 | 2885/3313/3319 |
| retryOptions | 1 | 1 | 0 | 0 | 2675（只写不读） |
| probed | 2 | 1 | 0 | 1 | 2617 |
| tickMark | 2 | 1 | 0 | 1 | 2521 |

### 2. local/grab.py —— 输出种类与退出码归属

子命令 6 个（4013-4057）：login / check / list / cancel / grab / selftest。

**输出类别计数**（按调用点计，定义行已剔除；嵌套函数计入所属子命令）：

| 类别 | 调用点数 | 分布 |
|---|---|---|
| `print(` | 85 | cmd_grab 33、cmd_list 11、cmd_login 10、cmd_selftest 6、_by_index_or_name 6、resolve_target 6、pick_activity 4、cmd_check 4、main 2、cmd_cancel 1、log() 内 1、_stderr_note 内 1 |
| `sys.stdout.write(` | 0 | 无 |
| `sys.stderr.write(` | 1 | _rollback_note |
| `log(`（自定义日志，276 定义） | 66 | cmd_grab 43、run_cancel 5、cmd_check 1、cmd_list 2、cmd_cancel 1、notify 2、其余散点 |
| `log_event(`（314 定义） | 6 | 全部在 cmd_login |
| `_stderr_note(`（244 定义） | 6 | log() 内 4、_append_log_line_unlocked 1、cmd_list 1 |
| `notify(`（1646 定义，飞书推送） | 4 | 全部在 cmd_grab |

注：`_stdout_to_stderr(True)`（256）在 cancel 等场景把 print 重定向到 stderr，stdout 协议行另受保护；`list --json` 的 stdout 由 app 解析（AGENTS.md 所述协议）。

**退出码归属**（子命令 → 码；不含嵌套函数返回值）：

| 子命令 | 码 | 出处（基线行号） |
|---|---|---|
| login | 0 / 1 / 2 / 中继返回值 | 1313→0；1272、1286→1；1261、1303、1310→2；1239→`_cmd_login_relay`（run_http_relay 结果） |
| check | 0 / 2 | 1327→0；1330→2 |
| list | 0 / 2 | 1419、1422、1467、1475→0；1361、1373、1376→2。嵌套 `rank(a)`（1403-1413）的 0/1 是**排序键**，不是退出码 |
| cancel | 0 / 2 | 1605：kind=="cancelled"→0，否则 2 |
| grab | 0 / 2 / 3 | terminal()（2553-2628）：success→0（2572）、already_signed→0（2575）、login_invalid→3（2580）、auth_unavailable→3（2586）、max_attempts→2（2591）、unconfirmed→2（2600）、clock_unavailable→3（2605）、REPLY_STOP_HINTS 7 类→2（2613）、process_error→2（2618）、兜底 sign_end/retry_duration→2（2627）；terminal 重入→2（2556）。另有直返：2513、2521、2711→3；2528、2533、2759→2；2752、2842→0 |
| selftest | 0 / 2 | 3988→0；3987、3992→2 |
| main() | 2 / 130 / 转发 | 4063 站点未配置→2；4072 KeyboardInterrupt→130；4069→`args.func(args)` |
| argparse | 2 | 用法错误标准退出 |

**退出码全集 {0, 1, 2, 3, 130} 共 5 档**；1 只出现在 login。

### 3. local/app.py —— Api 方法

`class Api`（app.py:813 起）：**方法共 153 个；公开（不以下划线开头）60 个；私有/`__init__` 93 个**。

60 个公开方法（基线行号）：clock_snapshot 1036、sync_clock 1046、bootstrap 1149、help 1245、download_advanced_feature 1425、cancel_advanced_feature_download 1452、enable_advanced_feature 1459、advanced_component_location 1488、open_advanced_component_dir 1506、advanced_features_state 1525、inspect_advanced_component 1606、pick_advanced_component 1624、install_advanced_feature 1644、remove_advanced_feature 1733、save_relogin_credentials 1770、clear_relogin_credentials 1795、front_ready 2052、check_update 2057、update_download 2117、update_cancel 2171、update_launch 2177、check 2252、list_activities 2283、cancel_signup 2555、login 2762、grab 2780、start_request_state 2854、cancel_start_request 2891、start_plan 2923、cancel_task 3234、stop_plan 3242、plan_active_for_close 3271、ask_window_close 3310、request_window_close 3334、hide_window 3389、show_window 3427、window_visibility 3443、shutdown 3521、stop 3621、phone_access_state 3767、start_phone_access 3812、set_phone_access_preferences 3897、restore_phone_access 3913、schedule_phone_restore 3937、schedule_component_auto_update 3963、stop_phone_access 4017、prepare_phone_relogin 4043、relogin_begin 4153、relogin_submit 4182、relogin_cancel 4186、relogin_auto_once 4194、phone_relogin_begin 4211、phone_relogin_submit 4244、phone_relogin_cancel 4248、open_data 4333、open_latest_release 4344、get_license_text 4357、save_prefs 4376、accept_terms 4383、withdraw_terms 4409。

其中未以 `api("…")` 字符串形式被桌面 JS 调用的公开方法 11 个：help、advanced_features_state（经 bootstrap 快照 1174/3810 带出）、remove_advanced_feature、grab、plan_active_for_close、hide_window、shutdown、stop、restore_phone_access、schedule_phone_restore、schedule_component_auto_update（内部/托盘/gui 路径）。

### 4. 桌面前端（local/ui/ 除 m/）—— esc( 调用点

- **唯一函数定义**：`local/ui/state/time.js:123` `function esc(value)`。terms.js:46 的 `const esc = dialog.querySelector(".help-esc")` 是同名局部变量（DOM 元素），**不是**第二个定义。
- `esc(` 匹配 116 处 = 定义 1 + **调用 115 处**，落在 12 个文件 87 行：

| 文件 | 调用处数 |
|---|---|
| views/plan-panel.js | 38 |
| views/list.js | 28 |
| views/clock-pop.js | 12 |
| views/terms.js | 8 |
| state/filters.js | 7 |
| views/conflict-tip.js | 6 |
| views/selection.js | 6 |
| views/help.js | 3 |
| views/login.js | 3 |
| views/status-cards.js | 2 |
| controllers/window.js | 2 |
| state/time.js | 0 调用（1 处为定义本身） |

- 落点分类：列表行渲染（list.js：组条/组注/计数、时刻、旗标、地点、aria、取消确认块）、计划面板（plan-panel.js：批次头、任务卡、冲突弹层、横幅、policy 行、路线图）、时钟弹窗（clock-pop.js 12）、奖励 chips 与旗标（filters.js）、条款（terms.js 8）、冲突气泡（conflict-tip.js）、选择弹层（selection.js）、帮助（help.js）、登录结果（login.js）、状态卡（status-cards.js）、窗口操作列表（window.js）。手机页（m/）不用 esc(，用 textContent + `PhoneModel.escape`（m/app.js:430）。index.html 与 led.js：0 处。

### 5. stop_reason 三端出现处

**定义（domain 层）**：
- `local/domain/signup_reply.py:49-54` TERMINAL_STOP_REASONS：full/closed/conflict/no_activity；`:63-77` STOP_REASON_LABELS：full/closed/conflict/no_activity/clock_skew/unknown_reply/page_unavailable（7 键短结论）；`:94-96` stop_reason_label。
- `local/domain/retry_rules.py:28-46` parse_retry_line（从 `[retry] kind=done` 行读 stop_reason）；`:87-119` retry_payload（透传 stop_reason；110-114 `outcome_label = stop_reason_label(...)`）。
- `local/domain/plan_rules.py:168-229` classify_task_stop（already_signed/success/canceled→user_stopped/监督收走→unconfirmed 或 binding；code==3 兜底 login_invalid，否则 process_error）；`:157-165` task_stop_reason_binding（sign_end/retry_duration）。
- `local/domain/login_rules.py:61-71` component_error → worker_missing/worker_permission/spawn_failed。

**产出（worker）**：`local/grab.py` terminal()（2553-2628）共 **17 种 stop_reason**：success、already_signed、login_invalid、auth_unavailable、max_attempts、unconfirmed、clock_unavailable、full、closed、conflict、no_activity、clock_skew（3097）、unknown_reply（3110）、page_unavailable（3821）、process_error、sign_end、retry_duration。REPLY_STOP_HINTS（2491-2499）覆盖其中 7 种学校侧终态。退出码映射：0=success/already_signed，3=login_invalid/auth_unavailable/clock_unavailable，2=其余。

**父层消费**：`local/application/plan_service.py:32-38`（full/unconfirmed 单列聚合）、286-313（终态行才带 stop_reason）、406-411（只认带 stop_reason 的行）；`local/app.py:3180` spawn_failed（worker 拉起失败直接写进任务）。

**桌面 UI 消费**：
- `local/ui/state/clock.js:3` TASK_RUNTIME_FIELDS 含 stop_reason（plan-events.js:2-12 mergeTask 按它保字段）。
- `local/ui/state/task-display.js:62-65`：unconfirmed→待核对、auth_unavailable→未提交、full→名额已满。
- `local/ui/state/labels.js:60-64` taskClass：unconfirmed/auth_unavailable→is-warn、full→is-neutral。
- `local/ui/state/plan.js:139-155` planOutcome（failed 按 unconfirmed/auth_unavailable 单列）+ 159-166 unknownLabel。
- `local/ui/controllers/plan-events.js:94-115`：unconfirmed/auth_unavailable 单场结论；stopReasonText 兜底。
- `local/ui/views/plan-panel.js:1058-1079` stopReasonText **17 键**映射；615/636/691 verifiedSigned/verifyTask（unconfirmed 刷新核对）；1123/1153 任务卡；resultCounts/resultView（约 1240-1300：六类，含桌面独有「错过了 missed」档）。
- `local/ui/controllers/refresh.js:376-384` RUNTIME_ERRORS（spawn_failed 等组件码，同名人话体系）。

**手机 UI 消费**（`local/ui/m/app.js`）：
- 415-429 taskText：full、unconfirmed 专用句；login_wait=waiting 句。
- 871-936 taskCard：failed+full→名额已满、failed+unconfirmed→待核对（886-896）；RS02 三句。
- 977-1034 resultView：failed+stop_reason∈{full,unconfirmed} 单列五类统计；手机无「错过了」档。
- 手机对其余 stop_reason（login_invalid 等）不单独映射，落「报名未成功：outcome_label」。

### 6. local/domain/phone_rules.py —— ACTION_PARAMS 全部键

`local/domain/phone_rules.py:155-171`，**12 个动作键**：

| 动作 | 允许参数 |
|---|---|
| list_activities | request_id |
| check | request_id |
| start_plan | items, headed, retry_policy, request_id |
| start_request_state | request_id |
| cancel_start_request | request_id |
| stop_plan | plan_id |
| cancel_task | plan_id, task_id |
| save_retry_policy | retry_policy |
| show_window | （空集） |
| phone_relogin_begin | username, password, save |
| phone_relogin_submit | flow_id, challenge_id, code |
| phone_relogin_cancel | flow_id |

另有 `RETRY_POLICY_KEYS = {retry_for_s, max_attempts}`（173 行）；normalize_action（176-251）逐键校验。

### 7. 字符串桥接暴露名与实际定义对应

**桌面 `api("…")`（bridge.js 包装 window.pywebview.api[name]）**：44 个不同名、45 个调用点（relogin_begin 在 views/relogin.js:371 一行两处）。44 名单：accept_terms、advanced_component_location、ask_window_close、bootstrap、cancel_advanced_feature_download、cancel_signup、cancel_task、check、check_update、clear_relogin_credentials、clock_snapshot、download_advanced_feature、enable_advanced_feature、front_ready、get_license_text、inspect_advanced_component、install_advanced_feature、list_activities、login、open_advanced_component_dir、open_data、open_latest_release、phone_access_state、pick_advanced_component、prepare_phone_relogin、relogin_auto_once、relogin_begin、relogin_cancel、relogin_submit、request_window_close、save_prefs、save_relogin_credentials、set_phone_access_preferences、start_phone_access、start_plan、start_request_state、stop_phone_access、stop_plan、sync_clock、update_cancel、update_download、update_launch、window_visibility、withdraw_terms。**全部 44 名都在 Api 60 个公开方法内**。

**`window.onBackend` kind**：后端 `_emit` 共 **12 种**——log、check、activities、done、plan、task、plan_done、business_clock、update、phone_relogin、window_close_ask、second_open（字面量 10 种；plan/task 经 `local/app.py:3099` 嵌套 `emit(kind,payload)`→3113 `self._emit(kind,…)` 变量转发，由计划运行器回调发出）。桌面监听 `local/ui/app.js:90` `window.onBackend = {…}` 恰为这 12 键；`local/ui/controllers/refresh.js:267/275` 另会本地合成 `window.onBackend.check(...)`。

**手机 `/api/action`**：m/app.js 发 **10 个 action 名**：start_plan 2734、start_request_state 2756、cancel_start_request 2785、stop_plan 2809、show_window 2819、cancel_task 2837、save_retry_policy 2880、phone_relogin_begin 3091、phone_relogin_submit 3128、phone_relogin_cancel 3165。全部在 ACTION_PARAMS 白名单内；白名单里 **list_activities、check 两键手机端不发**（手机读 /api/state 快照）。手机页无 window.onBackend（推送走 /api/state 的 events 缓冲，kind 仅 log/phone_relogin，m/app.js:2678-2695）。

### 8. 三端规则差异应覆盖的清单（每方面在哪端、在哪）

| 方面 | domain/后端 | 桌面 local/ui/ | 手机 local/ui/m/ |
|---|---|---|---|
| 登录失效判定 | signup_reply.py:7-8、86（只认 code=4001）；login_rules.py:179-214 check_hint/check_result 四态（网络词优先，unknown 不误导重登）；grab.py 2434-2467 probe_token（4001 后 LOGIN_RECHECK_S=1.5s 复查）；app.py 2339-2400 _note_login_conclusion/_push_login_expired（失效推飞书一次）；application/login_service.py:48 四态结论 | controllers/refresh.js check 事件→S.login.view 四态 + paintBanners「登录已失效」横幅（约 1420 起）；controllers/tick.js:103 周期 check | m/app.js:133-154 loginRaw（session_expired / session_present===false / last_check_state==="expired"）+ loginRecovering/loginExpired（自动登录进行中不算失效）；1465-1494 EX02 告警条；1094-1106 loginLine 四支；1767-1769、3221-3225 底栏主钮换「重新登录」 |
| 立即/预报名 | signup_plan.py:36 SIGNUP_MODES、56-74 classify_signup_mode、503-513 _prepare_ts（instant 启动即拉起、pre 提前 lead_s）；plan_rules.py:64-84 closed_items_error | state/labels.js:7-20 modeOf/modeText（预报名/立即报名/已截止）；controllers/plan.js:104-105、335-345 计数说明；plan-panel.js:476-483 批次头「现在」 | m/app.js:492-504 planSummary（N 场立即报名/N 场预报名）；548-558 stOf；643-646 行旗标（立即报名/预报名/下一场）；885-889 isPre→等待开放/准备报名；1055-1088 reviewBatches 现在批/预报名批 |
| 时间重叠 | plan_rules.py:99-122 check_conflicts（validate_fn=signup_plan.validate_plan，activity_overlap 才用冲突话术） | state/filters.js:183-195 groupSelected/validateSelection + signedClash；views/selection.js:74-81 与 plan-panel.js:733-735 冲突弹层（「只能选其中一场」）；state/conflict.js:77-136 气泡（四选一解除路径/时间条）+ views/conflict-tip.js | m/app.js:321-330 signedClash、586-595 overlapFirst、596-611 conflictNotice/pickItem、379-408 whyView、364-378 clashWay 四选一 |
| 结束原因标签与文案 | signup_reply.py:63-77 STOP_REASON_LABELS 7 键；retry_rules.py:110-114 outcome_label；plan_rules.py:176-229 各 reason 句 | plan-panel.js:1058-1079 stopReasonText 17 键；task-display.js:56-65 标签；labels.js:47-69 taskLabel/taskClass；plan.js:139-166 planOutcome/unknownLabel；plan-events.js:80-126 showTaskResult；plan-panel resultCounts/resultView 六类含「错过了」 | m/app.js:414-429 taskText；871-936 taskCard（RS02 三句）；977-1034 resultView 五类统计（无「错过了」档） |
| 列表分组排序 | grab.py cmd_list rank 1403-1413（0/1 排序键） | views/list.js:84-118 分组（正在开放/按日/报名时间待公布/已报名/已截止，byStart+zh 名称序）；state/labels.js:22-45 stateOf | m/app.js:559-573 groupKeyOf（今天/明天/后天/更晚开放）；726-771 listView（8 组固定顺序）；1991-1995 LIST_ZONES 三区 |
| 批次说明 | signup_plan.py:419-445 _run（同准备时刻同批启动） | state/filters.js:183-191 groupSelected（按 sign_start 分批）；plan-panel.js:471-485 批次头（现在/待公布/hmsDay + 立即报名 N 场/预报名，同时提交 N 场/预报名 1 场）；plan.js:335-345 | m/app.js:1046-1088 reviewBatches（同款三支 note）；859「这一批 N 场同时提交」 |
| 时间与倒计时 | retry_window.py（DEFAULT_RETRY_SECONDS=120、ADAPTIVE_RETRY=-1、ADAPTIVE_SECONDS=1500、resolve_window）；time_text.py；business_clock.py；time_contract.py | state/clock.js（CLOCK_MAX_AGE_MS=900000 等阈值、businessNowMs）；state/time.js（durText/hmsDay/whenText，esc 定义 123）；controllers/tick.js 每秒、controllers/clock.js 校准；views/clock.js、clock-pop.js；plan-panel.js:114-170 executionView（effectiveRetryDeadline） | m/app.js:174-189 taskDeadline（-1→120 兜底、sign_end 硬截）；113-118 nextTickDelay 整秒对齐；535-543 leftCn；829-870 runBoard（≤10 秒转红、离线 capB）；294-310 setClock/businessNowS（900 秒上限、H4 睡眠检测 2515-2525） |
| 组件与下载失败 | login_rules.py:61-71 component_error；app.py:341-345 WORKER_PROBLEM_TEXT、3180 stop_reason=spawn_failed、1425-1523 下载安装、application/advanced_component_service.py、infrastructure/component_packages.py | controllers/refresh.js:376-384 RUNTIME_ERRORS（worker_missing/worker_permission/spawn_failed 人话+重新检查）；state/store.js:79；views/phone.js:745-1070（下载/安装/浏览）；views/settings.js:183-338（relogin_ocr）；controllers/update.js:58-135 + views/update.js（更新下载）；plan-panel.js:1376 组件横幅 | 手机无组件下载功能（手机快照 DROP_TOP_KEYS 剔除 update/help；m/app.js 无对应块） |
| 核对计划弹层 | plan_rules.py:20-122 错误载荷 kind（bad_item/missing_id/duplicate_id/unknown_activity/activity_changed/sign_end_passed/already_signed/invalid_sign_start/activity_time_unknown/activity_time_invalid/activity_overlap） | plan-panel.js:720-760 冲突/校验弹层 + views/selection.js:60-81；plan-panel.js:346 勾选提醒 chips | m/app.js:937-957 confirmView 三档确认逐字；1678-1704 askConfirm/onConfirmYes（sheet 外壳）；2899-2961 renderReview（批次+preStartWarnings 434-477）；2957-2961 openReview |

---

（第一部分到此为止。以下第二部分在打开被审材料后撰写。）

## 第二部分：逐条差异意见（打开被审材料后撰写）

被审材料：desktop.md、phone.md、rules.md、grab.md、prereq.md（及同名 .cites.jsonl）。总体判断：五份材料在八项清单上的**主体数字与结论与我方独立清点一致**（详见第三部分互证表），发现 2 条重要、5 条次要差异，无阻断级问题。

### 意见 1【重要·整块漏】rules.md 规则 7「时间与倒计时」缺「重试截止倒计时」整块

- **我独立列的口径与数量**：「时间与倒计时」含两层——开放倒计时与**重试截止倒计时**。domain 算式在 `local/domain/retry_window.py`（DEFAULT_RETRY_SECONDS=120、ADAPTIVE_RETRY=-1、ADAPTIVE_SECONDS=1500、resolve_window 三模式与 sign_end 硬截，1-108 行）；worker 侧 compute_retry_window（grab.py:1819-1834）；桌面消费在 plan-panel.js executionView/effectiveRetryDeadline（114-170，重试截止取 retry_deadline telemetry）与 task-display.js submittingDetail；手机消费在 m/app.js:174-189 taskDeadline（telemetry retry_deadline 优先、retry_for_s=-1→120 兜底、0→sign_end 直达、sign_end 硬截）与 runBoard/提交中明细（829-870、928-933）。
- **交付里写的**：rules.md 规则 7 只覆盖 time_contract/business_clock（r-056~058）、state/time.js 的时长文案（r-061/r-062）、手机 leftCn/businessNowS/900 秒上限（r-063~065）。其余四份材料均未覆盖 retry_deadline 倒计时：grab.md 的 B5 只把 retry_deadline 当协议字段列出；desktop.md、phone.md 不涉及。
- **差异**：整块漏（交付缺失）。
- **影响**：这是 worker/父监督/界面三方共用的冻结契约（重试窗口算式改一处，三端倒计时全变）；重构若只按 rules.md 规则 7 的清单动手，会漏掉 retry_window.py 与两端 taskDeadline 的联动。
- **严重度**：重要。

### 意见 2【重要·类别错并+整块漏】phone.md 七出口把「停止计划」与「取消一场」并成一节，独立的「取消一场」出口分析缺失

- **我独立列的口径与数量**：手机页等待操作 12 个里，stopPlan（m/app.js:2804-2816）与 cancelTask（2831-2844）是两个独立动作：接口不同（stop_plan vs cancel_task）、失败文案不同（「没能停止计划：…」2811 vs「没能取消这一场：…」2839）、确认槽不同（askConfirm("stop") 3239 vs askConfirm("cancelTask", name, taskId) 2260，cancelTask 带 task_id 记忆 B-P1-1）、取消钮只给 waiting 场（taskCard canCancel，935）。
- **交付里写的**：phone.md 第 20 行口径说明宣称清单含「取消一场」共 12 个操作；但正文从「### 6. 停止计划（stopPlan）」直接跳到「### 8. 重新登录开始」，编号 7 缺失。第 6 节的「失败」子弹写的是「回包 error → sheet 红条『没能取消这一场：…』、回 false」并引 [[p-121]]——p-121 摘录恰是 cancelTask（2831-2844），即 cancelTask 的内容被并进了 stopPlan 标题下；同节最后一条子弹「取消/超时/页面隐藏/配对失效：与『停止计划』同构」在停止计划小节里自我引用，语义悬空。
- **差异**：类别错并（两个操作并进一节且标题只写其一）+ 整块漏（cancelTask 作为独立操作的七出口没有单独成节，其 task_id 定位、canCancel 门禁、确认槽带参等进入条件没有对应的出口分析）。
- **影响**：重构手机页动作层时按该节理解会误以为两动作完全同构，忽略 cancelTask 需要按 task_id 定位、按钮只在 waiting 场出现等差异；「没能取消这一场」这句失败文案会被读成停止计划的文案。
- **严重度**：重要。

### 意见 3【次要·数量少算】prereq.md 4.2 的桌面 api("…") 字面量调用点数 42 与事实 54 不符，且与其自身「44 个不同名」矛盾

- **我独立列的口径与数量**：桌面 `api("…")` 字面量调用点 **54 处**（`git grep -oE 'api\("[A-Za-z_0-9]+"'` 计数；单引号形态 0 处），44 个不同名——relogin_begin 在 views/relogin.js:371 一行两处，bootstrap 5 处、open_data/open_data 类多点名各 2 处；44 名全部存在于 Api 60 公开方法。
- **交付里写的**：prereq.md 4.2「桌面前端共 44 个不同方法名的字符串调用（42 处 api("…") 字面量去重，双引号形态；无单引号形态、无变量名形态）」——42 个字面量不可能去重出 44 个名字，内部自相矛盾；实际 54 处。
- **差异**：数量少算（42 vs 54），且句内自洽性破坏。核心结论（44 名全存在）本身正确。
- **影响**：这是「重构前置清点」的量化交付，数字自相矛盾会动摇对清点脚本输出的信任。
- **严重度**：次要。

### 意见 4【次要·混合：notify 漏计是错的，log() 61 属口径不同但成立】grab.md 输出总数 159 的构成

- **我独立列的口径与数量**：按调用点计（剔除定义行与 docstring 中的字样）：print 85、log **64**、log_event 6、_stderr_note 6、sys.stderr.write 1、notify 4，合计 170。log( 的 67 次原始匹配中有 3 次非调用：定义行 276、docstring 258（「log() 等辅助函数」）、docstring 315（「log() 补」）；真实调用 64 中，log_event 内部转发 1 处（320）、notify 内部转发 2 处（1667/1670）。
- **交付里写的**：grab.md 第 9 行「输出调用 159 处：print 85、log() 61、log_event 6、_stderr_note 6、sys.stderr.write 1、sys.stdout.write 0、logging 0」。notify 只在 D1 行描述、未计入总数；log()=61 的口径（64 真实调用 − log_event 内部 1 − notify 内部 2）可复算但文中未披露构成，只对外部参考口径 187 做了说明。
- **差异**：notify 4 处调用未计入总数——**交付是错的**；log() 61——**口径不同但成立**（两边口径：我按「grab.py 内所有 log() 调用点」计 64；交付按「log 自有通道调用点，log_event/notify 内部转发归各自通道」计 61），但口径未在文中写明。
- **影响**：以 159 做重构回归基线会漏掉 notify 通道的输出行为；log() 计数无法从文中复算。
- **严重度**：次要。

### 意见 5【次要·覆盖缺】rules.md 规则 4 桌面侧漏两处 stop_reason 消费面；桌面/后端各存在一套未提及的计数双口径

- **我独立列的口径与数量**：桌面 stop_reason 消费共 7 处：state/clock.js:3（TASK_RUNTIME_FIELDS，mergeTask 保字段）、state/task-display.js:56-65、state/labels.js:60-64（taskClass 着色）、**state/plan.js:139-166（planOutcome：failed 里 unconfirmed/auth_unavailable 各自单列计数；unknownLabel：「有 N 场需确认/待核对/未提交」）**、**controllers/plan-events.js:80-126（showTaskResult：unconfirmed/auth_unavailable 两个专支的单场结论与「刷新列表」动作）**、views/plan-panel.js:1058-1079（stopReasonText 17 键）+ resultCounts/resultView、controllers/refresh.js:376-384（组件码同形体系）。后端另有 application/plan_service.py:32-38 的计划级聚合（full 单列、unconfirmed 单列、其余归一类）。
- **交付里写的**：rules.md 规则 4 桌面只引 task-display（r-032）、labels taskLabel（r-033）、plan-panel stopReasonText（r-034）与 unconfirmed 长句（r-035，指向 plan-panel.js:1145-1147）、结果页统计标签（r-036，plan-panel.js:705-707）。planOutcome/unknownLabel、showTaskResult 两支、plan_service 聚合均未引用。
- **差异**：覆盖缺（交付缺失而非数字错）。特别地，桌面存在两套结果计数口径——resultCounts 把 auth_unavailable 并进「报名未成功」（plan-panel.js resultCounts 注释自述），planOutcome 把它与 unconfirmed 并列单列供大屏/LED/总结标题——rules.md 未提，重构时容易当成一个口径合并。
- **影响**：改任务卡/结果呈现时按 rules.md 的清单会漏掉「需确认」计数的独立来源；auth_unavailable 的归档分歧（并 vs 单列）是真实的双口径风险点。
- **严重度**：次要。

### 意见 6【次要·覆盖缺】rules.md 规则 2/6 漏桌面 plan.js 的「N 场立即报名 / N 场预报名」呈现面

- **我独立列的口径与数量**：桌面在两处按 signup_mode 计数呈现：controllers/plan.js:104-105（futureCount/instantCount）与 335-345（计划来源说明句「已安排…」配套的「N 场立即报名、N 场预报名」，按后端快照 signup_mode 分）。
- **交付里写的**：规则 2 手机侧引了 m planSummary（r-019），规则 6 桌面侧引了 plan-panel 批次头（r-051）与运行中批次句（r-052）；plan.js 这两处未引。
- **差异**：覆盖缺。与手机 planSummary 对应的桌面呈现面缺席，规则 2 的「三端比对」在桌面这一面不完整。
- **影响**：轻微；改计划说明句时可能漏改。
- **严重度**：次要。

### 意见 7【口径不同但成立/待复核】grab.md login(--relay) 退出码 0/1/3/4 的「3、4」两档我未能独立复核

- **我独立列的口径与数量**：login 经 `_cmd_login_relay`（grab.py:1239）转出返回值，我未展开枚举；我给出的退出码全集按 local/grab.py 直返为 {0,1,2,3,130}。
- **交付里写的**：grab.md ② login(--relay) 行：「返回 login_relay.run_http_relay 的值：0 成功；1 等不到凭据(eof)；3 token 未验证；4 持久化失败」，引 g-118/g-088/g-089，并如实声明 Playwright 兜底路径的 1/2 未逐条引证。
- **差异**：g-118 摘录（grab.py:1233-1239）与 g-089 摘录（login_relay.py:703-716 _http_settle「持久化失败不报成功」）与 claim 方向一致；但我未逐行复核 3/4 的落点行。「1」我在 login_relay.py 的 return 清单中见到多处（265、319），「2」在 281/293/323（属 Playwright 兜底，交付已声明未引证）。
- **差异判断**：不判错；标注「待复核」——若 3/4 不成立，grab.md 的退出码矩阵多两档。
- **影响**：无直接影响；重构登录中继时需按基线复核。
- **严重度**：次要。

### 我方清点的三处修正（诚实记录，非交付缺陷）

1. **grab.py log() 真实调用点是 64，不是第一部分所写 66**：67 次原始匹配含定义行（276）与两处 docstring 字样（258「log() 等辅助函数」、315「log() 补」）。第一部分写作 66（67−定义行），漏剔 docstring；已在上文意见 4 修正。
2. **「未被桌面 api("…") 调用的公开方法」应为 16 个，不是第一部分所写 11 个**：我漏了 show_window、cancel_start_request、phone_relogin_begin、phone_relogin_submit、phone_relogin_cancel 这 5 个手机专属名（prereq.md 4.2 的 16 名单正确）。
3. **桌面「核对计划」用词修正**：我第一部分把桌面冲突/校验呈现写成「弹层」；经复核桌面**没有**核对计划弹层——`#btn-dock-start` 直接绑定 startPlan（local/ui/app.js:384），选择提醒/校验错误/时间重叠渲染进内联 `#plan-conflicts` 框（plan-panel.js:731-738，innerHTML+hidden 切换）。rules.md 规则 9 的判定（桌面无独立弹层、手机才有 sheet）成立。

## 第三部分：互证表（我方独立清点 × 交付数字）

| 项 | 我独立清点 | 交付数字 | 判定 |
|---|---|---|---|
| 1 手机 model 字段 | 字面量 47 + 动态 8 = 55；写入 148（136 赋值+9 子字段+3 原地）+6 别名=154；读取 296（444 引用−145 赋值−3 原地） | phone.md：55；148+6=154；296 | 一致（逐字段行号抽查一致） |
| 2 grab 输出 | print 85、stdout 0、stderr 1、log 64、log_event 6、_stderr_note 6、notify 4 | print 85、stdout 0、stderr 1、log 61（口径见意见 4）、log_event 6、_stderr_note 6、notify 未计数 | 部分一致（意见 4） |
| 2 grab 退出码 | 子命令 6 个；直返档 {0,1,2,3,130}；grab 经 terminal() 17 种 stop_reason→0/2/3；嵌套 rank 0/1/2 是排序键 | 子命令 6 个；逐档行号与我直返点全对上（2513/2521→3、2528/2533→2、2752 查不到目标→0、2842 dry-run→0 等）；terminal 17 种（补记）；嵌套 79 条单列「非退出码」 | 一致（relay 3/4 档待复核，意见 7） |
| 3 Api 方法 | 153 总 / 60 公开 / 93 私有含 __init__ | prereq.md 二节：153/60/93，60 名单分 6 块且与我 60 名单全等 | 一致 |
| 4 桌面 esc( | 定义 1（time.js:123）；调用 115 处/87 行；分布 plan-panel 38、list 28、clock-pop 12、terms 8、filters 7、conflict-tip 6、selection 6、help 3、login 3、status-cards 2、window 2 | prereq.md 三节：定义 1、调用 115 处/88 行（含定义行）、逐文件分布与我全等；另指出 esc 不转义单引号、terms.js:46/82/85 局部遮蔽 | 一致（交付另有两个正确增量） |
| 5 stop_reason | worker 终态 17 种；domain 定义/映射/消费三端 7+4+若干处 | grab.md 补记 17 种；rules.md 规则 4 三端主链一致（桌面兜底表后 5 键如实声明未单独引用）；桌面漏 2 处消费面（意见 5） | 大体一致（意见 5） |
| 6 ACTION_PARAMS | 12 键 + RETRY_POLICY_KEYS | prereq.md 4.4：12 键逐一对上 Api 成员；save_retry_policy 经特判改道 save_prefs | 一致（交付更细） |
| 7 桥接名 | 桌面 api 44 名/54 处全存在；onBackend 12 kind=12 监听键（plan/task 经闭包转发）；手机 10 action，白名单中 list_activities/check 未用 | prereq.md 4.2-4.5：44 名全存在（但调用点写 42，见意见 3）；12 kind=12 键一一对应；手机 10 action、list_activities/check 白名单宽于用法 | 一致（意见 3 一处数字错） |
| 8 三端规则差异 | 9 方面锚点表（见第一部分 8） | rules.md 规则 1-9 全覆盖且多数差异判定与我一致（手机失效聚合、缺举办时段不算冲突、组内排序语义不同、批次键语义不同、手机无组件界面、桌面无核对弹层、already_signed 文案两端不一致）；漏重试倒计时（意见 1）、漏桌面 plan.js 计数句（意见 6） | 大体一致（意见 1/6） |

## 附录：独立清点使用的命令与脚本

- 基线读取：`git -C <仓库根> show/grep 7e2d31c:<路径>` 与只读基线树 `D:\@Temp\zcode_baseline_badcwdhp\<相对路径>`（git archive 导出）。未读工作区现行产品文件；被审材料在第一部分写完后才打开。
- 全仓检索：`git grep -n/-c/-oE "<模式>" 7e2d31c -- <路径>`（stop_reason、esc(、onBackend、api("、"4001"、instant_signup、REPLY_STOP_HINTS、ACTION_PARAMS、emit( 等）。
- 只读清点脚本（系统临时目录 `%TEMP%\aa2_audit\scan.py`，标准库，输入仅基线树，未写入仓库）：
  - 第 1 项：正则 `\bmodel\.(\w+)` 全量引用/`\bmodel\.(\w+)\s*=(?!=)` 赋值/`\bmodel\.(\w+)\.\w+\s*=(?!=)` 子字段赋值，逐字段行号清单；字面量字段按 `const model = {…}` 块解析（该正则只抓到行首字段，47 个的最终名单经人工全文复读校正）。
  - 第 3 项：`ast.parse` local/app.py，取 `class Api` 直接子节点 FunctionDef，分公开/私有，带行号。
  - 第 4 项：os.walk 遍历基线 `local/ui`（排除 m/），`(?<![\w.])esc\(` 计 occurrences 与行数；定义点用 `function esc|const esc =` 复查（terms.js:46 为同名局部变量，非定义）。
  - 第 7 项：桌面 `(?<![\w.])api\(\s*["']([^"']+)["']`、手机 `action:\s*"([^"]+)"`、app.py `_emit\(\s*["']([^"']+)["']` 与 `emit\(` 闭包转发、ui/app.js 的 window.onBackend 监听键。
  - 第 2 项：输出类别按 `print\(|sys\.stdout\.write|sys\.stderr\.write|(?<![\w_.])log\(|log_event\(|_stderr_note\(|notify\(` 计匹配；AST 顶层函数行区间归属子命令；`nested_returns`（不下钻嵌套函数）枚举 cmd_*/main 的 return 常量与表达式，区分退出码与排序键。
- 复核用一次性 python stdin 脚本（未落盘）：log( 逐行分类（定义/docstring/内部转发）、m/app.js 注释行 model 引用计数（0，证明 phone.md 读取点口径与我的正则口径可对齐）、desktop `api\("…"` 计数（54）、rules/phone/grab/prereq cites.jsonl 定向条目抽查。
- 产出文件（本文件）是本次唯一写入仓库的文件；未修改任何被审文件，未运行测试与构建，未联网。

（完）
