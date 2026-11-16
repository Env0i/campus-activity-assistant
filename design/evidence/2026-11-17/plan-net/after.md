# 补测试之后：逐条重跑与跟进结论

- **基线提交**：`3091a3a`，分支 `refactor/step1`。执行日期：2026-11-16。
- **怎么跑的**：与 `before.md` 同一份候选、同一条执行路径（只在临时副本里改一处，先过 `node --check`，再按 `plan_flow` → `plan_board` → `exit_paths_plan` → `main_window_plan` → `contract_plan` 的顺序跑，第一个变红即停），补完测试后把全部候选重跑一遍。
- **数字**：候选 690 条；补测后变红 354 条，等价 10 条，没人守 312 条，变异不成立 14 条。
- **补测前**：红 242 条、没变红 434 条、不成立 14 条（见 `before.md`）。

## 等价项的入口清单

等价不是「看起来没差别」，而是把这个值或这个动作的全部入口列出来，逐个说明为什么到不了、或到了也看不出差别。只列判断本身到不了的入口，不算列全。

### §1 页面元素恒在

守的是 `$()` 拿不到元素时提前返回或给空值的那类判断：

| 判断 | 入口清单 | 为什么到不了 |
|---|---|---|
| `if (!actions) return;`（`paintBoardActions`） | 计划栏只由 `render()` 调用；`render()` 在页面脚本执行后每次重画都跑 | `#route-actions` 在 `index.html` 里出现一次，没有被删掉的代码路径；同一进程只有一份 DOM |
| `if (!board) return;`（`paintBoardState`） | 同上 | `#board` 同上 |
| `if (!tag || !label) return;`（`setBoardTag`） | 同上 | `#board-tag`、`#board-tag-text` 同上 |
| `if (!warn || !hint) return;`（`paintRunPanel`） | 同上 | `#run-warn`、`#plan-hint` 同上 |
| `if (why) why.hidden = true;`（`paintRunPanel`） | 同上 | `#modify-why` 同上 |
| `if (restore) restore.hidden = !S.editing;`（`paintBoardActions`） | 同上 | `#btn-edit-restore` 同上 |
| `$("#retry-for") ? … : null`、`$("#max-attempts") ? … : null`（`paintBoardActions`） | 同上 | 两个下拉都在 `index.html` 里，`$()` 不会返回 null，所以三元永远走真分支 |

这些判断在真实页面上恒为真，改掉它们用户看不到任何差别；沙箱里的 `$()` 也永远返回元素，跑不出差别。因此判等价，不补用例。

### §2 结果页判定先看忙态

`resultMode()` 的第一项是 `!S.busy`。调用它的六处都会先看忙态：`paintSelected` 的忙态分支在前、`boardPlanState` 第一行就是 `if (S.busy) return "running";`、`paintBoardActions` 里 `result` 为真只让按钮更早收起、`paintPlan` 的 `showTasks` 是 `S.busy || resultMode()`、`paintDock` 写的是 `!S.busy && resultMode()`、`paintLed` 也先走忙态。把这一项换成恒真以后，六处的结果都不变，因此判等价。

## 逐条结论

「已守」列写第一个变红的测试文件与用例；「等价」列指向上面那一段入口清单。

### views/plan-panel.js（339 条）

| 编号 | 定位：函数 / 那一行的文字 / 第几次出现 | 变异写法 | 补测后 |
|---|---|---|---|
| M001 | `paintSelected` `if (!S.busy && S.login.present === false && !S.runtime.error) {`（第 1 次） | `条件-恒假`：`if (!S.busy && S.login.present === false && !S.runtime.error` → `(false)` | 已守 · `test_first_use_board_invites_login` · '暂时没有' != '首次使用' |
| M002 | `paintSelected` `if (!S.busy && S.login.present === false && !S.runtime.error) {`（第 1 次） | `短路-去右侧`：`!S.busy && S.login.present === false ` → `!S.busy ` | 已守 · `test_late_same_plan_events_do_not_revive_terminal_plan` · '报名计划完成' not found in '登录后开始' |
| M003 | `paintSelected` `if (!S.busy && S.login.present === false && !S.runtime.error) {`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '首次使用' != '准备中' |
| M004 | `paintSelected` `if (!S.busy && S.login.present === false && !S.runtime.error) {`（第 1 次） | `短路-去右侧`：` false && !S.runtime.error` → ` false ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '首次使用' != '不可用' |
| M005 | `paintSelected` `if (S.login.loginPending) {`（第 1 次） | `条件-恒假`：`if (S.login.loginPending)` → `(false)` | 已守 · `test_login_start_reports_failure_and_keeps_previous_session` · '正在准备报名' != '正在打开登录窗口' |
| M006 | `paintSelected` `if (resultMode()) {`（第 1 次） | `条件-恒假`：`if (resultMode())` → `(false)` | 已守 · `test_late_same_plan_events_do_not_revive_terminal_plan` · '报名计划完成' not found in '近期没有要开放的活动' |
| M007 | `paintSelected` `const termsHold = !S.busy && termsLocked() && S.login.present !== fals`（第 1 次） | `短路-去右侧`：` !S.busy && termsLocked() ` → ` !S.busy ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '已暂停' != '修改中' |
| M008 | `paintSelected` `const termsHold = !S.busy && termsLocked() && S.login.present !== fals`（第 2 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_running_board_never_falls_back_to_draft_states` · '已暂停' != '准备中' |
| M009 | `paintSelected` `const termsHold = !S.busy && termsLocked() && S.login.present !== fals`（第 1 次） | `短路-去右侧`：` termsLocked() && S.login.present !== false` → ` termsLocked() ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '已暂停' != '不可用' |
| M010 | `paintSelected` `if (termsHold && !items.length) {`（第 1 次） | `条件-恒假`：`if (termsHold && !items.length)` → `(false)` | 已守 · `test_terms_hold_board_stops_at_terms_before_selection` · '暂时没有' != '已暂停' |
| M011 | `paintSelected` `if (termsHold && !items.length) {`（第 1 次） | `短路-去右侧`：`termsHold && !items.length` → `termsHold ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '同意条款后才能报名' != '已选 1 场' |
| M012 | `paintSelected` `box.textContent = S.terms.unknown ? "重新确认条款后才能报名" : "同意条款后才能报名";`（第 1 次） | `三元-对调`：`? "重新确认条款后才能报名" : "同意条款后才能报名"` → `? "同意条款后才能报名": "重新确认条款后才能报名" ` | 已守 · `test_terms_hold_board_stops_at_terms_before_selection` · '重新确认条款后才能报名' != '同意条款后才能报名' |
| M013 | `paintSelected` `boardText.textContent = S.terms.unknown ? "登录、活动列表和报名计划暂时停用。帮助和设置照常可用。`（第 1 次） | `三元-对调`：`? "登录、活动列表和报名计划暂时停用。帮助和设置照常可用。"
      : "登录、活动列表和报名计划都停用了。帮助` → `? "登录、活动列表和报名计划都停用了。帮助和设置照常可用。": "登录、活动列` | 已守 · `test_terms_hold_board_stops_at_terms_before_selection` · '暂时停用' not found in '登录、活动列表和报名计划都停用了。帮助和设置照常可用。' |
| M014 | `paintSelected` `if (!S.busy && S.runtime.error && S.listState !== "ready") {`（第 1 次） | `条件-恒假`：`if (!S.busy && S.runtime.error && S.listState !== "ready")` → `(false)` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '暂时没有' != '不可用' |
| M015 | `paintSelected` `if (!S.busy && S.runtime.error && S.listState !== "ready") {`（第 1 次） | `短路-去右侧`：`!S.busy && S.runtime.error ` → `!S.busy ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '不可用' != '开放中' |
| M016 | `paintSelected` `if (!S.busy && S.runtime.error && S.listState !== "ready") {`（第 3 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_running_board_never_falls_back_to_draft_states` · '不可用' != '准备中' |
| M017 | `paintSelected` `if (!S.busy && S.runtime.error && S.listState !== "ready") {`（第 1 次） | `短路-去右侧`：` S.runtime.error && S.listState !== "ready"` → ` S.runtime.error ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '暂时不能报名' != '学校当前没有活动' |
| M018 | `paintSelected` `if (!S.busy && S.listState === "error" && !S.items.length) {`（第 1 次） | `条件-恒假`：`if (!S.busy && S.listState === "error" && !S.items.length)` → `(false)` | 已守 · `test_board_names_login_component_error_and_loading_states` · '暂时没有' != '需重试' |
| M019 | `paintSelected` `if (!S.busy && S.listState === "error" && !S.items.length) {`（第 1 次） | `短路-去右侧`：`!S.busy && S.listState === "error" ` → `!S.busy ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '活动暂时没加载' != '学校当前没有活动' |
| M020 | `paintSelected` `if (!S.busy && S.listState === "error" && !S.items.length) {`（第 4 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_running_board_never_falls_back_to_draft_states` · '需重试' != '准备中' |
| M021 | `paintSelected` `if (!S.busy && S.listState === "error" && !S.items.length) {`（第 1 次） | `短路-去右侧`：` "error" && !S.items.length` → ` "error" ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '需重试' != '下一场' |
| M022 | `paintSelected` `if (!S.busy && S.listState === "loading" && !items.length) {`（第 1 次） | `条件-恒假`：`if (!S.busy && S.listState === "loading" && !items.length)` → `(false)` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '暂时没有' != '加载中' |
| M023 | `paintSelected` `if (!S.busy && S.listState === "loading" && !items.length) {`（第 1 次） | `短路-去右侧`：`!S.busy && S.listState === "loading" ` → `!S.busy ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '活动列表正在加载' != '没有可报名的场次' |
| M024 | `paintSelected` `if (!S.busy && S.listState === "loading" && !items.length) {`（第 5 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_running_board_never_falls_back_to_draft_states` · '加载中' != '准备中' |
| M025 | `paintSelected` `if (!S.busy && S.listState === "loading" && !items.length) {`（第 1 次） | `短路-去右侧`：` "loading" && !items.length` → ` "loading" ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '加载中' != '报名计划' |
| M026 | `paintSelected` `if (S.busy) {`（第 1 次） | `条件-恒假`：`if (S.busy)` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '已选 1 场' != '正在准备报名' |
| M027 | `paintSelected` `if (S.busy) {`（第 6 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '已选 1 场' != '正在准备报名' |
| M028 | `paintSelected` `if (view.phase === "submitting" \|\| view.phase === "arming" \|\| view`（第 1 次） | `条件-恒假`：`if (view.phase === "submitting" \|\| view.phase === "arming"` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '正在准备报名' != '活动甲' |
| M029 | `paintSelected` `if (view.phase === "submitting" \|\| view.phase === "arming" \|\| view`（第 1 次） | `短路-去右侧`：` "submitting" \|\| view.phase === "arming" ` → ` "submitting" ` | 已守 · `test_future_prewarm_is_not_reported_as_submitting` · '准备中' != '准备报名' |
| M030 | `paintSelected` `if (view.phase === "submitting" \|\| view.phase === "arming" \|\| view`（第 1 次） | `短路-去右侧`：` "arming" \|\| view.phase === "waiting"` → ` "arming" ` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '正在准备报名' != '活动甲' |
| M031 | `paintSelected` `setBoardTag(runTagText(view), view.phase === "submitting" ? "red" : "a`（第 1 次） | `三元-对调`：`? "red" : "amber"` → `? "amber": "red" ` | 已守 · `test_running_board_uses_tone_and_caption_for_each_phase` · 'amber' != 'red' |
| M032 | `paintSelected` `box.textContent = view.item ? view.item.name : "这一场活动";`（第 1 次） | `三元-对调`：`? view.item.name : "这一场活动"` → `? "这一场活动": view.item.name ` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '这一场活动' != '活动甲' |
| M033 | `paintSelected` `setBoardTag(view.phase === "settling" ? "汇总中" : "准备中", "amber", true);`（第 1 次） | `三元-对调`：`? "汇总中" : "准备中"` → `? "准备中": "汇总中" ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '准备中' != '汇总中' |
| M034 | `paintSelected` `box.textContent = view.phase === "settling" ? "正在汇总结果" : "正在准备报名";`（第 1 次） | `三元-对调`：`? "正在汇总结果" : "正在准备报名"` → `? "正在准备报名": "正在汇总结果" ` | 已守 · `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` · '正在汇总结果' != '正在准备报名' |
| M035 | `paintSelected` `? "每一场都结束了，正在汇总这一轮的结果。"`（第 1 次） | `三元-对调`：`? "每一场都结束了，正在汇总这一轮的结果。"
      : "计划已经接管，正在核对每一场的开放时间。"` → `? "计划已经接管，正在核对每一场的开放时间。": "每一场都结束了，正在汇总这` | 已守 · `test_running_board_uses_tone_and_caption_for_each_phase` · '计划已经接管，正在核对每一场的开放时间。' != '每一场都结束了，正在汇总这一轮的结果。' |
| M036 | `paintSelected` `if (!items.length) {`（第 1 次） | `条件-恒假`：`if (!items.length)` → `(false)` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '已选 0 场' != '没有可报名的场次' |
| M037 | `paintSelected` `if (next) {`（第 1 次） | `条件-恒假`：`if (next)` → `(false)` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '暂时没有' != '开放中' |
| M038 | `paintSelected` `setBoardTag(openNow ? "开放中" : "下一场", "amber", !openNow);`（第 1 次） | `三元-对调`：`? "开放中" : "下一场"` → `? "下一场": "开放中" ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '下一场' != '开放中' |
| M039 | `paintSelected` `} else if (S.listState === "ready" && !S.items.length) {`（第 1 次） | `条件-恒假`：`else if (S.listState === "ready" && !S.items.length)` → `(false)` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '没有可报名的场次' != '学校当前没有活动' |
| M040 | `paintSelected` `} else if (S.listState === "ready" && !S.items.length) {`（第 1 次） | `短路-去右侧`：` "ready" && !S.items.length` → ` "ready" ` | 已守 · `test_empty_board_separates_school_empty_from_no_target` · '学校当前没有活动' != '没有可报名的场次' |
| M041 | `paintSelected` `} else if (S.listState === "ready" && bnowS() === null && !S.demo) {`（第 1 次） | `条件-恒假`：`else if (S.listState === "ready" && bnowS() === null && !S.d` → `(false)` | 已守 · `test_empty_board_separates_school_empty_from_no_target` · '暂时没有' != '时间待校准' |
| M042 | `paintSelected` `} else if (S.listState === "ready" && bnowS() === null && !S.demo) {`（第 1 次） | `短路-去右侧`：` "ready" && bnowS() === null ` → ` "ready" ` | 已守 · `test_empty_board_separates_school_empty_from_no_target` · '时间待校准' != '没有可报名的场次' |
| M043 | `paintSelected` `} else if (S.listState === "ready" && bnowS() === null && !S.demo) {`（第 1 次） | `短路-去右侧`：` null && !S.demo` → ` null ` | 已守 · `test_running_board_never_falls_back_to_draft_states` · '时间待校准' != '没有可报名的场次' |
| M044 | `paintSelected` `} else if (S.listState === "ready") {`（第 1 次） | `条件-恒假`：`else if (S.listState === "ready")` → `(false)` | 已守 · `test_empty_board_separates_school_empty_from_no_target` · '近期没有要开放的活动' != '没有可报名的场次' |
| M045 | `paintSelected` `if (termsHold) setBoardTag("已暂停", "off", true);`（第 1 次） | `条件-恒假`：`if (termsHold)` → `(false)` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '报名计划' != '已暂停' |
| M046 | `paintSelected` `else setBoardTag(S.editing ? "修改中" : "报名计划", "amber", true);`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_start_and_stop_buttons_follow_the_run_phase` · '报名计划' != '修改中' |
| M047 | `paintSelected` `else setBoardTag(S.editing ? "修改中" : "报名计划", "amber", true);`（第 1 次） | `三元-对调`：`? "修改中" : "报名计划"` → `? "报名计划": "修改中" ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '报名计划' != '修改中' |
| M048 | `selectionSummary` `return [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名等开放" : ""`（第 1 次） | `三元-对调`：`? instant + " 场立即报名" : ""` → `? "": instant + " 场立即报名" ` | 已守 · `test_draft_dock_uses_the_summary_sentence_not_the_countdown` · '0 场立即报名，1 场预报名等开放' != '1 场预报名等开放' |
| M049 | `selectionSummary` `return [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名等开放" : ""`（第 1 次） | `三元-对调`：`? pre + " 场预报名等开放" : ""` → `? "": pre + " 场预报名等开放" ` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '预报名等开放' not found in '' |
| M050 | `runTagText` `if (view.phase === "submitting") return "正在提交";`（第 1 次） | `条件-恒假`：`if (view.phase === "submitting")` → `(false)` | 已守 · `test_running_board_uses_tone_and_caption_for_each_phase` · '等开放' != '正在提交' |
| M051 | `runTagText` `if (view.phase === "arming") return "准备报名";`（第 1 次） | `条件-恒假`：`if (view.phase === "arming")` → `(false)` | 已守 · `test_future_prewarm_is_not_reported_as_submitting` · '即将开放' != '准备报名' |
| M052 | `runTagText` `const left = view.openAt === null ? null : bnLeftSec(view.openAt);`（第 1 次） | `三元-对调`：`? null : bnLeftSec(view.openAt)` → `? bnLeftSec(view.openAt): null ` | 已守 · `test_waiting_plan_turns_to_soon_inside_five_seconds` · '等开放' != '即将开放' |
| M053 | `runTagText` `return left !== null && left <= RUN_SOON_S ? "即将开放" : "等开放";`（第 1 次） | `三元-对调`：`? "即将开放" : "等开放"` → `? "等开放": "即将开放" ` | 已守 · `test_waiting_plan_shows_waiting_target_and_cancel_action` · '等开放' != '即将开放' |
| M054 | `runHeadKey` `return view.phase + "\|" + (["submitting", "arming", "waiting"].indexO`（第 1 次） | `三元-对调`：`? runTagText(view) : ""` → `? "": runTagText(view) ` | 没人守 |
| M055 | `runCaption` `if (view.phase === "submitting") {`（第 1 次） | `条件-恒假`：`if (view.phase === "submitting")` → `(false)` | 已守 · `test_running_board_uses_tone_and_caption_for_each_phase` · '已提交 1 次' not found in '这一场等开放，到点自动开始。' |
| M056 | `runCaption` `if (count > 1) return "正在提交 " + count + " 场，每场结果单独显示。";`（第 1 次） | `条件-恒假`：`if (count > 1)` → `(false)` | 没人守 |
| M057 | `runCaption` `const last = String(task.last_reason \|\| "").trim();`（第 1 次） | `短路-去右侧`：`task.last_reason \|\| ""` → `task.last_reason ` | 没人守 |
| M058 | `runCaption` `return "已提交 " + tried + " 次" + (last ? "，最近：" + last : "");`（第 1 次） | `三元-对调`：`? "，最近：" + last : ""` → `? "": "，最近：" + last ` | 已守 · `test_run_submitting_single_caption_and_cancel_label` · False is not true : 已提交 3 次 |
| M059 | `runCaption` `if (view.phase === "arming") {`（第 1 次） | `条件-恒假`：`if (view.phase === "arming")` → `(false)` | 没人守 |
| M060 | `runCaption` `return count > 1 ? "已开放，正在准备 " + count + " 场，每场结果单独显示。" : "已开放，正在准备提交。`（第 1 次） | `三元-对调`：`? "已开放，正在准备 " + count + " 场，每场结果单独显示。" : "已开放，正在准备提交。"` → `? "已开放，正在准备提交。": "已开放，正在准备 " + count + "` | 没人守 |
| M061 | `runCaption` `return count > 1 ? "这一批 " + count + " 场同时提交，到点自动开始。" : "这一场等开放，到点自动开始。`（第 1 次） | `三元-对调`：`? "这一批 " + count + " 场同时提交，到点自动开始。" : "这一场等开放，到点自动开始。"` → `? "这一场等开放，到点自动开始。": "这一批 " + count + " 场` | 已守 · `test_run_tag_turns_soon_inside_five_seconds` · '这一批 1 场同时提交，到点自动开始。' != '这一场等开放，到点自动开始。' |
| M062 | `setBoardTag` `if (!tag \|\| !label) return;`（第 1 次） | `条件-恒假`：`if (!tag \|\| !label)` → `(false)` | 等价 · §1 页面元素恒在 |
| M063 | `setBoardTag` `tag.dataset.tone = tone \|\| "amber";`（第 1 次） | `短路-去右侧`：` tone \|\| "amber"` → ` tone ` | 没人守 |
| M064 | `setBoardTag` `tag.dataset.dot = dot === false ? "false" : "true";`（第 1 次） | `三元-对调`：`? "false" : "true"` → `? "true": "false" ` | 没人守 |
| M065 | `boardPlanState` `if (S.busy) return "running";`（第 1 次） | `条件-恒假`：`if (S.busy)` → `(false)` | 已守 · `test_all_terminal_waits_for_plan_done` · 'idle' != 'running' |
| M066 | `boardPlanState` `if (S.busy) return "running";`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_all_terminal_waits_for_plan_done` · 'idle' != 'running' |
| M067 | `boardPlanState` `if (!resultMode()) return "idle";`（第 1 次） | `条件-恒假`：`if (!resultMode())` → `(false)` | 已守 · `test_single_failure_does_not_paint_plan` · 'stopped' != 'idle' |
| M068 | `boardPlanState` `if (frame === "ok") return "completed";`（第 1 次） | `条件-恒假`：`if (frame === "ok")` → `(false)` | 已守 · `test_result_all_success_shows_mini_led` · 'stopped' != 'completed' |
| M069 | `boardPlanState` `if (frame === "bad") return "failed";`（第 1 次） | `条件-恒假`：`if (frame === "bad")` → `(false)` | 已守 · `test_result_page_distinguishes_pending_from_total_failure` · 'stopped' != 'failed' |
| M070 | `boardPlanState` `if (frame === "warn") return String(S.plan.status) === "partial" ? "pa`（第 1 次） | `条件-恒假`：`if (frame === "warn")` → `(false)` | 已守 · `test_result_page_distinguishes_pending_from_total_failure` · 'stopped' != 'attention' |
| M071 | `boardPlanState` `if (frame === "warn") return String(S.plan.status) === "partial" ? "pa`（第 1 次） | `三元-对调`：`? "partial" : "attention"` → `? "attention": "partial" ` | 已守 · `test_result_page_distinguishes_pending_from_total_failure` · 'partial' != 'attention' |
| M072 | `paintBoardState` `if (!board) return;`（第 1 次） | `条件-恒假`：`if (!board)` → `(false)` | 等价 · §1 页面元素恒在 |
| M073 | `paintBoardActions` `const policyFor = $("#retry-for") ? $("#retry-for").closest(".policy-s`（第 1 次） | `三元-对调`：`? $("#retry-for").closest(".policy-select") : null` → `? null: $("#retry-for").closest(".policy` | 等价 · §1 页面元素恒在 |
| M074 | `paintBoardActions` `const policyMax = $("#max-attempts") ? $("#max-attempts").closest(".po`（第 1 次） | `三元-对调`：`? $("#max-attempts").closest(".policy-select") : null` → `? null: $("#max-attempts").closest(".pol` | 等价 · §1 页面元素恒在 |
| M075 | `paintBoardActions` `if (!actions) return;`（第 1 次） | `条件-恒假`：`if (!actions)` → `(false)` | 等价 · §1 页面元素恒在 |
| M076 | `paintBoardActions` `const showPick = !S.busy && !result && !selectedItems().length && !!bo`（第 1 次） | `短路-去右侧`：` !S.busy && !result ` → ` !S.busy ` | 没人守 |
| M077 | `paintBoardActions` `const showPick = !S.busy && !result && !selectedItems().length && !!bo`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M078 | `paintBoardActions` `const showPick = !S.busy && !result && !selectedItems().length && !!bo`（第 1 次） | `短路-去右侧`：` !result && !selectedItems().length ` → ` !result ` | 已守 · `test_pick_and_clear_controls_follow_selection_and_run_state` · False is not true |
| M079 | `paintBoardActions` `const showPick = !S.busy && !result && !selectedItems().length && !!bo`（第 1 次） | `短路-去右侧`：` !selectedItems().length && !!boardTargetItem()
    ` → ` !selectedItems().length ` | 没人守 |
| M080 | `paintBoardActions` `const showPick = !S.busy && !result && !selectedItems().length && !!bo`（第 1 次） | `短路-去右侧`：` !!boardTargetItem()
    && S.listState === "ready" ` → ` !!boardTargetItem()
    ` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · False is not true : 已选活动时不显示「选这一场」 |
| M081 | `paintBoardActions` `&& S.listState === "ready" && !termsLocked();`（第 1 次） | `短路-去右侧`：` "ready" && !termsLocked()` → ` "ready" ` | 没人守 |
| M082 | `paintBoardActions` `if (quickPick) quickPick.hidden = !showPick;`（第 1 次） | `条件-恒假`：`if (quickPick)` → `(false)` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · False is not true |
| M083 | `paintBoardActions` `if (clear) clear.hidden = S.busy \|\| result \|\| !S.selected.size;`（第 1 次） | `条件-恒假`：`if (clear)` → `(false)` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · False is not true |
| M084 | `paintBoardActions` `if (clear) clear.hidden = S.busy \|\| result \|\| !S.selected.size;`（第 1 次） | `短路-去右侧`：` S.busy \|\| result ` → ` S.busy ` | 没人守 |
| M085 | `paintBoardActions` `if (clear) clear.hidden = S.busy \|\| result \|\| !S.selected.size;`（第 2 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_pick_and_clear_controls_follow_selection_and_run_state` · False is not true |
| M086 | `paintBoardActions` `if (clear) clear.hidden = S.busy \|\| result \|\| !S.selected.size;`（第 1 次） | `短路-去右侧`：` result \|\| !S.selected.size` → ` result ` | 已守 · `test_pick_and_clear_controls_follow_selection_and_run_state` · False is not true |
| M087 | `paintBoardActions` `if (S.busy \|\| result) {`（第 1 次） | `条件-恒假`：`if (S.busy \|\| result)` → `(false)` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · False is not true |
| M088 | `paintBoardActions` `if (S.busy \|\| result) {`（第 1 次） | `短路-去右侧`：`S.busy \|\| result` → `S.busy ` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · False is not true : 结果页不摆开始按钮 |
| M089 | `paintBoardActions` `if (S.busy \|\| result) {`（第 3 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · False is not true |
| M090 | `paintBoardActions` `[checks, headed, policyFor, policyMax, start].forEach((el) => { if (el`（第 1 次） | `条件-恒假`：`if (el)` → `(false)` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · True is not false : 草稿要把检查条放出来 |
| M091 | `paintBoardActions` `if (restore) restore.hidden = !S.editing;`（第 1 次） | `条件-恒假`：`if (restore)` → `(false)` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · False is not true : 没在修改时不显示「放弃修改」 |
| M092 | `paintBoardActions` `if (restore) restore.hidden = !S.editing;`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_board_actions_show_only_what_the_phase_allows` · True is not false : 修改中要显示「放弃修改」 |
| M093 | `editNoteText` `const done = Math.max(0, Math.floor(Number(S.editing && S.editing.done`（第 1 次） | `短路-去右侧`：`Number(S.editing && S.editing.doneN) \|\| 0` → `Number(S.editing && S.editing.doneN) ` | 没人守 |
| M094 | `editNoteText` `const done = Math.max(0, Math.floor(Number(S.editing && S.editing.done`（第 1 次） | `短路-去右侧`：`S.editing && S.editing.doneN` → `S.editing ` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '已结束的 2 场不受影响' not found in '计划已暂停，重新开始前不会自动报名。离最近一场开放只剩 4 分 |
| M095 | `editNoteText` `const done = Math.max(0, Math.floor(Number(S.editing && S.editing.done`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '已结束的 2 场不受影响' not found in '计划已暂停，重新开始前不会自动报名。离最近一场开放只剩 4 分 |
| M096 | `editNoteText` `const done = Math.max(0, Math.floor(Number(S.editing && S.editing.done`（第 2 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '已结束的 2 场不受影响' not found in '计划已暂停，重新开始前不会自动报名。离最近一场开放只剩 4 分 |
| M097 | `editNoteText` `if (done > 0) text += "已结束的 " + done + " 场不受影响。";`（第 1 次） | `条件-恒假`：`if (done > 0)` → `(false)` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '已结束的 2 场不受影响' not found in '计划已暂停，重新开始前不会自动报名。离最近一场开放只剩 4 分 |
| M098 | `editNoteText` `((S.editing && S.editing.ids) \|\| []).forEach((id) => {`（第 1 次） | `短路-去右侧`：`(S.editing && S.editing.ids) \|\| []` → `(S.editing && S.editing.ids) ` | 没人守 |
| M099 | `editNoteText` `((S.editing && S.editing.ids) \|\| []).forEach((id) => {`（第 1 次） | `短路-去右侧`：`S.editing && S.editing.ids` → `S.editing ` | 已守 · `test_restore_edited_plan_sends_original_selection` · JS 行为测试崩溃：TypeError: (S.editing \|\| []).forEach is not a func |
| M100 | `editNoteText` `((S.editing && S.editing.ids) \|\| []).forEach((id) => {`（第 3 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '离最近一场开放只剩' not found in '计划已暂停，重新开始前不会自动报名。已结束的 2 场不受影响。' |
| M101 | `editNoteText` `((S.editing && S.editing.ids) \|\| []).forEach((id) => {`（第 4 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '离最近一场开放只剩' not found in '计划已暂停，重新开始前不会自动报名。已结束的 2 场不受影响。' |
| M102 | `editNoteText` `const ts = item ? toTs(item.sign_start) : null;`（第 1 次） | `三元-对调`：`? toTs(item.sign_start) : null` → `? null: toTs(item.sign_start) ` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '离最近一场开放只剩' not found in '计划已暂停，重新开始前不会自动报名。已结束的 2 场不受影响。' |
| M103 | `editNoteText` `if (ts !== null && (first === null \|\| ts < first)) first = ts;`（第 1 次） | `条件-恒假`：`if (ts !== null && (first === null \|\| ts < first))` → `(false)` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '离最近一场开放只剩' not found in '计划已暂停，重新开始前不会自动报名。已结束的 2 场不受影响。' |
| M104 | `editNoteText` `if (now !== null && first !== null) {`（第 1 次） | `条件-恒假`：`if (now !== null && first !== null)` → `(false)` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '离最近一场开放只剩' not found in '计划已暂停，重新开始前不会自动报名。已结束的 2 场不受影响。' |
| M105 | `editNoteText` `if (gap > 0 && gap <= 300) text += "离最近一场开放只剩 " + durText(gap) + "。";`（第 1 次） | `条件-恒假`：`if (gap > 0 && gap <= 300)` → `(false)` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '离最近一场开放只剩' not found in '计划已暂停，重新开始前不会自动报名。已结束的 2 场不受影响。' |
| M106 | `paintEditNote` `if (!note) return;`（第 1 次） | `条件-恒假`：`if (!note)` → `(false)` | 等价 · §1 页面元素恒在 |
| M107 | `paintEditNote` `note.hidden = !S.editing \|\| S.busy;`（第 1 次） | `短路-去右侧`：` !S.editing \|\| S.busy` → ` !S.editing ` | 没人守 |
| M108 | `paintEditNote` `note.hidden = !S.editing \|\| S.busy;`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · True is not false |
| M109 | `paintEditNote` `note.hidden = !S.editing \|\| S.busy;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M110 | `paintEditNote` `note.textContent = S.editing && !S.busy ? editNoteText() : "";`（第 1 次） | `短路-去右侧`：` S.editing && !S.busy ` → ` S.editing ` | 没人守 |
| M111 | `paintEditNote` `note.textContent = S.editing && !S.busy ? editNoteText() : "";`（第 2 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '已结束的 2 场不受影响' not found in '' |
| M112 | `paintEditNote` `note.textContent = S.editing && !S.busy ? editNoteText() : "";`（第 2 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M113 | `paintEditNote` `note.textContent = S.editing && !S.busy ? editNoteText() : "";`（第 1 次） | `三元-对调`：`? editNoteText() : ""` → `? "": editNoteText() ` | 已守 · `test_edit_note_is_visible_only_for_the_editing_draft` · '已结束的 2 场不受影响' not found in '' |
| M114 | `resultMode` `function resultMode() {`（第 1 次） | `短路-去右侧`：`
  return !S.busy && !S.editing ` → `
  return !S.busy ` | 没人守 |
| M115 | `resultMode` `return !S.busy && !S.editing && S.plan.tasks.size > 0`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 等价 · §2 结果页判定先看忙态 |
| M116 | `resultMode` `return !S.busy && !S.editing && S.plan.tasks.size > 0`（第 1 次） | `短路-去右侧`：` !S.editing && S.plan.tasks.size > 0
    ` → ` !S.editing ` | 已守 · `test_P14_a_new_plan_event_leaves_editing` · '报名计划已停止' != '还没选活动' |
| M117 | `resultMode` `return !S.busy && !S.editing && S.plan.tasks.size > 0`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 没人守 |
| M118 | `resultMode` `return !S.busy && !S.editing && S.plan.tasks.size > 0`（第 1 次） | `短路-去右侧`：` 0
    && PLAN_TERMINAL.indexOf(String(S.plan.status \|\| ""` → ` 0
    ` | 没人守 |
| M119 | `resultMode` `&& PLAN_TERMINAL.indexOf(String(S.plan.status \|\| "")) >= 0 && result`（第 1 次） | `短路-去右侧`：`S.plan.status \|\| ""` → `S.plan.status ` | 没人守 |
| M120 | `boardTargetItem` `if (next.bestId) return findItem(next.bestId);`（第 1 次） | `条件-恒假`：`if (next.bestId)` → `(false)` | 已守 · `test_board_keeps_busy_terms_and_cached_list_apart` · '暂时没有' != '下一场' |
| M121 | `boardTargetItem` `if (next.bestId) return findItem(next.bestId);`（第 1 次） | `短路-去右侧`：`
  if (next.openNow) return S.items.find((item) => !item.sig` → `
  if (next.openNow) return S.items.find` | 没人守 |
| M122 | `boardTargetItem` `if (next.openNow) return S.items.find((item) => !item.signed && stateO`（第 1 次） | `条件-恒假`：`if (next.openNow)` → `(false)` | 没人守 |
| M123 | `boardTargetItem` `if (next.openNow) return S.items.find((item) => !item.signed && stateO`（第 1 次） | `短路-去右侧`：` !item.signed && stateOf(item) === "open"` → ` !item.signed ` | 没人守 |
| M124 | `startBlocker` `if (S.busy) return null;`（第 1 次） | `条件-恒假`：`if (S.busy)` → `(false)` | 没人守 |
| M125 | `startBlocker` `if (S.busy) return null;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M126 | `startBlocker` `if (S.runtime.error) return { text: "程序组件缺失，看顶部提示" };`（第 1 次） | `条件-恒假`：`if (S.runtime.error)` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '程序组件缺失' not found in '还差一步：学校还没有可选的活动刷新' |
| M127 | `startBlocker` `if (S.cancel.busyId) return { text: "正在取消报名，等它结束再开始" };`（第 1 次） | `条件-恒假`：`if (S.cancel.busyId)` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '正在取消报名' not found in '还差一步：学校还没有可选的活动刷新' |
| M128 | `startBlocker` `if (termsLocked()) {`（第 1 次） | `条件-恒假`：`if (termsLocked())` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '先同意使用条款' not found in '还差一步：学校还没有可选的活动刷新' |
| M129 | `startBlocker` `const newer = typeof termsUpdateMode === "function" && termsUpdateMode`（第 1 次） | `短路-去右侧`：` "function" && termsUpdateMode()` → ` "function" ` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '先同意使用条款' not found in '还差一步：先同意新版条款查看条款' |
| M130 | `startBlocker` `return { text: S.terms.unknown ? "先重新确认条款" : (newer ? "先同意新版条款" : "先同意`（第 1 次） | `三元-对调`：`? "先重新确认条款" : (newer ? "先同意新版条款" : "先同意使用条款")` → `? (newer ? "先同意新版条款" : "先同意使用条款"): "先重新确` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '先同意使用条款' not found in '还差一步：先重新确认条款查看条款' |
| M131 | `startBlocker` `return { text: S.terms.unknown ? "先重新确认条款" : (newer ? "先同意新版条款" : "先同意`（第 1 次） | `三元-对调`：`? "先同意新版条款" : "先同意使用条款"` → `? "先同意使用条款": "先同意新版条款" ` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '先同意使用条款' not found in '还差一步：先同意新版条款查看条款' |
| M132 | `startBlocker` `if (!S.demo) {`（第 1 次） | `条件-恒假`：`if (!S.demo)` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '还没有登录' not found in '还差一步：学校还没有可选的活动刷新' |
| M133 | `startBlocker` `const login = (S.login.view \|\| {}).state;`（第 1 次） | `短路-去右侧`：`S.login.view \|\| {}` → `S.login.view ` | 已守 · `test_enter_during_running_plan_does_not_start_again` · TypeError: Cannot read properties of undefined (reading 'sta |
| M134 | `startBlocker` `if (S.login.present === false \|\| login === "none") return { text: "还`（第 1 次） | `条件-恒假`：`if (S.login.present === false \|\| login === "none")` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '还没有登录' not found in '还差一步：学校还没有可选的活动刷新' |
| M135 | `startBlocker` `if (S.login.present === false \|\| login === "none") return { text: "还`（第 1 次） | `短路-去右侧`：` false \|\| login === "none"` → ` false ` | 没人守 |
| M136 | `startBlocker` `if (login === "bad") return { text: "登录已失效", act: "login", label: "重新登`（第 1 次） | `条件-恒假`：`if (login === "bad")` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '登录已失效' not found in '还差一步：学校还没有可选的活动刷新' |
| M137 | `startBlocker` `if (login === "unknown") return { text: "登录状态还没确认", act: "refresh", la`（第 1 次） | `条件-恒假`：`if (login === "unknown")` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '登录状态还没确认' not found in '还差一步：学校还没有可选的活动刷新' |
| M138 | `startBlocker` `if (login === "checking") return { text: "登录状态还没确认" };`（第 1 次） | `条件-恒假`：`if (login === "checking")` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '登录状态还没确认' not found in '还差一步：学校还没有可选的活动刷新' |
| M139 | `startBlocker` `if (login === "pending") return { text: S.autoLogin ? "正在自动登录" : "正在登录`（第 1 次） | `条件-恒假`：`if (login === "pending")` → `(false)` | 没人守 |
| M140 | `startBlocker` `if (login === "pending") return { text: S.autoLogin ? "正在自动登录" : "正在登录`（第 1 次） | `三元-对调`：`? "正在自动登录" : "正在登录" ` → `? "正在登录" : "正在自动登录" ` | 没人守 |
| M141 | `startBlocker` `if (businessNowMs() === null && !S.demo) return { text: "北京时间还没校准", ac`（第 1 次） | `条件-恒假`：`if (businessNowMs() === null && !S.demo)` → `(false)` | 已守 · `test_draft_clock_blocker_resyncs_directly` · '还差一步：北京时间还没校准' not found in '<span>还差一步：已选场次有问题，看上面的提醒</spa |
| M142 | `startBlocker` `if (businessNowMs() === null && !S.demo) return { text: "北京时间还没校准", ac`（第 1 次） | `短路-去右侧`：` null && !S.demo` → ` null ` | 没人守 |
| M143 | `startBlocker` `if (S.listState !== "ready") return { text: "活动列表还没加载", act: "refresh"`（第 1 次） | `条件-恒假`：`if (S.listState !== "ready")` → `(false)` | 没人守 |
| M144 | `startBlocker` `if (!S.selected.size) {`（第 1 次） | `条件-恒假`：`if (!S.selected.size)` → `(false)` | 已守 · `test_empty_board_offers_pick_and_selected_board_offers_start` · '学校还没有可选的活动' not found in '' |
| M145 | `startBlocker` `return S.items.length ? { text: "先在时刻表勾选活动" } : { text: "学校还没有可选的活动", `（第 1 次） | `三元-对调`：`? { text: "先在时刻表勾选活动" } : { text: "学校还没有可选的活动", act: "refres` → `? { text: "学校还没有可选的活动", act: "refresh", ` | 已守 · `test_empty_board_offers_pick_and_selected_board_offers_start` · '学校还没有可选的活动' not found in '还差一步：先在时刻表勾选活动' |
| M146 | `startBlocker` `if (validation.errors.length \|\| validation.conflicts.length) return `（第 1 次） | `条件-恒假`：`if (validation.errors.length \|\| validation.conflicts.lengt` → `(false)` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '已选场次有问题' not found in '' |
| M147 | `startBlocker` `if (validation.errors.length \|\| validation.conflicts.length) return `（第 1 次） | `短路-去右侧`：`validation.errors.length \|\| validation.conflicts.length` → `validation.errors.length ` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '已选场次有问题' not found in '' |
| M148 | `paintWhy` `if (!box) return;`（第 1 次） | `条件-恒假`：`if (!box)` → `(false)` | 等价 · §1 页面元素恒在 |
| M149 | `paintWhy` `const blocker = plan && plan.disabled && !S.starting ? startBlocker() `（第 1 次） | `短路-去右侧`：` plan && plan.disabled ` → ` plan ` | 没人守 |
| M150 | `paintWhy` `const blocker = plan && plan.disabled && !S.starting ? startBlocker() `（第 1 次） | `短路-去右侧`：` plan.disabled && !S.starting ` → ` plan.disabled ` | 没人守 |
| M151 | `paintWhy` `const blocker = plan && plan.disabled && !S.starting ? startBlocker() `（第 1 次） | `读 S.starting`：`S.starting` → `false` | 没人守 |
| M152 | `paintWhy` `const blocker = plan && plan.disabled && !S.starting ? startBlocker() `（第 1 次） | `三元-对调`：`? startBlocker() : null` → `? null: startBlocker() ` | 已守 · `test_empty_board_offers_pick_and_selected_board_offers_start` · '学校还没有可选的活动' not found in '' |
| M153 | `paintWhy` `box.innerHTML = blocker ? "<span>还差一步：" + esc(blocker.text) + "</span>`（第 1 次） | `三元-对调`：`? "<span>还差一步：" + esc(blocker.text) + "</span>"
    + (block` → `? "": "<span>还差一步：" + esc(blocker.text) ` | 已守 · `test_enter_during_running_plan_does_not_start_again` · JS 行为测试崩溃：TypeError: Cannot read properties of null (reading |
| M154 | `paintWhy` `+ (blocker.act ? '<button type="button" data-act="' + blocker.act + '"`（第 1 次） | `三元-对调`：`? '<button type="button" data-act="' + blocker.act + '">' + ` → `? "": '<button type="button" data-act="'` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '刷新' not found in '还差一步：学校还没有可选的活动' |
| M155 | `planLate` `if (now === null) return true;`（第 1 次） | `条件-恒假`：`if (now === null)` → `(false)` | 没人守 |
| M156 | `planLate` `const st = String(task.status \|\| "");`（第 1 次） | `短路-去右侧`：`task.status \|\| ""` → `task.status ` | 没人守 |
| M157 | `planLate` `if (st === "submitting") late = true;`（第 1 次） | `条件-恒假`：`if (st === "submitting")` → `(false)` | 没人守 |
| M158 | `planLate` `else if (st === "queued" \|\| st === "waiting") {`（第 1 次） | `条件-恒假`：`else if (st === "queued" \|\| st === "waiting")` → `(false)` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '来不及重新登录' not found in '登录失效了，计划还在等。只要在 14:18:20 前重新登录，计划照常继 |
| M159 | `planLate` `else if (st === "queued" \|\| st === "waiting") {`（第 1 次） | `短路-去右侧`：` "queued" \|\| st === "waiting"` → ` "queued" ` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '来不及重新登录' not found in '登录失效了，计划还在等。只要在 14:18:20 前重新登录，计划照常继 |
| M160 | `planLate` `if (open !== null && open - now <= LATE_WINDOW_S) late = true;`（第 1 次） | `条件-恒假`：`if (open !== null && open - now <= LATE_WINDOW_S)` → `(false)` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '来不及重新登录' not found in '登录失效了，计划还在等。只要在 14:18:20 前重新登录，计划照常继 |
| M161 | `paintRunPanel` `if (!warn \|\| !hint) return;`（第 1 次） | `条件-恒假`：`if (!warn \|\| !hint)` → `(false)` | 等价 · §1 页面元素恒在 |
| M162 | `paintRunPanel` `if (!S.busy \|\| !S.plan.id) {`（第 1 次） | `条件-恒假`：`if (!S.busy \|\| !S.plan.id)` → `(false)` | 没人守 |
| M163 | `paintRunPanel` `if (!S.busy \|\| !S.plan.id) {`（第 1 次） | `短路-去右侧`：`!S.busy \|\| !S.plan.id` → `!S.busy ` | 没人守 |
| M164 | `paintRunPanel` `if (!S.busy \|\| !S.plan.id) {`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '电脑正在自动登录（最多约 20 秒）' not found in '' |
| M165 | `paintRunPanel` `if (why) why.hidden = true;`（第 1 次） | `条件-恒假`：`if (why)` → `(false)` | 等价 · §1 页面元素恒在 |
| M166 | `paintRunPanel` `const waitList = tasks.filter((t) => ["queued", "waiting"].indexOf(Str`（第 1 次） | `短路-去右侧`：`t.status \|\| ""` → `t.status ` | 没人守 |
| M167 | `paintRunPanel` `const submitting = tasks.some((t) => String(t.status \|\| "") === "sub`（第 2 次） | `短路-去右侧`：`t.status \|\| ""` → `t.status ` | 没人守 |
| M168 | `paintRunPanel` `const waitingAuto = tasks.some((t) => String(t.login_wait \|\| "") ===`（第 1 次） | `短路-去右侧`：`t.login_wait \|\| ""` → `t.login_wait ` | 没人守 |
| M169 | `paintRunPanel` `const login = (S.login.view \|\| {}).state;`（第 1 次） | `短路-去右侧`：`S.login.view \|\| {}` → `S.login.view ` | 没人守 |
| M170 | `paintRunPanel` `if ((waitingAuto \|\| login === "bad") && (waitList.length \|\| submit`（第 1 次） | `条件-恒假`：`if ((waitingAuto \|\| login === "bad") && (waitList.length \` → `(false)` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '电脑正在自动登录（最多约 20 秒）' not found in '' |
| M171 | `paintRunPanel` `if ((waitingAuto \|\| login === "bad") && (waitList.length \|\| submit`（第 1 次） | `短路-去右侧`：`(waitingAuto \|\| login === "bad") && (waitList.length \|\| ` → `(waitingAuto \|\| login === "bad") ` | 没人守 |
| M172 | `paintRunPanel` `if ((waitingAuto \|\| login === "bad") && (waitList.length \|\| submit`（第 1 次） | `短路-去右侧`：`waitingAuto \|\| login === "bad"` → `waitingAuto ` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '只要在' not found in '' |
| M173 | `paintRunPanel` `if ((waitingAuto \|\| login === "bad") && (waitList.length \|\| submit`（第 1 次） | `短路-去右侧`：`waitList.length \|\| submitting` → `waitList.length ` | 已守 · `test_run_warning_explains_auto_login_and_both_relogin_windows` · '电脑正在自动登录（最多约 20 秒）' not found in '' |
| M174 | `paintRunPanel` `if (waitingAuto) {`（第 1 次） | `条件-恒假`：`if (waitingAuto)` → `(false)` | 已守 · `test_run_warning_explains_auto_login_and_both_relogin_windows` · '电脑正在自动登录（最多约 20 秒）' not found in '登录失效了。正在提交，来不及重新登录，正在提交的场 |
| M175 | `paintRunPanel` `text = submitting ? "登录失效了，电脑正在自动登录（最多约 20 秒），成功后接着提交。"`（第 1 次） | `三元-对调`：`? "登录失效了，电脑正在自动登录（最多约 20 秒），成功后接着提交。"
        : "登录失效了，电脑正在自` → `? "登录失效了，电脑正在自动登录。计划照常等开放，不用你管。": "登录失效了` | 已守 · `test_run_warning_explains_auto_login_and_both_relogin_windows` · '电脑正在自动登录（最多约 20 秒）' not found in '登录失效了，电脑正在自动登录。计划照常等开放，不用 |
| M176 | `paintRunPanel` `if (late \|\| first === null) {`（第 1 次） | `条件-恒假`：`if (late \|\| first === null)` → `(false)` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '来不及重新登录' not found in '登录失效了，计划还在等。只要在 07:58:20 前重新登录，计划照常继 |
| M177 | `paintRunPanel` `const pivot = submitting ? now : first;`（第 1 次） | `三元-对调`：`? now : first` → `? first: now ` | 没人守 |
| M178 | `paintRunPanel` `text = "登录失效了。" + (submitting ? "正在提交" : "离开放不到 100 秒") + "，来不及重新登录，"`（第 1 次） | `三元-对调`：`? "正在提交" : "离开放不到 100 秒"` → `? "离开放不到 100 秒": "正在提交" ` | 没人守 |
| M179 | `paintRunPanel` `+ (submitting ? "正在提交的场次" : "这一批") + "会以“登录失效”结束。"`（第 1 次） | `三元-对调`：`? "正在提交的场次" : "这一批"` → `? "这一批": "正在提交的场次" ` | 已守 · `test_run_warning_explains_auto_login_and_both_relogin_windows` · '正在提交的场次' not found in '登录失效了。正在提交，来不及重新登录，这一批会以“登录失效”结束。' |
| M180 | `paintRunPanel` `+ (later ? "后面的场次等它结束后重新登录就行。" : "");`（第 1 次） | `三元-对调`：`? "后面的场次等它结束后重新登录就行。" : ""` → `? "": "后面的场次等它结束后重新登录就行。" ` | 没人守 |
| M181 | `paintRunPanel` `const html = text ? "<span>" + esc(text) + "</span>"`（第 1 次） | `三元-对调`：`? "<span>" + esc(text) + "</span>"
    + (act ? '<button typ` → `? "": "<span>" + esc(text) + "</span>"
 ` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '电脑正在自动登录（最多约 20 秒）' not found in '' |
| M182 | `paintRunPanel` `+ (act ? '<button type="button" data-act="' + act.act + '">' + esc(act`（第 1 次） | `三元-对调`：`? '<button type="button" data-act="' + act.act + '">' + esc(` → `? "": '<button type="button" data-act="'` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · JS 行为测试崩溃：TypeError: Cannot read properties of null (reading |
| M183 | `paintRunPanel` `if (warn.dataset.html !== html) {`（第 1 次） | `条件-恒假`：`if (warn.dataset.html !== html)` → `(false)` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '电脑正在自动登录（最多约 20 秒）' not found in '' |
| M184 | `paintRunPanel` `const fromPhone = String(S.plan.source \|\| "") === "phone";`（第 1 次） | `短路-去右侧`：`S.plan.source \|\| ""` → `S.plan.source ` | 没人守 |
| M185 | `paintRunPanel` `+ (fromPhone ? "这个计划是从手机开始的，在电脑和手机上都能看进度、停止。" : "");`（第 1 次） | `三元-对调`：`? "这个计划是从手机开始的，在电脑和手机上都能看进度、停止。" : ""` → `? "": "这个计划是从手机开始的，在电脑和手机上都能看进度、停止。" ` | 已守 · `test_run_warning_explains_auto_login_and_both_relogin_windows` · '从手机开始的' not found in '可以最小化窗口，但不要关闭工具或让电脑睡眠。' |
| M186 | `paintRunPanel` `if (modify) modify.disabled = late \|\| S.stopping \|\| !waitList.leng`（第 1 次） | `条件-恒假`：`if (modify)` → `(false)` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · False is not true |
| M187 | `paintRunPanel` `if (modify) modify.disabled = late \|\| S.stopping \|\| !waitList.leng`（第 1 次） | `短路-去右侧`：` late \|\| S.stopping ` → ` late ` | 没人守 |
| M188 | `paintRunPanel` `if (modify) modify.disabled = late \|\| S.stopping \|\| !waitList.leng`（第 1 次） | `短路-去右侧`：` S.stopping \|\| !waitList.length` → ` S.stopping ` | 没人守 |
| M189 | `paintRunPanel` `if (modify) modify.disabled = late \|\| S.stopping \|\| !waitList.leng`（第 1 次） | `读 S.stopping`：`S.stopping` → `false` | 没人守 |
| M190 | `paintRunPanel` `if (why) {`（第 2 次） | `条件-恒假`：`if (why)` → `(false)` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '正在提交，现在不能修改' not found in '' |
| M191 | `paintRunPanel` `why.textContent = submitting ? "有场次正在提交，现在不能修改。"`（第 1 次） | `三元-对调`：`? "有场次正在提交，现在不能修改。"
      : (late ? "有场次 100 秒内开放，工具已在准备，现在不` → `? (late ? "有场次 100 秒内开放，工具已在准备，现在不能修改。"
` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '正在提交，现在不能修改' not found in '有场次 100 秒内开放，工具已在准备，现在不能修改。' |
| M192 | `paintRunPanel` `: (late ? "有场次 100 秒内开放，工具已在准备，现在不能修改。"`（第 1 次） | `三元-对调`：`? "有场次 100 秒内开放，工具已在准备，现在不能修改。"
        : "还没提交的场次可以放回草稿，改完要` → `? "还没提交的场次可以放回草稿，改完要重新开始。": "有场次 100 秒内开` | 已守 · `test_login_failure_warning_and_modify_gate_follow_open_window` · '100 秒内开放' not found in '还没提交的场次可以放回草稿，改完要重新开始。' |
| M193 | `verifyTask` `if (!S.verifyAsked) S.verifyAsked = new Set();`（第 1 次） | `条件-恒假`：`if (!S.verifyAsked)` → `(false)` | 已守 · `test_verify_task_switches_the_card_wording` · JS 行为测试崩溃：TypeError: Cannot read properties of undefined (re |
| M194 | `verifyTask` `if (!S.verifyAsked) S.verifyAsked = new Set();`（第 1 次） | `读 S.verifyAsked`：`S.verifyAsked` → `false` | 没人守 |
| M195 | `verifyTask` `S.verifyAsked.add(String(taskId));`（第 2 次） | `读 S.verifyAsked`：`S.verifyAsked` → `false` | 已守 · `test_verify_task_switches_the_card_wording` · JS 行为测试崩溃：TypeError: false.add is not a function |
| M196 | `resultCounts` `const st = String(task.status \|\| "");`（第 1 次） | `短路-去右侧`：`task.status \|\| ""` → `task.status ` | 没人守 |
| M197 | `resultCounts` `const stop = String(task.stop_reason \|\| "");`（第 1 次） | `短路-去右侧`：`task.stop_reason \|\| ""` → `task.stop_reason ` | 没人守 |
| M198 | `resultCounts` `if (st === "success" \|\| st === "already_signed" \|\| verifiedSigned(`（第 1 次） | `条件-恒假`：`if (st === "success" \|\| st === "already_signed" \|\| verif` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '报名计划完成' not found in '报名计划没有成功' |
| M199 | `resultCounts` `if (st === "success" \|\| st === "already_signed" \|\| verifiedSigned(`（第 1 次） | `短路-去右侧`：` "success" \|\| st === "already_signed" ` → ` "success" ` | 没人守 |
| M200 | `resultCounts` `if (st === "success" \|\| st === "already_signed" \|\| verifiedSigned(`（第 1 次） | `短路-去右侧`：` "already_signed" \|\| verifiedSigned(task)` → ` "already_signed" ` | 没人守 |
| M201 | `resultCounts` `else if (st === "canceled") counts.canceled += 1;`（第 1 次） | `条件-恒假`：`else if (st === "canceled")` → `(false)` | 已守 · `test_result_stopped_counts_canceled` · {'已报名': 1} != {'已报名': 1, '已取消': 1} |
| M202 | `resultCounts` `else if (stop === "full") counts.full += 1;`（第 1 次） | `条件-恒假`：`else if (stop === "full")` → `(false)` | 已守 · `test_missed_is_counted_apart_and_never_double_counted` · '报名计划没有成功' != '电脑睡眠，错过了开放' |
| M203 | `resultCounts` `else if (stop === "unconfirmed") counts.pending += 1;`（第 1 次） | `条件-恒假`：`else if (stop === "unconfirmed")` → `(false)` | 已守 · `test_result_page_distinguishes_pending_from_total_failure` · '未成功' != '需确认' |
| M204 | `resultCounts` `else if (taskMissedBySleep(task)) counts.missed += 1;`（第 1 次） | `条件-恒假`：`else if (taskMissedBySleep(task))` → `(false)` | 已守 · `test_all_missed_conclusion_title_body_and_red_frame` · '报名计划没有成功' != '电脑睡眠，错过了开放' |
| M205 | `resultCounts` `else if (st === "failed") counts.bad += 1;`（第 1 次） | `条件-恒假`：`else if (st === "failed")` → `(false)` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · '报名未成功' not found in '' |
| M206 | `resultView` `if (String(S.plan.status) === "stopped") {`（第 1 次） | `条件-恒假`：`if (String(S.plan.status) === "stopped")` → `(false)` | 已守 · `test_natural_end_cancels_editing_and_opens_result` · '报名计划已停止' not found in '报名计划没有成功' |
| M207 | `resultView` `return { tag: c.pending ? "已停止，需确认" : "已停止", tone: c.pending ? "amber"`（第 1 次） | `三元-对调`：`? "已停止，需确认" : "已停止"` → `? "已停止": "已停止，需确认" ` | 已守 · `test_result_stopped_counts_canceled` · '已停止，需确认' != '已停止' |
| M208 | `resultView` `return { tag: c.pending ? "已停止，需确认" : "已停止", tone: c.pending ? "amber"`（第 1 次） | `三元-对调`：`? "amber" : "off"` → `? "off": "amber" ` | 没人守 |
| M209 | `resultView` `frame: c.pending ? "warn" : "", led: null };`（第 1 次） | `三元-对调`：`? "warn" : ""` → `? "": "warn" ` | 已守 · `test_single_failure_does_not_paint_plan` · 'attention' != 'stopped' |
| M210 | `resultView` `const allSettled = Array.from(S.plan.tasks.values()).every((task) => T`（第 1 次） | `短路-去右侧`：`task.status \|\| ""` → `task.status ` | 没人守 |
| M211 | `resultView` `if (c.ok && !c.bad && !c.missed && !c.pending && !c.canceled && !c.ful`（第 1 次） | `条件-恒假`：`if (c.ok && !c.bad && !c.missed && !c.pending && !c.canceled` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '报名计划完成' not found in '报名计划部分完成' |
| M212 | `resultView` `if (c.ok) {`（第 1 次） | `条件-恒假`：`if (c.ok)` → `(false)` | 已守 · `test_result_page_distinguishes_pending_from_total_failure` · '未成功' != '部分完成' |
| M213 | `resultView` `text: c.pending ? "有 " + c.pending + " 场需要到活动页核对，结果以学校为准。"`（第 1 次） | `三元-对调`：`? "有 " + c.pending + " 场需要到活动页核对，结果以学校为准。"
               : ` → `? (c.full ? "有 " + c.full + " 场名额已满，不是工具` | 已守 · `test_result_dock_shows_the_conclusion_from_the_result_page` · '结果以学校活动页为准。' != '有 1 场需要到活动页核对，结果以学校为准。' |
| M214 | `resultView` `: (c.full ? "有 " + c.full + " 场名额已满，不是工具出错。" : "结果以学校活动页为准。"),`（第 1 次） | `三元-对调`：`? "有 " + c.full + " 场名额已满，不是工具出错。" : "结果以学校活动页为准。"` → `? "结果以学校活动页为准。": "有 " + c.full + " 场名额已满` | 没人守 |
| M215 | `resultView` `if (c.pending) {`（第 1 次） | `条件-恒假`：`if (c.pending)` → `(false)` | 已守 · `test_result_page_distinguishes_pending_from_total_failure` · '未成功' != '需确认' |
| M216 | `resultView` `if (c.missed && !c.bad) {`（第 1 次） | `条件-恒假`：`if (c.missed && !c.bad)` → `(false)` | 已守 · `test_all_missed_conclusion_title_body_and_red_frame` · '报名计划没有成功' != '电脑睡眠，错过了开放' |
| M217 | `resultView` `if (c.full && !c.bad && !c.missed) {`（第 1 次） | `条件-恒假`：`if (c.full && !c.bad && !c.missed)` → `(false)` | 已守 · `test_result_only_full_has_no_reselect` · '报名计划没有成功' != '这次没报上：名额满了' |
| M218 | `reselectableIds` `const st = String(task.status \|\| "");`（第 1 次） | `短路-去右侧`：`task.status \|\| ""` → `task.status ` | 没人守 |
| M219 | `reselectableIds` `const stop = String(task.stop_reason \|\| "");`（第 1 次） | `短路-去右侧`：`task.stop_reason \|\| ""` → `task.stop_reason ` | 没人守 |
| M220 | `reselectableIds` `if (["failed", "canceled"].indexOf(st) < 0 \|\| stop === "full" \|\| s`（第 1 次） | `条件-恒假`：`if (["failed", "canceled"].indexOf(st) < 0 \|\| stop === "fu` → `(false)` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · Lists differ: ['a1', 'a2', 'a3'] != ['a1'] |
| M221 | `reselectableIds` `if (["failed", "canceled"].indexOf(st) < 0 \|\| stop === "full" \|\| s`（第 1 次） | `短路-去右侧`：` 0 \|\| stop === "full" ` → ` 0 ` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · Lists differ: ['a1', 'a2'] != ['a1'] |
| M222 | `reselectableIds` `if (["failed", "canceled"].indexOf(st) < 0 \|\| stop === "full" \|\| s`（第 1 次） | `短路-去右侧`：` "full" \|\| stop === "unconfirmed"` → ` "full" ` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · Lists differ: ['a1', 'a3'] != ['a1'] |
| M223 | `reselectableIds` `if (item && isEligibleForPlan(item) && !signedClash(item)) ids.push(St`（第 1 次） | `条件-恒假`：`if (item && isEligibleForPlan(item) && !signedClash(item))` → `(false)` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · True is not false |
| M224 | `paintResultPanel` `if (stats) {`（第 1 次） | `条件-恒假`：`if (stats)` → `(false)` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · '待核对' not found in '' |
| M225 | `paintResultPanel` `stats.hidden = !done \|\| !cells.length;`（第 1 次） | `短路-去右侧`：` !done \|\| !cells.length` → ` !done ` | 没人守 |
| M226 | `paintResultPanel` `stats.innerHTML = done ? cells.map((cell) => '<div data-tone="' + cell`（第 1 次） | `三元-对调`：`? cells.map((cell) => '<div data-tone="' + cell[2] + '"><str` → `? "": cells.map((cell) => '<div data-ton` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · '待核对' not found in '' |
| M227 | `paintResultPanel` `if (actions) {`（第 1 次） | `条件-恒假`：`if (actions)` → `(false)` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · Lists differ: ['#btn-finish'] != ['#board'] |
| M228 | `paintResultPanel` `if (reselect) reselect.hidden = !done \|\| !reselectableIds().length;`（第 1 次） | `条件-恒假`：`if (reselect)` → `(false)` | 已守 · `test_result_all_success_shows_mini_led` · False is not true : 名额已满不放回重新选择 |
| M229 | `paintResultPanel` `if (reselect) reselect.hidden = !done \|\| !reselectableIds().length;`（第 1 次） | `短路-去右侧`：` !done \|\| !reselectableIds().length` → ` !done ` | 已守 · `test_result_all_success_shows_mini_led` · False is not true : 名额已满不放回重新选择 |
| M230 | `paintPlan` `if (S.selectionNotice) messages.push("<div class=\"conflict-item\"><st`（第 1 次） | `条件-恒假`：`if (S.selectionNotice)` → `(false)` | 没人守 |
| M231 | `paintPlan` `const showTasks = tasks.length && (S.busy \|\| resultMode());`（第 1 次） | `短路-去右侧`：` tasks.length && (S.busy \|\| resultMode())` → ` tasks.length ` | 没人守 |
| M232 | `paintPlan` `const showTasks = tasks.length && (S.busy \|\| resultMode());`（第 1 次） | `短路-去右侧`：`S.busy \|\| resultMode()` → `S.busy ` | 已守 · `test_unconfirmed_task_switches_from_cancel_to_verify` · '刷新核对' not found in '' |
| M233 | `paintPlan` `const showTasks = tasks.length && (S.busy \|\| resultMode());`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_task_events_keep_the_terminal_fact_and_update_the_card` · '等待开放' not found in '' |
| M234 | `paintPlan` `tasksBox.innerHTML = showTasks ? tasks.map((task) => taskHtml(task, no`（第 1 次） | `三元-对调`：`? tasks.map((task) => taskHtml(task, now)).join("") : ""` → `? "": tasks.map((task) => taskHtml(task,` | 已守 · `test_task_events_keep_the_terminal_fact_and_update_the_card` · '等待开放' not found in '' |
| M235 | `stopReasonText` `function stopReasonText(reason) {`（第 1 次） | `短路-去右侧`：`
  return {
    success: "报名成功",
    already_signed: "已经报过",` → `
  return {
    success: "报名成功",
    alr` | 没人守 |
| M236 | `taskHtml` `const state = String(task.status \|\| "queued");`（第 1 次） | `短路-去右侧`：`task.status \|\| "queued"` → `task.status ` | 没人守 |
| M237 | `taskHtml` `const stop = String(task.stop_reason \|\| "");`（第 1 次） | `短路-去右侧`：`task.stop_reason \|\| ""` → `task.stop_reason ` | 没人守 |
| M238 | `taskHtml` `let detail = task.reason \|\| task.detail \|\| "";`（第 1 次） | `短路-去右侧`：` task.detail \|\| ""` → ` task.detail ` | 没人守 |
| M239 | `taskHtml` `if (RUNNING_STATUSES.indexOf(state) >= 0) {`（第 1 次） | `条件-恒假`：`if (RUNNING_STATUSES.indexOf(state) >= 0)` → `(false)` | 已守 · `test_prepared_task_uses_checkpoint_in_visible_detail` · '电脑正在自动登录' not found in '活动甲准备报名立即报名 · 取消这一场' |
| M240 | `taskHtml` `detail = taskDisplayDetail(task, now)`（第 1 次） | `短路-去右侧`：` taskDisplayDetail(task, now)
      \|\| (state === "waiting` → ` taskDisplayDetail(task, now)
      ` | 没人守 |
| M241 | `taskHtml` `\|\| (state === "waiting" ? (mode === "pre_register" ? "等待报名开放" : "报名已`（第 1 次） | `三元-对调`：`? (mode === "pre_register" ? "等待报名开放" : "报名已开放，马上开始") : deta` → `? detail: (mode === "pre_register" ? "等待` | 没人守 |
| M242 | `taskHtml` `\|\| (state === "waiting" ? (mode === "pre_register" ? "等待报名开放" : "报名已`（第 1 次） | `三元-对调`：`? "等待报名开放" : "报名已开放，马上开始"` → `? "报名已开放，马上开始": "等待报名开放" ` | 没人守 |
| M243 | `taskHtml` `} else if (verifiedSigned(task)) {`（第 1 次） | `条件-恒假`：`else if (verifiedSigned(task))` → `(false)` | 已守 · `test_verify_task_switches_the_card_wording` · '学校显示已报名' not found in '活动甲报名成功刷新核对：学校列表还没显示已报名，可能有延迟，去活动页看一 |
| M244 | `taskHtml` `} else if (state === "failed" && taskMissedBySleep(task)) {`（第 1 次） | `条件-恒假`：`else if (state === "failed" && taskMissedBySleep(task))` → `(false)` | 已守 · `test_task_cards_use_the_missed_verb_and_the_prototype_reason` · '' != '电脑睡眠期间到了开放时间，没有提交。' |
| M245 | `taskHtml` `} else if (state === "failed" && taskMissedBySleep(task)) {`（第 1 次） | `短路-去右侧`：` "failed" && taskMissedBySleep(task)` → ` "failed" ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '学校列表还没显示已报名' not found in '活动甲待核对电脑睡眠期间到了开放时间，没有提交。刷新核对' |
| M246 | `taskHtml` `} else if (state === "failed" && stop === "full") {`（第 1 次） | `条件-恒假`：`else if (state === "failed" && stop === "full")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '不是工具出错' not found in '活动甲名额已满提交了 2 次，名额已满' |
| M247 | `taskHtml` `} else if (state === "failed" && stop === "full") {`（第 1 次） | `短路-去右侧`：` "failed" && stop === "full"` → ` "failed" ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '学校列表还没显示已报名' not found in '活动甲待核对学校说报名人数已满，这一场到此结束，不再提交。不是工 |
| M248 | `taskHtml` `detail = "学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。" + (tried ? "已提交 " + tried + `（第 1 次） | `三元-对调`：`? "已提交 " + tried + " 次" : ""` → `? "": "已提交 " + tried + " 次" ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '已提交 2 次' not found in '活动甲名额已满学校说报名人数已满，这一场到此结束，不再提交。不是工具出错 |
| M249 | `taskHtml` `} else if (state === "canceled") {`（第 1 次） | `条件-恒假`：`else if (state === "canceled")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '你取消了这一场' not found in '活动甲已取消' |
| M250 | `taskHtml` `detail = String(S.plan.status \|\| "") === "stopped" ? "计划已停止，这一场没有提交"`（第 1 次） | `短路-去右侧`：`S.plan.status \|\| ""` → `S.plan.status ` | 没人守 |
| M251 | `taskHtml` `detail = String(S.plan.status \|\| "") === "stopped" ? "计划已停止，这一场没有提交"`（第 1 次） | `三元-对调`：`? "计划已停止，这一场没有提交" : "你取消了这一场"` → `? "你取消了这一场": "计划已停止，这一场没有提交" ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '你取消了这一场' not found in '活动甲已取消计划已停止，这一场没有提交' |
| M252 | `taskHtml` `} else if (state === "failed") {`（第 1 次） | `条件-恒假`：`else if (state === "failed")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '学校列表还没显示已报名' not found in '活动甲待核对刷新核对' |
| M253 | `taskHtml` `if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(Strin`（第 1 次） | `条件-恒假`：`if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked` → `(false)` | 已守 · `test_verify_task_switches_the_card_wording` · '学校列表还没显示已报名' not found in '活动甲待核对已提交 1 次，没拿到确定回应；结束时向学校核对也没 |
| M254 | `taskHtml` `if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(Strin`（第 1 次） | `短路-去右侧`：` "unconfirmed" && S.verifyAsked ` → ` "unconfirmed" ` | 已守 · `test_result_actions_reselect_only_eligible_tasks` · JS 行为测试崩溃：TypeError: Cannot read properties of undefined (re |
| M255 | `taskHtml` `if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(Strin`（第 1 次） | `短路-去右侧`：` S.verifyAsked && S.verifyAsked.has(String(task.task_id))
  ` → ` S.verifyAsked ` | 没人守 |
| M256 | `taskHtml` `if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(Strin`（第 1 次） | `读 S.verifyAsked`：`S.verifyAsked` → `false` | 已守 · `test_verify_task_switches_the_card_wording` · '学校列表还没显示已报名' not found in '活动甲待核对已提交 1 次，没拿到确定回应；结束时向学校核对也没 |
| M257 | `taskHtml` `if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(Strin`（第 1 次） | `短路-去右侧`：` S.verifyAsked.has(String(task.task_id))
        && S.listSt` → ` S.verifyAsked.has(String(task.task_id))` | 没人守 |
| M258 | `taskHtml` `if (stop === "unconfirmed" && S.verifyAsked && S.verifyAsked.has(Strin`（第 2 次） | `读 S.verifyAsked`：`S.verifyAsked` → `false` | 已守 · `test_verify_task_switches_the_card_wording` · JS 行为测试崩溃：TypeError: false.has is not a function |
| M259 | `taskHtml` `} else if (stop === "unconfirmed") {`（第 1 次） | `条件-恒假`：`else if (stop === "unconfirmed")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '没拿到确定回应' not found in '活动甲待核对提交了 2 次，报名结果待核对' |
| M260 | `taskHtml` `} else if (stop === "auth_unavailable") {`（第 1 次） | `条件-恒假`：`else if (stop === "auth_unavailable")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '登录状态无法确认' not found in '活动甲未提交提交了 2 次，登录状态暂时无法确认' |
| M261 | `taskHtml` `if (task.attempts) bits.push("提交了 " + task.attempts + " 次");`（第 1 次） | `条件-恒假`：`if (task.attempts)` → `(false)` | 没人守 |
| M262 | `taskHtml` `const stopNote = String(task.outcome_label \|\| "") \|\| stopReasonTex`（第 1 次） | `短路-去右侧`：` String(task.outcome_label \|\| "") \|\| stopReasonText(task` → ` String(task.outcome_label \|\| "") ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '登录失效，先重新登录' not found in '活动甲报名未成功提交了 2 次' |
| M263 | `taskHtml` `const stopNote = String(task.outcome_label \|\| "") \|\| stopReasonTex`（第 1 次） | `短路-去右侧`：`task.outcome_label \|\| ""` → `task.outcome_label ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '登录失效，先重新登录' not found in '活动甲报名未成功提交了 2 次，undefined' |
| M264 | `taskHtml` `if (stopNote && stop !== "success" && stop !== "already_signed") bits.`（第 1 次） | `条件-恒假`：`if (stopNote && stop !== "success" && stop !== "already_sign` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '登录失效，先重新登录' not found in '活动甲报名未成功提交了 2 次' |
| M265 | `taskHtml` `if (stopNote && stop !== "success" && stop !== "already_signed") bits.`（第 1 次） | `短路-去右侧`：`stopNote && stop !== "success" ` → `stopNote ` | 没人守 |
| M266 | `taskHtml` `if (stopNote && stop !== "success" && stop !== "already_signed") bits.`（第 1 次） | `短路-去右侧`：` "success" && stop !== "already_signed"` → ` "success" ` | 没人守 |
| M267 | `taskHtml` `if (bits.length) detail = (detail ? detail + "（" : "") + bits.join("，"`（第 1 次） | `条件-恒假`：`if (bits.length)` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '登录失效，先重新登录' not found in '活动甲报名未成功' |
| M268 | `taskHtml` `if (bits.length) detail = (detail ? detail + "（" : "") + bits.join("，"`（第 1 次） | `三元-对调`：`? detail + "（" : ""` → `? "": detail + "（" ` | 没人守 |
| M269 | `taskHtml` `if (bits.length) detail = (detail ? detail + "（" : "") + bits.join("，"`（第 1 次） | `三元-对调`：`? "）" : ""` → `? "": "）" ` | 没人守 |
| M270 | `taskHtml` `} else if (state === "success") {`（第 1 次） | `条件-恒假`：`else if (state === "success")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '学校回“报名成功”' not found in '活动甲报名成功' |
| M271 | `taskHtml` `const said = String(task.last_reason \|\| "").trim().replace(/[！!。.]+$`（第 1 次） | `短路-去右侧`：`task.last_reason \|\| ""` → `task.last_reason ` | 没人守 |
| M272 | `taskHtml` `detail = (said ? "学校回“" + said + "”，" : "") + "结束时向学校核对过：已报名";`（第 1 次） | `三元-对调`：`? "学校回“" + said + "”，" : ""` → `? "": "学校回“" + said + "”，" ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '学校回“报名成功”' not found in '活动甲报名成功结束时向学校核对过：已报名' |
| M273 | `taskHtml` `const canCancel = ["queued", "waiting"].indexOf(state) >= 0 && S.busy;`（第 1 次） | `短路-去右侧`：` 0 && S.busy` → ` 0 ` | 没人守 |
| M274 | `taskHtml` `const canCancel = ["queued", "waiting"].indexOf(state) >= 0 && S.busy;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_waiting_plan_shows_waiting_target_and_cancel_action` · '取消这一场' not found in '未来活动等待开放预报名 · 提前准备，等到 明天 09:00:00 开放' |
| M275 | `taskHtml` `const canVerify = !S.busy && stop === "unconfirmed" && !verifiedSigned`（第 1 次） | `短路-去右侧`：` !S.busy && stop === "unconfirmed" ` → ` !S.busy ` | 没人守 |
| M276 | `taskHtml` `const canVerify = !S.busy && stop === "unconfirmed" && !verifiedSigned`（第 2 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M277 | `taskHtml` `const canVerify = !S.busy && stop === "unconfirmed" && !verifiedSigned`（第 1 次） | `短路-去右侧`：` "unconfirmed" && !verifiedSigned(task)` → ` "unconfirmed" ` | 没人守 |
| M278 | `taskHtml` `const actionsHtml = (canCancel ? "<button class=\"task-cancel\" type=\`（第 1 次） | `三元-对调`：`? "<button class=\"task-cancel\" type=\"button\" data-task-i` → `? "": "<button class=\"task-cancel\" typ` | 已守 · `test_unconfirmed_task_switches_from_cancel_to_verify` · '取消这一场' not found in '未来活动等待开放预报名 · 提前准备，等到 明天 09:00:00 开放' |
| M279 | `taskHtml` `+ (canVerify ? "<button class=\"task-cancel task-verify\" type=\"butto`（第 1 次） | `三元-对调`：`? "<button class=\"task-cancel task-verify\" type=\"button\"` → `? "": "<button class=\"task-cancel task-` | 没人守 |
| M280 | `taskHtml` `return "<div class=\"task-row\" data-task-id=\"" + esc(task.task_id) +`（第 1 次） | `三元-对调`：`? "<div class=\"task-actions\">" + actionsHtml + "</div>" : ` → `? "": "<div class=\"task-actions\">" + a` | 已守 · `test_waiting_plan_shows_waiting_target_and_cancel_action` · '取消这一场' not found in '未来活动等待开放预报名 · 提前准备，等到 明天 09:00:00 开放' |
| M281 | `updateControls` `$("#btn-login").disabled = S.busy \|\| componentDown \|\| termsGate;`（第 1 次） | `短路-去右侧`：` S.busy \|\| componentDown ` → ` S.busy ` | 已守 · `test_controls_disable_login_refresh_and_clear_at_their_own_gates` · False is not true : 缺组件时登录按钮应禁用 |
| M282 | `updateControls` `$("#btn-login").disabled = S.busy \|\| componentDown \|\| termsGate;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_controls_disable_login_refresh_and_clear_at_their_own_gates` · False is not true : 计划运行中不允许再开登录窗口 |
| M283 | `updateControls` `$("#btn-refresh").disabled = S.listState === "loading" \|\| termsGate `（第 1 次） | `短路-去右侧`：` "loading" \|\| termsGate ` → ` "loading" ` | 已守 · `test_controls_disable_login_refresh_and_clear_at_their_own_gates` · False is not true |
| M284 | `updateControls` `$("#btn-refresh").disabled = S.listState === "loading" \|\| termsGate `（第 1 次） | `短路-去右侧`：` termsGate \|\| !!S.cancel.busyId` → ` termsGate ` | 已守 · `test_controls_disable_login_refresh_and_clear_at_their_own_gates` · False is not true : 正在取消报名时刷新要让开 |
| M285 | `updateControls` `const loginReady = !!S.demo \|\| (!S.login.checking && S.login.result `（第 1 次） | `短路-去右侧`：` !!S.demo \|\| (!S.login.checking && S.login.result === "val` → ` !!S.demo ` | 已守 · `test_start_and_stop_buttons_follow_the_run_phase` · True is not false |
| M286 | `updateControls` `const loginReady = !!S.demo \|\| (!S.login.checking && S.login.result `（第 1 次） | `短路-去右侧`：`!S.login.checking && S.login.result === "valid"` → `!S.login.checking ` | 已守 · `test_draft_priority_blocker_then_warnings_then_summary` · False is not true : 有 1 条提醒，开始前先看一眼 |
| M287 | `updateControls` `const canStart = !S.busy && !S.starting && !S.cancel.busyId && !compon`（第 1 次） | `短路-去右侧`：` !S.busy && !S.starting ` → ` !S.busy ` | 已守 · `test_start_timeout_enters_reconciliation_without_restarting` · False is not true |
| M288 | `updateControls` `const canStart = !S.busy && !S.starting && !S.cancel.busyId && !compon`（第 2 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M289 | `updateControls` `const canStart = !S.busy && !S.starting && !S.cancel.busyId && !compon`（第 1 次） | `短路-去右侧`：` !S.starting && !S.cancel.busyId ` → ` !S.starting ` | 没人守 |
| M290 | `updateControls` `const canStart = !S.busy && !S.starting && !S.cancel.busyId && !compon`（第 1 次） | `读 S.starting`：`S.starting` → `false` | 已守 · `test_start_timeout_enters_reconciliation_without_restarting` · False is not true |
| M291 | `updateControls` `const canStart = !S.busy && !S.starting && !S.cancel.busyId && !compon`（第 1 次） | `短路-去右侧`：` !S.cancel.busyId && !componentDown ` → ` !S.cancel.busyId ` | 没人守 |
| M292 | `updateControls` `const canStart = !S.busy && !S.starting && !S.cancel.busyId && !compon`（第 1 次） | `短路-去右侧`：` loginReady && S.selected.size > 0
    ` → ` loginReady ` | 已守 · `test_empty_board_offers_pick_and_selected_board_offers_start` · False is not true |
| M293 | `updateControls` `const canStart = !S.busy && !S.starting && !S.cancel.busyId && !compon`（第 1 次） | `短路-去右侧`：` 0
    && validation.errors.length === 0 ` → ` 0
    ` | 没人守 |
| M294 | `updateControls` `&& validation.errors.length === 0 && validation.conflicts.length === 0`（第 1 次） | `短路-去右侧`：` 0 && validation.conflicts.length === 0
    ` → ` 0 ` | 已守 · `test_start_blocker_names_each_missing_step_with_its_action` · '已选场次有问题' not found in '' |
| M295 | `updateControls` `&& validation.errors.length === 0 && validation.conflicts.length === 0`（第 1 次） | `短路-去右侧`：` 0
    && S.listState === "ready"` → ` 0
    ` | 没人守 |
| M296 | `updateControls` `const clockDown = businessNowMs() === null && !S.demo;`（第 1 次） | `短路-去右侧`：` null && !S.demo` → ` null ` | 没人守 |
| M297 | `updateControls` `const warned = (Number(S.preWarnCount) \|\| 0) > 0;`（第 1 次） | `短路-去右侧`：`Number(S.preWarnCount) \|\| 0` → `Number(S.preWarnCount) ` | 没人守 |
| M298 | `updateControls` `$("#btn-plan").textContent = S.busy ? "计划运行中"`（第 3 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_enter_during_running_plan_does_not_start_again` · '开始报名计划' != '计划运行中' |
| M299 | `updateControls` `$("#btn-plan").textContent = S.busy ? "计划运行中"`（第 1 次） | `三元-对调`：`? "计划运行中"
    : (S.startRequest.state === "reconciling" ? "正` → `? (S.startRequest.state === "reconciling` | 已守 · `test_enter_during_running_plan_does_not_start_again` · '计划运行中' != '正在提交…' |
| M300 | `updateControls` `: (S.startRequest.state === "reconciling" ? "正在确认是否启动…"`（第 1 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 已守 · `test_start_plan_sends_full_items_and_waits_on_pending` · '正在提交…' != '正在确认是否启动…' |
| M301 | `updateControls` `: (S.startRequest.state === "reconciling" ? "正在确认是否启动…"`（第 1 次） | `三元-对调`：`? "正在确认是否启动…"
      : (S.starting ? "正在提交…"
        : (clock` → `? (S.starting ? "正在提交…"
        : (clock` | 已守 · `test_start_plan_sends_full_items_and_waits_on_pending` · '正在确认是否启动…' != '正在提交…' |
| M302 | `updateControls` `: (S.starting ? "正在提交…"`（第 2 次） | `读 S.starting`：`S.starting` → `false` | 已守 · `test_start_timeout_enters_reconciliation_without_restarting` · '开始报名计划' != '正在提交…' |
| M303 | `updateControls` `: (S.starting ? "正在提交…"`（第 1 次） | `三元-对调`：`? "正在提交…"
        : (clockDown ? "北京时间未校准" : (S.editing ? "重` → `? (clockDown ? "北京时间未校准" : (S.editing ? ` | 已守 · `test_start_timeout_enters_reconciliation_without_restarting` · '开始报名计划' != '正在提交…' |
| M304 | `updateControls` `: (clockDown ? "北京时间未校准" : (S.editing ? "重新开始计划"`（第 1 次） | `三元-对调`：`? "北京时间未校准" : (S.editing ? "重新开始计划"
          : (warned ? "仍` → `? (S.editing ? "重新开始计划"
          : (war` | 已守 · `test_start_and_stop_buttons_follow_the_run_phase` · '北京时间未校准' != '开始报名计划' |
| M305 | `updateControls` `: (clockDown ? "北京时间未校准" : (S.editing ? "重新开始计划"`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_start_and_stop_buttons_follow_the_run_phase` · '开始报名计划' != '重新开始计划' |
| M306 | `updateControls` `: (clockDown ? "北京时间未校准" : (S.editing ? "重新开始计划"`（第 1 次） | `三元-对调`：`? "重新开始计划"
          : (warned ? "仍然开始报名计划" : "开始报名计划")` → `? (warned ? "仍然开始报名计划" : "开始报名计划"): "重新开` | 已守 · `test_start_and_stop_buttons_follow_the_run_phase` · '重新开始计划' != '开始报名计划' |
| M307 | `updateControls` `: (warned ? "仍然开始报名计划" : "开始报名计划")))));`（第 1 次） | `三元-对调`：`? "仍然开始报名计划" : "开始报名计划"` → `? "开始报名计划": "仍然开始报名计划" ` | 已守 · `test_start_and_stop_buttons_follow_the_run_phase` · '仍然开始报名计划' != '开始报名计划' |
| M308 | `updateControls` `$("#btn-stop").disabled = !S.busy \|\| !S.plan.id \|\| S.stopping;`（第 1 次） | `短路-去右侧`：` !S.busy \|\| !S.plan.id ` → ` !S.busy ` | 没人守 |
| M309 | `updateControls` `$("#btn-stop").disabled = !S.busy \|\| !S.plan.id \|\| S.stopping;`（第 4 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · True is not false |
| M310 | `updateControls` `$("#btn-stop").disabled = !S.busy \|\| !S.plan.id \|\| S.stopping;`（第 1 次） | `短路-去右侧`：` !S.plan.id \|\| S.stopping` → ` !S.plan.id ` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · False is not true |
| M311 | `updateControls` `$("#btn-stop").disabled = !S.busy \|\| !S.plan.id \|\| S.stopping;`（第 1 次） | `读 S.stopping`：`S.stopping` → `false` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · False is not true |
| M312 | `updateControls` `$("#btn-stop").textContent = S.stopping ? "正在停止…" : "停止计划";`（第 2 次） | `读 S.stopping`：`S.stopping` → `false` | 已守 · `test_stop_rejection_clears_stopping_and_editing` · '停止计划' != '正在停止…' |
| M313 | `updateControls` `$("#btn-stop").textContent = S.stopping ? "正在停止…" : "停止计划";`（第 1 次） | `三元-对调`：`? "正在停止…" : "停止计划"` → `? "停止计划": "正在停止…" ` | 已守 · `test_stop_rejection_clears_stopping_and_editing` · '停止计划' != '正在停止…' |
| M314 | `updateControls` `if (runActions) runActions.hidden = !S.busy;`（第 1 次） | `条件-恒假`：`if (runActions)` → `(false)` | 没人守 |
| M315 | `updateControls` `if (runActions) runActions.hidden = !S.busy;`（第 5 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_start_and_stop_buttons_follow_the_run_phase` · True is not false |
| M316 | `updateControls` `$("#btn-clear-plan").disabled = S.busy \|\| S.starting \|\| (!S.select`（第 1 次） | `短路-去右侧`：` S.busy \|\| S.starting ` → ` S.busy ` | 已守 · `test_controls_disable_login_refresh_and_clear_at_their_own_gates` · False is not true : 正在提交时不许清空选择 |
| M317 | `updateControls` `$("#btn-clear-plan").disabled = S.busy \|\| S.starting \|\| (!S.select`（第 6 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M318 | `updateControls` `$("#btn-clear-plan").disabled = S.busy \|\| S.starting \|\| (!S.select`（第 1 次） | `短路-去右侧`：` S.starting \|\| (!S.selected.size && !S.plan.tasks.size)` → ` S.starting ` | 已守 · `test_controls_disable_login_refresh_and_clear_at_their_own_gates` · False is not true : 没选活动时清空按钮不该出现 |
| M319 | `updateControls` `$("#btn-clear-plan").disabled = S.busy \|\| S.starting \|\| (!S.select`（第 3 次） | `读 S.starting`：`S.starting` → `false` | 已守 · `test_controls_disable_login_refresh_and_clear_at_their_own_gates` · False is not true : 正在提交时不许清空选择 |
| M320 | `updateControls` `$("#btn-clear-plan").disabled = S.busy \|\| S.starting \|\| (!S.select`（第 1 次） | `短路-去右侧`：`!S.selected.size && !S.plan.tasks.size` → `!S.selected.size ` | 没人守 |
| M321 | `updateControls` `check.disabled = S.busy \|\| S.starting \|\| termsLocked() \|\| !isEli`（第 2 次） | `短路-去右侧`：` S.busy \|\| S.starting ` → ` S.busy ` | 没人守 |
| M322 | `updateControls` `check.disabled = S.busy \|\| S.starting \|\| termsLocked() \|\| !isEli`（第 7 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M323 | `updateControls` `check.disabled = S.busy \|\| S.starting \|\| termsLocked() \|\| !isEli`（第 1 次） | `短路-去右侧`：` S.starting \|\| termsLocked() ` → ` S.starting ` | 没人守 |
| M324 | `updateControls` `check.disabled = S.busy \|\| S.starting \|\| termsLocked() \|\| !isEli`（第 4 次） | `读 S.starting`：`S.starting` → `false` | 没人守 |
| M325 | `updateControls` `if (!id) return;`（第 1 次） | `条件-恒假`：`if (!id)` → `(false)` | 没人守 |
| M326 | `updateControls` `btn.textContent = S.cancel.busyId === id ? "正在取消…" : "取消报名";`（第 1 次） | `三元-对调`：`? "正在取消…" : "取消报名"` → `? "取消报名": "正在取消…" ` | 没人守 |
| M327 | `updateControls` `if (!S.busy) {`（第 1 次） | `条件-恒假`：`if (!S.busy)` → `(false)` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · False is not true : 计划结束后停止确认弹层要收起 |
| M328 | `updateControls` `if (!S.busy) {`（第 8 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M329 | `updateControls` `if (ask && !ask.hidden) {`（第 1 次） | `条件-恒假`：`if (ask && !ask.hidden)` → `(false)` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · False is not true : 计划结束后停止确认弹层要收起 |
| M330 | `updateControls` `if (ask && !ask.hidden) {`（第 1 次） | `短路-去右侧`：`ask && !ask.hidden` → `ask ` | 没人守 |
| M331 | `updateControls` `const inside = !!active && (active.id === "btn-stop-keep" \|\| active.`（第 1 次） | `短路-去右侧`：` !!active && (active.id === "btn-stop-keep" \|\| active.id =` → ` !!active ` | 没人守 |
| M332 | `updateControls` `const inside = !!active && (active.id === "btn-stop-keep" \|\| active.`（第 1 次） | `短路-去右侧`：` "btn-stop-keep" \|\| active.id === "btn-stop-yes"` → ` "btn-stop-keep" ` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · Lists differ: [] != ['#board'] |
| M333 | `updateControls` `if (inside) {`（第 1 次） | `条件-恒假`：`if (inside)` → `(false)` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · Lists differ: [] != ['#board'] |
| M334 | `updateControls` `const target = finish && !finish.hidden && !($("#result-actions") \|\|`（第 1 次） | `短路-去右侧`：` finish && !finish.hidden ` → ` finish ` | 没人守 |
| M335 | `updateControls` `const target = finish && !finish.hidden && !($("#result-actions") \|\|`（第 1 次） | `短路-去右侧`：` !finish.hidden && !($("#result-actions") \|\| {}).hidden ` → ` !finish.hidden ` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · Lists differ: ['#btn-finish'] != ['#board'] |
| M336 | `updateControls` `const target = finish && !finish.hidden && !($("#result-actions") \|\|`（第 1 次） | `短路-去右侧`：`$("#result-actions") \|\| {}` → `$("#result-actions") ` | 没人守 |
| M337 | `updateControls` `const target = finish && !finish.hidden && !($("#result-actions") \|\|`（第 1 次） | `三元-对调`：`? finish : $("#board")` → `? $("#board"): finish ` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · Lists differ: ['#btn-finish'] != ['#board'] |
| M338 | `updateControls` `if (target && target.focus) {`（第 1 次） | `条件-恒假`：`if (target && target.focus)` → `(false)` | 已守 · `test_stop_button_and_stop_ask_follow_the_plan` · Lists differ: [] != ['#board'] |
| M339 | `updateControls` `if (target === $("#board")) target.tabIndex = -1;`（第 1 次） | `条件-恒假`：`if (target === $("#board"))` → `(false)` | 没人守 |

### state/plan.js（54 条）

| 编号 | 定位：函数 / 那一行的文字 / 第几次出现 | 变异写法 | 补测后 |
|---|---|---|---|
| M340 | `mergeTask` `const value = incoming ? incoming[key] : undefined;`（第 1 次） | `三元-对调`：`? incoming[key] : undefined` → `? undefined: incoming[key] ` | 没人守 |
| M341 | `mergeTask` `if ((value === undefined \|\| value === null \|\| value === "") && pre`（第 1 次） | `条件-恒假`：`if ((value === undefined \|\| value === null \|\| value === ` → `(false)` | 没人守 |
| M342 | `mergeTask` `if ((value === undefined \|\| value === null \|\| value === "") && pre`（第 1 次） | `短路-去右侧`：`(value === undefined \|\| value === null \|\| value === "") ` → `(value === undefined \|\| value === null` | 已守 · `test_natural_end_cancels_editing_and_opens_result` · JS 行为测试崩溃：TypeError: Cannot read properties of null (reading |
| M343 | `mergeTask` `if ((value === undefined \|\| value === null \|\| value === "") && pre`（第 1 次） | `短路-去右侧`：` null \|\| value === ""` → ` null ` | 没人守 |
| M344 | `mergeTask` `if (String(merged.status) === "submitting" && !merged.submitSeen) merg`（第 1 次） | `条件-恒假`：`if (String(merged.status) === "submitting" && !merged.submit` → `(false)` | 没人守 |
| M345 | `mergeTask` `if (String(merged.status) === "submitting" && !merged.submitSeen) merg`（第 1 次） | `短路-去右侧`：` "submitting" && !merged.submitSeen` → ` "submitting" ` | 没人守 |
| M346 | `maxPlanGen` `const b = Number(S.plan && S.plan.gen);`（第 1 次） | `短路-去右侧`：`S.plan && S.plan.gen` → `S.plan ` | 已守 · `test_old_plan_event_cannot_replace_current_running_plan` · 'old' != 'new' |
| M347 | `maxPlanGen` `return Math.max(Number.isFinite(a) && a > 0 ? a : 0,`（第 1 次） | `三元-对调`：`? a : 0` → `? 0: a ` | 没人守 |
| M348 | `maxPlanGen` `Number.isFinite(b) && b > 0 ? b : 0);`（第 1 次） | `三元-对调`：`? b : 0` → `? 0: b ` | 已守 · `test_old_plan_event_cannot_replace_current_running_plan` · 'old' != 'new' |
| M349 | `planEventOwns` `const id = String((data && data.plan_id) \|\| "");`（第 1 次） | `短路-去右侧`：`(data && data.plan_id) \|\| ""` → `(data && data.plan_id) ` | 没人守 |
| M350 | `planEventOwns` `if (!id) return false;`（第 1 次） | `条件-恒假`：`if (!id)` → `(false)` | 没人守 |
| M351 | `planEventOwns` `if (S.plan.id === id) return true;          // 当前屏上计划：同计划按幂等合并`（第 1 次） | `条件-恒假`：`if (S.plan.id === id)` → `(false)` | 已守 · `test_natural_end_cancels_editing_and_opens_result` · JS 行为测试崩溃：TypeError: Cannot read properties of undefined (re |
| M352 | `planEventOwns` `if (!Number.isFinite(gen)) return !S.plan.id;   // 旧格式载荷：只在空屏时接纳`（第 1 次） | `条件-恒假`：`if (!Number.isFinite(gen))` → `(false)` | 已守 · `test_result_all_success_shows_mini_led` · {} != {'已报名': 1, '已取消': 1} |
| M353 | `admitPlanEvent` `if (!Number.isFinite(gen)) return 0;`（第 1 次） | `条件-恒假`：`if (!Number.isFinite(gen))` → `(false)` | 没人守 |
| M354 | `admitPlanEvent` `S.maxPlanGen = Math.max(S.maxPlanGen \|\| 0, gen);`（第 1 次） | `短路-去右侧`：`S.maxPlanGen \|\| 0` → `S.maxPlanGen ` | 没人守 |
| M355 | `advancePlanStatus` `if (PLAN_TERMINAL.indexOf(S.plan.status) >= 0) return;`（第 1 次） | `条件-恒假`：`if (PLAN_TERMINAL.indexOf(S.plan.status) >= 0)` → `(false)` | 已守 · `test_late_same_plan_events_do_not_revive_terminal_plan` · '报名计划' not found in '正在汇总结果' |
| M356 | `advancePlanStatus` `S.plan.status = String(incoming \|\| "ready");`（第 1 次） | `短路-去右侧`：`incoming \|\| "ready"` → `incoming ` | 没人守 |
| M357 | `handlePlan` `if (!planEventOwns(data)) return;      /* 旧计划迟到事件不替换当前计划（P1） */`（第 1 次） | `条件-恒假`：`if (!planEventOwns(data))` → `(false)` | 已守 · `test_old_plan_event_cannot_replace_current_running_plan` · 'old' != 'new' |
| M358 | `handlePlan` `if (!S.plan.id \|\| S.plan.id !== String(data.plan_id)) {`（第 1 次） | `条件-恒假`：`if (!S.plan.id \|\| S.plan.id !== String(data.plan_id))` → `(false)` | 已守 · `test_natural_end_cancels_editing_and_opens_result` · {'ids': ['a1'], 'doneN': 0} is not None |
| M359 | `handlePlan` `if (!S.plan.id \|\| S.plan.id !== String(data.plan_id)) {`（第 1 次） | `短路-去右侧`：`!S.plan.id \|\| S.plan.id !== String(data.plan_id)` → `!S.plan.id ` | 已守 · `test_phone_started_plan_logs_one_start_line` · Lists differ: [] != ['从手机开始了报名计划：1 场立即报名，2 场预报名等开放'] |
| M360 | `handlePlan` `S.plan = { id: String(data.plan_id \|\| ""), gen: gen, status: String(`（第 1 次） | `短路-去右侧`：`data.plan_id \|\| ""` → `data.plan_id ` | 没人守 |
| M361 | `handlePlan` `S.plan = { id: String(data.plan_id \|\| ""), gen: gen, status: String(`（第 1 次） | `短路-去右侧`：`data.status \|\| "ready"` → `data.status ` | 没人守 |
| M362 | `handlePlan` `if (gen > (Number(S.plan.gen) \|\| 0)) S.plan.gen = gen;`（第 1 次） | `条件-恒假`：`if (gen > (Number(S.plan.gen) \|\| 0))` → `(false)` | 没人守 |
| M363 | `handlePlan` `if (gen > (Number(S.plan.gen) \|\| 0)) S.plan.gen = gen;`（第 1 次） | `短路-去右侧`：`Number(S.plan.gen) \|\| 0` → `Number(S.plan.gen) ` | 没人守 |
| M364 | `handlePlan` `if (data.source) S.plan.source = String(data.source);`（第 1 次） | `条件-恒假`：`if (data.source)` → `(false)` | 已守 · `test_phone_started_plan_logs_one_start_line` · Lists differ: [] != ['从手机开始了报名计划：2 场预报名等开放'] |
| M365 | `handlePlan` `(data.tasks \|\| []).forEach((task) => {`（第 1 次） | `短路-去右侧`：`data.tasks \|\| []` → `data.tasks ` | 没人守 |
| M366 | `handlePlan` `mergeTask(S.plan.tasks.get(String(task.task_id)) \|\| null, task));`（第 1 次） | `短路-去右侧`：`S.plan.tasks.get(String(task.task_id)) \|\| null` → `S.plan.tasks.get(String(task.task_id)) ` | 没人守 |
| M367 | `handlePlan` `if (S.plan.source === "phone" && !S.plan.startNoted) {`（第 1 次） | `条件-恒假`：`if (S.plan.source === "phone" && !S.plan.startNoted)` → `(false)` | 已守 · `test_phone_started_plan_logs_one_start_line` · Lists differ: [] != ['从手机开始了报名计划：2 场预报名等开放'] |
| M368 | `handlePlan` `if (S.plan.source === "phone" && !S.plan.startNoted) {`（第 1 次） | `短路-去右侧`：` "phone" && !S.plan.startNoted` → ` "phone" ` | 已守 · `test_phone_plan_restored_after_reload_does_not_log_again` · Lists differ: ['从手机开始了报名计划：1 场预报名等开放'] != [] |
| M369 | `handleTask` `if (!planEventOwns(data)) return;           // 旧计划的场次事件：不改当前计划（P1）`（第 1 次） | `条件-恒假`：`if (!planEventOwns(data))` → `(false)` | 没人守 |
| M370 | `handleTask` `if (!S.plan.id \|\| S.plan.id !== String(data.plan_id)) {`（第 1 次） | `条件-恒假`：`if (!S.plan.id \|\| S.plan.id !== String(data.plan_id))` → `(false)` | 没人守 |
| M371 | `handleTask` `if (!S.plan.id \|\| S.plan.id !== String(data.plan_id)) {`（第 1 次） | `短路-去右侧`：`!S.plan.id \|\| S.plan.id !== String(data.plan_id)` → `!S.plan.id ` | 没人守 |
| M372 | `handleTask` `S.plan = { id: String(data.plan_id \|\| ""), gen: gen, status: "runnin`（第 1 次） | `短路-去右侧`：`data.plan_id \|\| ""` → `data.plan_id ` | 没人守 |
| M373 | `handleTask` `} else if (gen > (Number(S.plan.gen) \|\| 0)) {`（第 1 次） | `条件-恒假`：`else if (gen > (Number(S.plan.gen) \|\| 0))` → `(false)` | 没人守 |
| M374 | `handleTask` `} else if (gen > (Number(S.plan.gen) \|\| 0)) {`（第 1 次） | `短路-去右侧`：`Number(S.plan.gen) \|\| 0` → `Number(S.plan.gen) ` | 没人守 |
| M375 | `handleTask` `const prev = S.plan.tasks.get(String(data.task_id)) \|\| null;`（第 1 次） | `短路-去右侧`：` S.plan.tasks.get(String(data.task_id)) \|\| null` → ` S.plan.tasks.get(String(data.task_id)) ` | 没人守 |
| M376 | `handleTask` `if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0`（第 1 次） | `条件-恒假`：`if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0
` → `(false)` | 已守 · `test_task_events_keep_the_terminal_fact_and_update_the_card` · 'waiting' != 'success' |
| M377 | `handleTask` `if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0`（第 1 次） | `短路-去右侧`：`prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0
    ` → `prev ` | 没人守 |
| M378 | `handleTask` `if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0`（第 1 次） | `短路-去右侧`：` 0
      && TASK_TERMINAL.indexOf(String(task.status)) < 0` → ` 0
      ` | 没人守 |
| M379 | `handleTask` `if (["success", "failed", "already_signed", "canceled"].indexOf(task.s`（第 1 次） | `条件-恒假`：`if (["success", "failed", "already_signed", "canceled"].inde` → `(false)` | 已守 · `test_task_events_keep_the_terminal_fact_and_update_the_card` · '报名成功：活动甲' not found in '' |
| M380 | `handleTask` `if (noteSignedTasks([task])) scheduleSignedRefresh();`（第 1 次） | `条件-恒假`：`if (noteSignedTasks([task]))` → `(false)` | 没人守 |
| M381 | `syncResultSelection` `if (S.resultOpen) S.resultSel = selectionSignature();`（第 1 次） | `条件-恒假`：`if (S.resultOpen)` → `(false)` | 没人守 |
| M382 | `resultPageOpen` `if (!S.resultOpen) return false;`（第 1 次） | `条件-恒假`：`if (!S.resultOpen)` → `(false)` | 没人守 |
| M383 | `resultPageOpen` `if (S.resultSel !== selectionSignature()) {`（第 1 次） | `条件-恒假`：`if (S.resultSel !== selectionSignature())` → `(false)` | 已守 · `test_result_partial_with_pending_and_no_fallback` · 'stopped' != 'idle' |
| M384 | `planOutcome` `const state = String(task.status \|\| "");`（第 1 次） | `短路-去右侧`：`task.status \|\| ""` → `task.status ` | 没人守 |
| M385 | `planOutcome` `if (state === "success") counts.success += 1;`（第 1 次） | `条件-恒假`：`if (state === "success")` → `(false)` | 没人守 |
| M386 | `planOutcome` `else if (state === "already_signed") counts.already_signed += 1;`（第 1 次） | `条件-恒假`：`else if (state === "already_signed")` → `(false)` | 没人守 |
| M387 | `planOutcome` `else if (state === "canceled") counts.canceled += 1;`（第 1 次） | `条件-恒假`：`else if (state === "canceled")` → `(false)` | 没人守 |
| M388 | `planOutcome` `else if (state === "failed") {`（第 1 次） | `条件-恒假`：`else if (state === "failed")` → `(false)` | 没人守 |
| M389 | `planOutcome` `if (task.stop_reason === "unconfirmed") counts.unconfirmed += 1;`（第 1 次） | `条件-恒假`：`if (task.stop_reason === "unconfirmed")` → `(false)` | 没人守 |
| M390 | `planOutcome` `else if (task.stop_reason === "auth_unavailable") counts.auth_unavaila`（第 1 次） | `条件-恒假`：`else if (task.stop_reason === "auth_unavailable")` → `(false)` | 没人守 |
| M391 | `unknownLabel` `if (!outcome \|\| !outcome.unknown) return "";`（第 1 次） | `条件-恒假`：`if (!outcome \|\| !outcome.unknown)` → `(false)` | 没人守 |
| M392 | `unknownLabel` `if (outcome.unconfirmed && outcome.auth_unavailable) {`（第 1 次） | `条件-恒假`：`if (outcome.unconfirmed && outcome.auth_unavailable)` → `(false)` | 没人守 |
| M393 | `unknownLabel` `if (outcome.unconfirmed) return "有 " + outcome.unconfirmed + " 场待核对";`（第 1 次） | `条件-恒假`：`if (outcome.unconfirmed)` → `(false)` | 没人守 |

### state/task-display.js（85 条）

| 编号 | 定位：函数 / 那一行的文字 / 第几次出现 | 变异写法 | 补测后 |
|---|---|---|---|
| M394 | `taskDisplayItem` `if (found) return found;`（第 1 次） | `条件-恒假`：`if (found)` → `(false)` | 没人守 |
| M395 | `taskDisplayItem` `if (!task) return null;`（第 1 次） | `条件-恒假`：`if (!task)` → `(false)` | 没人守 |
| M396 | `taskDisplayItem` `id: String(task.activity_id \|\| task.task_id \|\| ""),`（第 1 次） | `短路-去右侧`：` task.task_id \|\| ""` → ` task.task_id ` | 没人守 |
| M397 | `taskDisplayItem` `name: String(task.name \|\| "这一场活动"),`（第 1 次） | `短路-去右侧`：`task.name \|\| "这一场活动"` → `task.name ` | 没人守 |
| M398 | `taskDisplayItem` `sign_start: task.sign_start \|\| "",`（第 1 次） | `短路-去右侧`：` task.sign_start \|\| ""` → ` task.sign_start ` | 没人守 |
| M399 | `taskDisplayItem` `sign_end: task.sign_end \|\| "",`（第 1 次） | `短路-去右侧`：` task.sign_end \|\| ""` → ` task.sign_end ` | 没人守 |
| M400 | `taskDisplayItem` `act_start: task.act_start \|\| "",`（第 1 次） | `短路-去右侧`：` task.act_start \|\| ""` → ` task.act_start ` | 没人守 |
| M401 | `taskDisplayItem` `act_end: task.act_end \|\| "",`（第 1 次） | `短路-去右侧`：` task.act_end \|\| ""` → ` task.act_end ` | 没人守 |
| M402 | `taskDisplayItem` `place: task.place \|\| "",`（第 1 次） | `短路-去右侧`：` task.place \|\| ""` → ` task.place ` | 没人守 |
| M403 | `taskDisplayPhase` `if (!task) return "terminal";`（第 1 次） | `条件-恒假`：`if (!task)` → `(false)` | 没人守 |
| M404 | `taskDisplayPhase` `const status = String(task.status \|\| "");`（第 1 次） | `短路-去右侧`：`task.status \|\| ""` → `task.status ` | 没人守 |
| M405 | `taskDisplayPhase` `if (RUNNING_STATUSES.indexOf(status) < 0) return "terminal";`（第 1 次） | `条件-恒假`：`if (RUNNING_STATUSES.indexOf(status) < 0)` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '待核对' not found in '活动甲提交中已提交 1 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动 |
| M406 | `taskDisplayPhase` `if (Number.isFinite(attempts) && attempts > 0) return "retrying";`（第 1 次） | `条件-恒假`：`if (Number.isFinite(attempts) && attempts > 0)` → `(false)` | 已守 · `test_running_board_uses_tone_and_caption_for_each_phase` · '提交中' not found in '活动甲准备报名立即报名 · 已开放，正在准备提交' |
| M407 | `taskDisplayPhase` `const at = Number.isFinite(now) ? now : bnowS();`（第 1 次） | `三元-对调`：`? now : bnowS()` → `? bnowS(): now ` | 已守 · `test_activity_row_tracks_phase_and_open_time` · '等待开放' != '准备报名' |
| M408 | `taskDisplayPhase` `const mode = String(task.signup_mode \|\| "");`（第 1 次） | `短路-去右侧`：`task.signup_mode \|\| ""` → `task.signup_mode ` | 没人守 |
| M409 | `taskDisplayPhase` `if (at == null) return mode === "instant_signup" ? "preparing" : "preo`（第 1 次） | `条件-恒假`：`if (at == null)` → `(false)` | 没人守 |
| M410 | `taskDisplayPhase` `if (at == null) return mode === "instant_signup" ? "preparing" : "preo`（第 1 次） | `三元-对调`：`? "preparing" : "preopen"` → `? "preopen": "preparing" ` | 没人守 |
| M411 | `taskDisplayPhase` `if (open === null) return mode === "instant_signup" ? "preparing" : "p`（第 1 次） | `条件-恒假`：`if (open === null)` → `(false)` | 已守 · `test_snapshot_restore_without_selection_or_list_item` · '时间待公布' not found in '已开放 · 准备提交 1 场' |
| M412 | `taskDisplayPhase` `if (open === null) return mode === "instant_signup" ? "preparing" : "p`（第 2 次） | `三元-对调`：`? "preparing" : "preopen"` → `? "preopen": "preparing" ` | 已守 · `test_snapshot_restore_without_selection_or_list_item` · '时间待公布' not found in '已开放 · 准备提交 1 场' |
| M413 | `taskDisplayPhase` `if (open > at) return "preopen";`（第 1 次） | `条件-恒假`：`if (open > at)` → `(false)` | 已守 · `test_task_events_keep_the_terminal_fact_and_update_the_card` · '等待开放' not found in '活动甲准备报名预报名 · 已开放，正在准备提交取消这一场' |
| M414 | `taskDisplayLabel` `if (phase === "preopen") return "等待开放";`（第 1 次） | `条件-恒假`：`if (phase === "preopen")` → `(false)` | 已守 · `test_activity_row_tracks_phase_and_open_time` · '等待开放' not found in '<div class="task-row" data-task-id="A"> |
| M415 | `taskDisplayLabel` `if (phase === "preparing") return "准备报名";`（第 1 次） | `条件-恒假`：`if (phase === "preparing")` → `(false)` | 已守 · `test_activity_row_tracks_phase_and_open_time` · '提交中' != '准备报名' |
| M416 | `taskDisplayLabel` `if (phase === "retrying") return "提交中";`（第 1 次） | `条件-恒假`：`if (phase === "retrying")` → `(false)` | 没人守 |
| M417 | `taskDisplayLabel` `const state = String(task && task.status \|\| "queued");`（第 1 次） | `短路-去右侧`：`task && task.status ` → `task ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '待核对' not found in '活动甲处理中已提交 1 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动 |
| M418 | `taskDisplayLabel` `const state = String(task && task.status \|\| "queued");`（第 1 次） | `短路-去右侧`：` task.status \|\| "queued"` → ` task.status ` | 已守 · `test_verify_task_switches_the_card_wording` · '排队' not found in '活动甲处理中立即报名 · ' : 缺状态字段的旧载荷按「排队」显示 |
| M419 | `taskDisplayLabel` `if (state === "failed") {`（第 1 次） | `条件-恒假`：`if (state === "failed")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '待核对' not found in '活动甲报名未成功已提交 1 次，没拿到确定回应；结束时向学校核对也没查到结果。去 |
| M420 | `taskDisplayLabel` `if (typeof verifiedSigned === "function" && verifiedSigned(task)) retu`（第 1 次） | `条件-恒假`：`if (typeof verifiedSigned === "function" && verifiedSigned(t` → `(false)` | 已守 · `test_verify_task_switches_the_card_wording` · '报名成功' not found in '活动甲待核对刷新核对：学校显示已报名' |
| M421 | `taskDisplayLabel` `if (typeof verifiedSigned === "function" && verifiedSigned(task)) retu`（第 1 次） | `短路-去右侧`：` "function" && verifiedSigned(task)` → ` "function" ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '待核对' not found in '活动甲报名成功已提交 1 次，没拿到确定回应；结束时向学校核对也没查到结果。去活 |
| M422 | `taskDisplayLabel` `if (typeof taskMissedBySleep === "function" && taskMissedBySleep(task)`（第 1 次） | `条件-恒假`：`if (typeof taskMissedBySleep === "function" && taskMissedByS` → `(false)` | 已守 · `test_task_cards_use_the_missed_verb_and_the_prototype_reason` · Lists differ: ['is-bad', '报名未成功'] != ['is-bad', '错过了'] |
| M423 | `taskDisplayLabel` `if (typeof taskMissedBySleep === "function" && taskMissedBySleep(task)`（第 1 次） | `短路-去右侧`：` "function" && taskMissedBySleep(task)` → ` "function" ` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '待核对' not found in '活动甲错过了已提交 1 次，没拿到确定回应；结束时向学校核对也没查到结果。去活动 |
| M424 | `taskDisplayLabel` `if (task.stop_reason === "unconfirmed") return "待核对";`（第 1 次） | `条件-恒假`：`if (task.stop_reason === "unconfirmed")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '待核对' not found in '活动甲报名未成功已提交 1 次，没拿到确定回应；结束时向学校核对也没查到结果。去 |
| M425 | `taskDisplayLabel` `if (task.stop_reason === "auth_unavailable") return "未提交";`（第 1 次） | `条件-恒假`：`if (task.stop_reason === "auth_unavailable")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '未提交' not found in '活动甲报名未成功登录状态无法确认，本场没有提交 · 检查网络后刷新重试' |
| M426 | `taskDisplayLabel` `if (task.stop_reason === "full") return "名额已满";`（第 1 次） | `条件-恒假`：`if (task.stop_reason === "full")` → `(false)` | 已守 · `test_task_card_writes_each_outcome_in_plain_words` · '名额已满' not found in '活动甲报名未成功学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。已 |
| M427 | `taskModePrefix` `const state = String(task && task.status \|\| "queued");`（第 1 次） | `短路-去右侧`：`task && task.status ` → `task ` | 没人守 |
| M428 | `taskModePrefix` `const state = String(task && task.status \|\| "queued");`（第 1 次） | `短路-去右侧`：` task.status \|\| "queued"` → ` task.status ` | 没人守 |
| M429 | `taskModePrefix` `return RUNNING_STATUSES.indexOf(state) >= 0 && modeText(mode) ? modeTe`（第 1 次） | `三元-对调`：`? modeText(mode) + " · " : ""` → `? "": modeText(mode) + " · " ` | 已守 · `test_task_cards_use_the_missed_verb_and_the_prototype_reason` · '立即报名 · 电脑睡眠期间到了开放时间，没有提交。' != '电脑睡眠期间到了开放时间，没有提交。' |
| M430 | `taskPrepared` `const clickPath = String(task && task.path \|\| "") === "click";`（第 1 次） | `短路-去右侧`：` task.path \|\| ""` → ` task.path ` | 没人守 |
| M431 | `taskPrepared` `const at = clickPath ? page : (watch > 0 ? watch : page);`（第 1 次） | `三元-对调`：`? page : (watch > 0 ? watch : page)` → `? (watch > 0 ? watch : page): page ` | 已守 · `test_task_prepared_uses_checkpoint_time` · '已准备好，06:28:20 开放时提交' not found in '<div class="task-row" da |
| M432 | `taskPrepared` `const at = clickPath ? page : (watch > 0 ? watch : page);`（第 1 次） | `三元-对调`：`? watch : page` → `? page: watch ` | 已守 · `test_prepared_task_uses_checkpoint_in_visible_detail` · '已准备好' not found in '已准备活动等待开放预报名 · 提前准备，等到 14:30:00 开放取消这一场 |
| M433 | `taskPrepared` `if (!(at > 0)) return false;`（第 1 次） | `条件-恒假`：`if (!(at > 0))` → `(false)` | 已守 · `test_task_prepared_uses_checkpoint_time` · '提前准备，等到 06:28:20 开放' not found in '<div class="task-row" da |
| M434 | `taskPrepared` `const current = Number.isFinite(now) ? now : bnowS();`（第 1 次） | `三元-对调`：`? now : bnowS()` → `? bnowS(): now ` | 没人守 |
| M435 | `taskDisplayDetail` `if (phase !== "terminal" && String(task && task.login_wait \|\| "") ==`（第 1 次） | `条件-恒假`：`if (phase !== "terminal" && String(task && task.login_wait \` → `(false)` | 已守 · `test_task_cards_explain_login_wait_and_submission_phase` · '电脑正在自动登录' not found in '活动甲准备报名立即报名 · 已开放，正在准备提交取消这一场' |
| M436 | `taskDisplayDetail` `if (phase !== "terminal" && String(task && task.login_wait \|\| "") ==`（第 1 次） | `短路-去右侧`：` "terminal" && String(task && task.login_wait \|\| "") === "` → ` "terminal" ` | 已守 · `test_prepared_task_uses_checkpoint_in_visible_detail` · '已提交 2 次' not found in '活动甲提交中立即报名 · 电脑正在自动登录，换上新登录态后接着提交' |
| M437 | `taskDisplayDetail` `if (phase !== "terminal" && String(task && task.login_wait \|\| "") ==`（第 1 次） | `短路-去右侧`：` task.login_wait \|\| ""` → ` task.login_wait ` | 没人守 |
| M438 | `taskDisplayDetail` `if (phase === "preopen") {`（第 1 次） | `条件-恒假`：`if (phase === "preopen")` → `(false)` | 已守 · `test_prepared_task_uses_checkpoint_in_visible_detail` · '已准备好' not found in '已准备活动等待开放预报名 · 等待报名开放取消这一场' |
| M439 | `taskDisplayDetail` `if (open === null) return "提前准备，开放时间待公布";`（第 1 次） | `条件-恒假`：`if (open === null)` → `(false)` | 没人守 |
| M440 | `taskDisplayDetail` `return taskPrepared(task, now) ? "已准备好，" + hmsDay(open) + " 开放时提交"`（第 1 次） | `三元-对调`：`? "已准备好，" + hmsDay(open) + " 开放时提交"
      : "提前准备，等到 " + hms` → `? "提前准备，等到 " + hmsDay(open) + " 开放": "已准` | 已守 · `test_prepared_task_uses_checkpoint_in_visible_detail` · '已准备好' not found in '已准备活动等待开放预报名 · 提前准备，等到 14:30:00 开放取消这一场 |
| M441 | `taskDisplayDetail` `if (phase === "preparing") return "已开放，正在准备提交";`（第 1 次） | `条件-恒假`：`if (phase === "preparing")` → `(false)` | 已守 · `test_future_prewarm_is_not_reported_as_submitting` · '已开放，正在准备提交' not found in '预报名 · ' |
| M442 | `taskDisplayDetail` `if (phase === "retrying") return submittingDetail(task);`（第 1 次） | `条件-恒假`：`if (phase === "retrying")` → `(false)` | 已守 · `test_task_cards_explain_login_wait_and_submission_phase` · '已提交 2 次' not found in '活动甲提交中立即报名 · ' |
| M443 | `executionView` `if (!S.busy \|\| !S.plan.id) return empty;`（第 1 次） | `条件-恒假`：`if (!S.busy \|\| !S.plan.id)` → `(false)` | 没人守 |
| M444 | `executionView` `if (!S.busy \|\| !S.plan.id) return empty;`（第 1 次） | `短路-去右侧`：`!S.busy \|\| !S.plan.id` → `!S.busy ` | 没人守 |
| M445 | `executionView` `if (!S.busy \|\| !S.plan.id) return empty;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '正在准备报名' != '活动甲' |
| M446 | `executionView` `if (!running.length) {`（第 1 次） | `条件-恒假`：`if (!running.length)` → `(false)` | 已守 · `test_enter_during_running_plan_does_not_start_again` · JS 行为测试崩溃：TypeError: Cannot read properties of undefined (re |
| M447 | `executionView` `return Object.assign({}, empty, { phase: tasks.length ? "settling" : "`（第 1 次） | `三元-对调`：`? "settling" : "preparing" ` → `? "preparing" : "settling" ` | 已守 · `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` · '正在汇总结果' != '正在准备报名' |
| M448 | `executionView` `let bestAt = best.at === null ? Infinity : best.at;`（第 1 次） | `三元-对调`：`? Infinity : best.at` → `? best.at: Infinity ` | 没人守 |
| M449 | `executionView` `const at = list[i].at === null ? Infinity : list[i].at;`（第 1 次） | `三元-对调`：`? Infinity : list[i].at` → `? list[i].at: Infinity ` | 没人守 |
| M450 | `executionView` `if (at < bestAt) { best = list[i]; bestAt = at; }`（第 1 次） | `条件-恒假`：`if (at < bestAt)` → `(false)` | 没人守 |
| M451 | `executionView` `(task) => String(task.sign_start \|\| "") === String(signStart \|\| ""`（第 1 次） | `短路-去右侧`：`task.sign_start \|\| ""` → `task.sign_start ` | 没人守 |
| M452 | `executionView` `(task) => String(task.sign_start \|\| "") === String(signStart \|\| ""`（第 1 次） | `短路-去右侧`：`signStart \|\| ""` → `signStart ` | 没人守 |
| M453 | `executionView` `if (retrying.length) {`（第 1 次） | `条件-恒假`：`if (retrying.length)` → `(false)` | 已守 · `test_run_warning_explains_auto_login_and_both_relogin_windows` · JS 行为测试崩溃：TypeError: Cannot read properties of undefined (re |
| M454 | `executionView` `if (at !== null && (bestAt === null \|\| at < bestAt)) { best = retryi`（第 1 次） | `条件-恒假`：`if (at !== null && (bestAt === null \|\| at < bestAt))` → `(false)` | 没人守 |
| M455 | `executionView` `if (arming.length) {`（第 1 次） | `条件-恒假`：`if (arming.length)` → `(false)` | 已守 · `test_pick_and_clear_controls_follow_selection_and_run_state` · JS 行为测试崩溃：TypeError: Cannot read properties of undefined (re |
| M456 | `verifiedSigned` `if (!task \|\| String(task.stop_reason \|\| "") !== "unconfirmed") ret`（第 1 次） | `条件-恒假`：`if (!task \|\| String(task.stop_reason \|\| "") !== "unconfi` → `(false)` | 已守 · `test_result_stopped_counts_canceled` · '学校回“报名成功”，结束时向学校核对过：已报名' not found in '<div class="task-row |
| M457 | `verifiedSigned` `if (!task \|\| String(task.stop_reason \|\| "") !== "unconfirmed") ret`（第 1 次） | `短路-去右侧`：`!task \|\| String(task.stop_reason \|\| "") !== "unconfirmed` → `!task ` | 已守 · `test_result_stopped_counts_canceled` · '学校回“报名成功”，结束时向学校核对过：已报名' not found in '<div class="task-row |
| M458 | `verifiedSigned` `if (!task \|\| String(task.stop_reason \|\| "") !== "unconfirmed") ret`（第 1 次） | `短路-去右侧`：`task.stop_reason \|\| ""` → `task.stop_reason ` | 没人守 |
| M459 | `telemetryDeadline` `return Number.isFinite(epoch) && epoch > 0 ? epoch : null;`（第 1 次） | `三元-对调`：`? epoch : null` → `? null: epoch ` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · JS 行为测试崩溃：RangeError: Invalid time value |
| M460 | `submittingDetail` `const head = "已提交 " + attempts + " 次（" + (limited ? "上限 " + cap + " 次"`（第 1 次） | `三元-对调`：`? "上限 " + cap + " 次" : "不限次数"` → `? "不限次数": "上限 " + cap + " 次" ` | 已守 · `test_run_submitting_single_caption_and_cancel_label` · '已提交 3 次（不限次数）。最近：还没开放，重试到 ' not found in '<div class="task- |
| M461 | `submittingDetail` `const last = String(task && task.last_reason \|\| "").trim();`（第 1 次） | `短路-去右侧`：` task.last_reason \|\| ""` → ` task.last_reason ` | 没人守 |
| M462 | `submittingDetail` `if (last) tail.push("最近：" + last);`（第 1 次） | `条件-恒假`：`if (last)` → `(false)` | 已守 · `test_run_submitting_single_caption_and_cancel_label` · '已提交 3 次（不限次数）。最近：还没开放，重试到 ' not found in '<div class="task- |
| M463 | `submittingDetail` `tail.push(deadline === null ? "等待提交结果" : "重试到 " + hmsDay(deadline));`（第 1 次） | `三元-对调`：`? "等待提交结果" : "重试到 " + hmsDay(deadline)` → `? "重试到 " + hmsDay(deadline): "等待提交结果" ` | 已守 · `test_run_submitting_single_caption_and_cancel_label` · '已提交 3 次（不限次数）。最近：还没开放，重试到 ' not found in '<div class="task- |
| M464 | `effectiveRetryDeadline` `if (telemetry !== null) return telemetry;`（第 1 次） | `条件-恒假`：`if (telemetry !== null)` → `(false)` | 已守 · `test_run_submitting_single_caption_and_cancel_label` · 1792929720 != 1792929900 : 遥测必须优先 |
| M465 | `effectiveRetryDeadline` `const now = Number.isFinite(fallbackNow) ? fallbackNow : bnowS();`（第 1 次） | `三元-对调`：`? fallbackNow : bnowS()` → `? bnowS(): fallbackNow ` | 已守 · `test_truncation_fallback_and_telemetry` · None != 1792933320 : 未来场未启动时用原定开放作计划参考 |
| M466 | `effectiveRetryDeadline` `const rawFor = task && Number.isFinite(Number(task.retry_for_s)) ? Num`（第 1 次） | `三元-对调`：`? Number(task.retry_for_s) : RETRY_WINDOW_S` → `? RETRY_WINDOW_S: Number(task.retry_for_` | 已守 · `test_absolute_deadline_needs_no_anchor` · 1792929720 != 1792931400 : 时长 0 且有截止时直接到截止 |
| M467 | `effectiveRetryDeadline` `const retryFor = rawFor === -1 ? RETRY_WINDOW_S : rawFor;`（第 1 次） | `三元-对调`：`? RETRY_WINDOW_S : rawFor` → `? rawFor: RETRY_WINDOW_S ` | 已守 · `test_absolute_deadline_needs_no_anchor` · 1792929720 != 1792931400 : 时长 0 且有截止时直接到截止 |
| M468 | `effectiveRetryDeadline` `const signEnd = task ? toTs(task.sign_end) : null;`（第 1 次） | `三元-对调`：`? toTs(task.sign_end) : null` → `? null: toTs(task.sign_end) ` | 已守 · `test_absolute_deadline_needs_no_anchor` · 1792929720 != 1792929660 : sign_end 必须硬截断 |
| M469 | `effectiveRetryDeadline` `if (retryFor === 0 && signEnd !== null) return signEnd;`（第 1 次） | `条件-恒假`：`if (retryFor === 0 && signEnd !== null)` → `(false)` | 已守 · `test_absolute_deadline_needs_no_anchor` · 1792929720 != 1792931400 : 时长 0 且有截止时直接到截止 |
| M470 | `effectiveRetryDeadline` `if (Number.isFinite(policyStart) && policyStart > 0) {`（第 1 次） | `条件-恒假`：`if (Number.isFinite(policyStart) && policyStart > 0)` → `(false)` | 没人守 |
| M471 | `effectiveRetryDeadline` `let frozen = retryFor > 0 ? policyStart + retryFor : policyStart + RET`（第 1 次） | `三元-对调`：`? policyStart + retryFor : policyStart + RETRY_WINDOW_S` → `? policyStart + RETRY_WINDOW_S: policySt` | 没人守 |
| M472 | `effectiveRetryDeadline` `if (signEnd !== null) frozen = Math.min(frozen, signEnd);`（第 1 次） | `条件-恒假`：`if (signEnd !== null)` → `(false)` | 没人守 |
| M473 | `effectiveRetryDeadline` `if (started !== null) anchor = open !== null ? Math.max(open, started)`（第 1 次） | `条件-恒假`：`if (started !== null)` → `(false)` | 已守 · `test_anchor_is_stable_across_open` · '待定' != '—' |
| M474 | `effectiveRetryDeadline` `if (started !== null) anchor = open !== null ? Math.max(open, started)`（第 1 次） | `三元-对调`：`? Math.max(open, started) : started` → `? started: Math.max(open, started) ` | 已守 · `test_anchor_is_stable_across_open` · 1792929620 != 1792929660 : sign_end 必须硬截断 |
| M475 | `effectiveRetryDeadline` `else if (open !== null && open > now) anchor = open;`（第 1 次） | `条件-恒假`：`else if (open !== null && open > now)` → `(false)` | 已守 · `test_truncation_fallback_and_telemetry` · None != 1792933320 : 未来场未启动时用原定开放作计划参考 |
| M476 | `effectiveRetryDeadline` `if (anchor === null) return null;`（第 1 次） | `条件-恒假`：`if (anchor === null)` → `(false)` | 已守 · `test_absolute_deadline_needs_no_anchor` · 120 is not None : 没有时间参考时必须是未知，不是当前时刻 |
| M477 | `effectiveRetryDeadline` `let deadline = retryFor > 0 ? anchor + retryFor : anchor + RETRY_WINDO`（第 1 次） | `三元-对调`：`? anchor + retryFor : anchor + RETRY_WINDOW_S` → `? anchor + RETRY_WINDOW_S: anchor + retr` | 已守 · `test_truncation_fallback_and_telemetry` · 1792929600 != 1792929720 : 时长 0 且无截止时回退 120 秒 |
| M478 | `effectiveRetryDeadline` `if (signEnd !== null) deadline = Math.min(deadline, signEnd);`（第 2 次） | `条件-恒假`：`if (signEnd !== null)` → `(false)` | 已守 · `test_truncation_fallback_and_telemetry` · 1792929720 != 1792929660 : sign_end 必须硬截断 |

### controllers/plan.js（209 条）

| 编号 | 定位：函数 / 那一行的文字 / 第几次出现 | 变异写法 | 补测后 |
|---|---|---|---|
| M479 | `startPlan` `if (S.busy \|\| S.starting \|\| S.cancel.busyId) return;`（第 1 次） | `条件-恒假`：`if (S.busy \|\| S.starting \|\| S.cancel.busyId)` → `(false)` | 已守 · `test_enter_during_running_plan_does_not_start_again` · 1 != 0 : 计划运行中不能再发一次开始请求 |
| M480 | `startPlan` `if (S.busy \|\| S.starting \|\| S.cancel.busyId) return;`（第 1 次） | `短路-去右侧`：`S.busy \|\| S.starting ` → `S.busy ` | 没人守 |
| M481 | `startPlan` `if (S.busy \|\| S.starting \|\| S.cancel.busyId) return;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_enter_during_running_plan_does_not_start_again` · 1 != 0 : 计划运行中不能再发一次开始请求 |
| M482 | `startPlan` `if (S.busy \|\| S.starting \|\| S.cancel.busyId) return;`（第 1 次） | `短路-去右侧`：` S.starting \|\| S.cancel.busyId` → ` S.starting ` | 没人守 |
| M483 | `startPlan` `if (S.busy \|\| S.starting \|\| S.cancel.busyId) return;`（第 1 次） | `读 S.starting`：`S.starting` → `false` | 没人守 |
| M484 | `startPlan` `if (termsLocked()) {`（第 1 次） | `条件-恒假`：`if (termsLocked())` → `(false)` | 已守 · `test_start_plan_refuses_before_sending_anything` · 1 != 0 : 条款没同意不能发开始请求 |
| M485 | `startPlan` `if (!S.terms.declined && !S.terms.unknown) openTerms();`（第 1 次） | `条件-恒假`：`if (!S.terms.declined && !S.terms.unknown)` → `(false)` | 没人守 |
| M486 | `startPlan` `if (!S.terms.declined && !S.terms.unknown) openTerms();`（第 1 次） | `短路-去右侧`：`!S.terms.declined && !S.terms.unknown` → `!S.terms.declined ` | 没人守 |
| M487 | `startPlan` `if (!S.selected.size) {`（第 1 次） | `条件-恒假`：`if (!S.selected.size)` → `(false)` | 已守 · `test_start_plan_refuses_before_sending_anything` · '还没选活动' not found in '' |
| M488 | `startPlan` `if (validation.errors.length \|\| validation.conflicts.length) {`（第 1 次） | `条件-恒假`：`if (validation.errors.length \|\| validation.conflicts.lengt` → `(false)` | 已守 · `test_start_plan_refuses_before_sending_anything` · '计划还不能开始' not found in '' |
| M489 | `startPlan` `if (validation.errors.length \|\| validation.conflicts.length) {`（第 1 次） | `短路-去右侧`：`validation.errors.length \|\| validation.conflicts.length` → `validation.errors.length ` | 已守 · `test_start_plan_refuses_before_sending_anything` · '计划还不能开始' not found in '' |
| M490 | `startPlan` `sign_start: item.sign_start \|\| "",`（第 1 次） | `短路-去右侧`：` item.sign_start \|\| ""` → ` item.sign_start ` | 没人守 |
| M491 | `startPlan` `sign_end: item.sign_end \|\| "",`（第 1 次） | `短路-去右侧`：` item.sign_end \|\| ""` → ` item.sign_end ` | 没人守 |
| M492 | `startPlan` `act_start: item.act_start \|\| "",`（第 1 次） | `短路-去右侧`：` item.act_start \|\| ""` → ` item.act_start ` | 没人守 |
| M493 | `startPlan` `act_end: item.act_end \|\| "",`（第 1 次） | `短路-去右侧`：` item.act_end \|\| ""` → ` item.act_end ` | 没人守 |
| M494 | `startPlan` `if (S.startRequest) {`（第 1 次） | `条件-恒假`：`if (S.startRequest)` → `(false)` | 没人守 |
| M495 | `startPlan` `if (S.startRequest) {`（第 1 次） | `读 S.startRequest`：`S.startRequest` → `null` | 没人守 |
| M496 | `startPlan` `clearTimeout(S.startRequest.timer);`（第 1 次） | `读 S.startRequest.timer`：`S.startRequest.timer` → `0` | 没人守 |
| M497 | `startPlan` `clearTimeout(S.startRequest.queryTimer);`（第 1 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 没人守 |
| M498 | `startPlan` `S.startRequest.timer = setTimeout(() => reconcileStart(requestId), 150`（第 2 次） | `读 S.startRequest.timer`：`S.startRequest.timer` → `0` | 变异不成立（赋值点） |
| M499 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 1 次） | `条件-恒假`：`if (!S.startRequest \|\| S.startRequest.id !== requestId)` → `(false)` | 没人守 |
| M500 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 1 次） | `短路-去右侧`：`!S.startRequest \|\| S.startRequest.id !== requestId` → `!S.startRequest ` | 没人守 |
| M501 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 2 次） | `读 S.startRequest`：`S.startRequest` → `null` | 已守 · `test_start_plan_rejection_branches_show_their_own_exit` · 'submitting' != 'reconciling' |
| M502 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 1 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 已守 · `test_start_plan_rejection_branches_show_their_own_exit` · 'submitting' != 'reconciling' |
| M503 | `startPlan` `clearTimeout(S.startRequest.timer);`（第 3 次） | `读 S.startRequest.timer`：`S.startRequest.timer` → `0` | 没人守 |
| M504 | `startPlan` `clearTimeout(S.startRequest.queryTimer);`（第 2 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 没人守 |
| M505 | `startPlan` `if (res && res.pending) {`（第 1 次） | `条件-恒假`：`if (res && res.pending)` → `(false)` | 已守 · `test_start_plan_sends_full_items_and_waits_on_pending` · 'settled' != 'reconciling' |
| M506 | `startPlan` `S.startRequest.state = "settled";`（第 1 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 变异不成立（赋值点） |
| M507 | `startPlan` `if (!res \|\| res.ok === false) {`（第 1 次） | `条件-恒假`：`if (!res \|\| res.ok === false)` → `(false)` | 已守 · `test_start_plan_rejection_branches_show_their_own_exit` · 'v1' != '' |
| M508 | `startPlan` `if (res && res.error === "terms_required") {`（第 1 次） | `条件-恒假`：`if (res && res.error === "terms_required")` → `(false)` | 已守 · `test_start_plan_rejection_branches_show_their_own_exit` · 'v1' != '' |
| M509 | `startPlan` `if (res && res.error === "terms_required") {`（第 1 次） | `短路-去右侧`：`res && res.error === "terms_required"` → `res ` | 已守 · `test_start_plan_rejection_branches_show_their_own_exit` · '程序组件缺失' not found in '' |
| M510 | `startPlan` `if (res && res.error && RUNTIME_ERRORS[res.error]) {`（第 1 次） | `条件-恒假`：`if (res && res.error && RUNTIME_ERRORS[res.error])` → `(false)` | 已守 · `test_start_plan_rejection_branches_show_their_own_exit` · '程序组件缺失' not found in '' |
| M511 | `startPlan` `showPlanError(res && res.text, res && res.conflicts, res && res.errors`（第 1 次） | `短路-去右侧`：`res && res.text` → `res ` | 已守 · `test_start_plan_rejection_branches_show_their_own_exit` · '场次已截止' not found in '计划没能开始[object Object]' |
| M512 | `startPlan` `if (!S.plan.id \|\| S.plan.id !== String(res.plan_id \|\| "")) {`（第 1 次） | `条件-恒假`：`if (!S.plan.id \|\| S.plan.id !== String(res.plan_id \|\| ""` → `(false)` | 已守 · `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` · None != 'p1' |
| M513 | `startPlan` `if (!S.plan.id \|\| S.plan.id !== String(res.plan_id \|\| "")) {`（第 1 次） | `短路-去右侧`：`!S.plan.id \|\| S.plan.id !== String(res.plan_id \|\| "")` → `!S.plan.id ` | 没人守 |
| M514 | `startPlan` `if (!S.plan.id \|\| S.plan.id !== String(res.plan_id \|\| "")) {`（第 1 次） | `短路-去右侧`：`res.plan_id \|\| ""` → `res.plan_id ` | 没人守 |
| M515 | `startPlan` `S.plan = { id: String(res.plan_id \|\| ""), gen: ackGen,`（第 2 次） | `短路-去右侧`：`res.plan_id \|\| ""` → `res.plan_id ` | 没人守 |
| M516 | `startPlan` `} else if (ackGen > (Number(S.plan.gen) \|\| 0)) {`（第 1 次） | `条件-恒假`：`else if (ackGen > (Number(S.plan.gen) \|\| 0))` → `(false)` | 没人守 |
| M517 | `startPlan` `} else if (ackGen > (Number(S.plan.gen) \|\| 0)) {`（第 1 次） | `短路-去右侧`：`Number(S.plan.gen) \|\| 0` → `Number(S.plan.gen) ` | 没人守 |
| M518 | `startPlan` `if (S.plan.id === String(res.plan_id \|\| "")`（第 1 次） | `条件-恒假`：`if (S.plan.id === String(res.plan_id \|\| "")
        && PLA` → `(false)` | 已守 · `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` · True is not false |
| M519 | `startPlan` `if (S.plan.id === String(res.plan_id \|\| "")`（第 1 次） | `短路-去右侧`：` String(res.plan_id \|\| "")
        && PLAN_TERMINAL.indexO` → ` String(res.plan_id \|\| "")
        ` | 已守 · `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` · False is not true |
| M520 | `startPlan` `if (S.plan.id === String(res.plan_id \|\| "")`（第 3 次） | `短路-去右侧`：`res.plan_id \|\| ""` → `res.plan_id ` | 没人守 |
| M521 | `startPlan` `if (futureCount) parts.push(futureCount + " 场预报名等开放");`（第 1 次） | `条件-恒假`：`if (futureCount)` → `(false)` | 已守 · `test_start_plan_reports_the_ack_and_respects_a_terminal_ack` · '已安排 1 场活动：1 场预报名等开放。' not found in '已安排 1 场活动：按各场状态执行。' |
| M522 | `startPlan` `if (instantCount) parts.push(instantCount + " 场立即报名马上执行");`（第 1 次） | `条件-恒假`：`if (instantCount)` → `(false)` | 没人守 |
| M523 | `startPlan` `addLog("已安排 " + items.length + " 场活动：" + (parts.join("，") \|\| "按各场状态执`（第 1 次） | `短路-去右侧`：`parts.join("，") \|\| "按各场状态执行"` → `parts.join("，") ` | 没人守 |
| M524 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 2 次） | `条件-恒假`：`if (!S.startRequest \|\| S.startRequest.id !== requestId)` → `(false)` | 没人守 |
| M525 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 2 次） | `短路-去右侧`：`!S.startRequest \|\| S.startRequest.id !== requestId` → `!S.startRequest ` | 没人守 |
| M526 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 3 次） | `读 S.startRequest`：`S.startRequest` → `null` | 已守 · `test_start_timeout_enters_reconciliation_without_restarting` · '正在确认是否启动' not found in '正在提交…' |
| M527 | `startPlan` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 2 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 已守 · `test_start_timeout_enters_reconciliation_without_restarting` · '正在确认是否启动' not found in '正在提交…' |
| M528 | `startPlan` `clearTimeout(S.startRequest.timer);`（第 4 次） | `读 S.startRequest.timer`：`S.startRequest.timer` → `0` | 没人守 |
| M529 | `startPlan` `S.startRequest.state = "reconciling";`（第 2 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 变异不成立（赋值点） |
| M530 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 1 次） | `条件-恒假`：`if (!S.startRequest \|\| S.startRequest.id !== requestId)` → `(false)` | 没人守 |
| M531 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 1 次） | `短路-去右侧`：`!S.startRequest \|\| S.startRequest.id !== requestId` → `!S.startRequest ` | 没人守 |
| M532 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 1 次） | `读 S.startRequest`：`S.startRequest` → `null` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '正在确认是否启动' not found in '正在提交…' |
| M533 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 1 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · '正在确认是否启动' not found in '正在提交…' |
| M534 | `reconcileStart` `S.startRequest.state = "reconciling";`（第 1 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 变异不成立（赋值点） |
| M535 | `reconcileStart` `const gen = (S.startRequest.gen \|\| 0) + 1;`（第 1 次） | `短路-去右侧`：`S.startRequest.gen \|\| 0` → `S.startRequest.gen ` | 没人守 |
| M536 | `reconcileStart` `const gen = (S.startRequest.gen \|\| 0) + 1;`（第 1 次） | `读 S.startRequest.gen`：`S.startRequest.gen` → `-1` | 没人守 |
| M537 | `reconcileStart` `S.startRequest.gen = gen;`（第 2 次） | `读 S.startRequest.gen`：`S.startRequest.gen` → `-1` | 变异不成立（赋值点） |
| M538 | `reconcileStart` `clearTimeout(S.startRequest.queryTimer);`（第 1 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 没人守 |
| M539 | `reconcileStart` `text: hint ? "开始请求没有正常返回（" + hint + "），正在向本机确认；请勿重复启动。"`（第 1 次） | `三元-对调`：`? "开始请求没有正常返回（" + hint + "），正在向本机确认；请勿重复启动。"
      : "开始请求没有` → `? "开始请求没有立刻返回，正在向本机确认；请勿重复启动。": "开始请求没有正` | 没人守 |
| M540 | `reconcileStart` `clearTimeout(S.startRequest.queryTimer);`（第 2 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 没人守 |
| M541 | `reconcileStart` `S.startRequest.queryTimer = null;`（第 3 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 变异不成立（赋值点） |
| M542 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 1 次） | `条件-恒假`：`if (!S.startRequest \|\| S.startRequest.id !== requestId \|\` → `(false)` | 没人守 |
| M543 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 1 次） | `短路-去右侧`：`!S.startRequest \|\| S.startRequest.id !== requestId ` → `!S.startRequest ` | 没人守 |
| M544 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 2 次） | `读 S.startRequest`：`S.startRequest` → `null` | 已守 · `test_reconciliation_failure_leaves_visible_unknown_result` · '结果未确认，请勿重复启动' not found in '正在确认是否启动开始请求没有立刻返回，正在向本机确认；请勿重复 |
| M545 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 2 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 已守 · `test_reconciliation_failure_leaves_visible_unknown_result` · '结果未确认，请勿重复启动' not found in '正在确认是否启动开始请求没有立刻返回，正在向本机确认；请勿重复 |
| M546 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 1 次） | `短路-去右侧`：` requestId \|\| S.startRequest.gen !== gen` → ` requestId ` | 没人守 |
| M547 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 3 次） | `读 S.startRequest.gen`：`S.startRequest.gen` → `-1` | 已守 · `test_reconciliation_failure_leaves_visible_unknown_result` · '结果未确认，请勿重复启动' not found in '正在确认是否启动开始请求没有立刻返回，正在向本机确认；请勿重复 |
| M548 | `reconcileStart` `S.startRequest.state = "unknown";`（第 2 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 变异不成立（赋值点） |
| M549 | `reconcileStart` `S.startRequest.queryTimer = setTimeout(() => {`（第 4 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 变异不成立（赋值点） |
| M550 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 2 次） | `条件-恒假`：`if (!S.startRequest \|\| S.startRequest.id !== requestId \|\` → `(false)` | 没人守 |
| M551 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 2 次） | `短路-去右侧`：`!S.startRequest \|\| S.startRequest.id !== requestId ` → `!S.startRequest ` | 没人守 |
| M552 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 3 次） | `读 S.startRequest`：`S.startRequest` → `null` | 没人守 |
| M553 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 3 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 没人守 |
| M554 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 2 次） | `短路-去右侧`：` requestId \|\| S.startRequest.gen !== gen` → ` requestId ` | 没人守 |
| M555 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId \|\| S.startR`（第 4 次） | `读 S.startRequest.gen`：`S.startRequest.gen` → `-1` | 没人守 |
| M556 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 2 次） | `条件-恒假`：`if (!S.startRequest \|\| S.startRequest.id !== requestId)` → `(false)` | 没人守 |
| M557 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 2 次） | `短路-去右侧`：`!S.startRequest \|\| S.startRequest.id !== requestId` → `!S.startRequest ` | 没人守 |
| M558 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 4 次） | `读 S.startRequest`：`S.startRequest` → `null` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · False is not true |
| M559 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 4 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · False is not true |
| M560 | `reconcileStart` `if (S.startRequest.gen !== gen) return;      /* 旧代次迟到：不得替换后来的计划 */`（第 1 次） | `条件-恒假`：`if (S.startRequest.gen !== gen)` → `(false)` | 没人守 |
| M561 | `reconcileStart` `if (S.startRequest.gen !== gen) return;      /* 旧代次迟到：不得替换后来的计划 */`（第 5 次） | `读 S.startRequest.gen`：`S.startRequest.gen` → `-1` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · False is not true |
| M562 | `reconcileStart` `if (state === "accepted") {`（第 1 次） | `条件-恒假`：`if (state === "accepted")` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · False is not true |
| M563 | `reconcileStart` `adoptPlan(S.startRequest.id, res && res.plan_id, res && res.snapshot,`（第 5 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 没人守 |
| M564 | `reconcileStart` `if (state === "rejected") {`（第 1 次） | `条件-恒假`：`if (state === "rejected")` → `(false)` | 没人守 |
| M565 | `reconcileStart` `S.startRequest.state = "rejected";`（第 3 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 变异不成立（赋值点） |
| M566 | `reconcileStart` `showPlanError((res && res.text) \|\| "计划没能开始", [], []);`（第 1 次） | `短路-去右侧`：`(res && res.text) \|\| "计划没能开始"` → `(res && res.text) ` | 没人守 |
| M567 | `reconcileStart` `showPlanError((res && res.text) \|\| "计划没能开始", [], []);`（第 1 次） | `短路-去右侧`：`res && res.text` → `res ` | 没人守 |
| M568 | `reconcileStart` `if (state === "canceled") {`（第 1 次） | `条件-恒假`：`if (state === "canceled")` → `(false)` | 已守 · `test_P03_canceled_reconciliation_releases_the_start_button` · True is not false : 取消是结论，不能一直锁着开始 |
| M569 | `reconcileStart` `S.startRequest.state = "canceled";`（第 4 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 变异不成立（赋值点） |
| M570 | `reconcileStart` `if (state === "pending" && S.startRequest.reconcile < 8) {`（第 1 次） | `条件-恒假`：`if (state === "pending" && S.startRequest.reconcile < 8)` → `(false)` | 没人守 |
| M571 | `reconcileStart` `if (state === "pending" && S.startRequest.reconcile < 8) {`（第 1 次） | `短路-去右侧`：` "pending" && S.startRequest.reconcile < 8` → ` "pending" ` | 没人守 |
| M572 | `reconcileStart` `if (state === "pending" && S.startRequest.reconcile < 8) {`（第 1 次） | `读 S.startRequest.reconcile`：`S.startRequest.reconcile` → `8` | 没人守 |
| M573 | `reconcileStart` `S.startRequest.reconcile += 1;`（第 2 次） | `读 S.startRequest.reconcile`：`S.startRequest.reconcile` → `8` | 变异不成立（赋值点） |
| M574 | `reconcileStart` `S.startRequest.timer = setTimeout(() => reconcileStart(requestId), 200`（第 1 次） | `读 S.startRequest.timer`：`S.startRequest.timer` → `0` | 变异不成立（赋值点） |
| M575 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 3 次） | `条件-恒假`：`if (!S.startRequest \|\| S.startRequest.id !== requestId)` → `(false)` | 没人守 |
| M576 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 3 次） | `短路-去右侧`：`!S.startRequest \|\| S.startRequest.id !== requestId` → `!S.startRequest ` | 没人守 |
| M577 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 5 次） | `读 S.startRequest`：`S.startRequest` → `null` | 已守 · `test_reconciliation_failure_leaves_visible_unknown_result` · '结果未确认，请勿重复启动' not found in '正在确认是否启动开始请求没有立刻返回，正在向本机确认；请勿重复 |
| M578 | `reconcileStart` `if (!S.startRequest \|\| S.startRequest.id !== requestId) return;`（第 6 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 已守 · `test_reconciliation_failure_leaves_visible_unknown_result` · '结果未确认，请勿重复启动' not found in '正在确认是否启动开始请求没有立刻返回，正在向本机确认；请勿重复 |
| M579 | `reconcileStart` `if (S.startRequest.gen !== gen) return;`（第 2 次） | `条件-恒假`：`if (S.startRequest.gen !== gen)` → `(false)` | 没人守 |
| M580 | `reconcileStart` `if (S.startRequest.gen !== gen) return;`（第 6 次） | `读 S.startRequest.gen`：`S.startRequest.gen` → `-1` | 已守 · `test_reconciliation_failure_leaves_visible_unknown_result` · '结果未确认，请勿重复启动' not found in '正在确认是否启动开始请求没有立刻返回，正在向本机确认；请勿重复 |
| M581 | `adoptPlan` `if (S.startRequest && S.startRequest.id === requestId) {`（第 1 次） | `条件-恒假`：`if (S.startRequest && S.startRequest.id === requestId)` → `(false)` | 没人守 |
| M582 | `adoptPlan` `if (S.startRequest && S.startRequest.id === requestId) {`（第 1 次） | `短路-去右侧`：`S.startRequest && S.startRequest.id === requestId` → `S.startRequest ` | 没人守 |
| M583 | `adoptPlan` `if (S.startRequest && S.startRequest.id === requestId) {`（第 1 次） | `读 S.startRequest`：`S.startRequest` → `null` | 没人守 |
| M584 | `adoptPlan` `if (S.startRequest && S.startRequest.id === requestId) {`（第 1 次） | `读 S.startRequest.id`：`S.startRequest.id` → `"__other__"` | 没人守 |
| M585 | `adoptPlan` `S.startRequest.state = "accepted";`（第 1 次） | `读 S.startRequest.state`：`S.startRequest.state` → `"settled"` | 变异不成立（赋值点） |
| M586 | `adoptPlan` `clearTimeout(S.startRequest.queryTimer);`（第 1 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 没人守 |
| M587 | `adoptPlan` `S.startRequest.queryTimer = null;`（第 2 次） | `读 S.startRequest.queryTimer`：`S.startRequest.queryTimer` → `0` | 变异不成立（赋值点） |
| M588 | `adoptPlan` `const id = String(planId \|\| "");`（第 1 次） | `短路-去右侧`：`planId \|\| ""` → `planId ` | 没人守 |
| M589 | `adoptPlan` `const status = String((snapshot && snapshot.status) \|\| (finished ? "`（第 1 次） | `短路-去右侧`：`(snapshot && snapshot.status) \|\| (finished ? "unknown" : "` → `(snapshot && snapshot.status) ` | 没人守 |
| M590 | `adoptPlan` `const status = String((snapshot && snapshot.status) \|\| (finished ? "`（第 1 次） | `短路-去右侧`：`snapshot && snapshot.status` → `snapshot ` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · True is not false : 接纳回来的快照已经结束，不能置忙 |
| M591 | `adoptPlan` `const status = String((snapshot && snapshot.status) \|\| (finished ? "`（第 1 次） | `三元-对调`：`? "unknown" : "running"` → `? "running": "unknown" ` | 没人守 |
| M592 | `adoptPlan` `if (id && (!S.plan.id \|\| S.plan.id !== id)) {`（第 1 次） | `条件-恒假`：`if (id && (!S.plan.id \|\| S.plan.id !== id))` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · None != 'p1' |
| M593 | `adoptPlan` `if (id && (!S.plan.id \|\| S.plan.id !== id)) {`（第 1 次） | `短路-去右侧`：`id && (!S.plan.id \|\| S.plan.id !== id)` → `id ` | 没人守 |
| M594 | `adoptPlan` `if (id && (!S.plan.id \|\| S.plan.id !== id)) {`（第 1 次） | `短路-去右侧`：`!S.plan.id \|\| S.plan.id !== id` → `!S.plan.id ` | 没人守 |
| M595 | `adoptPlan` `S.plan = { id: id, gen: gen, status: terminal ? status : "running", ta`（第 1 次） | `三元-对调`：`? status : "running"` → `? "running": status ` | 没人守 |
| M596 | `adoptPlan` `} else if (gen > (Number(S.plan.gen) \|\| 0)) {`（第 1 次） | `条件-恒假`：`else if (gen > (Number(S.plan.gen) \|\| 0))` → `(false)` | 没人守 |
| M597 | `adoptPlan` `} else if (gen > (Number(S.plan.gen) \|\| 0)) {`（第 1 次） | `短路-去右侧`：`Number(S.plan.gen) \|\| 0` → `Number(S.plan.gen) ` | 没人守 |
| M598 | `adoptPlan` `if ((snapshot && snapshot.tasks \|\| []).length) {`（第 1 次） | `条件-恒假`：`if ((snapshot && snapshot.tasks \|\| []).length)` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · Lists differ: [] != ['t1'] |
| M599 | `adoptPlan` `if ((snapshot && snapshot.tasks \|\| []).length) {`（第 1 次） | `短路-去右侧`：`snapshot && snapshot.tasks ` → `snapshot ` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · Lists differ: [] != ['t1'] |
| M600 | `adoptPlan` `if ((snapshot && snapshot.tasks \|\| []).length) {`（第 1 次） | `短路-去右侧`：` snapshot.tasks \|\| []` → ` snapshot.tasks ` | 没人守 |
| M601 | `adoptPlan` `(snapshot.tasks \|\| []).forEach((task) => {`（第 1 次） | `短路-去右侧`：`snapshot.tasks \|\| []` → `snapshot.tasks ` | 没人守 |
| M602 | `adoptPlan` `const prev = S.plan.tasks.get(key) \|\| null;`（第 1 次） | `短路-去右侧`：` S.plan.tasks.get(key) \|\| null` → ` S.plan.tasks.get(key) ` | 没人守 |
| M603 | `adoptPlan` `if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0`（第 1 次） | `条件-恒假`：`if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0
` → `(false)` | 没人守 |
| M604 | `adoptPlan` `if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0`（第 1 次） | `短路-去右侧`：`prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0
    ` → `prev ` | 没人守 |
| M605 | `adoptPlan` `if (prev && TASK_TERMINAL.indexOf(String(prev.status)) >= 0`（第 1 次） | `短路-去右侧`：` 0
          && TASK_TERMINAL.indexOf(String(merged.status))` → ` 0
          ` | 没人守 |
| M606 | `adoptPlan` `if (prevTries > snapTries) merged.attempts = prevTries;`（第 1 次） | `条件-恒假`：`if (prevTries > snapTries)` → `(false)` | 没人守 |
| M607 | `adoptPlan` `if (terminal) {`（第 1 次） | `条件-恒假`：`if (terminal)` → `(false)` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · False is not true |
| M608 | `adoptPlan` `plan_generation: gen > 0 ? gen : undefined });`（第 1 次） | `三元-对调`：`? gen : undefined ` → `? undefined : gen ` | 没人守 |
| M609 | `adoptPlan` `if (S.plan.id === id && PLAN_TERMINAL.indexOf(S.plan.status) >= 0) {`（第 1 次） | `条件-恒假`：`if (S.plan.id === id && PLAN_TERMINAL.indexOf(S.plan.status)` → `(false)` | 没人守 |
| M610 | `adoptPlan` `if (S.plan.id === id && PLAN_TERMINAL.indexOf(S.plan.status) >= 0) {`（第 1 次） | `短路-去右侧`：` id && PLAN_TERMINAL.indexOf(S.plan.status) >= 0` → ` id ` | 已守 · `test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state` · False is not true |
| M611 | `adoptPlan` `if (info && info.plan) ingestBootstrapPlan({ plan: info.plan });`（第 1 次） | `条件-恒假`：`if (info && info.plan)` → `(false)` | 没人守 |
| M612 | `cancelTask` `if (!S.plan.id \|\| !taskId) return;`（第 1 次） | `条件-恒假`：`if (!S.plan.id \|\| !taskId)` → `(false)` | 没人守 |
| M613 | `cancelTask` `if (!S.plan.id \|\| !taskId) return;`（第 1 次） | `短路-去右侧`：`!S.plan.id \|\| !taskId` → `!S.plan.id ` | 没人守 |
| M614 | `cancelTask` `if (res && res.ok === false) addLog(res.text \|\| "这一场已经结束");`（第 1 次） | `条件-恒假`：`if (res && res.ok === false)` → `(false)` | 没人守 |
| M615 | `cancelTask` `if (res && res.ok === false) addLog(res.text \|\| "这一场已经结束");`（第 1 次） | `短路-去右侧`：`res.text \|\| "这一场已经结束"` → `res.text ` | 没人守 |
| M616 | `stopAskOpen` `const ask = $("#plan-stop-ask");`（第 1 次） | `短路-去右侧`：`
  return !!ask && !ask.hidden` → `
  return !!ask ` | 没人守 |
| M617 | `openStopAsk` `if (!ask \|\| !ask.hidden) return;`（第 1 次） | `条件-恒假`：`if (!ask \|\| !ask.hidden)` → `(false)` | 没人守 |
| M618 | `openStopAsk` `if (!ask \|\| !ask.hidden) return;`（第 1 次） | `短路-去右侧`：`!ask \|\| !ask.hidden` → `!ask ` | 没人守 |
| M619 | `closeStopAsk` `if (!ask \|\| ask.hidden) return;`（第 1 次） | `条件-恒假`：`if (!ask \|\| ask.hidden)` → `(false)` | 没人守 |
| M620 | `closeStopAsk` `if (!ask \|\| ask.hidden) return;`（第 1 次） | `短路-去右侧`：`!ask \|\| ask.hidden` → `!ask ` | 没人守 |
| M621 | `closeStopAsk` `if (restoreFocus !== false && opener && !opener.disabled) opener.focus`（第 1 次） | `条件-恒假`：`if (restoreFocus !== false && opener && !opener.disabled)` → `(false)` | 已守 · `test_escape_closes_and_returns_focus_to_stop_button` · '#btn-stop-keep' != '#btn-stop' |
| M622 | `closeStopAsk` `if (restoreFocus !== false && opener && !opener.disabled) opener.focus`（第 1 次） | `短路-去右侧`：` opener && !opener.disabled` → ` opener ` | 没人守 |
| M623 | `stopAskKey` `if (key === "Escape") { event.preventDefault(); closeStopAsk(true); re`（第 1 次） | `条件-恒假`：`if (key === "Escape")` → `(false)` | 已守 · `test_escape_closes_and_returns_focus_to_stop_button` · False is not true : Esc 必须关闭弹层 |
| M624 | `stopAskKey` `if (key === "Tab") {`（第 1 次） | `条件-恒假`：`if (key === "Tab")` → `(false)` | 已守 · `test_tab_cycles_between_the_two_buttons_only` · Lists differ: ['#btn-stop-keep', '#btn-stop-keep', '#btn-sto |
| M625 | `stopAskKey` `const next = at < 0 ? (event.shiftKey ? yes : keep)`（第 1 次） | `三元-对调`：`? (event.shiftKey ? yes : keep)
      : order[(at + (event.s` → `? order[(at + (event.shiftKey ? order.le` | 已守 · `test_tab_cycles_between_the_two_buttons_only` · Lists differ: ['#btn-stop-keep', '#btn-stop-keep', '#btn-sto |
| M626 | `stopAskKey` `const next = at < 0 ? (event.shiftKey ? yes : keep)`（第 1 次） | `三元-对调`：`? yes : keep` → `? keep: yes ` | 没人守 |
| M627 | `stopAskKey` `: order[(at + (event.shiftKey ? order.length - 1 : 1)) % order.length]`（第 1 次） | `三元-对调`：`? order.length - 1 : 1` → `? 1: order.length - 1 ` | 没人守 |
| M628 | `stopAskKey` `if ((event.ctrlKey && (key === "f" \|\| key === "F")) \|\| key === "/"`（第 1 次） | `条件-恒假`：`if ((event.ctrlKey && (key === "f" \|\| key === "F")) \|\| k` → `(false)` | 已守 · `test_enter_and_search_keys_do_not_reach_background` · False is not true : 背景快捷键被弹层吞掉 |
| M629 | `stopAskKey` `if ((event.ctrlKey && (key === "f" \|\| key === "F")) \|\| key === "/"`（第 1 次） | `短路-去右侧`：`(event.ctrlKey && (key === "f" \|\| key === "F")) \|\| key =` → `(event.ctrlKey && (key === "f" \|\| key ` | 已守 · `test_enter_and_search_keys_do_not_reach_background` · False is not true : 背景快捷键被弹层吞掉 |
| M630 | `stopAskKey` `if ((event.ctrlKey && (key === "f" \|\| key === "F")) \|\| key === "/"`（第 1 次） | `短路-去右侧`：`event.ctrlKey && (key === "f" \|\| key === "F")` → `event.ctrlKey ` | 没人守 |
| M631 | `stopAskKey` `if ((event.ctrlKey && (key === "f" \|\| key === "F")) \|\| key === "/"`（第 1 次） | `短路-去右侧`：` "f" \|\| key === "F"` → ` "f" ` | 没人守 |
| M632 | `stopPlan` `if (!S.plan.id) return;`（第 1 次） | `条件-恒假`：`if (!S.plan.id)` → `(false)` | 已守 · `test_no_plan_means_no_prompt` · False is not true : 没有计划就没有可停止的东西 |
| M633 | `confirmStopPlan` `if (!S.busy \|\| S.stopping) return;`（第 1 次） | `条件-恒假`：`if (!S.busy \|\| S.stopping)` → `(false)` | 已守 · `test_confirm_after_plan_ended_does_not_call_backend` · Lists differ: ['p1', 'p1'] != ['p1'] |
| M634 | `confirmStopPlan` `if (!S.busy \|\| S.stopping) return;`（第 1 次） | `短路-去右侧`：`!S.busy \|\| S.stopping` → `!S.busy ` | 已守 · `test_confirm_runs_existing_stop_flow_once` · Lists differ: ['p1', 'p1'] != ['p1'] |
| M635 | `confirmStopPlan` `if (!S.busy \|\| S.stopping) return;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_confirm_runs_existing_stop_flow_once` · Lists differ: [] != ['p1'] |
| M636 | `confirmStopPlan` `if (!S.busy \|\| S.stopping) return;`（第 1 次） | `读 S.stopping`：`S.stopping` → `false` | 已守 · `test_confirm_runs_existing_stop_flow_once` · Lists differ: ['p1', 'p1'] != ['p1'] |
| M637 | `noteStartedFromPhone` `const list = Array.isArray(tasks) ? tasks : [];`（第 1 次） | `三元-对调`：`? tasks : []` → `? []: tasks ` | 已守 · `test_phone_started_plan_logs_one_start_line` · Lists differ: ['从手机开始了报名计划'] != ['从手机开始了报名计划：2 场预报名等开放'] |
| M638 | `noteStartedFromPhone` `const instant = list.filter((task) => String(task && task.signup_mode `（第 1 次） | `短路-去右侧`：` task.signup_mode \|\| ""` → ` task.signup_mode ` | 没人守 |
| M639 | `noteStartedFromPhone` `const pre = list.filter((task) => String(task && task.signup_mode \|\|`（第 2 次） | `短路-去右侧`：` task.signup_mode \|\| ""` → ` task.signup_mode ` | 没人守 |
| M640 | `noteStartedFromPhone` `const summary = [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名`（第 1 次） | `三元-对调`：`? instant + " 场立即报名" : ""` → `? "": instant + " 场立即报名" ` | 已守 · `test_phone_started_plan_logs_one_start_line` · Lists differ: ['从手机开始了报名计划：0 场立即报名，2 场预报名等开放'] != ['从手机开始了报名 |
| M641 | `noteStartedFromPhone` `const summary = [instant ? instant + " 场立即报名" : "", pre ? pre + " 场预报名`（第 1 次） | `三元-对调`：`? pre + " 场预报名等开放" : ""` → `? "": pre + " 场预报名等开放" ` | 已守 · `test_phone_started_plan_logs_one_start_line` · Lists differ: ['从手机开始了报名计划'] != ['从手机开始了报名计划：2 场预报名等开放'] |
| M642 | `noteStartedFromPhone` `addLogFresh("从手机开始了报名计划" + (summary ? "：" + summary : ""));`（第 1 次） | `三元-对调`：`? "：" + summary : ""` → `? "": "：" + summary ` | 已守 · `test_phone_started_plan_logs_one_start_line` · Lists differ: ['从手机开始了报名计划'] != ['从手机开始了报名计划：2 场预报名等开放'] |
| M643 | `modifyPlan` `if (!S.busy \|\| !S.plan.id \|\| S.stopping \|\| planLate()) return;`（第 1 次） | `条件-恒假`：`if (!S.busy \|\| !S.plan.id \|\| S.stopping \|\| planLate())` → `(false)` | 没人守 |
| M644 | `modifyPlan` `if (!S.busy \|\| !S.plan.id \|\| S.stopping \|\| planLate()) return;`（第 1 次） | `短路-去右侧`：`!S.busy \|\| !S.plan.id ` → `!S.busy ` | 没人守 |
| M645 | `modifyPlan` `if (!S.busy \|\| !S.plan.id \|\| S.stopping \|\| planLate()) return;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 已守 · `test_modify_plan_logs_the_paused_line_with_the_draft_count` · 0 != 1 : 停止成功后才写，且只写一句：[] |
| M646 | `modifyPlan` `if (!S.busy \|\| !S.plan.id \|\| S.stopping \|\| planLate()) return;`（第 1 次） | `短路-去右侧`：` !S.plan.id \|\| S.stopping ` → ` !S.plan.id ` | 没人守 |
| M647 | `modifyPlan` `if (!S.busy \|\| !S.plan.id \|\| S.stopping \|\| planLate()) return;`（第 1 次） | `短路-去右侧`：` S.stopping \|\| planLate()` → ` S.stopping ` | 没人守 |
| M648 | `modifyPlan` `if (!S.busy \|\| !S.plan.id \|\| S.stopping \|\| planLate()) return;`（第 1 次） | `读 S.stopping`：`S.stopping` → `false` | 没人守 |
| M649 | `modifyPlan` `if (["queued", "waiting"].indexOf(String(task.status \|\| "")) >= 0) k`（第 1 次） | `条件-恒假`：`if (["queued", "waiting"].indexOf(String(task.status \|\| ""` → `(false)` | 已守 · `test_modify_plan_logs_the_paused_line_with_the_draft_count` · 0 != 1 : 停止成功后才写，且只写一句：['正在停止计划：结束还在重试的场次…', '计划已暂停：0 场放回草稿修 |
| M650 | `modifyPlan` `if (["queued", "waiting"].indexOf(String(task.status \|\| "")) >= 0) k`（第 1 次） | `短路-去右侧`：`task.status \|\| ""` → `task.status ` | 没人守 |
| M651 | `restoreEditedPlan` `if (S.editing && Array.isArray(S.editing.ids)) {`（第 1 次） | `条件-恒假`：`if (S.editing && Array.isArray(S.editing.ids))` → `(false)` | 已守 · `test_restore_edited_plan_sends_original_selection` · Lists differ: ['a2'] != ['a1'] |
| M652 | `restoreEditedPlan` `if (S.editing && Array.isArray(S.editing.ids)) {`（第 1 次） | `短路-去右侧`：`S.editing && Array.isArray(S.editing.ids)` → `S.editing ` | 没人守 |
| M653 | `restoreEditedPlan` `if (S.editing && Array.isArray(S.editing.ids)) {`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_restore_edited_plan_sends_original_selection` · Lists differ: ['a2'] != ['a1'] |
| M654 | `restoreEditedPlan` `if (S.editing && Array.isArray(S.editing.ids)) {`（第 2 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_restore_edited_plan_sends_original_selection` · Lists differ: ['a2'] != ['a1'] |
| M655 | `restoreEditedPlan` `S.editing.ids.forEach((id) => {`（第 3 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_restore_edited_plan_sends_original_selection` · JS 行为测试崩溃：TypeError: Cannot read properties of undefined (re |
| M656 | `restoreEditedPlan` `if (item && isEligibleForPlan(item)) S.selected.add(String(id));`（第 1 次） | `条件-恒假`：`if (item && isEligibleForPlan(item))` → `(false)` | 已守 · `test_restore_edited_plan_sends_original_selection` · Lists differ: [] != ['a1'] |
| M657 | `reselectFailed` `if (S.busy) return;`（第 1 次） | `条件-恒假`：`if (S.busy)` → `(false)` | 没人守 |
| M658 | `reselectFailed` `if (S.busy) return;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M659 | `finishResult` `if (typeof setPlanOpen === "function") setPlanOpen(false);`（第 1 次） | `条件-恒假`：`if (typeof setPlanOpen === "function")` → `(false)` | 没人守 |
| M660 | `doStopPlan` `if (!S.plan.id) return;`（第 1 次） | `条件-恒假`：`if (!S.plan.id)` → `(false)` | 没人守 |
| M661 | `doStopPlan` `const wasEditing = !!S.editing;`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 已守 · `test_stop_rejection_clears_stopping_and_editing` · '停止没成功，计划继续运行' not found in '正在停止计划：结束还在重试的场次…\|暂时不能停' |
| M662 | `doStopPlan` `if (wasEditing) {`（第 1 次） | `条件-恒假`：`if (wasEditing)` → `(false)` | 已守 · `test_stop_rejection_clears_stopping_and_editing` · '停止没成功，计划继续运行' not found in '正在停止计划：结束还在重试的场次…\|暂时不能停' |
| M663 | `doStopPlan` `if (res && res.ok === false) stopFailed(res.text \|\| "当前没有这个计划");`（第 1 次） | `条件-恒假`：`if (res && res.ok === false)` → `(false)` | 已守 · `test_stop_rejection_clears_stopping_and_editing` · '正在停止…' != '停止计划' |
| M664 | `doStopPlan` `if (res && res.ok === false) stopFailed(res.text \|\| "当前没有这个计划");`（第 1 次） | `短路-去右侧`：`res.text \|\| "当前没有这个计划"` → `res.text ` | 没人守 |
| M665 | `doLogin` `if (S.busy) return;`（第 1 次） | `条件-恒假`：`if (S.busy)` → `(false)` | 没人守 |
| M666 | `doLogin` `if (S.busy) return;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M667 | `doLogin` `if (termsLocked()) {`（第 1 次） | `条件-恒假`：`if (termsLocked())` → `(false)` | 没人守 |
| M668 | `doLogin` `if (!S.terms.declined && !S.terms.unknown) openTerms();`（第 1 次） | `条件-恒假`：`if (!S.terms.declined && !S.terms.unknown)` → `(false)` | 没人守 |
| M669 | `doLogin` `if (!S.terms.declined && !S.terms.unknown) openTerms();`（第 1 次） | `短路-去右侧`：`!S.terms.declined && !S.terms.unknown` → `!S.terms.declined ` | 没人守 |
| M670 | `doLogin` `if (res && res.demo) {`（第 1 次） | `条件-恒假`：`if (res && res.demo)` → `(false)` | 已守 · `test_login_start_reports_failure_and_keeps_previous_session` · '演示模式不登录' not found in '' |
| M671 | `doLogin` `setResult({ ok: "partial", title: "演示模式不登录", text: res.text \|\| "演示模式`（第 1 次） | `短路-去右侧`：` res.text \|\| "演示模式不联网。" ` → ` res.text ` | 没人守 |
| M672 | `doLogin` `if (!res \|\| res.ok === false) {`（第 1 次） | `条件-恒假`：`if (!res \|\| res.ok === false)` → `(false)` | 已守 · `test_login_start_reports_failure_and_keeps_previous_session` · '登录没能开始' not found in '' |
| M673 | `doLogin` `if (res && res.error && RUNTIME_ERRORS[res.error]) {`（第 1 次） | `条件-恒假`：`if (res && res.error && RUNTIME_ERRORS[res.error])` → `(false)` | 已守 · `test_login_start_reports_failure_and_keeps_previous_session` · '登录没能开始' unexpectedly found in '登录没能开始x' |
| M674 | `doLogin` `setResult({ ok: false, title: "登录没能开始", text: (res && res.text) \|\| "`（第 1 次） | `短路-去右侧`：` (res && res.text) \|\| "再点一次「登录」试试。" ` → ` (res && res.text) ` | 没人守 |
| M675 | `doLogin` `setResult({ ok: false, title: "登录没能开始", text: (res && res.text) \|\| "`（第 1 次） | `短路-去右侧`：`res && res.text` → `res ` | 已守 · `test_login_start_reports_failure_and_keeps_previous_session` · '窗口没起来' not found in '登录没能开始[object Object]' |
| M676 | `handleDone` `if (data.kind === "login") {`（第 1 次） | `条件-恒假`：`if (data.kind === "login")` → `(false)` | 没人守 |
| M677 | `handleDone` `if (data.ok) {`（第 1 次） | `条件-恒假`：`if (data.ok)` → `(false)` | 没人守 |
| M678 | `handleDone` `refresh(true, S.items.length ? { background: true } : undefined);`（第 1 次） | `三元-对调`：`? { background: true } : undefined` → `? undefined: { background: true } ` | 没人守 |
| M679 | `handleDone` `if (data.kind === "grab") {`（第 1 次） | `条件-恒假`：`if (data.kind === "grab")` → `(false)` | 没人守 |
| M680 | `handleDone` `if (data.ok) setResult({ ok: true, title: "报名成功：" + stripLabel(data.la`（第 2 次） | `条件-恒假`：`if (data.ok)` → `(false)` | 没人守 |
| M681 | `loginFailCopy` `const raw = String(reason \|\| "");`（第 1 次） | `短路-去右侧`：`reason \|\| ""` → `reason ` | 没人守 |
| M682 | `loginFailCopy` `if (/窗口被关掉/.test(raw)) return { title: "登录窗口被关掉了", text: "登录还没完成，窗口就关了`（第 1 次） | `条件-恒假`：`if (/窗口被关掉/.test(raw))` → `(false)` | 没人守 |
| M683 | `loginFailCopy` `if (/仍未检测到登录成功/.test(raw)) return { title: "等了 10 分钟还没登录成功", text: "浏览`（第 1 次） | `条件-恒假`：`if (/仍未检测到登录成功/.test(raw))` → `(false)` | 没人守 |
| M684 | `loginFailCopy` `if (/打不开登录页/.test(raw)) return { title: "打不开学校的登录页", text: "检查网络、校园网或代`（第 1 次） | `条件-恒假`：`if (/打不开登录页/.test(raw))` → `(false)` | 没人守 |
| M685 | `loginFailCopy` `if (/接口校验失败/.test(raw)) return { title: "登录后学校那边没校验通过", text: "登录状态存下来`（第 1 次） | `条件-恒假`：`if (/接口校验失败/.test(raw))` → `(false)` | 没人守 |
| M686 | `loginFailCopy` `if (/没找到可用的浏览器/.test(raw)) return { title: "没找到能用的浏览器", text: "这台电脑上要有`（第 1 次） | `条件-恒假`：`if (/没找到可用的浏览器/.test(raw))` → `(false)` | 没人守 |
| M687 | `loginFailCopy` `return { title: "登录没完成", text: cleanReason(raw) \|\| "原因不明。可以再试一次，或者看看`（第 1 次） | `短路-去右侧`：` cleanReason(raw) \|\| "原因不明。可以再试一次，或者看看运行记录。" ` → ` cleanReason(raw) ` | 没人守 |

### controllers/tick.js（3 条）

| 编号 | 定位：函数 / 那一行的文字 / 第几次出现 | 变异写法 | 补测后 |
|---|---|---|---|
| M688 | `tick` `const runPhase = S.busy ? runHeadKey() : null;`（第 1 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |
| M689 | `tick` `if (S.editing) paintEditNote();`（第 1 次） | `读 S.editing`：`S.editing` → `false` | 没人守 |
| M690 | `tick` `if (S.busy) paintRunPanel();`（第 2 次） | `读 S.busy`：`S.busy` → `false` | 没人守 |

## 还没人守的分布

下面这些候选补测后仍然跑不出红：要么现有用例没走到那条分支，要么沙箱缺能触发它的手段。逐条编号见上表（结论列写「没人守」）。

| 文件 · 函数 | 条数 |
|---|---:|
| plan.js · `reconcileStart` | 29 |
| plan.js · `startPlan` | 28 |
| plan-panel.js · `updateControls` | 23 |
| plan.js · `adoptPlan` | 23 |
| plan-panel.js · `taskHtml` | 20 |
| plan-panel.js · `paintRunPanel` | 14 |
| plan.js · `handleTask` | 10 |
| task-display.js · `taskDisplayItem` | 9 |
| task-display.js · `executionView` | 8 |
| plan-panel.js · `startBlocker` | 7 |
| plan.js · `planOutcome` | 7 |
| plan.js · `doLogin` | 7 |
| plan.js · `loginFailCopy` | 7 |
| plan.js · `handlePlan` | 6 |
| plan.js · `modifyPlan` | 6 |
| plan-panel.js · `paintBoardActions` | 5 |
| plan.js · `mergeTask` | 5 |
| task-display.js · `taskDisplayPhase` | 5 |
| plan.js · `handleDone` | 5 |
| plan-panel.js · `runCaption` | 4 |
| plan-panel.js · `paintEditNote` | 4 |
| plan-panel.js · `resultMode` | 4 |
| plan-panel.js · `resultCounts` | 4 |
| plan.js · `cancelTask` | 4 |
| plan.js · `stopAskKey` | 4 |
| plan-panel.js · `boardTargetItem` | 3 |
| plan-panel.js · `paintWhy` | 3 |
| plan-panel.js · `planLate` | 3 |
| plan-panel.js · `resultView` | 3 |
| plan.js · `unknownLabel` | 3 |
| task-display.js · `effectiveRetryDeadline` | 3 |
| plan.js · `closeStopAsk` | 3 |
| tick.js · `tick` | 3 |
| plan-panel.js · `setBoardTag` | 2 |
| plan-panel.js · `editNoteText` | 2 |
| plan-panel.js · `reselectableIds` | 2 |
| plan-panel.js · `paintPlan` | 2 |
| plan.js · `planEventOwns` | 2 |
| plan.js · `admitPlanEvent` | 2 |
| task-display.js · `taskModePrefix` | 2 |
| task-display.js · `taskPrepared` | 2 |
| task-display.js · `taskDisplayDetail` | 2 |
| plan.js · `openStopAsk` | 2 |
| plan.js · `noteStartedFromPhone` | 2 |
| plan.js · `reselectFailed` | 2 |
| plan.js · `doStopPlan` | 2 |
| plan-panel.js · `runHeadKey` | 1 |
| plan-panel.js · `verifyTask` | 1 |
| plan-panel.js · `paintResultPanel` | 1 |
| plan-panel.js · `stopReasonText` | 1 |
| plan.js · `maxPlanGen` | 1 |
| plan.js · `advancePlanStatus` | 1 |
| plan.js · `syncResultSelection` | 1 |
| plan.js · `resultPageOpen` | 1 |
| task-display.js · `taskDisplayLabel` | 1 |
| task-display.js · `verifiedSigned` | 1 |
| task-display.js · `submittingDetail` | 1 |
| plan.js · `stopAskOpen` | 1 |
| plan.js · `restoreEditedPlan` | 1 |
| plan.js · `finishResult` | 1 |
