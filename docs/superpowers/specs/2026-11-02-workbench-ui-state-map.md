# 新工作台原型：场景与数据来源对照表

状态：文档先行，2026-11-03（UI-A 计划产物；代码未落地）

- 设计真源：[新工作台设计](2026-11-02-workbench-ui-redesign-design.md)
- 原型快照：[design/prototype/workbench-2026-11/](../../../design/prototype/workbench-2026-11/README.md)（版本 32，83 张画板）
- 界面规则与文案以设计文档为准；设计文档没写的，以 `Main.dc.html` / `Phone.dc.html` 的 `renderVals()` 为准。
- 本表按原型场景目录逐行，去掉 `DesignSpec`（视觉规范）与 `ImplNotes`（实现备注）两张说明板。
- 字段名以现有代码为准：`local/app.py` 的 `Api` 快照、`onBackend` 事件、`local/signup_plan.py` 的任务快照。
- 「缺口」只列现有后端没有的新增字段或动作，并指向 UI-B（`20261103-ui-b-core`）或 UI-C（`20261103-ui-c-finish`）的任务 id；现有字段够用的写「无」。

## 数据来源速记

| 来源 | 关键字段 |
|---|---|
| `bootstrap()` | `version`、`prefs`、`terms{version, accepted_version, accepted_at}`、`business_clock`、`help`、`advanced_features`、`login{session_present, session_expired, last_check_at, last_check_state}`、`lifecycle`、`demo`、`retry_options`、`busy`、`update_check`、`plan`（重载时的计划快照） |
| `onBackend.activities` | `{ok, items}`；活动项字段见 `docs/UI_SPEC.md` §5.3（`signed`、`sync_pending`、`state`、`seconds_to_open` 等） |
| `onBackend.check` | `{ok, session_present, session_expired, text, reason, hint, result}` |
| `onBackend.plan` / `onBackend.task` | 任务快照：`status`、`stop_reason`、`outcome_label`、`last_reason`、`attempts`、`retry_deadline`、`path`（`direct`/`click`）、`path_reason`、`login_wait`、`login_wait_until` |
| `onBackend.plan_done` | `{plan_id, status, ok, summary}` |
| `advanced_features_state()` | `features`（`phone_control`、`relogin_ocr`）、`channels{tailscale, cloudflare}`、`phone_access`、`credential{saved, username, ocr_ready, automatic, last_origin}` |
| `phone_access_state()` | `running`、`channel`、`address`、`qr`、`pair_code`、`pair_code_status`、`preferred_channel`、`tailscale_autostart` |
| 手机 `/api/state` | `activities`、`login`（只有 `login_state`，没有 `last_check_*`）、`plan`、`busy`、`business_clock`、`retry_options`、`terms`、`login_relay` |
| 业务时钟 | `state`、`source`、`uncertainty_s`、`age_s`、`sync_status`、`retry_attempt`、`retry_in_s`、`last_failure_source`、`last_failure_reason`（`bootstrap.business_clock` 与 `onBackend.business_clock` 同源） |
| 前端自测信号 | 断网 `navigator.onLine`；睡眠看 `controllers/tick.js` 的心跳间隔（`S.sleepGap`，单调时钟；`lifecycle` 只描述上次关闭程序，不是运行中睡眠）；组件缺失看 `worker_missing` 等错误码 |

## 场景对照表

| 画板 | 场景 | 界面显示的关键状态 | 数据来源 | 缺口（新增 → 任务 id） |
|---|---|---|---|---|
| Main | `draft` | 宽窗默认；时刻表分天与「现在」线；计划栏草稿已选 3 场；手机标识已连接 | `onBackend.activities.items`（`name`/`place`/`sign_start`/`state`/`seconds_to_open`/`signed`/`checkin_required`/`checkout_required`）；`bootstrap.login`（`session_present`/`last_check_at`/`last_check_state`）；`bootstrap.business_clock`（`state`/`source`）；`advanced_features.phone_access` + `phone_access_state.running`/`pair_code_status.reason`；`prefs.retry_policy`（`retry_for_s`/`max_attempts`）；前端草稿选择 | 无 |
| Running | `running` | 计划栏等开放或提交中；路线图；每场提交次数与最近回应 | `bootstrap.plan` 或 `onBackend.plan`/`onBackend.task`：`status`/`attempts`/`last_reason`/`retry_deadline`/`path`/`path_reason`/`login_wait`；`onBackend.plan_done.summary`；`bootstrap.retry_options` | 无 |
| Result | `result` | 结果大数字只显示不为 0 的；每场结论；待核对场次给「刷新核对」 | `onBackend.plan_done`（`status`/`summary`）；`onBackend.task`（`status`/`stop_reason`/`outcome_label`/`attempts`/`last_reason`）；`onBackend.activities.items.signed`（刷新核对） | 刷新核对入口 → code-arch-followups |
| Attention | `unknown` | 登录胶囊「暂时无法确认」；不诱导重新登录 | `bootstrap.login.last_check_state`（`unknown`）；`onBackend.check`（`result`/`reason`/`hint`/`text`）；`advanced_features.credential.ocr_ready` | 无 |
| FirstUse | `first` | 条款弹窗先于欢迎与引导；未同意时学校动作停用；同意后才继续引导 | `bootstrap.terms`（`version`/`accepted_version`/`accepted_at`）；`bootstrap.login.session_present`；`prefs.tour_version`/`tour_completed_at`/`tour_skipped_at` | 无（引导版本 3 由 code-ui-dialogs 实现） |
| Settings | `settings` | 设置抽屉三组：高级功能 / 登录 / 程序；条款与隐私可撤回 | `advanced_features_state`（`features`/`channels`/`credential`）；`phone_access_state`；`prefs.window.close_action`；`bootstrap.terms`；`bootstrap.update_check` | 撤回同意 `withdraw_terms` → code-backend-terms |
| Short | `draft` | 矮窗（高 < 660）：点阵屏缩到 13rem，计划栏内滚动，主按钮固定底部 | 同 Main；窗口高度走前端 CSS 断点 | 无 |
| Narrow | `draft` | 窄窗（< 720）：单栏、底栏计划条、顶栏只留图标、详情卡铺满 | 同 Main；视口分档走前端 CSS 断点 | 无 |
| Waiting | `waiting` | 等开放；运行路线图；修改计划、停止计划 | `onBackend.plan`/`onBackend.task`（`status=waiting`/`retry_deadline`/`login_wait`/`login_wait_until`）；`bootstrap.plan`；`stop_plan`/`cancel_task` 返回 | 无（修改流程由 code-ui-plan-panel 实现） |
| Editing | `editing` | 「计划已暂停，改完要重新开始」；可增删场次 | 修改 = `stop_plan` 后重选：`onBackend.plan_done.status=stopped`；`start_plan`/`cancel_task` 返回；后端没有「暂停」状态，修改中是前端模式 | 无 |
| TourTable | `tour` | 五步引导第 1 步高亮时刻表 | `prefs.tour_version`/`tour_completed_at`/`tour_skipped_at`；前端 `TOUR_STEPS`/`TOUR_VERSION` | 无（`TOUR_VERSION` 2→3 由 code-ui-dialogs 实现） |
| TourPick | `tour2` | 第 2 步可真实勾选一行，其余背景不可点 | 同上 + `onBackend.activities.items` | 无 |
| TourRun | `tour4` | 第 4 步指向计划栏 | 同上 + `onBackend.plan`/`onBackend.task` | 无 |
| PhoneSetup | `phonesetup` | 手机访问未安装；标题行右侧「下载并安装」 | `advanced_features.features.phone_control`（`ready`/`busy`/`download`）；`phone_access_state.running`/`supported`/`preferred_channel` | 无 |
| PhoneTs | `phonets` | 通道还差一步：Tailscale 未登录 | `advanced_features.channels.tailscale`（`available`/`state`/`text`） | 无 |
| PhoneWait | `phonewait` | 已开启、等手机连接；二维码、配对码与 5 分钟剩余 | `phone_access_state.running`/`address`/`qr`/`pair_code`/`pair_code_status`（`expires_in`/`seq`/`reason`） | 无 |
| PhoneLinked | `phonelinked` | 手机已连接；配对码收起；没保存账号时提示保存 | `phone_access_state.pair_code_status.reason="paired"`/`pair_code=""`；`advanced_features.credential.saved`/`username` | 无 |
| PhoneApp | `pair` | 手机配对页；6 位点阵输入框 | 手机 `/api/state`（未配对只回公开状态）；配对接口返回；前端输入 | 无 |
| PhonePick | `picked` | 手机首页页签（可报名 / 已报名 / 全部）与勾选；底部「核对并开始」 | 手机 `/api/state`：`activities`（`state`/`signed`/`seconds_to_open`）、`login`、`terms`、`busy`、`business_clock` | 无 |
| PhoneReview | `review` | 核对计划弹层；尝试时长、最多提交次数；开始前提醒 | 手机 `/api/state`：`activities`/`retry_options`/`business_clock`/`terms`；`start_plan` 返回 `plan_id` | 计划来源 `plan.source` → code-backend-signals |
| PhoneRun | `running` | 手机只读进度；只能停止计划 | 手机 `/api/state`：`plan`（`status`/`tasks.status`/`attempts`/`last_reason`/`path`/`path_reason`）、`busy` | `plan.source` → code-backend-signals |
| PhoneResult | `result` | 与电脑同一套结果；待核对给刷新核对 | 手机 `/api/state`：`plan`（`status`/`tasks.stop_reason`/`outcome_label`）；`activities.signed` | 刷新核对 → code-arch-followups |
| PhoneLock | `pairlock` | 配对码错太多被锁，显示倒计时 | 配对接口返回的锁定剩余秒数与错误码；前端倒计时 | 无 |
| PhoneOffline | `offline` | 顶部红条「确认电脑开着、程序没退出」；提供重试 | 前端 `fetch` 失败/超时；最近成功时间由前端记录 | 无 |
| PhoneCheck | `pending` | 开始请求长时间没回应 | 前端请求超时；手机 `/api/state.busy` | 无 |
| PhoneExpired | `expired` | 登录失效；可重新登录 | 手机 `/api/state`：`login`（`session_present`/`session_expired`）、`login_relay` | 手机 `last_check_*` → code-arch-followups；`relogin_*` → code-backend-relogin |
| PhoneCaptcha | `captcha` | 电脑有账号、没识别：手机只输验证码 | 手机 `/api/state.login_relay`（`mode`/`challenge_id`/`image`/`retrying`）；`phone_relogin_submit` 返回 | 无（电脑端 `relogin_*` → code-backend-relogin） |
| PhoneAuto | `auto` | 电脑自动登录中，手机只显示进度 | 手机 `/api/state.login_relay`（`mode="auto"`/`retrying`/`retry_in`/`auto_failures`） | 无 |
| CloseLive | `closerun` | 可操作关窗入口 | `onBackend.window_close_ask`（`plan_running`/`default_action`） | 关窗载荷 `tray_ok`/`phone_running`/`phone_live` → code-ui-dialogs |
| CloseAsk | `closeask` | 计划运行中；先列计划与手机访问，再给三个出口 | 同上 + `phone_access_state.running`；`prefs.window.close_action` | 同上 |
| CloseConfirm | `closeexit` | 计划运行中选退出，二次确认 | `window_close_ask.plan_running`；`request_window_close` 返回 | 同上 |
| CloseIdle | `closeidle` | 没计划、托盘也不可用：隐藏到后台不可用 | `window_close_ask.default_action`；托盘可用性目前没有载荷字段 | 关窗载荷 `tray_ok`/`phone_running` → code-ui-dialogs |
| CloseHidden | `closehidden` | 已隐藏到后台；托盘或手机可召回 | `request_window_close("hide")` 返回；`prefs.window.close_action="hide"` | 同上（含 `phone_live`） |
| UpdateLive | `update` | 版本与更新行；点「检查更新」 | `bootstrap.update_check`（`checking`/`result`/`installer_path`）；`onBackend.update` | 无 |
| UpdateAvail | `upavail` | 发现新版本；标题行右侧「下载并安装」 | `update_check.result`（`state=available`/版本/资产）；`onBackend.update` | 无 |
| UpdateDown | `updown` | 下载中（41%）；可取消 | `onBackend.update`（`state=downloading`/`downloaded`/`total_bytes`/`request_id`） | 无 |
| UpdateReady | `upready` | 校验通过；计划运行中提醒并改「仍然启动安装程序」 | `update_check.result`（`state=ready_to_install`）；`bootstrap.busy`/`onBackend.plan.status` | 无 |
| UpdateFail | `upfail` | 校验失败；旧版本与数据未动 | `update_check.result`（`state=failed`/`error_code`/`text`） | 无 |
| CompLive | `comp` | 验证码识别可一键下载安装 | `advanced_features.features.relogin_ocr`（`ready`/`busy`/`download`）；`advanced_features.credential.ocr_ready` | `relogin_ocr` 组件资产与下载 → code-backend-ocr-asset |
| CompWrong | `compwrong` | 手动导入选错包，说清选的是哪个 | 导入接口返回（`kind`/`feature`/`version`/`text`）；`advanced_features.features.relogin_ocr` | 同上 |
| CompOk | `compok` | 下载中（41%） | `advanced_features.features.relogin_ocr.download`（`state`/进度）；组件下载事件 | 同上 |
| CredForm | `credform` | 填写账号密码；默认只用一次，可勾选保存 | `advanced_features.credential`（`available`/`store_available`/`saved`/`username`）；`save_relogin_credentials` 返回 | 无 |
| CredSaved | `credsaved` | 已保存账号，自动登录已启用 | `credential.saved`/`username`/`ocr_ready`/`automatic`（`state`/`inflight`/`failures`/`retry_in`） | 无 |
| CompFail | `compfail` | 下载失败：重试，或露出导入组件包 | `features.relogin_ocr.download`（`state=failed`/`error`/`text`）；导入接口 | 同上（`relogin_ocr` 组件资产） → code-backend-ocr-asset |
| Relogin | `relogin` | 有账号、没识别：电脑填账号密码，用户只输验证码 | `credential.saved`/`ocr_ready`；`relogin_begin`/`relogin_submit`/`relogin_cancel` 返回；`bootstrap.login.last_check_state` | `relogin_*` → code-backend-relogin |
| RlCap | `rlcap` | 电脑上输验证码 | 同上 + `login_relay`（`challenge_id`/`image`） | 同上 |
| RlConfirm | `rlconfirm` | 自动登录一次，先确认 | `credential.ocr_ready`/`automatic`；`relogin_auto_once` 返回 | 同上 |
| RlBad | `rlbad` | 保存的密码学校不认；自动登录暂停 | `credential.automatic`（暂停/失败次数/`retry_in`）；`relogin_*` 返回错误码 | `relogin_*` 的 `bad` 暂停标记 → code-backend-relogin |
| LoginShort | `loginshort` | 登录撑不到开放；开始前提醒（最晚一场 1 小时以上且没开全自动） | `bootstrap.login`；`credential.saved`/`ocr_ready`/`automatic`；`onBackend.plan.tasks.sign_start`；`bootstrap.business_clock` | 无 |
| PhoneRelAll | `relall` | 手机：电脑没账号、没识别，账号密码验证码都输 | 手机 `/api/state.login_relay`（`mode`）；`phone_relogin_begin`/`phone_relogin_submit` 返回 | 无（电脑端 `relogin_*` → code-backend-relogin） |
| PhoneRelAcct | `relacct` | 手机：电脑没账号、有识别，只输账号密码 | 同上 | 无 |
| PhoneRelConfirm | `relconfirm` | 手机：自动登录一次，先确认 | 手机 `/api/state.login_relay`（`mode="auto"`/`retrying`） | 无 |
| PhoneRelBad | `relbad` | 保存的密码不认；自动登录暂停 | 手机 `/api/state.login_relay`；`credential.automatic` 的暂停原因 | `bad` 暂停标记 → code-backend-relogin |
| TermsUpdate | `termsupdate` | 条款升版弹窗列 6 条改动；正文标「本版新增」 | `bootstrap.terms`（`version` 与 `accepted_version` 不同）；内嵌条款正文；`accept_terms` 返回 | 无 |
| TermsDoc | `termsdoc` | 完整条款三页签；同意新版 | `bootstrap.terms`；`accept_terms(document_version)`；内嵌条款正文 | 无 |
| TermsPrivacy | `termsprivacy` | 隐私政策页签，只读 | 内嵌条款正文；`bootstrap.terms.accepted_at` | 无 |
| TermsOff | `termsoff` | 没同意：胶囊「等同意条款」；学校动作停用；缓存列表只读 | `bootstrap.terms`（`version`/`accepted_version`）；`onBackend.activities.items`（缓存）；后端 `_terms_gate` 拒绝 | 无 |
| TermsWithdraw | `termswithdraw` | 撤回同意需确认；计划运行中不可撤回 | `bootstrap.terms`；`bootstrap.busy`；`withdraw_terms` | `withdraw_terms` → code-backend-terms |
| PhoneTerms | `phoneterms` | 手机：电脑没同意，停在缓存，不能开始或重登 | 手机 `/api/state.terms`（`version`/`accepted_version`）；`terms_ok` | 手机 `terms_ok` → code-backend-terms |
| PopClock | `popclock` | 时间详情卡：五态、误差、来源、重新校准 | `bootstrap.business_clock`/`clock_snapshot`（`state`/`source`/`uncertainty_s`/`age_s`/`sync_status`/`retry_attempt`/`retry_in_s`/`last_failure_source`/`last_failure_reason`） | 无 |
| PopLogin | `poplogin` | 登录详情卡：大号「登录有效」+ 上次校验；不显示剩余时间 | `bootstrap.login`（`session_present`/`last_check_at`/`last_check_state`）；`credential.saved`/`ocr_ready`/`automatic`；`phone_access_state.running` | 无 |
| PopDown | `popdown` | 北京时间待校准；不影响已保存登录 | `business_clock.state=unavailable`/`retry_in_s`/`last_failure_reason` | 无 |
| PopPhone | `popphone` | 手机访问详情卡：连接状态与管理入口 | `phone_access_state.running`/`channel`/`address`/`pair_code_status`；`advanced_features.channels` | 无 |
| PreWarn | `prewarn` | 开始前提醒：断网、上次校准结果、1 小时以上无全自动、到截止但无截止时间、24 小时以上 | `navigator.onLine`；`business_clock.state`；`credential.saved`/`ocr_ready`/`automatic`；`activities.items.sign_start`/`sign_end`；`bootstrap.retry_options` | 无 |
| NetOff | `netoff` | 计划运行中断网横幅 | `navigator.onLine`；`onBackend.task.last_reason`/`stop_reason`；`onBackend.plan.status` | 无 |
| Slept | `slept` | 电脑睡眠错过开放；行标「错过了」，可重新勾选 | 前端心跳间隔 `S.sleepGap`（`controllers/tick.js`）；`onBackend.task.status`/`stop_reason`/`attempts`（间隔内到点、没提交过的场次）；`activities.items.state`/`seconds_to_open` | 无（用现有信号推导，「错过了」只标在睡眠间隔内到点且没提交的场次） |
| Broken | `broken` | 程序组件缺失横幅；活动列表不加载 | `advanced_features.features`（`ready`/`reason`）；`onBackend.activities`/`onBackend.check` 的 `worker_missing` 等错误码 | 无 |
| HelpKeys | `helpkeys` | 帮助里的键盘快捷键 | `bootstrap.help`；`prefs.tour_version` | 无 |
| LongName | `longname` | 超长活动名与地点两行截断，悬停看全文 | `activities.items.name`/`place` | 无 |
| NarrowPop | `poplogin` | 窄窗详情卡铺满宽度，去指示箭头 | 同 PopLogin；前端 CSS 断点 | 无 |
| NarrowWarn | `prewarn` | 窄窗有提醒时底栏不给「开始」 | 同 PreWarn；前端 CSS 断点 | 无 |
| ZeroAct | `zeroact` | 学校返回 0 场；写明「这不是登录问题」 | `onBackend.activities`（`ok=true`/`items=[]`） | 无 |
| ClockHold | `clockhold` | 沿用上次校准结果；可照常开始，只在计划栏提醒 | `business_clock.state`/`sync_status`/`age_s`/`source` | 无 |
| RunExpired | `runexpired` | 运行中登录失效；计划不停；来不及的场次以「登录失效」结束 | `bootstrap.login.last_check_state=expired`；`onBackend.task.status=failed`/`stop_reason=login_invalid`（`auth_unavailable` 是「登录状态无法确认、未提交」，不是失效）；`task.login_wait`/`login_wait_until`；`relogin_*` | `relogin_*`/`plan_late` → code-backend-relogin |
| ToastMin | `toastmin` | 窗口最小化或隐藏时计划结束，发系统通知 | `onBackend.plan_done`（`status`/`summary`）；`bootstrap.busy`；窗口隐藏由前端状态记录 | `tray.notify` → code-backend-signals |
| RunPhone | `runphone` | 计划栏底部写「这个计划是从手机开始的」 | `bootstrap.plan.source` / `onBackend.plan.source` | `plan.source` → code-backend-signals |
| RunAuto | `runauto` | 等开放时自动登录；胶囊「自动登录中…」 | `onBackend.task.login_wait`/`login_wait_until`（报名进程在等自动登录）；`credential.automatic`（`inflight`/`failures`/`retry_in`）；`login_relay`；`bootstrap.login` | 无 |
| RunClick | `runclick` | 本场改用页面点击及原因；活动页已提前打开 | `onBackend.task.path="click"`/`path_reason`；`onBackend.task` | 无 |
| PhoneReviewWarn | `reviewwarn` | 手机核对计划带提醒；按钮「仍然开始报名计划」 | 手机 `/api/state`：`activities`/`retry_options`/`business_clock`/`terms` | 无 |
| Medium | `draft` | 中档 900：单栏，底部计划条 | 同 Main；前端 CSS 断点（720–1039） | 无 |
| MediumRun | `running` | 中档运行中：计划条 + 查看计划 | 同 Running；前端 CSS 断点 | 无 |

## 只为演示存在、实现时删除的控件

对照原型 `ImplNotes.dc.html`。实现时整段删掉，不要变成隐藏功能；真实程序里状态只来自后端。

| 位置 | 演示控件 | 真实程序里由谁决定 |
|---|---|---|
| 计划栏 | 「演示：时间快进到开放前 12 秒」；结束后「演示时间已复位」 | 真实业务时钟 |
| 设置 · 手机访问 | 演示：下载失败、切换 Tailscale 状态、手机配对成功、Cloudflare 隧道断开 | 组件下载结果、Tailscale 检测、配对服务、隧道进程状态 |
| 设置 · 验证码识别 | 演示：下载失败 | 下载与校验结果 |
| 设置 · 版本与更新 | 演示：下一次检查结果（下拉）、演示：校验失败 | 发布页返回与安装包哈希校验 |
| 导入组件包 | 模拟系统选择文件窗口；按文件名猜校验结论 | 系统文件对话框；包内清单与哈希 |
| 重新登录对话框 | 验证码填 0000；模拟学校说密码不对 | 学校登录接口返回 |
| 关闭窗口 | 模拟 Windows 标题栏、桌面、任务栏、托盘、系统通知；「原型演示：关窗以后」卡片 | pywebview 窗口事件、系统托盘、Windows 通知 |
| 组件缺失横幅 | 「重新检查」直接通过（假设已重装） | 真实文件自检 |
| 手机页 · 配对 | 原型演示配对码提示 | 配对码只显示在电脑上 |
| 手机页 · 菜单 | 「原型演示」整组开关（连不上电脑、登录失效、没保存账号、没装识别、保存密码已改、没同意条款、连续 3 次认错）；快进到开放前 12 秒 | 电脑端推过来的状态 |

假数据（同样不进产品）：活动列表、账号打码、版本号与大小、条款版本与正文、二维码与验证码图片、上次校验时刻。
