# T3 三端规则比对（基线 7e2d31c）

- 审计日期：2026-11-12/13；审计执行：zcode（只读审计任务 T3）。
- 基线：提交 `7e2d31c`（fix(component): 导入装好后收掉旧的下载失败）。产品代码全部按基线读，未读工作区现行文件。
- 引用条目：106 条，见同目录 `rules.cites.jsonl`（id 前缀 r-）。md 内事实主张只写双方括号包裹的条目 id（形如 r-0xx），原文与行号以该文件为准。
- 三端定义（都在基线 `local/` 内）：
  - **后端** = local/ 的 Python（app.py、application/、infrastructure/、domain/、grab.py 等）；
  - **桌面** = local/ui/（不含 m/ 子目录）；
  - **手机** = local/ui/m/。
- 口径说明：
  - 每条规则先分端写「位置与行为」，再给差异分类（语义不同 / 文案不同 / 只是写法不同 / 一致），最后比对基线测试（local/tests、server/tests 内按测试名引用；找不到就写「无」并说明检索词）。
  - 「标签」指任务卡/状态格上的短结论，「说明文案」指任务卡说明行、日志、结果页里的长句；两用途分开比对。
  - 某端没有该规则时写「该端没有」，并给出检索位置与检索词。
  - 抽查记录见文末 spot_checks。

## 1. 登录是否失效的判定

### 后端
- 位置：`local/domain/login_rules.py`（check_result/check_hint/build_session_state）、`local/grab.py`（probe_token）、`local/application/login_service.py`（build_check_event）。
- 行为：check 结论是四态——只有学校接口真实成功才是 valid；本机无会话是 none；能认出的登录失效（4001/登录类字样且不含网络词）是 expired；网络类与认不出的失败一律 unknown，不得诱导重登 [[r-001]]。worker 侧登录探测同样只有学校明确回 4001 才判 expired，单次 4001 先隔 LOGIN_RECHECK_S（1.5 秒）复查一次 [[r-002]]；四态结论经 check 事件载荷的 `result` 字段下发界面 [[r-003]]。会话三态快照区分「从没登录过」（缺 token）与「登录过期」，缺 token 不报小时数 [[r-004]]。

### 桌面
- 位置：`local/ui/state/login.js`（reconcileAutoLogin/setLogin）、`local/ui/views/login.js`（paintLogin）、`local/ui/views/status-cards.js`。
- 行为：桌面不自行判定，只消费后端结论——「自动登录中」只在后端说电脑正在恢复或中继确有一场自动登录时亮着，结论 valid/已转人工/不是 expired 时收回 [[r-005]]；计划运行中胶囊平时保持「已登录」，但学校明确判失效（expired）时必须显示「登录已失效」，网络原因的 unknown 保持原样 [[r-006]]；状态卡四态标签为「登录有效/登录已失效/还没登录/暂时无法确认」[[r-007]]。

### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.loginRaw/loginExpired/loginRecovering/loginLine）。
- 行为：手机把「已失效」的原始口径定为 session_expired、快照明说没有会话（session_present===false）、或最近一次学校校验 last_check_state=expired 三者任一 [[r-008]]；电脑正在静默自动登录（未转人工）时不算失效，不出失效横幅 [[r-009]]；核对 sheet 的登录行按失效结论 × 自动登录配置组合出四种人话 [[r-010]]。

### 差异分类
- 后端↔桌面：**一致**。桌面完全沿用后端四态结论，不自行判定。
- 后端↔手机：**语义不同**（呈现聚合）。后端把「从没登录过（none）」与「网络/接口异常（unknown）」独立成态 [[r-001]]；手机没有独立 unknown 档，把「无会话」直接并入失效口径 [[r-008]]（unknown 类信息手机只能经 recovering/flow 收敛 [[r-009]]）。失效的根判据（学校 last_check_state=expired / session_expired）两端一致。
- 桌面↔手机：**语义不同**（同上），标签文案本身一致（「登录已失效」vs「电脑上的登录已失效」属同一句式）。

### 测试比对
- local/tests/test_login_probe.py::test_two_4001_is_expired、::test_4001_then_ok_is_valid、::test_4001_then_other_error_is_unknown（后端四态与复查）。
- local/tests/test_phone_ui.py::test_phone_has_no_expired_banner_while_the_computer_recovers、::test_login_expired_alert_and_bar_point_to_relogin、::test_login_line_four_states_follow_prototype（手机失效呈现）。
- server/tests/test_grab_signup_retry.py::test_login_keyword_without_code_4001_does_not_close、server/tests/test_login_resilience.py（服务器版同口径旁证：4001-only）。
- 桌面四态标签与手机聚合口径的差异无专门比对测试：**无**。

## 2. 立即报名还是预报名

### 后端
- 位置：`local/signup_plan.py`（classify_signup_mode、TaskSpec）、`local/domain/plan_rules.py`（closed_items_error）。
- 行为：按报名窗口分三种执行模式——sign_end 已过=closed、sign_start 在未来=pre_register（预报名）、其余（含 sign_end 缺失）=instant_signup（立即报名/抢名额）；举办时间不参与分类 [[r-011]]。模式在计划接纳时定格进 TaskSpec 快照，预报名带 lead_s=100 秒提前准备窗口 [[r-012]]；后端最终门禁里已截止活动不能进 worker，pre_register 与 instant_signup 是两个正式模式、混合计划可共存、逐场按各自模式运行 [[r-013]]。

### 桌面
- 位置：`local/ui/state/labels.js`（modeOf/modeText）、`local/ui/views/list.js`（行内模式旗标）。
- 行为：modeOf 用与后端同一判定式复算三态，未校准（无可信北京时间）时返回 unknown，并注明后端仍是最终权威 [[r-014]]；模式标签文案「预报名/立即报名/已截止」[[r-015]]；活动行在等待/开放中状态显示自己的执行模式旗标 [[r-016]]。

### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.stOf/rowView/planSummary）。
- 行为：开放状态按 signed→closed→open→pre→unknown 判定，注释自称与电脑 classify_signup_mode 同口径；时钟不可用时分辨不出 open/closed，呈现「待校准」 [[r-017]]；行旗标 open=「立即报名」、pre=「预报名」（最早一场标「下一场」）、signed=「已报名」、closed=「已截止」 [[r-018]]；底栏按 open<=now 数出「N 场立即报名」「N 场预报名」 [[r-019]]。

### 差异分类
- 三端**语义一致**（同一判定式：sign_end 已过→截止、sign_start 未来→预报名、其余→立即报名；举办时间都不参与）。
- **只是写法不同**：手机把 instant_signup/pre_register 表达成 open/pre 两态 [[r-017]]；桌面未校准返回 unknown 档 [[r-014]]，手机未校准呈现「待校准」并在时钟不可用时不判 open/closed [[r-017]]。
- **文案一致**：预报名/立即报名/已截止三词三端同名（[[r-015]] vs [[r-018]]）。
- 模式定格时机：后端在接纳时定格 [[r-012]]，两端展示侧每帧按业务时钟现算——**只是写法不同**（桌面注释明说后端最终权威 [[r-014]]）。
- 呈现面（T7 依 AA2-6 补做）：桌面确认弹层「N 场预报名等开放 / N 场立即报名马上执行」[[r-104]]、草稿副行「X 场立即报名，Y 场预报名等开放」（为 0 的一半不写）[[r-105]]；手机底栏 planSummary「N 场立即报名 / N 场预报名」。桌面↔手机计数控**文案不同**（「马上执行」「等开放」的有无）。

### 测试比对
- local/tests/test_signup_plan.py::test_three_modes_table_driven、::test_task_spec_carries_signup_mode、::test_cached_closed_beats_stale_frontend_end。
- local/tests/test_ui_contract.py::test_mode_of_and_mode_texts、::test_start_plan_payload_carries_sign_end_and_mode、::test_task_card_shows_signup_mode。
- local/tests/test_phone_ui.py::test_groups_counts_flags_and_nowline_follow_prototype。
- 三端差异（open/pre 与 instant/pre_register 命名映射）无专门比对测试：**无**。

## 3. 时间重叠（举办时段冲突）判定

### 后端
- 位置：`local/signup_plan.py`（intervals_overlap/validate_plan）、`local/domain/plan_rules.py`（check_conflicts）。
- 行为：半开区间比较，首尾相接不算冲突 [[r-020]]；已报名活动占用的举办时段是冲突基线，只算「外部已占用」时段 [[r-021]]；选中活动与该基线逐场做半开区间比较 [[r-022]]；已报名活动缺举办时段时单独报 signed_activity_time_unknown 保守阻止（validate_plan，见 [[r-081]] 的桌面同款）。

### 桌面
- 位置：`local/ui/state/filters.js`（validateSelection/signedClash）。
- 行为：同一规则——已报名是外部占用，只按举办时段 act_start/act_end 比较，报名开放时间不参与 [[r-023]]；signedClash 用同一套半开区间比较找出与已报名重叠的那一场，时刻表据此直接禁选 [[r-024]]；已报名活动缺举办时段时保守阻止，不静默放行 [[r-081]]。

### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.signedClash/overlapFirst/conflictNotice/pickItem）。
- 行为：signedClash 与电脑同一半开区间规则；已报名、已截止的行本身不算，「没有完整举办时段的行无从判断，不算」[[r-025]]；与已选场的重叠用 overlapFirst（半开区间同 signedClash），勾选撞上已选场时保留原选择并回提示「…活动时间重叠，只能选其中一场。已保留原选择。」[[r-026]]。

### 差异分类
- 半开区间与「已报名=外部占用」口径：三端**一致**（[[r-020]][[r-023]][[r-025]]）。
- 已报名活动缺举办时段：后端与桌面**保守阻止**（[[r-021]]、[[r-081]]），手机**不算冲突、不阻止**（[[r-025]]「无从判断，不算」）→ **语义不同**。
- 提示形态：桌面时刻表直接禁选并在气泡里给解除路径（四选一），手机勾选时保留原选择+一句提示（[[r-026]]）→ **只是写法不同**（同为半开区间、同为只提示不代提交）。

### 测试比对
- local/tests/test_signup_plan.py::test_touching_boundaries_do_not_overlap、::test_selected_overlapping_signed_activity_is_rejected、::test_touching_boundaries_are_not_overlap。
- local/tests/test_ui_conflict_cancel.py::test_clash_row_is_disabled_with_a_bare_tag。
- local/tests/test_phone_conflict.py::test_signed_clash_uses_a_half_open_interval_like_the_desktop、::test_clash_row_is_disabled_and_tap_toggles_the_reason。
- 手机「已报名活动缺举办时段不算冲突」的对照测试：**无**（检索词 clash/actRange/act_start 于 test_phone_conflict.py、test_phone_ui.py，无此差异用例）。

## 4. 报名结束原因的标签与说明文案

### 后端
- 位置：`local/domain/signup_reply.py`（PHRASE_TABLE/STOP_REASON_LABELS）、`local/domain/retry_rules.py`（retry_payload）、`local/domain/plan_rules.py`（classify_task_stop）。
- 行为（标签）：回包按关键短语归 kind 并给界面短结论 label（报名还没开始/名额已满/时间冲突/报名已截止/版本不兼容/请求已超时/活动不存在）[[r-027]]；基础三标签为「报名成功/登录失效/学校回了无法识别的结果」[[r-028]]；按 stop_reason 给新增终态的界面短结论表（full=名额已满、closed=报名已截止、conflict=时间冲突、no_activity=活动不存在、clock_skew=本机时钟不准、unknown_reply=学校回了无法识别的结果、page_unavailable=学校页面打不开）[[r-029]]；这些短结论随任务载荷以 outcome_label 下发，旧终态不带该键 [[r-030]]。
- 行为（说明文案）：停止时已发出提交但无确定回应的终态说明是「两层事实」句，不说「没抢到」 [[r-031]]。

### 桌面
- 位置：`local/ui/state/task-display.js`（taskDisplayLabel）、`local/ui/state/labels.js`（taskLabel）、`local/ui/views/plan-panel.js`（stopReasonText/taskHtml/resultCounts）。
- 行为（标签）：失败任务先判刷新核对确认过→「报名成功」，再判错过→「错过了」，unconfirmed→「待核对」、auth_unavailable→「未提交」（代码独有）、full→「名额已满」 [[r-032]]；任务状态动词表 queued=排队、waiting=等待开放、submitting=提交中、success=报名成功、already_signed=已报名、failed=报名未成功、canceled=已取消、missed=错过了（后端没有 missed，由前端推导） [[r-033]]。
- 行为（说明文案）：按 stop_reason 的兜底同义词表，注明后端 outcome_label 优先 [[r-034]]；unconfirmed 终态的长句「已提交 N 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动页看一眼，或稍后刷新核对。工具不会再自动重发。」 [[r-035]]；结果页统计标签「已报名/名额已满/报名未成功/错过了/待核对/已取消」 [[r-036]]。
- 消费面（T7 返修补）：结果页大数字 resultCounts 的口径声明——「报名未成功」含 auth_unavailable（没提交）、pending 即「待核对」、错过了在 failed 之前拦下防双重计数 [[r-100]]；归并逻辑里 auth_unavailable 落进 bad（failed else 分支） [[r-101]]。计划级结论 planOutcome 则按 stop_reason 单列：unconfirmed 与 auth_unavailable 各自独立计数、unknown=两者之和，任务卡、总结、大屏和 LED 共用这一份 [[r-097]][[r-098]]；unknownLabel 对两种未知并存说「需确认」、单独时说「待核对/未提交」，不把没提交的混进「待核对」 [[r-099]]。单场终态消费点：showTaskResult 对 unconfirmed 只给次数与「刷新列表」动作、不说没抢到 [[r-102]]；对 auth_unavailable 说「暂时无法验证登录状态」且不跳「重新登录」 [[r-103]]。

### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.taskCard/taskText）。
- 行为（标签）：任务卡 map——waiting 按 mode 分「等待开放/准备报名」、submitting=「提交中」、success 与 already_signed 都显示「报名成功」、failed 按 stop_reason 分「名额已满/待核对/报名未成功」、canceled=「已取消」 [[r-037]]。
- 行为（说明文案）：终态说明句与桌面同源（原型 RS02 三句：名额已满句、unconfirmed 句、成功句） [[r-038]]；taskText 给 success/already_signed→「已报名」，full/unconfirmed 有专句，其余失败拼 outcome_label [[r-039]]。

### 差异分类
- 标签（新增终态键值）：后端 outcome_label 与桌面兜底表 **一致**（[[r-029]] vs [[r-034]]，键值同名同义）。
- already_signed 标签：桌面「已报名」 [[r-033]]，手机任务卡「报名成功」 [[r-037]]，手机 taskText 又是「已报名」 [[r-039]] → **文案不同**（且手机内部两处不一致）。
- 「错过了」（missed）：桌面独有推导态标签（[[r-032]][[r-033]]），手机任务卡没有该档（[[r-037]] map 无 missed） → **语义不同**（桌面多一档「确定没提交的红标」呈现）。
- unconfirmed 的说明长句：后端 reason、桌面 taskHtml、手机 taskCard 逐字同源（[[r-031]][[r-035]][[r-038]][[r-039]]） → **一致**。
- auth_unavailable 标签「未提交」为桌面代码独有（[[r-032]] 注释明说），手机无此档（[[r-037]]） → **语义不同**（呈现档位不同）。
- 双计数口径（T7 返修补）：同一批任务两套桌面计数——resultCounts 把 auth_unavailable 并进「报名未成功」 [[r-100]][[r-101]]，planOutcome 单列并合成 unknown（[[r-097]][[r-098]]）；这是同一端内**有意的双口径**（结果页大数字 vs 任务数/总结/大屏），不是矛盾：planOutcome 注释明说「对用户这是两种不同的事实」 [[r-097]]。单场终态消费点 showTaskResult 与 planOutcome 的单列口径一致（[[r-102]][[r-103]]）→ **一致**（端内双口径，端间无冲突）。

### 测试比对
- local/tests/test_signup_reply.py::test_every_terminal_kind_has_a_label、::test_old_stop_reasons_have_no_label、::test_retry_payload_carries_outcome_label_only_for_new_reasons（后端标签契约）。
- local/tests/test_phone_ui.py::test_task_card_follows_prototype_detail_priority、::test_task_lines_use_the_computer_vocabulary、::test_result_view_counts_and_heads_follow_prototype。
- local/tests/test_ui_contract.py::test_app_js_renders_attempts_and_stop_reason（桌面 attempts/stop_reason 渲染）。
- already_signed 桌面「已报名」vs 手机「报名成功」的差异比对测试：**无**。
- local/tests/test_ui_main_window_plan.py::test_missed_is_counted_apart_and_never_double_counted、::test_missed_never_makes_a_plan_look_fully_successful、::test_without_a_sleep_window_nothing_is_missed；local/tests/test_ui_contract.py::test_full_is_counted_apart_and_never_reselected（resultCounts 归并与单列）。
- local/tests/test_ui_reliability.py::test_unconfirmed_is_pending_not_failure、::test_auth_unavailable_does_not_push_relogin（单场终态消费面行为）。
- planOutcome/unknownLabel 的直接单测：**无**（检索 unknownLabel/planOutcome 于 local/tests，无以它们为对象的用例；test_ui_contract.py:1762 的 unknownLabel 是时钟不确定度变量的同名巧合）。

## 5. 列表分组与排序

### 后端
- 位置：`local/grab.py`（list 的 rank/rows.sort）。
- 行为：rank——未开放排最前、其次开放中、已报名垫底；时钟不可用时未开放与开放中同档 [[r-040]]；排序键 rank、sign_start 文本、name [[r-041]]。后端不做「组」概念，只给一个扁平序。

### 桌面
- 位置：`local/ui/views/list.js`（groupTimetable/groupHtml）、`local/ui/views/selection.js`（paintChips）。
- 行为：按天分组的车站时刻表，组序为正在开放→「现在」线→按天→待公布→已报名→已截止，已报名在已截止前 [[r-042]]；组内按 sign_start 升序、并列按中文名 localeCompare 排序；组旁注「正在开放=现在就能报」「已截止=只能查看」 [[r-043]]；状态胶囊可报名排除已截止、已报名单独计，时钟不可用时计数显示「待确认」而不出伪 0 [[r-044]]。

### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.bucketOf/groupKeyOf/listView/visibleItems）。
- 行为：顶栏分区 24 小时内开放算「今天」、已报名折成 signed、缺开放时间按快照 closed 折叠 [[r-045]]；分组键「已报名/正在开放/已截止/待公布 + 今天/明天/后天/更晚开放」，按北京时间日历日与业务此刻比对，时钟不可用时可退手机墙钟（只影响归组） [[r-046]]；组序固定为数组 titles，组内行由 visible 过滤直接映射、不再排序（沿用电脑下发顺序） [[r-047]]；组旁注与桌面同词 [[r-048]]；段钮「可报名」=open/pre 两态 [[r-049]]。

### 差异分类
- 分组类别与组序：**一致**（开放在最前、已报名在已截止前、待公布在日期组之后；[[r-042]] vs [[r-047]]）。手机多一个「更晚开放」组名、桌面用按天分组容纳更晚日期 → **只是写法不同**。
- 组内排序：桌面自行按 sign_start+中文名排序 [[r-043]]；手机不再排序，沿用电脑下发顺序 [[r-047]]，而电脑下发顺序是后端 rank（未开放在前、开放中次之 [[r-040]]） → **语义不同**（同一组内同时含已开放与未开放行时，手机可能把未开放排前，桌面按开放时刻排；影响很小但口径确实不同）。
- 「可报名」口径：桌面排除已截止（时钟不可用显示待确认） [[r-044]]，手机 open/pre 两态 [[r-049]] → **一致**。

### 测试比对
- local/tests/test_ui_contract.py::test_group_timetable_places_each_activity_in_its_correct_group。
- local/tests/test_ui_main_window_list.py::test_groups_run_unknown_then_signed_then_closed。
- local/tests/test_phone_ui.py::test_groups_counts_flags_and_nowline_follow_prototype、::test_signed_groups_render_in_main_list_and_summary_only_in_result、::test_bucket_uses_beijing_sign_start_without_open_ts。
- 后端 grab 列表 rank/排序的专门测试：**无**（检索 rank/sort/9999 于 local/tests，无直接用例）。
- 三端组内排序差异（桌面重排 vs 手机沿用后端序）无比对测试：**无**。

## 6. 批次说明

### 后端
- 位置：`local/signup_plan.py`（group_by_sign_start）。
- 行为：按完整报名开放时间分组、从早到晚并发执行，批次本身没有用户可见文案 [[r-050]]；预报名批次带 100 秒提前准备窗口 [[r-012]]。
- 批次头呈现（T7 依 AA2-6 补做）：桌面批次头「立即报名 N 场」「预报名，同时提交 N 场 / 预报名 1 场」，已开放批写「现在」[[r-106]]；与手机「这一批 N 场同时提交」句式属**文案不同**。

### 桌面
- 位置：`local/ui/views/plan-panel.js`（paintTickets/runCaption）。
- 行为：草稿票区批次头「已开放写『现在』、预报名写时刻」，数量注「立即报名 N 场 / 预报名，同时提交 N 场 / 预报名 1 场」 [[r-051]]；运行中等待态批次句「这一批 N 场同时提交，到点自动开始。」 [[r-052]]。

### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.reviewBatches、运行板 board）。
- 行为：核对批次照原型 batchMap——已开放（st=open）同归「现在」批、其余按开放时刻分批 [[r-053]]；数量注与桌面 paintTickets 逐字同文案 [[r-054]]；运行板副题「这一批 N 场同时提交，到点自动开始。」与桌面 runCaption 同句，另有「即将开放」（gap≤5）分档 [[r-055]]。

### 差异分类
- 数量注与运行中批次句文案：桌面与手机**一致**（[[r-051]] vs [[r-054]]、[[r-052]] vs [[r-055]]）。
- 批次键：桌面草稿按 sign_start 文本分组（同 sign_start 一批 [[r-051]]），手机把所有已开放合并成「现在」批、其余按开放时刻分批 [[r-053]] → **语义不同**（多个不同时刻的已开放场次：手机合成一批「现在」，桌面按各自 sign_start 分多批）。
- 手机「即将开放」档（gap≤5）桌面无对应词（桌面 tag 是「开放中/下一场」） → **文案不同**（轻微）。

### 测试比对
- local/tests/test_signup_plan.py::test_same_open_non_overlapping_can_share_batch（批次并发分组）。
- local/tests/test_phone_ui.py::test_review_batches_follow_prototype_batch_map、::test_run_board_waiting_led_thresholds_and_batch_copy。
- local/tests/test_ui_contract.py::test_run_submitting_single_caption_and_cancel_label（提交态单场副题，部分覆盖）。
- 桌面「这一批 N 场同时提交」等待态批次句无专门用例：**无**。

## 7. 北京时间与倒计时显示

### 后端
- 位置：`local/time_contract.py`、`local/business_clock.py`。
- 行为：学校时间永远按 UTC+8 解释，非法日历日期一律判不可用、绝不滚到别的日期 [[r-056]]；解析只接受严格的 `YYYY-MM-DD HH:MM:SS`，非法返回 None 并要求界面显示「时间待确认」 [[r-057]]；业务时刻=网络授时锚点+应用内经过时长，绝不回退系统墙钟，holdover 超 900 秒或超阈值转 unavailable [[r-058]]。

### 桌面
- 位置：`local/ui/state/time.js`（SCHOOL_TZ/toTs/fmt/durText）。
- 行为：学校时间用 Asia/Shanghai 时区换算与格式化 [[r-059]]；toTs 用 Date.UTC 算再逐字段回验，非法返回 null（R14：不替用户编一个不存在的报名时间） [[r-060]]；倒计时格式跨天「N天 HH:MM」、否则「HH:MM:SS」 [[r-061]]；行内距开放「N 天 N 时 / N 时 N 分 / N 分 N 秒」 [[r-062]]。

### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.businessNowS/leftCn/hhmmss）。
- 行为：businessNowS 用电脑快照锚点+单调推进，超 900 秒不可信返回 null（与后端 holdover 上限同值） [[r-063]]；距开放文案 ≥10 小时取整小时「N 小时后」、不足 1 小时带秒 [[r-064]]；整页口径「时刻与倒计时只用 businessNowS、不读手机墙钟；分组的日历日时钟不可用时退墙钟，但不产生任何倒计时」 [[r-065]]。

### 重试截止倒计时（T7 返修补）

#### 后端
- 位置：`local/domain/retry_window.py`（resolve_window/_cut）。
- 行为：重试窗口三模式由 retry_for_s 区分——正数=显式硬时长（sign_end 更早时截断）、0=直到报名截止（缺截止回退 120 秒）、ADAPTIVE_RETRY(-1)=自动延长（初始 120、逐次增长、上限 anchor+1500 秒且受 sign_end 硬截）；非法值兜底后只有 -1 改变含义 [[r-085]]；常量 120/1500/-1，自动延长上限「起点起 25 分钟」且 sign_end 仍硬截 [[r-086]]；resolve_window 返回 (初始绝对截止, 约束来源)，anchor 由调用方冻结、函数不读此刻 [[r-087]]；分发与 _cut——sign_end 是绝对硬上限，任何模式的截止都不许越过，-1 初始预算就是 120 秒 [[r-088]]。

#### 桌面
- 位置：`local/ui/views/plan-panel.js`（effectiveRetryDeadline/submittingDetail/routeDeadline）。
- 行为：统一截止函数 telemetry 优先（合法扩窗后的权威截止从后端回包接管），-1 初始按 120 算、只有 0 直达 sign_end [[r-089]]；冻结起点 retry_started_at 最权威、sign_end 用 Math.min 截断，无任何参考点返回 null 不冒充 0 秒 [[r-090]]；提交中任务卡「已提交 N 次（上限 M 次）…重试到 HH:MM:SS」，截止未知写「等待提交结果」不编 0 秒 [[r-091]]；路线/LED「本次尝试截止」与任务卡同一来源，长策略不再显示成 120 秒 [[r-092]]。

#### 手机
- 位置：`local/ui/m/app.js`（PhoneModel.taskDeadline 及其两处消费）。
- 行为：taskDeadline 只读快照——telemetry（retry_deadline）优先，RETRY_FALLBACK_S=120，-1 初始 120、0 直达 sign_end [[r-093]]；无锚点返回 null、sign_end 用 Math.min 硬截 [[r-094]]；消费点一：运行板提交中 LED「本次尝试到」 [[r-095]]；消费点二：任务卡提交中说明「…重试到 …」 [[r-096]]。

### 差异分类
- 时间语义：三端**一致**（业务北京时间；不读本机墙钟；非法时间不编造，[[r-056]][[r-059]][[r-065]]）。
- 倒计时/时长文案：桌面「HH:MM:SS / N天 HH:MM / N 天 N 时」 [[r-061]][[r-062]]，手机「N 小时后 / N 时 N 分 / N 分 N 秒 / HH:MM:SS（cap 99 小时）」 [[r-064]] → **文案不同**（同一含义不同措辞；手机照原型、桌面也照原型，两份原型写法不同）。
- 900 秒 holdover 上限：后端与手机同值（[[r-058]][[r-063]]），桌面端无独立实现（由后端时钟状态驱动） → **一致**（同源）。
- 重试截止倒计时（T7 返修补）：算式三端同源——后端三模式（[[r-085]][[r-086]][[r-088]]）、桌面投影（[[r-089]][[r-090]]）与手机只读投影（[[r-093]][[r-094]]）同为「telemetry 优先 → 0 直达 sign_end → -1 初始 120 → sign_end 硬截」 → **一致**；两端的「无参考点返回 null」兜底也一致（[[r-090]] vs [[r-094]]）。文案：任务卡句桌面「重试到 HH:MM:SS」 [[r-091]] 与手机「重试到 …」 [[r-096]] 同式；LED cap 名桌面「本次尝试截止」 [[r-092]] vs 手机「本次尝试到」 [[r-095]] → **文案不同**（一词之差）。

### 测试比对
- local/tests/test_time_contract.py::test_school_time_is_utc_plus_eight、::test_js_same_epoch_in_every_time_zone、::test_js_and_python_agree（JS 与 Python 同 epoch 跨时区一致）。
- local/tests/test_phone_ui.py::test_row_left_countdown_soon_and_clock_down、::test_bucket_uses_beijing_sign_start_without_open_ts。
- local/tests/test_business_clock.py（锚点/holdover/unavailable，文件级覆盖）。
- local/tests/test_retry_policy.py::test_deadline_never_passes_sign_end、::test_fallback_never_runs_forever、::test_long_policy_truncated_by_sign_end、::test_until_sign_end_policy_uses_sign_end、::test_sign_end_truncation_and_fallback_unchanged（后端三模式与 sign_end 硬截）。
- local/tests/test_ui_contract.py::test_unified_effective_retry_deadline、::test_anchor_is_stable_across_open（桌面统一截止与锚点稳定）。
- local/tests/test_phone_ui.py::test_deadline_projection_prefers_telemetry_and_three_modes（手机三模式投影）。
- 桌面与手机倒计时文案差异无比对测试：**无**（各测各的原型口径）。

## 8. 组件与下载失败原因

### 后端
- 位置：`local/domain/login_rules.py`（component_error）、`local/application/advanced_component_service.py`。
- 行为：worker 进程创建失败归成 worker_missing/worker_permission/spawn_failed 三码；只归进程启动阶段的 OS 层失败，数据/解析异常不得诱导重新下载 [[r-066]]；组件下载失败分类——资产 404 报 not_published（清单列了组件、文件却没传），不说成网络问题 [[r-067]]；组件状态文案表 failed=「下载或安装没有成功」、cancelled=「已取消下载，现有组件没有被改动」、missing=「组件包未安装」 [[r-068]]。

### 桌面
- 位置：`local/ui/controllers/refresh.js`（RUNTIME_ERRORS）、`local/ui/views/update.js`。
- 行为：把三码翻成横幅标题与提示——「程序组件缺失/程序组件无法读取/程序组件启动失败」，各配恢复指引 [[r-069]]；更新包哈希校验失败有专句「下载内容的哈希校验没通过，已放弃并删掉临时文件。旧版本和你的数据都没动。」，其余 error_code 照旧显示后端 text [[r-070]]。

### 手机
- **该端没有**。检索说明：在基线 local/ui/m/app.js 全文 grep「组件 / 下载 / 更新 / update / component / 安装」，只命中离线提示（「电脑那边连不上学校站点，现在显示的是缓存列表」）与会话令牌刷新提示，没有组件安装、更新或下载失败界面；手机页是电脑的受限只读投影，组件与更新是电脑端功能。

### 差异分类
- 错误码键集：后端与桌面 **一致**（三码同名，test_reason_maps 有契约测试）。
- 文案：桌面标题+hint 比后端错误码更详细（如 worker_permission 提示「解除锁定」步骤） → **文案不同**（同码更详尽，语义一致）。
- 手机：该端没有，无从比对。

### 测试比对
- local/tests/test_reason_maps.py::test_python_and_js_reason_maps_share_keys、::test_not_published_reason_is_in_both_maps（Python/JS 键一致契约）。
- local/tests/test_advanced_features.py::test_outdated_component_is_not_reported_as_failed、::test_busy_without_cache_reports_checking_not_failed。
- local/tests/test_update_check.py::test_download_hash_failure_goes_to_failed。
- 手机：**无**（该端没有）。

## 9. 核对计划弹层内容

### 后端
- **该端没有弹层**（无 UI）。后端在链路里承担的是门禁与文案来源：已截止不能进 worker、两个正式模式可共存 [[r-013]]；非冲突类失败的外层文案逐字复用前端 PLAN_ERROR_TEXT（不发明新句子，前端逐 kind 文案表见 [[r-072]]） [[r-071]]。

### 桌面
- **没有独立「核对计划」弹层**。检索说明：在基线 local/ui/{views,controllers} grep「核对 / dialog / modal / 弹层 / 确认计划」，`<dialog>` 只有帮助与条款（views/help.js、views/terms.js），另有停止确认遮罩（plan-panel.js 内 stopAsk，计划结束收起）；「开始前核对」由计划面板草稿区承担——冲突与选择提醒呈现在 `#plan-conflicts` 框 [[r-073]]、尝试概括行「尝试 N，最多 N 次」 [[r-074]]、开始按钮被门禁挡住时给「还差一步：…」提示条 [[r-075]]、草稿票区按批次分组（[[r-051]]）。

### 手机
- 位置：`local/ui/m/app.js`（SHEET_TITLES/renderReview/preStartWarnings/loginLine）。
- 行为：有独立「核对计划」sheet（SHEET_TITLES.review） [[r-076]]；内容=批次条目+移除钮（[[r-053]][[r-054]]）+开始前提醒列表（有提醒时主钮变「仍然开始报名计划」） [[r-077]]；提醒关键句——等待久「电脑上没装验证码识别/没开自动登录…中途登录失效要你输验证码/重新登录；开放前 100 秒内失效，那场就结束」「有场次在 24 小时后才开放，电脑要开着、不能睡眠」 [[r-078]]；提醒只提醒不拦、三支句式照原型，holdover 句是电脑端补入（记 deviation） [[r-079]]；登录行四态照原型 loginLine [[r-080]]。

### 差异分类
- 形态：桌面无弹层（计划面板草稿区承担）、手机有独立 sheet → **语义不同**（开始前确认的载体不同；两者的批次条目内容一致，见规则 6）。
- 开始前提醒：手机有逐句提醒清单（缺截止 2 分钟/等待久输验证码/24 小时/holdover，[[r-078]][[r-079]]）；桌面无对应清单，同类风险由门禁（planLate 100 秒窗口、后端 closed 门禁 [[r-013]]）与「还差一步」提示条 [[r-075]]承担 → **语义不同**（提醒覆盖面不同：手机更前置、更成体系）。
- 冲突呈现：桌面 plan-conflicts 逐条列出（[[r-073]]），手机勾选即拦+核对页批次呈现（[[r-026]]） → **只是写法不同**。

### 测试比对
- local/tests/test_phone_ui.py::test_review_lists_the_plan_and_the_same_reminders、::test_review_batches_follow_prototype_batch_map、::test_review_remove_toggles_off_and_closes_when_empty。
- local/tests/test_signup_plan.py::test_real_conflict_keeps_conflict_copy、::test_mixed_overlap_takes_priority（后端冲突文案契约，核对弹层文案的来源）。
- 桌面「无独立核对弹层」的形态无对应测试：**无**；桌面与手机开始前提醒覆盖面差异无比对测试：**无**。

## 差异汇总表

| # | 规则 | 后端 | 桌面 | 手机 | 分类 | 关键差异 |
|---|---|---|---|---|---|---|
| 1 | 登录失效判定 | 四态 valid/expired/none/unknown，4001 复查 [[r-001]][[r-002]] | 只消费结论 [[r-005]][[r-006]][[r-007]] | 三源归一判失效 [[r-008]][[r-009]] | 语义不同（桌面↔手机） | 手机把无会话并入失效、无 unknown 独立档 |
| 2 | 立即/预报名 | 三态分类+接纳时定格 [[r-011]][[r-012]] | 同式复算 [[r-014]][[r-015]] | open/pre 表达 [[r-017]][[r-018]] | 一致（写法不同） | 同一判定式；文案同名 |
| 3 | 时间重叠 | 半开区间+已报名基线+保守拦截 [[r-020]][[r-021]][[r-022]] | 同规则+保守拦截 [[r-023]][[r-024]][[r-081]] | 同规则、缺时段不算 [[r-025]][[r-026]] | 语义不同（一处） | 手机对已报名缺举办时段不保守拦截 |
| 4 | 结束原因标签/说明 | label+outcome_label+两层事实句 [[r-027]][[r-029]][[r-030]][[r-031]] | 兜底表+待核对/未提交/错过了 [[r-032]][[r-033]][[r-034]][[r-035]][[r-036]]；消费面双计数 resultCounts 并入 [[r-100]][[r-101]] / planOutcome 单列 [[r-097]][[r-098]][[r-099]] | 任务卡 map+taskText [[r-037]][[r-038]][[r-039]] | 文案不同 | already_signed 桌面「已报名」vs 手机「报名成功」；missed/未提交档桌面独有；桌面双计数口径（结果页并入、计划级单列） |
| 5 | 列表分组排序 | rank 扁平序 [[r-040]][[r-041]] | 按天分组+组内重排 [[r-042]][[r-043]] | 日历日分组+沿用后端序 [[r-046]][[r-047]] | 语义不同（组内排序）+写法不同 | 手机不重排、沿用后端 rank 序 |
| 6 | 批次说明 | 按 sign_start 分批 [[r-050]] | 批次头+数量注+批次句 [[r-051]][[r-052]] | 同文案；已开放合一批 [[r-053]][[r-054]][[r-055]] | 文案一致；批次键语义不同 | 手机把所有已开放合并「现在」批 |
| 7 | 北京时间与倒计时 | UTC+8 契约+业务时钟+重试窗口三模式 [[r-056]][[r-057]][[r-085]][[r-086]] | Asia/Shanghai+逐字段回验+effectiveRetryDeadline [[r-059]][[r-060]][[r-089]][[r-091]] | businessNowS+900 秒上限+taskDeadline [[r-063]][[r-064]][[r-093]][[r-095]] | 一致；文案不同 | 倒计时措辞两套；重试截止算式三端同源，LED cap「截止/到」一词之差 |
| 8 | 组件/下载失败 | 三码+not_published+状态文案 [[r-066]][[r-067]][[r-068]] | 同码横幅+哈希专句 [[r-069]][[r-070]] | 该端没有 | 一致（文案更详） | 手机无组件/更新界面 |
| 9 | 核对计划弹层 | 无弹层；门禁+复用前端文案 [[r-013]][[r-071]] | 无弹层；面板草稿区承担 [[r-073]][[r-074]][[r-075]] | 独立「核对计划」sheet+提醒清单 [[r-076]][[r-077]][[r-078]][[r-079]][[r-080]] | 语义不同 | 手机开始前提醒更成体系；桌面无弹层 |

## spot_checks

抽查方法：从 `git show 7e2d31c:<file>` 重新取原文（独立于生成时用的 git archive 基线树），与 jsonl 里声明的 start..end 行段逐字比对，并回看上下文确认语义。日期：2026-11-13。复现命令：`python` 读取 rules.cites.jsonl 后逐条 `git show 7e2d31c:<file>` 比对（本次抽查脚本为一次性 stdin 执行，未落盘）。

抽样 14 条，全部逐字命中、全文唯一、行号与声明一致：

- r-001（local/domain/login_rules.py 201-211）：check_result 四态与 unknown 兜底，语义与 claim 相符。
- r-008（local/ui/m/app.js 133-139）：手机 loginRaw 三源判失效，相符。
- r-011（local/signup_plan.py 60-65）：classify_signup_mode 三态注释与实现，相符。
- r-017（local/ui/m/app.js 544-558）：手机 stOf 五态与「待校准」，相符。
- r-020（local/signup_plan.py 77-80）：半开区间、首尾相接不算，相符。
- r-027（local/domain/signup_reply.py 33-43）：PHRASE_TABLE 七行（含证据注释），相符。
- r-032（local/ui/state/task-display.js 56-66）：桌面失败标签分派次序，相符。
- r-037（local/ui/m/app.js 886-896）：手机任务卡 map（already_signed→「报名成功」），相符——与桌面「已报名」的差异成立。
- r-040（local/grab.py 1403-1412）：rank 三档与时钟不可用同档，相符。
- r-046（local/ui/m/app.js 559-572）：手机 groupKeyOf 八组键，相符。
- r-051（local/ui/views/plan-panel.js 472-478）：桌面批次头与数量注，相符。
- r-058（local/business_clock.py 3-13）：业务时钟设计要点与 900 秒上限，相符。
- r-066（local/domain/login_rules.py 61-71）：component_error 三码与「数据坏了不是组件坏了」，相符。
- r-073（local/ui/views/plan-panel.js 729-736）：plan-conflicts 框渲染选择提醒/错误/冲突，相符。

结论：14/14 通过，未发现摘录失真或断章取义。

T7 返修补做后追加抽查（2026-11-13）：对新增条目抽样 10 条（r-085、r-086、r-088、r-089、r-091、r-093、r-096、r-098、r-100、r-103），同样以 `git show 7e2d31c:<file>` 重取原文逐字比对，10/10 命中、全文唯一、行号与声明一致；语义回看确认——retry_window 三模式与 sign_end 硬截（r-085/r-086/r-088）、桌面 effectiveRetryDeadline 的 telemetry 优先与 -1/0 语义（r-089）、提交中「重试到 HH:MM:SS」（r-091）、手机 taskDeadline 三模式（r-093）、任务卡「重试到」（r-096）、planOutcome 单列（r-098）、resultCounts 并入口径（r-100）、showTaskResult auth_unavailable 不跳重登（r-103）均与 claim 相符。结论：10/10 通过。

## 未尽事项

1. 引用条目聚焦九条规则的主链路；同一规则在 help/tour/设置页的次要文案（如 led.js、views/help.js）未逐条引用。
2. 手机端快照字段 `item.closed` 的产生链路（电脑下发时如何计算）未追溯到具体行，仅按手机侧用法（[[r-017]][[r-045]]）描述。
3. 「批次键差异」（桌面按 sign_start 文本 vs 手机已开放合并「现在」批）的后续影响（运行中计数口径）未展开验证，属于推测级观察，未单列引用。
4. 桌面 stopReasonText 表的后半段（conflict/no_activity/clock_skew/unknown_reply/page_unavailable 五键）在 r-034 截取范围之外，未单独引用；其与后端 STOP_REASON_LABELS 的一致性由 test_reason_maps.py 契约测试间接覆盖。
5. server/tests 只作为同口径旁证引用（规则 1）；服务器版本身不在本次三端定义内，未单独比对。
6. 本次未运行任何测试与构建（只读审计约束），测试名为静态检索所得，未实际执行验证其当前为绿。

## 主执行方复核抽查（2026-11-12，基线 7e2d31c）

随机抽样 10 条（种子 20261112，12.3%），逐条重读基线核对原文与语义：10/10 成立。明细存 plan/verify/rules-spot.txt；verify_cites.py 复跑 84 条 0 失败存 plan/verify/rules.txt。


## 补记：分组日界的时钟口径（T6 对补充轮 U19 的裁定，2026-11-12）

- 桌面 `startOfDay` 按 `schoolParts`（学校日历日）切天 [[r-082]]；相对日（今天/明天）的日差用 `businessNowMs` 计算 [[r-083]]，按天分组的兜底键同样取 `businessNowMs` [[r-084]]。手机按 `dayOf(openEpochOf)` 的 UTC+8 日序与业务此刻比对、时钟不可用时退墙钟（只影响归组）[[r-046]] [[r-065]]。
- **裁定**：补充轮 U19「桌面 startOfDay 与手机 UTC+8 dayOf 切分来源可能不同」的推测**推翻**——两端同走业务时钟与学校日历日，差异只是实现写法（毫秒 startOfDay vs 秒 dayOf）。
- 真实差异（语义不同）：时钟不可用时手机退手机墙钟仍归组 [[r-046]]；桌面无墙钟退路，日差得 NaN、日期组不成立（计数呈「待确认」[[r-044]]）。呈现口径不同，读代码定不了用户感知差异，标「需测试定」——missing：缺一条时钟不可用下两端列表归组的行为测试。

> 计数勘误（T7）：初版写 81 条，现共 106 条（r-082..r-084 为 T6 对 U19 的裁定补做；r-085..r-106 为 T7 返修补做：规则 7 增「重试截止倒计时」三端、规则 4 增桌面消费面）。
