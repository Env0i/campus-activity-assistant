# 补测试之前：表甲「认结论与认步骤」与表乙「读进行中标志」的变异结论

- **基线提交**：`896baf2`。执行日期：2026-11-15。
- **量的是什么**：登录胶囊（`views/login.js` 的 `paintLogin` 与它调用的 `state/login.js` 函数）、重新登录对话框（`views/relogin.js`）在搬成模块之前，哪些分支与读取已经有跑 node 的用例守着、哪些没有。
  - 表甲（74 行）：决定显示哪种结论、哪一步、哪一种情况、标题与按钮的每个分支。变异做法——带条件的行把条件换成 `false`，兜底返回的字面量换掉，让输入落到别的分支。
  - 表乙（44 行，其中 6 行与表甲同一处读取，直接复用表甲结论）：`S.login.checking` / `S.login.loginPending` / `S.autoLogin` / `S.relogin.*` / `reloginRelay.*` / `S.busy` 的每一处读取（赋值不算）。变异做法——把这一处读取换成它「空闲时的值」，让守卫失效。
- **怎么做**：`scripts/mutate_login.py` 按「文件、函数、那一行的文字」定位（不按行号），行清单在同一文件的 `ROWS`。只在临时目录下的仓库副本里做（副本按 `git ls-files` 复制，`local/data`、`server/data`、两个 `config.json` 不进副本），仓库本体不动。每条变异只改一处，`node --check` 通过后跑相关测试集合。
- **相关测试集合**：`test_ui_contract_login.py`、`test_ui_exit_paths_login.py`、`test_ui_reliability.py`、`test_ui_contract_feedback.py`、`test_ui_contract_plan.py`、`test_ui_contract_settings.py`、`test_ui_contract_shell.py`、`test_prerefactor_fixes.py`。本文件是「补测试之前」，所以只跑这 8 个既有文件（`--legacy-only`），两个新文件还没参与。
- **结论口径**：变红的用例里至少一条是跑 node 的行为用例即「行为测试已守」（指名）；全是字面断言即「只有字面断言守」；没有用例变红即「没人守」；换掉以后用户看到的和发出的请求都不变的记「等价」并写明理由（人工复判，见文末）。
- **分片**：112 条独立变异按（文件长度+行号）的 crc32 分 8 片并行，每片自建临时副本；逐条原始输出不入库，在结果目录。

| 编号 | 表 | 定位（函数 / 那一行的文字） | 改的是什么 | 结论 | 出处（变红的第一条） |
|---|---|---|---|---|---|
| J01 | 甲 | `paintLogin` `const busyExpired = S.login.result === "expired" && S.login.` | 计划运行中仍要报失效的那条前提 | 行为测试已守 | 旧用例：`test_busy_pill_shows_expired_but_keeps_unknown` — AssertionError: '已登录' != '登录已失效' |
| J02 | 甲 | `paintLogin` `if (S.busy && !S.login.loginPending && !busyExpired && !S.au` | 忙碌时胶囊要说「已登录」而不是正在处理 | 行为测试已守 | 旧用例：`test_busy_pill_shows_expired_but_keeps_unknown` — AssertionError: '登录待确认' != '已登录' |
| J03 | 甲 | `paintLogin` `} else if (S.demo) {` | 演示模式自己说出来 | 行为测试已守 | 旧用例：`test_demo_pill_is_explicit` — AssertionError: '未登录' != '演示模式' |
| J04 | 甲 | `paintLogin` `} else if (S.autoLogin) {` | 自动登录中… | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — AssertionError: '登录已失效' != '自动登录中…' |
| J05 | 甲 | `paintLogin` `} else if (S.login.loginPending) {` | 登录中…（登录窗口还在等） | 行为测试已守 | 旧用例：`test_L07_demo_login_releases_the_pending_pill` — AssertionError: '登录已失效' != '登录中…' |
| J06 | 甲 | `paintLogin` `} else if (S.login.checking \|\| (ok === null && S.login.prese` | 检查登录…，本机有会话也不提前宣布已登录 | 行为测试已守 | 旧用例：`test_L01_check_timeout_after_100s_leaves_checking` — AssertionError: '未登录' != '检查登录…' |
| J07 | 甲 | `paintLogin` `} else if (S.login.present === false) {` | 从没登录过：引导首次登录 | 没人守 | 没红 |
| J08 | 甲 | `paintLogin` `} else if (S.login.result === "unknown" && ok === false) {` | 登录待确认（网络原因） | 行为测试已守 | 旧用例：`test_no_anchor_shows_unknown_not_fabricated` — AssertionError: '登录已失效' != '登录待确认' |
| J09 | 甲 | `paintLogin` `} else if (ok === false && S.login.present !== false) {` | 登录已失效 | 行为测试已守 | 旧用例：`test_L08_failed_start_releases_the_pending_pill_and_rolls_back` — AssertionError: '未登录' != '登录已失效' |
| J10 | 甲 | `paintLogin` `} else if (ok === true) {` | 已登录 | 行为测试已守 | 旧用例：`test_pill_shows_last_check_not_remaining_time` — AssertionError: '' != '14:20 校验' |
| J11 | 甲 | `paintLogin` `let text = "未登录";` | 兜底的胶囊文字 | 行为测试已守 | 旧用例：`test_cancelled_relogin_without_any_session_stays_logged_out` — AssertionError: '已登录' != '未登录' |
| J12 | 甲 | `paintLogin` `if (termsLocked() && !S.demo && state !== "pending") {` | 等同意条款 | 行为测试已守 | 旧用例：`test_terms_unaccepted_disables_the_school_actions` — AssertionError: '已登录' != '等同意条款' |
| J13 | 甲 | `paintLogin` `state === "bad" \|\| state === "warn" \|\| state === "ok" ? "重新登` | 登录按钮叫「重新登录」还是「登录」 | 只有字面断言守 | `test_app_js_first_use_is_not_bad` |
| J14 | 甲 | `paintLogin` `const solid = state === "none" \|\| state === "bad";` | 登录按钮转实心还是描边 | 没人守 | 没红 |
| J15 | 甲 | `reconcileAutoLogin` `if (!S.autoLogin) return;` | 自动登录态收回的入口 | 没人守 | 没红 |
| J16 | 甲 | `reconcileAutoLogin` `if (S.login.handoff \|\| S.login.result === "valid") {` | 已转人工/学校确认有效时收回自动登录 | 没人守 | 没红 |
| J17 | 甲 | `reconcileAutoLogin` `if (S.login.result === "expired") return;` | 失效时留给 recovering 与中继事件 | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — AssertionError: False is not true : 新一轮失效且能恢复：自动登录该亮回来 |
| J18 | 甲 | `reconcileAutoLogin` `if (typeof reloginAutoLive !== "function" \|\| !reloginAutoLiv` | 中继里没有这一场时收回自动登录 | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_check_cannot_reach_the_school` — AssertionError: True is not false |
| J19 | 甲 | `setLogin` `if (S.login.result === "expired" && !S.login.handoff)` | check 回来说失效且没转人工，才点亮自动登录中 | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — KeyError: 'autoLogin' |
| J20 | 甲 | `setLogin` `if (S.login.result === "valid") S.login.handoff = false;` | 结论为有效时清掉已转人工 | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — AssertionError: True is not false : 学校确认有效就不再是等验证码 |
| J21 | 甲 | `expiryText` `return at ? "约到 " + whenText(at) : "未知（以学校校验为准）";` | 预计有效的长句 | 没人守 | 没红 |
| J22 | 甲 | `loginEstimateShort` `if (!at) return "";` | 没有锚点时不编预计时间 | 行为测试已守 | 旧用例：`test_logged_in_without_last_check_says_never_checked` — AssertionError: '学校确认登录有效；预计约到 1月1日 08:00，以学校为准' != '学校确认登录有效' |
| J23 | 甲 | `loginEstimateShort` `if (now === null) return "约到 "` | 未校准时写具体日期 | 没人守 | 没红 |
| J24 | 甲 | `loginEstimateShort` `if (diff === 0) return "约到 " + time;` | 当天写「约到 时刻」 | 行为测试已守 | 旧用例：`test_login_estimate_five_writings` — AssertionError: Regex didn't match: '约到 \\d{2}:\\d{2}（按登录后 10 小时估，以学校为准）' not found in '预计 |
| J25 | 甲 | `loginEstimateShort` `if (diff === 1) return "约到明天 " + time;` | 明天写「约到明天 时刻」 | 行为测试已守 | 旧用例：`test_login_estimate_five_writings` — AssertionError: '约到明天' not found in '预计有效约到 11月16日 02:13（按登录后 10 小时估，以学校为准）别处登录可能让这里失效，比如手 |
| J26 | 甲 | `reloginCase` `if (cred.saved && cred.paused) return "bad";` | 保存的密码不对这一步 | 没人守 | 没红 |
| J27 | 甲 | `reloginCase` `if (cred.saved) return "captcha";` | 有保存账号直接进验证码步 | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: 'login' != 'wait' |
| J28 | 甲 | `reloginCase` `return "login";` | 没账号时落登录表单 | 没人守 | 没红 |
| J29 | 甲 | `reloginCapSub` `return mask ? "账号 " + mask + " 和密码由电脑自动填写" : "账号和密码由电脑自动填写";` | 验证码步副句带不带打码账号 | 没人守 | 没红 |
| J30 | 甲 | `reloginFromLogin` `return !!(S.relogin && S.relogin.fromLogin);` | 这一场是不是从登录表单点进来的 | 没人守 | 没红 |
| J31 | 甲 | `reloginHead` `if (step === "confirm") {` | 确认步的标题与副句 | 没人守 | 没红 |
| J32 | 甲 | `reloginHead` `} else if (step === "login") {` | 登录表单步的标题与副句 | 没人守 | 没红 |
| J33 | 甲 | `reloginHead` `} else if (step === "bad") {` | 密码不对步的标题与正文 | 没人守 | 没红 |
| J34 | 甲 | `reloginHead` `} else if (step === "lgwait") {` | 在学校登录页等待的标题 | 没人守 | 没红 |
| J35 | 甲 | `reloginHead` `} else if (step === "cap") {` | 验证码步的标题与副句 | 没人守 | 没红 |
| J36 | 甲 | `reloginHead` `} else if (step === "wait") {` | 等待步的标题与副句 | 没人守 | 没红 |
| J37 | 甲 | `reloginHead` `if (/核对验证码/.test(busy)) {` | 核对验证码时标题仍是输入验证码 | 没人守 | 没红 |
| J38 | 甲 | `reloginHead` `} else if (/自动/.test(busy)) {` | 自动登录时标题是「正在自动登录」 | 没人守 | 没红 |
| J39 | 甲 | `reloginHead` `title = "输入验证码";
    sub = reloginFromLogin() && mask` | 从登录表单进来时副句说密码已填好 | 没人守 | 没红 |
| J40 | 甲 | `reloginActs` `if (step === "login") return RELOGIN_LOGIN_ACTS[reloginWay()` | 登录步底栏按钮跟登录方式走 | 没人守 | 没红 |
| J41 | 甲 | `reloginActs` `if (step === "cap" && reloginFromLogin()) return ["btn-lg-ba` | 从登录表单进来的验证码步第一个按钮是「上一步」 | 没人守 | 没红 |
| J42 | 甲 | `reloginActs` `return RELOGIN_ACTS[step] \|\| [];` | 其余步骤的按钮表 | 没人守 | 没红 |
| J43 | 甲 | `reloginWay` `return S.relogin && S.relogin.way === "browser" ? "browser" ` | 登录方式默认听 S.relogin.way | 没人守 | 没红 |
| J44 | 甲 | `reloginStep` `if (box) box.hidden = name !== step;` | 只显示当前步骤的块 | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: False is not true : 不回到账号密码表单 |
| J45 | 甲 | `reloginStep` `if (dlg) dlg.classList.toggle("wide", step === "login");` | 登录那一屏宽一档 | 没人守 | 没红 |
| J46 | 甲 | `reloginStep` `if (el) el.hidden = acts.indexOf(id) < 0;` | 底栏按钮按步骤显隐 | 没人守 | 没红 |
| J47 | 甲 | `reloginStep` `if (foot) foot.hidden = acts.length === 0;` | 忙碌时整条底栏收起 | 没人守 | 没红 |
| J48 | 甲 | `reloginNextReady` `if (btn) btn.disabled = !user \|\| !pass;` | 账号密码都填了才亮下一步 | 没人守 | 没红 |
| J49 | 甲 | `reloginCodeReady` `if (btn) btn.disabled = !/^[0-9A-Za-z]{4}$/.test(code);` | 验证码满 4 位才亮登录 | 没人守 | 没红 |
| J50 | 甲 | `reloginError` `err.hidden = !text;` | 红字有内容才出现 | 没人守 | 没红 |
| J51 | 甲 | `openRelogin` `if (reloginRelay && reloginRelay.live) {` | 中继里有一场在跑就接上 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: 'login' != 'cap' |
| J52 | 甲 | `openRelogin` `if (reloginRelay.state === "waiting_code" && reloginRelay.mo` | 接上时已经有验证码图就直接画验证码步 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: 'wait' != 'cap' |
| J53 | 甲 | `openRelogin` `reloginStep("wait", reloginRelay.mode === "auto" ? "电脑正在识别验证` | 接上时等待行的说法 | 没人守 | 没红 |
| J54 | 甲 | `openRelogin` `if (kind === "bad") reloginStep("bad");` | 保存的密码不对就落那一步 | 没人守 | 没红 |
| J55 | 甲 | `openRelogin` `else if (kind === "captcha") {` | 有保存账号直接开验证码步 | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: 'login' != 'wait' |
| J56 | 甲 | `openRelogin` `else reloginStep("login");` | 没账号落登录表单 | 没人守 | 没红 |
| J57 | 甲 | `loginEntry` `if (login.result === "expired" \|\| login.handoff) {` | 登录过又失效才走重新登录 | 行为测试已守 | 旧用例：`test_handoff_restores_the_reminder_and_asks_for_the_captcha` — AssertionError: 'login' != 'cap' |
| J58 | 甲 | `closeRelogin` `const live = S.relogin && S.relogin.step && ["wait", "cap"].` | 关掉时还活着的场次才要取消 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: Lists differ: [] != ['f2'] |
| J59 | 甲 | `closeRelogin` `if (live && flowId && !reloginAutoLive(flowId)) return api("` | 关掉时取消这一场 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: Lists differ: [] != ['f2'] |
| J60 | 甲 | `reloginRefusal` `if (data.error === "plan_late") {` | 计划来不及时单独一句 | 没人守 | 没红 |
| J61 | 甲 | `reloginRefusal` `return String(data.text \|\| "这次没能开始登录，稍后再试。");` | 后端拒绝的兜底说法 | 没人守 | 没红 |
| J62 | 甲 | `receiveReloginState` `if (handoff && !reloginHandoffSeen) {` | 转人工只提醒一次 | 行为测试已守 | 旧用例：`test_handoff_log_matches_the_attempt_count` — AssertionError: '电脑没认出验证码' not found in '' |
| J63 | 甲 | `receiveReloginState` `if (!handoff) reloginHandoffSeen = false;` | 没转人工时清掉提醒过的标记 | 没人守 | 没红 |
| J64 | 甲 | `receiveReloginState` `if (data.state === "success" \|\| data.live === false) S.login` | 一场走完就不再是等用户输码 | 行为测试已守 | 旧用例：`test_L12_finished_relay_clears_handoff_so_auto_login_can_return` — AssertionError: True is not false : 这一场走完就不再等验证码 |
| J65 | 甲 | `receiveReloginState` `else if (handoff) S.login.handoff = true;` | 转人工时记下已转人工 | 行为测试已守 | 旧用例：`test_handoff_restores_the_reminder_and_asks_for_the_captcha` — AssertionError: False is not true |
| J66 | 甲 | `receiveReloginState` `const auto = String(data.origin \|\| "") === "auto" && !!data.` | 顶栏「自动登录中…」的成立条件 | 行为测试已守 | 旧用例：`test_a_live_auto_flow_survives_an_unknown_check` — AssertionError: False is not true |
| J67 | 甲 | `receiveReloginState` `if (auto !== !!S.autoLogin) {` | 自动登录态变了才重画胶囊与横幅 | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_relay_finishes_or_hands_off` — AssertionError: True is not false |
| J68 | 甲 | `receiveReloginState` `if (!S.relogin \|\| !S.relogin.open) {` | 对话框没开时只记账不接管画面 | 行为测试已守 | 旧用例：`test_relogin_success_without_flow_id_refreshes_only_once` — AssertionError: JS 行为测试崩溃：TypeError: Cannot read properties of undefined (reading 'flowId' |
| J69 | 甲 | `receiveReloginState` `if (data.state === "success") {` | 对话框没开时成功就刷新列表 | 行为测试已守 | 旧用例：`test_relogin_success_without_flow_id_refreshes_only_once` — AssertionError: 0 != 1 : 无 flow_id 的成功快照同样要立刻拉一次活动列表 |
| J70 | 甲 | `receiveReloginState` `if (state === "waiting_code" && data.mode !== "auto" && data` | 等到用户输码时画验证码步 | 行为测试已守 | 旧用例：`test_saved_account_goes_straight_to_the_captcha_without_confirming` — AssertionError: 'wait' != 'cap' |
| J71 | 甲 | `receiveReloginState` `if (state === "verifying" \|\| state === "starting" \|\| (state ` | 进行中画等待行 | 没人守 | 没红 |
| J72 | 甲 | `receiveReloginState` `if (state === "success") {` | 对话框开着时成功画结果步 | 行为测试已守 | 旧用例：`test_open_dialog_success_also_loads_the_list` — AssertionError: 0 != 1 : 对话框确认成功后也要加载列表 |
| J73 | 甲 | `receiveReloginState` `if (state === "failed" \|\| state === "canceled") {` | 失败/取消画结果步 | 行为测试已守 | 旧用例：`test_bad_password_goes_to_the_bad_step_not_a_generic_message` — AssertionError: 'wait' != 'bad' |
| J74 | 甲 | `receiveReloginState` `if (code === "bad_password") reloginStep("bad");` | 密码不对落「保存的密码不对」 | 行为测试已守 | 旧用例：`test_bad_password_goes_to_the_bad_step_not_a_generic_message` — AssertionError: 'msg' != 'bad' |
| Y01 | 乙 | `paintLogin` `if (S.busy && !S.login.loginPending` | paintLogin 读 S.busy | 行为测试已守 | 旧用例：`test_busy_pill_shows_expired_but_keeps_unknown` — AssertionError: '登录待确认' != '已登录' |
| Y02 | 乙 | `paintLogin` `&& !S.login.loginPending && !busyExpired` | paintLogin 读 S.login.loginPending | 没人守 | 没红 |
| Y03 | 乙 | `paintLogin` `&& !busyExpired && !S.autoLogin) {` | paintLogin 读 S.autoLogin | 没人守 | 没红 |
| Y04 | 乙 | `paintLogin` `` | paintLogin 读 S.autoLogin（分支条件，与认结论同一处） | 复用 J04（行为测试已守） | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — AssertionError: '登录已失效' != '自动登录中…' |
| Y05 | 乙 | `paintLogin` `` | paintLogin 读 S.login.loginPending（分支条件，与认结论同一处） | 复用 J05（行为测试已守） | 旧用例：`test_L07_demo_login_releases_the_pending_pill` — AssertionError: '登录已失效' != '登录中…' |
| Y06 | 乙 | `paintLogin` `} else if (S.login.checking \|\| (ok === null` | paintLogin 读 S.login.checking | 没人守 | 没红 |
| Y07 | 乙 | `setBusy` `if (S.busy && S.tour.open` | setBusy 读 S.busy 暂停引导 | 行为测试已守 | 旧用例：`test_busy_pause_releases_constraints_and_resume` — AssertionError: True is not false : 暂停期间引导不可见（不挡运行界面） |
| Y08 | 乙 | `setBusy` `if (!S.busy && S.tour.paused) tourResumeNow();` | setBusy 读 S.busy 继续引导 | 行为测试已守 | 旧用例：`test_busy_pause_releases_constraints_and_resume` — AssertionError: True is not false : 暂停期间引导不可见（不挡运行界面） |
| Y09 | 乙 | `setResult` `if (!S.busy) setResult(null);` | 结果条自动收起前读 S.busy | 没人守 | 没红 |
| Y10 | 乙 | `reconcileAutoLogin` `` | reconcileAutoLogin 读 S.autoLogin（与认结论同一处） | 复用 J15（没人守） | 没红 |
| Y11 | 乙 | `reconcileAutoLogin` `!reloginAutoLive()) S.autoLogin = false;` | reconcileAutoLogin 经 reloginAutoLive 读中继 | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_check_cannot_reach_the_school` — AssertionError: True is not false |
| Y12 | 乙 | `setLogin` `if (S.login.result === "expired" && !S.login.handoff)` | setLogin 读 S.login.handoff | 没人守 | 没红 |
| Y13 | 乙 | `reloginAutoLive` `if (!relay \|\| !relay.live \|\|` | reloginAutoLive 读中继的 live | 没人守 | 没红 |
| Y14 | 乙 | `reloginAutoLive` `relay.handoff \|\| String(relay.origin` | reloginAutoLive 读中继的 handoff | 行为测试已守 | 旧用例：`test_closing_after_the_auto_flow_handed_off_still_cancels` — AssertionError: Lists differ: [] != ['f1'] |
| Y15 | 乙 | `reloginFromLogin` `` | reloginFromLogin 读 S.relogin.fromLogin（与认结论同一处） | 复用 J30（没人守） | 没红 |
| Y16 | 乙 | `reloginWay` `` | reloginWay 读 S.relogin.way（与认结论同一处） | 复用 J43（没人守） | 没红 |
| Y17 | 乙 | `watchBrowserLogin` `if (!S.relogin \|\| !S.relogin.open) {` | 轮询读 S.relogin.open | 没人守 | 没红 |
| Y18 | 乙 | `watchBrowserLogin` `if (login.result === "valid" \|\| login.ok === true) {` | 轮询读 S.login 的结论 | 没人守 | 没红 |
| Y19 | 乙 | `openRelogin` `&& reloginRelay.live) {` | openRelogin 读中继的 live | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: 1 != 2 : 再试一次要真开新的一场 |
| Y20 | 乙 | `openRelogin` `reloginRelay.state === "waiting_code" &&` | openRelogin 读中继的 state | 没人守 | 没红 |
| Y21 | 乙 | `openRelogin` `&& reloginRelay.mode !== "auto"` | openRelogin 读中继的 mode（是否自动） | 没人守 | 没红 |
| Y22 | 乙 | `openRelogin` `&& reloginRelay.image) {` | openRelogin 读中继的 image | 没人守 | 没红 |
| Y23 | 乙 | `openRelogin` `reloginStep("wait", reloginRelay.mode === "auto" ? "电脑正在识别验证` | openRelogin 等待行读中继的 mode | 没人守 | 没红 |
| Y24 | 乙 | `reloginPickWay` `if (!S.relogin \|\| !S.relogin.open) return;` | reloginPickWay 读 S.relogin.open | 没人守 | 没红 |
| Y25 | 乙 | `closeRelogin` `` | closeRelogin 读 S.relogin.step（与认结论同一处） | 复用 J58（行为测试已守） | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: Lists differ: [] != ['f2'] |
| Y26 | 乙 | `closeRelogin` `if (live && flowId && !reloginAutoLive(flowId))` | closeRelogin 经 reloginAutoLive 读中继 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: Lists differ: [] != ['f2'] |
| Y27 | 乙 | `beginRelogin` `if (!S.relogin.open) return;` | beginRelogin 读 S.relogin.open | 没人守 | 没红 |
| Y28 | 乙 | `autoReloginOnce` `if (!S.relogin.open) return;` | autoReloginOnce 读 S.relogin.open | 没人守 | 没红 |
| Y29 | 乙 | `submitReloginCode` `if (S.relogin.open && result` | 提交验证码回来读 S.relogin.open | 没人守 | 没红 |
| Y30 | 乙 | `reloginSucceeded` `if (S.busy) return;` | 登录成功后读 S.busy | 没人守 | 没红 |
| Y31 | 乙 | `receiveReloginState` `!(S.login && S.login.result === "valid")` | 收进度时读 S.login 的结论 | 行为测试已守 | 旧用例：`test_relay_replay_after_a_valid_check_does_not_bring_auto_login_back` — AssertionError: True is not false |
| Y32 | 乙 | `receiveReloginState` `if (auto !== !!S.autoLogin) {` | 收进度时读 S.autoLogin | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_relay_finishes_or_hands_off` — AssertionError: True is not false |
| Y33 | 乙 | `receiveReloginState` `if (!S.relogin \|\| !S.relogin.open) {` | 收进度时读 S.relogin.open | 没人守 | 没红 |
| Y34 | 乙 | `receiveReloginState` `if (S.busy) addLog("重新登录成功，报名计划照常继续");` | 对话框没开时读 S.busy 写运行记录 | 没人守 | 没红 |
| Y35 | 乙 | `receiveReloginState` `addLog(S.busy ? "重新登录成功，报名计划照常继续" : "重新登录成功");` | 成功那一条运行记录读 S.busy | 没人守 | 没红 |
| Y36 | 乙 | `receiveReloginState` `reloginStep("msg", S.busy ? "重新登录成功，报名计划照常继续。" : "重新登录成功。");` | 成功结果步读 S.busy | 没人守 | 没红 |
| Y37 | 乙 | `receiveReloginState` `if (S.relogin.flowId && data.flow_id && String(data.flow_id)` | 收进度时读 S.relogin.flowId | 没人守 | 没红 |
| Y38 | 乙 | `renderLoginCard` `S.busy \|\| !!S.login.checking` | 登录详情卡的检查按钮读 S.busy | 没人守 | 没红 |
| Y39 | 乙 | `renderLoginCard` `!!S.login.checking \|\| termsLocked()` | 登录详情卡的检查按钮读 S.login.checking | 没人守 | 没红 |
| Y40 | 乙 | `scheduleSignedRefresh` `if (S.busy \|\| S.starting \|\| S.demo) return;` | 计划运行时推迟刷新读 S.busy | 行为测试已守 | 旧用例：`test_success_event_schedules_one_bounded_refresh` — AssertionError: {'bus[20 chars]nt': 1}, 'starting': {'armed': 1, 'sent': 0}, [27 chars]: 0 |
| Y41 | 乙 | `checkRoundOpen` `return S.round.background ? !!S.runtime.checkPending : !!S.l` | 前台轮是否在跑读 S.login.checking | 行为测试已守 | 旧用例：`test_L01_check_timeout_after_100s_leaves_checking` — AssertionError: True is not false : 超时后不能停在检查中 |
| Y42 | 乙 | `autoRefreshDue` `if (S.login.result !== "valid") return false;` | 自动刷新读 S.login 的结论 | 行为测试已守 | 旧用例：`test_each_skip_condition_blocks_the_tick_on_its_own` — AssertionError: True is not false : 「登录结论不是 valid」成立时这一拍不能刷新 |
| Y43 | 乙 | `autoRefreshDue` `if (S.login.loginPending) return false;` | 自动刷新读 S.login.loginPending | 没人守 | 没红 |
| Y44 | 乙 | `autoRefreshDue` `if (S.login.checking) return false;` | 自动刷新读 S.login.checking | 行为测试已守 | 旧用例：`test_each_skip_condition_blocks_the_tick_on_its_own` — AssertionError: True is not false : 「正在检查登录」成立时这一拍不能刷新 |

## 结论数字

只有字面断言守 1；没人守 64；行为测试已守 53（共 118 行，其中实测 112 行，复用 6 行）
