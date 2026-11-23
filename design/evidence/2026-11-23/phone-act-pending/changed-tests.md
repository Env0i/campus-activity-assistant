# 手机页开始前举办时间检查变更用例清单

## 一、放行调整的既有旧用例（仅补夹具举办时间，期望断言一字未改）

七条旧用例原本被勾选或已报名的活动夹具未写 `act_start`、`act_end`，测试意图均与举办时间无关；开始前新增举办时间检查后会在拦截与底栏副题处触发，故仅给对应活动夹具补上互不重叠的合法 `act_start` / `act_end`，所有期望断言保持不变：

1. `test_phone_ui.SheetsOpsDomTests.test_review_remove_toggles_off_and_closes_when_empty`（`local/tests/test_phone_ui.py`）
   - 改前：`a1`（`sign_start: "2026-11-08 20:00:00"`）、`a2`（`sign_start: "2026-11-09 09:00:00"`）均未写举办时间。
   - 改后：分别补 `act_start: "2026-11-11 09:00:00", act_end: "2026-11-11 10:00:00"` 与 `act_start: "2026-11-11 11:00:00", act_end: "2026-11-11 12:00:00"`。
   - 原因：夹具缺举办时间，开始前新门禁会拦，与用例要测的核对移除无关。
2. `test_phone_ui.ResultTermsDomTests.test_reselect_skips_expired_real_shape_task_via_dom`（`local/tests/test_phone_ui.py`）
   - 改前：`exp` 与 `fut` 均未写举办时间。
   - 改后：`exp` 补 `act_start: "2026-11-21 09:00:00", act_end: "2026-11-21 10:00:00"`，`fut` 补 `act_start: "2026-11-21 11:00:00", act_end: "2026-11-21 12:00:00"`。
   - 原因：夹具缺举办时间，开始前新门禁会拦，与用例要测的重选跳过已截止场次无关。
3. `test_phone_ui.ExceptionStatesTests.test_login_expired_alert_and_bar_point_to_relogin`（`local/tests/test_phone_ui.py`）
   - 改前：`a1` 未写举办时间。
   - 改后：`a1` 补 `act_start: "2026-11-11 09:00:00", act_end: "2026-11-11 10:00:00"`。
   - 原因：夹具缺举办时间，开始前新门禁会拦，与用例要测的登录失效告警和底栏指向重登无关。
4. `test_phone_ui.ExceptionStatesTests.test_pc_list_error_alert_hides_bar_until_recovered`（`local/tests/test_phone_ui.py`）
   - 改前：`a1` 未写举办时间。
   - 改后：`a1` 补 `act_start: "2026-11-11 09:00:00", act_end: "2026-11-11 10:00:00"`。
   - 原因：夹具缺举办时间，恢复列表后底栏副题会被新门禁文案覆盖，与用例要测的电脑列表加载失败恢复无关。
5. `test_phone_ui.ExceptionStatesTests.test_clock_unavailable_blocks_start_and_shows_pending_calibration`（`local/tests/test_phone_ui.py`）
   - 改前：`a1` 未写举办时间。
   - 改后：`a1` 补 `act_start: "2026-11-11 09:00:00", act_end: "2026-11-11 10:00:00"`。
   - 原因：夹具缺举办时间，校准恢复后开始仍会被新门禁拦住，与用例要测的时钟待校准及恢复无关。
6. `test_phone_ui.WorkbenchPhoneTests.test_terms_not_accepted_keeps_the_phone_read_only`（`local/tests/test_phone_ui.py`）
   - 改前：`a1` 未写举办时间。
   - 改后：`a1` 补 `act_start: "2026-11-11 09:00:00", act_end: "2026-11-11 10:00:00"`。
   - 原因：夹具缺举办时间，同意条款后开始与底栏副题会被新门禁拦住，与用例要测的条款门禁及恢复无关。
7. `test_phone_ui.WorkbenchPhoneTests.test_review_lists_the_plan_and_the_same_reminders`（`local/tests/test_phone_ui.py`）
   - 改前：`ui.ingest` 传入的 `activities[0]`（`a1`）未写举办时间。
   - 改后：仅给 `ui.ingest` 的 `a1` 补 `act_start: "2026-11-11 09:00:00", act_end: "2026-11-11 10:00:00"`（`PhoneModel.reviewBatches` 单测用的 `picked` 夹具保持不变）。
   - 原因：夹具缺举办时间，点开始时新门禁会拦住核对面板，与用例要测的核对面板批次和开始前提醒无关。

## 二、新增用例（`local/tests/test_phone_ui.py` · `ActPendingBlockTests`）

- `test_phone_ui.ActPendingBlockTests.test_act_block_table`
  - 表驱动验证 `PhoneModel.actBlock(items, selectedIds)`：空选择、已选缺时间、已选齐全但已报名缺时间、两者都缺时已选优先、全部齐全五种情形。
- `test_phone_ui.ActPendingBlockTests.test_act_block_text_and_can_start`
  - 验证 `PhoneModel.actBlockText` 的 `null`、单场/多场、`selected`/`signed` 及首场名称超过 12 字截断加省略号；验证其余门禁均通过时 `PhoneModel.canStart` 因 `actBlock` 返回 `false`，补齐后返回 `true`。
- `test_phone_ui.ActPendingBlockTests.test_dom_selected_pending_shows_bar_and_row_and_recovers_on_uncheck`
  - 验证已选缺举办时间活动时，底栏副题写「还差一步：已选的「…」举办时间待公布，先取消勾选」且主按钮禁用；列表行在 `pre` 与 `open` 状态缺举办时间均写「举办时间待公布」；通过复选框取消勾选该场后，底栏副题与主按钮恢复。
- `test_phone_ui.ActPendingBlockTests.test_dom_signed_pending_blocks_bar_and_start`
  - 验证已选活动齐全但存在缺举办时间的已报名活动时，底栏副题写「还差一步：已报名的「…」缺少举办时间，暂时开始不了」且主按钮禁用。
