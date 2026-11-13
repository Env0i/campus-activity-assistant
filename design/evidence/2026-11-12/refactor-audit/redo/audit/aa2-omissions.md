# AA2 漏项审计（aa2-omissions）

审计者：AA2（Haiku 子智能体二，漏项）。基线：提交 `7e2d31c`，用 `git archive` 导出到一个新建的临时空目录，只读。未改任何被审文件；未提交、未联网、未装依赖、未跑测试或产品。

## 开工与收工的 git 状态

首次开工（`git log --oneline -3`、`git status --short`）：HEAD 为 `7e2d31c`；工作区为

```
 M design/proposals/engineering-refactor.md
?? .workbuddy/
?? design/evidence/2026-11-12/esm-verify/
?? design/evidence/2026-11-12/refactor-audit/
```

中断后恢复（打开附录 A 之前再查一次）：HEAD 仍为 `7e2d31c`，工作区状态与首次一致。`redo/` 下多出 `zcode/` 子目录，属于另一执行方的独立产物，本审计不读、不引用。

## 第一步：独立清点（附录 A）

盲做顺序：附录 A 在打开 `redo/` 下任何重做材料之前写成。下列清单全部由脚本在基线导出上生成，或由 `git` / `ast` 直接取得，不引用重做材料。脚本放在临时目录，未入库。

### 清单 1：手机页 `model` 字段与写入点

来源 `local/ui/m/app.js`，`model` 字面量在 L1386–L1421。脚本 `item1.py` 扫描 `model.X` 的读、直接赋值、变异调用（`.push/.add/.delete/.clear/.set/.sort`）。第三列的函数名由最近的函数声明启发式回推，以行号为准。

要点：读写并集 55 个字段；54 个有直接赋值写入；1 个（`seenEventSeq`）只经 `.add/.delete/.clear` 变异；字面量里没有声明的字段 8 个（`cancelingStart`、`plan`、`reconciling`、`reloginSetup`、`retryOptions`、`termsOk`、`tickMark`、`tickTimer`）。别名写入：未发现 `const m = model`、`Object.assign(model, …)` 或 `model[…] =`。`PhoneModel` 助手中通过参数写 `model` 的只有 `setClock`（`app.js:301`）与 `toggleWhy`（`app.js:411`），二者已包含在上表中。

```
literal_lines 1386 1422 | 字段总数(读/写/变异并集) 55 | 有写入的字段 54 | 有变异调用的字段 1 | 只读字段 0
backoff | 字面量Y | 写 2442:poll:.backoff; 2464:onPollFail:.backoff; 2488:onForbidden:.backoff | 变异 - | 读 6
bannerKind | 字面量Y | 写 1429:setBanner:.bannerKind | 变异 - | 读 3
busy | 字面量Y | 写 2665:ingest:.busy | 变异 - | 读 24
cancelingStart | 字面量N | 写 2783:cancelPendingStart:.cancelingStart; 2798:cancelPendingStart:.cancelingStart | 变异 - | 读 3
challenge | 字面量Y | 写 2987:ingestRelogin:.challenge; 3001:ingestRelogin:.challenge; 3028:ingestRelogin:.challenge; 3044:ingestRelogin:.challenge; 3055:ingestRelogin:.challenge; 3171:cancelRelogin:.challenge | 变异 - | 读 15
clock | 字面量Y | 写 301:setClock:.clock; 2523:tickClock:.clock | 变异 - | 读 6
clockState | 字面量Y | 写 2655:ingest:.clockState | 变异 - | 读 7
confirm | 字面量Y | 写 1601:closeSheet:.confirm; 1681:askConfirm:.confirm | 变异 - | 读 3
csrf | 字面量Y | 写 2287:api:.csrf; 2416:pair:.csrf; 2433:poll:.csrf; 2484:onForbidden:.csrf | 变异 - | 读 7
dismissedPlanId | 字面量Y | 写 2852:reselectFailed:.dismissedPlanId; 2871:finishPlanView:.dismissedPlanId | 变异 - | 读 3
filter | 字面量Y | 写 1973:goSigned:.filter; 2210:toggleSearch:.filter.q; 3276:wire:.filter.q; 3283:wire:.filter.q; 3297:wire:.filter.status; 3305:wire:.filter.time | 变异 - | 读 9
flashId | 字面量Y | 写 1980:goSigned:.flashId; 1984:goSigned:.flashId | 变异 - | 读 3
flow | 字面量Y | 写 2972:ingestRelogin:.flow | 变异 - | 读 15
flying | 字面量Y | 写 2434:poll:.flying; 2453:poll:.flying | 变异 - | 读 10
items | 字面量Y | 写 2636:ingest:.items | 变异 - | 读 17
lastOkAt | 字面量Y | 写 2441:poll:.lastOkAt | 变异 - | 读 8
lastOkText | 字面量Y | 写 2660:ingest:.lastOkText | 变异 - | 读 3
listOpen | 字面量Y | 写 2732:startPlan:.listOpen; 2864:reselectFailed:.listOpen; 2874:finishPlanView:.listOpen; 3249:wire:.listOpen | 变异 - | 读 8
login | 字面量Y | 写 2703:ingest:.login | 变异 - | 读 8
notice | 字面量Y | 写 1789:buildRow:.notice; 2645:ingest:.notice; 2731:startPlan:.notice; 2865:reselectFailed:.notice; 2875:finishPlanView:.notice; 2952:removeFromReview:.notice; 3292:wire:.notice | 变异 - | 读 9
nowMs | 字面量Y | 写 1496:canWrite:.nowMs; 1501:refreshControls:.nowMs; 1998:renderItems:.nowMs | 变异 - | 读 10
offlineTries | 字面量Y | 写 1446:syncOffline:.offlineTries; 2463:onPollFail:.offlineTries | 变异 - | 读 5
pairErr | 字面量Y | 写 2351:setPairError:.pairErr; 2366:schedulePairTick:.pairErr; 2397:pair:.pairErr; 2420:pair:.pairErr; 3192:wire:.pairErr | 变异 - | 读 6
pairLockLeft | 字面量Y | 写 2358:beginPairLock:.pairLockLeft; 2364:schedulePairTick:.pairLockLeft; 2373:stopPairLock:.pairLockLeft | 变异 - | 读 7
pairOkPending | 字面量Y | 写 2418:pair:.pairOkPending; 3204:wire:.pairOkPending | 变异 - | 读 3
pairTickTimer | 字面量Y | 写 2362:schedulePairTick:.pairTickTimer; 2363:schedulePairTick:.pairTickTimer; 2372:stopPairLock:.pairTickTimer | 变异 - | 读 5
paired | 字面量Y | 写 2417:pair:.paired; 2443:poll:.paired; 2468:onNeedPair:.paired | 变异 - | 读 10
pairing | 字面量Y | 写 2401:pair:.pairing; 2426:pair:.pairing | 变异 - | 读 3
pcListError | 字面量Y | 写 2664:ingest:.pcListError | 变异 - | 读 4
pending | 字面量Y | 写 2730:startPlan:.pending; 2741:startPlan:.pending.done; 2742:startPlan:.pending.outcome | 变异 - | 读 32
pickId | 字面量Y | 写 2164:renderBoard:.pickId; 2182:renderBoard:.pickId | 变异 - | 读 4
plan | 字面量N | 写 2650:ingest:.plan; 2853:reselectFailed:.plan; 2872:finishPlanView:.plan | 变异 - | 读 26
pollTimer | 字面量Y | 写 2470:onNeedPair:.pollTimer; 2494:schedule:.pollTimer; 2497:schedule:.pollTimer; 3325:wire:.pollTimer; 3335:wire:.pollTimer | 变异 - | 读 13
probed | 字面量Y | 写 2617:probeExistingSession:.probed | 变异 - | 读 2
reconciling | 字面量N | 写 2753:reconcile:.reconciling; 2773:reconcile:.reconciling | 变异 - | 读 3
relConfirm | 字面量Y | 写 1602:closeSheet:.relConfirm; 1666:openRelogin:.relConfirm; 3067:beginRelogin:.relConfirm; 3262:wire:.relConfirm | 变异 - | 读 5
relEnteredAcct | 字面量Y | 写 3068:beginRelogin:.relEnteredAcct; 3087:beginRelogin:.relEnteredAcct | 变异 - | 读 3
relSavedChoice | 字面量Y | 写 3069:beginRelogin:.relSavedChoice; 3088:beginRelogin:.relSavedChoice | 变异 - | 读 3
reloginSetup | 字面量N | 写 2653:ingest:.reloginSetup | 变异 - | 读 8
reloginStarting | 字面量Y | 写 2989:ingestRelogin:.reloginStarting; 3065:beginRelogin:.reloginStarting; 3079:beginRelogin:.reloginStarting; 3092:beginRelogin:.reloginStarting | 变异 - | 读 9
reloginSubmitting | 字面量Y | 写 2988:ingestRelogin:.reloginSubmitting; 2997:ingestRelogin:.reloginSubmitting; 3004:ingestRelogin:.reloginSubmitting; 3020:ingestRelogin:.reloginSubmitting; 3024:ingestRelogin:.reloginSubmitting; 3029:ingestRelogin:.reloginSubmitting; 3045:ingestRelogin:.reloginSubmitting; 3056:ingestRelogin:.reloginSubmitting; 3123:submitRelogin:.reloginSubmitting; 3148:submitRelogin:.reloginSubmitting | 变异 - | 读 15
retry | 字面量Y | 写 2668:ingest:.retry; 3312:wire:.retry.retry_for_s; 3318:wire:.retry.max_attempts | 变异 - | 读 11
retryDirty | 字面量Y | 写 2885:saveRetry:.retryDirty; 3313:wire:.retryDirty; 3319:wire:.retryDirty | 变异 - | 读 4
retryHydrated | 字面量Y | 写 2672:ingest:.retryHydrated | 变异 - | 读 2
retryOptions | 字面量N | 写 2675:ingest:.retryOptions | 变异 - | 读 1
searchOpen | 字面量Y | 写 2207:toggleSearch:.searchOpen | 变异 - | 读 6
seenEventSeq | 字面量Y | 写 - | 变异 2624:ingest:.seenEventSeq.clear(); 2683:ingest:.seenEventSeq.add(); 2685:ingest:.seenEventSeq.delete() | 读 6
selected | 字面量Y | 写 1788:buildRow:.selected; 2639:ingest:.selected; 2863:reselectFailed:.selected; 2873:finishPlanView:.selected; 2951:removeFromReview:.selected; 3291:wire:.selected | 变异 - | 读 20
seq | 字面量Y | 写 2625:ingest:.seq; 2680:ingest:.seq; 2697:ingest:.seq | 变异 - | 读 6
sheetId | 字面量Y | 写 1565:openSheet:.sheetId; 1586:closeSheet:.sheetId | 变异 - | 读 9
sheetOpener | 字面量Y | 写 1564:openSheet:.sheetOpener; 1604:closeSheet:.sheetOpener | 变异 - | 读 3
termsOk | 字面量N | 写 2652:ingest:.termsOk | 变异 - | 读 12
tickMark | 字面量N | 写 2521:tickClock:.tickMark | 变异 - | 读 2
tickTimer | 字面量N | 写 2472:onNeedPair:.tickTimer; 2504:scheduleTick:.tickTimer; 2507:scheduleTick:.tickTimer; 2508:scheduleTick:.tickTimer; 3327:wire:.tickTimer; 3337:wire:.tickTimer | 变异 - | 读 14
whyId | 字面量Y | 写 411:toggleWhy:.whyId; 1968:goSigned:.whyId | 变异 - | 读 5
```

### 清单 2：`local/grab.py` 输出种类、子命令与退出码

脚本 `item2.py` 用 `ast` 枚举全部 `print`、`log`、`sys.stdout.write`、`sys.stderr.write` 调用（含嵌套函数），标出嵌套链。`item2b.py` 枚举各子命令入口函数自身的 `return`，不含嵌套函数。

要点：输出调用共 148 处（`print` 85、`log` 62、`sys.*.write` 1；`_stderr_note` 内部的 `print` 计入 `print`）。`log()`（`grab.py:276–299`）先加北京时间戳（`line = "%s %s" % (stamp, msg)`，L288–289），再 `print` 到 stdout（L299），同时写 `grab.log`。`log_event`（L314）经 `log` 输出。`_stdout_to_stderr`（L256–274）只在 `list --json`（L1354–1429）与 `cancel --json`（L1595）里把 stdout 改道到 stderr。

```
== 顶层函数
def configure_business_clock L91
def business_now L98
def business_bounds L105
def clock_meta L112
def setup_business_clock L125
def setup_console L158
def _school_open L167
def _log_file_lock L191
def rotate_log_file L219
def _stderr_note L244
def _stdout_to_stderr L256
def log L276
def _append_log_line_unlocked L302
def log_event L314
def read_json L325
def write_json_atomic L339
def _session_write_lock L362
def _write_login_file L390
def save_session L402
def save_storage_state L409
def _unlink_quiet L416
def _snapshot_bytes L423
def save_verified_files L432
def _save_verified_files_locked L448
def _restore_original L488
def _rollback_note L515
def token L524
def _hmac_sha256_hex L529
def _xor_base64 L533
def _encode_x_token L540
def sign_request_headers L551
def _request_nonce L576
def _remember_school_date L588
def school_date_now L607
def clear_school_date L613
def _post L618
def _get L669
def clock_sample L691
def clock_skew L754
def _tri_state L761
def _activity_flag L775
def _activity_time L813
def _reward_number L822
def _detail_fields L840
def parse_attendance_detail L848
def fetch_activity_detail L890
def _apply_attendance L908
def enrich_attendance_items L951
def _map_activity L976
def fetch_activities L1004
def _join_state L1034
def is_joined L1056
def parse_ts L1077
def still_relevant L1089
def keep_in_list L1100
def sign_state L1119
def launch_browser L1138
def new_context L1157
def page_local_storage L1164
def session_from_items L1170
def _cmd_login_relay L1188
def cmd_login L1237
def cmd_check L1316
def cmd_list L1333
def _cancel_facts L1489
def _cancel_joined L1505
def run_cancel L1514
def cmd_cancel L1592
def candidates L1608
def pick_activity L1627
def notify L1646
def wait_until L1674
def _by_index_or_name L1694
def _at_or_now L1723
def resolve_target L1739
def retry_anchor L1790
def compute_retry_window L1819
def attempts_allowed L1836
def next_submit_gap L1849
def wait_before_next_submit L1860
def _classify_response L2294
def _decode_body L2320
def _recognizable_code L2338
def _ts_text L2356
def _checkpoint_event L2363
def _retry_event L2382
def _probe_list L2399
def _direct_headers L2406
def fetch_runtime_key L2412
def probe_token L2434
def check_token L2469
def _known_policy_start L2475
def _policy_window L2485
def cmd_grab L2502
def cmd_selftest L3970
def main L3997
== 输出调用
L299 | print | log | 嵌套链=log | line
L320 | log | log_event | 嵌套链=log_event | format_event_line(event, source, level=level, activity_id=activity_id or _EVENT_CONTEXT['a
L1245 | print | cmd_login | 嵌套链=cmd_login | '=' * 64
L1246 | print | cmd_login | 嵌套链=cmd_login | '即将打开浏览器，请在窗口里完成学生登录（账号 + 密码 + 图形验证码）。'
L1247 | print | cmd_login | 嵌套链=cmd_login | '登录成功会自动保存登录态并关闭窗口；最多等待 %d 秒。' % args.timeout
L1248 | print | cmd_login | 嵌套链=cmd_login | '=' * 64
L1311 | print | cmd_login | 嵌套链=cmd_login | '[OK] 登录成功，登录态已保存（失效后重新运行本步即可）。'
L1328 | print | cmd_check | 嵌套链=cmd_check | '[X] %s' % msg
L1329 | print | cmd_check | 嵌套链=cmd_check | '    请运行：python grab.py login   （或双击 1-登录.bat）'
L1469 | print | cmd_list | 嵌套链=cmd_list | '%3s  %s  %s  %s' % ('#', '报名开始', '状态', '活动名')
L1474 | print | cmd_list | 嵌套链=cmd_list | '\n提示：双击 2-抢活动.bat 可直接选择并到点抢；也可以双击 4-图形界面.bat 用鼠标点。'
L1568 | log | run_cancel | 嵌套链=run_cancel | '[cancel] 前置核对通过，调用取消接口一次'
L1588 | log | run_cancel | 嵌套链=run_cancel | '[cancel] 复查没查到结果'
L1604 | print | cmd_cancel | 嵌套链=cmd_cancel | json.dumps(result, ensure_ascii=False)
L1633 | print | pick_activity | 嵌套链=pick_activity | '%-4s %-19s %-19s %s' % ('序号', '报名开始', '活动开始', '活动名')
L1777 | print | resolve_target | 嵌套链=resolve_target | '\n已选择：%s' % act['name']
L1778 | print | resolve_target | 嵌套链=resolve_target | '报名开始：%s   活动时间：%s   地点：%s' % (act['sign_start'], act['act_start'], act['place'])
L2379 | log | _checkpoint_event | 嵌套链=_checkpoint_event | '[checkpoint] ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
L2389 | log | _retry_event | 嵌套链=_retry_event | '[retry] ' + body
L2463 | log | probe_token | 嵌套链=probe_token | '[i] 登录探测：4001 后复查恢复（复查 code=%s）' % (again_code,)
L2775 | print | cmd_grab | 嵌套链=cmd_grab | '[i] 目标：%s' % display
L3973 | print | cmd_selftest | 嵌套链=cmd_selftest | '[i] 自检：拉起浏览器并打开站点首页 ...'
L250 | print | _stderr_note | 嵌套链=_stderr_note | text
L517 | sys.stderr.write | _rollback_note | 嵌套链=_rollback_note | '[X] 登录态回滚没成功：%s 可能还是新内容（%s）\n' % (Path(path).name, type(exc).__name__)
L1307 | print | cmd_login | 嵌套链=cmd_login | '[X] 已保存登录态，但接口校验失败：%s' % msg
L1319 | print | cmd_check | 嵌套链=cmd_check | '[OK] 登录态有效。'
L1322 | log | cmd_check | 嵌套链=cmd_check | '[clock] ' + json.dumps(sample, ensure_ascii=False, separators=(',', ':'))
L1359 | print | cmd_list | 嵌套链=cmd_list | '[X] %s' % msg
L1360 | print | cmd_list | 嵌套链=cmd_list | '    请先运行：python grab.py login（或点界面上的「登录」）'
L1420 | print | cmd_list | 嵌套链=cmd_list | '[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。'
L1421 | print | cmd_list | 嵌套链=cmd_list | '    想连历史活动一起看：python grab.py list --all'
L1465 | print | cmd_list | 嵌套链=cmd_list | json.dumps(out, ensure_ascii=False)
L1473 | print | cmd_list | 嵌套链=cmd_list | '%3d  %s  %s  %s' % (i, act['sign_start'] or '-', flag, act['name'])
L1520 | log | refuse | 嵌套链=refuse<run_cancel | '[cancel] 前置核对未通过：%s（未调取消接口）' % reason
L1575 | log | run_cancel | 嵌套链=run_cancel | '[cancel] 复查：学校记录里已没有这场报名'
L1578 | log | run_cancel | 嵌套链=run_cancel | '[cancel] 复查：仍是已报名'
L1631 | print | pick_activity | 嵌套链=pick_activity | '[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。'
L1635 | print | pick_activity | 嵌套链=pick_activity | '%-4d %-19s %-19s %s' % (i, act['sign_start'], act['act_start'][:16], act['name'])
L1643 | print | pick_activity | 嵌套链=pick_activity | '输入的序号不对，请重试。'
L1667 | log | notify | 嵌套链=notify | '[i] 飞书通知%s' % ('已发送' if ok else '失败：%s' % str(payload)[:80])
L1711 | print | _by_index_or_name | 嵌套链=_by_index_or_name | '[X] 没有名称含「%s」的活动。' % kw
L1712 | print | _by_index_or_name | 嵌套链=_by_index_or_name | '    运行 python grab.py list 查看当前可抢的活动。'
L1715 | print | _by_index_or_name | 嵌套链=_by_index_or_name | '[X] 「%s」匹配到 %d 个活动，请改用 --pick 序号：' % (kw, len(hits))
L1767 | print | resolve_target | 嵌套链=resolve_target | '[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。'
L2510 | log | cmd_grab | 嵌套链=cmd_grab | '[X] 北京时间未校准，本次自动报名不启动'
L2511 | print | cmd_grab | 嵌套链=cmd_grab | '\n[X] 暂时无法获取可信北京时间，自动报名没有开始。'
L2512 | print | cmd_grab | 嵌套链=cmd_grab | '    登录态与活动列表不受影响；稍后重试。'
L2558 | log | terminal | 嵌套链=terminal<cmd_grab | '[retry] kind=done attempts=%d stop_reason=%s retry_deadline=%d sign_end=%d pending=%d str
L2619 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 报名失败（尝试 %d 次，最近原因 %s）' % (attempts, last or '名额已满/未开放')
L2622 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[X] 没抢到：%s（%s）' % (last or '名额已满／页面未放开', tail_note)
L2623 | print | terminal | 嵌套链=terminal<cmd_grab | '    建议手动打开活动页确认，必要时再试一次。'
L2681 | log | _wait_for_relogin | 嵌套链=_wait_for_relogin<cmd_grab | '[!] 登录失效（%s）：等自动登录，最多 %d 秒，期间不提交' % (where, int(wait_s))
L2698 | log | _wait_for_relogin | 嵌套链=_wait_for_relogin<cmd_grab | '[X] 等自动登录超时（%s）' % where
L2709 | print | cmd_grab | 嵌套链=cmd_grab | '[X] %s' % token_detail
L2710 | print | cmd_grab | 嵌套链=cmd_grab | '    请先运行：python grab.py login'
L2739 | log | cmd_grab | 嵌套链=cmd_grab | '[clock] ' + json.dumps(sample, ensure_ascii=False, separators=(',', ':'))
L2781 | print | cmd_grab | 嵌套链=cmd_grab | '[i] 活动已开放，本次立即报名/抢名额（原定开放 %s）' % original_at
L2782 | print | cmd_grab | 嵌套链=cmd_grab | '[i] 本次执行：%s；失败重试窗口 %.0f 秒' % (target['at'], args.window)
L2785 | print | cmd_grab | 嵌套链=cmd_grab | '[i] 报名开始：%s；提前 %.0f 秒打开页面；失败重试窗口 %.0f 秒' % (target['at'], args.lead, args.window)
L2788 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 报名截止：%s；重试到 %s 截止' % (_ts_text(sign_end_ts), _ts_text(state['deadline']))
L4062 | print | main | 嵌套链=main | '[X] %s' % SITE_CONFIG_MESSAGE
L335 | log | read_json | 嵌套链=read_json | '[!] 读取 %s 失败（%s）' % (Path(path).name, type(exc).__name__)
L397 | log | _write_login_file | 嵌套链=_write_login_file | '[X] %s 没写成：%d 秒内没拿到登录态写锁（另一个进程正在写）' % (Path(target).name, int(timeout_s))
L444 | log | save_verified_files | 嵌套链=save_verified_files | '[X] 登录态没写成：%d 秒内没拿到写锁（另一个进程正在写）' % int(timeout_s)
L1282 | print | cmd_login | 嵌套链=cmd_login | '[X] 等了 %d 秒仍未检测到登录成功，请重试。' % args.timeout
L1300 | print | cmd_login | 嵌套链=cmd_login | '[X] 登录成功，但登录态没能写入（另一个进程正在写），请稍后重新登录。'
L1324 | print | cmd_check | 嵌套链=cmd_check | '[!] 学校 HTTP Date 与本机时间有偏差（粗测含网络误差约 ±%.1f 秒）。该粗测只作诊断，报名调度按工具自己的北京时间执行。' % (sample.get('unc
L1372 | print | cmd_list | 嵌套链=cmd_list | '[X] 登录态已失效（%s），请先运行 python grab.py login' % exc
L1375 | print | cmd_list | 嵌套链=cmd_list | '[X] 拉取活动失败：%s' % exc
L1417 | print | cmd_list | 嵌套链=cmd_list | '[]'
L1670 | log | notify | 嵌套链=notify | '[i] 飞书通知失败：%s' % type(exc).__name__
L1703 | print | _by_index_or_name | 嵌套链=_by_index_or_name | '[X] --pick %d 超出范围（当前有 %d 个可抢的活动）' % (pick, len(cand))
L1704 | print | _by_index_or_name | 嵌套链=_by_index_or_name | '    运行 python grab.py list 查看序号。'
L1762 | print | resolve_target | 嵌套链=resolve_target | '[X] 登录态已失效（%s），请先运行 python grab.py login' % exc
L1783 | print | resolve_target | 嵌套链=resolve_target | '[i] 已取消。'
L2192 | log | register_request | 嵌套链=register_request | 'attempt_no 未递增（%s → %s）：倒序重算不再等于发送序' % (self._last_attempt_no, attempt_no)
L2519 | log | cmd_grab | 嵌套链=cmd_grab | '[X] 北京时间在入口处不可用，本次自动报名不启动'
L2520 | print | cmd_grab | 嵌套链=cmd_grab | '\n[X] 暂时无法获取可信北京时间，自动报名没有开始。'
L2527 | print | cmd_grab | 嵌套链=cmd_grab | '[X] 报名截止时间格式不对：%r' % (args.sign_end,)
L2532 | print | cmd_grab | 嵌套链=cmd_grab | '[X] 报名开始时间格式不对：%r' % (args.at,)
L2566 | log | terminal | 嵌套链=terminal<cmd_grab | '[OK] 报名成功（尝试 %d 次）' % attempts
L2567 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[OK] 报名成功：%s' % display
L2568 | print | terminal | 嵌套链=terminal<cmd_grab | '     不想去请尽快在活动页取消，别占名额。'
L2574 | print | terminal | 嵌套链=terminal<cmd_grab | '[i] 你已经报过这个活动了。'
L2577 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 登录失效（尝试 %d 次）' % attempts
L2578 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[X] 登录失效：%s' % (last or '学校要求重新登录')
L2579 | print | terminal | 嵌套链=terminal<cmd_grab | '    重试没有意义，请先重新登录再跑。'
L2583 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 登录状态暂时无法确认（%s）' % (last or '接口没有应答')
L2584 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[X] 登录状态暂时无法确认：%s' % (last or '接口没有应答')
L2585 | print | terminal | 嵌套链=terminal<cmd_grab | '    先检查网络或校园网，再点「刷新」重试；不要急着重新登录。'
L2588 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 达到最大提交次数 %d（最近原因 %s）' % (attempts, last)
L2589 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[X] 已提交 %d 次仍没成功：%s' % (attempts, last or '名额已满')
L2590 | print | terminal | 嵌套链=terminal<cmd_grab | '    到达你设置的最大提交次数，停止重试。'
L2594 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 结果未确认（已发起 %d 次提交，仍有 %d 次没有确定结果）' % (attempts, state['pending'])
L2596 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[?] 结果未确认：提交已经发出，但没有拿到学校的确定结果。'
L2597 | print | terminal | 嵌套链=terminal<cmd_grab | '    请打开活动页核对是否已报名；不要直接重复提交。'
L2602 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 北京时间暂不可用，已停止自动动作（尝试 %d 次）' % attempts
L2603 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[X] 暂时无法获取可信北京时间，已停止自动报名动作。'
L2604 | print | terminal | 嵌套链=terminal<cmd_grab | '    已发出的提交不受影响，请到活动页核对；不要直接重复提交。'
L2609 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 本场结束：%s（尝试 %d 次）' % (label, attempts)
L2610 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[X] 没报上：%s' % label
L2611 | print | terminal | 嵌套链=terminal<cmd_grab | '    ' + REPLY_STOP_HINTS[stop_reason]
L2615 | log | terminal | 嵌套链=terminal<cmd_grab | '[X] 本机流程异常结束（%s）' % (last or '未知异常')
L2616 | print | terminal | 嵌套链=terminal<cmd_grab | '\n[X] 本机流程异常结束：%s' % (last or '未知异常')
L2617 | print | terminal | 嵌套链=terminal<cmd_grab | '    这不代表学校拒绝了报名；请到活动页核对后再决定。'
L2741 | print | cmd_grab | 嵌套链=cmd_grab | '[!] 学校 HTTP Date 粗测与本机有偏差（含网络误差约 ±%.1f 秒）；该粗测只作诊断参考，报名调度按工具的独立北京时间执行。' % (sample.get('unc
L2758 | print | cmd_grab | 嵌套链=cmd_grab | '[X] 报名开始时间格式不对：%r' % (target['at'],)
L3983 | print | cmd_selftest | 嵌套链=cmd_selftest | '[OK] 打开成功：title=%s' % title
L3984 | print | cmd_selftest | 嵌套链=cmd_selftest | '[i] 页面片段：%s' % body
L4071 | print | main | 嵌套链=main | '\n[i] 已手动中断。'
L1257 | print | cmd_login | 嵌套链=cmd_login | '[X] 打不开登录页：%s' % type(exc).__name__
L1600 | log | cmd_cancel | 嵌套链=cmd_cancel | '[cancel] 异常 %s' % type(exc).__name__
L1718 | print | _by_index_or_name | 嵌套链=_by_index_or_name | '    %-3d %s  %s' % (i, a['sign_start'], a['name'])
L1749 | print | resolve_target | 嵌套链=resolve_target | '[X] 活动 %s 找不到报名开始时间，请显式传 --at' % aid
L2694 | log | _wait_for_relogin | 嵌套链=_wait_for_relogin<cmd_grab | '[i] 自动登录完成：换上新的登录态，继续'
L3727 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 开始盯按钮'
L3986 | print | cmd_selftest | 嵌套链=cmd_selftest | '[!] 页面内容看起来不对，可能被网络/代理拦截。'
L3990 | print | cmd_selftest | 嵌套链=cmd_selftest | '[X] 自检失败：%s' % type(exc).__name__
L3991 | print | cmd_selftest | 嵌套链=cmd_selftest | '    请确认已安装：pip install playwright && playwright install chromium'
L1268 | print | cmd_login | 嵌套链=cmd_login | '[X] 窗口被关掉了，登录未完成。'
L1392 | log | cmd_list | 嵌套链=cmd_list | '[!] 北京时间暂不可用，回包也没有可用的 Date 头：本次保留全部活动，开放状态显示未知。'
L1395 | log | cmd_list | 嵌套链=cmd_list | '[!] 北京时间暂不可用：已按学校服务器时间筛选要显示的活动。'
L2818 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 运行时密钥：%s' % key_reason
L2835 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 详情页已加载'
L2840 | log | cmd_grab | 嵌套链=cmd_grab | '[i] dry-run：joined=%s buttons=%s' % (is_joined(target['id'], budget=budget), btns)
L2858 | print | cmd_grab | 嵌套链=cmd_grab | '[i] 后台等待中，到点自动提交；想看着它点就加 --headed。'
L2868 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 活动已开放，立即报名/抢名额'
L2870 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 开始等待开放'
L2932 | log | _downgrade | 嵌套链=_downgrade<cmd_grab | '[!] 本场切换为点击兜底（原因：%s）' % reason
L2971 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 报名路径：直发（运行时密钥）'
L2974 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 报名路径：点击（原因：%s）' % path_reason
L3186 | log | _settle_one | 嵌套链=_settle_one<cmd_grab | '[i] 第 %d 次提交：%s' % (state['attempts'], _reason_with_raw(reply_raw))
L3216 | log | _register_request | 嵌套链=_register_request<cmd_grab | '[i] 第 %d 次提交：已发起' % state['attempts']
L2830 | log | cmd_grab | 嵌套链=cmd_grab | '[!] 详情页打不开（%s）：直发照常，点击兜底不可用' % type(exc).__name__
L2948 | log | _rekey_after_version | 嵌套链=_rekey_after_version<cmd_grab | '[i] 版本不兼容：已重取运行时密钥，继续直发'
L3260 | log | _settle_direct_event | 嵌套链=_settle_direct_event<cmd_grab | '[i] 第 %d 次提交：直发已发起' % state['attempts']
L3346 | log | _settle_direct_event | 嵌套链=_settle_direct_event<cmd_grab | '[i] 第 %d 次提交：%s' % (state['attempts'], _reason_with_raw(reply_raw))
L3376 | log | _try_direct_fire | 嵌套链=_try_direct_fire<cmd_grab | '[!] token 缺失：停止发送'
L3624 | log | _precheck_send | 嵌套链=_precheck_send<cmd_grab | '[!] 预检跳过：登录态里没有 token'
L3693 | log | _precheck_before_open | 嵌套链=_precheck_before_open<cmd_grab | '[i] 预检回包：%s｜%s' % (reply.label, reply.raw)
L3762 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 复查登录结论 %s：不判失效，继续发送' % recheck
L3888 | log | cmd_grab | 嵌套链=cmd_grab | '[i] 本次点击没有发出提交：%s' % (state['last_reason'] or '未点开确认框')
L3324 | log | _settle_direct_event | 嵌套链=_settle_direct_event<cmd_grab | '[!] ' + anomaly
L3691 | log | _precheck_before_open | 嵌套链=_precheck_before_open<cmd_grab | '[i] 预检通过：学校回「报名未开始」，密钥和格式都对（%s）' % reply.raw
L3078 | log | _apply_conclusion | 嵌套链=_apply_conclusion<cmd_grab | '[!] 提交中收到 4001（%s），停发并复查登录' % reply.raw
L3661 | log | _precheck_send | 嵌套链=_precheck_send<cmd_grab | '[!] 预检回了 HTTP %s，没有业务回包' % (ev.get('http_status'),)
L3686 | log | _precheck_before_open | 嵌套链=_precheck_before_open<cmd_grab | '[!] 预检没有拿到学校回包：不影响正式提交，到点照常发'
L3121 | log | _apply_conclusion | 嵌套链=_apply_conclusion<cmd_grab | '[i] 学校还没开门：已过预期开放 %d 秒仍回「报名未开始」，按全速节奏继续（%s）' % (int(late_s), reply.raw)
== sys.exit / exit 调用
L4076 | sys.exit(main()) | 所在函数=(module)
== 顶层 __main__ 块
main block L4075
```

子命令自身的 `return`（`item2b.py` 输出）。`main()` 直接返回 `args.func(args)`，`sys.exit(main())` 在 L4076：

```
cmd_login L1237 自身 return: [(1239, '_cmd_login_relay(args)'), (1261, '2'), (1272, '1'), (1286, '1'), (1303, '2'), (1310, '2'), (1313, '0')]
cmd_check L1316 自身 return: [(1327, '0'), (1330, '2')]
cmd_list L1333 自身 return: [(1361, '2'), (1373, '2'), (1376, '2'), (1419, '0'), (1422, '0'), (1467, '0'), (1475, '0')]
   嵌套函数: ['_emit_list_timing', 'rank']
run_cancel L1514 自身 return: [(1525, "refuse('site_unconfigured')"), (1527, "refuse('not_in_list')"), (1531, "refuse('login_expired')"), (1533, "refuse('unknown_state')"), (1540, "refuse('clock_unavailable')"), (1548, "refuse('clock_unavailable')"), (1549, "refuse('unknown_state')"), (1551, "refuse('not_signed')"), (1555, "refuse('unknown_state')"), (1558, "refuse('not_allowed')"), (1560, "refuse('unknown_state')"), (1564, "refuse('clock_unavailable')"), (1566, "refuse('window_closed')"), (1576, "{'ok': True, 'kind': 'cancelled'}"), (1587, 'result'), (1589, "{'ok': False, 'kind': 'unknown'}")]
   嵌套函数: ['refuse']
cmd_cancel L1592 自身 return: [(1605, "0 if result.get('kind') == 'cancelled' else 2")]
cmd_grab L2502 自身 return: [(2513, '3'), (2521, '3'), (2528, '2'), (2533, '2'), (2654, "terminal('sign_end' if binding == 'sign_end' else 'retry_duration')"), (2656, '_clock_stop()'), (2705, "_budget_stop('鉴权')"), (2707, '_clock_stop()'), (2711, '3'), (2717, "_budget_stop('鉴权')"), (2719, '_clock_stop()'), (2721, "terminal('login_invalid')"), (2725, "terminal('auth_unavailable')"), (2731, '_clock_stop()'), (2736, "_budget_stop('粗校时')"), (2738, '_clock_stop()'), (2748, "_budget_stop('查目标')"), (2750, '_clock_stop()'), (2752, '0'), (2759, '2'), (2770, "terminal('sign_end' if binding == 'sign_end' else 'retry_duration')"), (2772, '_clock_stop()'), (2796, "_budget_stop('前置检查')"), (2798, '_clock_stop()'), (2842, '0'), (2853, "terminal('already_signed')"), (2866, '_clock_stop()'), (3922, '_finalize(stop_reason)'), (3928, '_clock_stop()'), (3929, "_finalize('clock_unavailable')"), (3934, "_budget_stop('页面')"), (3935, '_finalize(_fallback, fallback=_fallback)'), (3939, "terminal('process_error')"), (3940, "_finalize('process_error', fallback='process_error')"), (3962, '_clock_stop()'), (3965, "terminal('sign_end' if state['binding'] == 'sign_end' else 'retry_duration')"), (3968, "terminal('process_error')")]
   嵌套函数: ['terminal', '_clock_stop', '_budget_stop', '_wait_for_relogin', '_downgrade', '_rekey_after_version', '_is_signup_url', '_sync_pending', 'on_request', 'on_response', 'on_requestfailed', '_sync_budget_window', '_apply_conclusion', '_reason_with_raw', '_settle_one', '_settle_failed', '_register_request', '_settle_pending', '_settle_direct_event', '_drain_direct', '_try_direct_fire', '_pump_wait', '_may_fire', '_fallback_terminal', '_finalize', '_finalize_once', '_precheck_send', '_precheck_before_open']
cmd_selftest L3970 自身 return: [(3987, '2'), (3988, '0'), (3992, '2')]
main L3997 自身 return: [(4063, '2'), (4069, 'args.func(args)'), (4072, '130')]
```

人工对应（已逐个对照源码行）：

- `cmd_login`：L1239 返回 `_cmd_login_relay(args)`（relay 模式，退出码由 `login_relay.run_http_relay` 决定）。普通模式：L1261 返回 2（登录页打不开）；L1272 返回 1（窗口被关）；L1286 返回 1（超时）；L1303 返回 2（登录态写不进）；L1310 返回 2（校验失败）；L1313 返回 0（成功）。

- `cmd_check`：L1327 返回 0（登录态有效，此分支内会 `log("[clock] …")`）；L1330 返回 2（`print("[X] …")` 之后）。

- `cmd_list`：L1361、L1373、L1376 返回 2（登录态失效、`PermissionError`、其他异常）。L1419 在 `--json` 且无数据时先 `print("[]")` 再返回 0；L1422 为文本模式无数据，返回 0；L1467、L1475 在有数据时返回 0。

- `cmd_cancel`：L1605 `0 if result.get("kind") == "cancelled" else 2`。`run_cancel` 的返回值是字典，不是退出码。

- `cmd_grab`：自身的 `return` 里大量调用嵌套 helper（`terminal`、`_budget_stop`、`_clock_stop`、`_finalize`），它们的返回值直接成为 `cmd_grab` 的退出码（L2654、L2656、L2705–2738、L2770–2798、L2853、L3922–3968）。`terminal` 的返回值由 `stop_reason` 决定：`success`、`already_signed` 返回 0（`grab.py:2565–2575`）；`login_invalid`、`auth_unavailable`、`clock_unavailable` 返回 3（`grab.py:2576–2584`、`2601–2605`）；`max_attempts`、`unconfirmed`、`REPLY_STOP_HINTS` 的键、`process_error` 与其余失败返回 2（`grab.py:2587–2618`）。`terminal` 若已标记 `done`，直接返回 2（L2556）。

- `cmd_grab` 的非终态分支：L2513、L2521 返回 3（北京时间不可用）；L2528、L2533、L2759 返回 2（时间格式错）；L2711 返回 3（登录态缺 token）；L2752 `if not target: return 0`，而 `resolve_target` 返回 `None` 的情形包括 L1749（「找不到报名开始时间」）与 L1783（「已取消」）；L2842 dry-run 返回 0。

- `cmd_selftest`：L3987 返回 2（页面内容不对）；L3988 返回 0；L3992 返回 2（异常）。

- `main`：L4063 返回 2（站点未配置，`cancel` 除外）；L4072 返回 130（KeyboardInterrupt）。

### 清单 3：全仓解析方（按前缀、正则、子串、`json.loads` 读 stdout）

搜索范围：`local/`（含 `tests/`）、`tools/`、`contracts/`；排除 `design/archive/` 与原型目录（它们不是产品解析方）。表中「对带时间戳行」一列指：若 worker 输出经 `log()` 带上北京时间戳，该解析是否仍然成立。

| # | 位置（基线） | 对象 | 匹配方式 | 对带时间戳行 |
|---|---|---|---|---|
| P1 | `local/domain/retry_rules.py:25` `ATTEMPT_RE` | 「第 N 次提交」 | 正则 `^(?:\[i\]\s*)?第 (\d+) 次提交`，锚定行首 | 不成立 |
| P2 | `local/domain/retry_rules.py:28–46` `parse_retry_line` | `[retry] …` 结构化行 | `text.startswith("[retry] ")`，再 `partition(" last_reason=")` | 不成立 |
| P3 | `local/application/plan_service.py:252–326` `feed()` | 计划运行时 worker 的每一行 | 调用 P1（L269）、P2（L276）、`parse_checkpoint_line`（L262） | P1、P2 不成立；checkpoint 成立 |
| P4 | `local/application/plan_service.py:406–413` 收尾取终态 | `[retry]` 终态行 | 逆序对 `tail` 调用 P2（L410） | 不成立 |
| P5 | `local/domain/worker_lines.py:14–38` `parse_checkpoint_line` | `[checkpoint] {json}` | `text.find("[checkpoint] ")` 后 `json.loads` | 成立（子串定位） |
| P6 | `local/domain/worker_lines.py:41–59` `parse_clock_line` | `[clock] {json}` | `line.find("[clock] ")` 后 `json.loads` | 成立 |
| P7 | `local/domain/plan_rules.py:176–177` | 「你已经报过这个活动」 | 子串 `in` | 成立 |
| P8 | `local/domain/plan_rules.py:183–184` | 「[OK] 报名成功」 | 子串 `in` | 成立 |
| P9 | `local/domain/plan_rules.py:208–211` 失败原因 | 「[X] 」行 | 逆序取 `line.startswith("[X] ")` | 对 `log()` 输出的 [X] 行不成立；对 `print()` 输出的 [X] 行成立 |
| P10 | `local/domain/plan_rules.py:224–225` | 「登录失效」 | `"登录失效" in "".join(tail)` | 成立 |
| P11 | `local/domain/login_rules.py:173–175` `check_reason_line` | `check` 输出的第一条「[X] 」行 | 先按子串去掉 `[clock] `、`[checkpoint] ` 行，再 `startswith("[X] ")` | 同 P9，取决于是 `log()` 还是 `print()` |
| P12 | `local/application/login_service.py:59–72` `done_result` | 登录/报名进程的 tail | L68 `t.startswith("[X] ")`；grab 另查子串「报名成功」（L64） | `[X]` 同 P9；「报名成功」成立 |
| P13 | `local/app.py:4583–4600` `Api._pump` 读 worker stdout | `[login] ` 行与 tail | L4592 `line.startswith("[login] ")`；tail 交 `done_result`（L4599） | 见 P12 与 P14 |
| P14 | 输出端 `local/login_relay.py:206`；解析端 `local/application/login_relay_service.py:394–398` | `[login] {json}` | 输出端 `stdout.write(LOGIN_PREFIX + json)`，不经 `log()`；解析端 `startswith` 后 `json.loads` | 成立（输出端不带戳） |
| P15 | `local/domain/cancel_rules.py:44–52` | `cancel --json` 的 stdout | 取最后一个非空行 `json.loads` | 成立（stdout 已改道） |
| P16 | `local/app.py:2703` | `list --json` 的 stdout | `json.loads(res["stdout"])`，stderr 不混入 | 成立 |
| P17 | `local/gui.py:895` | `list --json` 的 stdout（另一个界面入口） | `json.loads(out.splitlines()[-1])` | 成立；但全仓没有 `import gui` 或 `from gui`，是否仍被使用需人工确认 |
| P18 | `local/app.py:4639–4649` | `_ATTEMPT_RE`、`_parse_retry_line`、`_check_reason_line` | 仅作再导出，`local/tests` 中的 `test_retry_policy.py`、`test_session_persistence.py`、`test_ui_contract.py` 调用 | 不参与生产路径 |
| P19 | `local/ui/**/*.js`（不含 `m/`） | 桌面前端 | 不解析 worker 文本行，只消费 `window.onBackend.<kind>` 的结构化 payload（`local/ui/app.js:90–165`） | 不适用 |

测试中的替身输入（与生产输出的形状差异）：

- `local/tests/test_retry_policy.py:269–405`：fake worker 用 `print('[retry] …')`、`print('[i] 第 N 次提交：…')` 直接输出，行首没有时间戳。
- `local/tests/test_retry_events.py:17–33`：直接把 `"[retry] kind=…"` 字符串交给 `parse_retry_line`，不经过 `feed()`。
- `local/tests/test_application_services.py:141–142`：直接把 `"[i] 第 1 次提交：已发起"`、`"[X] 没抢到：名额已满"` 放进 tail 交给收尾分类，同样没有时间戳。
- `local/tests/test_clock_tail.py:294–300` 与 `local/tests/test_ui_reliability.py:1768`：有带戳的行，但测的是前端日志呈现，不经过 `feed()`。

W6 数据流（独立推导，供第二步对照）：

1. 生产：`terminal()`（`grab.py:2553–2618`，其中 `[retry] kind=done` 在 L2558）、`_retry_event`（L2382–2390，发 `[retry] kind=…`）、以及 L3186、L3216、L3260、L3346 的「第 N 次提交」行，全部经 `log()`。stdout 上的行形如 `2026-11-13 10:00:00 [retry] kind=done …` 或 `2026-11-13 10:00:00 [i] 第 3 次提交：…`，前缀由 `log()` 的 L288–289 产生。
2. 读取：`plan_service.py:178` `lines.put(line.rstrip("\r\n"))`，只去换行，不去时间戳。
3. 解析：`feed()`（L252）把这一行交给 `ATTEMPT_RE.match`（L269，锚定行首，不匹配）和 `parse_retry_line`（L276，`startswith`，不匹配）。收尾时 `reversed(tail)` 再交 `parse_retry_line`（L410），同样不匹配。
4. 结果：生产的计划模式下，`[retry]` 终态行与「第 N 次提交」行都不被解析。`observed["attempts"]` 不由它们更新；`stop` 为空；`classify_task_stop` 中 `stop.get("stop_reason")` 为空。`parse_checkpoint_line`（P5）用 `find` 定位，仍然成立。
5. 测试为什么没发现：`test_retry_policy.py` 的 fake worker 用 `print`（无戳），与生产不一致。
6. `print()` 输出的行没有戳（例如 `grab.py` L2578 `\n[X] 登录失效：…`、L2622 `\n[X] 没抢到：…`、L2709 `[X] %s`）。所以 P9 对 `print()` 的 [X] 行仍然成立，对 `log()` 的 [X] 行不成立。
7. 效果（代码层推断，需测试定）：生产中收尾时 `stop_reason` 为空，`classify_task_stop` 会落到 `process_error`（`plan_rules.py:224–225`），或者 `reason` 取「退出码 N」（L227）。端到端显示是否如此，需用带戳的 stdout 替身驱动 `run_plan_task` 来确定。

### 清单 4：`local/app.py` 的 `Api` 公开方法（ast）

```
Api 类体 L813-L4620，公开方法 60 个
| L1036 | `clock_snapshot()` |
| L1046 | `sync_clock()` |
| L1149 | `bootstrap()` |
| L1245 | `help()` |
| L1425 | `download_advanced_feature(key)` |
| L1452 | `cancel_advanced_feature_download(key)` |
| L1459 | `enable_advanced_feature(key)` |
| L1488 | `advanced_component_location(key)` |
| L1506 | `open_advanced_component_dir(key)` |
| L1525 | `advanced_features_state()` |
| L1606 | `inspect_advanced_component(key, path)` |
| L1624 | `pick_advanced_component(key)` |
| L1644 | `install_advanced_feature(key, path)` |
| L1733 | `remove_advanced_feature(key)` |
| L1770 | `save_relogin_credentials(username, password)` |
| L1795 | `clear_relogin_credentials()` |
| L2052 | `front_ready()` |
| L2057 | `check_update(request_id)` |
| L2117 | `update_download(request_id)` |
| L2171 | `update_cancel()` |
| L2177 | `update_launch(request_id)` |
| L2252 | `check(request_id)` |
| L2283 | `list_activities(request_id)` |
| L2555 | `cancel_signup(activity_id)` |
| L2762 | `login()` |
| L2780 | `grab(activity_id, name, at, headed)` |
| L2854 | `start_request_state(request_id)` |
| L2891 | `cancel_start_request(request_id)` |
| L2923 | `start_plan(items, headed, retry_policy, request_id, source)` |
| L3234 | `cancel_task(plan_id, task_id)` |
| L3242 | `stop_plan(plan_id)` |
| L3271 | `plan_active_for_close()` |
| L3310 | `ask_window_close()` |
| L3334 | `request_window_close(action)` |
| L3389 | `hide_window()` |
| L3427 | `show_window()` |
| L3443 | `window_visibility()` |
| L3521 | `shutdown()` |
| L3621 | `stop()` |
| L3767 | `phone_access_state()` |
| L3812 | `start_phone_access(channel)` |
| L3897 | `set_phone_access_preferences(preferred_channel)` |
| L3913 | `restore_phone_access()` |
| L3937 | `schedule_phone_restore(window)` |
| L3963 | `schedule_component_auto_update(window)` |
| L4017 | `stop_phone_access()` |
| L4043 | `prepare_phone_relogin(username, password, save)` |
| L4153 | `relogin_begin(username, password, save)` |
| L4182 | `relogin_submit(flow_id, challenge_id, code)` |
| L4186 | `relogin_cancel(flow_id)` |
| L4194 | `relogin_auto_once()` |
| L4211 | `phone_relogin_begin(username, password, save)` |
| L4244 | `phone_relogin_submit(flow_id, challenge_id, code)` |
| L4248 | `phone_relogin_cancel(flow_id)` |
| L4333 | `open_data()` |
| L4344 | `open_latest_release()` |
| L4357 | `get_license_text()` |
| L4376 | `save_prefs(prefs)` |
| L4383 | `accept_terms(document_version)` |
| L4409 | `withdraw_terms()` |
```

### 清单 5：桌面前端 `esc(` 调用点（`local/ui/` 不含 `m/`）

脚本 `item5.py` 逐个列出调用，并按前文粗分类（分类结果只作参考，逐条已人工复核）。`esc`（`local/ui/state/time.js:123–125`）只转义 `& < > "`，**不转义单引号**。全部调用中，没有一处与单引号属性（`='`）同行；没有 `on*` 事件处理器字符串中的 `esc(`；没有 `href`/`src` 中的 `esc(`。`innerHTML` 中不与 `esc(` 同行的 39 处，多数经带转义的辅助函数拼接；已抽查 `plan-panel.js:709`（数值与静态文字）和 `plan-panel.js:1464`（静态字符串）。

```
local/ui/controllers/window.js:88 | 文本节点 | return "<li" + cls + "><b>" + esc(line.label) + "</b><span>" + esc(line.text) + "</span></li>";
local/ui/controllers/window.js:88 | 文本节点 | return "<li" + cls + "><b>" + esc(line.label) + "</b><span>" + esc(line.text) + "</span></li>";
local/ui/state/filters.js:54 | 文本节点 | const add = (text, unknown) => flags.push('<span class="activity-flag' + (unknown ? " is-unknown" : "") + '">'
local/ui/state/filters.js:86 | 双引号属性 | if (rw.pend) return '<span class="rw" title="' + esc(rw.title) + '"><span class="rw-p">奖励同步中</span></span>';
local/ui/state/filters.js:88 | 文本节点 | const ptsChip = rw.pts ? '<span class="rw-c pt"><b>' + esc(rw.pts) + "</b>分</span>" : '<span class="rw-c pt na
local/ui/state/filters.js:89 | 文本节点 | const wageChip = rw.wage ? '<span class="rw-c wg">工资<b>' + esc(rw.wage) + "</b></span>" : '<span class="rw-c w
local/ui/state/filters.js:90 | 双引号属性 | return '<span class="rw" title="' + esc(rw.title) + '">' + ptsChip + wageChip + "</span>";
local/ui/state/filters.js:98 | 双引号属性 | return '<span class="' + (rw.pend ? "rw-i p" : "rw-i") + '" title="' + esc(rw.title) + '">' + esc(text) + "</s
local/ui/state/filters.js:98 | 文本节点 | return '<span class="' + (rw.pend ? "rw-i p" : "rw-i") + '" title="' + esc(rw.title) + '">' + esc(text) + "</s
local/ui/views/clock-pop.js:103 | 文本节点 | '<div class="pop-time" id="clock-pop-time">' + esc(parts.time) + '</div>' +
local/ui/views/clock-pop.js:104 | 文本节点 | '<div class="pop-date">' + esc(parts.date) + '</div>' +
local/ui/views/clock-pop.js:106 | 文本节点 | (CLOCK_ICONS[ui] || CLOCK_ICONS.unavailable) + '</span><span>' + esc(copy.label) + '</span></div>' +
local/ui/views/clock-pop.js:107 | 文本节点 | '<p class="pop-explain">' + esc(copy.explain) + '</p>' +
local/ui/views/clock-pop.js:109 | 文本节点 | '<div><dt>最近校准</dt><dd>' + esc(ui === "demo" ? "离线示例" : clockLastSyncText()) + '</dd></div>' +
local/ui/views/clock-pop.js:110 | 文本节点 | '<div><dt>估计误差</dt><dd>' + esc(ui === "demo" ? "不适用" : clockUncertaintyText(uncNow)) + '</dd></div>' +
local/ui/views/clock-pop.js:111 | 文本节点 | '<div><dt>下一次重试</dt><dd>' + esc(ui === "demo" ? "不适用"
local/ui/views/clock-pop.js:113 | 文本节点 | '<div><dt>最近失败来源</dt><dd>' + esc(ui === "demo" ? "不适用"
local/ui/views/clock-pop.js:115 | 文本节点 | '<div><dt>最近失败原因</dt><dd>' + esc(ui === "demo" ? "不适用"
local/ui/views/clock-pop.js:117 | 文本节点 | '<div><dt>上次退出</dt><dd>' + esc(lifeText) + '</dd></div>' +
local/ui/views/clock-pop.js:120 | 文本节点 | '<div><dt>校准来源</dt><dd>' + esc(ui === "demo" ? "演示模式"
local/ui/views/clock-pop.js:122 | 文本节点 | '<div><dt>学校 HTTP 时间</dt><dd>' + esc(httpText) + '</dd></div>' +
local/ui/views/conflict-tip.js:6 | 文本节点 | const rows = model.rows.map((r) => "<dt>" + esc(r.label) + "</dt><dd><b>" + esc(r.name) + "</b>　" + esc(r.span
local/ui/views/conflict-tip.js:6 | 文本节点 | const rows = model.rows.map((r) => "<dt>" + esc(r.label) + "</dt><dd><b>" + esc(r.name) + "</b>　" + esc(r.span
local/ui/views/conflict-tip.js:6 | 文本节点 | const rows = model.rows.map((r) => "<dt>" + esc(r.label) + "</dt><dd><b>" + esc(r.name) + "</b>　" + esc(r.span
local/ui/views/conflict-tip.js:8 | 文本节点 | const days = model.days.map((d) => "<span>" + esc(d.text) + "</span>").join("");
local/ui/views/conflict-tip.js:10 | 双引号属性 | '<div class="tl" role="img" aria-label="' + esc(model.aria) + '"><div class="tl-track">' + cuts +
local/ui/views/conflict-tip.js:16 | 文本节点 | '<p class="tipb-s">' + esc(model.way) +
local/ui/views/help.js:6 | 文本节点 | $("#help-steps").innerHTML = (data.steps || []).map((step) => "<li><span class=\"no\">" + esc(step.no) + "</sp
local/ui/views/help.js:6 | 文本节点 | $("#help-steps").innerHTML = (data.steps || []).map((step) => "<li><span class=\"no\">" + esc(step.no) + "</sp
local/ui/views/help.js:6 | 文本节点 | $("#help-steps").innerHTML = (data.steps || []).map((step) => "<li><span class=\"no\">" + esc(step.no) + "</sp
local/ui/views/list.js:120 | 文本节点 | return '<section class="gsec" data-g="' + (kind || "") + '"><div class="grp"><b>' + esc(label) + "</b>" +
local/ui/views/list.js:121 | 文本节点 | (note ? "<span>" + esc(note) + "</span>" : "") + '<span class="count">' + items.length + " 场</span></div>" +
local/ui/views/list.js:163 | 文本节点 | timeHtml = '<span class="t">' + esc(mm[4] + ":" + mm[5]) + "</span>" + (mm[6] && mm[6] !== "00" ? '<span class
local/ui/views/list.js:163 | 文本节点 | timeHtml = '<span class="t">' + esc(mm[4] + ":" + mm[5]) + "</span>" + (mm[6] && mm[6] !== "00" ? '<span class
local/ui/views/list.js:166 | 文本节点 | if (state !== "waiting" && dayDiffMs !== null && Math.round(dayDiffMs / 86400000) !== 0) timeHtml += '<span cl
local/ui/views/list.js:170 | 文本节点 | if (state === "open" && toTs(item.sign_end) !== null) sub.push("<span>报名截止 " + esc(whenText(toTs(item.sign_end
local/ui/views/list.js:173 | 文本节点 | sub.push('<span class="activity-flags"><span class="activity-flag">' + esc(modeText(modeOf(item))) + "</span><
local/ui/views/list.js:175 | 文本节点 | sub.push("<span" + (invalid ? ' class="is-unknown"' : "") + ">" + esc(activityTimeText(item)) + "</span>");
local/ui/views/list.js:189 | 文本节点 | const flags = requirementFlags(item) + (warn ? '<span class="row-warn">' + esc(warn) + "</span>" : "");
local/ui/views/list.js:190 | 双引号属性 | return "<div class=\"" + classes.join(" ") + "\" data-id=\"" + esc(id) + "\" aria-label=\"" + esc(item.name) +
local/ui/views/list.js:190 | 双引号属性 | return "<div class=\"" + classes.join(" ") + "\" data-id=\"" + esc(id) + "\" aria-label=\"" + esc(item.name) +
local/ui/views/list.js:191 | 双引号属性 | "<div class=\"c-sel\"><input class=\"row-check\" type=\"checkbox\" data-id=\"" + esc(id) + "\"" + (selected ? 
local/ui/views/list.js:191 | 双引号属性 | "<div class=\"c-sel\"><input class=\"row-check\" type=\"checkbox\" data-id=\"" + esc(id) + "\"" + (selected ? 
local/ui/views/list.js:193 | 双引号属性 | "<div class=\"c-main\"><div class=\"nl\"><div class=\"name\" title=\"" + esc(item.name) + "\">" + esc(item.nam
local/ui/views/list.js:193 | 文本节点 | "<div class=\"c-main\"><div class=\"nl\"><div class=\"name\" title=\"" + esc(item.name) + "\">" + esc(item.nam
local/ui/views/list.js:194 | 双引号属性 | "<div class=\"c-place\" tabindex=\"0\" role=\"button\" aria-expanded=\"false\" aria-label=\"地点：" + esc(item.pl
local/ui/views/list.js:194 | 双引号属性 | "<div class=\"c-place\" tabindex=\"0\" role=\"button\" aria-expanded=\"false\" aria-label=\"地点：" + esc(item.pl
local/ui/views/list.js:194 | 文本节点 | "<div class=\"c-place\" tabindex=\"0\" role=\"button\" aria-expanded=\"false\" aria-label=\"地点：" + esc(item.pl
local/ui/views/list.js:214 | 双引号属性 | return '<div class="rx" data-rx="' + esc(id) + '">' +
local/ui/views/list.js:215 | 文本节点 | (ask ? '<div class="ph-confirm" role="alert">取消「' + esc(item.name) + '」的报名？取消后名额可能被别人报走，不能撤回。' +
local/ui/views/list.js:216 | 双引号属性 | '<div class="ph-acts"><button class="btn btn-line" type="button" data-cancel-no="' + esc(id) + '">不取消</button>
local/ui/views/list.js:217 | 双引号属性 | '<button class="btn btn-stop" type="button" data-cancel-yes="' + esc(id) + '">确认取消报名</button></div></div>' : "
local/ui/views/list.js:218 | 文本节点 | (result ? '<p class="cx-res ' + result.cls + '" role="status">' + esc(result.text) + "</p>" : "") + "</div>";
local/ui/views/list.js:226 | 双引号属性 | return '<button class="btn btn-line cx-btn" type="button" data-cancel="' + esc(id) + '"' + (block.off ? " disa
local/ui/views/list.js:227 | 双引号属性 | (block.why ? ' title="' + esc(block.why) + '"' : "") + ">" + (here ? "正在取消…" : "取消报名") + "</button>";
local/ui/views/list.js:232 | 文本节点 | if (armed) return '<span class="state-tag state-armed">' + esc(taskDisplayLabel(armed)) + "</span>";
local/ui/views/list.js:244 | 文本节点 | return "<span class=\"left" + (leftText !== "待公布" && parseLeft(item) <= 600 ? " is-soon" : "") + "\">" + esc(l
local/ui/views/list.js:251 | 文本节点 | (canCancelNow(item) ? '<span class="cx-until">' + esc(cancelUntilText(item)) + "</span>" + cancelButtonHtml(it
local/ui/views/login.js:131 | 文本节点 | el.innerHTML = "<strong>" + esc(result.title || "") + "</strong><span>" + esc(result.text || "") + "</span>" +
local/ui/views/login.js:131 | 文本节点 | el.innerHTML = "<strong>" + esc(result.title || "") + "</strong><span>" + esc(result.text || "") + "</span>" +
local/ui/views/login.js:132 | 文本节点 | (result.action ? "<button class=\"result-action\" type=\"button\" id=\"result-action\">" + esc(result.action.l
local/ui/views/plan-panel.js:210 | 其他（需人工） | const place = esc(placeText);
local/ui/views/plan-panel.js:211 | 其他（需人工） | const act = esc(activityTimeText(item));
local/ui/views/plan-panel.js:215 | 双引号属性 | + ' title="' + esc("完整地点：" + placeText + "（Enter 展开/收起）") + '">'
local/ui/views/plan-panel.js:346 | 文本节点 | + '"><i aria-hidden="true">' + (c.ok ? "✓" : "!") + "</i>" + esc(c.text) + "</span>").join("");
local/ui/views/plan-panel.js:418 | 事件处理器字符串 | box.innerHTML = warns.map((w) => '<li data-tone="' + w.tone + '"><span>' + esc(w.text) + "</span>"
local/ui/views/plan-panel.js:419 | 文本节点 | + (w.act ? '<button type="button" data-act="' + w.act + '">' + esc(w.label) + "</button>" : "") + "</li>").joi
local/ui/views/plan-panel.js:458 | 文本节点 | box.innerHTML = blocker ? "<span>还差一步：" + esc(blocker.text) + "</span>"
local/ui/views/plan-panel.js:459 | 文本节点 | + (blocker.act ? '<button type="button" data-act="' + blocker.act + '">' + esc(blocker.label) + "</button>" : 
local/ui/views/plan-panel.js:478 | 文本节点 | return '<div class="bh"><b>' + esc(instant ? "现在" : (at === null ? "待公布" : hmsDay(at))) + "</b><span>" + esc(n
local/ui/views/plan-panel.js:478 | 文本节点 | return '<div class="bh"><b>' + esc(instant ? "现在" : (at === null ? "待公布" : hmsDay(at))) + "</b><span>" + esc(n
local/ui/views/plan-panel.js:479 | 双引号属性 | + group.items.map((item) => '<div class="tk"><div><b title="' + esc(item.name) + '">' + esc(item.name)
local/ui/views/plan-panel.js:479 | 文本节点 | + group.items.map((item) => '<div class="tk"><div><b title="' + esc(item.name) + '">' + esc(item.name)
local/ui/views/plan-panel.js:480 | 文本节点 | + "</b><small>" + esc(activityTimeText(item)) + "</small>"
local/ui/views/plan-panel.js:483 | 其他（需人工） | + esc(String(item.id)) + '" aria-label="' + esc("从计划移除「" + item.name + "」") + '">'
local/ui/views/plan-panel.js:483 | 双引号属性 | + esc(String(item.id)) + '" aria-label="' + esc("从计划移除「" + item.name + "」") + '">'
local/ui/views/plan-panel.js:508 | 文本节点 | $("#policy-text").innerHTML = "尝试 <b>" + esc(retryText) + "</b>，<b>"
local/ui/views/plan-panel.js:592 | 文本节点 | const html = text ? "<span>" + esc(text) + "</span>"
local/ui/views/plan-panel.js:593 | 文本节点 | + (act ? '<button type="button" data-act="' + act.act + '">' + esc(act.label) + "</button>" : "") : "";
local/ui/views/plan-panel.js:733 | 文本节点 | if (S.selectionNotice) messages.push("<div class=\"conflict-item\"><strong>选择提醒</strong><br>" + esc(S.selectio
local/ui/views/plan-panel.js:734 | 文本节点 | validation.errors.forEach((error) => messages.push("<div class=\"conflict-item\"><strong>" + esc(error.title) 
local/ui/views/plan-panel.js:734 | 文本节点 | validation.errors.forEach((error) => messages.push("<div class=\"conflict-item\"><strong>" + esc(error.title) 
local/ui/views/plan-panel.js:735 | 文本节点 | validation.conflicts.forEach((conflict) => messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong>
local/ui/views/plan-panel.js:735 | 文本节点 | validation.conflicts.forEach((conflict) => messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong>
local/ui/views/plan-panel.js:735 | 文本节点 | validation.conflicts.forEach((conflict) => messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong>
local/ui/views/plan-panel.js:735 | 文本节点 | validation.conflicts.forEach((conflict) => messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong>
local/ui/views/plan-panel.js:799 | 文本节点 | return '<div class="stn" data-s="' + state + '"><i class="stn-dot"></i><span class="stn-name">' + esc(station.
local/ui/views/plan-panel.js:800 | 文本节点 | '</span><span class="stn-time">' + esc(station.time) + "</span></div>";
local/ui/views/plan-panel.js:1087 | 事件处理器字符串 | return '<small class="t-via" data-tone="warn">改用页面点击' + (why ? "：" + esc(why) : "")
local/ui/views/plan-panel.js:1167 | 双引号属性 | const actionsHtml = (canCancel ? "<button class=\"task-cancel\" type=\"button\" data-task-id=\"" + esc(task.ta
local/ui/views/plan-panel.js:1168 | 双引号属性 | + (canVerify ? "<button class=\"task-cancel task-verify\" type=\"button\" data-task-id=\"" + esc(task.task_id)
local/ui/views/plan-panel.js:1169 | 双引号属性 | return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) + "\"><strong class=\"task-name\" title=\
local/ui/views/plan-panel.js:1169 | 双引号属性 | return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) + "\"><strong class=\"task-name\" title=\
local/ui/views/plan-panel.js:1169 | 文本节点 | return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) + "\"><strong class=\"task-name\" title=\
local/ui/views/plan-panel.js:1169 | 文本节点 | return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) + "\"><strong class=\"task-name\" title=\
local/ui/views/plan-panel.js:1169 | 文本节点 | return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) + "\"><strong class=\"task-name\" title=\
local/ui/views/plan-panel.js:1376 | 事件处理器字符串 | parts.push('<div class="banner" data-tone="bad" role="alert"><span class="grow"><b>' + esc(copy.title) + "。</b
local/ui/views/plan-panel.js:1377 | 其他（需人工） | esc(copy.hint) + "</span>" +
local/ui/views/plan-panel.js:1413 | 文本节点 | : missed.length ? "期间" + missed.map((name) => "「" + esc(name) + "」").join("") + "到了开放时间，没有提交。"
local/ui/views/selection.js:74 | 文本节点 | messages.push("<div class=\"conflict-item\"><strong>" + esc(label) + "</strong><br>" + (name ? "「" + esc(name)
local/ui/views/selection.js:74 | 文本节点 | messages.push("<div class=\"conflict-item\"><strong>" + esc(label) + "</strong><br>" + (name ? "「" + esc(name)
local/ui/views/selection.js:79 | 文本节点 | messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong><br>「" + esc(left.name) + "」与「" + esc(right
local/ui/views/selection.js:79 | 文本节点 | messages.push("<div class=\"conflict-item\"><strong>活动时间重叠</strong><br>「" + esc(left.name) + "」与「" + esc(right
local/ui/views/selection.js:80 | 其他（需人工） | "」举办时段重叠（" + esc(shortTime(left.act_start)) + " – " + esc(shortTime(left.act_end)) + "），只能选其中一场。</div>");
local/ui/views/selection.js:80 | 其他（需人工） | "」举办时段重叠（" + esc(shortTime(left.act_start)) + " – " + esc(shortTime(left.act_end)) + "），只能选其中一场。</div>");
local/ui/views/status-cards.js:77 | 文本节点 | return rows.map((row) => "<dt>" + esc(row[0]) + "</dt><dd>" + esc(row[1]) + "</dd>").join("");
local/ui/views/status-cards.js:77 | 文本节点 | return rows.map((row) => "<dt>" + esc(row[0]) + "</dt><dd>" + esc(row[1]) + "</dd>").join("");
local/ui/views/terms.js:26 | 文本节点 | return "你之前同意的是 <b>" + esc(prev) + "</b>，新版还没同意。";
local/ui/views/terms.js:185 | 其他（需人工） | + esc(String(head.textContent || "")) + "</button>").join("");
local/ui/views/terms.js:268 | 其他（需人工） | ? "（" + esc(consentTimeText(acceptedAt)) + " 同意）"
local/ui/views/terms.js:273 | 文本节点 | " <b>" + esc(version || "版本未知") + "</b>" + when +
local/ui/views/terms.js:347 | 其他（需人工） | ? esc(text).replace("现在就看",
local/ui/views/terms.js:349 | 其他（需人工） | : esc(text);
local/ui/views/terms.js:350 | 文本节点 | return "<li><b>" + esc(String(point.title || "")) + "</b><span>" + body + "</span></li>";
local/ui/views/terms.js:370 | 文本节点 | '<li><span class="tu-new">新增</span><span>' + esc(String(text)) + "</span></li>").join("");
TOTAL 115 {'文本节点': 79, '双引号属性': 23, '其他（需人工）': 10, '事件处理器字符串': 3}
```

注：脚本给出 115 个调用。加上 `local/ui/views/terms.js:46` 的局部变量 `const esc = dialog.querySelector(…)`（不是函数调用），与 `grep` 的 116 个出现次数吻合。脚本分类中的「事件处理器字符串」3 条是误判（`data-tone=` 中含 `on`），已人工改为双引号属性。

### 清单 6：`stop_reason` 取值（后端、桌面、手机）

生产者（写入 `stop_reason` 的位置）：
- `grab.py`：`terminal(…)` 的参数（分支在 L2565–2618；调用点在 L2654、L2660、L2725、L2770、L3507–3508、L3609、L3965）：`success`、`already_signed`、`login_invalid`、`auth_unavailable`、`max_attempts`、`unconfirmed`、`clock_unavailable`、`sign_end`、`retry_duration`、`process_error`，以及 `REPLY_STOP_HINTS` 的键。
- `grab.py` 的 `state["terminal_reason"]` 与局部 `stop_reason`：`login_invalid`（L3579、L3735、L3749、L3899）、`process_error`（L3767、L3815）、`max_attempts`（L3771、L3907）、`sign_end` / `retry_duration`（L3773–3775、L3909–3911、L3931–3932）、`unconfirmed`（L3779、L3789）、`clock_unavailable`（L3781）、`page_unavailable`（L3821）、`clock_skew`（L3097）、`unknown_reply`（L3110）。`TERMINAL_STOP_REASONS`（`domain/signup_reply.py:50–55`）映射出 `full`、`closed`、`conflict`、`no_activity`，于 `grab.py:3083–3086` 消费。
- `domain/plan_rules.py`：`already_signed`（L180）、`success`（L187）、`unconfirmed`（L196、L204、L216、L220）、`user_stopped`（L206）、`sign_end` / `retry_duration`（L164–165、L218）、`process_error` 或 `login_invalid`（L224–225）。
- `app.py:3180`：`spawn_failed`，启动失败时的合成终态。
- `application/plan_service.py:43`：`full` 只在 `plan_done_notice` 中被消费，不产生。

各端映射：
- 后端短结论标签：`domain/signup_reply.py:63–72` `STOP_REASON_LABELS`，键为 `full`、`closed`、`conflict`、`no_activity`、`clock_skew`、`unknown_reply`、`page_unavailable`。`domain/retry_rules.py:112–114` 只在这些键上写 `outcome_label`。
- 后端说明文案：`grab.py:2491–2499` `REPLY_STOP_HINTS`，键与上面七个相同。
- 桌面标签：`local/ui/views/plan-panel.js:1058–1080` `stopReasonText`，覆盖 `success`、`already_signed`、`login_invalid`、`auth_unavailable`、`max_attempts`、`retry_duration`、`sign_end`、`unconfirmed`、`user_stopped`、`process_error` 与七个回包键。`local/ui/state/task-display.js:62–65` 另对 `unconfirmed`（待核对）、`auth_unavailable`（未提交）、`full`（名额已满）给状态标签。`local/ui/state/labels.js:60–66` 决定颜色。`local/ui/controllers/plan-events.js:94–118` 分别处理 `unconfirmed`、`auth_unavailable`，其余经 `stopReasonText`，且 `process_error` 不显示。
- 手机标签：`local/ui/m/app.js:412–432` `taskText`，只分支处理 `full`（「名额已满（学校说满了，不再提交，不是工具出错）」）与 `unconfirmed`（「待核对（…）」）。其余 `failed` / `canceled` 统一为「报名未成功」加 `outcome_label`（若有）。`auth_unavailable`、`login_invalid`、`max_attempts`、`retry_duration`、`sign_end`、`process_error` 在手机上没有专门文案，且不在 `STOP_REASON_LABELS` 中，因此没有 `outcome_label`，只显示无原因的「报名未成功」。
- 手机统计：`local/ui/m/app.js:981–990`。`full` 计为名额已满，`unconfirmed` 计为待核对，其余失败（含 `auth_unavailable`）计为「报名未成功」。`local/ui/m/app.js:886–887` 的 `failedFull` / `failedAsk` 决定卡片样式。
- 计划完成通知（后端）：`application/plan_service.py:28–50` `plan_done_notice`，只区分 `unconfirmed` 与 `full`，其余归入「没成功」。

### 清单 7：`ACTION_PARAMS`、手机派发、前端方法名与 `onBackend` 事件

- `local/domain/phone_rules.py:155–171` `ACTION_PARAMS` 共 12 个键：`list_activities`、`check`、`start_plan`、`start_request_state`、`cancel_start_request`、`stop_plan`、`cancel_task`、`save_retry_policy`、`show_window`、`phone_relogin_begin`、`phone_relogin_submit`、`phone_relogin_cancel`。L166 的注释仍写「未实现时明确报错」，但三个 `phone_relogin_*` 在 `Api` 上已有实现（L4211、L4244、L4248）。
- `local/application/phone_service.py:422–435` `dispatch` 的特判：`save_retry_policy` 改调 `save_prefs`（L430，`Api` 上存在于 L4376），只保留 `retry_policy`；`start_plan` 强制 `source="phone"`（L432–434）。其余直接 `self._call(name, clean)`（L435）。`save_retry_policy` 不是 `Api` 方法名，只能靠这条特判进入。
- `ACTION_PARAMS` 与 `Api` 公开方法比对：12 个键中，只有 `save_retry_policy` 不在 `Api` 上，由上条特判覆盖。
- 手机前端 `local/ui/m/app.js` 经 `postAction({action: …})`（落到 `/api/action`）发送的动作名共 10 个：`start_plan`（L2734）、`start_request_state`（L2756）、`cancel_start_request`（L2785）、`stop_plan`（L2809）、`show_window`（L2819）、`cancel_task`（L2837）、`save_retry_policy`（L2880）、`phone_relogin_begin`（L3091）、`phone_relogin_submit`（L3128）、`phone_relogin_cancel`（L3165）。`ACTION_PARAMS` 里的 `list_activities` 与 `check` 手机前端不发送。
- 桌面前端 `api("…")` 调用的方法名共 44 个，全部在 `Api` 上存在（脚本核对）。
- 桌面 `window.onBackend` 对象（`local/ui/app.js:90–165`）的 12 个键：`log`、`window_close_ask`、`check`、`activities`、`done`、`business_clock`、`plan`、`task`、`plan_done`、`second_open`、`update`、`phone_relogin`。后端发出的 kind 也是这 12 个（`local/app.py` 的 `_emit`，以及 `signup_plan.py:355–532` 经 `_publish` 发出的 `plan`、`task`）。两侧一一对应，没有孤立键。
- `local/app.py:1120–1123` 拼接 `window.onBackend && window.onBackend.%s(%s)`，kind 即 `_emit` 的第一个参数。
- 前端对 `window.onBackend.check(…)` 的直接调用：`local/ui/controllers/refresh.js:267`、`:275`。

## 第二步：比对与意见

### 概览

- 对比对象：`grab.md`（T4）、`rules.md`（T3）、`phone.md`（T2）、`prereq.md`（T5）、`reconcile.md`（T6），以及 `desktop.md`（T1，只抽核与本计划清单相关的条目）。`redo/zcode/` 未读、未引用。
- 共 15 条意见：漏项 8、事实错 3、计数不符 3、判断站不住 1；严重度为阻断 1、重要 4、次要 10。
- 逐项核过且一致的部分（不计入意见）见第四节。

### 一、意见

**AA2-01（事实错，重要）** 被审：`grab.md` §二 login 行。
- 原文说什么：「1 两处（保存登录态没写成一类）；2 其余失败（打不开登录页、窗口被关、等超时、接口校验失败等）」。
- 代码实际是什么：`cmd_login` 的返回值为：打不开登录页返回 2（`local/grab.py:1261`，`reason=login_page_unreachable`）；窗口被关返回 1（`:1272`，`reason=window_closed`）；等超时返回 1（`:1286`，`reason=timeout`）；登录态没能写入返回 2（`:1303`，`reason=session_not_saved`）；接口校验失败返回 2（`:1310`，`reason=verify_failed`）。
- 被审条目：该表没有引用条目 id；基线 `local/grab.py:1261–1313`。
- 类别：事实错。严重度：重要（退出码表是协议说明，重构时会照抄）。

**AA2-02（事实错，重要）** 被审：`grab.md` 「脚本数字」段，「`log_event` 6 处（只写事件日志，不上标准流）」。
- 代码实际是什么：`log_event`（`local/grab.py:314–320`）调用 `log(...)`，而 `log()` 在 `:299` 执行 `print(line, flush=True)`，即写到 stdout。`log_event` 的每一行都带北京时间戳出现在 stdout 上。
- 类别：事实错。严重度：重要（直接影响「哪些行会出现在 stdout 上、解析方能看到什么」的判断）。

**AA2-03（计数不符，次要）** 被审：`grab.md` 「脚本数字」段，「输出调用共 187 处」，以及「归属：grab 130、login 30、list 23、cancel 16、check 14、selftest 6、main 2、无静态可达 2」。
- 代码实际是什么：归属各项相加为 223，与 187 对不上。187 的口径也没有写明：它包括 `terminal(...)`（22 处）这类只是调用、本身不输出的封装，以及 `log_event(...)` 与 `_stderr_note(...)` 的封装调用。用 `ast` 直接数输出函数本身（`print`、`log`、`sys.stdout.write`、`sys.stderr.write`，含 `_stderr_note` 函数体里的 `print`）得 148 处，另有 `sys.exit` 1 处（`local/grab.py:4076`）。
- 类别：计数不符（同时口径不明）。严重度：次要。

**AA2-04（计数不符，次要）** 被审：`grab.md` §二 grab 子命令末段「合计 14 个有专门分支的终态（2 个返回 0，3 个返回 3，其余 9 类返回 2，其中回包类占 7 个）」；`reconcile.md` RC-58 沿用「14 个（0 两个、3 三个、2 九类）」。
- 代码实际是什么：`terminal()` 对 `stop_reason` 有 15 个显式取值。返回 0 的 2 个：`success`（`local/grab.py:2565–2572`）、`already_signed`（`:2573–2575`）。返回 3 的 3 个：`login_invalid`（`:2576–2580`）、`auth_unavailable`（`:2581–2586`）、`clock_unavailable`（`:2601–2605`）。返回 2 的 10 个：`max_attempts`（`:2587–2591`）、`unconfirmed`（`:2592–2600`）、回包类七键（`:2606–2613`）、`process_error`（`:2614–2618`）。另有兜底 `:2621–2627` 返回 2。
- 类别：计数不符。严重度：次要。

**AA2-05（事实错，次要）** 被审：`grab.md` §二 list 行，「2 三处失败（站点/登录态/拉取失败）」。
- 代码实际是什么：三处返回 2 是 `local/grab.py:1361`（检查登录态失败）、`:1373`（`PermissionError`，登录态失效）、`:1376`（拉取活动异常）。站点未配置由 `main` 返回 2（`:4063`），不属于 list。
- 类别：事实错。严重度：次要。

**AA2-06（漏项，重要）** 被审：`grab.md` §一 第 1 行「`[retry] kind=… attempts=… …`（进度型与终态型两种）」。
- 说明：这一行没有列出进度行的 kind 清单。`_retry_event` 的调用共 9 种 kind，另有终态 `kind=done`：`login_wait`（`local/grab.py:2682`）、`login_resumed`（`:2695`）、`window`（`:2790`）、`path`（`:2933`、`:2972`、`:2975`）、`window_extended`（`:3046`）、`submit`（`:3217`、`:3261`、`:3700`）、`not_ready`（`:3169`、`:3328`）、`throttled`（`:3175`、`:3334`）、`server_error`（`:3181`、`:3340`）；终态 `done`（`:2558`）。
- 解析方实况：`local/domain/retry_rules.py:57–77` `progress_event_status` 只认 `path`、`login_wait`、`login_resumed`；`local/application/plan_service.py:289` 认 `window_extended`，`:292` 认 `login_wait`；`window`、`submit`、`not_ready`、`throttled`、`server_error` 没有按 kind 的分支，只靠 `retry_deadline`、`attempts`、`phase` 字段被 `plan_service.py:302–312` 读取。
- 类别：漏项。严重度：重要（协议表与 W6 的影响范围都依赖这份 kind 清单）。

**AA2-07（漏项，重要）** 被审：`grab.md` §一 第 9 行，以及 W6 段。
- 说明：计划模式下，失败原因的解析方是 `local/domain/plan_rules.py:207–211`，它逆序取第一条 `line.startswith("[X] ")` 作为 `reason`，由 `local/application/plan_service.py:417` 的 `classify_task_stop` 使用。`grab.md` 只列了 `local/application/login_service.py:68`（旧的 `_spawn` 路径的 done 事件），计划模式的这条解析没有列。
- 影响（代码层）：对 `print()` 输出的 `[X]` 行（无时间戳，例如 `local/grab.py:2622`）成立；对 `log()` 输出的 `[X]` 行（带时间戳，例如 `:2577`）不成立。计划模式的失败原因因此取决于该行是哪种输出，这一点 W6 段没有写。
- 类别：漏项。严重度：重要。

**AA2-08（判断站不住，阻断）** 被审：`grab.md` §一 W6（「需测试定，优先级高」）；`reconcile.md` RC-55。
- 原文说什么：W6 的结论是「读代码的结论是：计划模式下 `[retry]` 终态行和『第 N 次提交』行应该都认不出来」，但「只记『需测试定』」，理由是没有运行真实 worker，也没有核对中间环节是否去掉时间戳。
- 代码实际是什么：这条链的三段都是代码层事实，不需要运行即可判定。第一，`log()` 无条件拼接北京时间戳并 `print`（`local/grab.py:288–289`、`:299`），仓库里没有关闭它的环境开关（`grab.py` 中的环境变量读取只有 `CAMPUS_CLOCK_SNAPSHOT`，`:127`）。第二，`plan_service.py:178` 只做 `line.rstrip("\r\n")`，中间没有去戳。第三，`parse_retry_line` 用 `text.startswith("[retry] ")`（`local/domain/retry_rules.py:36`），`ATTEMPT_RE` 用 `^`（`:25`），两者都不容忍前缀。所以计划模式下这两类行不被解析，是代码层事实。运行期真正需要确认的只剩端到端表现（例如界面是否因此显示 `process_error`）。grab.md 把整条链都降级为需测试定，等于把可判定的部分也推迟了。
- 被审条目与基线：`grab.md` §一 W6；`reconcile.md` RC-55；基线 `local/grab.py:288–289、299`，`local/application/plan_service.py:178、269、276`，`local/domain/retry_rules.py:25、36`。
- 阻断理由：计划模式的终态（`stop_reason`）是界面状态机和计划结果的输入。redo 把它写成未定论，指挥会话可能据此推迟修复，或在重构前置里漏掉这一项。
- 类别：判断站不住。严重度：阻断。

**AA2-09（漏项，次要）** 被审：`grab.md` §一 W6 段，「现有测试给解析函数的输入全是不带时间戳的行（`test_retry_events` 的样例）」。
- 代码实际是什么：不只 `test_retry_events`。`local/tests/test_retry_policy.py:265–405` 的 fake worker 用 `print('[retry] …')`、`print('[i] 第 N 次提交：…')` 直接驱动真实的计划服务，同样没有时间戳。这才是测试没有红的主要原因：它走了完整路径，但输入形状与生产不同。grab.md 只提到了单元样例。
- 类别：漏项。严重度：次要。

**AA2-10（漏项，次要）** 被审：`grab.md` §一 与 §三。
- 代码实际是什么：`_stderr_note` 有 6 个调用点。其中 5 个是 `[log]` 诊断行（`local/grab.py:280`、`:293`、`:297`、`:298`、`:307`，用于数据目录不可用、日志轮转失败、拿不到日志锁、写日志失败），写的是 stderr。第 6 个是 `[timing]`（`:1344`）。前 5 个没有出现在 §一 的表里，§三 的「写文件」与「写 stderr」也没有提。读取方（如果有）未核。
- 类别：漏项。严重度：次要。

**AA2-11（漏项，次要）** 被审：`grab.md` §二 grab 行。
- 代码实际是什么：`cmd_grab` 有两处 `return 0` 没有列出：`local/grab.py:2752`（`if not target: return 0`，`resolve_target` 返回 None 时执行，包括 `:1749` 的「找不到报名开始时间」和 `:1783` 的「已取消」），以及 `:2842`（dry-run 完成）。其中「找不到报名开始时间」是一条 `[X]` 失败，却以 0 退出。
- 类别：漏项。严重度：次要。

**AA2-12（漏项，次要）** 被审：`rules.md` §4 后端「说明文案」列，原文「同一份短结论，经任务载荷下发」。
- 代码实际是什么：后端另有 `local/grab.py:2491–2499` 的 `REPLY_STOP_HINTS`，七条长句，终态时在 `:2611` `print` 出来；`sign_end` 与 `retry_duration` 的尾注「报名已截止」「重试时长到了」在 `:2621`。这些说明只出现在 worker 的控制台输出里，桌面与手机页都不读。跨端差异应写一行。
- 类别：漏项。严重度：次要。

**AA2-13（漏项，次要）** 被审：`prereq.md` §四.3（`ACTION_PARAMS` 的核对）。
- 代码实际是什么：`local/domain/phone_rules.py:166` 的注释仍写「白名单先占位，未实现时明确报错」，但 `Api` 上 `phone_relogin_begin`、`phone_relogin_submit`、`phone_relogin_cancel` 已有实现（`local/app.py:4211`、`:4244`、`:4248`）。prereq 没有提到这条过时注释。
- 类别：漏项。严重度：次要（只影响注释，但拆 `Api` 时容易被误读）。

**AA2-14（漏项，次要）** 被审：`grab.md` §一 第 9 行与其余 `[X]`、`登录失效` 类解析的列举。
- 代码实际是什么：有两处解析未列。`local/domain/plan_rules.py:224–225` 用 `"登录失效" in "".join(tail)` 判 `login_invalid`（子串，对带时间戳行成立）。`local/gui.py:895` 用 `json.loads(out.splitlines()[-1])` 读 `list --json` 的 stdout，但全仓没有 `import gui` 或 `from gui`，是否仍被使用需确认。
- 类别：漏项。严重度：次要。

**AA2-15（计数不符，次要）** 被审：`phone.md` §二 表后「`ingest` 一个函数里直接写到的不同字段数 16」，以及 §一 对照的口径。
- 代码实际是什么：`local/ui/m/app.js:2617–2705`（`ingest`）直接赋值的字段为 15 个：`busy`、`clockState`、`items`、`lastOkText`、`login`、`notice`、`pcListError`、`plan`、`reloginSetup`、`retry`、`retryHydrated`、`retryOptions`、`selected`、`seq`、`termsOk`。只有把 `seenEventSeq` 的容器改（`clear`、`add`、`delete`，`:2624`、`:2683`、`:2685`）也计入，才得到 16。口径需要写明。
- 类别：计数不符。严重度：次要。

### 二、W6 完整数据流（替代 grab.md W6 段中的链路描述，供指挥会话使用）

1. 产生：`log()` 为每行加前缀 `"%s %s" % (stamp, msg)`（`local/grab.py:288–289`），然后 `print(line, flush=True)`（`:299`）。经过 `log()` 的行包括：`terminal()` 的 `[retry] kind=done`（`:2558`）、`_retry_event` 的 `[retry] kind=…`（`:2389`）、「第 N 次提交」（`:3186`、`:3216`、`:3260`、`:3346`）、`log_event` 的行（`:320`）。这些行在 stdout 上形如 `2026-11-13 10:00:00 [retry] kind=done …`。
2. 子进程 stdout 进入读线程：`local/application/plan_service.py:178` `lines.put(line.rstrip("\r\n"))`，只去换行，不去时间戳。
3. 主循环取出后调用 `feed(line)`（`:252`，调用点 `:355`、`:367`）。
4. `feed()` 内：`tail.append(line)`（`:259`）；`parse_checkpoint_line`（`:262`，用 `str.find`，**成立**）；`ATTEMPT_RE.match`（`:269`，**不成立**）；`parse_retry_line`（`:276`，**不成立**）。进度行与「第 N 次提交」的次数更新因此都不发生。
5. 收尾：`reversed(tail)` 上调用 `parse_retry_line`（`:410`，**不成立**），`stop` 为空。`classify_task_stop`（`local/domain/plan_rules.py:168` 起）中：成功判断用子串 `[OK] 报名成功`（`:184`，**成立**）；`already_signed` 用子串（`:177`，**成立**）；失败原因用 `startswith("[X] ")`（`:209`，print 版本**成立**，log 版本**不成立**）；`stop_reason` 落到 `login_invalid`（需退出码 3 且尾部含「登录失效」子串，`:225`）或默认的 `process_error`（`:225`）。
6. 结论（代码层推断）：计划模式下，`unconfirmed`、`full`、`max_attempts`、`sign_end`、`retry_duration` 等细分原因在收尾时拿不到，只能落到 `process_error`；`supervised` 路径的 `unconfirmed` 依赖 `attempts_seen`，而次数也不再被观察到。端到端表现需要用带时间戳的 stdout 替身驱动计划服务来确认。测试草案：把 `test_retry_policy.py` 的 fake worker 输出改成与 `log()` 同形（前缀时间戳），断言 `stop_reason` 为 `full` 或 `unconfirmed`。

### 三、对附录 A 的补正

第一遍清点（清单 2）的 `item2.py` 只识别 `print`、`log`、`sys.stdout.write`、`sys.stderr.write` 的直接调用，没有把 `_stderr_note(...)`、`log_event(...)`、`terminal(...)` 的调用点列入。第二步核对后补正：`_stderr_note` 调用 6 处（`local/grab.py:280`、`:293`、`:297`、`:298`、`:307`、`:1344`）；`log_event` 调用 6 处（不含定义）；`terminal` 调用多处，它们只是封装，本身不输出。清单 2 的 148 处只统计输出函数本身，这一口径差异即 AA2-03。

### 四、逐项核过且一致（不计入意见）

- `phone.md`：55 个字段、47 个字面量声明、8 个未声明（与清单 1 一致）；直接赋值 136、容器改 3、嵌套写 9、别名内部写 6（别名写全部在 `pending` 上，`app.js:2760、2761、2782、2788、2789、2797`）；`reloginSubmitting` 为 1 处真、9 处假，与 `ingestRelogin` 8 处加 `submitRelogin` 1 处的描述一致。`api()` 的 8 秒超时（`REQUEST_TIMEOUT_MS = 8000`，`:1371`）、401 只对 `/api/action` 生效（`:2301–2302`）一致。`onConfirmYes` 的 `.then` 无 `.catch`（`:1699–1702`），W1 属实。`pairTickTimer` 未被 `visibilitychange` 清理，W2 属实。
- `prereq.md`：`Api` 共 153 个方法，其中公开 60 个（与清单 4 一致）；五块与跨块的计数 5、11、6、11、7、20 一致，无未归类项；`with self.<锁>` 的方法数 66、12、9 一致。`esc(` 115 处、11 个文件，无单引号属性、事件处理器、URL 落点（与清单 5 一致）；`innerHTML` 赋值 43 处一致。桌面 `api("…")` 名 44 个，`Api` 公开方法中有 16 个桌面不引用，逐个核对一致。`onBackend` 的 12 个键与后端 `_emit` 的 10 个字面量加 `plan`、`task`（经变量 kind 发出）一致；`ACTION_PARAMS` 12 键，其中 11 个与 `Api` 同名，`save_retry_policy` 经 `dispatch` 特判为 `save_prefs`，一致。
- `reconcile.md`：80 条 = 48 + 22 + 8 + 2，各来源小计一致；RC-27 属实（`local/app.py:799–804` 的 `_RelayTree.terminate` 转到进程树的终止，`process_tree` 的注释写明终止后最多等 1 秒，`:237`）。
- `rules.md`：汇总 13 / 7 / 7 一致；规则 2 的 `planSummary`（`local/ui/m/app.js:494–504`）开放时刻缺失按 0 处理、已截止的计入预报名，属实；规则 4 桌面 17 键中 7 个与后端逐字相同，属实；规则 5 手机 8 组（`app.js:747`）属实；规则 6 批次三句逐字相同（`local/ui/views/plan-panel.js:475–476`、`local/ui/m/app.js:1084–1085`），属实；规则 7 的倒计时示例（26 小时：桌面「1 天 2 时」、手机「26 小时后」）属实；桌面时区写死 `Asia/Shanghai`（`local/ui/state/time.js:2`）属实；规则 1 中 `session_expired` 恒为假，属实（`local/domain/login_rules.py:128`、`local/app.py:2411`，只读于 `login_service.py:37`）。
- `grab.md`：`[X]` 的 `startswith` 与 `[OK]` 子串的描述、`_stdout_to_stderr` 的范围、`list --json` 与 `cancel --json` 的改道、环境变量的读取与父进程传入（`local/app.py:400–411`），均属实。109 个嵌套函数内 `return`（`cmd_list` 4、`cmd_grab` 105）属实。

### 五、未核（诚实说明）

- `phone.md` 的读取点 296 与「整个 model 作为实参传出 45 次」只核了写入相关的计数，读取计数未核。
- `desktop.md` 的 U6、U11、U12 调用链、`prereq.md` §一 的测试名搜索、`rules.md` 各条的测试名比对，均未逐个读测试体核对。
- `[log]` 诊断行的读取方、`sign_end` 尾注在桌面的展示，未核。

### 六、阻断意见摘要

AA2-08：grab.md 的 W6 段把代码层可判定的解析失败降级为「需测试定」，并漏了计划模式的失败原因解析（AA2-07）。这会让计划模式的 `stop_reason` 问题在重构前置里被忽略。建议把「计划模式下 `[retry]` 与『第 N 次提交』行认不出」改为代码层事实，端到端影响单独写成需测试定，并在 W6 数据流里补上 `plan_rules.py:209`。


## 收工：git 状态与范围说明

收工时执行 `git log --oneline -3` 与 `git status --short`，结果如下：

```
7e2d31c fix(component): 导入装好后收掉旧的下载失败
e0054c4 docs(proposals): 前端采用 ES Modules 并留样机
5d95f34 docs(proposals): 工程化重构提案

 M CHANGELOG.md
 M design/proposals/engineering-refactor.md
 M local/application/login_service.py
 M local/application/plan_service.py
 M local/domain/plan_rules.py
 M local/domain/worker_lines.py
?? .workbuddy/
?? design/evidence/2026-11-12/esm-verify/
?? design/evidence/2026-11-12/refactor-audit/
?? local/tests/test_worker_line_stamp.py
```

范围说明：

- 本审计只写了 `redo/audit/aa2-omissions.md`，未改任何被审文件，未改任何产品代码，未提交、未推送。
- 收工时的 `CHANGELOG.md`、`local/application/login_service.py`、`local/application/plan_service.py`、`local/domain/plan_rules.py`、`local/domain/worker_lines.py` 与未跟踪的 `local/tests/test_worker_line_stamp.py` **不是本审计所为**。它们与 AA2-08 讨论的时间戳问题直接相关，疑似另一执行方正在修复 W6 的代码。本审计按基线 `7e2d31c` 读代码，因此上述意见仍针对基线；这些改动未经本审计核对，结论不涵盖它们。按计划规则，本审计不恢复、不清理这些文件，只在此记录并交指挥会话。
- `redo/zcode/` 未读、未引用。
- 中间文件只放在一个新建的临时空目录与脚本目录中，未写入仓库。
