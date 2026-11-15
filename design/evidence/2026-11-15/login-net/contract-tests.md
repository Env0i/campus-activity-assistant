# 契约测试逐条分类（local/tests/test_ui_contract_login.py 的 35 条）

- **基线提交**：`896baf2`。执行日期：2026-11-15。
- **量法**：逐条读用例断言什么、归入四类——照原型逐字的文案、无障碍名称、页面里有某个元素（含反向）、源码形状；再写它守的是什么、有没有跑 node 的用例守着同一件事（指名文件与用例），以及本批为它补了哪一条。
- **跑 node 的用例**：指调用了 `fixtures/ui_harness` 的 `run_js`（整页脚本清单）。本文件里自带 18 条；另外新补的两个文件 `test_ui_login_capsule.py`（14 条）与 `test_ui_relogin_dialog.py`（15 条）也算。
- **行为化的边界**：node 沙箱的元素桩对任意选择器自动创建元素，所以「HTML 里有没有这个元素 / 这段文案」在沙箱里证不了；样式表不进沙箱。这类条目保留字面断言，不硬凑。
- **范围说明**：这个文件名叫 login，实际混进了几条不属于登录块的静态契约（时钟浮层、断网/睡眠横幅、宽度断点、结果页行动按钮）。它们不在本计划的搬动范围（表甲表乙只覆盖 `views/login.js`、`state/login.js`、`views/relogin.js` 与两处登录相关读取），本批不在登录的两个新文件里补，理由与代偿用例见下表与结果文件的 plan_amendments。

| # | 用例 | 分类 | 它守的是什么 | 跑 node 的用例守同一件事吗 | 本批补的 |
|---|---|---|---|---|---|
| 1 | test_backend_login_state_fields_in_payloads | 后端载荷 | `app.py` 有 `login_state`，登录载荷带 `session_present` / `session_expired` | 不适用（后端，不在本块） | 不补 |
| 2 | test_login_state_semantics | 后端行为 | 会话文件不存在、解析失败、缺 token、旧 `saved_at` 各判什么 | 不适用（后端） | 不补 |
| 3 | test_check_hint_success_beats_login_keyword | 后端行为 | `code==0` 的成功行含「登录」字样时不得归类 login | 不适用（后端） | 不补 |
| 4 | test_app_js_first_use_is_not_bad | 源码形状（分支与文案） | `paintLogin` 用 `session_present` 区分首次使用；「重新登录」只给登录过的状态 | 有（本批补）：`test_ui_login_capsule.py` 的 `test_first_use_asks_to_log_in` 与 `test_expired_says_relogin` | 已补，见下条 |
| 5 | test_app_js_reuse_login_copy_contract | 照原型逐字的文案（运行记录） | 「已复用本机登录态」与 README 示例同源，禁回退 | 无——这是运行记录文案，登录胶囊与对话框都不显示 | 不补（非登录块的可见面） |
| 6 | test_refresh_catch_leaves_checking | 源码形状（catch 分支写了什么） | `refresh` 的 catch 要清 `checking`、清 `ok`、落 `unknown` | 有：同文件的 `test_refresh_catch_failure_leaves_checking_and_sets_unknown`（跑 node） | 不补（已有） |
| 7 | test_refresh_catch_failure_leaves_checking_and_sets_unknown | 行为 | 同上，运行时真的清了三态并写运行记录 | — | — |
| 8 | test_start_button_requires_valid_or_demo | 源码形状（门禁条件） | 开始按钮要求 `result === "valid"` 且 `!checking`，demo 例外 | 无 | `test_ui_login_capsule.py` 的 `test_start_button_waits_for_a_confirmed_login`：同一份可开始状态只换登录结论，断言有效时可点、失效与检查中禁用 |
| 9 | test_bootstrap_carries_demo_flag | 后端载荷 | `bootstrap` 载荷带 demo 标记，前端门禁才能放行演示 | 不适用（后端） | 不补 |
| 10 | test_backend_start_plan_rejects_unconfirmed_login | 后端行为 | 非 demo 且最近 check 不是 valid 时 `start_plan` 拒绝 | 不适用（后端最终防线） | 不补 |
| 11 | test_login_expiry_check_present | 源码形状 | 检查条只报学校登录结论；开始前提醒按「最晚一场要等多久」给，不再拿登录估算比窗口 | 部分：`test_ui_contract_shell.py` 的 `test_five_pre_start_warnings_only_remind` 守提醒句；检查条本身没有行为用例 | 不补（属计划栏，不在登录块的搬动范围；见 plan_amendments） |
| 12 | test_clock_skew_structured_and_not_text_scraped | 源码形状 | 学校时间只认结构化载荷，逐轮替换，只进时间详情浮层 | 有：`test_ui_reliability.py` 的 `test_warn_then_ok_then_unknown`（跑 node） | 不补（已有） |
| 13 | test_online_offline_banners | 源码形状 | 监听 online / offline，断网横幅有文字 | 有：`test_ui_contract_list.py` 的 `test_offline_refresh_sends_nothing_and_keeps_the_banner`、`test_ui_contract_shell.py` 的 `test_banner_shows_only_the_highest_priority_one` | 不补（已有） |
| 14 | test_sleep_gap_uses_real_interval | 源码形状 | 睡眠阈值常量与基于真实心跳间隔的判定；不留模拟钩子 | 有：`test_ui_contract_shell.py` 的 `test_banner_shows_only_the_highest_priority_one`（睡眠横幅）、`test_ui_main_window_list.py` 的睡眠横幅行为用例 | 不补（已有） |
| 15 | test_responsive_breakpoints | 源码形状（样式表） | 1060 / 900 / 860 与矮窗口 720 四个断点，860 收起地点列并换短品牌名 | 无——沙箱不加载样式表、不算布局 | 不补（补不了） |
| 16 | test_error_result_has_action | 源码形状 | 失败结论带行动按钮（刷新列表 / 再试一次） | 无——`result-action` 只在源码断言里出现 | 不补（属结果页，不在登录块；见 plan_amendments） |
| 17 | test_check_event_carries_hint | 后端载荷 | check 事件的载荷里带可区分的 `hint` 分类 | 不适用（后端） | 不补 |
| 18 | test_relogin_swaps_anchor_without_reload | 行为 | 窗口内重新登录后 check 带回新锚点，不重载窗口 | — | — |
| 19 | test_pill_shows_last_check_not_remaining_time | 行为 | 胶囊写上次校验时刻，不写倒计时，时钟推进也不走字 | — | — |
| 20 | test_login_estimate_five_writings | 行为 | 详情卡五种估算写法各就各位，只作提示不参与失效判定 | — | — |
| 21 | test_repeated_check_does_not_renew_anchor | 行为 | 同一凭证重复 check 时锚点不随刷新漂移 | — | — |
| 22 | test_valid_at_zero_estimate_stays_valid | 行为 | 估算到点但学校 valid 仍是「已登录」，胶囊不露到期说法 | — | — |
| 23 | test_no_anchor_shows_unknown_not_fabricated | 行为 | 没有锚点时不编小时数，unknown 不显示成过期 | — | — |
| 24 | test_cancelled_relogin_restores_full_prior_login_state | 行为 | 取消重登把胶囊、副句、锚点、按钮整份回滚 | — | — |
| 25 | test_login_pending_never_paints_run_board | 行为 | 点登录期间大屏说「登录中」，不借忙碌说成正在准备报名 | — | — |
| 26 | test_logged_in_without_last_check_says_never_checked | 行为 | 有会话但没校验过：胶囊不编时刻，状态卡明说还没校验过 | — | — |
| 27 | test_failed_relogin_keeps_countdown_instead_of_invalid | 行为 | 失败重登保留旧结论与上次校验时刻，不画成失效 | — | — |
| 28 | test_cancelled_relogin_without_any_session_stays_logged_out | 行为 | 本来没有会话时取消重登仍是未登录 | — | — |
| 29 | test_successful_relogin_clears_old_anchor_then_adopts_new | 行为 | 成功重登先作废旧锚点与快照，再换新校验时刻 | — | — |
| 30 | test_old_round_check_cannot_override_restored_state | 行为 | 回滚后上一轮迟到的 check 不得改写结论 | — | — |
| 31 | test_sync_login_dependent_view_repaints_every_surface | 行为 | 统一收口确实重画胶囊、时钟、空态、大屏、路线、列表 | — | — |
| 32 | test_other_login_row_is_hedged | 照原型逐字的文案 | 登录详情卡「别处登录」只说「可能」，以实际登录状态为准 | 无——详情卡这一行没有行为用例 | 不补（文案本身的语气，行为侧没有等价可断言） |
| 33 | test_success_fires_one_refresh_and_replays_do_not | 行为 | 成功后只刷新一次、同 flow 重放不再刷、计划运行中不刷 | — | — |
| 34 | test_open_dialog_success_also_loads_the_list | 行为 | 对话框开着时成功同样立刻加载列表，并停在结果步 | — | — |
| 35 | test_relogin_success_without_flow_id_refreshes_only_once | 行为 | 无 flow_id 的成功快照视为同一事件只放行一次 | — | — |

## 汇总

- 35 条：跑 node 的行为用例 18 条；后端（载荷与行为）6 条；字面/源码形状 11 条。
- 11 条字面类里：已有跑 node 的用例守同一件事的 4 条（#6、#12、#13、#14）；本批补出行为用例的 2 条（#4、#8）；沙箱证不了的 2 条（#15 样式表、#16 结果页行动按钮的源码形状）；属文案或非登录块、没有行为等价可断言的 3 条（#5、#11 的检查条、#32）。
- 补出的两条都落在登录块能看见的结果上：胶囊的首次使用/失效文案（#4），以及登录结论决定开始按钮能不能点（#8）。
- 复跑命令（仓库根）：
  `python -B -m unittest discover -s local/tests -p "test_ui_contract_login.py" -v`
  `python -B -m unittest discover -s local/tests -p "test_ui_login_capsule.py" -v`
