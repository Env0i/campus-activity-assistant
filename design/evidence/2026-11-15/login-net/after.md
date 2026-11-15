# 补完测试之后：表甲「认结论与认步骤」与表乙「读进行中标志」的变异结论

- **基线提交**：`896baf2`。执行日期：2026-11-15。
- **和 before.md 的差别**：这一轮的测试集合多了本批新增的 `test_ui_login_capsule.py` 与 `test_ui_relogin_dialog.py`，其余口径、行清单、分片方式完全相同（同一个 `scripts/mutate_login.py`，同样按（文件长度+行号）分 8 片，同样在临时副本里改一处）。
- **结论口径**：变红的用例里至少一条是跑 node 的行为用例即「行为测试已守」；全是字面断言即「只有字面断言守」；没有用例变红即「没人守」；换掉以后用户看到的和发出的请求都不变的记「等价」，理由列在文末。
- **D6 五个必测场景各自由谁守着**：
  1. 启动第一次检查时胶囊不显示成已登录也不显示成失效 → `test_ui_login_capsule.py::test_checking_without_a_saved_session_says_checking`。
  2. 自动登录中胶囊不先闪红 → `test_ui_login_capsule.py::test_busy_plan_says_auto_login`。
  3. 条款没同意时胶囊写等同意条款、登录与检查按钮不可用 → `test_ui_login_capsule.py::test_waiting_terms_says_so`（文字）＋ `test_ui_contract_shell.py::test_terms_unaccepted_disables_the_school_actions`（按钮不可用，既有用例）。
  4. 重新登录对话框在自动登录进行中关掉时不取消这一场 → `test_ui_relogin_dialog.py::test_closing_keeps_the_computers_own_auto_login`。
  5. 验证码认错后对话框留在输验证码那一步：电脑认不出转人工的给出红字 → `test_ui_relogin_dialog.py::test_wrong_captcha_keeps_the_code_step_with_a_red_hint`；用户自己手输认错的只给灰字次数说明、不出红字（与 D6 原文「给出红字」不一致，留给状态机那一步）→ `test_ui_relogin_dialog.py::test_typed_wrong_code_stays_on_code_step_with_grey_tries_note`。

| 编号 | 表 | 定位（函数 / 那一行的文字） | 改的是什么 | 结论 | 出处（变红的第一条） |
|---|---|---|---|---|---|
| J01 | 甲 | `paintLogin` `const busyExpired = S.login.result === "expired" && S.login.present !== false;` | 计划运行中仍要报失效的那条前提 | 行为测试已守 | 旧用例：`test_busy_pill_shows_expired_but_keeps_unknown` — AssertionError: '已登录' != '登录已失效' |
| J02 | 甲 | `paintLogin` `if (S.busy && !S.login.loginPending && !busyExpired && !S.autoLogin) {` | 忙碌时胶囊要说「已登录」而不是正在处理 | 行为测试已守 | 旧用例：`test_busy_pill_shows_expired_but_keeps_unknown` — AssertionError: '登录待确认' != '已登录' |
| J03 | 甲 | `paintLogin` `} else if (S.demo) {` | 演示模式自己说出来 | 行为测试已守 | 旧用例：`test_demo_pill_is_explicit` — AssertionError: '未登录' != '演示模式' |
| J04 | 甲 | `paintLogin` `} else if (S.autoLogin) {` | 自动登录中… | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — AssertionError: '登录已失效' != '自动登录中…' |
| J05 | 甲 | `paintLogin` `} else if (S.login.loginPending) {` | 登录中…（登录窗口还在等） | 行为测试已守 | 旧用例：`test_L07_demo_login_releases_the_pending_pill` — AssertionError: '登录已失效' != '登录中…' |
| J06 | 甲 | `paintLogin` `} else if (S.login.checking \|\| (ok === null && S.login.present === true)) {` | 检查登录…，本机有会话也不提前宣布已登录 | 行为测试已守 | 旧用例：`test_L01_check_timeout_after_100s_leaves_checking` — AssertionError: '未登录' != '检查登录…' |
| J07 | 甲 | `paintLogin` `} else if (S.login.present === false) {` | 从没登录过：引导首次登录 | 行为测试已守 | 本批补：`test_first_use_asks_to_log_in` — AssertionError: '打开顶栏的登录状态，点「登录」开始使用' != '打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录' |
| J08 | 甲 | `paintLogin` `} else if (S.login.result === "unknown" && ok === false) {` | 登录待确认（网络原因） | 行为测试已守 | 旧用例：`test_no_anchor_shows_unknown_not_fabricated` — AssertionError: '登录已失效' != '登录待确认' |
| J09 | 甲 | `paintLogin` `} else if (ok === false && S.login.present !== false) {` | 登录已失效 | 行为测试已守 | 旧用例：`test_L08_failed_start_releases_the_pending_pill_and_rolls_back` — AssertionError: '未登录' != '登录已失效' |
| J10 | 甲 | `paintLogin` `} else if (ok === true) {` | 已登录 | 行为测试已守 | 旧用例：`test_pill_shows_last_check_not_remaining_time` — AssertionError: '' != '14:20 校验' |
| J11 | 甲 | `paintLogin` `let text = "未登录";` | 兜底的胶囊文字 | 行为测试已守 | 旧用例：`test_cancelled_relogin_without_any_session_stays_logged_out` — AssertionError: '已登录' != '未登录' |
| J12 | 甲 | `paintLogin` `if (termsLocked() && !S.demo && state !== "pending") {` | 等同意条款 | 行为测试已守 | 旧用例：`test_terms_unaccepted_disables_the_school_actions` — AssertionError: '已登录' != '等同意条款' |
| J13 | 甲 | `paintLogin` `state === "bad" \|\| state === "warn" \|\| state === "ok" ? "重新登录" : "登录"` | 登录按钮叫「重新登录」还是「登录」 | 行为测试已守 | 旧用例：`test_app_js_first_use_is_not_bad` — AssertionError: 'state === "bad" \|\| state === "warn" \|\| state === "ok" ? "重新登录" : "登录"' not found in '/* 状态仓库：常量、引导文案、全局状态 S（唯一状态持有者）。 */\nconst $ = (selector) => document.querySelector(selector);\n\nconst DEFAULT_HELP = {\n  title: "使用帮助",\n  subtitle: "三步完成一次报名",\n  /* 文案逐字照抄原型 Main.dc.html:745（1: |
| J14 | 甲 | `paintLogin` `const solid = state === "none" \|\| state === "bad";` | 登录按钮转实心还是描边 | 行为测试已守 | 本批补：`test_expired_says_relogin` — AssertionError: False is not true : 失效时按钮转实心 |
| J15 | 甲 | `reconcileAutoLogin` `if (!S.autoLogin) return;` | 自动登录态收回的入口 | 等价 | 进来时 S.autoLogin 本来就是 false；余下几条分支也只是把它置 false，用户看到的胶囊和发出的请求都不变。 |
| J16 | 甲 | `reconcileAutoLogin` `if (S.login.handoff \|\| S.login.result === "valid") {` | 已转人工/学校确认有效时收回自动登录 | 行为测试已守 | 本批补：`test_handoff_retracts_the_auto_login_state` — AssertionError: True is not false : 转人工以后自动登录态要收回 |
| J17 | 甲 | `reconcileAutoLogin` `if (S.login.result === "expired") return;` | 失效时留给 recovering 与中继事件 | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — AssertionError: False is not true : 新一轮失效且能恢复：自动登录该亮回来 |
| J18 | 甲 | `reconcileAutoLogin` `if (typeof reloginAutoLive !== "function" \|\| !reloginAutoLive())` | 中继里没有这一场时收回自动登录 | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_check_cannot_reach_the_school` — AssertionError: True is not false |
| J19 | 甲 | `setLogin` `if (S.login.result === "expired" && !S.login.handoff)` | check 回来说失效且没转人工，才点亮自动登录中 | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — KeyError: 'autoLogin' |
| J20 | 甲 | `setLogin` `if (S.login.result === "valid") S.login.handoff = false;` | 结论为有效时清掉已转人工 | 行为测试已守 | 旧用例：`test_L11_valid_check_clears_handoff_so_auto_login_can_return` — AssertionError: True is not false : 学校确认有效就不再是等验证码 |
| J21 | 甲 | `expiryText` `return at ? "约到 " + whenText(at) : "未知（以学校校验为准）";` | 预计有效的长句 | 行为测试已守 | 本批补：`test_anchor_with_a_future_time_says_roughly_when` — AssertionError: False is not true : 长句要带具体日期 |
| J22 | 甲 | `loginEstimateShort` `if (!at) return "";` | 没有锚点时不编预计时间 | 行为测试已守 | 旧用例：`test_logged_in_without_last_check_says_never_checked` — AssertionError: '学校确认登录有效；预计约到 1月1日 08:00，以学校为准' != '学校确认登录有效' |
| J23 | 甲 | `loginEstimateShort` `if (now === null) return "约到 "` | 未校准时写具体日期 | 等价 | now 为 null 时跳过这一行会落到最后的兜底：startOfDay(null) 得 NaN，diff 不等于 0 或 1，仍然拼出「约到 月日 时:分」，字面完全相同。 |
| J24 | 甲 | `loginEstimateShort` `if (diff === 0) return "约到 " + time;` | 当天写「约到 时刻」 | 行为测试已守 | 旧用例：`test_login_estimate_five_writings` — AssertionError: Regex didn't match: '约到 \\d{2}:\\d{2}（按登录后 10 小时估，以学校为准）' not found in '预计有效约到 11月15日 07:13（按登录后 10 小时估，以学校为准）别处登录可能让这里失效，比如手机上的学校页面；以实际登录状态为准' |
| J25 | 甲 | `loginEstimateShort` `if (diff === 1) return "约到明天 " + time;` | 明天写「约到明天 时刻」 | 行为测试已守 | 旧用例：`test_login_estimate_five_writings` — AssertionError: '约到明天' not found in '预计有效约到 11月16日 02:13（按登录后 10 小时估，以学校为准）别处登录可能让这里失效，比如手机上的学校页面；以实际登录状态为准' : 跨天的估算写「明天」 |
| J26 | 甲 | `reloginCase` `if (cred.saved && cred.paused) return "bad";` | 保存的密码不对这一步 | 行为测试已守 | 本批补：`test_rejected_saved_password_opens_the_update_step` — AssertionError: '重新登录' != '保存的密码不对' |
| J27 | 甲 | `reloginCase` `if (cred.saved) return "captcha";` | 有保存账号直接进验证码步 | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: 'login' != 'wait' |
| J28 | 甲 | `reloginCase` `return "login";` | 没账号时落登录表单 | 行为测试已守 | 本批补：`test_without_a_saved_account_starts_at_the_login_form` — AssertionError: '保存的密码不对' != '登录学校账号' |
| J29 | 甲 | `reloginCapSub` `return mask ? "账号 " + mask + " 和密码由电脑自动填写" : "账号和密码由电脑自动填写";` | 验证码步副句带不带打码账号 | 行为测试已守 | 本批补：`test_code_step_explains_the_computer_fills_the_password` — AssertionError: '账号和密码由电脑自动填写' != '账号 20****01 和密码由电脑自动填写' |
| J30 | 甲 | `reloginFromLogin` `return !!(S.relogin && S.relogin.fromLogin);` | 这一场是不是从登录表单点进来的 | 行为测试已守 | 本批补：`test_code_step_after_the_form_says_the_password_is_filled` — AssertionError: False is not true : 账号 20****01 和密码由电脑自动填写 |
| J31 | 甲 | `reloginHead` `if (step === "confirm") {` | 确认步的标题与副句 | 行为测试已守 | 本批补：`test_confirm_step_offers_the_automatic_login_once` — AssertionError: '重新登录' != '自动登录一次？' |
| J32 | 甲 | `reloginHead` `} else if (step === "login") {` | 登录表单步的标题与副句 | 行为测试已守 | 本批补：`test_without_a_saved_account_starts_at_the_login_form` — AssertionError: '重新登录' != '登录学校账号' |
| J33 | 甲 | `reloginHead` `} else if (step === "bad") {` | 密码不对步的标题与正文 | 行为测试已守 | 本批补：`test_rejected_saved_password_opens_the_update_step` — AssertionError: '重新登录' != '保存的密码不对' |
| J34 | 甲 | `reloginHead` `} else if (step === "lgwait") {` | 在学校登录页等待的标题 | 行为测试已守 | 本批补：`test_school_page_step_says_the_browser_is_open` — AssertionError: '重新登录' != '在学校登录页登录' |
| J35 | 甲 | `reloginHead` `} else if (step === "cap") {` | 验证码步的标题与副句 | 行为测试已守 | 本批补：`test_code_step_after_the_form_says_the_password_is_filled` — AssertionError: '重新登录' != '输入验证码' |
| J36 | 甲 | `reloginHead` `} else if (step === "wait") {` | 等待步的标题与副句 | 行为测试已守 | 本批补：`test_auto_login_wait_step_says_so` — AssertionError: '重新登录' != '正在自动登录' |
| J37 | 甲 | `reloginHead` `if (/核对验证码/.test(busy)) {` | 核对验证码时标题仍是输入验证码 | 行为测试已守 | 本批补：`test_checking_captcha_keeps_the_code_title` — AssertionError: '重新登录' != '输入验证码' |
| J38 | 甲 | `reloginHead` `} else if (/自动/.test(busy)) {` | 自动登录时标题是「正在自动登录」 | 行为测试已守 | 本批补：`test_auto_login_wait_step_says_so` — AssertionError: '重新登录' != '正在自动登录' |
| J39 | 甲 | `reloginHead` `title = "输入验证码";     sub = reloginFromLogin() && mask` | 从登录表单进来时副句说密码已填好 | 行为测试已守 | 本批补：`test_code_step_after_the_form_says_the_password_is_filled` — AssertionError: False is not true : 账号 20****01 和密码由电脑自动填写 |
| J40 | 甲 | `reloginActs` `if (step === "login") return RELOGIN_LOGIN_ACTS[reloginWay()] \|\| RELOGIN_LOGIN_ACTS.here;` | 登录步底栏按钮跟登录方式走 | 行为测试已守 | 本批补：`test_browser_way_offers_the_school_page_button` — AssertionError: False is not true : 浏览器方式要给「打开学校登录页」 |
| J41 | 甲 | `reloginActs` `if (step === "cap" && reloginFromLogin()) return ["btn-lg-back", "btn-rl-cancel", "btn-rl-code"];` | 从登录表单进来的验证码步第一个按钮是「上一步」 | 行为测试已守 | 本批补：`test_code_step_after_the_form_says_the_password_is_filled` — AssertionError: False is not true : 从表单进来要能退回上一步 |
| J42 | 甲 | `reloginActs` `return RELOGIN_ACTS[step] \|\| [];` | 其余步骤的按钮表 | 行为测试已守 | 本批补：`test_code_step_explains_the_computer_fills_the_password` — AssertionError: False is not true : 验证码步留「改用浏览器登录」 |
| J43 | 甲 | `reloginWay` `return S.relogin && S.relogin.way === "browser" ? "browser" : "here";` | 登录方式默认听 S.relogin.way | 行为测试已守 | 本批补：`test_browser_way_offers_the_school_page_button` — AssertionError: False is not true : 浏览器方式要给「打开学校登录页」 |
| J44 | 甲 | `reloginStep` `if (box) box.hidden = name !== step;` | 只显示当前步骤的块 | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: False is not true : 不回到账号密码表单 |
| J45 | 甲 | `reloginStep` `if (dlg) dlg.classList.toggle("wide", step === "login");` | 登录那一屏宽一档 | 行为测试已守 | 本批补：`test_without_a_saved_account_starts_at_the_login_form` — AssertionError: False is not true : 登录这一屏宽一档 |
| J46 | 甲 | `reloginStep` `if (el) el.hidden = acts.indexOf(id) < 0;` | 底栏按钮按步骤显隐 | 行为测试已守 | 本批补：`test_code_step_after_the_form_says_the_password_is_filled` — AssertionError: True is not false : 第一个按钮该是上一步 |
| J47 | 甲 | `reloginStep` `if (foot) foot.hidden = acts.length === 0;` | 忙碌时整条底栏收起 | 行为测试已守 | 本批补：`test_busy_step_hides_the_whole_foot_bar` — AssertionError: True is not false : 等待步整条底栏收起 |
| J48 | 甲 | `reloginNextReady` `if (btn) btn.disabled = !user \|\| !pass;` | 账号密码都填了才亮下一步 | 行为测试已守 | 本批补：`test_without_a_saved_account_starts_at_the_login_form` — AssertionError: False is not true : 账号密码没填之前不能下一步 |
| J49 | 甲 | `reloginCodeReady` `if (btn) btn.disabled = !/^[0-9A-Za-z]{4}$/.test(code);` | 验证码满 4 位才亮登录 | 行为测试已守 | 本批补：`test_code_step_explains_the_computer_fills_the_password` — AssertionError: False is not true : 验证码没填满 4 位时不能提交 |
| J50 | 甲 | `reloginError` `err.hidden = !text;` | 红字有内容才出现 | 行为测试已守 | 本批补：`test_error_line_only_shows_when_it_has_text` — AssertionError: False is not true : 没有错误时红字条不该出现 |
| J51 | 甲 | `openRelogin` `if (reloginRelay && reloginRelay.live) {` | 中继里有一场在跑就接上 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: 'login' != 'cap' |
| J52 | 甲 | `openRelogin` `if (reloginRelay.state === "waiting_code" && reloginRelay.mode !== "auto" && reloginRelay.image) {` | 接上时已经有验证码图就直接画验证码步 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: 'wait' != 'cap' |
| J53 | 甲 | `openRelogin` `reloginStep("wait", reloginRelay.mode === "auto" ? "电脑正在识别验证码…" : "正在登录…");` | 接上时等待行的说法 | 行为测试已守 | 本批补：`test_relay_auto_mode_says_the_computer_is_recognizing` — AssertionError: '正在登录…' != '电脑正在识别验证码…' |
| J54 | 甲 | `openRelogin` `if (kind === "bad") reloginStep("bad");` | 保存的密码不对就落那一步 | 行为测试已守 | 本批补：`test_rejected_saved_password_opens_the_update_step` — AssertionError: '登录学校账号' != '保存的密码不对' |
| J55 | 甲 | `openRelogin` `else if (kind === "captcha") {` | 有保存账号直接开验证码步 | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: 'login' != 'wait' |
| J56 | 甲 | `openRelogin` `else reloginStep("login");` | 没账号落登录表单 | 行为测试已守 | 本批补：`test_without_a_saved_account_starts_at_the_login_form` — AssertionError: '保存的密码不对' != '登录学校账号' |
| J57 | 甲 | `loginEntry` `if (login.result === "expired" \|\| login.handoff) {` | 登录过又失效才走重新登录 | 行为测试已守 | 旧用例：`test_handoff_restores_the_reminder_and_asks_for_the_captcha` — AssertionError: 'login' != 'cap' |
| J58 | 甲 | `closeRelogin` `const live = S.relogin && S.relogin.step && ["wait", "cap"].indexOf(S.relogin.step) >= 0;` | 关掉时还活着的场次才要取消 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: Lists differ: [] != ['f2'] |
| J59 | 甲 | `closeRelogin` `if (live && flowId && !reloginAutoLive(flowId)) return api("relogin_cancel", flowId).catch(() => {});` | 关掉时取消这一场 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: Lists differ: [] != ['f2'] |
| J60 | 甲 | `reloginRefusal` `if (data.error === "plan_late") {` | 计划来不及时单独一句 | 行为测试已守 | 本批补：`test_plan_too_late_is_explained_with_a_reason` — AssertionError: '现在来不及重新登录' not found in '有场次正在提交' |
| J61 | 甲 | `reloginRefusal` `return String(data.text \|\| "这次没能开始登录，稍后再试。");` | 后端拒绝的兜底说法 | 行为测试已守 | 本批补：`test_generic_refusal_shows_the_backend_text` — AssertionError: '这次没能开始登录，稍后再试。' != '服务器忙，请稍后再试' |
| J62 | 甲 | `receiveReloginState` `if (handoff && !reloginHandoffSeen) {` | 转人工只提醒一次 | 行为测试已守 | 旧用例：`test_handoff_log_matches_the_attempt_count` — AssertionError: '电脑没认出验证码' not found in '' |
| J63 | 甲 | `receiveReloginState` `if (!handoff) reloginHandoffSeen = false;` | 没转人工时清掉提醒过的标记 | 行为测试已守 | 本批补：`test_handoff_reminder_resets_after_a_non_handoff_event` — AssertionError: '3 次没认对' not found in '14:00:00  [!] 电脑没认出验证码，请点「重新登录」输入验证码' : 第二次转人工要再提醒一次 |
| J64 | 甲 | `receiveReloginState` `if (data.state === "success" \|\| data.live === false) S.login.handoff = false;` | 一场走完就不再是等用户输码 | 行为测试已守 | 旧用例：`test_L12_finished_relay_clears_handoff_so_auto_login_can_return` — AssertionError: True is not false : 这一场走完就不再等验证码 |
| J65 | 甲 | `receiveReloginState` `else if (handoff) S.login.handoff = true;` | 转人工时记下已转人工 | 行为测试已守 | 旧用例：`test_handoff_restores_the_reminder_and_asks_for_the_captcha` — AssertionError: False is not true |
| J66 | 甲 | `receiveReloginState` `const auto = String(data.origin \|\| "") === "auto" && !!data.live && !handoff` | 顶栏「自动登录中…」的成立条件 | 行为测试已守 | 旧用例：`test_a_live_auto_flow_survives_an_unknown_check` — AssertionError: False is not true |
| J67 | 甲 | `receiveReloginState` `if (auto !== !!S.autoLogin) {` | 自动登录态变了才重画胶囊与横幅 | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_relay_finishes_or_hands_off` — AssertionError: True is not false |
| J68 | 甲 | `receiveReloginState` `if (!S.relogin \|\| !S.relogin.open) {` | 对话框没开时只记账不接管画面 | 行为测试已守 | 旧用例：`test_relogin_success_without_flow_id_refreshes_only_once` — AssertionError: JS 行为测试崩溃：TypeError: Cannot read properties of undefined (reading 'flowId') |
| J69 | 甲 | `receiveReloginState` `if (data.state === "success") {` | 对话框没开时成功就刷新列表 | 行为测试已守 | 旧用例：`test_relogin_success_without_flow_id_refreshes_only_once` — AssertionError: 0 != 1 : 无 flow_id 的成功快照同样要立刻拉一次活动列表 |
| J70 | 甲 | `receiveReloginState` `if (state === "waiting_code" && data.mode !== "auto" && data.image) {` | 等到用户输码时画验证码步 | 行为测试已守 | 旧用例：`test_saved_account_goes_straight_to_the_captcha_without_confirming` — AssertionError: 'wait' != 'cap' |
| J71 | 甲 | `receiveReloginState` `if (state === "verifying" \|\| state === "starting" \|\| (state === "waiting_code" && data.mode === "auto")) {` | 进行中画等待行 | 行为测试已守 | 本批补：`test_verifying_state_draws_the_wait_step` — AssertionError: '正在打开学校登录页…' != '正在登录…' |
| J72 | 甲 | `receiveReloginState` `if (state === "success") {` | 对话框开着时成功画结果步 | 行为测试已守 | 旧用例：`test_open_dialog_success_also_loads_the_list` — AssertionError: 0 != 1 : 对话框确认成功后也要加载列表 |
| J73 | 甲 | `receiveReloginState` `if (state === "failed" \|\| state === "canceled") {` | 失败/取消画结果步 | 行为测试已守 | 旧用例：`test_bad_password_goes_to_the_bad_step_not_a_generic_message` — AssertionError: 'wait' != 'bad' |
| J74 | 甲 | `receiveReloginState` `if (code === "bad_password") reloginStep("bad");` | 密码不对落「保存的密码不对」 | 行为测试已守 | 旧用例：`test_bad_password_goes_to_the_bad_step_not_a_generic_message` — AssertionError: 'msg' != 'bad' |
| Y01 | 乙 | `paintLogin` `if (S.busy && !S.login.loginPending` | paintLogin 读 S.busy | 行为测试已守 | 旧用例：`test_busy_pill_shows_expired_but_keeps_unknown` — AssertionError: '登录待确认' != '已登录' |
| Y02 | 乙 | `paintLogin` `&& !S.login.loginPending && !busyExpired` | paintLogin 读 S.login.loginPending | 行为测试已守 | 本批补：`test_busy_plan_does_not_hide_a_login_in_progress` — AssertionError: '已登录' != '登录中…' |
| Y03 | 乙 | `paintLogin` `&& !busyExpired && !S.autoLogin) {` | paintLogin 读 S.autoLogin | 行为测试已守 | 本批补：`test_busy_plan_says_auto_login` — AssertionError: '已登录' != '自动登录中…' |
| Y06 | 乙 | `paintLogin` `} else if (S.login.checking \|\| (ok === null` | paintLogin 读 S.login.checking | 行为测试已守 | 本批补：`test_checking_without_a_saved_session_says_checking` — AssertionError: '未登录' != '检查登录…' |
| Y07 | 乙 | `setBusy` `if (S.busy && S.tour.open` | setBusy 读 S.busy 暂停引导 | 行为测试已守 | 旧用例：`test_busy_pause_releases_constraints_and_resume` — AssertionError: True is not false : 暂停期间引导不可见（不挡运行界面） |
| Y08 | 乙 | `setBusy` `if (!S.busy && S.tour.paused) tourResumeNow();` | setBusy 读 S.busy 继续引导 | 行为测试已守 | 旧用例：`test_busy_pause_releases_constraints_and_resume` — AssertionError: True is not false : 暂停期间引导不可见（不挡运行界面） |
| Y09 | 乙 | `setResult` `if (!S.busy) setResult(null);` | 结果条自动收起前读 S.busy | 行为测试已守 | 本批补：`test_auto_close_result_stays_while_a_plan_runs` — AssertionError: True is not false : 忙碌时结果条要留着 |
| Y11 | 乙 | `reconcileAutoLogin` `!reloginAutoLive()) S.autoLogin = false;` | reconcileAutoLogin 经 reloginAutoLive 读中继 | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_check_cannot_reach_the_school` — AssertionError: True is not false |
| Y12 | 乙 | `setLogin` `if (S.login.result === "expired" && !S.login.handoff)` | setLogin 读 S.login.handoff | 等价 | 紧接着调用的 reconcileAutoLogin 在已转人工时会把 S.autoLogin 收回，所以这一行的取值不影响最终状态。 |
| Y13 | 乙 | `reloginAutoLive` `if (!relay \|\| !relay.live \|\|` | reloginAutoLive 读中继的 live | 行为测试已守 | 本批补：`test_closing_cancels_a_finished_auto_relay` — AssertionError: Lists differ: [] != ['f8'] |
| Y14 | 乙 | `reloginAutoLive` `relay.handoff \|\| String(relay.origin` | reloginAutoLive 读中继的 handoff | 行为测试已守 | 旧用例：`test_closing_after_the_auto_flow_handed_off_still_cancels` — AssertionError: Lists differ: [] != ['f1'] |
| Y17 | 乙 | `watchBrowserLogin` `if (!S.relogin \|\| !S.relogin.open) {` | 轮询读 S.relogin.open | 行为测试已守 | 本批补：`test_browser_watch_stops_when_the_dialog_closes` — AssertionError: JS 行为测试崩溃：TypeError: dlg.removeAttribute is not a function |
| Y18 | 乙 | `watchBrowserLogin` `if (login.result === "valid" \|\| login.ok === true) {` | 轮询读 S.login 的结论 | 行为测试已守 | 本批补：`test_browser_watch_closes_on_a_valid_login` — AssertionError: '登录成功' not found in '' |
| Y19 | 乙 | `openRelogin` ` && reloginRelay.live) {` | openRelogin 读中继的 live | 行为测试已守 | 旧用例：`test_network_error_can_be_retried_with_a_new_captcha` — AssertionError: 1 != 2 : 再试一次要真开新的一场 |
| Y20 | 乙 | `openRelogin` `reloginRelay.state === "waiting_code" && ` | openRelogin 读中继的 state | 行为测试已守 | 本批补：`test_a_pending_login_window_blocks_the_auto_refresh` — AssertionError: False is not true : 窗口关掉后自动刷新照旧 |
| Y21 | 乙 | `openRelogin` ` && reloginRelay.mode !== "auto"` | openRelogin 读中继的 mode（是否自动） | 行为测试已守 | 本批补：`test_relay_auto_mode_waits_instead_of_showing_code` — AssertionError: 'cap' != 'wait' |
| Y22 | 乙 | `openRelogin` ` && reloginRelay.image) {` | openRelogin 读中继的 image | 行为测试已守 | 本批补：`test_relay_without_an_image_waits_instead_of_showing_code` — AssertionError: 'cap' != 'wait' |
| Y23 | 乙 | `openRelogin` `reloginStep("wait", reloginRelay.mode === "auto" ? "电脑正在识别验证码…" : "正在登录…");` | openRelogin 等待行读中继的 mode | 行为测试已守 | 本批补：`test_auto_once_result_after_closing_does_not_move_the_step` — AssertionError: 'wait' != 'login' |
| Y24 | 乙 | `reloginPickWay` `if (!S.relogin \|\| !S.relogin.open) return;` | reloginPickWay 读 S.relogin.open | 行为测试已守 | 本批补：`test_pick_way_after_closing_does_not_move_the_step` — AssertionError: 'login' != 'cap' |
| Y26 | 乙 | `closeRelogin` `if (live && flowId && !reloginAutoLive(flowId))` | closeRelogin 经 reloginAutoLive 读中继 | 行为测试已守 | 旧用例：`test_closing_a_user_started_flow_still_cancels_it` — AssertionError: Lists differ: [] != ['f2'] |
| Y27 | 乙 | `beginRelogin` `if (!S.relogin.open) return;` | beginRelogin 读 S.relogin.open | 行为测试已守 | 本批补：`test_begin_result_after_closing_does_not_move_the_step` — AssertionError: 'f9' != '' |
| Y28 | 乙 | `autoReloginOnce` `if (!S.relogin.open) return;` | autoReloginOnce 读 S.relogin.open | 行为测试已守 | 本批补：`test_auto_once_result_after_closing_does_not_move_the_step` — AssertionError: 'f8' != '' |
| Y29 | 乙 | `submitReloginCode` `if (S.relogin.open && result` | 提交验证码回来读 S.relogin.open | 行为测试已守 | 本批补：`test_a_failed_code_answer_after_closing_does_not_show_a_message_step` — AssertionError: 'msg' != 'wait' |
| Y30 | 乙 | `reloginSucceeded` `if (S.busy) return;` | 登录成功后读 S.busy | 行为测试已守 | 本批补：`test_success_during_a_plan_does_not_refresh_the_list` — AssertionError: Lists differ: ['check', 'refresh'] != [] |
| Y31 | 乙 | `receiveReloginState` `!(S.login && S.login.result === "valid")` | 收进度时读 S.login 的结论 | 行为测试已守 | 旧用例：`test_relay_replay_after_a_valid_check_does_not_bring_auto_login_back` — AssertionError: True is not false |
| Y32 | 乙 | `receiveReloginState` `if (auto !== !!S.autoLogin) {` | 收进度时读 S.autoLogin | 行为测试已守 | 旧用例：`test_pill_leaves_auto_login_when_the_relay_finishes_or_hands_off` — AssertionError: True is not false |
| Y33 | 乙 | `receiveReloginState` `if (!S.relogin \|\| !S.relogin.open) {` | 收进度时读 S.relogin.open | 行为测试已守 | 本批补：`test_closed_dialog_success_does_not_log_the_done_line` — AssertionError: '重新登录成功' unexpectedly found in '14:00:00  重新登录成功' |
| Y34 | 乙 | `receiveReloginState` `if (S.busy) addLog("重新登录成功，报名计划照常继续");` | 对话框没开时读 S.busy 写运行记录 | 行为测试已守 | 本批补：`test_closed_dialog_busy_success_logs_the_plan_line` — AssertionError: '重新登录成功，报名计划照常继续' not found in '' |
| Y35 | 乙 | `receiveReloginState` `addLog(S.busy ? "重新登录成功，报名计划照常继续" : "重新登录成功");` | 成功那一条运行记录读 S.busy | 行为测试已守 | 本批补：`test_open_dialog_busy_success_log_mentions_the_plan` — AssertionError: '重新登录成功，报名计划照常继续' not found in '14:00:00  重新登录成功' |
| Y36 | 乙 | `receiveReloginState` `reloginStep("msg", S.busy ? "重新登录成功，报名计划照常继续。" : "重新登录成功。");` | 成功结果步读 S.busy | 行为测试已守 | 本批补：`test_open_dialog_busy_success_message_mentions_the_plan` — AssertionError: '重新登录成功。' != '重新登录成功，报名计划照常继续。' |
| Y37 | 乙 | `receiveReloginState` `if (S.relogin.flowId && data.flow_id && String(data.flow_id) !== S.relogin.flowId) return;` | 收进度时读 S.relogin.flowId | 行为测试已守 | 本批补：`test_stale_progress_from_another_flow_is_ignored` — AssertionError: 'msg' == 'msg' : 别的 flow 的失败不该改当前步骤 |
| Y38 | 乙 | `renderLoginCard` `S.busy \|\| !!S.login.checking` | 登录详情卡的检查按钮读 S.busy | 行为测试已守 | 本批补：`test_login_card_check_button_disabled_while_busy` — AssertionError: False is not true : 忙碌时检查按钮要禁用 |
| Y39 | 乙 | `renderLoginCard` `!!S.login.checking \|\| termsLocked()` | 登录详情卡的检查按钮读 S.login.checking | 行为测试已守 | 本批补：`test_login_card_check_button_disabled_while_checking` — AssertionError: False is not true : 检查中检查按钮要禁用 |
| Y40 | 乙 | `scheduleSignedRefresh` `if (S.busy \|\| S.starting \|\| S.demo) return;` | 计划运行时推迟刷新读 S.busy | 行为测试已守 | 旧用例：`test_success_event_schedules_one_bounded_refresh` — AssertionError: {'bus[20 chars]nt': 1}, 'starting': {'armed': 1, 'sent': 0}, [27 chars]: 0}} != {'bus[20 chars]nt': 0}, 'starting': {'armed': 1, 'sent': 0}, [27 chars]: 0}} |
| Y41 | 乙 | `checkRoundOpen` `return S.round.background ? !!S.runtime.checkPending : !!S.login.checking;` | 前台轮是否在跑读 S.login.checking | 行为测试已守 | 旧用例：`test_L01_check_timeout_after_100s_leaves_checking` — AssertionError: True is not false : 超时后不能停在检查中 |
| Y42 | 乙 | `autoRefreshDue` `if (S.login.result !== "valid") return false;` | 自动刷新读 S.login 的结论 | 行为测试已守 | 旧用例：`test_each_skip_condition_blocks_the_tick_on_its_own` — AssertionError: True is not false : 「登录结论不是 valid」成立时这一拍不能刷新 |
| Y43 | 乙 | `autoRefreshDue` `if (S.login.loginPending) return false;` | 自动刷新读 S.login.loginPending | 行为测试已守 | 本批补：`test_a_pending_login_window_blocks_the_auto_refresh` — AssertionError: True is not false : 登录窗口开着时不该自动刷新 |
| Y44 | 乙 | `autoRefreshDue` `if (S.login.checking) return false;` | 自动刷新读 S.login.checking | 行为测试已守 | 旧用例：`test_each_skip_condition_blocks_the_tick_on_its_own` — AssertionError: True is not false : 「正在检查登录」成立时这一拍不能刷新 |

## 结论数字

行为测试已守 109；等价 3（理由写在各行里）；没人守 0；只有字面断言守 0（共 112 行）。

## 这一轮补了哪些用例

上一轮量的时候两条新测试文件还没写完（`test_ui_relogin_dialog.py` 有 5 条在跑之前就崩），所以那份 after 里留下了 36 条「没人守」。这一轮先把那 5 条修好（沙箱里日志要从 `#log` 的子节点读、`shown()` 不能在 Python 侧调、去重会吃掉同一句），再按存活清单补了 7 条：

- `test_ui_login_capsule.py`：有锚点时胶囊写明「预计约到 …」、登录窗口开着时不自动刷新列表、已转人工时后端再说 recovering 也不点亮「自动登录中…」。
- `test_ui_relogin_dialog.py`：对话框关着时，开始登录 / 自动登录 / 选登录方式 / 提交验证码的返回都不该把流程推进下去（4 条）。

补完重跑全部 112 条：109 条变红，剩下 3 条记等价。
